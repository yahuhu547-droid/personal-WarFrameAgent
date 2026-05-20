"""紫卡（Riven）搜索模块 — 查询 warframe.market 拍卖并按属性过滤。"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlencode

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

RIVEN_WEAPON_ALIASES: dict[str, str] = {
    "战刃": "glaive",
    "glaive": "glaive",
}

# ── 数据结构 ──────────────────────────────────────────────────────────────────


@dataclass
class RivenQuery:
    weapon_url_name: str
    positive_attrs: list[str] = field(default_factory=list)
    negative_attrs: list[str] = field(default_factory=list)
    no_negative: bool = False
    max_price: int | None = None
    seller_statuses: tuple[str, ...] = ()


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


@dataclass
class RivenScore:
    score: int
    rating: str
    positive_notes: list[str] = field(default_factory=list)
    negative_notes: list[str] = field(default_factory=list)
    price_position: str = "样本不足"
    confidence: str = "低"
    disclaimer: str = "当前挂牌参考，不代表真实成交价"


@dataclass
class RivenSearchPage:
    results: list[RivenResult]
    total: int
    page: int = 1
    page_size: int = 10

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def start_index(self) -> int:
        if self.total == 0:
            return 0
        return (self.page - 1) * self.page_size + 1

    @property
    def end_index(self) -> int:
        return min(self.page * self.page_size, self.total)

    def __iter__(self):
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)

    def __getitem__(self, index):
        return self.results[index]

    def __bool__(self) -> bool:
        return bool(self.results)


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
        positive_attrs=list(dict.fromkeys(positive)),
        negative_attrs=list(dict.fromkeys(negative)),
        no_negative=no_negative,
        max_price=max_price,
    )


def _looks_like_riven_query(message: str) -> bool:
    keywords = {"紫卡", "裂罅", "riven", "洗卡", "紫卡搜", "查紫卡"}
    lowered = message.lower()
    return any(kw in lowered for kw in keywords)


def _extract_weapon_name(message: str, resolver: Callable[[str], str] | None) -> str | None:
    """提取消息中的武器名。"""
    for alias, weapon_url_name in sorted(RIVEN_WEAPON_ALIASES.items(), key=lambda entry: -len(entry[0])):
        if alias in message:
            return weapon_url_name

    # 先去掉紫卡相关关键词，避免干扰武器名识别
    cleaned = message
    noise_keywords = ["紫卡", "裂罅", "riven", "Riven", "查", "搜", "搜索", "查询", "帮我", "给我", "给出", "我要", "要", "找", "看看", "这个", "值不值得", "值得买", "能买吗", "适合买", "评价", "分析", "无负", "不要负", "在线", "在线玩家", "在线卖家", "在线的", "游戏中", "玩家", "卖家", "买家", "online"]
    for kw in sorted(noise_keywords, key=len, reverse=True):
        cleaned = cleaned.replace(kw, " ")

    # 去掉"负+属性"复合词（先去长的，再去短的，避免"负"残留）
    for attr_kw in sorted(list(RIVEN_ATTRIBUTES.keys()) + list(COMPOUND_KEYWORDS.keys()), key=len, reverse=True):
        cleaned = cleaned.replace(f"负{attr_kw}", " ")
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

    # 先检查显式负属性（如 "负后坐力"、"负暴击率"），排除"无负"/"不要负"前缀
    clean_for_neg = message.replace("无负", "").replace("不要负", "").replace("没负", "")
    for cn_name, api_name in _attribute_terms_by_length():
        if f"负{cn_name}" in clean_for_neg:
            negative.append(api_name)

    # 检查正向属性关键词（排除已被"负"修饰的）
    positive_text = message
    for cn_name, api_name in _attribute_terms_by_length():
        if cn_name in positive_text and api_name not in positive and api_name not in negative:
            positive.append(api_name)
            positive_text = positive_text.replace(cn_name, " ")

    return positive, negative, no_negative


def _attribute_terms_by_length() -> list[tuple[str, str]]:
    return sorted(RIVEN_ATTRIBUTES.items(), key=lambda entry: -len(entry[0]))


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
_riven_cache: dict[str, tuple[list[dict], float]] = {}


def fetch_riven_auctions(
    weapon_url_name: str,
    positive_attrs: list[str] | None = None,
    negative_attrs: list[str] | None = None,
    max_price: int | None = None,
) -> list[dict]:
    """从 warframe.market 获取紫卡拍卖原始数据。"""
    params = {
        "type": "riven",
        "weapon_url_name": weapon_url_name,
        "sort_by": "price_asc",
    }
    if positive_attrs:
        params["positive_stats"] = ",".join(dict.fromkeys(positive_attrs))
    if negative_attrs:
        params["negative_stats"] = ",".join(dict.fromkeys(negative_attrs))
    if max_price:
        params["buyout_price"] = str(max_price)
    cache_key = urlencode(params, doseq=True)
    if cache_key in _riven_cache:
        data, ts = _riven_cache[cache_key]
        if time.time() - ts < _RIVEN_CACHE_TTL:
            return data

    url = f"{_RIVEN_API_BASE}?{cache_key}"

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


def search_rivens(query: RivenQuery, page: int = 1, page_size: int = 10) -> RivenSearchPage:
    """搜索并过滤紫卡拍卖。"""
    auctions = fetch_riven_auctions(
        query.weapon_url_name,
        positive_attrs=query.positive_attrs,
        negative_attrs=query.negative_attrs,
        max_price=query.max_price,
    )
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
        seller_status = owner.get("status", "")
        if query.seller_statuses and seller_status not in query.seller_statuses:
            continue

        results.append(RivenResult(
            weapon=auction_item.get("weapon_url_name", ""),
            mod_name=auction_item.get("name", ""),
            positive_attrs=pos_attrs,
            negative_attrs=neg_attrs,
            price=price,
            seller=owner.get("ingame_name", ""),
            seller_status=seller_status,
            re_rolls=auction_item.get("re_rolls", 0),
        ))

    # 按价格排序
    if query.seller_statuses:
        status_rank = {status: index for index, status in enumerate(query.seller_statuses)}
        results.sort(key=lambda r: (status_rank.get(r.seller_status, 999), r.price or 999999))
    else:
        results.sort(key=lambda r: r.price or 999999)

    total = len(results)
    page_size = max(1, page_size)
    max_page = max(1, (total + page_size - 1) // page_size)
    page = min(max(1, page), max_page)
    start = (page - 1) * page_size
    return RivenSearchPage(results=results[start:start + page_size], total=total, page=page, page_size=page_size)


# ── 格式化 ────────────────────────────────────────────────────────────────────


def build_riven_whisper(user_name: str) -> str:
    return f"/w {user_name} Hi!"


def _coerce_riven_page(page: RivenSearchPage | list[RivenResult]) -> RivenSearchPage:
    if isinstance(page, list):
        return RivenSearchPage(results=page, total=len(page))
    return page


HIGH_VALUE_RIVEN_STATS = {
    "critical_chance": 24,
    "critical_damage": 24,
    "multishot": 22,
    "base_damage_/_melee_damage": 20,
    "toxin_damage": 14,
    "heat_damage": 12,
    "cold_damage": 12,
    "electric_damage": 12,
    "status_chance": 12,
}
MEDIUM_VALUE_RIVEN_STATS = {
    "fire_rate_/_attack_speed": 10,
    "slash_damage": 8,
    "puncture_damage": 5,
    "impact_damage": 4,
    "projectile_speed": 6,
    "punch_through": 6,
    "reload_speed": 4,
    "magazine_capacity": 3,
    "ammo_maximum": 2,
    "status_duration": 3,
}
LOW_IMPACT_NEGATIVES = {"recoil", "zoom", "ammo_maximum"}
HARMFUL_NEGATIVES = {
    "critical_chance",
    "critical_damage",
    "multishot",
    "base_damage_/_melee_damage",
    "fire_rate_/_attack_speed",
    "status_chance",
}


def build_riven_market_cues(page: RivenSearchPage | list[RivenResult]) -> dict:
    page = _coerce_riven_page(page)
    prices = sorted(result.price for result in page.results if result.price is not None)
    if not prices:
        return {"sample_size": 0, "min_price": None, "max_price": None, "median_price": None, "confidence": "低"}
    mid = len(prices) // 2
    median = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2
    confidence = "高" if len(prices) >= 8 else "中" if len(prices) >= 4 else "低"
    return {
        "sample_size": len(prices),
        "min_price": prices[0],
        "max_price": prices[-1],
        "median_price": median,
        "confidence": confidence,
    }


def score_riven_result(
    result: RivenResult,
    query: RivenQuery | None = None,
    market_cues: dict | None = None,
) -> RivenScore:
    score = 35
    positive_notes: list[str] = []
    negative_notes: list[str] = []

    positive_stats = [attr.get("stat", "") for attr in result.positive_attrs]
    negative_stats = [attr.get("stat", "") for attr in result.negative_attrs]
    for stat in positive_stats:
        points = HIGH_VALUE_RIVEN_STATS.get(stat, MEDIUM_VALUE_RIVEN_STATS.get(stat, 0))
        score += points
        if points >= 20:
            positive_notes.append(f"核心属性: {ATTR_DISPLAY_NAMES.get(stat, stat)}")
        elif points >= 8:
            positive_notes.append(f"有效属性: {ATTR_DISPLAY_NAMES.get(stat, stat)}")

    if {"critical_chance", "critical_damage"}.issubset(set(positive_stats)):
        score += 12
        positive_notes.append("暴击组合优秀")
    if {"critical_chance", "critical_damage", "multishot"}.issubset(set(positive_stats)):
        score += 8
        positive_notes.append("双爆多重组合稀缺")

    for stat in negative_stats:
        if stat in LOW_IMPACT_NEGATIVES:
            score += 4
            positive_notes.append(f"可接受负面: {ATTR_DISPLAY_NAMES.get(stat, stat)}")
        elif stat in HARMFUL_NEGATIVES:
            score -= 22
            negative_notes.append(f"有害负面: {ATTR_DISPLAY_NAMES.get(stat, stat)}")
        else:
            score -= 8
            negative_notes.append(f"负面属性: {ATTR_DISPLAY_NAMES.get(stat, stat)}")

    if query and query.positive_attrs:
        matched = set(query.positive_attrs).intersection(positive_stats)
        score += len(matched) * 3
    if result.price is None:
        score -= 8
        negative_notes.append("未标价，价格参考弱")

    score = max(0, min(100, score))
    cues = market_cues or {}
    price_position = _riven_price_position(result.price, cues)
    confidence = str(cues.get("confidence") or "低")
    return RivenScore(
        score=score,
        rating=_riven_rating(score),
        positive_notes=positive_notes,
        negative_notes=negative_notes,
        price_position=price_position,
        confidence=confidence,
    )


def format_riven_score_label(score: RivenScore) -> str:
    return f"属性评分 {score.score}/100 ({score.rating}) · 价格位置: {score.price_position} · 置信度: {score.confidence} · {score.disclaimer}"


def _riven_rating(score: int) -> str:
    if score >= 85:
        return "S"
    if score >= 70:
        return "A"
    if score >= 55:
        return "B"
    if score >= 40:
        return "C"
    return "D"


def _riven_price_position(price: int | None, cues: dict) -> str:
    if price is None or not cues or cues.get("sample_size", 0) < 2:
        return "样本不足"
    min_price = cues.get("min_price")
    max_price = cues.get("max_price")
    median = cues.get("median_price")
    if min_price is None or max_price is None or median is None:
        return "样本不足"
    if price <= min_price:
        return "当前列表低位"
    if price >= max_price:
        return "高于当前列表"
    if price <= median * 0.9:
        return "低于当前中位"
    if price >= median * 1.1:
        return "高于当前中位"
    return "接近当前中位"


def _safe_model_field(value: object, max_len: int = 120, forbidden_terms: tuple[str, ...] = ()) -> str:
    text = str(value if value is not None else "").strip()
    text = re.sub(r"https?://\S+", "[url-redacted]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)/w\s+\S+", "[whisper-redacted]", text)
    for term in forbidden_terms:
        term = str(term or "").strip()
        if term:
            text = re.sub(re.escape(term), "[seller-redacted]", text, flags=re.IGNORECASE)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[:max_len - 1] + "…"
    return text


def _format_model_attrs(result: RivenResult) -> str:
    forbidden_terms = (result.seller,)
    attr_parts = []
    for attr in result.positive_attrs:
        stat = _safe_model_field(attr.get("stat", ""), max_len=80, forbidden_terms=forbidden_terms)
        value = _safe_model_field(attr.get("value", ""), max_len=40, forbidden_terms=forbidden_terms)
        if stat:
            attr_parts.append(f"+{stat}={value}")
    for attr in result.negative_attrs:
        stat = _safe_model_field(attr.get("stat", ""), max_len=80, forbidden_terms=forbidden_terms)
        value = _safe_model_field(attr.get("value", ""), max_len=40, forbidden_terms=forbidden_terms)
        if stat:
            attr_parts.append(f"-{stat}={value}")
    return ",".join(attr_parts) if attr_parts else "none"


def _join_filter_values(values: list[str] | tuple[str, ...], empty: str = "none") -> str:
    cleaned = [_safe_model_field(value, max_len=80) for value in values if _safe_model_field(value, max_len=80)]
    return ",".join(cleaned) if cleaned else empty


def format_riven_results_for_model(query: RivenQuery, page: RivenSearchPage | list[RivenResult], max_items: int = 8) -> str:
    """格式化给模型读取的紫卡搜索摘要，刻意不包含卖家名、私聊命令或原始拍卖标识。"""
    page = _coerce_riven_page(page)
    max_items = max(0, max_items)
    seller_statuses = _join_filter_values(query.seller_statuses, empty="all")
    lines = [
        "tool=riven_search",
        f"weapon={_safe_model_field(query.weapon_url_name, max_len=80)}",
        "filters: "
        f"positive_attrs={_join_filter_values(query.positive_attrs)}; "
        f"negative_attrs={_join_filter_values(query.negative_attrs)}; "
        f"no_negative={query.no_negative}; "
        f"max_price={query.max_price if query.max_price is not None else 'none'}; "
        f"seller_statuses={seller_statuses}",
        "pagination: "
        f"page={page.page}; "
        f"page_size={page.page_size}; "
        f"total={page.total}; "
        f"shown={page.start_index}-{page.end_index}; "
        f"has_next={page.has_next}; "
        f"has_prev={page.has_prev}",
    ]

    if not page.results or max_items == 0:
        lines.append("items=none")
        return "\n".join(lines)

    lines.append("items:")
    market_cues = build_riven_market_cues(page)
    for index, result in enumerate(page.results[:max_items], page.start_index):
        price = result.price if result.price is not None else "unpriced"
        forbidden_terms = (result.seller,)
        score = score_riven_result(result, query=query, market_cues=market_cues)
        lines.append(
            f"- index={index}; "
            f"weapon={_safe_model_field(result.weapon, max_len=80, forbidden_terms=forbidden_terms)}; "
            f"mod_name={_safe_model_field(result.mod_name, forbidden_terms=forbidden_terms)}; "
            f"attrs={_format_model_attrs(result)}; "
            f"price={price}; "
            f"rerolls={result.re_rolls}; "
            f"seller_status={_safe_model_field(result.seller_status, max_len=40, forbidden_terms=forbidden_terms)}; "
            f"score={score.score}; rating={score.rating}; price_position={score.price_position}; "
            f"confidence={score.confidence}; disclaimer={score.disclaimer}"
        )
    if len(page.results) > max_items:
        lines.append(f"truncated_items={len(page.results) - max_items}")
    return "\n".join(lines)


def format_riven_results(query: RivenQuery, page: RivenSearchPage | list[RivenResult]) -> str:
    """格式化紫卡搜索结果。"""
    page = _coerce_riven_page(page)

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

    if not page.results:
        return f"{header}\n未找到符合条件的紫卡。"

    lines = [header, f"共找到 {page.total} 条，展示第 {page.start_index}-{page.end_index} 条，按价格排序：", ""]

    market_cues = build_riven_market_cues(page)
    for i, r in enumerate(page.results, page.start_index):
        price_str = f"{r.price}p" if r.price else "未定价"
        riven_score = score_riven_result(r, query=query, market_cues=market_cues)
        lines.append(f"{i}. {r.mod_name} | {price_str} | {r.re_rolls}次洗卡")
        lines.append(f"   {format_riven_score_label(riven_score)}")

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
        if r.seller and r.seller_status == "ingame":
            lines.append(f"   招呼: {build_riven_whisper(r.seller)}")
        elif r.seller and r.seller_status == "online":
            lines.append("   卖家站内在线，建议打开拍卖页或站内沟通；游戏内交易先打招呼后再发送紫卡名称。")

    hints = []
    if page.has_next:
        hints.append("回复“下一组”查看更多")
    if page.has_prev:
        hints.append("回复“上一组”返回上一页")
    if hints:
        lines.append("")
        lines.append("；".join(hints) + "。")

    return "\n".join(lines)
