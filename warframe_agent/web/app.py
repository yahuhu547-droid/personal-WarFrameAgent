from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Literal

import httpx
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pathlib import Path

from .. import config
from ..chat import ChatAgent, build_item_context_result
from ..dictionary import normalize_lookup_key, normalize_market_id
from ..market import fetch_orders, fetch_orders_async, best_sellers, best_buyers, get_max_rank_from_orders
from ..goals import create_goal, plan_for_goal, execute_plan, record_trade_outcome
from ..memory import AgentMemory, PriceAlert, MEMORY_PATH
from ..monitor import PriceMonitor, AlertNotification, WatchNotification, EnrichedNotification, ProactivePush
from ..names import display_item_name
from ..price_history import PriceHistoryDB
from ..trade_history import TradeHistoryDB
from ..formatter import build_whisper
from ..push import WxPusher, PushConfig, should_send_daily_report, WXPUSHER_QR_API
from ..feishu import FeishuBot, FeishuConfig

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    inject_custom_aliases()
    setup_monitor()
    # 启动飞书 WebSocket 连接
    if feishu_bot.available:
        feishu_bot.start()
    # 预热缓存（在线程池中执行避免阻塞启动）
    await asyncio.gather(
        asyncio.to_thread(_load_export_file, "ExportRelicArcane_en.json"),
        asyncio.to_thread(_load_export_file, "ExportUpgrades_en.json"),
        asyncio.to_thread(_load_wiki_json, "Warframes.json"),
        asyncio.to_thread(_load_wiki_json, "Weapons.json"),
        asyncio.to_thread(_load_wiki_json, "Mods.json"),
        asyncio.to_thread(_load_zh_names, "Warframes"),
        asyncio.to_thread(_load_zh_names, "Weapons"),
        asyncio.to_thread(_load_zh_names, "Upgrades"),
        asyncio.to_thread(_preload_relic_drop_data),
        asyncio.to_thread(_load_relic_vault_status),
        asyncio.to_thread(_load_relic_sources),
    )
    yield
    try:
        feishu_bot.stop()
    except Exception:
        pass
    try:
        monitor.stop()
    except Exception:
        pass


app = FastAPI(title="Warframe Trading Agent API", lifespan=lifespan)

# 后台任务跟踪
import time as _time
_bg_tasks: dict[str, dict] = {}  # task_id -> {"status": "running"|"done"|"error", "result": ..., "error": ..., "created_at": float}
_BG_TASK_TTL = 3600  # 1 hour


def _evict_old_bg_tasks():
    """清理超过 TTL 的后台任务，防止内存泄漏。"""
    now = _time.time()
    expired = [k for k, v in _bg_tasks.items() if now - v.get("created_at", now) > _BG_TASK_TTL]
    for k in expired:
        del _bg_tasks[k]


class NoCacheAPIMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(NoCacheAPIMiddleware)

chat_agent = ChatAgent()
monitor = PriceMonitor()
price_db = PriceHistoryDB()
trade_db = TradeHistoryDB()
ws_connections: list[WebSocket] = []

# WxPusher 微信推送
push_config = PushConfig.load()
push_client = WxPusher(push_config)

# 飞书机器人（WebSocket 长连接模式）
feishu_config = FeishuConfig.load()

def _feishu_on_message(user_text: str, message_id: str) -> str:
    """飞书消息回调：同步调用智能体"""
    return chat_agent.answer(user_text)

feishu_bot = FeishuBot(feishu_config, on_message=_feishu_on_message)

# 自定义别名存储
CUSTOM_ALIASES_PATH = Path(__file__).parent.parent.parent / "data" / "custom_aliases.json"

# 物品类型和等级缓存
_item_type_cache: dict[str, dict] = {}
_export_file_cache: dict[str, dict] = {}

# 大文件模块级缓存
_relic_drop_data_cache: dict = {}
_relic_sources_cache: dict = {}


def _preload_relic_drop_data() -> dict:
    """预加载遗物掉落数据到缓存"""
    if not _relic_drop_data_cache:
        relic_path = config.DATA_DIR / "relics_drop_data.json"
        if relic_path.exists():
            try:
                with relic_path.open("r", encoding="utf-8") as f:
                    _relic_drop_data_cache.update(json.load(f))
            except Exception:
                pass
    return _relic_drop_data_cache


def _load_relic_sources() -> dict:
    """带缓存的遗物来源数据加载"""
    if not _relic_sources_cache:
        sources_path = config.DATA_DIR / "relic_sources.json"
        if sources_path.exists():
            try:
                with sources_path.open("r", encoding="utf-8") as f:
                    _relic_sources_cache.update(json.load(f))
            except Exception:
                pass
    return _relic_sources_cache


async def _load_memory_async() -> AgentMemory:
    return await asyncio.to_thread(AgentMemory.load, MEMORY_PATH)


async def _save_memory_async(memory: AgentMemory) -> None:
    await asyncio.to_thread(memory.save, MEMORY_PATH)


def _load_export_file(filename: str) -> dict:
    """带文件级缓存的导出文件加载"""
    if filename in _export_file_cache:
        return _export_file_cache[filename]
    export_dir = Path(__file__).parent.parent.parent / "data" / "export"
    try:
        with (export_dir / filename).open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        _export_file_cache[filename] = data
        return data
    except Exception:
        return {}


def get_item_type_info(item_id: str) -> dict | None:
    """获取物品类型和最大等级信息"""
    if item_id in _item_type_cache:
        return _item_type_cache[item_id]

    item_id_lower = item_id.lower()

    # 检查是否是赋能 (Arcane)
    if item_id_lower.startswith("arcane_"):
        try:
            data = _load_export_file("ExportRelicArcane_en.json")
            for item in data.get("ExportRelicArcane", []):
                unique_name = item.get("uniqueName", "").lower()
                name = item.get("name", "").lower().replace(" ", "_")
                if item_id_lower in unique_name or item_id_lower in name:
                    level_stats = item.get("levelStats", [])
                    max_rank = len(level_stats) - 1 if level_stats else 5
                    result = {
                        "type": "arcane",
                        "type_display": "赋能",
                        "max_rank": max_rank,
                        "rarity": item.get("rarity", "RARE"),
                    }
                    _item_type_cache[item_id] = result
                    return result
        except Exception:
            pass
        # 默认赋能等级
        result = {"type": "arcane", "type_display": "赋能", "max_rank": 5, "rarity": "RARE"}
        _item_type_cache[item_id] = result
        return result

    # 检查是否是 Mod
    try:
        data = _load_export_file("ExportUpgrades_en.json")
        for item in data.get("ExportUpgrades", []):
            unique_name = item.get("uniqueName", "").lower()
            name = item.get("name", "").lower().replace(" ", "_")
            if item_id_lower in unique_name or item_id_lower in name:
                level_stats = item.get("levelStats", [])
                max_rank = len(level_stats) - 1 if level_stats else 10
                result = {
                    "type": "mod",
                    "type_display": "Mod",
                    "max_rank": max_rank,
                    "rarity": item.get("rarity", "COMMON"),
                }
                _item_type_cache[item_id] = result
                return result
    except Exception:
        pass

    # 不是赋能或Mod
    return None


def load_custom_aliases() -> dict[str, str]:
    if not CUSTOM_ALIASES_PATH.exists():
        return {}
    try:
        with CUSTOM_ALIASES_PATH.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_custom_aliases(aliases: dict[str, str]) -> None:
    CUSTOM_ALIASES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CUSTOM_ALIASES_PATH.open("w", encoding="utf-8") as f:
        json.dump(aliases, f, ensure_ascii=False, indent=2)


def inject_custom_aliases() -> None:
    """将自定义别名注入到 ChatAgent 的 resolver 中"""
    aliases = load_custom_aliases()
    for name, item_id in aliases.items():
        key = normalize_lookup_key(name)
        if key and item_id:
            chat_agent.resolver.aliases[key] = normalize_market_id(item_id)


# ===== 杜卡特计算器 =====

# 杜卡特价值映射 (Prime 部件稀有度 → 杜卡特值)
# 基于 Warframe 游戏内实际杜卡特价值
DUCAT_RARITY_MAP = {
    "common": 15,      # 铜色 (Bronze)
    "uncommon": 45,    # 银色 (Silver)
    "rare": 100,       # 金色 (Gold)
    "legendary": 100,  # 传说级
}

