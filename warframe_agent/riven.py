"""紫卡（Riven）搜索模块 — 查询 warframe.market 拍卖并按属性过滤。"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable

import requests

from . import config
from .market import MARKET_HEADERS, _rate_lock, _wait_for_rate_limit

logger = logging.getLogger(__name__)

# ── 属性中文 → API url_name 映射 ──────────────────────────────────────────────

RIVEN_ATTRIBUTES: dict[str, str] = {
    "暴击率": "critical_chance",
    "暴击": "critical_chance",
    "暴击伤害": "critical_damage",
    "暴伤": "critical_damage",
    "基伤": "base_damage_/_melee_damage",
    "伤害": "base_damage_/_melee_damage",
    "多重": "multishot",
    "射速": "fire_rate_/_attack_speed",
    "攻速": "fire_rate_/_attack_speed",
    "射速攻速": "fire_rate_/_attack_speed",
    "毒伤": "toxin_damage",
    "冰伤": "cold_damage",
    "火伤": "heat_damage",
    "电伤": "electric_damage",
    "穿刺": "puncture_damage",
    "切割": "slash_damage",
    "冲击": "impact_damage",
    "触发率": "status_chance",
    "触发几率": "status_chance",
    "触发时间": "status_duration",
    "弹匣": "magazine_capacity",
    "装填": "reload_speed",
    "弹药": "ammo_maximum",
    "后坐力": "recoil",
    "穿透": "punch_through",
    "变焦": "zoom",
    "飞行速度": "projectile_speed",
    "对grineer": "damage_vs_grineer",
    "对corpus": "damage_vs_corpus",
    "对infested": "damage_vs_infested",
}

# 复合关键词 → 属性列表
COMPOUND_KEYWORDS: dict[str, list[str]] = {
    "双爆": ["critical_chance", "critical_damage"],
    "双暴": ["critical_chance", "critical_damage"],
}

# 属性 url_name → 中文显示名
ATTR_DISPLAY_NAMES: dict[str, str] = {
    "critical_chance": "暴击率",
    "critical_damage": "暴击伤害",
    "base_damage_/_melee_damage": "基伤",
    "multishot": "多重",
    "fire_rate_/_attack_speed": "射速/攻速",
    "toxin_damage": "毒伤",
    "cold_damage": "冰伤",
    "heat_damage": "火伤",
    "electric_damage": "电伤",
    "puncture_damage": "穿刺",
    "slash_damage": "切割",
    "impact_damage": "冲击",
    "status_chance": "触发率",
    "status_duration": "触发时间",
    "magazine_capacity": "弹匣",
    "reload_speed": "装填",
    "ammo_maximum": "弹药",
    "recoil": "后坐力",
    "punch_through": "穿透",
    "zoom": "变焦",
    "projectile_speed": "飞行速度",
    "damage_vs_grineer": "对Grineer",
    "damage_vs_corpus": "对Corpus",
    "damage_vs_infested": "对Infested",
}

# ── 数据结构 ──────────────────────────────────────────────────────────────────


@dataclass
class RivenQuery:
    weapon_url_name: str
    positive_attrs: list[str] = field(default_factory=list)
    negative_attrs: list[str] = field(default_factory=list)
    no_negative: bool = False
    max_price: int | None = None


@dataclass
class RivenResult:
    weapon: str
    mod_name: str
    positive_attrs: list[dict] = field(default_factory=list)
    negative_attrs: list[dict] = field(default_factory=list)
    price: int | None = None
    seller: str = ""
    seller_status: str = ""
    re_rolls: int = 0


# ── 解析 ─────────────────────────────────────────────────────────────────────


def parse_riven_query(
    message: str,
    weapon_resolver: Callable[[str], str] | None = None,
) -> RivenQuery | None:
    """从自然语言解析紫卡查询。返回 None 表示不是紫卡查询。"""
    if not _looks_like_riven_query(message):
        return None

    weapon_name = _extract_weapon_name(message, weapon_resolver)
    if not weapon_name:
        return None

    positive, negative, no_negative = _extract_attributes(message)
    max_price = _extract_max_price(message)

    return RivenQuery(
        weapon_url_name=weapon_name,
        positive_attrs=positive,
        negative_attrs=negative,
        no_negative=no_negative,
        max_price=max_price,
    )


def _looks_like_riven_query(message: str) -> bool:
    keywords = {"紫卡", "裂罅", "riven", "洗卡", "紫卡搜", "查紫卡"}
    lowered = message.lower()
    return any(kw in lowered for kw in keywords)


def _extract_weapon_name(message: str, resolver: Callable[[str], str] | None) -> str | None:
    """提取消息中的武器名。"""
    # 先去掉紫卡相关关键词，避免干扰武器名识别
    cleaned = message
    for kw in ["紫卡", "裂罅", "riven", "Riven", "查", "搜", "搜索", "查询", "无负", "不要负"]:
        cleaned = cleaned.replace(kw, " ")

    # 去掉属性关键词
    for attr_kw in list(RIVEN_ATTRIBUTES.keys()) + list(COMPOUND_KEYWORDS.keys()):
        cleaned = cleaned.replace(attr_kw, " ")

    # 去掉价格相关
    cleaned = re.sub(r"\d+\s*[pP铂]", " ", cleaned)
    cleaned = re.sub(r"以下|以内|不超过", " ", cleaned)

    # 提取剩余的有意义词
    tokens = cleaned.split()
    if not tokens:
        return None

    # 尝试每个 token 作为武器名
    if resolver:
        for token in tokens:
            token = token.strip()
            if not token or len(token) < 2:
                continue
            try:
                resolved = resolver(token)
                if resolved:
                    return resolved
            except Exception:
                continue

    # 回退：尝试直接用 token 作为英文武器名
    for token in tokens:
        token = token.strip().lower()
        if token and len(token) >= 2 and re.match(r"^[a-z_]+$", token):
            return token

    return None


def _extract_attributes(message: str) -> tuple[list[str], list[str], bool]:
    """提取消息中的正/负属性。返回 (positive, negative, no_negative)。"""
    positive = []
    negative = []
    no_negative = False

    # 检查无负
    if "无负" in message or "不要负" in message or "没负" in message:
        no_negative = True

    # 检查复合关键词
    for keyword, attrs in COMPOUND_KEYWORDS.items():
        if keyword in message:
            for attr in attrs:
                if attr not in positive:
                    positive.append(attr)

    # 检查单个属性关键词
    for cn_name, api_name in RIVEN_ATTRIBUTES.items():
        if cn_name in message and api_name not in positive:
            positive.append(api_name)

    # 检查显式负属性（如 "负后坐力"、"负后坐"）
    for cn_name, api_name in RIVEN_ATTRIBUTES.items():
        if f"负{cn_name}" in message:
            negative.append(api_name)

    return positive, negative, no_negative


def _extract_max_price(message: str) -> int | None:
    """提取价格上限，如 "100以下"、"50p以内"、"不超过200"。"""
    match = re.search(r"(\d+)\s*(?:以下|以内|[pP铂])", message)
    if match:
        return int(match.group(1))
    match = re.search(r"不超过\s*(\d+)", message)
    if match:
        return int(match.group(1))
    return None


# ── API 调用 ─────────────────────────────────────────────────────────────────

_RIVEN_API_BASE = "https://api.warframe.market/v1/auctions/search"
_RIVEN_CACHE_TTL = 120  # 2 分钟
_riven_cache: dict[str, tuple[list[RivenResult], float]] = {}


def fetch_riven_auctions(weapon_url_name: str) -> list[dict]:
    """从 warframe.market 获取紫卡拍卖原始数据。"""
    cache_key = weapon_url_name
    if cache_key in _riven_cache:
        data, ts = _riven_cache[cache_key]
        if time.time() - ts < _RIVEN_CACHE_TTL:
            return data

    url = f"{_RIVEN_API_BASE}?type=riven&weapon_url_name={weapon_url_name}&sort_by=price_asc"

    for attempt in range(3):
        try:
            _wait_for_rate_limit()
            resp = requests.get(url, headers=MARKET_HEADERS, timeout=15)
            if resp.status_code == 429:
                backoff = min(0.5 * (2 ** attempt), 30)
                logger.warning("Riven API 429，退避 %.1fs", backoff)
                time.sleep(backoff)
                continue
            resp.raise_for_status()
            auctions = resp.json().get("payload", {}).get("auctions", [])
            return auctions
        except requests.RequestException as exc:
            logger.warning("Riven API 请求失败 (attempt %d): %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(1)

    return []


def search_rivens(query: RivenQuery) -> list[RivenResult]:
    """搜索并过滤紫卡拍卖。"""
    auctions = fetch_riven_auctions(query.weapon_url_name)
    results = []

    for item in auctions:
        auction_item = item.get("item", {})
        attributes = auction_item.get("attributes", [])

        pos_attrs = []
        neg_attrs = []
        for attr in attributes:
            entry = {
                "stat": attr.get("url_name", ""),
                "value": attr.get("value", 0),
            }
            if attr.get("positive", True):
                pos_attrs.append(entry)
            else:
                neg_attrs.append(entry)

        # 过滤：必须包含所有期望的正属性
        if query.positive_attrs:
            pos_stat_names = {a["stat"] for a in pos_attrs}
            if not all(attr in pos_stat_names for attr in query.positive_attrs):
                continue

        # 过滤：无负
        if query.no_negative and neg_attrs:
            continue

        # 过滤：指定负属性
        if query.negative_attrs:
            neg_stat_names = {a["stat"] for a in neg_attrs}
            if not all(attr in neg_stat_names for attr in query.negative_attrs):
                continue

        # 价格
        price = item.get("buyout_price") or item.get("starting_price")
        if query.max_price and price and price > query.max_price:
            continue

        owner = item.get("owner", {})
        results.append(RivenResult(
            weapon=auction_item.get("weapon_url_name", ""),
            mod_name=auction_item.get("name", ""),
            positive_attrs=pos_attrs,
            negative_attrs=neg_attrs,
            price=price,
            seller=owner.get("ingame_name", ""),
            seller_status=owner.get("status", ""),
            re_rolls=auction_item.get("re_rolls", 0),
        ))

    # 按价格排序
    results.sort(key=lambda r: r.price or 999999)
    return results[:10]


# ── 格式化 ────────────────────────────────────────────────────────────────────


def format_riven_results(query: RivenQuery, results: list[RivenResult]) -> str:
    """格式化紫卡搜索结果。"""
    weapon_display = query.weapon_url_name.replace("_", " ").title()
    conditions = []
    if query.positive_attrs:
        cond = "+".join(ATTR_DISPLAY_NAMES.get(a, a) for a in query.positive_attrs)
        conditions.append(f"正属性: {cond}")
    if query.no_negative:
        conditions.append("无负")
    elif query.negative_attrs:
        cond = "+".join(ATTR_DISPLAY_NAMES.get(a, a) for a in query.negative_attrs)
        conditions.append(f"负属性: {cond}")
    if query.max_price:
        conditions.append(f"≤{query.max_price}p")

    header = f"{weapon_display} 紫卡搜索结果"
    if conditions:
        header += f"（{'、'.join(conditions)}）"

    if not results:
        return f"{header}\n未找到符合条件的紫卡。"

    lines = [header, f"共找到 {len(results)} 条，按价格排序：", ""]

    for i, r in enumerate(results, 1):
        price_str = f"{r.price}p" if r.price else "未定价"
        lines.append(f"{i}. {r.mod_name} | {price_str} | {r.re_rolls}次洗卡")

        # 属性行
        attr_parts = []
        for a in r.positive_attrs:
            name = ATTR_DISPLAY_NAMES.get(a["stat"], a["stat"])
            attr_parts.append(f"+{name} {a['value']}")
        for a in r.negative_attrs:
            name = ATTR_DISPLAY_NAMES.get(a["stat"], a["stat"])
            attr_parts.append(f"-{name} {a['value']}")
        if attr_parts:
            lines.append(f"   {' '.join(attr_parts)}")

        # 卖家行
        status_map = {"ingame": "游戏中", "online": "在线", "offline": "离线"}
        status = status_map.get(r.seller_status, r.seller_status)
        lines.append(f"   卖家: {r.seller} ({status})")

    return "\n".join(lines)
