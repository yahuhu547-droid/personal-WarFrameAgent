"""Phase 35: Adaptive Intelligence E2E functional tests."""
from __future__ import annotations

from warframe_agent.chat import build_system_context
from warframe_agent.feedback import FeedbackAnalyzer
from warframe_agent.goals import TradeOutcome
from warframe_agent.knowledge import ItemKnowledge, MarketKnowledge
from warframe_agent.memory import AgentMemory, TradingPreferences
from warframe_agent.rules import _is_strategy_blocked, compute_thresholds


class FakeEvent:
    def __init__(self, items_affected, impact, event_type="", description=""):
        self.items_affected = items_affected
        self.impact = impact
        self.event_type = event_type
        self.description = description


class FakePriceDB:
    def recent(self, *a, **k):
        return []

    def predict_trend(self, *a, **k):
        return None


# ── Feedback Loop ──

def test_feedback_loop_strategies():
    outcomes = [
        TradeOutcome(outcome_id="o1", goal_id="flip_mod", action="bought", item_id="serration", price=10, expected_profit=20, actual_profit=15, user_feedback="good", timestamp="2025-01-01T00:00:00"),
        TradeOutcome(outcome_id="o2", goal_id="flip_mod", action="bought", item_id="vitality", price=5, expected_profit=10, actual_profit=8, user_feedback="good", timestamp="2025-01-02T00:00:00"),
        TradeOutcome(outcome_id="o3", goal_id="flip_mod", action="bought", item_id="flow", price=8, expected_profit=15, actual_profit=-3, user_feedback="bad", timestamp="2025-01-03T00:00:00"),
        TradeOutcome(outcome_id="o4", goal_id="build_set", action="bought", item_id="intensify", price=12, expected_profit=25, actual_profit=30, user_feedback="good", timestamp="2025-01-04T00:00:00"),
        TradeOutcome(outcome_id="o5", goal_id="build_set", action="bought", item_id="stretch", price=3, expected_profit=8, actual_profit=6, user_feedback="good", timestamp="2025-01-05T00:00:00"),
    ]
    strategies = FeedbackAnalyzer().analyze_strategies(outcomes)
    assert len(strategies) == 2
    mod_flip = next((s for s in strategies if s.strategy == "mod_flip"), None)
    assert mod_flip is not None
    assert abs(mod_flip.win_rate - 2 / 3) < 0.01  # 2 wins out of 3
    assert mod_flip.sample_size == 3
    assert mod_flip.confidence == "medium"


def test_feedback_blocks_bad_strategy():
    outcomes = [
        TradeOutcome(outcome_id=f"o{i}", goal_id="flip_mod", action="bought", item_id="x", price=10, expected_profit=10, actual_profit=-5, user_feedback="bad", timestamp=f"2025-01-0{i}T00:00:00")
        for i in range(1, 6)
    ]
    assert _is_strategy_blocked("mod_flip", outcomes) is True  # 0% win rate, 5 samples


def test_feedback_items():
    outcomes = [
        TradeOutcome(outcome_id="o1", goal_id="g1", action="bought", item_id="serration", price=10, expected_profit=20, actual_profit=15, user_feedback="good", timestamp="2025-01-01T00:00:00"),
        TradeOutcome(outcome_id="o2", goal_id="g1", action="bought", item_id="serration", price=12, expected_profit=18, actual_profit=10, user_feedback="good", timestamp="2025-01-02T00:00:00"),
    ]
    items = FeedbackAnalyzer().analyze_items(outcomes)
    assert len(items) == 1
    assert items[0].item_id == "serration"
    assert items[0].times_traded == 2
    assert items[0].win_rate == 1.0


# ── Adaptive Thresholds ──

def test_adaptive_thresholds_no_knowledge():
    t = compute_thresholds(None)
    assert t.roi_good == 30
    assert t.roi_excellent == 50
    assert t.volatility_high == 50
    assert t.min_profit == 5


def test_adaptive_thresholds_with_knowledge():
    items = {
        "a": ItemKnowledge(item_id="a", category="mod", subcategory="common", rolling_avg_sell=100, rolling_avg_buy=50, volatility=30, trend="rising", scan_count=5),
        "b": ItemKnowledge(item_id="b", category="mod", subcategory="common", rolling_avg_sell=200, rolling_avg_buy=150, volatility=40, trend="stable", scan_count=3),
    }
    knowledge = MarketKnowledge(items=items)
    t = compute_thresholds(knowledge)
    # avg_roi = avg(volatility) = 35, avg_profit = avg(spread) = 75/2 = 37.5
    assert t.roi_good > 30  # 35 * 1.2 = 42
    assert t.min_profit > 5  # 37.5 * 0.8 = 30


# ── Chat Context ──

def test_chat_context_includes_market_info():
    items = {
        "serration": ItemKnowledge(item_id="serration", category="mod", subcategory="common", rolling_avg_sell=10, rolling_avg_buy=5, volatility=20, trend="rising", scan_count=5),
        "arcane_energize": ItemKnowledge(item_id="arcane_energize", category="arcane", subcategory="arcane", rolling_avg_sell=100, rolling_avg_buy=80, volatility=25, trend="rising", scan_count=10),
    }
    knowledge = MarketKnowledge(items=items)
    memory = AgentMemory(preferences=TradingPreferences(), price_alerts=[], favorite_items=["arcane_energize"], common_questions=[], watchlist=[])
    ctx = build_system_context(knowledge=knowledge, memory=memory)
    assert "市场概况" in ctx
    assert "跟踪物品" in ctx
    assert "热门" in ctx


