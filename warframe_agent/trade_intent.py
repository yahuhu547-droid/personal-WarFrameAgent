from __future__ import annotations

import re

from .dictionary import normalize_lookup_key

BUY_TERMS = [
    "我要买",
    "我想买",
    "最低卖",
    "最低卖价",
    "卖最低",
    "收一套",
    "收这个",
]
SELL_TERMS = [
    "我要卖",
    "我想卖",
    "我要出",
    "我想出",
    "最高收",
    "最高收价",
    "收多少",
    "有人收吗",
    "卖给谁",
]
SPREAD_TERMS = [
    "价差",
    "倒货",
    "倒一手",
    "能赚",
    "利润",
    "差价",
]

TREND_TERMS = [
    "会涨",
    "会跌",
    "涨吗",
    "跌吗",
    "涨了吗",
    "跌了吗",
    "趋势",
    "走势",
    "预测",
    "行情",
]

COMPARE_TERMS = [
    "对比",
    "比较",
    " vs ",
    " 哪个",
    " 哪个更",
    "哪个划算",
]

# 已完成交易关键词
COMPLETED_BUY_TERMS = [
    "我买了", "我刚买", "我收了", "我刚收", "入手了", "买到了",
    "花了", "收了一套", "买了一套",
]
COMPLETED_SELL_TERMS = [
    "我卖了", "我刚卖", "我出了", "我刚出", "卖掉了", "出掉了",
    "卖了", "出了",
]

# 价格提取正则
_PRICE_PATTERN = re.compile(r"(\d+)\s*[pP铂]")


def detect_trade_intent(message: str) -> str:
    normalized = normalize_lookup_key(message)
    if _contains_any(normalized, SELL_TERMS):
        return "sell"
    if _contains_any(normalized, BUY_TERMS):
        return "buy"
    if _contains_any(normalized, SPREAD_TERMS):
        return "spread"
    return "overview"


def detect_trend_query(message: str) -> bool:
    """检测是否为价格趋势/预测类查询。"""
    normalized = normalize_lookup_key(message)
    return _contains_any(normalized, TREND_TERMS)


def detect_compare_query(message: str) -> bool:
    """检测是否为多物品对比类查询。"""
    normalized = normalize_lookup_key(message)
    return _contains_any(normalized, COMPARE_TERMS)


def detect_completed_trade(message: str) -> tuple[str, int] | None:
    """检测已完成的交易语句，返回 (trade_type, price) 或 None。

    示例：
    - "我买了充沛 80p" → ("buy", 80)
    - "刚出了一套犀牛 120p" → ("sell", 120)
    """
    for term in COMPLETED_BUY_TERMS:
        if term in message:
            price_match = _PRICE_PATTERN.search(message)
            if price_match:
                return ("buy", int(price_match.group(1)))
    for term in COMPLETED_SELL_TERMS:
        if term in message:
            price_match = _PRICE_PATTERN.search(message)
            if price_match:
                return ("sell", int(price_match.group(1)))
    return None


def _contains_any(normalized_message: str, terms: list[str]) -> bool:
    return any(normalize_lookup_key(term) in normalized_message for term in terms)
