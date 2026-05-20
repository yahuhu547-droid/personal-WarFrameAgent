"""Tests for rule engine (rules.py)."""
from __future__ import annotations

from unittest.mock import MagicMock

from warframe_agent.rules import (
    MarketState,
    AdaptiveThresholds,
    compute_thresholds,
    evaluate_market_state,
    generate_auto_goals,
    generate_proactive_message,
    decide_next_step,
    ProactivePush,
)
from warframe_agent.knowledge import CategoryHealth, MarketKnowledge, ItemKnowledge
from warframe_agent.memory import AgentMemory, ProactiveSuggestion, TradingPreferences
from warframe_agent.goals import AgentGoal, TradeOutcome


def _default_memory(**kwargs) -> AgentMemory:
    return AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
        **kwargs,
    )


# ── MarketState ──

def test_market_state_defaults():
    ms = MarketState()
    assert ms.trend_direction == "neutral"
    assert ms.volatility_index == 0.0


# ── evaluate_market_state ──

def test_evaluate_with_knowledge():
    items = {
        "a": ItemKnowledge(item_id="a", category="mod", subcategory="primed", trend="rising"),
        "b": ItemKnowledge(item_id="b", category="mod", subcategory="common", trend="rising"),
    }
    knowledge = MarketKnowledge(items=items)
    memory = _default_memory()
    price_db = MagicMock()
    trade_db = MagicMock()

    state = evaluate_market_state(price_db, trade_db, memory, knowledge)
    assert state.trend_direction == "bullish"
    assert state.activity_level == "low"  # only 2 items


def test_evaluate_without_knowledge():
    memory = _default_memory()
    price_db = MagicMock()
    trade_db = MagicMock()
    trade_db.get_recent_trades.return_value = [MagicMock()] * 25

    state = evaluate_market_state(price_db, trade_db, memory, None)
    assert state.activity_level == "high"
    assert state.trend_direction == "neutral"


# ── generate_auto_goals ──

def test_auto_goals_mod_high_roi():
    cat = {"mod": CategoryHealth(category="mod", avg_roi=150, opportunity_count=10)}
    state = MarketState(category_performance=cat)
    memory = _default_memory()

    goals = generate_auto_goals(state, memory)
    assert len(goals) >= 1
    assert any(g.goal_type == "flip_mod" for g in goals)


def test_auto_goals_deduplicates():
    existing = AgentGoal(
        goal_id="g1", goal_type="flip_mod", description="[自动] existing",
        target="mod_flip", criteria={}, status="active",
        created_at="2026-05-05", results=[],
    )
    cat = {"mod": CategoryHealth(category="mod", avg_roi=150)}
    state = MarketState(category_performance=cat)
    memory = _default_memory(active_goals=[existing])

    goals = generate_auto_goals(state, memory)
    assert not any(g.goal_type == "flip_mod" for g in goals)


def test_auto_goals_max_three():
    existing = [
        AgentGoal(goal_id=f"g{i}", goal_type=t, description=f"[自动] {i}",
                  target="all", criteria={}, status="active",
                  created_at="2026-05-05", results=[])
        for i, t in enumerate(["flip_mod", "build_set", "find_bargain"])
    ]
    state = MarketState()
    memory = _default_memory(active_goals=existing)

    goals = generate_auto_goals(state, memory)
    assert len(goals) == 0


def test_auto_goals_set_opportunities():
    cat = {"prime_set": CategoryHealth(category="prime_set", opportunity_count=8)}
    state = MarketState(category_performance=cat)
    memory = _default_memory()

    goals = generate_auto_goals(state, memory)
    assert any(g.goal_type == "build_set" for g in goals)


def test_auto_goals_bearish_anomaly():
    memory = _default_memory(recent_suggestions=[
        ProactiveSuggestion(item_id="x", suggestion_type="anomaly", priority=1, message="spike"),
    ])
    state = MarketState(anomaly_count=1, trend_direction="bearish")

    goals = generate_auto_goals(state, memory)
    assert any(g.goal_type == "maximize_profit" for g in goals)


def test_auto_goals_neutral_no_goals():
    state = MarketState()
    memory = _default_memory()

    goals = generate_auto_goals(state, memory)
    assert len(goals) == 0


# ── generate_proactive_message ──

