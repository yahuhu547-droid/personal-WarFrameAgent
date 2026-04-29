from __future__ import annotations

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


def detect_trade_intent(message: str) -> str:
    normalized = normalize_lookup_key(message)
    if _contains_any(normalized, SELL_TERMS):
        return "sell"
    if _contains_any(normalized, BUY_TERMS):
        return "buy"
    if _contains_any(normalized, SPREAD_TERMS):
        return "spread"
    return "overview"


def _contains_any(normalized_message: str, terms: list[str]) -> bool:
    return any(normalize_lookup_key(term) in normalized_message for term in terms)
