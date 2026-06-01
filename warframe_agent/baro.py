"""Baro Ki'Teer inventory analysis for ranked Mods and Arcanes."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .events import BaroItem, GameEvent
from .market import MarketOrder, best_buyers, best_sellers, fetch_orders, get_max_rank_from_orders
from .names import display_item_name, english_name, preferred_chinese_name


ItemInfoLookup = Callable[[str], Optional[dict]]


@dataclass(frozen=True)
class BaroRecommendation:
    item_name: str
    market_id: str
    ducat_cost: int
    credit_cost: int
    rank: Optional[int]
    max_rank: int
    item_kind: str
    best_buy_price: int | None
    best_sell_price: int | None
    buyers: list[MarketOrder] = field(default_factory=list)
    sellers: list[MarketOrder] = field(default_factory=list)

    @property
    def market_plat_price(self) -> int | None:
        """Backward-compatible alias for the lowest sell price."""
        return self.best_sell_price

    @property
    def recommendation(self) -> str:
        """Backward-compatible category for callers that group recommendations."""
        return "consider"

    @property
    def reason(self) -> str:
        return "Baro 兑换成本和 warframe.market 当前订单"


def parse_baro_rank_request(message: str) -> int | str:
    text = message.strip().lower()
    if any(word in text for word in ("满级", "满阶", "max", "最高级", "拉满")):
        return "max"
    match = re.search(r"(?:r|rank|等级|级)\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*(?:级|阶)", text)
    if match:
        return int(match.group(1))
    return "unspecified"


def analyze_baro_inventory(
    baro_event: GameEvent,
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    rank_request: int | str = "unspecified",
    item_info_lookup: ItemInfoLookup | None = None,
    order_limit: int = 5,
) -> list[BaroRecommendation]:
    """Return Baro Mod/Arcane market snapshots at the requested rank."""
    recommendations: list[BaroRecommendation] = []

    for item in baro_event.baro_items:
        market_id = item.market_id or _baro_market_id_from_item_type(item.item_type)
        if not market_id:
            continue
        info = _item_info(market_id, item.item_name, item.item_type, item_info_lookup)
        if info is None:
            continue

        try:
            orders = order_fetcher(market_id)
        except Exception:
            orders = []

        max_rank = _max_rank(market_id, info, orders)
        rank = _resolve_rank(rank_request, max_rank)
        if rank is None:
            rank = max_rank
        sellers = best_sellers(orders, limit=order_limit, rank_filter=rank)
        buyers = best_buyers(orders, limit=order_limit, rank_filter=rank)
        recommendations.append(
            BaroRecommendation(
                item_name=item.item_name,
                market_id=market_id,
                ducat_cost=item.ducat_cost,
                credit_cost=item.credit_cost,
                rank=rank,
                max_rank=max_rank,
                item_kind=str(info.get("type", "mod")),
                best_buy_price=buyers[0].platinum if buyers else None,
                best_sell_price=sellers[0].platinum if sellers else None,
                buyers=buyers,
                sellers=sellers,
            )
        )

    recommendations.sort(
        key=lambda r: (
            r.best_buy_price is None,
            -(r.best_buy_price or 0),
            r.best_sell_price is None,
            r.best_sell_price or 999999,
        )
    )
    return recommendations


def format_baro_inventory(
    items: list[BaroItem],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    order_limit: int = 5,
) -> str:
    recommendations = _inventory_recommendations(items, order_fetcher=order_fetcher, order_limit=order_limit)
    return format_baro_report(recommendations)


def format_baro_report(recommendations: list[BaroRecommendation]) -> str:
    if not recommendations:
        return "Baro 库存中没有可分析的 Mod 或赋能。"

    lines = [
        "## Baro Mod / 赋能价格",
        "仅展示可分析的 Mod / 赋能；装饰、外观等非交易项暂不做价格分析。",
    ]
    for r in recommendations:
        lines.append(
            f"- {_summary_name(r.market_id)}{_rank_suffix(r)} | "
            f"杜卡德金币: {r.ducat_cost} | "
            f"最高买价: {_price(r.best_buy_price)} | "
            f"最低卖价: {_price(r.best_sell_price)}"
        )
    return "\n".join(lines)


def format_baro_order_details(
    recommendation: BaroRecommendation,
    seller_limit: int = 1,
    buyer_limit: int = 1,
) -> str:
    if recommendation.rank is None:
        return f"{_summary_name(recommendation.market_id)} 请先说明等级，例如 R0、R{recommendation.max_rank} 或满级。"

    lines = [f"## {_summary_name(recommendation.market_id)} R{recommendation.rank} 玩家订单"]
    if buyer_limit > 0:
        lines.append("买家:")
        if recommendation.buyers[:buyer_limit]:
            for index, order in enumerate(recommendation.buyers[:buyer_limit], 1):
                lines.append(_format_order_line("买家", index, order, recommendation, "buy"))
        else:
            lines.append("- 暂无游戏内买家")

    if seller_limit > 0:
        lines.append("卖家:")
        if recommendation.sellers[:seller_limit]:
            for index, order in enumerate(recommendation.sellers[:seller_limit], 1):
                lines.append(_format_order_line("卖家", index, order, recommendation, "sell"))
        else:
            lines.append("- 暂无游戏内卖家")
    return "\n".join(lines)


def format_baro_order_details_for_model(
    recommendation: BaroRecommendation,
    seller_limit: int = 1,
    buyer_limit: int = 1,
) -> str:
    """Return compact Baro follow-up context without player-identifying order data."""
    parts = [
        "tool=baro_order_followup",
        f"item={_summary_name(recommendation.market_id)}",
        f"rank={recommendation.rank if recommendation.rank is not None else 'unspecified'}",
        f"max_rank={recommendation.max_rank}",
    ]
    if buyer_limit > 0:
        buyers = recommendation.buyers[:buyer_limit]
        parts.append(f"buyer_count={len(buyers)}")
        parts.append(f"best_buy={_price(buyers[0].platinum if buyers else None)}")
    if seller_limit > 0:
        sellers = recommendation.sellers[:seller_limit]
        parts.append(f"seller_count={len(sellers)}")
        parts.append(f"best_sell={_price(sellers[0].platinum if sellers else None)}")
    return "\n".join(parts)


def find_baro_recommendation(
    recommendations: list[BaroRecommendation],
    message: str,
) -> BaroRecommendation | None:
    if not recommendations:
        return None
    match = re.search(r"(?:第|#)?\s*(\d+)\s*(?:个|条|项)?", message)
    if match:
        index = int(match.group(1)) - 1
        if 0 <= index < len(recommendations):
            return recommendations[index]
    lowered = message.lower()
    for rec in recommendations:
        name = display_item_name(rec.market_id).lower()
        if rec.market_id.lower() in lowered or name in lowered or rec.item_name.lower() in lowered:
            return rec
    return recommendations[0]


def parse_order_detail_limits(message: str) -> tuple[int, int]:
    text = message.lower()
    wants_many = any(word in text for word in ("多个", "多条", "前几个", "列表", "全部"))
    buyer_count = _explicit_order_limit(text, "买家")
    seller_count = _explicit_order_limit(text, "卖家")
    if buyer_count is not None or seller_count is not None:
        return buyer_count or 0, seller_count or 0

    count = _first_order_count(text)
    if count is not None:
        if "卖家" in text and "买家" not in text:
            return 0, count
        return count, 0
    if wants_many:
        if "买家" in text and "卖家" not in text:
            return 5, 0
        if "卖家" in text and "买家" not in text:
            return 0, 5
        return 5, 5
    if "卖家" in text and "买家" not in text:
        return 0, 1
    return 5, 0


_CHINESE_ORDER_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _first_order_count(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:个|条)?", text)
    if match:
        return max(1, min(int(match.group(1)), 10))
    match = re.search(r"([一二两三四五六七八九十])\s*(?:个|条)?", text)
    if match:
        return _CHINESE_ORDER_NUMBERS[match.group(1)]
    return None


def _explicit_order_limit(text: str, label: str) -> int | None:
    match = re.search(rf"(\d+)\s*(?:个|条)?\s*{label}", text)
    if match:
        return max(1, min(int(match.group(1)), 10))
    match = re.search(rf"([一二两三四五六七八九十])\s*(?:个|条)?\s*{label}", text)
    if match:
        return _CHINESE_ORDER_NUMBERS[match.group(1)]
    return None


def is_baro_order_detail_request(message: str) -> bool:
    lowered = message.lower()
    return any(word in lowered for word in ("玩家", "链接", "买家", "卖家", "私聊", "/w", "订单"))


def _inventory_recommendations(
    items: list[BaroItem],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    order_limit: int = 5,
) -> list[BaroRecommendation]:
    recommendations: list[BaroRecommendation] = []
    for item in items:
        market_id = item.market_id or _baro_market_id_from_item_type(item.item_type)
        if not market_id:
            continue
        try:
            orders = order_fetcher(market_id)
        except Exception:
            orders = []
        info = _item_info(market_id, item.item_name, item.item_type, None)
        if info is None:
            continue
        max_rank = _max_rank(market_id, info, orders)
        sellers = best_sellers(orders, limit=order_limit, rank_filter=max_rank)
        buyers = best_buyers(orders, limit=order_limit, rank_filter=max_rank)
        recommendations.append(
            BaroRecommendation(
                item_name=item.item_name,
                market_id=market_id,
                ducat_cost=item.ducat_cost,
                credit_cost=item.credit_cost,
                rank=max_rank,
                max_rank=max_rank,
                item_kind=str(info.get("type", "mod")),
                best_buy_price=buyers[0].platinum if buyers else None,
                best_sell_price=sellers[0].platinum if sellers else None,
            )
        )
    recommendations.sort(
        key=lambda r: (
            r.best_buy_price is None,
            r.best_buy_price or 999999,
            r.best_sell_price is None,
            -(r.best_sell_price or 0),
        )
    )
    return recommendations


def _item_info(
    item_id: str,
    item_name: str,
    item_type: str,
    item_info_lookup: ItemInfoLookup | None,
) -> dict | None:
    if item_info_lookup:
        info = item_info_lookup(item_id)
        if info and info.get("type") in {"mod", "arcane"}:
            return info

    lowered = f"{item_id} {item_name} {item_type}".lower()
    if item_id.startswith("arcane_") or "arcane" in lowered:
        return {"type": "arcane", "max_rank": 5}
    if item_id.startswith("mod_") or "primed_" in item_id or "/mods/" in lowered or "mod" in lowered:
        return {"type": "mod", "max_rank": _lookup_mod_max_rank(item_id) or 10}
    return None


def _max_rank(item_id: str, info: dict, orders: list[dict]) -> int:
    configured = info.get("max_rank")
    if isinstance(configured, int) and configured >= 0:
        return configured
    order_rank = get_max_rank_from_orders(orders)
    if order_rank is not None:
        return int(order_rank)
    if info.get("type") == "arcane":
        return 5
    return _lookup_mod_max_rank(item_id) or 10


def _resolve_rank(rank_request: int | str, max_rank: int) -> Optional[int]:
    if rank_request == "unspecified":
        return None
    if rank_request == "max":
        return max_rank
    try:
        requested = int(rank_request)
    except (TypeError, ValueError):
        requested = 0
    return max(0, min(requested, max_rank))


def _price(value: int | None) -> str:
    return f"{value}p" if value is not None else "暂无订单"


def _rank_suffix(recommendation: BaroRecommendation) -> str:
    if recommendation.rank is None:
        return ""
    return f" R{recommendation.rank}"


def _rank_text(recommendation: BaroRecommendation) -> str:
    if recommendation.rank is None:
        return f"请说明 R0-R{recommendation.max_rank} 或满级"
    return f"R{recommendation.rank}"


def _summary_name(item_id: str) -> str:
    return preferred_chinese_name(item_id) or english_name(item_id)


def _format_order_line(
    label: str,
    index: int,
    order: MarketOrder,
    recommendation: BaroRecommendation,
    order_side: str,
) -> str:
    profile = f"https://warframe.market/profile/{order.user_name}"
    command = _ranked_whisper(order.user_name, recommendation.market_id, order.platinum, order_side, recommendation.rank)
    return f"{label} {index}. {order.user_name} | {order.platinum}p | 数量 {order.quantity} | {profile}\n   {command}"


def _ranked_whisper(user_name: str, item_id: str, platinum: int, order_type: str, rank: int) -> str:
    action = "buy" if order_type == "sell" else "sell"
    item_name = f"{_summary_name(item_id)} (Rank {rank})"
    return f'/w {user_name} Hi! I want to {action}: "{item_name}" for {platinum} platinum. (warframe.market)'


_BARO_ITEM_TYPE_MAP: dict[str, str] | None = None


def _baro_market_id_from_item_type(item_type: str) -> str:
    global _BARO_ITEM_TYPE_MAP
    if _BARO_ITEM_TYPE_MAP is None:
        _BARO_ITEM_TYPE_MAP = _build_baro_item_type_map()
    return _BARO_ITEM_TYPE_MAP.get(item_type) or _BARO_ITEM_TYPE_MAP.get(item_type.replace("/StoreItems/", "/"), "")


def _build_baro_item_type_map() -> dict[str, str]:
    name_to_id = _market_name_to_id()
    mapping: dict[str, str] = {}
    for filename, keys in (
        ("ExportUpgrades_en.json", ("ExportUpgrades",)),
        ("ExportRelicArcane_en.json", ("ExportRelicArcane",)),
    ):
        path = Path(__file__).resolve().parent.parent / "data" / "export" / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        entries = []
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            for key in keys:
                entries = data.get(key, [])
                if entries:
                    break
        for entry in entries:
            unique = str(entry.get("uniqueName") or "")
            name = str(entry.get("name") or "")
            market_id = name_to_id.get(name.lower()) or _fallback_market_id(name)
            if unique and market_id:
                mapping[unique] = market_id
                mapping[unique.replace("/Lotus/", "/Lotus/StoreItems/")] = market_id
    return mapping


def _market_name_to_id() -> dict[str, str]:
    path = Path(__file__).resolve().parent.parent / "data" / "items_full.json"
    if not path.exists():
        return {}
    try:
        items = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    names: dict[str, str] = {}
    for item in items:
        item_id = item.get("item_id") or item.get("id")
        if not item_id:
            continue
        en_name = str(item.get("en_name") or item.get("en") or "")
        if en_name:
            names[en_name.lower()] = item_id
        for term in item.get("search_terms", []):
            names.setdefault(str(term).lower(), item_id)
    return names


def _fallback_market_id(name: str) -> str:
    return name.lower().replace(" ", "_").replace("'", "")


_MOD_RANK_CACHE: dict[str, int] | None = None


def _lookup_mod_max_rank(item_id: str) -> int | None:
    global _MOD_RANK_CACHE
    if _MOD_RANK_CACHE is None:
        _MOD_RANK_CACHE = _build_mod_rank_cache()
    return _MOD_RANK_CACHE.get(item_id)


def _build_mod_rank_cache() -> dict[str, int]:
    cache: dict[str, int] = {}
    path = Path(__file__).resolve().parent.parent / "githubProduct" / "warframe-items" / "data" / "json" / "Mods.json"
    if not path.exists():
        return cache
    try:
        mods = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return cache
    for mod in mods:
        name = str(mod.get("name", ""))
        if not name:
            continue
        item_key = name.lower().replace(" ", "_").replace("'", "")
        fusion_limit = mod.get("fusionLimit")
        if isinstance(fusion_limit, int):
            cache[item_key] = fusion_limit
    return cache
