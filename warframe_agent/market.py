from __future__ import annotations

import asyncio
import json as _json
import logging
import random
import sqlite3
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

from . import config

logger = logging.getLogger(__name__)

MARKET_HEADERS = {
    "Accept": "application/json",
    "Crossplay": "true",
    "Language": "en",
    "Platform": "pc",
    "User-Agent": "warframe-local-trading-agent/1.0",
}

_cache: OrderedDict[str, tuple[list[dict], float]] = OrderedDict()
_stats_cache: OrderedDict[str, tuple[dict, float]] = OrderedDict()
_rate_lock = threading.Lock()
_last_request_time = 0.0
_rate_limit_delay = 0.34  # ~3 requests per second
_max_retries = 3

# ── 持久化缓存 ────────────────────────────────────────────────────────────

_PERSISTENT_DB_PATH = config.DATA_DIR / "price_cache.db"
_PERSISTENT_TTL = 600  # 10 分钟
_db_conn: sqlite3.Connection | None = None


def _get_db() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        _db_conn = sqlite3.connect(str(_PERSISTENT_DB_PATH), check_same_thread=False)
        _db_conn.execute("PRAGMA journal_mode=WAL")
        _db_conn.execute("""
            CREATE TABLE IF NOT EXISTS market_cache (
                item_id TEXT PRIMARY KEY,
                cache_type TEXT NOT NULL,
                data_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        _db_conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_type ON market_cache(cache_type)")
        _db_conn.commit()
    return _db_conn


def _persistent_get(item_id: str, cache_type: str) -> dict | list | None:
    """从 SQLite 持久化缓存读取。"""
    try:
        db = _get_db()
        row = db.execute(
            "SELECT data_json, updated_at FROM market_cache WHERE item_id=? AND cache_type=?",
            (item_id, cache_type),
        ).fetchone()
        if row and (time.time() - row[1]) < _PERSISTENT_TTL:
            return _json.loads(row[0])
    except Exception as exc:
        logger.debug("Persistent cache read error for %s: %s", item_id, exc)
    return None


def _persistent_set(item_id: str, cache_type: str, data: dict | list):
    """写入 SQLite 持久化缓存。"""
    try:
        db = _get_db()
        db.execute(
            "INSERT OR REPLACE INTO market_cache (item_id, cache_type, data_json, updated_at) VALUES (?, ?, ?, ?)",
            (item_id, cache_type, _json.dumps(data, ensure_ascii=False), time.time()),
        )
        db.commit()
    except Exception as exc:
        logger.debug("Persistent cache write error for %s: %s", item_id, exc)


def warm_persistent_cache():
    """启动时从 SQLite 预热内存缓存（加载最近 100 条）。"""
    try:
        db = _get_db()
        cutoff = time.time() - _PERSISTENT_TTL
        rows = db.execute(
            "SELECT item_id, cache_type, data_json, updated_at FROM market_cache WHERE updated_at > ? ORDER BY updated_at DESC LIMIT 100",
            (cutoff,),
        ).fetchall()
        loaded = 0
        for item_id, cache_type, data_json, updated_at in rows:
            data = _json.loads(data_json)
            if cache_type == "orders":
                _cache[item_id] = (data, updated_at)
                loaded += 1
            elif cache_type == "stats":
                _stats_cache[item_id] = (data, updated_at)
                loaded += 1
        if loaded:
            logger.info("Persistent cache warmed: %d entries loaded", loaded)
    except Exception as exc:
        logger.debug("Persistent cache warm-up failed: %s", exc)


def clear_persistent_cache():
    """清除持久化缓存。"""
    try:
        db = _get_db()
        db.execute("DELETE FROM market_cache")
        db.commit()
    except Exception:
        pass


def _wait_for_rate_limit():
    """线程安全的速率限制，带随机抖动避免固定间隔被识别为爬虫。"""
    global _last_request_time
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_request_time
        delay = _rate_limit_delay + random.uniform(0, 0.1)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        _last_request_time = time.time()


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
    # 检查内存缓存
    if item_id in _cache:
        data, timestamp = _cache[item_id]
        if time.time() - timestamp < config.ORDER_CACHE_TTL:
            _cache.move_to_end(item_id)
            return data

    # 检查 SQLite 持久化缓存
    persistent = _persistent_get(item_id, "orders")
    if persistent is not None:
        _cache[item_id] = (persistent, time.time())
        _cache.move_to_end(item_id)
        return persistent

    _wait_for_rate_limit()

    url = f"{config.MARKET_API_BASE}/orders/item/{item_id}"
    last_exc = None
    for attempt in range(_max_retries):
        try:
            response = requests.get(url, headers=MARKET_HEADERS, timeout=config.REQUEST_TIMEOUT_SECONDS)
            if response.status_code == 429:
                backoff = min(0.5 * (2 ** attempt), 30)
                logger.warning("fetch_orders 429 rate limited for %s, backoff %.1fs", item_id, backoff)
                time.sleep(backoff)
                _wait_for_rate_limit()
                continue
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            last_exc = exc
            logger.debug("fetch_orders attempt %d failed for %s: %s", attempt + 1, item_id, exc)
            if attempt < _max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
    else:
        raise last_exc

    data = response.json()
    orders = data.get("data", []) if "data" in data else data.get("payload", {}).get("orders", [])

    # 更新内存缓存（LRU 淘汰）
    _cache[item_id] = (orders, time.time())
    _cache.move_to_end(item_id)
    while len(_cache) > config.CACHE_MAX_SIZE:
        _cache.popitem(last=False)

    # 持久化到 SQLite
    _persistent_set(item_id, "orders", orders)

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
    """清除所有缓存（内存 + 持久化）"""
    global _cache, _stats_cache
    _cache.clear()
    _stats_cache.clear()
    clear_persistent_cache()


def get_max_rank_from_orders(orders: Iterable[dict]) -> int | None:
    """从订单数据中检测最大等级，用于赋能/Mod 等级过滤"""
    ranks = []
    for o in orders:
        r = o.get("rank") if o.get("rank") is not None else o.get("mod_rank")
        if r is not None:
            ranks.append(r)
    return max(ranks) if ranks else None


def fetch_item_statistics(item_id: str) -> dict | None:
    """获取物品 48 小时成交量（共享函数，供 mod_flipper/set_profit/investment 使用）。"""
    # 检查内存缓存
    if item_id in _stats_cache:
        data, timestamp = _stats_cache[item_id]
        if time.time() - timestamp < config.STATS_CACHE_TTL:
            _stats_cache.move_to_end(item_id)
            return data

    # 检查 SQLite 持久化缓存
    persistent = _persistent_get(item_id, "stats")
    if persistent is not None:
        _stats_cache[item_id] = (persistent, time.time())
        _stats_cache.move_to_end(item_id)
        return persistent

    _wait_for_rate_limit()

    url = f"https://api.warframe.market/v1/items/{item_id}/statistics"
    last_exc = None
    for attempt in range(_max_retries):
        try:
            resp = requests.get(url, headers=MARKET_HEADERS, timeout=config.REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 429:
                backoff = min(0.5 * (2 ** attempt), 30)
                logger.warning("fetch_item_statistics 429 rate limited for %s, backoff %.1fs", item_id, backoff)
                time.sleep(backoff)
                _wait_for_rate_limit()
                continue
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            last_exc = exc
            logger.debug("fetch_item_statistics attempt %d failed for %s: %s", attempt + 1, item_id, exc)
            if attempt < _max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
    else:
        logger.warning("fetch_item_statistics failed for %s after %d attempts: %s", item_id, _max_retries, last_exc)
        return None

    stats = resp.json().get("payload", {}).get("statistics_closed", {})
    # statistics_closed 是 dict: {"48hours": [...], "90days": [...]}
    if isinstance(stats, dict):
        entries = stats.get("48hours", [])
    else:
        entries = stats
    volume = sum(s.get("volume", 0) for s in entries[-4:])
    result = {"volume_48h": volume}

    # 更新内存缓存
    _stats_cache[item_id] = (result, time.time())
    _stats_cache.move_to_end(item_id)
    while len(_stats_cache) > config.CACHE_MAX_SIZE:
        _stats_cache.popitem(last=False)

    # 持久化到 SQLite
    _persistent_set(item_id, "stats", result)

    return result
