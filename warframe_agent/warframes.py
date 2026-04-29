from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config
from .formatter import build_whisper
from .market import best_buyers, best_sellers, fetch_orders
from .names import display_item_name, english_name
from .trade_intent import detect_trade_intent

PARTS = {
    "blueprint": {"suffix": "blueprint", "label": "蓝图", "terms": ["蓝图", "总图", "bp", "blueprint"]},
    "chassis": {"suffix": "chassis_blueprint", "label": "机体", "terms": ["机体", "chassis"]},
    "neuroptics": {"suffix": "neuroptics_blueprint", "label": "头部神经光元", "terms": ["头", "头部", "神经", "神经光元", "neuroptics"]},
    "systems": {"suffix": "systems_blueprint", "label": "系统", "terms": ["系统", "systems"]},
    "barrel": {"suffix": "barrel", "label": "枪管", "terms": ["枪管", "barrel"]},
    "receiver": {"suffix": "receiver", "label": "枪机", "terms": ["枪机", "机匣", "receiver"]},
    "stock": {"suffix": "stock", "label": "枪托", "terms": ["枪托", "stock"]},
    "blade": {"suffix": "blade", "label": "刀刃", "terms": ["刀刃", "blade"]},
    "handle": {"suffix": "handle", "label": "刀柄", "terms": ["刀柄", "handle"]},
    "link": {"suffix": "link", "label": "连接器", "terms": ["连接器", "连结器", "link"]},
    "disc": {"suffix": "disc", "label": "圆盘", "terms": ["圆盘", "disc"]},
    "grip": {"suffix": "grip", "label": "弓身", "terms": ["弓身", "弓把", "grip"]},
    "string": {"suffix": "string", "label": "弓弦", "terms": ["弓弦", "string"]},
    "upper_limb": {"suffix": "upper_limb", "label": "上弓臂", "terms": ["上弓臂", "upper limb"]},
    "lower_limb": {"suffix": "lower_limb", "label": "下弓臂", "terms": ["下弓臂", "lower limb"]},
}
SET_TERMS = ["一套", "整套", "总价", "set", "成本", "拆件", "全套"]
MISSING_TERMS = ["还差", "缺", "补齐", "补全", "做一套", "做全", "还要"]
COMMON_WARFRAME_ALIASES = {
    "伏特": "volt",
    "电男": "volt",
    "犀牛": "rhino",
    "牛": "rhino",
    "毒妈": "saryn",
    "女枪": "mesa",
    "龙王": "chroma",
    "猴子": "wukong",
    "摸尸": "nekros",
    "奶妈": "trinity",
}
WARFRAME_CHINESE_NAMES = {
    "volt": "伏特",
    "rhino": "犀牛",
    "wukong": "悟空",
}
_SUFFIXES = ["_set"] + [f"_{info['suffix']}" for info in PARTS.values()]
_SUFFIXES.sort(key=len, reverse=True)


@dataclass(frozen=True)
class PrimeGroup:
    base_id: str
    items: dict[str, str]
    tags: set[str] = field(default_factory=set)
    zh_title: str | None = None
    en_title: str | None = None


@dataclass(frozen=True)
class WarframeQuery:
    base_id: str
    query_type: str
    part_key: str | None = None
    owned_parts: list[str] = field(default_factory=list)

    def item_ids(self) -> list[str]:
        if self.query_type == "part" and self.part_key:
            return [part_item_id(self.base_id, self.part_key)]
        group = build_prime_groups(_load_items()).get(self.base_id)
        if not group:
            return [set_item_id(self.base_id)] + [part_item_id(self.base_id, key) for key in PARTS]
        set_id = group.items.get("set")
        part_ids = [group.items[key] for key in group.items if key != "set"]
        return ([set_id] if set_id else []) + sorted(part_ids)


def parse_warframe_query(message: str, items: list[dict] | None = None) -> WarframeQuery | None:
    groups = build_prime_groups(items or _load_items())
    base_id = _detect_base_id(message, groups)
    if not base_id:
        return None
    owned_parts = _detect_owned_parts(message)
    if _looks_like_missing_parts_query(message) and owned_parts:
        return WarframeQuery(base_id=base_id, query_type="missing_parts", owned_parts=owned_parts)
    part_key = _detect_part_key(message)
    if part_key:
        return WarframeQuery(base_id=base_id, query_type="part", part_key=part_key)
    return WarframeQuery(base_id=base_id, query_type="set")


