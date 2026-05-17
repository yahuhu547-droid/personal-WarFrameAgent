"""游戏事件追踪 — 从 Warframe World State API 获取活动信息。"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from . import config

EVENT_CACHE_PATH = config.DATA_DIR / "game_events_cache.json"
EVENT_CACHE_TTL = config.EVENT_REFRESH_INTERVAL  # 30 分钟
CYCLE_CACHE_TTL = min(EVENT_CACHE_TTL, 60)


@dataclass(frozen=True)
class PrimeResurgenceItem:
    item_type: str
    item_name: str
    market_id: str
    prime_price: int = 0
    regular_price: int = 0


@dataclass(frozen=True)
class PrimeResurgenceRotation:
    featured_item: str = ""
    featured_names: list[str] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    next_featured_item: str = ""
    next_featured_names: list[str] = field(default_factory=list)
    next_start_time: str = ""
    next_end_time: str = ""
    items: list[PrimeResurgenceItem] = field(default_factory=list)


@dataclass(frozen=True)
class BaroItem:
    item_type: str          # raw ItemType path
    item_name: str          # 解析后的显示名
    market_id: str          # warframe.market url_name，如 "primed_continuity"
    ducat_cost: int         # PrimePrice（杜卡特）
    credit_cost: int        # Price（现金）


@dataclass(frozen=True)
class VoidFissure:
    node: str               # 如 "SolNode742"
    node_display: str       # 如 "虚空 - Mot"
    mission_type: str       # 如 "MT_EXTERMINATION"
    mission_display: str    # 如 "歼灭"
    tier: str               # 如 "VoidT4"
    tier_display: str       # 如 "后纪 (Axi)"
    hard: bool              # 钢铁模式
    activation: str
    expiry: str


@dataclass(frozen=True)
class WorldCycle:
    cycle: str
    cycle_display: str
    state: str
    state_display: str
    activation: str = ""
    expiry: str = ""
    time_left: str = ""


@dataclass(frozen=True)
class GameEvent:
    event_type: str         # "baro_visit" / "prime_vault" / "alert" / "void_storm" / "invasion"
    items_affected: list[str] = field(default_factory=list)
    start_time: str = ""
    end_time: str | None = None
    impact: str = "neutral"  # "positive" / "negative" / "neutral"
    description: str = ""
    baro_items: list[BaroItem] = field(default_factory=list)
    prime_resurgence: PrimeResurgenceRotation | None = None


# 物品关键词 → 事件影响映射
_BARO_KEYWORDS = {"primed", "baro"}
_VAULT_KEYWORDS = {"vault", "unvaulted", "prime_access"}

# 裂缝等级映射
_TIER_MAP = {
    "VoidT1": "古纪 (Lith)",
    "VoidT2": "前纪 (Meso)",
    "VoidT3": "中纪 (Neo)",
    "VoidT4": "后纪 (Axi)",
    "VoidT5": "遗珍 (Requiem)",
    "VoidT6": "仲裁 (Arbitration)",
}

_CYCLE_META = {
    "earth": ("地球", ("earthCycle", "EarthCycle"), "day"),
    "cetus": ("希图斯/夜灵平原", ("cetusCycle", "CetusCycle"), "day"),
    "vallis": ("奥布山谷/金星", ("vallisCycle", "VallisCycle"), "warm"),
    "cambion": ("魔胎之境", ("cambionCycle", "CambionCycle"), "fass"),
}

_CYCLE_STATE_DISPLAY = {
    "day": "白天",
    "night": "黑夜",
    "warm": "温暖",
    "cold": "寒冷",
    "fass": "Fass",
    "vome": "Vome",
}

_CYCLE_STATE_ALIASES = {
    "day": "day",
    "night": "night",
    "warm": "warm",
    "cold": "cold",
    "fass": "fass",
    "vome": "vome",
    "白天": "day",
    "白昼": "day",
    "黑夜": "night",
    "夜晚": "night",
    "晚上": "night",
    "温暖": "warm",
    "暖": "warm",
    "热": "warm",
    "寒冷": "cold",
    "冷": "cold",
    "法斯": "fass",
    "沃姆": "vome",
}

# 任务类型映射
_MISSION_TYPE_MAP = {
    "MT_EXTERMINATION": "歼灭",
    "MT_CAPTURE": "捕获",
    "MT_DEFENSE": "防御",
    "MT_SURVIVAL": "生存",
    "MT_RESCUE": "救援",
    "MT_SABOTAGE": "破坏",
    "MT_MOBILE_DEFENSE": "移动防御",
    "MT_INTEL": "间谍",
    "MT_TERRITORY": "拦截",
    "MT_ARTIFACT": "挖掘",
    "MT_ALCHEMY": "炼金",
    "MT_DISRUPTION": "中断",
    "MT_SPY": "间谍",
    "MT_ASSASSINATION": "刺杀",
}

_LIMITED_EVENT_NAMES = {
    "jadeshadowsevent": "兽之腹",
    "jadeshadows": "兽之腹",
    "thermiafractures": "热美亚裂缝",
    "thermiafracture": "热美亚裂缝",
    "friendlyfiretacalert": "利刃豺狼舰队",
    "corpusrazorbackproject": "利刃豺狼舰队",
    "razorback": "利刃豺狼舰队",
    "fomorian": "巨人战舰",
    "ghoul": "尸鬼净化",
}


# 入侵描述映射
_INVASION_MAP = {
    "/Lotus/Language/Menu/CorpusInvasionGeneric": "Corpus 入侵",
    "/Lotus/Language/Menu/GrineerInvasionGeneric": "Grineer 入侵",
    "/Lotus/Language/Menu/InfestedInvasionBoss": "Infested 入侵",
}

# 节点名映射（常用节点）
_NODE_NAMES = {
    "SolNode1": "地球 - E Prime",
    "SolNode2": "地球 - Everest",
    "SolNode3": "地球 - Lith",
    "SolNode22": "水星 - Elion",
    "SolNode27": "金星 - Malva",
    "SolNode36": "火星 - Alator",
    "SolNode57": "火卫一 - Zeugma",
    "SolNode126": "木星 - Carme",
    "SolNode309": "塞德娜 - Hydron",
    "SolNode310": "塞德娜 - Berehynia",
    "SolNode742": "虚空 - Mot",
    "SolNode745": "虚空 - Ani",
    "SolNode747": "虚空 - Taranis",
}


def _node_name(node_id: str) -> str:
    """将节点 ID 转为可读名称。"""
    return _NODE_NAMES.get(node_id, node_id)


# Baro ItemType → market url_name 映射缓存
_ITEM_TYPE_MAP: dict[str, str] | None = None


def _item_type_to_market_id(item_type: str) -> str:
    """将 Baro ItemType 路径映射到 warframe.market url_name。"""
    global _ITEM_TYPE_MAP
    if _ITEM_TYPE_MAP is None:
        _ITEM_TYPE_MAP = _build_item_type_map()
    return _ITEM_TYPE_MAP.get(item_type, "")


def _item_type_leaf(item_type: str) -> str:
    return item_type.split("/")[-1].replace(" ", "_")


def _readable_prime_name(raw: str) -> str:
    leaf = _item_type_leaf(raw)
    leaf = leaf.removeprefix("MPV")
    leaf = leaf.removesuffix("SinglePack")
    leaf = leaf.removesuffix("DualPack")
    leaf = leaf.removesuffix("PrimeSet")
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", leaf).split()
    return " ".join(words) if words else leaf


def _format_worldstate_time(raw) -> str:
    ts = _parse_timestamp(raw)
    if not ts:
        return str(raw or "")
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _parse_resurgence_item(raw: dict) -> PrimeResurgenceItem | None:
    item_type = raw.get("ItemType") or raw.get("item") or ""
    if not item_type:
        return None
    return PrimeResurgenceItem(
        item_type=item_type,
        item_name=_readable_prime_name(item_type),
        market_id=_item_type_to_market_id(item_type),
        prime_price=int(raw.get("PrimePrice") or 0),
        regular_price=int(raw.get("RegularPrice") or 0),
    )


def _prime_featured_names(featured_item: str) -> list[str]:
    leaf = _item_type_leaf(featured_item).removeprefix("MPV")
    leaf = leaf.removesuffix("DualPack").removesuffix("SinglePack")
    names = [name for name in re.findall(r"[A-Z][a-z]+(?=Prime|[A-Z]|$)", leaf) if name != "Prime"]
    return [f"{name} Prime" for name in names]


def _load_prime_resurgence(data: dict | None) -> PrimeResurgenceRotation | None:
    if not data:
        return None
    return PrimeResurgenceRotation(
        featured_item=data.get("featured_item", ""),
        featured_names=data.get("featured_names", []),
        start_time=data.get("start_time", ""),
        end_time=data.get("end_time", ""),
        next_featured_item=data.get("next_featured_item", ""),
        next_featured_names=data.get("next_featured_names", []),
        next_start_time=data.get("next_start_time", ""),
        next_end_time=data.get("next_end_time", ""),
        items=[PrimeResurgenceItem(**item) for item in data.get("items", [])],
    )


def _build_item_type_map() -> dict[str, str]:
    """构建 ItemType → market_id 映射表。"""
    import json as _json
    from pathlib import Path as _Path
    mapping: dict[str, str] = {}
    # 从 items_full.json 构建 name_lower → item_id
    items_path = config.DATA_DIR / "items_full.json"
    if not items_path.exists():
        return mapping
    try:
        items = _json.loads(items_path.read_text(encoding="utf-8-sig"))
        name_to_id: dict[str, str] = {}
        for item in items:
            en_name = (item.get("en_name") or item.get("en", "")).lower()
            item_id = item.get("item_id") or item.get("id", "")
            if en_name and item_id:
                name_to_id[en_name] = item_id
            # 也用 search_terms
            for term in item.get("search_terms", []):
                if term.lower() not in name_to_id:
                    name_to_id[term.lower()] = item_id
    except Exception:
        name_to_id = {}
    # 从 ExportUpgrades 构建 uniqueName → en_name
    for export_file in config.DATA_DIR.glob("Export*.json"):
        try:
            data = _json.loads(export_file.read_text(encoding="utf-8-sig"))
            items_list = data if isinstance(data, list) else data.get("ExportUpgrades", data.get("ExportWeapons", data.get("ExportRelicArcane", data.get("ExportSentinels", data.get("ExportGear", data.get("ExportCustoms", []))))))
            if isinstance(items_list, list):
                for entry in items_list:
                    unique = entry.get("uniqueName", "")
                    name = entry.get("name", "")
                    if unique and name:
                        market_id = name_to_id.get(name.lower(), "")
                        if market_id:
                            mapping[unique] = market_id
        except Exception:
            continue
    return mapping


def _parse_timestamp(raw) -> float:
    """解析时间戳，兼容普通数字和 MongoDB {$date: {$numberLong: ...}} 格式。"""
    if isinstance(raw, dict):
        date = raw.get("$date", raw)
        if isinstance(date, dict):
            val = date.get("$numberLong", date.get("$numberDouble", 0))
            return float(val) / 1000.0  # 毫秒转秒
        return float(date)
    try:
        val = float(raw)
        return val / 1000.0 if val > 1e12 else val
    except (ValueError, TypeError):
        return 0.0


def cycle_timestamp(raw) -> float:
    return _parse_timestamp(raw)


def _normalize_cycle_state(cycle: str, raw: dict[str, Any], boolean_key: str, true_state: str, false_state: str) -> str:
    state = raw.get("state") or raw.get("State")
    if isinstance(state, str):
        normalized = _CYCLE_STATE_ALIASES.get(state.strip().lower()) or _CYCLE_STATE_ALIASES.get(state.strip())
        if normalized:
            return normalized
    value = raw.get(boolean_key)
    if value is None:
        value = raw.get(boolean_key[0].upper() + boolean_key[1:])
    if isinstance(value, bool):
        return true_state if value else false_state
    if cycle == "cambion" and isinstance(state, str):
        lowered = state.strip().lower()
        if "fass" in lowered:
            return "fass"
        if "vome" in lowered:
            return "vome"
    return ""


def _limited_event_name(*values: object) -> str:
    text = " ".join(str(value or "") for value in values).lower()
    compact = re.sub(r"[^a-z0-9]+", "", text)
    for key, name in _LIMITED_EVENT_NAMES.items():
        if key in compact:
            return name
    return ""


def _limited_event_description(name: str, raw: dict[str, Any]) -> str:
    node = _node_name(str(raw.get("Node") or raw.get("VictimNode") or ""))
    end = _format_worldstate_time(raw.get("Expiry"))
    parts = [name]
    if node:
        parts.append(f"节点: {node}")
    if end:
        parts.append(f"结束: {end}")
    health = raw.get("HealthPct")
    if isinstance(health, (int, float)):
        parts.append(f"进度: {health * 100:.0f}%")
    return " | ".join(parts)


def _classify_event(raw: dict) -> GameEvent | None:
    """从原始 API 数据解析事件。"""
    event_type = raw.get("type", "unknown")
    desc = raw.get("description", raw.get("tooltip", ""))
    start = raw.get("activation", raw.get("start", ""))
    end = raw.get("expiry", raw.get("end", None))

    if event_type == "baro_visit":
        return GameEvent(
            event_type="baro_visit",
            start_time=start,
            end_time=end,
            impact="positive",
            description=f"Baro Ki'Teer 来访: {desc}" if desc else "Baro Ki'Teer 来访",
        )

    if event_type in ("void_storm", "storm"):
        return GameEvent(
            event_type="void_storm",
            start_time=start,
            end_time=end,
            impact="neutral",
            description=f"虚空风暴: {desc}" if desc else "虚空风暴活动",
        )

    if event_type in ("invasion",):
        return GameEvent(
            event_type="invasion",
            start_time=start,
            end_time=end,
            impact="neutral",
            description=f"入侵: {desc}" if desc else "入侵事件",
        )

    if event_type in ("alert", "event"):
        return GameEvent(
            event_type="alert",
            start_time=start,
            end_time=end,
            impact="positive",
            description=desc or "警报/活动",
        )

    # 未知类型，尝试从描述推断
    if any(kw in desc.lower() for kw in _BARO_KEYWORDS):
        return GameEvent(
            event_type="baro_visit",
            start_time=start,
            end_time=end,
            impact="positive",
            description=desc,
        )

    return None


class EventTracker:
    """游戏事件追踪器，带缓存和容错。"""

    def __init__(self):
        self._events: list[GameEvent] = []
        self._world_state: dict[str, Any] | None = None
        self._last_fetch: float = 0
        self._cycle_cache: dict[str, WorldCycle] = {}
        self._cycle_last_fetch: float = 0
        self._fetcher = self._default_fetcher
        self._cycle_fetcher = self._default_cycle_fetcher

    def _default_fetcher(self) -> dict[str, Any]:
        """从 Warframe 官方 API 获取世界状态。"""
        import re
        import urllib.request
        url = "https://content.warframe.com/dynamic/worldState.php"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
        # 官方 JSON 有尾随逗号，需修复
        fixed = re.sub(r",\s*}", "}", raw)
        fixed = re.sub(r",\s*]", "]", fixed)
        return json.loads(fixed)

    def _default_cycle_fetcher(self, cycle: str) -> dict[str, Any]:
        import urllib.request
        url = f"https://api.warframestat.us/pc/{cycle}Cycle"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "warframe-agent"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def set_fetcher(self, fetcher) -> None:
        self._fetcher = fetcher

    def set_cycle_fetcher(self, fetcher) -> None:
        self._cycle_fetcher = fetcher

    def fetch_world_state(self) -> dict[str, Any] | None:
        """获取世界状态，带容错。"""
        try:
            return self._fetcher()
        except Exception:
            return None

    def parse_events(self, world_state: dict[str, Any]) -> list[GameEvent]:
        """从世界状态解析事件列表（兼容官方 API 和 warframestat.us 两种格式）。"""
        events: list[GameEvent] = []

        # Baro 虚空商人（兼容官方 VoidTraders 数组 + 第三方 voidTrader 格式）
        void_traders_raw = world_state.get("VoidTraders") or world_state.get("VoidTrader") or world_state.get("voidTrader")
        if isinstance(void_traders_raw, list):
            void_trader = void_traders_raw[0] if void_traders_raw else {}
        else:
            void_trader = void_traders_raw or {}
        # 判断 Baro 是否活跃：检查 Active 字段或时间范围
        is_active = void_trader.get("Active") or void_trader.get("active")
        if not is_active and void_trader:
            import time as _time
            try:
                activation = _parse_timestamp(void_trader.get("Activation", void_trader.get("activation", 0)))
                expiry = _parse_timestamp(void_trader.get("Expiry", void_trader.get("expiry", 0)))
                now_ts = _time.time()
                is_active = activation < now_ts < expiry
            except (ValueError, TypeError):
                pass
        if void_trader and is_active:
            manifest = void_trader.get("Manifest") or void_trader.get("inventory", [])
            items = []
            baro_items = []
            for item in manifest:
                raw_type = item.get("ItemType") or item.get("item", "")
                if raw_type:
                    parsed_name = raw_type.split("/")[-1].replace(" ", "_")
                    market_id = _item_type_to_market_id(raw_type)
                    ducat_cost = item.get("PrimePrice", item.get("primePrice", 0))
                    credit_cost = item.get("Price", item.get("price", 0))
                    items.append(parsed_name.lower())
                    baro_items.append(BaroItem(
                        item_type=raw_type,
                        item_name=parsed_name,
                        market_id=market_id,
                        ducat_cost=int(ducat_cost) if ducat_cost else 0,
                        credit_cost=int(credit_cost) if credit_cost else 0,
                    ))
            node = void_trader.get("Node") or void_trader.get("location", "")
            events.append(GameEvent(
                event_type="baro_visit",
                items_affected=items,
                start_time=str(void_trader.get("Activation") or void_trader.get("activation", "")),
                end_time=str(void_trader.get("Expiry") or void_trader.get("expiry", "")),
                impact="positive",
                description=f"Baro Ki'Teer 来访 @ {node}，库存 {len(items)} 件物品",
                baro_items=baro_items,
            ))

        # 虚空裂缝（官方 API：Modifier 字段以 VoidT 开头标识裂缝等级）
        for mission in world_state.get("ActiveMissions", []):
            modifier = mission.get("Modifier", "")
            if modifier.startswith("Void"):
                tier = _TIER_MAP.get(modifier, modifier)
                node = _node_name(mission.get("Node", ""))
                hard = mission.get("Hard", False)
                mode = "钢铁" if hard else "普通"
                mt = _MISSION_TYPE_MAP.get(mission.get("MissionType", ""), mission.get("MissionType", ""))
                events.append(GameEvent(
                    event_type="void_fissure",
                    start_time=str(mission.get("Activation", "")),
                    end_time=str(mission.get("Expiry", "")),
                    impact="neutral",
                    description=f"虚空裂缝: {tier} {mt} {mode} @ {node}",
                ))

        # 虚空风暴
        for storm in world_state.get("VoidStorms", world_state.get("voidStorms", [])):
            node = _node_name(storm.get("Node", ""))
            events.append(GameEvent(
                event_type="void_storm",
                start_time=str(storm.get("Activation", "")),
                end_time=str(storm.get("Expiry", "")),
                impact="neutral",
                description=f"虚空风暴 @ {node}",
            ))

        # 警报
        for alert in world_state.get("alerts", []):
            active = alert.get("active") or alert.get("Active", False)
            if active:
                desc = ""
                mission = alert.get("mission", {})
                if isinstance(mission, dict):
                    desc = mission.get("description", "")
                events.append(GameEvent(
                    event_type="alert",
                    start_time=str(alert.get("activation", "")),
                    end_time=str(alert.get("expiry", "")),
                    impact="positive",
                    description=f"警报: {desc}" if desc else "活跃警报",
                ))

        # 入侵
        for invasion in world_state.get("Invasions", world_state.get("invasions", [])):
            completed = invasion.get("Completed") or invasion.get("completed", False)
            if not completed:
                desc = invasion.get("LocTag") or invasion.get("desc", "")
                events.append(GameEvent(
                    event_type="invasion",
                    start_time=str(invasion.get("Activation") or invasion.get("activation", "")),
                    impact="neutral",
                    description=_INVASION_MAP.get(desc, f"入侵: {desc}"),
                ))

        # Prime Resurgence（PrimeVaultTraders 商店轮换）
        for trader in world_state.get("PrimeVaultTraders", []):
            if not isinstance(trader, dict):
                continue
            manifest = trader.get("Manifest") or []
            items = [item for item in (_parse_resurgence_item(raw) for raw in manifest if isinstance(raw, dict)) if item]
            schedule = trader.get("ScheduleInfo") or []
            now_ts = time.time()
            starts = [_parse_timestamp(trader.get("Activation"))]
            starts.extend(_parse_timestamp(entry.get("Expiry")) for entry in schedule if isinstance(entry, dict))
            starts = sorted(ts for ts in starts if ts)
            current_start_ts = _parse_timestamp(trader.get("Activation"))
            featured_item = ""
            featured_names: list[str] = []
            end_raw = trader.get("Expiry")
            next_featured_item = ""
            next_featured_names: list[str] = []
            next_start_raw = ""
            next_end_raw = ""
            previous_expiry_raw = trader.get("Activation")
            found_current = False
            for entry in schedule:
                if not isinstance(entry, dict):
                    continue
                expiry_raw = entry.get("Expiry")
                expiry_ts = _parse_timestamp(expiry_raw)
                if not expiry_ts:
                    continue
                if not found_current and expiry_ts >= now_ts:
                    end_raw = expiry_raw
                    featured_item = entry.get("FeaturedItem", "")
                    featured_names = _prime_featured_names(featured_item)
                    current_start_ts = _parse_timestamp(previous_expiry_raw)
                    found_current = True
                elif found_current:
                    next_start_raw = previous_expiry_raw
                    next_end_raw = expiry_raw
                    next_featured_item = entry.get("FeaturedItem", "")
                    next_featured_names = _prime_featured_names(next_featured_item)
                    break
                previous_expiry_raw = expiry_raw
            rotation = PrimeResurgenceRotation(
                featured_item=featured_item,
                featured_names=featured_names,
                start_time=_format_worldstate_time(current_start_ts),
                end_time=_format_worldstate_time(end_raw),
                next_featured_item=next_featured_item,
                next_featured_names=next_featured_names,
                next_start_time=_format_worldstate_time(next_start_raw),
                next_end_time=_format_worldstate_time(next_end_raw),
                items=items,
            )
            affected = [item.market_id or item.item_name.lower().replace(" ", "_") for item in items]
            label = " + ".join(featured_names) if featured_names else "当前轮换"
            events.append(GameEvent(
                event_type="prime_resurgence",
                items_affected=affected,
                start_time=rotation.start_time,
                end_time=rotation.end_time,
                impact="positive",
                description=f"Prime 重生: {label}",
                prime_resurgence=rotation,
            ))

        # Prime Vault（PrimeVaultAvailabilities 数组）
        for vault in world_state.get("PrimeVaultAvailabilities", []):
            if not isinstance(vault, dict):
                continue
            start = vault.get("StartDate", vault.get("Activation", ""))
            end = vault.get("EndDate", vault.get("Expiry", None))
            # 提取 Vault 中的物品名
            vault_items = []
            for pkg in vault.get("StoreItems", vault.get("Items", [])):
                if isinstance(pkg, str):
                    vault_items.append(pkg.split("/")[-1].lower())
                elif isinstance(pkg, dict):
                    vault_items.append(pkg.get("Name", pkg.get("ItemType", "")).split("/")[-1].lower())
            item_text = ", ".join(vault_items[:3]) if vault_items else "未知物品"
            events.append(GameEvent(
                event_type="prime_vault",
                items_affected=vault_items,
                start_time=str(start),
                end_time=str(end),
                impact="positive",
                description=f"Prime Vault 回归: {item_text}",
            ))

        # Prime Access（从 WorldStatePackages 或 PersistentEnemies 推断）
        for pkg in world_state.get("WorldStatePackages", []):
            pkg_type = pkg.get("type", "")
            if "primeaccess" in pkg_type.lower() or "prime_access" in pkg_type.lower():
                start = pkg.get("date", pkg.get("Activation", ""))
                events.append(GameEvent(
                    event_type="prime_access",
                    start_time=str(start),
                    impact="neutral",
                    description="Prime Access 上线 — 新 Prime 物品价格波动期",
                ))

        return events

    def refresh(self, force: bool = False) -> list[GameEvent]:
        """刷新事件缓存。"""
        now = time.time()
        if not force and now - self._last_fetch < EVENT_CACHE_TTL and self._events:
            return self._events

        world_state = self.fetch_world_state()
        if world_state is None:
            return self._events  # 失败时返回旧缓存

        self._world_state = world_state
        self._events = self.parse_events(world_state)
        self._last_fetch = now

        # 持久化缓存
        self._save_cache()
        return self._events

    def parse_limited_events(self, world_state: dict[str, Any] | None = None) -> list[GameEvent]:
        """解析运营限时活动，不包含裂缝、虚空风暴、入侵合集。"""
        ws = world_state if world_state is not None else self._world_state
        if not ws:
            return []
        events: list[GameEvent] = []
        seen: set[str] = set()

        for goal in ws.get("Goals", []):
            if not isinstance(goal, dict):
                continue
            name = _limited_event_name(goal.get("Tag"), goal.get("Desc"), goal.get("ToolTip"))
            if not name or name in seen:
                continue
            seen.add(name)
            events.append(GameEvent(
                event_type="limited_event",
                start_time=_format_worldstate_time(goal.get("Activation")),
                end_time=_format_worldstate_time(goal.get("Expiry")),
                impact="positive",
                description=_limited_event_description(name, goal),
            ))

        alert_names: set[str] = set()
        for alert in ws.get("Alerts", []) + ws.get("alerts", []):
            if not isinstance(alert, dict):
                continue
            mission = alert.get("MissionInfo") or alert.get("mission") or {}
            name = _limited_event_name(alert.get("Tag"), mission.get("descText"), mission.get("description"))
            if name and name not in seen:
                alert_names.add(name)
        for name in sorted(alert_names):
            seen.add(name)
            events.append(GameEvent(
                event_type="limited_event",
                impact="positive",
                description=name,
            ))

        resurgence = next((event for event in self.parse_events(ws) if event.event_type == "prime_resurgence"), None)
        if resurgence:
            events.append(resurgence)

        return events

    def get_limited_events(self) -> list[GameEvent]:
        """获取当前运营限时活动。"""
        now = time.time()
        if now - self._last_fetch >= EVENT_CACHE_TTL:
            self.refresh()
        return self.parse_limited_events()

    def parse_fissures(self, world_state: dict[str, Any] | None = None) -> list[VoidFissure]:
        """从世界状态解析结构化裂缝数据。"""
        ws = world_state if world_state is not None else self._world_state
        if not ws:
            return []
        fissures: list[VoidFissure] = []
        for mission in ws.get("ActiveMissions", []):
            modifier = mission.get("Modifier", "")
            if modifier.startswith("Void"):
                fissures.append(VoidFissure(
                    node=mission.get("Node", ""),
                    node_display=_node_name(mission.get("Node", "")),
                    mission_type=mission.get("MissionType", ""),
                    mission_display=_MISSION_TYPE_MAP.get(mission.get("MissionType", ""), mission.get("MissionType", "")),
                    tier=modifier,
                    tier_display=_TIER_MAP.get(modifier, modifier),
                    hard=mission.get("Hard", False),
                    activation=str(mission.get("Activation", "")),
                    expiry=str(mission.get("Expiry", "")),
                ))
        return fissures

    def get_active_fissures(self) -> list[VoidFissure]:
        """获取活跃裂缝（优先用缓存）。"""
        now = time.time()
        if now - self._last_fetch >= EVENT_CACHE_TTL:
            self.refresh()
        return self.parse_fissures()

    def parse_cycles(self, world_state: dict[str, Any] | None = None) -> list[WorldCycle]:
        ws = world_state if world_state is not None else self._world_state
        if not ws:
            return []
        cycles: list[WorldCycle] = []
        for cycle, (display, keys, default_true_state) in _CYCLE_META.items():
            raw = next((ws.get(key) for key in keys if isinstance(ws.get(key), dict)), None)
            if not raw:
                continue
            if cycle in ("earth", "cetus"):
                state = _normalize_cycle_state(cycle, raw, "isDay", "day", "night")
            elif cycle == "vallis":
                state = _normalize_cycle_state(cycle, raw, "isWarm", "warm", "cold")
            else:
                state = _normalize_cycle_state(cycle, raw, "isFass", "fass", "vome")
            if not state:
                state = default_true_state
            cycles.append(WorldCycle(
                cycle=cycle,
                cycle_display=display,
                state=state,
                state_display=_CYCLE_STATE_DISPLAY.get(state, state),
                activation=str(raw.get("activation") or raw.get("Activation") or ""),
                expiry=str(raw.get("expiry") or raw.get("Expiry") or ""),
                time_left=str(raw.get("timeLeft") or raw.get("TimeLeft") or ""),
            ))
        return cycles

    def _fetch_external_cycles(self) -> list[WorldCycle]:
        cycles: list[WorldCycle] = []
        for cycle, (display, _, _) in _CYCLE_META.items():
            try:
                raw = self._cycle_fetcher(cycle)
            except Exception:
                continue
            if not isinstance(raw, dict) or not raw:
                continue
            parsed = self.parse_cycles({f"{cycle}Cycle": raw})
            if parsed:
                cycles.extend(parsed)
                continue
            state = _normalize_cycle_state(cycle, raw, "isDay" if cycle in ("earth", "cetus") else "isWarm", "day" if cycle in ("earth", "cetus") else "warm", "night" if cycle in ("earth", "cetus") else "cold")
            if cycle == "cambion":
                state = _normalize_cycle_state(cycle, raw, "isFass", "fass", "vome")
            if not state:
                continue
            cycles.append(WorldCycle(
                cycle=cycle,
                cycle_display=display,
                state=state,
                state_display=_CYCLE_STATE_DISPLAY.get(state, state),
                activation=str(raw.get("activation") or raw.get("Activation") or ""),
                expiry=str(raw.get("expiry") or raw.get("Expiry") or ""),
                time_left=str(raw.get("timeLeft") or raw.get("TimeLeft") or ""),
            ))
        return cycles

    def get_cycles(self) -> list[WorldCycle]:
        now = time.time()
        if self._cycle_cache and now - self._cycle_last_fetch < CYCLE_CACHE_TTL:
            return list(self._cycle_cache.values())
        if not self._world_state or now - self._last_fetch >= CYCLE_CACHE_TTL:
            self.refresh(force=True)
        cycles = self.parse_cycles()
        if not cycles:
            cycles = self._fetch_external_cycles()
        if cycles:
            self._cycle_cache = {cycle.cycle: cycle for cycle in cycles}
            self._cycle_last_fetch = now
        return cycles

    def get_cycle(self, cycle: str) -> WorldCycle | None:
        for world_cycle in self.get_cycles():
            if world_cycle.cycle == cycle:
                return world_cycle
        return None

    def get_active_events(self) -> list[GameEvent]:
        """获取活跃事件（优先用缓存）。"""
        now = time.time()
        if now - self._last_fetch >= EVENT_CACHE_TTL:
            return self.refresh()
        return self._events

    def get_vault_status(self) -> list[GameEvent]:
        """获取当前 Vault 回归事件列表。"""
        events = self.get_active_events()
        return [e for e in events if e.event_type == "prime_vault"]

    def get_prime_resurgence(self) -> GameEvent | None:
        """获取当前 Prime 重生轮换。"""
        events = self.get_active_events()
        for event in events:
            if event.event_type == "prime_resurgence":
                return event
        return None

    def get_vaulted_item_ids(self) -> set[str]:
        """获取当前 Vault 回归中的物品 ID 集合（用于过滤投资分析）。"""
        vault_events = self.get_vault_status()
        result = set()
        for e in vault_events:
            result.update(e.items_affected)
        return result

    def get_event_impact(self, item_id: str) -> str | None:
        """检查物品是否受事件影响，返回事件描述。"""
        lower = item_id.lower()
        for event in self._events:
            # Baro 物品
            if event.event_type == "baro_visit":
                if any(kw in lower for kw in _BARO_KEYWORDS):
                    return event.description
                for affected in event.items_affected:
                    if affected in lower or lower in affected:
                        return event.description

            # Prime Vault / Prime Resurgence
            if event.event_type in ("prime_vault", "prime_access", "prime_resurgence"):
                if "prime" in lower:
                    return event.description

        return None

    def _save_cache(self) -> None:
        """持久化事件缓存。"""
        try:
            data = {
                "last_fetch": self._last_fetch,
                "events": [
                    {
                        "event_type": e.event_type,
                        "items_affected": e.items_affected,
                        "start_time": e.start_time,
                        "end_time": e.end_time,
                        "impact": e.impact,
                        "description": e.description,
                        "baro_items": [
                            {
                                "item_type": bi.item_type,
                                "item_name": bi.item_name,
                                "market_id": bi.market_id,
                                "ducat_cost": bi.ducat_cost,
                                "credit_cost": bi.credit_cost,
                            }
                            for bi in e.baro_items
                        ] if e.baro_items else [],
                        "prime_resurgence": {
                            "featured_item": e.prime_resurgence.featured_item,
                            "featured_names": e.prime_resurgence.featured_names,
                            "start_time": e.prime_resurgence.start_time,
                            "end_time": e.prime_resurgence.end_time,
                            "next_featured_item": e.prime_resurgence.next_featured_item,
                            "next_featured_names": e.prime_resurgence.next_featured_names,
                            "next_start_time": e.prime_resurgence.next_start_time,
                            "next_end_time": e.prime_resurgence.next_end_time,
                            "items": [
                                {
                                    "item_type": item.item_type,
                                    "item_name": item.item_name,
                                    "market_id": item.market_id,
                                    "prime_price": item.prime_price,
                                    "regular_price": item.regular_price,
                                }
                                for item in e.prime_resurgence.items
                            ],
                        } if e.prime_resurgence else None,
                    }
                    for e in self._events
                ],
            }
            EVENT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            EVENT_CACHE_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def load_cache(self) -> None:
        """从磁盘加载缓存。"""
        try:
            if not EVENT_CACHE_PATH.exists():
                return
            with EVENT_CACHE_PATH.open("r", encoding="utf-8-sig") as f:
                data = json.load(f)
            self._last_fetch = data.get("last_fetch", 0)
            self._events = [
                GameEvent(
                    event_type=e["event_type"],
                    items_affected=e.get("items_affected", []),
                    start_time=e.get("start_time", ""),
                    end_time=e.get("end_time"),
                    impact=e.get("impact", "neutral"),
                    description=e.get("description", ""),
                    baro_items=[
                        BaroItem(**bi) for bi in e.get("baro_items", [])
                    ] if e.get("baro_items") else [],
                    prime_resurgence=_load_prime_resurgence(e.get("prime_resurgence")),
                )
                for e in data.get("events", [])
            ]
        except (json.JSONDecodeError, KeyError):
            pass