def test_proactive_anomaly():
    suggestion = ProactiveSuggestion(
        item_id="arcane_energize", suggestion_type="anomaly",
        priority=1, message="arcane_energize 价格暴跌！当前 30p，均值 50p，偏差 -40%",
    )
    state = MarketState(volatility_index=20)

    push = generate_proactive_message(suggestion, state)
    assert push.item_id == "arcane_energize"
    assert push.push_type == "warning"
    assert push.priority == 1
    assert "暴跌" in push.message


def test_proactive_opportunity():
    suggestion = ProactiveSuggestion(
        item_id="test_item", suggestion_type="opportunity",
        priority=2, message="利润 50p",
    )
    state = MarketState()

    push = generate_proactive_message(suggestion, state)
    assert push.push_type == "opportunity"
    assert push.action_suggestion == "watch"


def test_proactive_opportunity_includes_rationale_and_dedupe_key():
    suggestion = ProactiveSuggestion(
        item_id="test_item",
        suggestion_type="opportunity",
        priority=2,
        message="利润 50p",
        data={"source": "spread", "rationale": "原因：价差超过阈值。", "profit": 50},
    )

    push = generate_proactive_message(suggestion, MarketState())

    assert "原因：价差超过阈值。" in push.message
    assert push.data["suggestion_type"] == "opportunity"
    assert push.data["source"] == "spread"
    assert push.data["profit"] == 50
    assert push.data["rationale"] == "原因：价差超过阈值。"
    assert push.data["dedupe_key"] == "opportunity:opportunity:test_item:spread"


def test_proactive_with_event_context():
    suggestion = ProactiveSuggestion(
        item_id="test_item", suggestion_type="anomaly",
        priority=1, message="test_item 价格暴跌！",
    )
    items = {"test_item": ItemKnowledge(item_id="test_item", category="mod", subcategory="primed", event_context="Baro 访问中")}
    knowledge = MarketKnowledge(items=items)
    state = MarketState(volatility_index=20)

    push = generate_proactive_message(suggestion, state, knowledge)
    assert "Baro" in push.message


def test_proactive_high_volatility():
    suggestion = ProactiveSuggestion(
        item_id="test", suggestion_type="anomaly",
        priority=1, message="test 价格暴涨！",
    )
    state = MarketState(volatility_index=60)

    push = generate_proactive_message(suggestion, state)
    assert push.action_suggestion == "watch"  # high vol → watch


# ── decide_next_step ──

def test_decide_max_iteration():
    action, params = decide_next_step(MagicMock(), [], [], 3, max_iter=3)
    assert action == "stop"


def test_decide_empty_results_different_scanner():
    goal = MagicMock()
    action, params = decide_next_step(goal, [], ["scan_mod_flip"], 0, max_iter=3)
    assert action in ("scan_set_profit", "scan_investment")


def test_decide_empty_results_all_tried():
    action, params = decide_next_step(
        MagicMock(), [], ["scan_mod_flip", "scan_set_profit", "scan_investment"], 0, max_iter=3
    )
    assert action == "stop"


def test_decide_high_roi_stop():
    results = [{"roi_pct": 600, "item_id": "x"}]
    action, params = decide_next_step(MagicMock(), results, [], 0, max_iter=3)
    assert action == "stop"


def test_decide_medium_roi_try_set():
    results = [{"roi_pct": 150, "item_id": "x"}]
    action, params = decide_next_step(MagicMock(), results, [], 0, max_iter=3)
    assert action == "scan_set_profit"


def test_decide_low_roi_try_mod():
    results = [{"roi_pct": 30, "item_id": "x"}]
    action, params = decide_next_step(MagicMock(), results, [], 0, max_iter=3)
    assert action == "scan_mod_flip"


def test_decide_no_new_scanner_stop():
    results = [{"roi_pct": 30, "item_id": "x"}]
    action, params = decide_next_step(
        MagicMock(), results, ["scan_mod_flip", "scan_set_profit", "scan_investment"], 0, max_iter=3
    )
    assert action == "stop"


# ── Feedback integration ──

def _outcome(actual_profit, expected_profit=20, goal_id="goal_mod_1", oid="o1"):
    return TradeOutcome(
        outcome_id=oid, goal_id=goal_id, action="bought", item_id="x",
        price=100, expected_profit=expected_profit, actual_profit=actual_profit,
        user_feedback="good", timestamp="2025-01-01T00:00:00",
    )


