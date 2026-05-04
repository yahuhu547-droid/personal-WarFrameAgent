from __future__ import annotations

import asyncio
import time
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

_cache: dict[str, tuple[list[dict], float]] = {}
_last_request_time = 0.0
_rate_limit_delay = 0.34  # ~3 requests per second


@dataclass(frozen=True)
class MarketOrder:
    order_type: str
    platinum: int
    quantity: int
    user_name: str
    status: str
    reputation: int
    mod_rank: int | None = None


@dataclass
class BuyPlanEntry:
    user_name: str
    platinum: int
    quantity: int
    subtotal: int
    reputation: int


@dataclass
class BuyPlan:
    entries: list[BuyPlanEntry]
    total_cost: int
    total_quantity: int
    fulfilled: bool


def fetch_orders(item_id: str) -> list[dict]:
    global _last_request_time

    # 检查缓存
    if item_id in _cache:
        data, timestamp = _cache[item_id]
        if time.time() - timestamp < 60:  # TTL 60秒
            return data

    # 限速
    elapsed = time.time() - _last_request_time
    if elapsed < _rate_limit_delay:
        time.sleep(_rate_limit_delay - elapsed)

    url = f"{config.MARKET_API_BASE}/orders/item/{item_id}"
    response = requests.get(url, headers=MARKET_HEADERS, timeout=config.REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    _last_request_time = time.time()

    data = response.json()
    orders = data.get("data", []) if "data" in data else data.get("payload", {}).get("orders", [])

    # 更新缓存
    _cache[item_id] = (orders, time.time())

    return orders


def validate_item_id(item_id: str) -> bool:
    try:
        fetch_orders(item_id)
        return True
    except requests.RequestException:
        return False


def best_sellers(orders: Iterable[dict], limit: int = config.TOP_ORDER_LIMIT, rank_filter: int | None = None) -> list[MarketOrder]:
    return sorted(
        _to_market_orders(orders, order_type="sell", rank_filter=rank_filter),
        key=lambda order: (order.platinum, -order.reputation),
    )[:limit]


def best_buyers(orders: Iterable[dict], limit: int = config.TOP_ORDER_LIMIT, rank_filter: int | None = None) -> list[MarketOrder]:
    return sorted(
        _to_market_orders(orders, order_type="buy", rank_filter=rank_filter),
        key=lambda order: (-order.platinum, -order.reputation),
    )[:limit]


def build_buy_plan(orders: list[dict], needed: int, rank_filter: int | None = None) -> BuyPlan:
    """贪心组合：按价格从低到高，凑够 needed 个"""
    sellers = sorted(
        _to_market_orders(orders, order_type="sell", rank_filter=rank_filter),
        key=lambda o: (o.platinum, -o.reputation),
    )
    entries: list[BuyPlanEntry] = []
    remaining = needed
    for seller in sellers:
        if remaining <= 0:
            break
        take = min(seller.quantity, remaining)
        entries.append(BuyPlanEntry(
            user_name=seller.user_name,
            platinum=seller.platinum,
            quantity=take,
            subtotal=seller.platinum * take,
            reputation=seller.reputation,
        ))
        remaining -= take
    total_cost = sum(e.subtotal for e in entries)
    total_quantity = sum(e.quantity for e in entries)
    return BuyPlan(
        entries=entries,
        total_cost=total_cost,
        total_quantity=total_quantity,
        fulfilled=remaining <= 0,
    )


def _to_market_orders(orders: Iterable[dict], order_type: str, rank_filter: int | None = None) -> list[MarketOrder]:
    result: list[MarketOrder] = []
    for order in orders:
        user = order.get("user", {})
        if (order.get("order_type") or order.get("type")) != order_type:
            continue
        if user.get("status") != "ingame":
            continue
        mod_rank = order.get("rank") if order.get("rank") is not None else order.get("mod_rank")
        # 如果指定了等级过滤，只保留该等级的订单
        if rank_filter is not None and mod_rank is not None and mod_rank != rank_filter:
            continue
        result.append(
            MarketOrder(
                order_type=order_type,
                platinum=int(order.get("platinum", 0)),
                quantity=int(order.get("quantity", 0)),
                user_name=str(user.get("ingame_name") or user.get("ingameName") or "未知玩家"),
                status=str(user.get("status", "unknown")),
                reputation=int(user.get("reputation", 0)),
                mod_rank=mod_rank,
            )
        )
    return result


async def fetch_orders_async(item_id: str) -> list[dict]:
    return await asyncio.to_thread(fetch_orders, item_id)


def clear_cache():
    """清除所有缓存"""
    global _cache
    _cache.clear()


def get_max_rank_from_orders(orders: Iterable[dict]) -> int | None:
    """从订单数据中检测最大等级，用于赋能/Mod 等级过滤"""
    ranks = []
    for o in orders:
        r = o.get("rank") if o.get("rank") is not None else o.get("mod_rank")
        if r is not None:
            ranks.append(r)
    return max(ranks) if ranks else None
