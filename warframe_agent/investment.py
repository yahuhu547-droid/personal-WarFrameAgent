"""投资顾问 — Prime 套装套利分析，按预算和 ROI 排序。"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from typing import Callable

logger = logging.getLogger(__name__)

from . import config
from .market import MarketOrder, best_buyers, best_sellers, fetch_item_statistics, fetch_orders
from .names import display_item_name, preferred_chinese_name
from .trade_plan import build_trade_plan, trade_step_from_order
from .warframes import PrimeGroup, build_prime_groups


@dataclass(frozen=True)
class PrimeInvestment:
    base_id: str
    display_name: str
    strategy: str           # "buy_parts_sell_set" 或 "buy_set_sell_parts"
    buy_cost: int           # 买入总成本
    sell_price: int         # 卖出收入
    profit_per_set: int     # 每套利润
    roi_pct: float          # ROI%
    sets_affordable: int    # 预算内可买几套
    total_profit: int       # 可买套数 × 每套利润
    volume_48h: int | None  # 48h 成交量
    risk_level: str         # "low" / "medium" / "high"
    part_details: list[dict]  # 各部件价格明细
    set_item_id: str        # 套装 item_id
    trade_plan: dict | None = None
    personal_score: float = 0.0
    personal_reasons: list[str] | None = None


_FIELD_SEPARATOR = " | "


def _format_model_value(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "/")


def format_prime_investment_results_for_model(
    results: list[PrimeInvestment],
    *,
    budget: int,
    min_roi_pct: float,
    limit: int,
    max_items: int = 8,
) -> str:
    lines = [
        " ".join([
            "tool=investment_advisor",
            f"budget={budget}",
            f"min_roi={min_roi_pct}",
            f"limit={limit}",
            f"result_count={len(results)}",
        ])
    ]

    shown_count = max(0, max_items)
    for index, result in enumerate(results[:shown_count], start=1):
        fields = [
            f"rank={index}",
            f"base_id={_format_model_value(result.base_id)}",
            f"display_name={_format_model_value(result.display_name)}",
            f"set_item_id={_format_model_value(result.set_item_id)}",
            f"strategy={_format_model_value(result.strategy)}",
            f"buy_cost={result.buy_cost}",
            f"sell_price={result.sell_price}",
            f"profit_per_set={result.profit_per_set}",
            f"roi_pct={result.roi_pct}",
            f"sets_affordable={result.sets_affordable}",
            f"total_profit={result.total_profit}",
            f"risk_level={_format_model_value(result.risk_level)}",
            f"volume_48h={result.volume_48h}",
            f"part_count={len(result.part_details)}",
            f"personal_score={result.personal_score}",
            f"personal_reasons={','.join(result.personal_reasons or [])}",
        ]
        lines.append(_FIELD_SEPARATOR.join(fields))

    omitted = len(results) - shown_count
    if omitted > 0:
        lines.append(f"omitted={omitted}")

    return "\n".join(lines)


def resolve_investment_preference_defaults(
    memory,
    *,
    budget: int | None,
    min_roi_pct: float | None,
    fallback_budget: int,
    fallback_min_roi_pct: float,
) -> tuple[int, float]:
    preferences = getattr(memory, "preferences", None)
    preference_budget = getattr(preferences, "budget_max", 0) or 0
    preference_roi = getattr(preferences, "min_roi_pct", 0) or 0
    resolved_budget = budget if budget is not None else (preference_budget or fallback_budget)
    resolved_min_roi = min_roi_pct if min_roi_pct is not None else (preference_roi or fallback_min_roi_pct)
    return max(0, int(resolved_budget)), max(0.0, float(resolved_min_roi))


def _assess_risk(volume_48h: int | None, supply_count: int, demand_count: int) -> str:
    """评估风险等级。"""
    vol = (volume_48h or 0) / 2  # 粗略日成交量
    ratio = supply_count / demand_count if demand_count > 0 else 999
    if vol >= 5 and ratio < 3:
        return "low"
    if vol >= 2 or ratio < 5:
        return "medium"
    return "high"


def _fetch_prices_parallel(
    item_ids: list[str],
    order_fetcher: Callable[[str], list[dict]],
    max_workers: int = 5,
) -> dict[str, list[dict]]:
    """并发获取多个物品的订单数据。"""
    results: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(order_fetcher, iid): iid for iid in item_ids}
        for future in as_completed(futures):
            iid = futures[future]
            try:
                results[iid] = future.result()
            except Exception as exc:
                logger.debug("获取 %s 订单失败: %s", iid, exc)
                results[iid] = []
    return results


# 部件后缀 -> 中文标签的映射（与 warframes.PARTS 保持一致）
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
    """获取部件的中文标签。"""
    return _PART_LABELS.get(part_key, part_key)


def analyze_prime_investment(
    group: PrimeGroup,
    order_fetcher: Callable[[str], list[dict]],
    budget: int = 500,
) -> PrimeInvestment | None:
    """分析单个 Prime 套装的套利机会。"""
    set_id = group.items.get("set")
    if not set_id:
        return None

    part_ids = [v for k, v in group.items.items() if k != "set"]
    if not part_ids:
        return None

    # 并发获取所有部件 + 套装的订单
    all_ids = part_ids + [set_id]
    all_orders = _fetch_prices_parallel(all_ids, order_fetcher)

    # 计算部件散买总价（取最低卖价）和散卖总价（取最高收价）
    parts_buy_total = 0
    parts_sell_total = 0
    parts_with_buy = 0
    parts_with_sell = 0
    part_details = []
    part_seller_orders: list[tuple[str, str, MarketOrder]] = []
    part_buyer_orders: list[tuple[str, str, MarketOrder]] = []
    all_supply = 0
    all_demand = 0

    for part_key, part_id in group.items.items():
        if part_key == "set":
            continue
        orders = all_orders.get(part_id, [])
        sellers = best_sellers(orders, limit=1)
        buyers = best_buyers(orders, limit=1)

        seller = sellers[0] if sellers else None
        buyer = buyers[0] if buyers else None
        buy_price = seller.platinum if seller else None
        sell_price = buyer.platinum if buyer else None
        if buy_price is not None and seller:
            parts_buy_total += buy_price
            parts_with_buy += 1
            part_seller_orders.append((part_key, part_id, seller))
        if sell_price is not None and buyer:
            parts_sell_total += sell_price
            parts_with_sell += 1
            part_buyer_orders.append((part_key, part_id, buyer))

        all_supply += sum(1 for o in orders if (o.get("order_type") or o.get("type")) == "sell")
        all_demand += sum(1 for o in orders if (o.get("order_type") or o.get("type")) == "buy")

        part_details.append({
            "key": part_key,
            "name": _part_label(part_key),
            "item_id": part_id,
            "buy": buy_price or 0,
            "sell": sell_price or 0,
        })

    # 套装价格
    set_orders = all_orders.get(set_id, [])
    set_sellers = best_sellers(set_orders, limit=1)
    set_buyers = best_buyers(set_orders, limit=1)

    set_seller = set_sellers[0] if set_sellers else None
    set_buyer = set_buyers[0] if set_buyers else None
    set_buy_price = set_seller.platinum if set_seller else None  # 买套装的成本
    set_sell_price = set_buyer.platinum if set_buyer else None   # 卖套装的收入

    all_supply += sum(1 for o in set_orders if (o.get("order_type") or o.get("type")) == "sell")
    all_demand += sum(1 for o in set_orders if (o.get("order_type") or o.get("type")) == "buy")

    # 策略 A: 散买部件 → 整套卖出
    profit_a = (
        set_sell_price - parts_buy_total
        if set_sell_price is not None and parts_with_buy == len(part_ids)
        else 0
    )
    # 策略 B: 整套买入 → 散卖部件
    profit_b = (
        parts_sell_total - set_buy_price
        if set_buy_price is not None and parts_with_sell == len(part_ids)
        else 0
    )

    if profit_a <= 0 and profit_b <= 0:
        return None

    # 选择更优策略
    if profit_a >= profit_b:
        strategy = "buy_parts_sell_set"
        buy_cost = parts_buy_total
        sell_price = set_sell_price
        profit = profit_a
    else:
        strategy = "buy_set_sell_parts"
        buy_cost = set_buy_price or 0
        sell_price = parts_sell_total
        profit = profit_b

    if buy_cost <= 0:
        return None

    roi_pct = (profit / buy_cost) * 100
    sets_affordable = budget // buy_cost if buy_cost > 0 else 0
    total_profit = sets_affordable * profit

    # 成交量和风险
    stats = fetch_item_statistics(set_id)
    volume_48h = stats.get("volume_48h") if stats else None
    risk_level = _assess_risk(volume_48h, all_supply, all_demand)

    display_name = preferred_chinese_name(set_id) or display_item_name(set_id)
    trade_plan = None
    if strategy == "buy_parts_sell_set" and set_buyer:
        buy_steps = [
            trade_step_from_order(
                side="buy",
                label=f"买入部件：{_part_label(part_key)}",
                item_id=part_id,
                order=order,
                quantity=1,
            )
            for part_key, part_id, order in part_seller_orders
        ]
        sell_steps = [trade_step_from_order(
            side="sell",
            label="出售整套",
            item_id=set_id,
            order=set_buyer,
            quantity=1,
        )]
        trade_plan = build_trade_plan(
            source="investment",
            strategy=strategy,
            display_strategy="买部件 -> 卖整套",
            item_id=set_id,
            display_name=display_name,
            required_quantity=len(buy_steps),
            buy_steps=buy_steps,
            sell_steps=sell_steps,
            total_cost=buy_cost,
            total_revenue=sell_price or 0,
            profit=profit,
            roi_pct=roi_pct,
            volume_48h=volume_48h,
            risk_level=risk_level,
        )
    elif strategy == "buy_set_sell_parts" and set_seller:
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
                item_id=part_id,
                order=order,
                quantity=1,
            )
            for part_key, part_id, order in part_buyer_orders
        ]
        trade_plan = build_trade_plan(
            source="investment",
            strategy=strategy,
            display_strategy="买整套 -> 卖部件",
            item_id=set_id,
            display_name=display_name,
            required_quantity=1,
            buy_steps=buy_steps,
            sell_steps=sell_steps,
            total_cost=buy_cost,
            total_revenue=sell_price or 0,
            profit=profit,
            roi_pct=roi_pct,
            volume_48h=volume_48h,
            risk_level=risk_level,
        )

    return PrimeInvestment(
        base_id=group.base_id,
        display_name=display_name,
        strategy=strategy,
        buy_cost=buy_cost,
        sell_price=sell_price,
        profit_per_set=profit,
        roi_pct=round(roi_pct, 1),
        sets_affordable=sets_affordable,
        total_profit=total_profit,
        volume_48h=volume_48h,
        risk_level=risk_level,
        part_details=part_details,
        set_item_id=set_id,
        trade_plan=trade_plan,
    )


def scan_prime_investments(
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    budget: int = 500,
    min_roi_pct: float = 10.0,
    limit: int = 30,
    scout_fn: Callable[[list], list[str]] | None = None,
    personal_profile=None,
) -> list[PrimeInvestment]:
    """扫描所有 Prime 套装，找出套利机会。"""
    groups = build_prime_groups(items)

    # 只保留战甲和武器套装
    all_candidates = []
    for group in groups.values():
        tags = group.tags
        if "warframe" in tags or "weapon" in tags:
            if "set" in group.items:
                all_candidates.append(group)

    # 智能预筛选
    if scout_fn is not None:
        try:
            scouted_ids = scout_fn(all_candidates)
            if scouted_ids:
                id_set = set(scouted_ids)
                candidates = [g for g in all_candidates if g.base_id in id_set]
                logger.info("Scout 预筛选: %d → %d 个投资候选", len(all_candidates), len(candidates))
            else:
                candidates = all_candidates
        except Exception as exc:
            logger.debug("Scout 预筛选失败，使用原始列表: %s", exc)
            candidates = all_candidates
    else:
        candidates = all_candidates

    results = []
    for group in candidates:
        try:
            result = analyze_prime_investment(group, order_fetcher, budget)
            if result and personal_profile is not None:
                from .personal_scoring import score_personal_fit

                fit = score_personal_fit(
                    item_id=result.set_item_id,
                    source="investment",
                    strategy=(result.trade_plan or {}).get("strategy", result.strategy),
                    total_cost=result.buy_cost,
                    profit=result.total_profit,
                    roi_pct=result.roi_pct,
                    risk_level=result.risk_level,
                    profile=personal_profile,
                )
                result = replace(result, personal_score=fit.personal_score, personal_reasons=fit.reasons)
            if result and result.roi_pct >= min_roi_pct:
                results.append(result)
        except Exception as exc:
            logger.debug("投资分析失败 %s: %s", group.base_id, exc)
            continue

    # 按 ROI% 降序排列
    results.sort(key=lambda r: r.roi_pct, reverse=True)
    if personal_profile is not None:
        results.sort(key=lambda r: (r.personal_score, r.total_profit, r.roi_pct), reverse=True)
    return results[:limit]