# 常见 Prime 部件的杜卡特价值（静态映射，作为备用）
STATIC_DUCAT_VALUES = {
    # 战甲 Prime 部件
    "ash_prime_blueprint": 45,
    "ash_prime_chassis": 45,
    "ash_prime_neuroptics": 45,
    "ash_prime_systems": 45,
    "atlas_prime_blueprint": 45,
    "atlas_prime_chassis": 45,
    "atlas_prime_neuroptics": 45,
    "atlas_prime_systems": 45,
    "banshee_prime_blueprint": 45,
    "banshee_prime_chassis": 45,
    "banshee_prime_neuroptics": 45,
    "banshee_prime_systems": 45,
    "baruuk_prime_blueprint": 45,
    "baruuk_prime_chassis": 45,
    "baruuk_prime_neuroptics": 45,
    "baruuk_prime_systems": 45,
    "chroma_prime_blueprint": 45,
    "chroma_prime_chassis": 45,
    "chroma_prime_neuroptics": 45,
    "chroma_prime_systems": 45,
    "ember_prime_blueprint": 45,
    "ember_prime_chassis": 45,
    "ember_prime_neuroptics": 45,
    "ember_prime_systems": 45,
    "equinox_prime_blueprint": 45,
    "equinox_prime_chassis": 45,
    "equinox_prime_neuroptics": 45,
    "equinox_prime_systems": 45,
    "frost_prime_blueprint": 45,
    "frost_prime_chassis": 45,
    "frost_prime_neuroptics": 45,
    "frost_prime_systems": 45,
    "gara_prime_blueprint": 45,
    "gara_prime_chassis": 45,
    "gara_prime_neuroptics": 45,
    "gara_prime_systems": 45,
    "garuda_prime_blueprint": 45,
    "garuda_prime_chassis": 45,
    "garuda_prime_neuroptics": 45,
    "garuda_prime_systems": 45,
    "gauss_prime_blueprint": 45,
    "gauss_prime_chassis": 45,
    "gauss_prime_neuroptics": 45,
    "gauss_prime_systems": 45,
    "grendel_prime_blueprint": 45,
    "grendel_prime_chassis": 45,
    "grendel_prime_neuroptics": 45,
    "grendel_prime_systems": 45,
    "harrow_prime_blueprint": 45,
    "harrow_prime_chassis": 45,
    "harrow_prime_neuroptics": 45,
    "harrow_prime_systems": 45,
    "hildryn_prime_blueprint": 45,
    "hildryn_prime_chassis": 45,
    "hildryn_prime_neuroptics": 45,
    "hildryn_prime_systems": 45,
    "hydroid_prime_blueprint": 45,
    "hydroid_prime_chassis": 45,
    "hydroid_prime_neuroptics": 45,
    "hydroid_prime_systems": 45,
    "inaros_prime_blueprint": 45,
    "inaros_prime_chassis": 45,
    "inaros_prime_neuroptics": 45,
    "inaros_prime_systems": 45,
    "ivara_prime_blueprint": 45,
    "ivara_prime_chassis": 45,
    "ivara_prime_neuroptics": 45,
    "ivara_prime_systems": 45,
    "khora_prime_blueprint": 45,
    "khora_prime_chassis": 45,
    "khora_prime_neuroptics": 45,
    "khora_prime_systems": 45,
    "limbo_prime_blueprint": 45,
    "limbo_prime_chassis": 45,
    "limbo_prime_neuroptics": 45,
    "limbo_prime_systems": 45,
    "loki_prime_blueprint": 45,
    "loki_prime_chassis": 45,
    "loki_prime_neuroptics": 45,
    "loki_prime_systems": 45,
    "mag_prime_blueprint": 45,
    "mag_prime_chassis": 45,
    "mag_prime_neuroptics": 45,
    "mag_prime_systems": 45,
    "mesa_prime_blueprint": 45,
    "mesa_prime_chassis": 45,
    "mesa_prime_neuroptics": 45,
    "mesa_prime_systems": 45,
    "mirage_prime_blueprint": 45,
    "mirage_prime_chassis": 45,
    "mirage_prime_neuroptics": 45,
    "mirage_prime_systems": 45,
    "nekros_prime_blueprint": 45,
    "nekros_prime_chassis": 45,
    "nekros_prime_neuroptics": 45,
    "nekros_prime_systems": 45,
    "nezha_prime_blueprint": 45,
    "nezha_prime_chassis": 45,
    "nezha_prime_neuroptics": 45,
    "nezha_prime_systems": 45,
    "nidus_prime_blueprint": 45,
    "nidus_prime_chassis": 45,
    "nidus_prime_neuroptics": 45,
    "nidus_prime_systems": 45,
    "nova_prime_blueprint": 45,
    "nova_prime_chassis": 45,
    "nova_prime_neuroptics": 45,
    "nova_prime_systems": 45,
    "nyx_prime_blueprint": 45,
    "nyx_prime_chassis": 45,
    "nyx_prime_neuroptics": 45,
    "nyx_prime_systems": 45,
    "oberon_prime_blueprint": 45,
    "oberon_prime_chassis": 45,
    "oberon_prime_neuroptics": 45,
    "oberon_prime_systems": 45,
    "octavia_prime_blueprint": 45,
    "octavia_prime_chassis": 45,
    "octavia_prime_neuroptics": 45,
    "octavia_prime_systems": 45,
    "protea_prime_blueprint": 45,
    "protea_prime_chassis": 45,
    "protea_prime_neuroptics": 45,
    "protea_prime_systems": 45,
    "revenant_prime_blueprint": 45,
    "revenant_prime_chassis": 45,
    "revenant_prime_neuroptics": 45,
    "revenant_prime_systems": 45,
    "rhino_prime_blueprint": 45,
    "rhino_prime_chassis": 45,
    "rhino_prime_neuroptics": 45,
    "rhino_prime_systems": 45,
    "saryn_prime_blueprint": 45,
    "saryn_prime_chassis": 45,
    "saryn_prime_neuroptics": 45,
    "saryn_prime_systems": 45,
    "sevagoth_prime_blueprint": 45,
    "sevagoth_prime_chassis": 45,
    "sevagoth_prime_neuroptics": 45,
    "sevagoth_prime_systems": 45,
    "titania_prime_blueprint": 45,
    "titania_prime_chassis": 45,
    "titania_prime_neuroptics": 45,
    "titania_prime_systems": 45,
    "trinity_prime_blueprint": 45,
    "trinity_prime_chassis": 45,
    "trinity_prime_neuroptics": 45,
    "trinity_prime_systems": 45,
    "valkyr_prime_blueprint": 45,
    "valkyr_prime_chassis": 45,
    "valkyr_prime_neuroptics": 45,
    "valkyr_prime_systems": 45,
    "vauban_prime_blueprint": 45,
    "vauban_prime_chassis": 45,
    "vauban_prime_neuroptics": 45,
    "vauban_prime_systems": 45,
    "volt_prime_blueprint": 45,
    "volt_prime_chassis": 45,
    "volt_prime_neuroptics": 45,
    "volt_prime_systems": 45,
    "wisp_prime_blueprint": 45,
    "wisp_prime_chassis": 45,
    "wisp_prime_neuroptics": 45,
    "wisp_prime_systems": 45,
    "wukong_prime_blueprint": 45,
    "wukong_prime_chassis": 45,
    "wukong_prime_neuroptics": 45,
    "wukong_prime_systems": 45,
    "xaku_prime_blueprint": 45,
    "xaku_prime_chassis": 45,
    "xaku_prime_neuroptics": 45,
    "xaku_prime_systems": 45,
    "zephyr_prime_blueprint": 45,
    "zephyr_prime_chassis": 45,
    "zephyr_prime_neuroptics": 45,
    "zephyr_prime_systems": 45,
    # 武器 Prime 部件 (常见示例)
    "braton_prime_blueprint": 45,
    "braton_prime_barrel": 45,
    "braton_prime_receiver": 45,
    "braton_prime_stock": 45,
    "burston_prime_blueprint": 45,
    "burston_prime_barrel": 45,
    "burston_prime_receiver": 45,
    "burston_prime_stock": 45,
    "latron_prime_blueprint": 45,
    "latron_prime_barrel": 45,
    "latron_prime_receiver": 45,
    "latron_prime_stock": 45,
    "soma_prime_blueprint": 45,
    "soma_prime_barrel": 45,
    "soma_prime_receiver": 45,
    "soma_prime_stock": 45,
    "tenora_prime_blueprint": 45,
    "tenora_prime_barrel": 45,
    "tenora_prime_receiver": 45,
    "tenora_prime_stock": 45,
    "tigris_prime_blueprint": 45,
    "tigris_prime_barrel": 45,
    "tigris_prime_receiver": 45,
    "tigris_prime_stock": 45,
    "hek_prime_blueprint": 45,
    "hek_prime_barrel": 45,
    "hek_prime_receiver": 45,
    "hek_prime_stock": 45,
    "boar_prime_blueprint": 45,
    "boar_prime_barrel": 45,
    "boar_prime_receiver": 45,
    "boar_prime_stock": 45,
    "lex_prime_blueprint": 45,
    "lex_prime_barrel": 45,
    "lex_prime_receiver": 45,
    "aklex_prime_link": 45,
    "vasto_prime_blueprint": 45,
    "vasto_prime_barrel": 45,
    "vasto_prime_receiver": 45,
    "akvasto_prime_link": 45,
    "bronco_prime_blueprint": 45,
    "bronco_prime_barrel": 45,
    "bronco_prime_receiver": 45,
    "fragor_prime_blueprint": 45,
    "fragor_prime_handle": 45,
    "fragor_prime_head": 45,
    "galatine_prime_blueprint": 45,
    "galatine_prime_blade": 45,
    "galatine_prime_handle": 45,
    "gram_prime_blueprint": 45,
    "gram_prime_blade": 45,
    "gram_prime_handle": 45,
    "nami_skyla_prime_blueprint": 45,
    "nami_skyla_prime_blade": 45,
    "nami_skyla_prime_handle": 45,
    "nikana_prime_blueprint": 45,
    "nikana_prime_blade": 45,
    "nikana_prime_hilt": 45,
    "orthos_prime_blueprint": 45,
    "orthos_prime_blade": 45,
    "orthos_prime_handle": 45,
    "reaper_prime_blueprint": 45,
    "reaper_prime_blade": 45,
    "reaper_prime_handle": 45,
    "tipedo_prime_blueprint": 45,
    "tipedo_prime_ornament": 45,
    "tipedo_prime_staff": 45,
    # 赋能 (Arcane) - 100 杜卡特
    "arcane_energize": 100,
    "arcane_grace": 100,
    "arcane_barrier": 100,
    "arcane_avenger": 100,
    "arcane_guardian": 100,
    "arcane_velocity": 100,
    "arcane_precision": 100,
    "arcane_rage": 100,
    "arcane_strike": 100,
    "arcane_ultimatum": 100,
    "arcane_fury": 100,
    "arcane_acceleration": 100,
    "arcane_arachne": 100,
    "arcane_bodyguard": 100,
    "arcane_consequence": 100,
    "arcane_deflection": 100,
    "arcane_healing": 100,
    "arcane_ice": 100,
    "arcane_phantasm": 100,
    "arcane_resistance": 100,
    "arcane_trickery": 100,
    "arcane_victory": 100,
}


def get_ducat_value(item_id: str) -> int | None:
    """获取物品的杜卡特价值"""
    # 首先检查静态映射
    if item_id in STATIC_DUCAT_VALUES:
        return STATIC_DUCAT_VALUES[item_id]

    # 根据物品ID模式推断杜卡特价值
    item_id_lower = item_id.lower()

    # Prime 部件通常是 45 杜卡特
    if "_prime_" in item_id_lower:
        # 战甲 Prime 部件
        if any(part in item_id_lower for part in ["blueprint", "chassis", "neuroptics", "systems"]):
            return 45
        # 武器 Prime 部件
        if any(part in item_id_lower for part in ["barrel", "receiver", "stock", "blade", "handle", "hilt", "head", "link", "ornament", "staff"]):
            return 45

    # 赋能 (Arcane) 通常是 100 杜卡特
    if "arcane_" in item_id_lower:
        return 100

    return None


def calculate_ducat_efficiency(platinum_price: int | None, ducat_value: int | None) -> dict | None:
    """计算杜卡特效率（每白金获得的杜卡特数）"""
    if platinum_price is None or ducat_value is None or platinum_price <= 0:
        return None

    ducats_per_plat = ducat_value / platinum_price
    return {
        "ducat_value": ducat_value,
        "platinum_price": platinum_price,
        "ducats_per_plat": round(ducats_per_plat, 2),
        "recommendation": "sell" if ducats_per_plat < 3 else "ducat"
    }


class ApiRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @staticmethod
    def _strip_text(value: str, field_name: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError(f"{field_name} 不能为空")
        return text

    @staticmethod
    def _normalize_item_id(value: str) -> str:
        text = normalize_market_id(value)
        if not text:
            raise ValueError("item_id 无效")
        if len(text) > 120:
            raise ValueError("item_id 过长")
        return text

    @staticmethod
    def _validate_hhmm(value: str) -> str:
        text = value.strip()
        if len(text) != 5 or text[2] != ":":
            raise ValueError("时间格式必须是 HH:MM")
        hour, minute = text.split(":", 1)
        if not hour.isdigit() or not minute.isdigit():
            raise ValueError("时间格式必须是 HH:MM")
        if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
            raise ValueError("时间格式必须是 HH:MM")
        return text


class ChatRequest(ApiRequestModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return cls._strip_text(value, "message")


class ChatResponse(BaseModel):
    reply: str


class MemoryResponse(BaseModel):
    favorites: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    preferences: dict[str, Any]
    watchlist: list[dict[str, Any]] = []


class FavoriteRequest(ApiRequestModel):
    item_id: str = Field(min_length=1, max_length=120)

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        return cls._normalize_item_id(value)


class AlertRequest(ApiRequestModel):
    item_id: str = Field(min_length=1, max_length=120)
    direction: Literal["below", "above"]
    price: int = Field(ge=1, le=100000)
    note: str = Field(default="", max_length=200)

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        return cls._normalize_item_id(value)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()


class PreferenceRequest(ApiRequestModel):
    key: Literal["platform", "crossplay", "max_results"]
    value: str = Field(min_length=1, max_length=32)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        return cls._strip_text(value, "value")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    reply = await asyncio.to_thread(chat_agent.answer, request.message)
    return ChatResponse(reply=reply)


@app.get("/api/memory", response_model=MemoryResponse)
async def get_memory() -> MemoryResponse:
    memory = await _load_memory_async()
    prefs = memory.preferences
    if hasattr(prefs, 'platform'):
        prefs_dict = {
            "platform": prefs.platform,
            "crossplay": prefs.crossplay,
            "max_results": prefs.max_results,
        }
    else:
        prefs_dict = prefs
    return MemoryResponse(
        favorites=[
            {"display": display_item_name(item_id), "item_id": item_id}
            for item_id in memory.favorite_items
        ],
        alerts=[
            {"item": display_item_name(a.item_id), "item_id": a.item_id, "direction": a.direction, "price": a.price, "note": a.note}
            for a in memory.price_alerts
        ],
        preferences=prefs_dict,
        watchlist=[
            {
                "item_id": item.item_id,
                "item_name": item.item_name,
                "frequency": item.frequency,
                "time": item.time,
                "content": item.content,
            }
            for item in memory.watchlist
        ],
    )


@app.post("/api/fav")
async def add_favorite(request: FavoriteRequest) -> JSONResponse:
    memory = await _load_memory_async()
    memory = memory.with_favorite_item(request.item_id)
    await _save_memory_async(memory)
    return JSONResponse({"status": "ok"})


@app.delete("/api/fav")
async def remove_favorite(request: FavoriteRequest) -> JSONResponse:
    memory = await _load_memory_async()
    memory = memory.without_favorite_item(request.item_id)
    await _save_memory_async(memory)
    return JSONResponse({"status": "ok"})


@app.post("/api/alert")
async def add_alert(request: AlertRequest) -> JSONResponse:
    memory = await _load_memory_async()
    memory = memory.with_price_alert(request.item_id, request.direction, request.price, request.note)
    await _save_memory_async(memory)
    return JSONResponse({"status": "ok"})


@app.delete("/api/alert")
async def remove_alert(request: AlertRequest) -> JSONResponse:
    memory = await _load_memory_async()
    memory = memory.without_price_alert(request.item_id, request.direction, request.price)
    await _save_memory_async(memory)
    return JSONResponse({"status": "ok"})


# ===== 微信推送 API =====

class PushConfigRequest(ApiRequestModel):
    enabled: bool | None = None
    app_token: str | None = Field(default=None, max_length=256)
    uids: list[str] | None = Field(default=None, max_length=20)
    push_alerts: bool | None = None
    push_watches: bool | None = None
    push_proactive: bool | None = None
    push_daily_report: bool | None = None
    report_time: str | None = Field(default=None, max_length=5)

    @field_validator("app_token", mode="before")
    @classmethod
    def normalize_app_token(cls, value: str | None):
        if value is None:
            return None
        return cls._strip_text(value, "app_token")

    @field_validator("uids", mode="before")
    @classmethod
    def normalize_uids(cls, value):
        if value is None:
            return None
        cleaned = []
        for uid in value:
            text = cls._strip_text(str(uid), "uid")
            if len(text) > 128:
                raise ValueError("uid 过长")
            cleaned.append(text)
        return cleaned

    @field_validator("report_time", mode="before")
    @classmethod
    def normalize_report_time(cls, value: str | None):
        if value is None:
            return None
        return cls._validate_hhmm(value)


@app.get("/api/push/config")
async def get_push_config() -> JSONResponse:
    cfg = PushConfig.load()
    data = cfg.__dict__.copy()
    # 隐藏 token 中间部分
    if data.get("app_token"):
        t = data["app_token"]
        data["app_token_masked"] = t[:5] + "***" + t[-4:] if len(t) > 9 else "***"
    return JSONResponse(data)


@app.post("/api/push/config")
async def update_push_config(req: PushConfigRequest) -> JSONResponse:
    global push_config, push_client
    cfg = PushConfig.load()
    for key, val in req.__dict__.items():
        if val is not None:
            setattr(cfg, key, val)
    cfg.save()
    push_config = cfg
    push_client = WxPusher(push_config)
    return JSONResponse({"status": "ok"})


@app.post("/api/push/test")
async def test_push() -> JSONResponse:
    if not push_client.available:
        return JSONResponse({"status": "error", "message": "推送未配置或未启用"}, status_code=400)
    ok = await asyncio.to_thread(push_client.send_text, "测试推送", "Warframe 交易助手推送测试成功！")
    if ok:
        return JSONResponse({"status": "ok", "message": "测试消息已发送"})
    return JSONResponse({"status": "error", "message": "推送失败，请检查配置"}, status_code=500)


@app.get("/api/push/qrcode")
async def get_push_qrcode() -> JSONResponse:
    """获取 WxPusher 关注二维码 URL。"""
    if not push_config.app_token:
        return JSONResponse({"status": "error", "message": "未配置 appToken"}, status_code=400)
    try:
        resp = await asyncio.to_thread(
            requests.post,
            WXPUSHER_QR_API,
            json={"appToken": push_config.app_token, "extra": "warframe"},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 1000:
            return JSONResponse({"status": "ok", "url": data["data"]})
        return JSONResponse({"status": "error", "message": data.get("msg", "获取二维码失败")}, status_code=500)
    except Exception as exc:
        logger.error("获取二维码失败: %s", exc)
        return JSONResponse({"status": "error", "message": "获取二维码失败，请稍后重试"}, status_code=500)


@app.post("/api/push/callback")
async def push_callback(request: Request) -> JSONResponse:
    """WxPusher 事件回调：用户关注/取关时自动更新 UID。"""
    global push_config, push_client
    try:
        body = await request.json()
        action = body.get("action")
        uid = body.get("uid")
        logger.info("WxPusher 回调: action=%s uid=%s", action, uid)
        if action == "subscribe" and uid:
            cfg = PushConfig.load()
            if uid not in cfg.uids:
                cfg.uids.append(uid)
                cfg.enabled = True
                cfg.save()
                push_config = cfg
                push_client = WxPusher(push_config)
                logger.info("自动添加 UID: %s", uid)
        elif action == "unsubscribe" and uid:
            cfg = PushConfig.load()
            if uid in cfg.uids:
                cfg.uids.remove(uid)
                cfg.save()
                push_config = cfg
                push_client = WxPusher(push_config)
                logger.info("自动移除 UID: %s", uid)
    except Exception as exc:
        logger.warning("回调处理异常: %s", exc)
    return JSONResponse({"code": 1000})


# ===== 飞书机器人 API =====

class FeishuConfigRequest(ApiRequestModel):
    enabled: bool | None = None
    app_id: str | None = Field(default=None, max_length=128)
    app_secret: str | None = Field(default=None, max_length=256)

    @field_validator("app_id", "app_secret", mode="before")
    @classmethod
    def normalize_secret_fields(cls, value: str | None):
        if value is None:
            return None
        return cls._strip_text(value, "config")


@app.get("/api/feishu/config")
async def get_feishu_config() -> JSONResponse:
    cfg = FeishuConfig.load()
    data = cfg.__dict__.copy()
    if data.get("app_secret"):
        data["app_secret_masked"] = "***" + data["app_secret"][-4:] if len(data["app_secret"]) > 4 else "***"
    return JSONResponse(data)


@app.post("/api/feishu/config")
async def update_feishu_config(req: FeishuConfigRequest) -> JSONResponse:
    global feishu_config, feishu_bot
    cfg = FeishuConfig.load()
    for key, val in req.__dict__.items():
        if val is not None:
            setattr(cfg, key, val)
    cfg.save()
    feishu_config = cfg
    # 重启飞书 WebSocket 连接
    feishu_bot.stop()
    feishu_bot = FeishuBot(feishu_config, on_message=_feishu_on_message)
    if feishu_bot.available:
        feishu_bot.start()
    return JSONResponse({"status": "ok"})


@app.post("/api/feishu/test")
async def test_feishu() -> JSONResponse:
    if not feishu_bot.available:
        return JSONResponse({"status": "error", "message": "飞书机器人未配置或未启用"}, status_code=400)
    try:
        client = feishu_bot._ensure_client()
        return JSONResponse({"status": "ok", "message": "客户端初始化成功，WebSocket 连接将在后台建立"})
    except Exception as exc:
        logger.error("飞书客户端初始化失败: %s", exc)
        return JSONResponse({"status": "error", "message": "客户端初始化失败，请检查配置"}, status_code=500)


# ===== 关注列表 API =====

class WatchRequest(ApiRequestModel):
    item_id: str = Field(min_length=1, max_length=120)
    item_name: str = Field(min_length=1, max_length=120)
    frequency: Literal["daily", "hourly", "weekly"] = "daily"
    time: str = Field(default="09:00", max_length=5)
    content: Literal["top3_sellers", "top3_buyers", "price_change", "all"] = "top3_buyers"

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        return cls._normalize_item_id(value)

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, value: str) -> str:
        return cls._strip_text(value, "item_name")

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        return cls._validate_hhmm(value)


@app.get("/api/watchlist")
async def get_watchlist() -> JSONResponse:
    """获取关注列表"""
    memory = await _load_memory_async()
    return JSONResponse({
        "watchlist": [
            {
                "item_id": item.item_id,
                "item_name": item.item_name,
                "frequency": item.frequency,
                "time": item.time,
                "content": item.content,
            }
            for item in memory.watchlist
        ]
    })


@app.post("/api/watchlist")
async def add_watch_item(request: WatchRequest) -> JSONResponse:
    """添加关注项"""
    memory = await _load_memory_async()
    memory = memory.with_watch_item(
        item_id=request.item_id,
        item_name=request.item_name,
        frequency=request.frequency,
        time=request.time,
        content=request.content,
    )
    await _save_memory_async(memory)
    return JSONResponse({"status": "ok"})


@app.delete("/api/watchlist/{item_id}")
async def remove_watch_item(item_id: str) -> JSONResponse:
    """移除关注项"""
    memory = await _load_memory_async()
    memory = memory.without_watch_item(item_id)
    await _save_memory_async(memory)
    return JSONResponse({"status": "ok"})


@app.post("/api/pref")
async def set_preference(request: PreferenceRequest) -> JSONResponse:
    value = request.value.strip().lower()
    if request.key == "platform" and value not in {"pc", "ps", "ps4", "xbox", "switch"}:
        raise HTTPException(status_code=422, detail="platform must be one of pc, ps, ps4, xbox, switch")
    if request.key == "crossplay" and value not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
        raise HTTPException(status_code=422, detail="crossplay must be on/off")
    if request.key == "max_results":
        if not value.isdigit() or not (1 <= int(value) <= 50):
            raise HTTPException(status_code=422, detail="max_results must be between 1 and 50")
    memory = await _load_memory_async()
    memory = memory.set_preference(request.key, value)
    await _save_memory_async(memory)
    return JSONResponse({"status": "ok"})


class RatingRequest(ApiRequestModel):
    message: str = Field(min_length=1, max_length=4000)
    reply: str = Field(min_length=1, max_length=12000)
    rating: int = Field(default=3, ge=1, le=5)
    session_id: str = Field(default="", max_length=64)

    @field_validator("message", "reply")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        return cls._strip_text(value, "text")

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str) -> str:
        return value.strip()


@app.post("/api/rate")
async def rate_response(request: RatingRequest) -> JSONResponse:
    from ..conversation_log import log_conversation, ConversationEntry
    log_conversation(ConversationEntry(
        user_message=request.message,
        assistant_reply=request.reply,
        rating=max(1, min(5, request.rating)),
        session_id=request.session_id,
    ))
    return JSONResponse({"status": "ok"})


@app.get("/api/history/{item_id}")
async def get_history(item_id: str, range: Literal["24h", "7d", "30d", "all"] = Query("all")) -> JSONResponse:
    range_map = {"24h": 24, "7d": 168, "30d": 720, "all": 0}
    hours = range_map.get(range, 0)
    if hours > 0:
        snapshots = price_db.recent_since(item_id, hours=hours)
    else:
        snapshots = price_db.recent(item_id, limit=50)
    return JSONResponse({
        "item_id": item_id,
        "range": range,
        "snapshots": [
            {
                "timestamp": s.timestamp,
                "sell_price": s.sell_price,
                "buy_price": s.buy_price,
            }
            for s in snapshots
        ]
    })


class CompareHistoryRequest(ApiRequestModel):
    item_ids: list[str] = Field(min_length=1, max_length=5)
    range: Literal["24h", "7d", "30d", "all"] = "7d"

    @field_validator("item_ids", mode="before")
    @classmethod
    def normalize_item_ids(cls, value):
        cleaned = []
        for item_id in value:
            cleaned.append(cls._normalize_item_id(str(item_id)))
        return cleaned


@app.post("/api/history/compare")
async def compare_history(request: CompareHistoryRequest) -> JSONResponse:
    """批量获取多个物品的历史价格，用于走势对比"""
    if len(request.item_ids) > 5:
        raise HTTPException(400, "最多比较5个物品")

    range_map = {"24h": 24, "7d": 168, "30d": 720, "all": 0}
    hours = range_map.get(request.range, 168)

    results = {}
    for item_id in request.item_ids:
        try:
            if hours > 0:
                snapshots = price_db.recent_since(item_id, hours=hours)
            else:
                snapshots = price_db.recent(item_id, limit=50)
            display = display_item_name(item_id)
            results[item_id] = {
                "display": display,
                "snapshots": [
                    {
                        "timestamp": s.timestamp,
                        "sell_price": s.sell_price,
                        "buy_price": s.buy_price,
                    }
                    for s in snapshots
                ]
            }
        except Exception:
            results[item_id] = {"display": item_id, "snapshots": []}

    return JSONResponse({"items": results, "range": request.range})


# ===== 价格异常检测 API =====

@app.get("/api/price/anomalies")
async def detect_price_anomalies(threshold: float = 30.0) -> JSONResponse:
    """检测价格异常（暴涨暴跌）
    threshold: 偏离平均价格的百分比阈值，默认30%
    """
    memory = await _load_memory_async()
    anomalies = []

    # 检查收藏物品
    items_to_check = set(memory.favorite_items)
    # 也检查关注列表
    for watch in memory.watchlist:
        items_to_check.add(watch.item_id)

    for item_id in items_to_check:
        try:
            # 获取历史数据
            snapshots = price_db.recent(item_id, limit=20)
            if len(snapshots) < 5:
                continue

            # 计算历史平均价格
            sell_prices = [s.sell_price for s in snapshots if s.sell_price is not None]
            if len(sell_prices) < 3:
                continue

            avg_price = sum(sell_prices) / len(sell_prices)
            latest_price = sell_prices[0]  # 最新的价格

            # 计算偏离百分比
            deviation = ((latest_price - avg_price) / avg_price) * 100

            if abs(deviation) >= threshold:
                anomaly_type = "spike" if deviation > 0 else "drop"
                anomalies.append({
                    "item_id": item_id,
                    "display": display_item_name(item_id),
                    "current_price": latest_price,
                    "avg_price": round(avg_price, 1),
                    "deviation": round(deviation, 1),
                    "type": anomaly_type,
                    "type_display": "暴涨" if anomaly_type == "spike" else "暴跌",
                    "snapshots_count": len(sell_prices),
                })
        except Exception:
            continue

    # 按偏离程度排序
    anomalies.sort(key=lambda x: abs(x["deviation"]), reverse=True)

    return JSONResponse({
        "anomalies": anomalies,
        "total": len(anomalies),
        "threshold": threshold,
    })


# ===== 虚空裂隙追踪 API =====

@app.get("/api/fissures")
async def get_fissures() -> JSONResponse:
    """获取虚空裂隙数据（优先外部API，失败则用本地掉落数据分析）"""
    # 尝试外部 API
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get("https://api.warframestat.us/pc/fissures")
            if resp.status_code == 200:
                fissures = resp.json()
                tiers = {"Lith": [], "Meso": [], "Neo": [], "Axi": [], "Requiem": []}
                for f in fissures:
                    tier = f.get("tier", "")
                    if tier in tiers:
                        tiers[tier].append({
                            "id": f.get("id"),
                            "node": f.get("node"),
                            "missionType": f.get("missionType"),
                            "enemy": f.get("enemy"),
                            "tier": tier,
                            "eta": f.get("eta"),
                            "expired": f.get("expired", False),
                        })
                return JSONResponse({"fissures": tiers, "timestamp": time.time(), "source": "live"})
    except Exception:
        pass

    # 外部 API 失败，使用本地掉落数据分析推荐
    try:
        data = _preload_relic_drop_data()
        if not data:
            return JSONResponse({"fissures": {}, "message": "外部API不可用且无本地遗物数据", "source": "none"})

        # 按纪元分组，只取 Intact 状态，计算稀有掉落
        tiers = {"Lith": [], "Meso": [], "Neo": [], "Axi": [], "Requiem": []}
        seen = set()
        for relic in data.get("relics", []):
            tier = relic.get("tier", "")
            relic_name = relic.get("relicName", "")
            state = relic.get("state", "")
            if tier not in tiers or state != "Intact":
                continue
            key = f"{tier}_{relic_name}"
            if key in seen:
                continue
            seen.add(key)

            rewards = relic.get("rewards", [])
            rare_drops = [r for r in rewards if r.get("rarity") == "Rare"]
            uncommon_drops = [r for r in rewards if r.get("rarity") == "Uncommon"]

            tiers[tier].append({
                "id": f"{tier} {relic_name}",
                "node": f"{tier} {relic_name}",
                "missionType": "虚空裂隙",
                "tier": tier,
                "eta": "随时可用",
                "expired": False,
                "rare_drops": [{"name": r.get("itemName", ""), "chance": r.get("chance", 0)} for r in rare_drops],
                "uncommon_drops": [{"name": r.get("itemName", ""), "chance": r.get("chance", 0)} for r in uncommon_drops[:2]],
                "rare_count": len(rare_drops),
            })

        # 每个纪元按稀有掉落数排序，取前20
        for t in tiers:
            tiers[t].sort(key=lambda x: x.get("rare_count", 0), reverse=True)
            tiers[t] = tiers[t][:20]

        return JSONResponse({
            "fissures": tiers,
            "timestamp": time.time(),
            "source": "local",
            "message": "外部API暂不可用，显示本地遗物掉落数据"
        })
    except Exception as e:
        logger.error("获取裂隙数据失败: %s", e)
        return JSONResponse({"error": "获取裂隙数据失败"}, status_code=500)


@app.get("/api/fissures/relics")
async def get_relic_info() -> JSONResponse:
    """获取遗物信息（从本地数据）"""
    try:
        relic_path = config.EXPORT_DIR / "ExportRelicArcane_zh.json"
        if not relic_path.exists():
            return JSONResponse({"relics": [], "message": "遗物数据不存在"})

        def _read_json():
            with relic_path.open("r", encoding="utf-8") as f:
                return json.load(f)

        data = await asyncio.to_thread(_read_json)

        relics = []
        for item in data.get("ExportRelicArcane", []):
            if "Relic" in item.get("name", ""):
                rewards = item.get("relicRewards", [])
                relics.append({
                    "name": item["name"],
                    "uniqueName": item["uniqueName"],
                    "rewards": [
                        {
                            "name": r.get("rewardName", "").split("/")[-1],
                            "rarity": r.get("rarity"),
                        }
                        for r in rewards
                    ],
                })

        return JSONResponse({"relics": relics[:100]})  # 限制返回数量
    except Exception as e:
        logger.error("获取遗物数据失败: %s", e)
        return JSONResponse({"error": "获取遗物数据失败"}, status_code=500)


@app.get("/api/favorites_prices")
async def get_favorites_prices(mode: str = "scatter") -> JSONResponse:
    """收藏物品价格。mode: scatter=零散(rank 0), maxrank=满级成品"""
    memory = await _load_memory_async()
    results = []
    for item_id in memory.favorite_items:
        try:
            orders = await fetch_orders_async(item_id)
            max_rank = get_max_rank_from_orders(orders)
            is_ranked = max_rank is not None and (
                item_id.startswith("arcane_") or item_id.startswith("mod_")
            )
            # scatter: rank 0 价格; maxrank: 满级成品价格
            sell_rank_filter = (max_rank if mode == "maxrank" and is_ranked else 0) if is_ranked else None
            sellers = best_sellers(orders, limit=1, rank_filter=sell_rank_filter)
            buyers = best_buyers(orders, limit=1, rank_filter=sell_rank_filter)
            entry = {
                "item_id": item_id,
                "sell_price": sellers[0].platinum if sellers else None,
                "buy_price": buyers[0].platinum if buyers else None,
                "max_rank": max_rank,
            }
            results.append(entry)
        except Exception:
            results.append({"item_id": item_id, "sell_price": None, "buy_price": None, "max_rank": None})
    return JSONResponse({"items": results, "mode": mode})


@app.get("/api/item_detail/{item_id}")
async def get_item_detail(item_id: str) -> JSONResponse:
    try:
        orders = await fetch_orders_async(item_id)
        ctx = build_item_context_result(item_id, orders)
        result = {
            "item_id": item_id,
            "display": display_item_name(item_id),
            "sell_price": ctx.best_sell_price,
            "buy_price": ctx.best_buy_price,
            "spread": (ctx.best_sell_price - ctx.best_buy_price) if ctx.best_sell_price and ctx.best_buy_price else None,
        }
        if ctx.best_seller:
            result["seller"] = {
                "name": ctx.best_seller.user_name,
                "price": ctx.best_seller.platinum,
                "reputation": ctx.best_seller.reputation,
            }
        if ctx.best_buyer:
            result["buyer"] = {
                "name": ctx.best_buyer.user_name,
                "price": ctx.best_buyer.platinum,
                "reputation": ctx.best_buyer.reputation,
            }
        whisper_sell = build_whisper(ctx.best_seller.user_name, item_id, ctx.best_seller.platinum, 'sell') if ctx.best_seller else None
        whisper_buy = build_whisper(ctx.best_buyer.user_name, item_id, ctx.best_buyer.platinum, 'buy') if ctx.best_buyer else None
        result["whisper_sell"] = whisper_sell
        result["whisper_buy"] = whisper_buy
        # 赋能/Mod：额外显示 rank 0 零散价格
        max_rank = get_max_rank_from_orders(orders)
        is_ranked = max_rank is not None and (
            item_id.startswith("arcane_") or item_id.startswith("mod_")
        )
        if is_ranked and max_rank > 0:
            rank0_sellers = best_sellers(orders, limit=1, rank_filter=0)
            result["rank0_sell_price"] = rank0_sellers[0].platinum if rank0_sellers else None
            result["max_rank_sell_price"] = ctx.best_sell_price  # 已按 max_rank 过滤

        # 物品类型和等级信息
        type_info = get_item_type_info(item_id)
        if type_info:
            result["item_type"] = type_info["type"]
            result["item_type_display"] = type_info["type_display"]
            result["max_rank"] = type_info["max_rank"]
            result["rarity"] = type_info.get("rarity", "COMMON")

        # 杜卡特信息
        ducat_value = get_ducat_value(item_id)
        if ducat_value is not None:
            result["ducat_value"] = ducat_value
            if ctx.best_sell_price:
                efficiency = calculate_ducat_efficiency(ctx.best_sell_price, ducat_value)
                if efficiency:
                    result["ducat_efficiency"] = efficiency

        # 供需比（仅统计在线/游戏中卖家 vs 买家）
        online_sell = [o for o in orders if (o.get("order_type") or o.get("type")) == "sell" and o.get("user", {}).get("status") in ("ingame", "online")]
        online_buy = [o for o in orders if (o.get("order_type") or o.get("type")) == "buy" and o.get("user", {}).get("status") in ("ingame", "online")]
        result["supply_count"] = len(online_sell)
        result["demand_count"] = len(online_buy)
        if len(online_buy) > 0:
            result["supply_demand_ratio"] = round(len(online_sell) / len(online_buy), 2)
        else:
            result["supply_demand_ratio"] = None

        # 历史价格趋势（从 price_db）
        snapshots = price_db.recent(item_id, limit=20)
        if snapshots:
            sell_prices = [s.sell_price for s in snapshots if s.sell_price is not None]
            if sell_prices:
                result["history_high"] = max(sell_prices)
                result["history_low"] = min(sell_prices)
                result["history_avg"] = round(sum(sell_prices) / len(sell_prices), 1)
                # 趋势判断：最近价格 vs 平均
                latest = sell_prices[0]
                avg = result["history_avg"]
                deviation = ((latest - avg) / avg * 100) if avg > 0 else 0
                if deviation > 5:
                    result["trend"] = "up"
                    result["trend_display"] = f"↑ {deviation:.1f}%"
                elif deviation < -5:
                    result["trend"] = "down"
                    result["trend_display"] = f"↓ {abs(deviation):.1f}%"
                else:
                    result["trend"] = "stable"
                    result["trend_display"] = "→ 稳定"
                result["trend_deviation"] = round(deviation, 1)

        return JSONResponse(result)
    except Exception as e:
        logger.error("获取物品详情失败 %s: %s", item_id, e)
        return JSONResponse({"item_id": item_id, "error": "获取物品详情失败"}, status_code=404)


@app.get("/api/report")
async def get_report() -> JSONResponse:
    memory = await _load_memory_async()
    report_lines = []
    report_lines.append(f"# Warframe 每日价格报告")
    report_lines.append(f"关注物品: {len(memory.favorite_items)} 个")
    report_lines.append("")
    for item_id in memory.favorite_items:
        try:
            orders = await fetch_orders_async(item_id)
            ctx = build_item_context_result(item_id, orders)
            sell = f"{ctx.best_sell_price}p" if ctx.best_sell_price else "暂无"
            buy = f"{ctx.best_buy_price}p" if ctx.best_buy_price else "暂无"
            spread = f"{ctx.best_sell_price - ctx.best_buy_price}p" if ctx.best_sell_price and ctx.best_buy_price else "-"
            report_lines.append(f"- {display_item_name(item_id)}: 卖 {sell} / 收 {buy} / 差 {spread}")
        except Exception:
            report_lines.append(f"- {display_item_name(item_id)}: 查询失败")
    return JSONResponse({"report": "\n".join(report_lines)})


@app.get("/api/ducats/{item_id}")
async def get_ducats(item_id: str) -> JSONResponse:
    """获取物品的杜卡特价值和效率分析"""
    ducat_value = get_ducat_value(item_id)

    if ducat_value is None:
        return JSONResponse({
            "item_id": item_id,
            "has_ducat": False,
            "message": "该物品无杜卡特价值"
        })

    # 获取当前市场价格
    try:
        orders = await fetch_orders_async(item_id)
        rank_filter = get_max_rank_from_orders(orders)
        sellers = best_sellers(orders, limit=1, rank_filter=rank_filter)
        sell_price = sellers[0].platinum if sellers else None
    except Exception:
        sell_price = None

    result = {
        "item_id": item_id,
        "display": display_item_name(item_id),
        "has_ducat": True,
        "ducat_value": ducat_value,
        "sell_price": sell_price,
    }

    if sell_price and sell_price > 0:
        efficiency = calculate_ducat_efficiency(sell_price, ducat_value)
        if efficiency:
            result["efficiency"] = efficiency
            result["recommendation"] = "建议拆成杜卡特" if efficiency["recommendation"] == "ducat" else "建议直接卖白金"
            result["reason"] = f"每白金获得 {efficiency['ducats_per_plat']} 杜卡特" + (
                " (高于3:1阈值)" if efficiency["recommendation"] == "ducat" else " (低于3:1阈值)"
            )

    return JSONResponse(result)


@app.post("/api/ducats/batch")
async def get_ducats_batch(request: ItemListRequest) -> JSONResponse:
    """批量获取物品的杜卡特价值"""
    results = []
    for item_id in request.items[:10]:  # 限制最多10个
        ducat_value = get_ducat_value(item_id)
        if ducat_value is not None:
            try:
                orders = await fetch_orders_async(item_id)
                rank_filter = get_max_rank_from_orders(orders)
                sellers = best_sellers(orders, limit=1, rank_filter=rank_filter)
                sell_price = sellers[0].platinum if sellers else None
            except Exception:
                sell_price = None

            result = {
                "item_id": item_id,
                "display": display_item_name(item_id),
                "ducat_value": ducat_value,
                "sell_price": sell_price,
            }

            if sell_price and sell_price > 0:
                efficiency = calculate_ducat_efficiency(sell_price, ducat_value)
                if efficiency:
                    result["efficiency"] = efficiency

            results.append(result)

    return JSONResponse({"items": results})


# ===== 交易历史 API =====

class TradeRequest(ApiRequestModel):
    item_id: str = Field(min_length=1, max_length=120)
    item_name: str = Field(min_length=1, max_length=120)
    trade_type: Literal["buy", "sell"]
    price: int = Field(ge=1, le=100000)
    player_name: str = Field(default="", max_length=80)
    notes: str = Field(default="", max_length=300)

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        return cls._normalize_item_id(value)

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, value: str) -> str:
        return cls._strip_text(value, "item_name")

    @field_validator("player_name", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str) -> str:
        return value.strip()