def price_warframe_query(
    message: str,
    items: list[dict] | None = None,
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
) -> str | None:
    items = items or _load_items()
    groups = build_prime_groups(items)
    query = parse_warframe_query(message, items)
    if not query:
        return None
    group = groups.get(query.base_id)
    if not group:
        return None
    intent = detect_trade_intent(message)
    if query.query_type == "missing_parts":
        return _render_missing_parts(group, query.owned_parts, order_fetcher)
    if query.query_type == "part" and query.part_key:
        return _render_part_price(group, query.part_key, order_fetcher, intent)
    return _render_set_price(group, order_fetcher, intent)


def build_prime_groups(items: list[dict]) -> dict[str, PrimeGroup]:
    grouped = {}
    for item in items:
        item_id = item.get("item_id", "")
        tags = set(item.get("tags", []))
        if "prime" not in tags:
            continue
        base_id, part_key = _split_item_id(item_id)
        if not base_id or not part_key:
            continue
        current = grouped.get(base_id)
        if current is None:
            current = PrimeGroup(base_id=base_id, items={}, tags=tags, zh_title=None, en_title=None)
        items_map = dict(current.items)
        items_map[part_key] = item_id
        zh_title = _pick_better_title(current.zh_title, _base_title_from_name(item.get("zh_name", "")), part_key)
        en_title = _pick_better_title(current.en_title, _base_title_from_name(item.get("en_name", "")), part_key)
        grouped[base_id] = PrimeGroup(base_id=base_id, items=items_map, tags=current.tags | tags, zh_title=zh_title, en_title=en_title)
    return grouped




def _pick_better_title(current: str | None, candidate: str | None, part_key: str | None) -> str | None:
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if _title_priority(part_key) > _title_priority_from_text(current) else current


def _title_priority(part_key: str | None) -> int:
    if part_key == "set":
        return 3
    if part_key == "blueprint":
        return 2
    return 1


def _title_priority_from_text(title: str) -> int:
    lowered = title.lower()
    if lowered.endswith(' prime') or lowered.endswith('prime'):
        return 2
    return 1

def set_item_id(base_id: str) -> str:
    return f"{base_id}_set"


def part_item_id(base_id: str, part_key: str) -> str:
    return f"{base_id}_{PARTS[part_key]['suffix']}"


def _render_part_price(group: PrimeGroup, part_key: str, order_fetcher: Callable[[str], list[dict]], intent: str = "overview") -> str:
    item_id = group.items.get(part_key)
    if not item_id:
        return None
    summary = _summarize_orders(item_id, order_fetcher(item_id))
    lines = [f"{_group_display_name(group)} {PARTS[part_key]['label']} / {display_item_name(item_id)}"]
    headline = _part_intent_headline(summary, intent)
    if headline:
        lines.extend([headline, ""])
    lines.extend(_summary_lines(summary))
    return "\n".join(lines)


def _render_set_price(group: PrimeGroup, order_fetcher: Callable[[str], list[dict]], intent: str = "overview") -> str:
    set_id = group.items.get("set")
    set_summary = _summarize_orders(set_id, order_fetcher(set_id)) if set_id else _empty_summary(None)
    part_summaries = [
        (key, _summarize_orders(item_id, order_fetcher(item_id)))
        for key, item_id in sorted(group.items.items())
        if key != "set"
    ]
    sell_total = sum(summary["sell_price"] or 0 for _, summary in part_summaries)
    buy_total = sum(summary["buy_price"] or 0 for _, summary in part_summaries)
    set_item_display = set_id or group.base_id
    lines = [f"{_group_display_name(group)} / {_group_english_title(group)} / {set_item_display}"]
    headline = _set_intent_headline(set_summary, sell_total, buy_total, intent)
    if headline:
        lines.extend([headline, ""])
    lines.extend(["", "整套直接交易:"])
    lines.append(f"- 整套直接买最低: {_price_text(set_summary['sell_price'])}")
    lines.append(f"- 整套最高收: {_price_text(set_summary['buy_price'])}")
    lines.extend(["", "拆件价格:"])
    for key, summary in part_summaries:
        lines.append(f"- {PARTS.get(key, {'label': key})['label']}: 买最低 {_price_text(summary['sell_price'])} / 卖最高 {_price_text(summary['buy_price'])}")
    lines.append(f"- 拆件买最低合计: {sell_total}p")
    lines.append(f"- 拆件最高收合计: {buy_total}p")
    lines.append("")
    lines.append(_recommendation(set_summary['sell_price'], sell_total, set_summary['buy_price'], buy_total))
    return "\n".join(lines)


