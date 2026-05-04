"""Prime 套装利润分析器 — 对比整套买卖 vs 拆件买卖。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import config
from .market import best_buyers, best_sellers, fetch_orders
from .names import display_item_name
from .warframes import PARTS, PrimeGroup, build_prime_groups, _load_items


@dataclass(frozen=True)
class SetProfitResult:
    base_id: str
    display_name: str
    set_buy_price: int | None
    parts_sell_total: int
    set_sell_price: int | None
    parts_buy_total: int
    profit_buy_parts_sell_set: int
    profit_buy_set_sell_parts: int
    best_strategy: str
    best_profit: int
    volume_48h: int | None
    part_count: int


def _fetch_statistics(item_id: str) -> int | None:
    """获取 48 小时成交量。"""
    import requests
    url = f"https://api.warframe.market/v1/items/{item_id}/statistics"
    try:
        resp = requests.get(url, headers={"Platform": "pc", "Language": "en"}, timeout=10)
        if resp.status_code == 200:
            stats = resp.json().get("payload", {}).get("statistics_closed", [])
            return sum(s.get("volume", 0) for s in stats[-4:])
    except Exception:
        pass
    return None


def analyze_set_profit(
    group: PrimeGroup,
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
) -> SetProfitResult | None:
    """分析单个 Prime 套装的利润。"""
    set_id = group.items.get("set")
    part_ids = [v for k, v in group.items.items() if k != "set"]
    if not part_ids:
        return None

    # 获取套装价格
    set_buy_price = None
    set_sell_price = None
    if set_id:
        try:
            set_orders = order_fetcher(set_id)
            set_sellers = best_sellers(set_orders, limit=1)
            set_buyers = best_buyers(set_orders, limit=1)
            set_buy_price = set_sellers[0].platinum if set_sellers else None
            set_sell_price = set_buyers[0].platinum if set_buyers else None
        except Exception:
            pass

    # 获取各部件价格
    parts_sell_total = 0
    parts_buy_total = 0
    parts_with_sell = 0
    parts_with_buy = 0
    for pid in part_ids:
        try:
            orders = order_fetcher(pid)
            sellers = best_sellers(orders, limit=1)
            buyers = best_buyers(orders, limit=1)
            if sellers:
                parts_sell_total += sellers[0].platinum
                parts_with_sell += 1
            if buyers:
                parts_buy_total += buyers[0].platinum
                parts_with_buy += 1
        except Exception:
            continue

    if parts_with_sell == 0 and parts_with_buy == 0:
        return None

    # 策略 1: 买部件 → 卖套装
    profit_buy_parts_sell_set = (set_sell_price or 0) - parts_buy_total
    # 策略 2: 买套装 → 卖部件
    profit_buy_set_sell_parts = parts_sell_total - (set_buy_price or 0)

    if profit_buy_parts_sell_set <= 0 and profit_buy_set_sell_parts <= 0:
        return None

    if profit_buy_parts_sell_set >= profit_buy_set_sell_parts:
        best_strategy = "买部件→卖套装"
        best_profit = profit_buy_parts_sell_set
    else:
        best_strategy = "买套装→卖部件"
        best_profit = profit_buy_set_sell_parts

    # 48h 成交量
    volume_48h = None
    if set_id:
        volume_48h = _fetch_statistics(set_id)

    return SetProfitResult(
        base_id=group.base_id,
        display_name=group.en_title or display_item_name(group.base_id),
        set_buy_price=set_buy_price,
        parts_sell_total=parts_sell_total,
        set_sell_price=set_sell_price,
        parts_buy_total=parts_buy_total,
        profit_buy_parts_sell_set=profit_buy_parts_sell_set,
        profit_buy_set_sell_parts=profit_buy_set_sell_parts,
        best_strategy=best_strategy,
        best_profit=best_profit,
        volume_48h=volume_48h,
        part_count=len(part_ids),
    )


def scan_all_set_profits(
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    min_profit: int = 5,
    limit: int = 20,
) -> list[SetProfitResult]:
    """扫描所有 Prime 套装，找出利润机会。"""
    groups = build_prime_groups(items)
    results = []
    for group in list(groups.values())[:80]:  # 限制扫描数量
        try:
            result = analyze_set_profit(group, order_fetcher)
            if result and result.best_profit >= min_profit:
                results.append(result)
        except Exception:
            continue

    results.sort(key=lambda r: r.best_profit, reverse=True)
    return results[:limit]
