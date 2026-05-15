"""机会扫描器 — 后台检测价格异常和交易机会，主动推送。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from . import config
from .knowledge import MarketKnowledge
from .market import fetch_orders
from .memory import AgentMemory, ProactiveSuggestion
from .names import display_item_name
from .price_history import PriceHistoryDB

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Opportunity:
    item_id: str
    item_display: str
    opportunity_type: str  # "price_drop" | "low_listing" | "high_spread" | "trend_reversal"
    severity: str          # "high" | "medium" | "low"
    sell_price: int | None
    buy_price: int | None
    spread: int
    message: str
    suggested_action: str  # "buy" | "sell" | "watch"


class OpportunityScanner:
    """扫描价格异常和交易机会。"""

    def __init__(
        self,
        knowledge: MarketKnowledge | None = None,
        price_db: PriceHistoryDB | None = None,
        order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    ):
        self.knowledge = knowledge
        self.price_db = price_db
        self.order_fetcher = order_fetcher

    def scan_item(self, item_id: str) -> Opportunity | None:
        """扫描单个物品，检测是否有异常机会。"""
        try:
            orders = self.order_fetcher(item_id)
        except Exception:
            return None

        if not orders:
            return None

        from .market import best_buyers, best_sellers
        sellers = best_sellers(orders)
        buyers = best_buyers(orders)

        sell_price = sellers[0].platinum if sellers else None
        buy_price = buyers[0].platinum if buyers else None

        if sell_price is None or buy_price is None:
            return None

        spread = sell_price - buy_price
        spread_pct = (spread / max(buy_price, 1)) * 100

        # 检测 1: 高价差（>30%）
        if spread_pct > 30:
            return Opportunity(
                item_id=item_id,
                item_display=display_item_name(item_id),
                opportunity_type="high_spread",
                severity="high" if spread_pct > 50 else "medium",
                sell_price=sell_price,
                buy_price=buy_price,
                spread=spread,
                message=f"{display_item_name(item_id)} 价差 {spread}p ({spread_pct:.0f}%)，收 {buy_price}p 卖 {sell_price}p",
                suggested_action="buy",
            )

        # 检测 2: 知识库异常
        if self.knowledge:
            stats = self.knowledge.get_item_stats(item_id)
            if stats:
                # 低挂单检测（当前卖价低于滚动均价的 70%）
                if stats.rolling_avg_sell > 0 and sell_price < stats.rolling_avg_sell * 0.7:
                    return Opportunity(
                        item_id=item_id,
                        item_display=display_item_name(item_id),
                        opportunity_type="low_listing",
                        severity="high",
                        sell_price=sell_price,
                        buy_price=buy_price,
                        spread=spread,
                        message=f"{display_item_name(item_id)} 当前卖价 {sell_price}p 低于均价 {stats.rolling_avg_sell:.0f}p 的 70%",
                        suggested_action="buy",
                    )

                # 趋势反转检测（从下跌转为上涨）
                if stats.trend == "rising" and stats.volatility > 30:
                    return Opportunity(
                        item_id=item_id,
                        item_display=display_item_name(item_id),
                        opportunity_type="trend_reversal",
                        severity="medium",
                        sell_price=sell_price,
                        buy_price=buy_price,
                        spread=spread,
                        message=f"{display_item_name(item_id)} 趋势转涨，波动率 {stats.volatility:.0f}%，当前 {sell_price}p",
                        suggested_action="watch",
                    )

        # 检测 3: 价格历史异常
        if self.price_db:
            history = self.price_db.get_history(item_id, days=7)
            if len(history) >= 3:
                recent_avg = sum(h.get("sell", 0) for h in history[-3:]) / 3
                if recent_avg > 0 and sell_price < recent_avg * 0.6:
                    return Opportunity(
                        item_id=item_id,
                        item_display=display_item_name(item_id),
                        opportunity_type="price_drop",
                        severity="high",
                        sell_price=sell_price,
                        buy_price=buy_price,
                        spread=spread,
                        message=f"{display_item_name(item_id)} 7日均价 {recent_avg:.0f}p → 当前 {sell_price}p，跌幅 {(1-sell_price/recent_avg)*100:.0f}%",
                        suggested_action="buy",
                    )

        return None

    def scan_batch(self, item_ids: list[str]) -> list[Opportunity]:
        """批量扫描物品，返回所有发现的机会。"""
        opportunities = []
        for item_id in item_ids[:50]:  # 限制扫描数量
            opp = self.scan_item(item_id)
            if opp and opp.severity in ("high", "medium"):
                opportunities.append(opp)
        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        opportunities.sort(key=lambda o: severity_order.get(o.severity, 9))
        return opportunities

    def format_opportunities(self, opportunities: list[Opportunity]) -> str:
        """格式化机会列表为推送文本。"""
        if not opportunities:
            return ""
        lines = ["发现交易机会：\n"]
        for i, opp in enumerate(opportunities[:5], 1):
            action_text = {"buy": "建议买入", "sell": "建议卖出", "watch": "建议关注"}.get(opp.suggested_action, "")
            severity_icon = {"high": "!!", "medium": "!"}.get(opp.severity, "")
            lines.append(f"{severity_icon} {i}. {opp.message}")
            lines.append(f"   {action_text}")
        if len(opportunities) > 5:
            lines.append(f"\n还有 {len(opportunities) - 5} 个机会，使用 /scan 查看。")
        return "\n".join(lines)


def generate_opportunity_push_text(opportunities: list[Opportunity]) -> str:
    """生成 WxPusher 推送文本。"""
    if not opportunities:
        return ""
    lines = ["[机会发现] 以下物品出现异常：\n"]
    for opp in opportunities[:3]:
        lines.append(f"- {opp.message}")
    return "\n".join(lines)