@app.get("/api/trades")
async def get_trades(limit: int = Query(20, ge=1, le=100)) -> JSONResponse:
    """获取最近的交易记录"""
    trades = await asyncio.to_thread(trade_db.get_recent_trades, limit=limit)
    return JSONResponse({
        "trades": [
            {
                "id": t.id,
                "item_id": t.item_id,
                "item_name": t.item_name,
                "trade_type": t.trade_type,
                "price": t.price,
                "player_name": t.player_name,
                "timestamp": t.timestamp,
                "notes": t.notes,
            }
            for t in trades
        ]
    })


@app.post("/api/trades")
async def add_trade(request: TradeRequest) -> JSONResponse:
    """添加交易记录"""
    trade_id = await asyncio.to_thread(
        trade_db.add_trade,
        item_id=request.item_id,
        item_name=request.item_name,
        trade_type=request.trade_type,
        price=request.price,
        player_name=request.player_name,
        notes=request.notes,
    )
    return JSONResponse({"status": "ok", "id": trade_id})


@app.delete("/api/trades/{trade_id}")
async def delete_trade(trade_id: int) -> JSONResponse:
    """删除交易记录"""
    success = await asyncio.to_thread(trade_db.delete_trade, trade_id)
    if success:
        return JSONResponse({"status": "ok"})
    raise HTTPException(status_code=404, detail="交易记录不存在")