def _render_missing_parts(group: PrimeGroup, owned_parts: list[str], order_fetcher: Callable[[str], list[dict]]) -> str:
    missing_parts = [key for key in group.items if key != "set" and key not in owned_parts]
    missing_summaries = [
        (key, _summarize_orders(group.items[key], order_fetcher(group.items[key])))
        for key in missing_parts
    ]
    missing_sell_total = sum(summary["sell_price"] or 0 for _, summary in missing_summaries)
    missing_buy_total = sum(summary["buy_price"] or 0 for _, summary in missing_summaries)
    set_id = group.items.get("set")
    set_summary = _summarize_orders(set_id, order_fetcher(set_id)) if set_id else _empty_summary(None)
    owned_labels = "、".join(PARTS[key]["label"] for key in owned_parts if key in PARTS)
    missing_labels = "、".join(PARTS[key]["label"] for key in missing_parts if key in PARTS)
    lines = [f"{_group_display_name(group)} / {_group_english_title(group)} / {set_id or group.base_id}"]
    lines.append(f"已拥有: {owned_labels or '未识别到部件'}")
    lines.append(f"缺少: {missing_labels or '无'}")
    for key, summary in missing_summaries:
        lines.append(f"- {PARTS[key]['label']}: 买最低 {_price_text(summary['sell_price'])} / 卖最高 {_price_text(summary['buy_price'])}")
    lines.append(f"补齐最低成本: {missing_sell_total}p")
    lines.append(f"补齐最高收合计: {missing_buy_total}p")
    if set_summary['sell_price'] is not None:
        lines.append(f"补齐后和整套对比: 整套直接买最低 {set_summary['sell_price']}p")
    return "\n".join(lines)


def _summarize_orders(item_id: str | None, orders: list[dict] | None) -> dict:
    if not item_id or orders is None:
        return _empty_summary(item_id)
    sellers = best_sellers(orders, limit=1)
    buyers = best_buyers(orders, limit=1)
    seller = sellers[0] if sellers else None
    buyer = buyers[0] if buyers else None
    return {
        "item_id": item_id,
        "sell_price": seller.platinum if seller else None,
        "buy_price": buyer.platinum if buyer else None,
        "seller": seller,
        "buyer": buyer,
    }


def _empty_summary(item_id: str | None) -> dict:
    return {"item_id": item_id, "sell_price": None, "buy_price": None, "seller": None, "buyer": None}


def _part_intent_headline(summary: dict, intent: str) -> str | None:
    if intent == "buy":
        return f"按你要买这个部件来看：当前最低卖价: {_price_text(summary['sell_price'])}"
    if intent == "sell":
        return f"按你要卖这个部件来看：当前最高收价: {_price_text(summary['buy_price'])}"
    if intent == "spread":
        return f"按你想看价差来看：最低卖价 {_price_text(summary['sell_price'])} / 最高收价 {_price_text(summary['buy_price'])}"
    return None


def _set_intent_headline(set_summary: dict, sell_total: int, buy_total: int, intent: str) -> str | None:
    if intent == "buy":
        return f"按你要买整套来看：整套直接买最低: {_price_text(set_summary['sell_price'])}；拆件买最低合计: {sell_total}p"
    if intent == "sell":
        return f"按你要卖整套来看：整套最高收: {_price_text(set_summary['buy_price'])}；拆件最高收合计: {buy_total}p"
    if intent == "spread":
        return f"按你想看价差来看：整套买卖价差 {_spread_text(set_summary['sell_price'], set_summary['buy_price'])}"
    return None


def _spread_text(sell_price: int | None, buy_price: int | None) -> str:
    if sell_price is None or buy_price is None:
        return "暂无"
    return f"{sell_price - buy_price}p"


def _summary_lines(summary: dict) -> list[str]:
    lines = []
    seller = summary["seller"]
    buyer = summary["buyer"]
    if seller:
        lines.append(f"最低卖价: {seller.platinum}p，数量 {seller.quantity}，卖家 {seller.user_name}")
        lines.append(f"推荐购买私聊: {build_whisper(seller.user_name, summary['item_id'], seller.platinum, 'sell')}")
    else:
        lines.append("最低卖价: 暂无在线卖家")
    if buyer:
        lines.append(f"最高收价: {buyer.platinum}p，数量 {buyer.quantity}，买家 {buyer.user_name}")
        lines.append(f"推荐出售私聊: {build_whisper(buyer.user_name, summary['item_id'], buyer.platinum, 'buy')}")
    else:
        lines.append("最高收价: 暂无在线买家")
    return lines


