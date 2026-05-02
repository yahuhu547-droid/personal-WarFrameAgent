from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from ..chat import ChatAgent, build_item_context_result
from ..dictionary import normalize_lookup_key, normalize_market_id
from ..market import fetch_orders_async, best_sellers, best_buyers
from ..memory import AgentMemory, PriceAlert, MEMORY_PATH
from ..monitor import PriceMonitor, AlertNotification
from ..names import display_item_name
from ..price_history import PriceHistoryDB
from ..trade_history import TradeHistoryDB
from ..formatter import build_whisper

app = FastAPI(title="Warframe Trading Agent API")

chat_agent = ChatAgent()
monitor = PriceMonitor()
price_db = PriceHistoryDB()
trade_db = TradeHistoryDB()
ws_connections: list[WebSocket] = []

# 自定义别名存储
CUSTOM_ALIASES_PATH = Path(__file__).parent.parent.parent / "data" / "custom_aliases.json"

# 杜卡特数据缓存
_ducat_cache: dict[str, dict] = {}
_ducat_cache_time = 0
DUCAT_CACHE_TTL = 3600  # 1小时缓存

# 物品类型和等级缓存
_item_type_cache: dict[str, dict] = {}


def get_item_type_info(item_id: str) -> dict | None:
    """获取物品类型和最大等级信息"""
    if item_id in _item_type_cache:
        return _item_type_cache[item_id]

    item_id_lower = item_id.lower()

    # 检查是否是赋能 (Arcane)
    if item_id_lower.startswith("arcane_"):
        # 从导出数据中查找赋能的最大等级
        export_dir = Path(__file__).parent.parent.parent / "data" / "export"
        try:
            with (export_dir / "ExportRelicArcane_en.json").open("r", encoding="utf-8-sig") as f:
                data = json.load(f)
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
    export_dir = Path(__file__).parent.parent.parent / "data" / "export"
    try:
        with (export_dir / "ExportUpgrades_en.json").open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
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


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class MemoryResponse(BaseModel):
    favorites: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    preferences: dict[str, Any]
    watchlist: list[dict[str, Any]] = []


class FavoriteRequest(BaseModel):
    item_id: str


class AlertRequest(BaseModel):
    item_id: str
    direction: str
    price: int
    note: str = ""


class PreferenceRequest(BaseModel):
    key: str
    value: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    reply = await asyncio.to_thread(chat_agent.answer, request.message)
    return ChatResponse(reply=reply)


@app.get("/api/memory", response_model=MemoryResponse)
async def get_memory() -> MemoryResponse:
    memory = AgentMemory.load(MEMORY_PATH)
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
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.with_favorite_item(request.item_id)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.delete("/api/fav")
async def remove_favorite(request: FavoriteRequest) -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.without_favorite_item(request.item_id)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.post("/api/alert")
async def add_alert(request: AlertRequest) -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.with_price_alert(request.item_id, request.direction, request.price, request.note)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.delete("/api/alert")
async def remove_alert(request: AlertRequest) -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.without_price_alert(request.item_id, request.direction, request.price)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


# ===== 关注列表 API =====

class WatchRequest(BaseModel):
    item_id: str
    item_name: str
    frequency: str = "daily"
    time: str = "09:00"
    content: str = "top3_buyers"


@app.get("/api/watchlist")
async def get_watchlist() -> JSONResponse:
    """获取关注列表"""
    memory = AgentMemory.load(MEMORY_PATH)
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
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.with_watch_item(
        item_id=request.item_id,
        item_name=request.item_name,
        frequency=request.frequency,
        time=request.time,
        content=request.content,
    )
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.delete("/api/watchlist/{item_id}")
async def remove_watch_item(item_id: str) -> JSONResponse:
    """移除关注项"""
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.without_watch_item(item_id)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.post("/api/pref")
async def set_preference(request: PreferenceRequest) -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    memory = memory.set_preference(request.key, request.value)
    memory.save(MEMORY_PATH)
    return JSONResponse({"status": "ok"})


@app.get("/api/history/{item_id}")
async def get_history(item_id: str, range: str = "all") -> JSONResponse:
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


