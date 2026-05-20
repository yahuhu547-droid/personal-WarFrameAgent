"""Prime 套装利润分析器 — 对比整套买卖 vs 拆件买卖。"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

from . import config
from .formatter import market_item_url, summarize_trade_order
from .market import MarketOrder, best_buyers, best_sellers, fetch_item_statistics, fetch_orders
from .names import display_item_name
from .trade_plan import build_trade_plan, trade_step_from_order
from .warframes import PARTS, PrimeGroup, build_prime_groups, _load_items


_PART_LABELS = {
    "blueprint": "蓝图", "chassis": "机体", "neuroptics": "头部神经光元",
    "systems": "系统", "barrel": "枪管", "receiver": "枪机", "stock": "枪托",
    "blade": "刀刃", "handle": "刀柄", "link": "连接器", "disc": "圆盘",
    "grip": "弓身", "string": "弓弦", "upper_limb": "上弓臂", "lower_limb": "下弓臂",
    "hilt": "剑柄", "guard": "护手", "gauntlet": "护臂", "carapace": "外壳",
    "cerebrum": "中枢", "boot": "靴甲", "head": "头部", "blades": "双刃",
    "pouch": "囊袋", "stars": "星镖", "band": "项圈", "buckle": "扣环",
    "ornament": "饰物", "chain": "锁链", "bag": "袋囊", "wing": "翼片",
}


def _part_label(part_key: str) -> str:
    return _PART_LABELS.get(part_key, part_key)


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
    set_item_id: str = ""
    market_url: str = ""
    part_details: list[dict] | None = None
    set_seller: dict | None = None
    set_buyer: dict | None = None
    trade_plan: dict | None = None
    best_cost: int = 0
    best_revenue: int = 0
    roi_pct: float = 0.0
    liquidity_score: float = 0.0
    risk_level: str = "medium"
    risk_score: float = 0.0
    opportunity_score: float = 0.0
    supply_count: int = 0
    demand_count: int = 0


def _count_orders(orders: list[dict], order_type: str) -> int:
    return sum(1 for order in orders if order.get("order_type") == order_type)


def _score_liquidity(volume_48h: int | None, supply_count: int, demand_count: int) -> float:
    volume_score = min(float(volume_48h or 0) * 2.0, 50.0)
    order_score = min(float(supply_count + demand_count) * 6.0, 50.0)
    return round(volume_score + order_score, 1)


def _score_risk(volume_48h: int | None, supply_count: int, demand_count: int) -> tuple[str, float]:
    score = 0.0
    if (volume_48h or 0) < 5:
        score += 35.0
    elif (volume_48h or 0) < 15:
        score += 15.0
    if supply_count <= 1:
        score += 20.0
    if demand_count <= 1:
        score += 20.0
    if min(supply_count, demand_count) == 0:
        score += 40.0
    score = min(score, 100.0)
    if score >= 60:
        return "high", round(score, 1)
    if score >= 30:
        return "medium", round(score, 1)
    return "low", round(score, 1)


def _score_opportunity(best_profit: int, roi_pct: float, liquidity_score: float, risk_score: float) -> float:
    return round(float(best_profit) + min(roi_pct, 200.0) * 0.25 + liquidity_score * 0.35 - risk_score * 0.2, 1)


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
    set_seller: MarketOrder | None = None
    set_buyer: MarketOrder | None = None
    set_seller_summary = None
    set_buyer_summary = None
    supply_count = 0
    demand_count = 0
    if set_id:
        try:
            set_orders = order_fetcher(set_id)
            supply_count += _count_orders(set_orders, "sell")
            demand_count += _count_orders(set_orders, "buy")
            set_sellers = best_sellers(set_orders, limit=1)
            set_buyers = best_buyers(set_orders, limit=1)
            set_seller = set_sellers[0] if set_sellers else None
            set_buyer = set_buyers[0] if set_buyers else None
            set_buy_price = set_seller.platinum if set_seller else None
            set_sell_price = set_buyer.platinum if set_buyer else None
            set_seller_summary = summarize_trade_order(set_seller, set_id)
            set_buyer_summary = summarize_trade_order(set_buyer, set_id)
        except Exception as exc:
            logger.debug("获取套装 %s 订单失败: %s", set_id, exc)

    # 获取各部件价格
    parts_sell_total = 0
    parts_buy_total = 0
    parts_with_sell = 0
    parts_with_buy = 0
    part_details: list[dict] = []
    part_seller_orders: list[tuple[str, str, MarketOrder]] = []
    part_buyer_orders: list[tuple[str, str, MarketOrder]] = []
    for part_key, pid in group.items.items():
        if part_key == "set":
            continue
        try:
            orders = order_fetcher(pid)
            supply_count += _count_orders(orders, "sell")
            demand_count += _count_orders(orders, "buy")
            sellers = best_sellers(orders, limit=1)
            buyers = best_buyers(orders, limit=1)
            seller = sellers[0] if sellers else None
            buyer = buyers[0] if buyers else None
            if seller:
                parts_sell_total += seller.platinum
                parts_with_sell += 1
                part_seller_orders.append((part_key, pid, seller))
            if buyer:
                parts_buy_total += buyer.platinum
                parts_with_buy += 1
                part_buyer_orders.append((part_key, pid, buyer))
            part_details.append({
                "key": part_key,
                "name": _part_label(part_key),
                "item_id": pid,
                "market_url": market_item_url(pid),
                "sell_price": seller.platinum if seller else None,
                "buy_price": buyer.platinum if buyer else None,
                "seller": summarize_trade_order(seller, pid),
                "buyer": summarize_trade_order(buyer, pid),
            })
        except Exception as exc:
            logger.debug("获取部件 %s 订单失败: %s", pid, exc)
            continue

    if parts_with_sell == 0 and parts_with_buy == 0:
        return None

    # 策略 1: 买部件 → 卖套装
    profit_buy_parts_sell_set = (
        set_sell_price - parts_sell_total
        if set_sell_price is not None and parts_with_sell == len(part_ids)
        else 0
    )
    # 策略 2: 买套装 → 卖部件
    profit_buy_set_sell_parts = (
        parts_buy_total - set_buy_price
        if set_buy_price is not None and parts_with_buy == len(part_ids)
        else 0
    )

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
        stats = fetch_item_statistics(set_id)
        volume_48h = stats.get("volume_48h") if stats else None

    if best_strategy == "买部件→卖套装":
        best_cost = parts_sell_total
        best_revenue = set_sell_price or 0
        supply_count = len(part_seller_orders)
        demand_count = 1 if set_buyer else 0
    else:
        best_cost = set_buy_price or 0
        best_revenue = parts_buy_total
        supply_count = 1 if set_seller else 0
        demand_count = len(part_buyer_orders)
    roi_pct = round((best_profit / best_cost * 100), 1) if best_cost > 0 else 0.0
    liquidity_score = _score_liquidity(volume_48h, supply_count, demand_count)
    risk_level, risk_score = _score_risk(volume_48h, supply_count, demand_count)
    opportunity_score = _score_opportunity(best_profit, roi_pct, liquidity_score, risk_score)

    display = group.en_title or display_item_name(group.base_id)
    trade_plan = None
    if best_strategy == "买部件→卖套装" and set_id and set_buyer:
        buy_steps = [
            trade_step_from_order(
                side="buy",
                label=f"买入部件：{_part_label(part_key)}",
                item_id=pid,
                order=order,
                quantity=1,
            )
            for part_key, pid, order in part_seller_orders
        ]
        sell_steps = [trade_step_from_order(
            side="sell",
            label="出售整套",
            item_id=set_id,
            order=set_buyer,
            quantity=1,
        )]
        trade_plan = build_trade_plan(
            source="set_profit",
            strategy="buy_parts_sell_set",
            display_strategy="买部件 -> 卖整套",
            item_id=set_id,
            display_name=display,
            required_quantity=len(buy_steps),
            buy_steps=buy_steps,
            sell_steps=sell_steps,
            total_cost=parts_sell_total,
            total_revenue=set_sell_price or 0,
            profit=profit_buy_parts_sell_set,
            roi_pct=roi_pct,
            volume_48h=volume_48h,
            risk_level=risk_level,
        )
    elif best_strategy == "买套装→卖部件" and set_id and set_seller:
        buy_steps = [trade_step_from_order(
            side="buy",
            label="买入整套",
            item_id=set_id,
            order=set_seller,
            quantity=1,
        )]
        sell_steps = [
            trade_step_from_order(
                side="sell",
                label=f"出售部件：{_part_label(part_key)}",
                item_id=pid,
                order=order,
                quantity=1,
            )
            for part_key, pid, order in part_buyer_orders
        ]
        trade_plan = build_trade_plan(
            source="set_profit",
            strategy="buy_set_sell_parts",
            display_strategy="买整套 -> 卖部件",
            item_id=set_id,
            display_name=display,
            required_quantity=1,
            buy_steps=buy_steps,
            sell_steps=sell_steps,
            total_cost=set_buy_price or 0,
            total_revenue=parts_buy_total,
            profit=profit_buy_set_sell_parts,
            roi_pct=roi_pct,
            volume_48h=volume_48h,
            risk_level=risk_level,
        )

    return SetProfitResult(
        base_id=group.base_id,
        display_name=display,
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
        set_item_id=set_id or "",
        market_url=market_item_url(set_id or ""),
        part_details=part_details,
        set_seller=set_seller_summary,
        set_buyer=set_buyer_summary,
        trade_plan=trade_plan,
        best_cost=best_cost,
        best_revenue=best_revenue,
        roi_pct=roi_pct,
        liquidity_score=liquidity_score,
        risk_level=risk_level,
        risk_score=risk_score,
        opportunity_score=opportunity_score,
        supply_count=supply_count,
        demand_count=demand_count,
    )


def format_set_profit_results_for_model(
    results: list[SetProfitResult],
    *,
    min_profit: int,
    limit: int,
    max_items: int = 8,
) -> str:
    safe_max_items = max(0, max_items)
    lines = [
        f"metadata tool=set_profit min_profit={min_profit} limit={limit} result_count={len(results)}"
    ]

    for index, result in enumerate(results[:safe_max_items], 1):
        lines.append(
            "\t".join(
                [
                    f"row {index}",
                    f"base_id={_format_model_value(result.base_id)}",
                    f"display_name={_format_model_value(result.display_name)}",
                    f"best_strategy={_format_model_value(result.best_strategy)}",
                    f"best_profit={result.best_profit}",
                    f"profit_buy_parts_sell_set={result.profit_buy_parts_sell_set}",
                    f"profit_buy_set_sell_parts={result.profit_buy_set_sell_parts}",
                    f"set_buy_price={_format_model_value(result.set_buy_price)}",
                    f"set_sell_price={_format_model_value(result.set_sell_price)}",
                    f"parts_buy_total={result.parts_buy_total}",
                    f"parts_sell_total={result.parts_sell_total}",
                    f"part_count={result.part_count}",
                    f"volume_48h={_format_model_value(result.volume_48h)}",
                    f"best_cost={result.best_cost}",
                    f"best_revenue={result.best_revenue}",
                    f"roi_pct={result.roi_pct}",
                    f"liquidity_score={result.liquidity_score}",
                    f"risk_level={_format_model_value(result.risk_level)}",
                    f"risk_score={result.risk_score}",
                    f"opportunity_score={result.opportunity_score}",
                    f"supply_count={result.supply_count}",
                    f"demand_count={result.demand_count}",
                ]
            )
        )

    omitted_count = len(results) - safe_max_items
    if omitted_count > 0:
        lines.append(f"omitted_count={omitted_count}")
    return "\n".join(lines)



def _format_model_value(value: object) -> str:
    if value is None:
        return "null"
    return " ".join(str(value).split())



def scan_all_set_profits(
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    min_profit: int = 5,
    limit: int = 20,
    scout_fn: Callable[[list], list[str]] | None = None,
) -> list[SetProfitResult]:
    """扫描所有 Prime 套装，找出利润机会。"""
    groups = build_prime_groups(items)
    all_candidates = list(groups.values())[:15]

    # 智能预筛选
    if scout_fn is not None:
        try:
            scouted_ids = scout_fn(all_candidates)
            if scouted_ids:
                id_set = set(scouted_ids)
                candidates = [g for g in all_candidates if g.base_id in id_set]
                logger.info("Scout 预筛选: %d → %d 个套装", len(all_candidates), len(candidates))
            else:
                candidates = all_candidates
        except Exception as exc:
            logger.debug("Scout 预筛选失败，使用原始列表: %s", exc)
            candidates = all_candidates
    else:
        candidates = all_candidates

    def _analyze(group: PrimeGroup) -> SetProfitResult | None:
        try:
            return analyze_set_profit(group, order_fetcher)
        except Exception:
            return None

    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_analyze, g): g for g in candidates}
        for future in as_completed(futures):
            result = future.result()
            if result and result.best_profit >= min_profit:
                results.append(result)

    results.sort(key=lambda r: (r.opportunity_score, r.best_profit, r.roi_pct), reverse=True)
    return results[:limit]