@app.get("/api/trades/stats")
async def get_trade_stats() -> JSONResponse:
    """获取交易统计信息"""
    stats = await asyncio.to_thread(trade_db.get_trade_stats)
    return JSONResponse(stats)


@app.get("/api/trades/item/{item_id}")
async def get_trades_by_item(item_id: str, limit: int = Query(10, ge=1, le=100)) -> JSONResponse:
    """获取指定物品的交易记录"""
    trades = await asyncio.to_thread(trade_db.get_trades_by_item, item_id, limit=limit)
    return JSONResponse({
        "item_id": item_id,
        "trades": [
            {
                "id": t.id,
                "item_name": t.item_name,
                "trade_type": t.trade_type,
                "price": t.price,
                "player_name": t.player_name,
                "timestamp": t.timestamp,
                "notes": t.notes,
            }
            for t in trades
        ]
    })


# ===== 套利检测 API =====


# ===== Mod 翻转 / 套装利润 / 投资顾问 API =====

_items_full_cache: list[dict] | None = None

def _load_items_full() -> list[dict]:
    """加载 items_full.json 并从 warframe-items 合并 tradable/fusionLimit 字段。"""
    global _items_full_cache
    if _items_full_cache is not None:
        return _items_full_cache

    path = config.DATA_DIR / "items_full.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig") as f:
        items = json.load(f)

    # 从 warframe-items Mods.json 加载 tradable 和 fusionLimit
    mods_path = Path(__file__).resolve().parent.parent.parent / "githubProduct" / "warframe-items" / "data" / "json" / "Mods.json"
    mods_lookup: dict[str, dict] = {}
    if mods_path.exists():
        try:
            with mods_path.open("r", encoding="utf-8") as f:
                for mod in json.load(f):
                    # name → url_name 映射
                    key = mod.get("name", "").lower().replace(" ", "_").replace("'", "")
                    mods_lookup[key] = mod
        except Exception:
            pass

    # 合并字段
    for item in items:
        item_id = item.get("item_id", "")
        if "mod" in item.get("tags", []):
            mod_data = mods_lookup.get(item_id, {})
            if not mod_data:
                # 尝试用 en_name 匹配
                en_key = item.get("en_name", "").lower().replace(" ", "_").replace("'", "")
                mod_data = mods_lookup.get(en_key, {})
            if mod_data:
                item.setdefault("tradable", mod_data.get("tradable", False))
                item.setdefault("modMaxRank", mod_data.get("fusionLimit", 0))
                item.setdefault("rarity", mod_data.get("rarity", "RARE"))
        else:
            item.setdefault("tradable", True)

    _items_full_cache = items
    return items


# 扫描结果缓存（避免每次请求都重新扫描）
_scan_cache: dict[str, tuple[list, float]] = {}
_SCAN_CACHE_TTL = 300  # 5 分钟缓存


def _get_scan_cache(key: str) -> list | None:
    if key in _scan_cache:
        data, ts = _scan_cache[key]
        if time.time() - ts < _SCAN_CACHE_TTL:
            return data
    return None


def _set_scan_cache(key: str, data: list) -> None:
    _scan_cache[key] = (data, time.time())


@app.get("/api/mod_flipper")
async def mod_flipper_endpoint(
    min_profit: int = Query(5, ge=0, le=100000),
    min_roi_pct: float = Query(100, ge=0, le=10000),
    limit: int = Query(50, ge=1, le=100),
) -> JSONResponse:
    """扫描 Mod 翻转利润（异步）。"""
    import uuid
    from ..mod_flipper import scan_all_mod_flips
    from ..scout import scout_mod_candidates
    cache_key = f"mod_flipper_{min_profit}_{min_roi_pct}_{limit}"
    cached = _get_scan_cache(cache_key)
    if cached is not None:
        return JSONResponse({"status": "done", "results": cached, "total": len(cached)})

    task_id = uuid.uuid4().hex[:12]
    _evict_old_bg_tasks()
    _bg_tasks[task_id] = {"status": "running", "result": None, "error": None, "created_at": _time.time()}

    async def _run():
        try:
            items = await asyncio.to_thread(_load_items_full)
            results = await asyncio.to_thread(
                scan_all_mod_flips, items, fetch_orders,
                min_profit=min_profit, min_roi_pct=min_roi_pct, limit=limit,
                scout_fn=scout_mod_candidates,
            )
            formatted = [
                {
                    "item_id": r.item_id, "display_name": r.display_name,
                    "r0_buy_price": r.r0_buy_price, "r10_sell_price": r.r10_sell_price,
                    "flip_profit": r.flip_profit, "roi_pct": round(r.roi_pct, 1),
                    "endo_cost": r.endo_cost, "plat_per_1k_endo": round(r.plat_per_1k_endo, 2),
                    "value_score": round(r.value_score, 2), "volume_48h": r.volume_48h,
                    "max_rank": r.max_rank, "rarity": r.rarity, "is_prime": r.is_prime,
                }
                for r in results
            ]
            _set_scan_cache(cache_key, formatted)
            _bg_tasks[task_id]["status"] = "done"
            _bg_tasks[task_id]["result"] = {"results": formatted, "total": len(formatted)}
        except Exception as exc:
            _bg_tasks[task_id]["status"] = "error"
            _bg_tasks[task_id]["error"] = str(exc)

    asyncio.create_task(_run())
    return JSONResponse({"status": "running", "task_id": task_id})


@app.get("/api/set_profit")
async def set_profit_endpoint(
    min_profit: int = Query(5, ge=0, le=100000),
    limit: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    """分析 Prime 套装利润（异步）。"""
    import uuid
    from ..set_profit import scan_all_set_profits
    from ..scout import scout_set_candidates
    cache_key = f"set_profit_{min_profit}_{limit}"
    cached = _get_scan_cache(cache_key)
    if cached is not None:
        return JSONResponse({"status": "done", "results": cached, "total": len(cached)})

    task_id = uuid.uuid4().hex[:12]
    _evict_old_bg_tasks()
    _bg_tasks[task_id] = {"status": "running", "result": None, "error": None, "created_at": _time.time()}

    async def _run():
        try:
            items = await asyncio.to_thread(_load_items_full)
            results = await asyncio.to_thread(
                scan_all_set_profits, items, fetch_orders,
                min_profit=min_profit, limit=limit,
                scout_fn=scout_set_candidates,
            )
            formatted = [
                {
                    "base_id": r.base_id, "display_name": r.display_name,
                    "set_buy_price": r.set_buy_price, "parts_sell_total": r.parts_sell_total,
                    "set_sell_price": r.set_sell_price, "parts_buy_total": r.parts_buy_total,
                    "profit_buy_parts_sell_set": r.profit_buy_parts_sell_set,
                    "profit_buy_set_sell_parts": r.profit_buy_set_sell_parts,
                    "best_strategy": r.best_strategy, "best_profit": r.best_profit,
                    "volume_48h": r.volume_48h, "part_count": r.part_count,
                }
                for r in results
            ]
            _set_scan_cache(cache_key, formatted)
            _bg_tasks[task_id]["status"] = "done"
            _bg_tasks[task_id]["result"] = {"results": formatted, "total": len(formatted)}
        except Exception as exc:
            _bg_tasks[task_id]["status"] = "error"
            _bg_tasks[task_id]["error"] = str(exc)

    asyncio.create_task(_run())
    return JSONResponse({"status": "running", "task_id": task_id})


@app.get("/api/investment")
async def investment_endpoint(
    budget: int = Query(500, ge=0, le=100000),
    min_roi_pct: float = Query(10.0, ge=0, le=10000),
    limit: int = Query(30, ge=1, le=100),
) -> JSONResponse:
    """Prime 套装套利顾问 API（异步）。"""
    import uuid
    from ..investment import scan_prime_investments
    from ..scout import scout_investment_candidates
    cache_key = f"investment_{budget}_{min_roi_pct}_{limit}"
    cached = _get_scan_cache(cache_key)
    if cached is not None:
        return JSONResponse({"status": "done", "results": cached, "total": len(cached)})

    task_id = uuid.uuid4().hex[:12]
    _evict_old_bg_tasks()
    _bg_tasks[task_id] = {"status": "running", "result": None, "error": None, "created_at": _time.time()}

    async def _run():
        try:
            items = await asyncio.to_thread(_load_items_full)
            results = await asyncio.to_thread(
                scan_prime_investments, items, fetch_orders,
                budget=budget, min_roi_pct=min_roi_pct, limit=limit,
                scout_fn=lambda groups: scout_investment_candidates(groups, budget=budget),
            )
            formatted = [
                {
                    "base_id": r.base_id, "display_name": r.display_name,
                    "strategy": r.strategy, "buy_cost": r.buy_cost,
                    "sell_price": r.sell_price, "profit_per_set": r.profit_per_set,
                    "roi_pct": r.roi_pct, "sets_affordable": r.sets_affordable,
                    "total_profit": r.total_profit, "volume_48h": r.volume_48h,
                    "risk_level": r.risk_level, "part_details": r.part_details,
                    "set_item_id": r.set_item_id,
                }
                for r in results
            ]
            _set_scan_cache(cache_key, formatted)
            _bg_tasks[task_id]["status"] = "done"
            _bg_tasks[task_id]["result"] = {"results": formatted, "total": len(formatted)}
        except Exception as exc:
            _bg_tasks[task_id]["status"] = "error"
            _bg_tasks[task_id]["error"] = str(exc)

    asyncio.create_task(_run())
    return JSONResponse({"status": "running", "task_id": task_id})


@app.get("/api/scan_status/{task_id}")
async def scan_status(task_id: str) -> JSONResponse:
    """通用扫描状态查询。"""
    task = _bg_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    resp: dict[str, Any] = {"status": task["status"]}
    if task["status"] == "done":
        resp.update(task["result"])
    elif task["status"] == "error":
        resp["error"] = task["error"]
    return JSONResponse(resp)


# ===== 目标引擎 API =====

class GoalRequest(ApiRequestModel):
    goal_type: Literal["maximize_profit", "flip_mod", "build_set", "find_bargain", "earn_platinum"]
    description: str = Field(min_length=1, max_length=200)
    target: str = Field(default="all", min_length=1, max_length=120)
    criteria: dict[str, Any] = Field(default_factory=dict)

    @field_validator("description", "target")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        return cls._strip_text(value, "goal")


class GoalOutcomeRequest(ApiRequestModel):
    action: str = Field(min_length=1, max_length=64)
    item_id: str = Field(min_length=1, max_length=120)
    price: int = Field(ge=1, le=100000)
    expected_profit: int = Field(default=0, ge=-100000, le=100000)
    actual_profit: int = Field(default=0, ge=-100000, le=100000)
    user_feedback: Literal["good", "bad", "ignored"] = "ignored"

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        return cls._strip_text(value, "action")

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        return cls._normalize_item_id(value)


@app.get("/api/goals")
async def get_goals() -> JSONResponse:
    """获取所有目标。"""
    memory = await _load_memory_async()
    goals = []
    for g in memory.active_goals:
        goals.append({
            "goal_id": g.goal_id,
            "goal_type": g.goal_type,
            "description": g.description,
            "target": g.target,
            "criteria": g.criteria,
            "status": g.status,
            "created_at": g.created_at,
            "results": g.results[-5:],  # 最近 5 条结果
            "result_count": len(g.results),
        })
    return JSONResponse({"goals": goals, "total": len(goals)})


@app.post("/api/goals")
async def create_goal_endpoint(request: GoalRequest) -> JSONResponse:
    """创建新目标。"""
    memory = await _load_memory_async()
    goal = create_goal(request.goal_type, request.description, request.target, request.criteria)
    memory = memory.with_goal(goal)
    await _save_memory_async(memory)
    return JSONResponse({
        "status": "ok",
        "goal_id": goal.goal_id,
        "goal_type": goal.goal_type,
        "description": goal.description,
    })


@app.delete("/api/goals/{goal_id}")
async def abandon_goal(goal_id: str) -> JSONResponse:
    """放弃目标。"""
    memory = await _load_memory_async()
    found = False
    for g in memory.active_goals:
        if g.goal_id == goal_id:
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="目标不存在")
    # 标记为 abandoned（通过替换）
    from dataclasses import replace
    goals = [replace(g, status="abandoned") if g.goal_id == goal_id else g for g in memory.active_goals]
    memory = replace(memory, active_goals=goals)
    await _save_memory_async(memory)
    return JSONResponse({"status": "ok", "goal_id": goal_id})