@app.get("/api/favorites_prices")
async def get_favorites_prices() -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
    results = []
    for item_id in memory.favorite_items:
        try:
            orders = await fetch_orders_async(item_id)
            sellers = best_sellers(orders, limit=1)
            buyers = best_buyers(orders, limit=1)
            results.append({
                "item_id": item_id,
                "sell_price": sellers[0].platinum if sellers else None,
                "buy_price": buyers[0].platinum if buyers else None,
            })
        except Exception:
            results.append({"item_id": item_id, "sell_price": None, "buy_price": None})
    return JSONResponse({"items": results})


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
        if item_id.startswith("arcane_") and ctx.best_sell_price:
            result["max_level_cost"] = ctx.best_sell_price * 21

        # 添加物品类型和等级信息
        type_info = get_item_type_info(item_id)
        if type_info:
            result["item_type"] = type_info["type"]
            result["item_type_display"] = type_info["type_display"]
            result["max_rank"] = type_info["max_rank"]
            result["rarity"] = type_info.get("rarity", "COMMON")

        # 添加杜卡特信息
        ducat_value = get_ducat_value(item_id)
        if ducat_value is not None:
            result["ducat_value"] = ducat_value
            # 计算杜卡特效率
            if ctx.best_sell_price:
                efficiency = calculate_ducat_efficiency(ctx.best_sell_price, ducat_value)
                if efficiency:
                    result["ducat_efficiency"] = efficiency

        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"item_id": item_id, "error": str(e)}, status_code=404)


@app.get("/api/report")
async def get_report() -> JSONResponse:
    memory = AgentMemory.load(MEMORY_PATH)
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
        sellers = best_sellers(orders, limit=1)
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
async def get_ducats_batch(item_ids: list[str]) -> JSONResponse:
    """批量获取物品的杜卡特价值"""
    results = []
    for item_id in item_ids[:10]:  # 限制最多10个
        ducat_value = get_ducat_value(item_id)
        if ducat_value is not None:
            try:
                orders = await fetch_orders_async(item_id)
                sellers = best_sellers(orders, limit=1)
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

class TradeRequest(BaseModel):
    item_id: str
    item_name: str
    trade_type: str  # "buy" or "sell"
    price: int
    player_name: str = ""
    notes: str = ""