def test_chat_context_empty():
    ctx = build_system_context()
    assert ctx == ""


def test_chat_context_with_trade_outcomes():
    from warframe_agent.goals import TradeOutcome
    memory = AgentMemory(
        preferences=TradingPreferences(), price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
        trade_outcomes=[
            TradeOutcome(outcome_id="o1", goal_id="g1", action="bought", item_id="x", price=10, expected_profit=20, actual_profit=15, user_feedback="good", timestamp="2025-01-01T00:00:00"),
        ],
    )
    ctx = build_system_context(memory=memory)
    assert "交易统计" in ctx
    assert "1/1" in ctx


# ── Event Intelligence ──

def test_predict_with_positive_event():
    items = {
        "serration": ItemKnowledge(item_id="serration", category="mod", subcategory="common", trend="stable", scan_count=5),
    }
    knowledge = MarketKnowledge(items=items)
    events = [FakeEvent(items_affected=["serration"], impact="positive")]
    assert knowledge.predict_with_events("serration", events) == "rising"


def test_predict_with_negative_event():
    items = {
        "serration": ItemKnowledge(item_id="serration", category="mod", subcategory="common", trend="stable", scan_count=5),
    }
    knowledge = MarketKnowledge(items=items)
    events = [FakeEvent(items_affected=["serration"], impact="negative")]
    assert knowledge.predict_with_events("serration", events) == "falling"


def test_predict_low_scan_count():
    items = {
        "new_item": ItemKnowledge(item_id="new_item", category="mod", subcategory="common", trend="rising", scan_count=1),
    }
    knowledge = MarketKnowledge(items=items)
    assert knowledge.predict_with_events("new_item", None) == "insufficient_data"


def test_predict_unknown_item():
    knowledge = MarketKnowledge()
    assert knowledge.predict_with_events("unknown", []) == "insufficient_data"


def test_event_context_injection():
    items = {
        "arcane_energize": ItemKnowledge(item_id="arcane_energize", category="arcane", subcategory="arcane", scan_count=10),
    }
    knowledge = MarketKnowledge(items=items)
    events = [FakeEvent(items_affected=["arcane_energize"], impact="positive", event_type="baro_visit", description="Baro visiting")]
    knowledge.update_from_scan([{"item_id": "arcane_energize"}], FakePriceDB(), events=events)
    stats = knowledge.get_item_stats("arcane_energize")
    assert stats.event_context is not None
    assert "baro_visit" in stats.event_context


# ── Volume Trend ──

def test_volume_trend_computed():
    """volume_trend should be computed from snapshot count, not hardcoded."""
    from unittest.mock import MagicMock
    snapshot = MagicMock()
    snapshot.sell_price = 100
    snapshot.buy_price = 80
    price_db = MagicMock()
    price_db.recent.return_value = [snapshot] * 8  # 8 snapshots = increasing
    price_db.predict_trend.return_value = None

    knowledge = MarketKnowledge()
    knowledge.update_from_scan([{"item_id": "test_item"}], price_db)
    stats = knowledge.get_item_stats("test_item")
    assert stats.volume_trend == "increasing"


def test_volume_trend_stable():
    from unittest.mock import MagicMock
    snapshot = MagicMock()
    snapshot.sell_price = 100
    snapshot.buy_price = 80
    price_db = MagicMock()
    price_db.recent.return_value = [snapshot] * 4  # 4 snapshots = stable
    price_db.predict_trend.return_value = None

    knowledge = MarketKnowledge()
    knowledge.update_from_scan([{"item_id": "test_item"}], price_db)
    stats = knowledge.get_item_stats("test_item")
    assert stats.volume_trend == "stable"


def test_volume_trend_decreasing():
    from unittest.mock import MagicMock
    snapshot = MagicMock()
    snapshot.sell_price = 100
    snapshot.buy_price = 80
    price_db = MagicMock()
    price_db.recent.return_value = [snapshot] * 2  # 2 snapshots = decreasing
    price_db.predict_trend.return_value = None

    knowledge = MarketKnowledge()
    knowledge.update_from_scan([{"item_id": "test_item"}], price_db)
    stats = knowledge.get_item_stats("test_item")
    assert stats.volume_trend == "decreasing"


# ── CategoryHealth avg_profit ──

def test_category_health_avg_profit():
    items = {
        "a": ItemKnowledge(item_id="a", category="mod", subcategory="common", rolling_avg_sell=100, rolling_avg_buy=60),
        "b": ItemKnowledge(item_id="b", category="mod", subcategory="common", rolling_avg_sell=50, rolling_avg_buy=30),
    }
    knowledge = MarketKnowledge(items=items)
    health = knowledge.get_category_health("mod")
    # spread_a = 40, spread_b = 20, avg = 30
    assert health.avg_profit == 30.0


def test_category_health_avg_profit_no_data():
    items = {
        "a": ItemKnowledge(item_id="a", category="mod", subcategory="common"),  # no prices
    }
    knowledge = MarketKnowledge(items=items)
    health = knowledge.get_category_health("mod")
    assert health.avg_profit == 0
