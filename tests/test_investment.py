"""测试投资顾问。"""
from __future__ import annotations

from warframe_agent.investment import (
    InvestmentFilter,
    InvestmentOpportunity,
    _assess_risk,
    analyze_investment,
)


def _mock_orders(profit=20, buy_price=30):
    sell_price = buy_price + profit
    return [
        {"order_type": "sell", "platinum": buy_price, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
        {"order_type": "sell", "platinum": buy_price + 5, "quantity": 1, "user": {"ingame_name": "s2", "status": "ingame", "reputation": 3}},
        {"order_type": "buy", "platinum": sell_price, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
        {"order_type": "buy", "platinum": sell_price - 3, "quantity": 1, "user": {"ingame_name": "b2", "status": "ingame", "reputation": 3}},
    ]


def test_analyze_single_item():
    filters = InvestmentFilter(budget=1000, min_roi_pct=10, min_profit=3)
    orders = _mock_orders(profit=20, buy_price=30)
    result = analyze_investment("test_item", orders, filters)
    assert result is not None
    assert result.buy_price == 30
    assert result.sell_price == 50
    assert result.profit == 20
    assert abs(result.roi_pct - 66.67) < 0.1
    assert result.supply_count == 2
    assert result.demand_count == 2


def test_budget_filter():
    filters = InvestmentFilter(budget=20, min_roi_pct=10, min_profit=3)
    orders = _mock_orders(profit=20, buy_price=30)
    result = analyze_investment("expensive_item", orders, filters)
    assert result is None  # buy_price=30 > budget=20


def test_min_roi_filter():
    filters = InvestmentFilter(budget=1000, min_roi_pct=80, min_profit=3)
    orders = _mock_orders(profit=20, buy_price=30)  # ROI = 66.67%
    result = analyze_investment("low_roi_item", orders, filters)
    assert result is None  # 66.67% < 80%


def test_min_profit_filter():
    filters = InvestmentFilter(budget=1000, min_roi_pct=10, min_profit=25)
    orders = _mock_orders(profit=20, buy_price=30)
    result = analyze_investment("low_profit_item", orders, filters)
    assert result is None  # profit=20 < min_profit=25


def test_risk_level_low():
    assert _assess_risk(daily_volume=10, supply_count=5, demand_count=5) == "low"


def test_risk_level_medium():
    assert _assess_risk(daily_volume=3, supply_count=10, demand_count=5) == "medium"


def test_risk_level_high():
    assert _assess_risk(daily_volume=0, supply_count=20, demand_count=2) == "high"


def test_no_orders():
    filters = InvestmentFilter()
    result = analyze_investment("empty_item", [], filters)
    assert result is None


def test_no_buy_orders():
    filters = InvestmentFilter()
    orders = [{"order_type": "sell", "platinum": 50, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}}]
    result = analyze_investment("sell_only", orders, filters)
    assert result is None