@app.post("/api/goals/{goal_id}/execute")
async def execute_goal(goal_id: str) -> JSONResponse:
    """手动触发目标执行（后台异步）。"""
    import uuid
    memory = await _load_memory_async()
    goal = None
    for g in memory.active_goals:
        if g.goal_id == goal_id and g.status == "active":
            goal = g
            break
    if not goal:
        raise HTTPException(status_code=404, detail="活跃目标不存在")

    task_id = uuid.uuid4().hex[:12]
    _evict_old_bg_tasks()
    _bg_tasks[task_id] = {"status": "running", "goal_id": goal_id, "result": None, "error": None, "created_at": _time.time()}

    async def _run():
        try:
            items = await asyncio.to_thread(_load_items_full)
            plan = plan_for_goal(goal)
            results = await asyncio.to_thread(execute_plan, plan, items, fetch_orders)
            mem = await _load_memory_async()
            for r in results[:10]:
                mem = mem.with_goal_result(goal_id, {
                    "item_id": r.get("item_id", ""),
                    "item_name": r.get("item_name", ""),
                    "profit": r.get("profit", 0),
                    "roi_pct": r.get("roi_pct", 0),
                    "source": r.get("source", ""),
                })
            await _save_memory_async(mem)
            _bg_tasks[task_id]["status"] = "done"
            _bg_tasks[task_id]["result"] = {"goal_id": goal_id, "results": results[:20], "total": len(results)}
        except Exception as exc:
            _bg_tasks[task_id]["status"] = "error"
            _bg_tasks[task_id]["error"] = str(exc)

    asyncio.create_task(_run())
    return JSONResponse({"task_id": task_id, "status": "running"})


@app.get("/api/goals/execute_status/{task_id}")
async def execute_status(task_id: str) -> JSONResponse:
    """查询目标执行状态。"""
    task = _bg_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    resp = {"status": task["status"]}
    if task["status"] == "done":
        resp["result"] = task["result"]
    elif task["status"] == "error":
        resp["error"] = task["error"]
    return JSONResponse(resp)


@app.post("/api/goals/{goal_id}/outcome")
async def record_outcome(goal_id: str, request: GoalOutcomeRequest) -> JSONResponse:
    """记录交易结果。"""
    memory = await _load_memory_async()
    outcome = record_trade_outcome(
        goal_id=goal_id,
        action=request.action,
        item_id=request.item_id,
        price=request.price,
        expected_profit=request.expected_profit,
        actual_profit=request.actual_profit,
        user_feedback=request.user_feedback,
    )
    memory = memory.with_trade_outcome(outcome)
    await _save_memory_async(memory)
    return JSONResponse({"status": "ok", "outcome_id": outcome.outcome_id})


@app.get("/api/goals/summary")
async def goals_summary() -> JSONResponse:
    """目标执行摘要。"""
    memory = await _load_memory_async()
    total_goals = len(memory.active_goals)
    active = sum(1 for g in memory.active_goals if g.status == "active")
    abandoned = sum(1 for g in memory.active_goals if g.status == "abandoned")
    total_outcomes = len(memory.trade_outcomes)
    good_outcomes = sum(1 for o in memory.trade_outcomes if o.user_feedback == "good")
    bad_outcomes = sum(1 for o in memory.trade_outcomes if o.user_feedback == "bad")
    total_expected = sum(o.expected_profit for o in memory.trade_outcomes)
    total_actual = sum(o.actual_profit for o in memory.trade_outcomes)

    return JSONResponse({
        "total_goals": total_goals,
        "active_goals": active,
        "abandoned_goals": abandoned,
        "total_outcomes": total_outcomes,
        "good_outcomes": good_outcomes,
        "bad_outcomes": bad_outcomes,
        "adoption_rate": round(good_outcomes / max(total_outcomes, 1) * 100, 1),
        "total_expected_profit": total_expected,
        "total_actual_profit": total_actual,
    })


class EarnPlatinumRequest(ApiRequestModel):
    target_amount: int = Field(default=100, ge=1, le=100000)
    budget: int = Field(default=500, ge=0, le=100000)


@app.post("/api/goals/earn")
async def create_earn_goal(request: EarnPlatinumRequest) -> JSONResponse:
    """创建攒白金目标 + 返回分解步骤。"""
    from ..goals import create_goal, decompose_platinum_goal
    memory = await _load_memory_async()

    goal = create_goal(
        goal_type="earn_platinum",
        description=f"攒 {request.target_amount} 白金",
        target="all",
        criteria={"target_amount": request.target_amount, "budget": request.budget},
    )
    memory = memory.with_goal(goal)
    await _save_memory_async(memory)

    items = _load_items_static()
    steps = decompose_platinum_goal(request.target_amount, request.budget, items)

    return JSONResponse({
        "goal_id": goal.goal_id,
        "target_amount": request.target_amount,
        "steps": steps,
        "total_steps": len(steps),
        "estimated_profit": sum(s.get("estimated_profit", 0) for s in steps),
    })


@app.get("/api/goals/{goal_id}/progress")
async def get_goal_progress(goal_id: str) -> JSONResponse:
    """获取目标进度。"""
    from ..goals import track_goal_progress
    memory = await _load_memory_async()

    goal = next((g for g in memory.active_goals if g.goal_id == goal_id), None)
    if not goal:
        return JSONResponse({"error": "目标不存在"}, status_code=404)

    target = goal.criteria.get("target_amount", 0)
    progress = track_goal_progress(goal_id, target, memory.trade_outcomes)

    return JSONResponse({
        "goal_id": progress.goal_id,
        "target_amount": progress.target_amount,
        "current_amount": progress.current_amount,
        "remaining": progress.remaining,
        "steps_completed": progress.steps_completed,
        "steps_total": progress.steps_total,
        "estimated_completion": progress.estimated_completion,
    })


def _load_items_static() -> list[dict]:
    """同步加载物品数据。"""
    import json as _json
    items_path = config.DATA_DIR / "items_full.json"
    if items_path.exists():
        with items_path.open("r", encoding="utf-8") as f:
            return _json.load(f)
    return []


# ===== 模式学习 API =====

@app.get("/api/patterns")
async def get_patterns() -> JSONResponse:
    """获取已学习的交易模式。"""
    memory = await _load_memory_async()
    return JSONResponse({
        "patterns": memory.learned_patterns,
        "total": len(memory.learned_patterns),
    })


# ===== 游戏事件 API =====

@app.get("/api/events")
async def get_events() -> JSONResponse:
    """获取当前游戏事件。"""
    from ..events import EventTracker
    tracker = EventTracker()
    tracker.load_cache()
    events = tracker.get_active_events()
    return JSONResponse({
        "events": [
            {
                "event_type": e.event_type,
                "description": e.description,
                "impact": e.impact,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "items_affected": e.items_affected,
            }
            for e in events
        ],
        "total": len(events),
    })


# ===== 利润计算器 API =====

class ProfitCalcRequest(ApiRequestModel):
    item_id: str = Field(min_length=1, max_length=120)
    material_costs: list[dict[str, int | str]] = Field(min_length=1, max_length=50)

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        return cls._normalize_item_id(value)


class ItemListRequest(ApiRequestModel):
    items: list[str] = Field(min_length=1, max_length=10)

    @field_validator("items", mode="before")
    @classmethod
    def normalize_items(cls, value):
        cleaned = []
        for item in value:
            text = cls._strip_text(str(item), "item")
            if len(text) > 120:
                raise ValueError("item 过长")
            cleaned.append(text)
        return cleaned


class AliasRequest(ApiRequestModel):
    name: str = Field(min_length=1, max_length=60)
    item_id: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return cls._strip_text(value, "name")

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        return cls._normalize_item_id(value)


class AliasDeleteRequest(ApiRequestModel):
    name: str = Field(min_length=1, max_length=60)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return cls._strip_text(value, "name")


@app.post("/api/profit/calculate")
async def calculate_profit(request: ProfitCalcRequest) -> JSONResponse:
    """计算制成品利润"""
    try:
        # 获取成品当前市场价格
        orders = await fetch_orders_async(request.item_id)
        rank_filter = get_max_rank_from_orders(orders)
        sellers = best_sellers(orders, limit=1, rank_filter=rank_filter)
        buyers = best_buyers(orders, limit=1, rank_filter=rank_filter)

        sell_price = sellers[0].platinum if sellers else None
        buy_price = buyers[0].platinum if buyers else None

        # 计算材料总成本
        total_cost = 0
        materials_detail = []
        for mat in request.material_costs:
            qty = mat.get("quantity", 1)
            unit_cost = mat.get("unit_cost", 0)
            mat_total = qty * unit_cost
            total_cost += mat_total
            materials_detail.append({
                "item_id": mat["item_id"],
                "display": display_item_name(mat["item_id"]),
                "quantity": qty,
                "unit_cost": unit_cost,
                "total_cost": mat_total,
            })

        # 计算利润
        profit_sell = sell_price - total_cost if sell_price else None
        profit_buy = buy_price - total_cost if buy_price else None
        margin_sell = round((profit_sell / total_cost) * 100, 1) if profit_sell is not None and total_cost > 0 else None
        margin_buy = round((profit_buy / total_cost) * 100, 1) if profit_buy is not None and total_cost > 0 else None

        return JSONResponse({
            "item_id": request.item_id,
            "display": display_item_name(request.item_id),
            "sell_price": sell_price,
            "buy_price": buy_price,
            "total_cost": total_cost,
            "materials": materials_detail,
            "profit": {
                "sell_profit": profit_sell,
                "buy_profit": profit_buy,
                "sell_margin": margin_sell,
                "buy_margin": margin_buy,
            },
            "recommendation": "盈利" if (profit_sell and profit_sell > 0) else "亏损",
        })
    except Exception as e:
        logger.error("计算利润失败: %s", e)
        return JSONResponse({"error": "计算利润失败"}, status_code=500)


@app.get("/api/suggest")
async def suggest_items(q: str = Query("", max_length=60)) -> JSONResponse:
    if not q or len(q) < 1:
        return JSONResponse({"suggestions": []})

    q_lower = q.lower()
    suggestions = set()

    # 从别名和字典中搜索
    resolver = chat_agent.resolver

    # 搜索别名
    for name, item_id in resolver.aliases.items():
        if q_lower in name.lower():
            suggestions.add(name)
            if len(suggestions) >= 10:
                break

    # 搜索字典
    if len(suggestions) < 10:
        for name, item_id in resolver.dictionary.items():
            if q_lower in name.lower():
                suggestions.add(name)
                if len(suggestions) >= 10:
                    break

    return JSONResponse({"suggestions": sorted(list(suggestions))[:10]})


@app.post("/api/compare")
async def compare_items(request: ItemListRequest) -> JSONResponse:
    results = []
    for item_name in request.items[:3]:
        try:
            result = chat_agent.resolver.resolve(item_name)
            orders = await fetch_orders_async(result.item_id)
            rank_filter = get_max_rank_from_orders(orders)
            sellers = best_sellers(orders, limit=1, rank_filter=rank_filter)
            buyers = best_buyers(orders, limit=1, rank_filter=rank_filter)

            item_result = {
                "name": display_item_name(result.item_id),
                "item_id": result.item_id,
                "sell_price": sellers[0].platinum if sellers else None,
                "buy_price": buyers[0].platinum if buyers else None,
            }

            # 添加物品类型和等级信息
            type_info = get_item_type_info(result.item_id)
            if type_info:
                item_result["item_type"] = type_info["type"]
                item_result["item_type_display"] = type_info["type_display"]
                item_result["max_rank"] = type_info["max_rank"]

            results.append(item_result)
        except Exception as e:
            logger.error("对比物品失败 %s: %s", item_name, e)
            results.append({"name": item_name, "error": "查询失败"})
    return JSONResponse({"items": results})


@app.post("/api/batch_query")
async def batch_query_items(request: ItemListRequest) -> JSONResponse:
    """批量查询物品价格（支持更多物品）"""
    results = []
    for item_name in request.items[:10]:  # 最多支持10个物品
        try:
            result = chat_agent.resolver.resolve(item_name)
            orders = await fetch_orders_async(result.item_id)
            rank_filter = get_max_rank_from_orders(orders)
            sellers = best_sellers(orders, limit=1, rank_filter=rank_filter)
            buyers = best_buyers(orders, limit=1, rank_filter=rank_filter)

            item_result = {
                "name": display_item_name(result.item_id),
                "item_id": result.item_id,
                "sell_price": sellers[0].platinum if sellers else None,
                "buy_price": buyers[0].platinum if buyers else None,
                "seller": sellers[0].user_name if sellers else None,
                "buyer": buyers[0].user_name if buyers else None,
            }

            # 添加物品类型和等级信息
            type_info = get_item_type_info(result.item_id)
            if type_info:
                item_result["item_type"] = type_info["type"]
                item_result["item_type_display"] = type_info["type_display"]
                item_result["max_rank"] = type_info["max_rank"]

            # 添加杜卡特信息
            ducat_value = get_ducat_value(result.item_id)
            if ducat_value is not None:
                item_result["ducat_value"] = ducat_value
                if sellers and sellers[0].platinum:
                    efficiency = calculate_ducat_efficiency(sellers[0].platinum, ducat_value)
                    if efficiency:
                        item_result["ducat_efficiency"] = efficiency

            # 计算价差
            if item_result["sell_price"] and item_result["buy_price"]:
                item_result["spread"] = item_result["sell_price"] - item_result["buy_price"]

            results.append(item_result)
        except Exception as e:
            logger.error("批量查询失败 %s: %s", item_name, e)
            results.append({"name": item_name, "error": "查询失败"})

    return JSONResponse({
        "items": results,
        "total": len(results),
        "success": len([r for r in results if "error" not in r])
    })