@app.get("/api/trades")
async def get_trades(limit: int = 20) -> JSONResponse:
    """获取最近的交易记录"""
    trades = trade_db.get_recent_trades(limit=limit)
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
    trade_id = trade_db.add_trade(
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
    success = trade_db.delete_trade(trade_id)
    if success:
        return JSONResponse({"status": "ok"})
    raise HTTPException(status_code=404, detail="交易记录不存在")


@app.get("/api/trades/stats")
async def get_trade_stats() -> JSONResponse:
    """获取交易统计信息"""
    stats = trade_db.get_trade_stats()
    return JSONResponse(stats)


@app.get("/api/trades/item/{item_id}")
async def get_trades_by_item(item_id: str, limit: int = 10) -> JSONResponse:
    """获取指定物品的交易记录"""
    trades = trade_db.get_trades_by_item(item_id, limit=limit)
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

@app.get("/api/arbitrage")
async def get_arbitrage_opportunities(min_profit: int = 3) -> JSONResponse:
    """检测套利机会（低买高卖）"""
    memory = AgentMemory.load(MEMORY_PATH)
    opportunities = []

    # 检查所有收藏物品的套利机会
    for item_id in memory.favorite_items:
        try:
            orders = await fetch_orders_async(item_id)
            sellers = best_sellers(orders, limit=3)
            buyers = best_buyers(orders, limit=3)

            if not sellers or not buyers:
                continue

            lowest_sell = sellers[0].platinum
            highest_buy = buyers[0].platinum

            # 计算潜在利润
            potential_profit = lowest_sell - highest_buy

            if potential_profit >= min_profit:
                # 计算杜卡特效率
                ducat_value = get_ducat_value(item_id)
                ducat_efficiency = None
                if ducat_value and lowest_sell:
                    ducat_efficiency = calculate_ducat_efficiency(lowest_sell, ducat_value)

                opportunities.append({
                    "item_id": item_id,
                    "display": display_item_name(item_id),
                    "buy_price": highest_buy,
                    "sell_price": lowest_sell,
                    "profit": potential_profit,
                    "profit_margin": round((potential_profit / highest_buy) * 100, 1) if highest_buy > 0 else 0,
                    "buyer": buyers[0].user_name,
                    "seller": sellers[0].user_name,
                    "ducat_value": ducat_value,
                    "ducat_efficiency": ducat_efficiency,
                })
        except Exception:
            continue

    # 按利润排序
    opportunities.sort(key=lambda x: x["profit"], reverse=True)

    return JSONResponse({
        "opportunities": opportunities,
        "total": len(opportunities),
        "min_profit_filter": min_profit,
    })


@app.get("/api/arbitrage/scan")
async def scan_arbitrage_from_watchlist() -> JSONResponse:
    """从 watchlist 扫描套利机会"""
    try:
        from pathlib import Path
        watchlist_path = config.DATA_DIR / "watchlist.json"
        if not watchlist_path.exists():
            return JSONResponse({"opportunities": [], "message": "watchlist 不存在"})

        with watchlist_path.open("r", encoding="utf-8") as f:
            watchlist = json.load(f)

        opportunities = []
        for item_id in list(watchlist.keys())[:20]:  # 限制扫描数量
            try:
                orders = await fetch_orders_async(item_id)
                sellers = best_sellers(orders, limit=1)
                buyers = best_buyers(orders, limit=1)

                if not sellers or not buyers:
                    continue

                lowest_sell = sellers[0].platinum
                highest_buy = buyers[0].platinum
                potential_profit = lowest_sell - highest_buy

                if potential_profit >= 2:  # watchlist 使用更低的阈值
                    opportunities.append({
                        "item_id": item_id,
                        "display": display_item_name(item_id),
                        "buy_price": highest_buy,
                        "sell_price": lowest_sell,
                        "profit": potential_profit,
                        "buyer": buyers[0].user_name,
                        "seller": sellers[0].user_name,
                    })
            except Exception:
                continue

        opportunities.sort(key=lambda x: x["profit"], reverse=True)
        return JSONResponse({"opportunities": opportunities})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/suggest")
async def suggest_items(q: str = "") -> JSONResponse:
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
async def compare_items(items: list[str]) -> JSONResponse:
    results = []
    for item_name in items[:3]:
        try:
            result = chat_agent.resolver.resolve(item_name)
            orders = await fetch_orders_async(result.item_id)
            sellers = best_sellers(orders, limit=1)
            buyers = best_buyers(orders, limit=1)

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
            results.append({"name": item_name, "error": str(e)})
    return JSONResponse({"items": results})


@app.post("/api/batch_query")
async def batch_query_items(items: list[str]) -> JSONResponse:
    """批量查询物品价格（支持更多物品）"""
    results = []
    for item_name in items[:10]:  # 最多支持10个物品
        try:
            result = chat_agent.resolver.resolve(item_name)
            orders = await fetch_orders_async(result.item_id)
            sellers = best_sellers(orders, limit=1)
            buyers = best_buyers(orders, limit=1)

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
            results.append({"name": item_name, "error": str(e)})

    return JSONResponse({
        "items": results,
        "total": len(results),
        "success": len([r for r in results if "error" not in r])
    })


@app.get("/api/aliases")
async def get_aliases() -> JSONResponse:
    aliases = load_custom_aliases()
    return JSONResponse({"aliases": [
        {"name": k, "item_id": v, "display": display_item_name(v)}
        for k, v in aliases.items()
    ]})


@app.post("/api/aliases")
async def add_alias(request: dict) -> JSONResponse:
    name = request.get("name", "").strip()
    item_id = request.get("item_id", "").strip()
    if not name or not item_id:
        return JSONResponse({"error": "名称和物品ID不能为空"}, status_code=400)
    aliases = load_custom_aliases()
    aliases[name] = item_id
    save_custom_aliases(aliases)
    inject_custom_aliases()
    return JSONResponse({"status": "ok", "name": name, "item_id": item_id})


@app.delete("/api/aliases")
async def remove_alias(request: dict) -> JSONResponse:
    name = request.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "名称不能为空"}, status_code=400)
    aliases = load_custom_aliases()
    if name in aliases:
        del aliases[name]
        save_custom_aliases(aliases)
        inject_custom_aliases()
    return JSONResponse({"status": "ok"})


@app.get("/api/search_items")
async def search_items(q: str = "") -> JSONResponse:
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
            reply = await asyncio.to_thread(chat_agent.answer, message)
            chunk_size = 3
            for i in range(0, len(reply), chunk_size):
                await websocket.send_json({"token": reply[i:i+chunk_size]})
                await asyncio.sleep(0.015)
            await websocket.send_json({"done": True, "reply": reply})
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
        ws_connections.remove(websocket)


async def broadcast_alert(notification: AlertNotification):
    message = {
        "type": "alert",
        "item": notification.item_display,
        "direction": notification.alert.direction,
        "price": notification.alert.price,
        "current_price": notification.current_price,
    }
    for ws in ws_connections:
        try:
            await ws.send_json(message)
        except Exception:
            pass


def setup_monitor():
    def on_alert_callback(notification: AlertNotification):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(broadcast_alert(notification), loop)
        except Exception:
            pass

    global monitor
    monitor = PriceMonitor(on_alert=on_alert_callback)
    monitor.start()


@app.on_event("startup")
async def startup_event():
    inject_custom_aliases()
    setup_monitor()


@app.on_event("shutdown")
async def shutdown_event():
    monitor.stop()


static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="root")
