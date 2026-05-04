"""投资顾问 — 按预算扫描物品翻转机会，按 ROI 排序。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from . import config
from .market import best_buyers, best_sellers, fetch_orders
from .names import display_item_name


@dataclass(frozen=True)
class InvestmentOpportunity:
    item_id: str
    display_name: str
    buy_price: int
    sell_price: int
    profit: int
    roi_pct: float
    volume_48h: int | None
    daily_volume: float | None
    supply_count: int
    demand_count: int
    risk_level: str


@dataclass
class InvestmentFilter:
    budget: int = 1000
    min_roi_pct: float = 10.0
    min_daily_volume: int = 1
    min_profit: int = 3
    limit: int = 15


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


def _assess_risk(daily_volume: float | None, supply_count: int, demand_count: int) -> str:
    """评估风险等级。"""
    vol = daily_volume or 0
    ratio = supply_count / demand_count if demand_count > 0 else 999
    if vol >= 5 and ratio < 3:
        return "low"
    if vol >= 2 or ratio < 5:
        return "medium"
    return "high"


def analyze_investment(
    item_id: str,
    orders: list[dict],
    filters: InvestmentFilter,
) -> InvestmentOpportunity | None:
    """分析单个物品的投资机会。"""
    sellers = best_sellers(orders, limit=1)
    buyers = best_buyers(orders, limit=1)
    if not sellers or not buyers:
        return None

    buy_price = sellers[0].platinum  # 买入成本
    sell_price = buyers[0].platinum  # 卖出收入
    profit = sell_price - buy_price

    if profit < filters.min_profit:
        return None
    if buy_price > filters.budget:
        return None

    roi_pct = (profit / buy_price) * 100 if buy_price > 0 else 0
    if roi_pct < filters.min_roi_pct:
        return None

    # 成交量
    volume_48h = _fetch_statistics(item_id)
    daily_volume = (volume_48h / 2) if volume_48h else None
    if daily_volume is not None and daily_volume < filters.min_daily_volume:
        return None

    # 供需统计
    supply_count = sum(1 for o in orders if o.get("order_type") == "sell")
    demand_count = sum(1 for o in orders if o.get("order_type") == "buy")
    risk_level = _assess_risk(daily_volume, supply_count, demand_count)

    return InvestmentOpportunity(
        item_id=item_id,
        display_name=display_item_name(item_id),
        buy_price=buy_price,
        sell_price=sell_price,
        profit=profit,
        roi_pct=roi_pct,
        volume_48h=volume_48h,
        daily_volume=daily_volume,
        supply_count=supply_count,
        demand_count=demand_count,
        risk_level=risk_level,
    )


def scan_investments(
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    filters: InvestmentFilter | None = None,
) -> list[InvestmentOpportunity]:
    """扫描物品列表，找出投资机会。"""
    if filters is None:
        filters = InvestmentFilter()

    # 构建候选列表：优先扫描赋能和高价值 Mod
    candidates = []
    for item in items:
        tags = item.get("tags", [])
        url_name = item.get("url_name", "")
        if not url_name:
            continue
        # 赋能、Mod、Prime 部件
        if any(t in tags for t in ["mod", "arcane"]) or "_prime_" in url_name:
            if item.get("tradable", False):
                candidates.append(url_name)

    results = []
    for item_id in candidates[:80]:  # 限制扫描数量
        try:
            orders = order_fetcher(item_id)
            result = analyze_investment(item_id, orders, filters)
            if result:
                results.append(result)
        except Exception:
            continue

    results.sort(key=lambda r: r.roi_pct, reverse=True)
    return results[:filters.limit]