@app.get("/api/aliases")
async def get_aliases() -> JSONResponse:
    aliases = await asyncio.to_thread(load_custom_aliases)
    return JSONResponse({"aliases": [
        {"name": k, "item_id": v, "display": display_item_name(v)}
        for k, v in aliases.items()
    ]})


@app.post("/api/aliases")
async def add_alias(request: AliasRequest) -> JSONResponse:
    name = request.name.strip()
    item_id = request.item_id.strip()
    if not name or not item_id:
        return JSONResponse({"error": "名称和物品ID不能为空"}, status_code=400)
    aliases = await asyncio.to_thread(load_custom_aliases)
    aliases[name] = item_id
    await asyncio.to_thread(save_custom_aliases, aliases)
    inject_custom_aliases()
    return JSONResponse({"status": "ok", "name": name, "item_id": item_id})


@app.delete("/api/aliases")
async def remove_alias(request: AliasDeleteRequest) -> JSONResponse:
    name = request.name.strip()
    if not name:
        return JSONResponse({"error": "名称不能为空"}, status_code=400)
    aliases = await asyncio.to_thread(load_custom_aliases)
    if name in aliases:
        del aliases[name]
        await asyncio.to_thread(save_custom_aliases, aliases)
        inject_custom_aliases()
    return JSONResponse({"status": "ok"})


@app.get("/api/search_items")
async def search_items(q: str = Query("", max_length=60)) -> JSONResponse:
    """根据物品名搜索候选列表（用于别名绑定）"""
    if not q or len(q) < 1:
        return JSONResponse({"items": []})

    q_lower = q.lower()
    seen_ids = set()
    results = []

    # 搜索字典（中文名/英文名 → item_id）
    for name_key, item_id in chat_agent.resolver.dictionary.items():
        if q_lower in name_key:
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                results.append({
                    "item_id": item_id,
                    "display": display_item_name(item_id),
                })
                if len(results) >= 10:
                    break

    # 搜索已有的别名
    if len(results) < 10:
        for name_key, item_id in chat_agent.resolver.aliases.items():
            if q_lower in name_key and item_id not in seen_ids:
                seen_ids.add(item_id)
                results.append({
                    "item_id": item_id,
                    "display": display_item_name(item_id),
                })
                if len(results) >= 10:
                    break

    # 搜索生成的别名
    if len(results) < 10:
        for name_key, item_id in chat_agent.resolver.generated_aliases.items():
            if q_lower in name_key and item_id not in seen_ids:
                seen_ids.add(item_id)
                results.append({
                    "item_id": item_id,
                    "display": display_item_name(item_id),
                })
                if len(results) >= 10:
                    break

    return JSONResponse({"items": results})


@app.get("/api/resolve/{name}")
async def resolve_item(name: str) -> JSONResponse:
    """尝试解析物品名，返回结果或候选建议"""
    try:
        result = chat_agent.resolver.resolve(name)
        return JSONResponse({
            "found": True,
            "item_id": result.item_id,
            "source": result.source,
            "display": display_item_name(result.item_id)
        })
    except (LookupError, ValueError):
        # 搜索相似物品作为候选
        suggestions = []
        q_lower = name.lower()
        for alias_name, alias_id in chat_agent.resolver.aliases.items():
            if q_lower in alias_name or alias_name in q_lower:
                suggestions.append({"name": alias_name, "item_id": alias_id})
                if len(suggestions) >= 5:
                    break
        return JSONResponse({
            "found": False,
            "suggestions": suggestions
        })


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data).get("message", "")
            await websocket.send_json({"status": "processing"})
            # 真正的流式输出：逐 token 从 LLM 获取
            full_reply = []
            try:
                async for token in chat_agent.answer_stream(message):
                    full_reply.append(token)
                    await websocket.send_json({"token": token})
            except Exception:
                # 流式失败，回退到同步调用
                reply = await asyncio.to_thread(chat_agent.answer, message)
                full_reply = [reply]
                await websocket.send_json({"token": reply})
            reply_text = "".join(full_reply)
            await websocket.send_json({"done": True, "reply": reply_text})
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    await websocket.accept()
    ws_connections.append(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in ws_connections:
            ws_connections.remove(websocket)


async def broadcast_alert(notification: AlertNotification):
    message = {
        "type": "alert",
        "item": notification.item_display,
        "direction": notification.alert.direction,
        "price": notification.alert.price,
        "current_price": notification.current_price,
    }
    for ws in list(ws_connections):
        try:
            await ws.send_json(message)
        except Exception:
            pass
    # 微信推送
    if push_client.available and push_config.push_alerts:
        direction_zh = "低于" if notification.alert.direction == "below" else "高于"
        await asyncio.to_thread(
            push_client.send_text,
            f"价格提醒: {notification.item_display}",
            f"{notification.item_display} {direction_zh} {notification.alert.price}p，当前 {notification.current_price}p",
        )


async def broadcast_watch(notification: WatchNotification):
    price_info = ""
    if notification.sell_price is not None:
        price_info = f"卖价 {notification.sell_price}p"
    if notification.buy_price is not None:
        price_info += f" 买价 {notification.buy_price}p" if price_info else f"买价 {notification.buy_price}p"

    message = {
        "type": "watch",
        "item_id": notification.item_id,
        "item_name": notification.item_name,
        "sell_price": notification.sell_price,
        "buy_price": notification.buy_price,
        "price_info": price_info.strip(),
        "content": notification.content,
        "frequency": notification.frequency,
    }
    for ws in list(ws_connections):
        try:
            await ws.send_json(message)
        except Exception:
            pass
    # 微信推送
    if push_client.available and push_config.push_watches:
        await asyncio.to_thread(
            push_client.send_text,
            f"关注通知: {notification.item_name}",
            f"{notification.item_name} {price_info.strip()}",
        )


async def broadcast_enriched(notification: EnrichedNotification):
    message = {
        "type": "enriched_analysis",
        "item_id": notification.item_id,
        "item_display": notification.item_display,
        "notification_type": notification.notification_type,
        "analysis": notification.analysis,
        "priority": notification.priority,
        "raw_data": notification.raw_data,
    }
    for ws in list(ws_connections):
        try:
            await ws.send_json(message)
        except Exception:
            pass


async def broadcast_goal_opportunity(opportunity: dict):
    message = {
        "type": "goal_opportunity",
        "item_id": opportunity.get("item_id", ""),
        "message": opportunity.get("message", ""),
        "priority": opportunity.get("priority", 2),
    }
    for ws in list(ws_connections):
        try:
            await ws.send_json(message)
        except Exception:
            pass


async def broadcast_proactive_push(push: ProactivePush):
    message = {
        "type": "proactive_push",
        "item_id": push.item_id,
        "item_display": push.item_display,
        "push_type": push.push_type,
        "priority": push.priority,
        "message": push.message,
        "action_suggestion": push.action_suggestion,
        "data": push.data,
    }
    for ws in list(ws_connections):
        try:
            await ws.send_json(message)
        except Exception:
            pass
    # 微信推送（仅高优先级）
    if push_client.available and push_config.push_proactive and push.priority <= 2:
        await asyncio.to_thread(
            push_client.send_text,
            f"交易机会: {push.item_display}",
            f"{push.message}\n建议: {push.action_suggestion}",
        )


async def broadcast_fissure_alert(msg: str):
    message = {"type": "fissure_alert", "message": msg}
    for ws in list(ws_connections):
        try:
            await ws.send_json(message)
        except Exception:
            pass


async def broadcast_baro_report(report_text: str):
    message = {"type": "baro_recommendation", "message": report_text}
    for ws in list(ws_connections):
        try:
            await ws.send_json(message)
        except Exception:
            pass


def setup_monitor():
    def on_alert_callback(notification: AlertNotification):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_alert(notification), loop)
        except Exception as exc:
            logger.debug("alert 回调异常: %s", exc)

    def on_watch_callback(notification: WatchNotification):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_watch(notification), loop)
        except Exception as exc:
            logger.debug("watch 回调异常: %s", exc)

    def on_goal_opportunity_callback(opportunity: dict):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_goal_opportunity(opportunity), loop)
        except Exception as exc:
            logger.debug("goal_opportunity 回调异常: %s", exc)

    def on_proactive_push_callback(push: ProactivePush):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_proactive_push(push), loop)
        except Exception as exc:
            logger.debug("proactive_push 回调异常: %s", exc)

    def on_daily_report_callback(report_text: str):
        """每日报告同时推送到飞书"""
        try:
            if feishu_bot.available:
                feishu_cfg = FeishuConfig.load()
                if feishu_cfg.enabled:
                    # 获取飞书 chat_id（从配置或缓存中）
                    chat_id_path = config.DATA_DIR / "feishu_chat_id.txt"
                    if chat_id_path.exists():
                        chat_id = chat_id_path.read_text(encoding="utf-8").strip()
                        if chat_id:
                            feishu_bot.send(chat_id, report_text)
                            logger.info("每日报告已推送到飞书")
        except Exception as exc:
            logger.warning("飞书每日报告推送失败: %s", exc)
            pass

    def on_fissure_callback(msg: str, fissure, alert):
        """裂缝匹配时推送到飞书和微信"""
        try:
            # WebSocket 广播
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_fissure_alert(msg), loop)
        except Exception as exc:
            logger.debug("fissure WebSocket 回调异常: %s", exc)
        # 飞书推送
        try:
            if feishu_bot.available:
                feishu_cfg = FeishuConfig.load()
                if feishu_cfg.enabled:
                    chat_id_path = config.DATA_DIR / "feishu_chat_id.txt"
                    if chat_id_path.exists():
                        chat_id = chat_id_path.read_text(encoding="utf-8").strip()
                        if chat_id:
                            feishu_bot.send(chat_id, msg)
        except Exception as exc:
            logger.debug("飞书裂缝推送失败: %s", exc)

    def on_baro_recommendation_callback(report_text: str):
        """Baro 推荐报告推送到飞书和微信"""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_baro_report(report_text), loop)
        except Exception as exc:
            logger.debug("baro 回调异常: %s", exc)
        # 飞书推送
        try:
            if feishu_bot.available:
                feishu_cfg = FeishuConfig.load()
                if feishu_cfg.enabled:
                    chat_id_path = config.DATA_DIR / "feishu_chat_id.txt"
                    if chat_id_path.exists():
                        chat_id = chat_id_path.read_text(encoding="utf-8").strip()
                        if chat_id:
                            feishu_bot.send(chat_id, report_text)
        except Exception as exc:
            logger.debug("飞书 Baro 推荐推送失败: %s", exc)

    from ..knowledge import MarketKnowledge
    knowledge = MarketKnowledge.load()

    global monitor
    monitor = PriceMonitor(
        on_alert=on_alert_callback,
        on_watch=on_watch_callback,
        on_goal_opportunity=on_goal_opportunity_callback,
        on_proactive_push=on_proactive_push_callback,
        on_daily_report=on_daily_report_callback,
        on_fissure=on_fissure_callback,
        on_baro_recommendation=on_baro_recommendation_callback,
        knowledge=knowledge,
    )
    monitor.start()

    # 注入知识库和事件追踪到聊天层
    chat_agent.knowledge = monitor.knowledge
    chat_agent.event_tracker = monitor.event_tracker



# ── 装备百科 / MOD数据库 / 遗物搜索 ──────────────────────────────────

WARFRAME_ITEMS_DIR = Path(__file__).parent.parent.parent / "githubProduct" / "warframe-items" / "data" / "json"
RELIC_DROP_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "relics_drop_data.json"
EXPORT_DIR = Path(__file__).parent.parent.parent / "data" / "export"

_wiki_cache: dict[str, Any] = {}
_zh_name_cache: dict[str, dict[str, str]] = {}

RELIC_TIER_ZH = {"Lith": "古纪", "Meso": "前纪", "Neo": "中纪", "Axi": "后纪", "Requiem": "安魂"}


def _load_wiki_json(filename: str) -> list[dict]:
    if filename not in _wiki_cache:
        path = WARFRAME_ITEMS_DIR / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                _wiki_cache[filename] = json.load(f)
        else:
            _wiki_cache[filename] = []
    return _wiki_cache[filename]


def _load_zh_names(category: str) -> dict[str, str]:
    """加载中文名映射 {uniqueName: 中文名}"""
    if category not in _zh_name_cache:
        mapping = {}
        filename = f"Export{category}_zh.json"
        path = EXPORT_DIR / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get(f"Export{category}", data) if isinstance(data, dict) else data
            if isinstance(items, list):
                for item in items:
                    uid = item.get("uniqueName", "")
                    name = item.get("name", "")
                    if uid and name:
                        mapping[uid] = name
        _zh_name_cache[category] = mapping
    return _zh_name_cache[category]


def _market_url(english_name: str) -> str:
    """生成 warframe.market 链接（非 Prime 物品）"""
    url_name = english_name.lower().replace(" ", "_").replace("'", "")
    return f"https://warframe.market/items/{url_name}"


def _market_url_prime_blueprint(item_name: str) -> str:
    """为 Prime 物品生成蓝图的 market 链接（Prime 物品在 market 只能搜部件）"""
    # "Mirage Prime" -> "mirage_prime_blueprint"
    # "Acceltra Prime" -> "acceltra_prime_blueprint"
    url_name = item_name.lower().replace(" ", "_").replace("'", "")
    return f"https://warframe.market/items/{url_name}_blueprint"


