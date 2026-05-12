"""Baro Ki'Teer 库存分析器 — 评估哪些物品值得从 Baro 购买。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .events import BaroItem, GameEvent
from .market import best_sellers, fetch_orders


# 杜卡特→白金的隐含汇率阈值
# 如果 市场价 > 杜卡特/3，说明从 Baro 买更划算
DUCAT_TO_PLAT_RATIO = 3


@dataclass(frozen=True)
class BaroRecommendation:
    item_name: str
    market_id: str
    ducat_cost: int
    credit_cost: int
    market_plat_price: int | None  # 市场最低卖价，None 表示不可交易
    recommendation: str            # "buy" / "skip" / "consider"
    reason: str


def analyze_baro_inventory(
    baro_event: GameEvent,
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
) -> list[BaroRecommendation]:
    """分析 Baro 库存，返回每个物品的购买建议。"""
    recommendations: list[BaroRecommendation] = []

    for item in baro_event.baro_items:
        if not item.market_id:
            # 不可交易物品，只能从 Baro 获取
            recommendations.append(BaroRecommendation(
                item_name=item.item_name,
                market_id="",
                ducat_cost=item.ducat_cost,
                credit_cost=item.credit_cost,
                market_plat_price=None,
                recommendation="buy",
                reason="非交易物品，只能从 Baro 获取",
            ))
            continue

        try:
            orders = order_fetcher(item.market_id)
            sellers = best_sellers(orders, limit=1, rank_filter=0)
            if sellers:
                plat_price = sellers[0].platinum
            else:
                plat_price = None
        except Exception:
            plat_price = None

        if plat_price is None:
            recommendations.append(BaroRecommendation(
                item_name=item.item_name,
                market_id=item.market_id,
                ducat_cost=item.ducat_cost,
                credit_cost=item.credit_cost,
                market_plat_price=None,
                recommendation="consider",
                reason="无法获取市场价",
            ))
            continue

        if item.ducat_cost == 0:
            recommendations.append(BaroRecommendation(
                item_name=item.item_name,
                market_id=item.market_id,
                ducat_cost=0,
                credit_cost=item.credit_cost,
                market_plat_price=plat_price,
                recommendation="consider",
                reason=f"仅需 {item.credit_cost:,} 现金，市场价 {plat_price}p",
            ))
            continue

        implied_plat = item.ducat_cost / DUCAT_TO_PLAT_RATIO
        if plat_price > implied_plat:
            recommendations.append(BaroRecommendation(
                item_name=item.item_name,
                market_id=item.market_id,
                ducat_cost=item.ducat_cost,
                credit_cost=item.credit_cost,
                market_plat_price=plat_price,
                recommendation="buy",
                reason=f"市场价 {plat_price}p > Baro 隐含价 {implied_plat:.0f}p（{item.ducat_cost} 杜卡特÷{DUCAT_TO_PLAT_RATIO}），Baro 更划算",
            ))
        else:
            recommendations.append(BaroRecommendation(
                item_name=item.item_name,
                market_id=item.market_id,
                ducat_cost=item.ducat_cost,
                credit_cost=item.credit_cost,
                market_plat_price=plat_price,
                recommendation="skip",
                reason=f"市场价 {plat_price}p ≤ Baro 隐含价 {implied_plat:.0f}p，市场更便宜",
            ))

    # 排序：buy > consider > skip
    priority = {"buy": 0, "consider": 1, "skip": 2}
    recommendations.sort(key=lambda r: (priority.get(r.recommendation, 9), -r.ducat_cost))
    return recommendations


def format_baro_report(recommendations: list[BaroRecommendation]) -> str:
    """格式化 Baro 推荐报告。"""
    if not recommendations:
        return "Baro 库存为空或无法分析"

    lines = ["## Baro Ki'Teer 购买建议\n"]

    groups = {"buy": [], "consider": [], "skip": []}
    for r in recommendations:
        groups[r.recommendation].append(r)

    if groups["buy"]:
        lines.append("### 值得买")
        for r in groups["buy"]:
            ducat_str = f"{r.ducat_cost} 杜卡特" if r.ducat_cost else ""
            credit_str = f"{r.credit_cost:,} 现金" if r.credit_cost else ""
            cost_str = " + ".join(filter(None, [ducat_str, credit_str]))
            plat_str = f"（市场价 {r.market_plat_price}p）" if r.market_plat_price else ""
            lines.append(f"- **{r.item_name}** — {cost_str}{plat_str}")
            lines.append(f"  {r.reason}")

    if groups["consider"]:
        lines.append("\n### 可考虑")
        for r in groups["consider"]:
            ducat_str = f"{r.ducat_cost} 杜卡特" if r.ducat_cost else ""
            credit_str = f"{r.credit_cost:,} 现金" if r.credit_cost else ""
            cost_str = " + ".join(filter(None, [ducat_str, credit_str]))
            lines.append(f"- **{r.item_name}** — {cost_str}")
            lines.append(f"  {r.reason}")

    if groups["skip"]:
        lines.append("\n### 不推荐（市场更便宜）")
        for r in groups["skip"]:
            ducat_str = f"{r.ducat_cost} 杜卡特" if r.ducat_cost else ""
            credit_str = f"{r.credit_cost:,} 现金" if r.credit_cost else ""
            cost_str = " + ".join(filter(None, [ducat_str, credit_str]))
            lines.append(f"- **{r.item_name}** — {cost_str}（市场价 {r.market_plat_price}p）")

    return "\n".join(lines)
