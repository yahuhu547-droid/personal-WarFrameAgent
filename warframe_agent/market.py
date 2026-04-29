from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import requests

from . import config


MARKET_HEADERS = {
    "Accept": "application/json",
    "Crossplay": "true",
    "Language": "en",
    "Platform": "pc",
    "User-Agent": "warframe-local-trading-agent/1.0",
}


@dataclass(frozen=True)
class MarketOrder:
    order_type: str
    platinum: int
    quantity: int
    user_name: str
    status: str
    reputation: int


def fetch_orders(item_id: str) -> list[dict]:
    url = f"{config.MARKET_API_BASE}/orders/item/{item_id}"
    response = requests.get(url, headers=MARKET_HEADERS, timeout=config.REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    if "data" in data:
        return data.get("data", [])
    return data.get("payload", {}).get("orders", [])


def validate_item_id(item_id: str) -> bool:
    try:
        fetch_orders(item_id)
        return True
    except requests.RequestException:
        return False


def best_sellers(orders: Iterable[dict], limit: int = config.TOP_ORDER_LIMIT) -> list[MarketOrder]:
    return sorted(
        _to_market_orders(orders, order_type="sell"),
        key=lambda order: (order.platinum, -order.reputation),
    )[:limit]


def best_buyers(orders: Iterable[dict], limit: int = config.TOP_ORDER_LIMIT) -> list[MarketOrder]:
    return sorted(
        _to_market_orders(orders, order_type="buy"),
        key=lambda order: (-order.platinum, -order.reputation),
    )[:limit]


def _to_market_orders(orders: Iterable[dict], order_type: str) -> list[MarketOrder]:
    result: list[MarketOrder] = []
    for order in orders:
        user = order.get("user", {})
        if (order.get("order_type") or order.get("type")) != order_type:
            continue
        if user.get("status") != "ingame":
            continue
        result.append(
            MarketOrder(
                order_type=order_type,
                platinum=int(order.get("platinum", 0)),
                quantity=int(order.get("quantity", 0)),
                user_name=str(user.get("ingame_name") or user.get("ingameName") or "未知玩家"),
                status=str(user.get("status", "unknown")),
                reputation=int(user.get("reputation", 0)),
            )
        )
    return result