def test_auto_goals_blocked_by_feedback():
    """策略被反馈屏蔽时不应生成目标。"""
    # mod_flip 亏损严重 → 被屏蔽
    outcomes = [_outcome(-10, 20, f"goal_mod_{i}", f"o{i}") for i in range(6)]
    mod_health = CategoryHealth(category="mod", opportunity_count=0, avg_roi=150, avg_profit=10, trend="bullish", top_items=[])
    cat = {"mod": mod_health}
    state = MarketState(category_performance=cat)
    memory = _default_memory()

    goals = generate_auto_goals(state, memory, trade_outcomes=outcomes)
    types = {g.goal_type for g in goals}
    assert "flip_mod" not in types


def test_auto_goals_not_blocked_small_sample():
    """样本不足时不应屏蔽。"""
    outcomes = [_outcome(-10, 20, f"goal_mod_{i}", f"o{i}") for i in range(2)]
    mod_health = CategoryHealth(category="mod", opportunity_count=0, avg_roi=150, avg_profit=10, trend="bullish", top_items=[])
    cat = {"mod": mod_health}
    state = MarketState(category_performance=cat)
    memory = _default_memory()

    goals = generate_auto_goals(state, memory, trade_outcomes=outcomes)
    types = {g.goal_type for g in goals}
    assert "flip_mod" in types


def test_decide_switch_strategy_low_win_rate():
    """策略历史胜率 < 20% 且样本 >= 3 → 换策略。"""
    outcomes = [_outcome(-10, 20, f"goal_mod_{i}", f"o{i}") for i in range(3)]
    action, params = decide_next_step(
        MagicMock(), [{"roi_pct": 80}], ["scan_mod_flip"], 0, max_iter=3,
        trade_outcomes=outcomes,
    )
    assert action == "switch_strategy"
    assert params["reason"] == "low_win_rate"


def test_decide_no_switch_good_strategy():
    """策略表现好时不应换。"""
    outcomes = [_outcome(10, 20, f"goal_mod_{i}", f"o{i}") for i in range(3)]
    action, params = decide_next_step(
        MagicMock(), [{"roi_pct": 80}], ["scan_mod_flip"], 0, max_iter=3,
        trade_outcomes=outcomes,
    )
    # 胜率 > 0.2 → 不换策略，继续决策树
    assert action != "switch_strategy"


# ── AdaptiveThresholds ──

def test_compute_thresholds_no_knowledge():
    """无知识库时返回保守默认值。"""
    t = compute_thresholds(None)
    assert t.roi_good == 30
    assert t.roi_excellent == 50
    assert t.volatility_high == 50
    assert t.min_profit == 5


def test_compute_thresholds_with_knowledge():
    """有知识库时阈值自适应。"""
    items = {
        "a": ItemKnowledge(item_id="a", category="mod", subcategory="common",
                           rolling_avg_sell=10, rolling_avg_buy=5, volatility=60,
                           trend="rising", volume_trend="stable", last_updated="", scan_count=5),
    }
    knowledge = MarketKnowledge(items=items)
    t = compute_thresholds(knowledge)
    # avg_roi from category health = avg_volatility = 60
    # roi_good = max(20, 60 * 1.2) = 72
    assert t.roi_good >= 20
    assert t.volatility_high >= 30


def test_auto_goals_use_adaptive_thresholds():
    """generate_auto_goals 使用自适应阈值。"""
    # 高 ROI 市场：avg_roi = 200
    mod_health = CategoryHealth(category="mod", opportunity_count=0, avg_roi=200, avg_profit=10, trend="bullish", top_items=[])
    cat = {"mod": mod_health}
    state = MarketState(category_performance=cat)
    memory = _default_memory()

    # 阈值应该 >= 200 * 1.2 = 240，但 mod_health.avg_roi = 200 < 240 → 不生成目标
    items = {
        "x": ItemKnowledge(item_id="x", category="mod", subcategory="common",
                           rolling_avg_sell=10, rolling_avg_buy=5, volatility=40,
                           trend="rising", volume_trend="stable", last_updated="", scan_count=5),
    }
    knowledge = MarketKnowledge(items=items)
    goals = generate_auto_goals(state, memory, knowledge)
    # 200 < roi_good (which is max(20, 40*1.2) = 48) → 200 > 48 → should generate
    # Actually: avg_roi from cat_health is 200, thresholds.roi_good = max(20, 40*1.2) = 48
    # 200 > 48 → should generate
    types = {g.goal_type for g in goals}
    assert "flip_mod" in types