def _recommendation(set_sell: int | None, parts_sell_total: int, set_buy: int | None, parts_buy_total: int) -> str:
    advice = []
    if set_sell is not None:
        if parts_sell_total and parts_sell_total + 10 < set_sell:
            advice.append("老玩家建议: 拆件买明显更便宜，可以分开收。")
        else:
            advice.append("老玩家建议: 整套和拆件差距不大，直接买整套省时间。")
    if set_buy is not None and parts_buy_total:
        if parts_buy_total > set_buy + 10:
            advice.append("如果你是卖家，拆件出可能比整套卖更赚。")
        else:
            advice.append("如果你是卖家，整套出更省事。")
    return " ".join(advice) if advice else "老玩家建议: 当前订单不足，先观望或扩大查询范围。"


def _price_text(price: int | None) -> str:
    return f"{price}p" if price is not None else "暂无"


def _detect_base_id(message: str, groups: dict[str, PrimeGroup]) -> str | None:
    normalized = message.lower().replace(" ", "_")
    for zh_alias, english_base in COMMON_WARFRAME_ALIASES.items():
        if zh_alias in message and ("p" in message.lower() or "prime" in message.lower()):
            candidate = f"{english_base}_prime"
            if candidate in groups:
                return candidate
    ranked = sorted(groups.values(), key=lambda group: len(group.base_id), reverse=True)
    for group in ranked:
        candidates = [group.base_id, _group_english_title(group).lower().replace(" ", "_"), _group_english_title(group).lower()]
        for zh_alias in _group_zh_aliases(group):
            candidates.append(zh_alias.replace(" ", ""))
            candidates.append((zh_alias + "p").replace(" ", ""))
        if any(candidate and candidate in normalized for candidate in candidates if "_" in candidate or candidate == candidate.lower()):
            return group.base_id
        lower_message = message.lower()
        if _group_english_title(group).lower() in lower_message:
            return group.base_id
        if any(zh_alias and zh_alias in message for zh_alias in _group_zh_aliases(group)):
            return group.base_id
    return None




def _group_zh_aliases(group: PrimeGroup) -> list[str]:
    aliases = []
    if group.zh_title:
        aliases.append(group.zh_title)
        if group.zh_title.endswith(" Prime"):
            aliases.append(group.zh_title[: -len(" Prime")])
    return [alias for alias in aliases if alias]

def _detect_part_key(message: str) -> str | None:
    lowered = message.lower()
    for key, info in PARTS.items():
        if any(term in message or term in lowered for term in info["terms"]):
            return key
    return None


def _detect_owned_parts(message: str) -> list[str]:
    lowered = message.lower()
    owned = []
    for key, info in PARTS.items():
        if any(term in message or term in lowered for term in info["terms"]):
            owned.append(key)
    return owned


def _looks_like_missing_parts_query(message: str) -> bool:
    lowered = message.lower()
    return any(term in message or term in lowered for term in MISSING_TERMS)


def _group_display_name(group: PrimeGroup) -> str:
    english_base = group.base_id.replace("_prime", "")
    if "warframe" in group.tags:
        chinese = WARFRAME_CHINESE_NAMES.get(english_base)
        if chinese:
            return f"{chinese} Prime"
    return _group_english_title(group)


def _group_english_title(group: PrimeGroup) -> str:
    if group.en_title:
        return group.en_title
    return english_name(set_item_id(group.base_id)).replace(" Set", "")


def _split_item_id(item_id: str) -> tuple[str | None, str | None]:
    for suffix in _SUFFIXES:
        if item_id.endswith(suffix):
            base_id = item_id[: -len(suffix)]
            part_key = "set" if suffix == "_set" else _part_key_for_suffix(suffix[1:])
            return base_id, part_key
    return None, None


def _part_key_for_suffix(suffix: str) -> str | None:
    for key, info in PARTS.items():
        if info["suffix"] == suffix:
            return key
    return None


def _base_title_from_name(name: str) -> str | None:
    if not name:
        return None
    for tail in [" Set", " Blueprint", " 一套", " 蓝图", " 机体 蓝图", " 头部神经光元 蓝图", " 系统 蓝图", " 枪管", " 枪机", " 枪托", " 刀刃", " 刀柄", " 连接器", " 圆盘", " 弓身", " 弓弦", " 上弓臂", " 下弓臂"]:
        if name.endswith(tail):
            return name[: -len(tail)]
    return name


def _load_items(path: Path = config.ITEMS_FULL_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)