def _extract_components(item: dict) -> list[dict]:
    """提取可交易的 Prime 部件信息"""
    components = []
    for comp in item.get("components", []):
        # 跳过资源类部件（如 Orokin Cell）
        if comp.get("type") == "Resource":
            continue
        components.append({
            "name": comp.get("name", ""),
            "tradable": comp.get("tradable", False),
            "ducats": comp.get("ducats", 0),
        })
    return components


@app.get("/api/wiki/warframes")
async def wiki_warframes(q: str = ""):
    data = _load_wiki_json("Warframes.json")
    zh_map = _load_zh_names("Warframes")
    results = []
    q_lower = q.lower()
    for wf in data:
        name = wf.get("name", "")
        uid = wf.get("uniqueName", "")
        name_zh = zh_map.get(uid, "")
        if q and q_lower not in name.lower() and q not in name_zh:
            continue
        is_prime = wf.get("isPrime", False)
        # Prime 战甲在 market 只能搜部件，默认跳转蓝图
        market_url = _market_url_prime_blueprint(name) if is_prime else _market_url(name)
        components = _extract_components(wf) if is_prime else []
        results.append({
            "name": name,
            "nameZh": name_zh,
            "uniqueName": uid,
            "health": wf.get("health", 0),
            "shield": wf.get("shield", 0),
            "armor": wf.get("armor", 0),
            "power": wf.get("power", 0),
            "sprintSpeed": wf.get("sprintSpeed", 0),
            "masteryReq": wf.get("masteryReq", 0),
            "description": wf.get("description", ""),
            "passiveDescription": wf.get("passiveDescription", ""),
            "marketUrl": market_url,
            "isPrime": is_prime,
            "tradable": wf.get("tradable", False),
            "components": components,
            "abilities": [
                {"name": a.get("name", ""), "description": a.get("description", "")}
                for a in wf.get("abilities", [])
            ],
        })
    results.sort(key=lambda x: x["name"])
    return {"warframes": results, "total": len(results)}


@app.get("/api/wiki/weapons")
async def wiki_weapons(type: str = "", q: str = ""):
    file_map = {
        "primary": "Primary.json",
        "secondary": "Secondary.json",
        "melee": "Melee.json",
        "archgun": "Arch-Gun.json",
        "archmelee": "Arch-Melee.json",
    }
    if type and type in file_map:
        files = [file_map[type]]
    else:
        files = [file_map["primary"], file_map["secondary"], file_map["melee"]]

    zh_map = _load_zh_names("Weapons")
    results = []
    q_lower = q.lower()
    for fname in files:
        data = _load_wiki_json(fname)
        category = fname.replace(".json", "").lower()
        cat_zh = {"primary": "主武器", "secondary": "副武器", "melee": "近战武器",
                  "archgun": "空战枪械", "archmelee": "空战近战"}.get(category, category)
        for w in data:
            name = w.get("name", "")
            uid = w.get("uniqueName", "")
            name_zh = zh_map.get(uid, "")
            if q and q_lower not in name.lower() and q not in name_zh:
                continue
            is_prime = w.get("isPrime", False)
            # Prime 武器在 market 只能搜部件，默认跳转蓝图
            market_url = _market_url_prime_blueprint(name) if is_prime else _market_url(name)
            components = _extract_components(w) if is_prime else []
            results.append({
                "name": name,
                "nameZh": name_zh,
                "uniqueName": uid,
                "category": category,
                "categoryZh": cat_zh,
                "totalDamage": w.get("totalDamage", 0),
                "criticalChance": w.get("criticalChance", 0),
                "criticalMultiplier": w.get("criticalMultiplier", 0),
                "procChance": w.get("procChance", 0),
                "fireRate": w.get("fireRate", 0),
                "masteryReq": w.get("masteryReq", 0),
                "magazineSize": w.get("magazineSize", 0),
                "reloadTime": w.get("reloadTime", 0),
                "trigger": w.get("trigger", ""),
                "noise": w.get("noise", ""),
                "accuracy": w.get("accuracy", 0),
                "description": w.get("description", ""),
                "marketUrl": market_url,
                "tradable": w.get("tradable", False),
                "isPrime": is_prime,
                "components": components,
            })
    results.sort(key=lambda x: x["name"])
    return {"weapons": results, "total": len(results)}


@app.get("/api/wiki/mods")
async def wiki_mods(q: str = "", polarity: str = "", rarity: str = "", category: str = ""):
    data = _load_wiki_json("Mods.json")
    zh_map = _load_zh_names("Upgrades")
    results = []
    q_lower = q.lower()
    for m in data:
        name = m.get("name", "")
        uid = m.get("uniqueName", "")
        name_zh = zh_map.get(uid, "")
        if q and q_lower not in name.lower() and q not in name_zh:
            continue
        if polarity and m.get("polarity", "") != polarity:
            continue
        if rarity and (m.get("rarity", "") or "").lower() != rarity.lower():
            continue
        if category:
            mod_type = (m.get("type", "") or "").lower()
            cat_lower = category.lower()
            if cat_lower not in mod_type:
                continue
        results.append({
            "name": name,
            "nameZh": name_zh,
            "uniqueName": uid,
            "polarity": m.get("polarity", ""),
            "rarity": m.get("rarity", ""),
            "baseDrain": m.get("baseDrain", 0),
            "maxRank": m.get("fusionLimit", 0),
            "type": m.get("type", ""),
            "compatName": m.get("compatName", ""),
            "isAugment": m.get("isAugment", False),
            "tradable": m.get("tradable", False),
            "description": m.get("description", ""),
            "marketUrl": _market_url(name),
        })
    results.sort(key=lambda x: x["name"])
    return {"mods": results[:200], "total": len(results)}


RELIC_VAULT_STATUS_PATH = Path(__file__).parent.parent.parent / "data" / "relic_vault_status.json"
_relic_vault_cache: dict[str, dict] = {}


def _load_relic_vault_status() -> dict[str, dict]:
    if not _relic_vault_cache:
        if RELIC_VAULT_STATUS_PATH.exists():
            with open(RELIC_VAULT_STATUS_PATH, "r", encoding="utf-8") as f:
                _relic_vault_cache.update(json.load(f))
    return _relic_vault_cache


def _get_vault_status(relic_base_name: str) -> str:
    """返回遗物入库状态：入库 / 非入库"""
    vault_data = _load_relic_vault_status()
    info = vault_data.get(relic_base_name, {})
    if info.get("vaulted"):
        return "入库"
    return "非入库"


@app.get("/api/riven/auctions")
async def get_riven_auctions(weapon: str = "") -> JSONResponse:
    """获取裂罅 Mod 拍卖数据（通过 Playwright 抓取）"""
    try:
        from ..scraper import scrape_riven_auctions, scrape_sync
        rivens = scrape_sync(scrape_riven_auctions(weapon))
        return JSONResponse({
            "rivens": [
                {
                    "weapon": r.weapon,
                    "mod_name": r.mod_name,
                    "attributes": r.attributes,
                    "price": r.price,
                    "seller": r.seller,
                }
                for r in rivens
            ],
            "total": len(rivens),
        })
    except Exception as e:
        logger.error("紫卡查询失败: %s", e)
        return JSONResponse({"error": "紫卡查询失败", "rivens": []}, status_code=500)


@app.get("/api/market/scrape/{item_url_name}")
async def scrape_market_orders(item_url_name: str) -> JSONResponse:
    """通过 Playwright 抓取 warframe.market 订单（绕过 Cloudflare）"""
    try:
        from ..scraper import scrape_orders, scrape_sync
        orders = scrape_sync(scrape_orders(item_url_name))
        return JSONResponse({
            "orders": [
                {
                    "item_id": o.item_id,
                    "order_type": o.order_type,
                    "platinum": o.platinum,
                    "quantity": o.quantity,
                    "user_name": o.user_name,
                    "status": o.status,
                    "reputation": o.reputation,
                }
                for o in orders
            ],
            "total": len(orders),
        })
    except Exception as e:
        logger.error("紫卡订单查询失败: %s", e)
        return JSONResponse({"error": "紫卡订单查询失败", "orders": []}, status_code=500)


@app.get("/api/relic/search")
async def relic_search(q: str = ""):
    if not q:
        return {"results": [], "total": 0}
    if not RELIC_DROP_DATA_PATH.exists():
        return {"results": [], "total": 0, "error": "遗物数据不可用"}

    relic_data = _preload_relic_drop_data()

    q_lower = q.lower()
    results = []
    seen = set()
    for relic in relic_data.get("relics", []):
        for reward in relic.get("rewards", []):
            item_name = reward.get("itemName", "")
            if q_lower in item_name.lower():
                tier_en = relic.get("tier", "")
                tier_zh = RELIC_TIER_ZH.get(tier_en, tier_en)
                relic_id = f"{tier_en} {relic['relicName']}"
                vault_status = _get_vault_status(relic_id)
                key = f"{relic_id}_{item_name}"
                if key in seen:
                    break
                seen.add(key)
                results.append({
                    "relicName": f"{tier_zh} {relic['relicName']}",
                    "relicNameEn": relic_id,
                    "state": relic.get("state", "Intact"),
                    "itemName": item_name,
                    "rarity": reward.get("rarity", ""),
                    "rarityZh": {"Rare": "稀有", "Uncommon": "非常规", "Common": "常规"}.get(reward.get("rarity", ""), reward.get("rarity", "")),
                    "chance": reward.get("chance", 0),
                    "vaultStatus": vault_status,
                })
                break
    results.sort(key=lambda x: (-{"Rare": 3, "Uncommon": 2, "Common": 1}.get(x["rarity"], 0), x["relicName"]))
    return {"results": results[:100], "total": len(results)}


@app.get("/api/relic/sources/{relic_name}")
async def get_relic_sources(relic_name: str):
    """获取遗物的掉落来源（哪些任务掉落）"""
    all_sources = _load_relic_sources()
    if not all_sources:
        return JSONResponse({"sources": [], "error": "来源数据不可用"})

    sources = all_sources.get(relic_name, [])
    return JSONResponse({
        "relicName": relic_name,
        "sources": sources[:30],  # 最多返回30个来源
        "total": len(sources),
    })


@app.get("/api/relic/drops/{tier}/{relic_name}")
async def get_relic_drops(tier: str, relic_name: str):
    """获取指定遗物的掉落信息（包含所有精炼等级）"""
    tier_upper = tier.capitalize()
    relic_name_upper = relic_name.upper()

    # 优先使用详细数据（来自 warframe-drop-data）
    detailed_path = config.DATA_DIR / "relics_detailed" / tier_upper / f"{relic_name_upper}.json"
    if detailed_path.exists():
        def _read_detailed():
            with open(detailed_path, "r", encoding="utf-8") as f:
                return json.load(f)

        data = await asyncio.to_thread(_read_detailed)

        vault_status = _get_vault_status(f"{tier_upper} {relic_name}")

        # 转换为前端友好格式
        rewards_by_state = {}
        for state, rewards in data.get("rewards", {}).items():
            rewards_by_state[state] = [
                {
                    "itemName": r.get("itemName", ""),
                    "rarity": r.get("rarity", ""),
                    "rarityZh": {"Rare": "稀有", "Uncommon": "非常规", "Common": "常规"}.get(r.get("rarity", ""), r.get("rarity", "")),
                    "chance": r.get("chance", 0),
                }
                for r in rewards
            ]

        return JSONResponse({
            "tier": tier_upper,
            "relicName": relic_name,
            "displayName": f"{RELIC_TIER_ZH.get(tier_upper, tier_upper)} {relic_name}",
            "vaultStatus": vault_status,
            "rewardsByState": rewards_by_state,
            "states": ["Intact", "Exceptional", "Flawless", "Radiant"],
            "stateLabels": {"Intact": "完好", "Exceptional": "卓越", "Flawless": "无瑕", "Radiant": "光辉"},
        })

    # 回退到旧数据
    relic_data = _preload_relic_drop_data()
    if not relic_data:
        return JSONResponse({"error": "遗物数据不可用"}, status_code=404)

    results = []
    for relic in relic_data.get("relics", []):
        if relic.get("tier", "").upper() == tier_upper and relic.get("relicName", "").upper() == relic_name_upper:
            state = relic.get("state", "Intact")
            for reward in relic.get("rewards", []):
                results.append({
                    "state": state,
                    "itemName": reward.get("itemName", ""),
                    "rarity": reward.get("rarity", ""),
                    "rarityZh": {"Rare": "稀有", "Uncommon": "非常规", "Common": "常规"}.get(reward.get("rarity", ""), reward.get("rarity", "")),
                    "chance": reward.get("chance", 0),
                })

    if not results:
        return JSONResponse({"error": f"未找到遗物 {tier} {relic_name}"}, status_code=404)

    vault_status = _get_vault_status(f"{tier_upper} {relic_name}")

    return JSONResponse({
        "tier": tier_upper,
        "relicName": relic_name,
        "displayName": f"{RELIC_TIER_ZH.get(tier_upper, tier_upper)} {relic_name}",
        "vaultStatus": vault_status,
        "rewards": results,
    })


static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="root")
