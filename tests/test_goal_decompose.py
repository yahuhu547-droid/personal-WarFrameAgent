"""Tests for goal decomposition (earn_platinum)."""
from __future__ import annotations

from unittest.mock import MagicMock

from warframe_agent.goals import (
    GoalProgress,
    decompose_platinum_goal,
    track_goal_progress,
    create_goal,
    plan_for_goal,
    TradeOutcome,
)


# ── GoalProgress ──

def test_goal_progress_defaults():
    gp = GoalProgress(
        goal_id="g1", target_amount=100, current_amount=30,
        remaining=70, steps_completed=2, steps_total=5,
        estimated_completion="还需 70p",
    )
    assert gp.goal_id == "g1"
    assert gp.remaining == 70


# ── decompose_platinum_goal ──

def test_decompose_with_mock_scanners():
    """模拟扫描器返回，验证贪心选取逻辑。"""
    # Mock mod_flipper
    flip_result = MagicMock()
    flip_result.item_id = "mod_a"
    flip_result.display_name = "Mod A / R10"
    flip_result.flip_profit = 60
    flip_result.r0_buy_price = 20
    flip_result.r10_sell_price = 80
    flip_result.max_rank = 10

    # Mock set_profit
    set_result = MagicMock()
    set_result.set_item_id = "set_b"
    set_result.display_name = "Set B"
    set_result.best_profit = 40
    set_result.best_strategy = "拆件卖"
    set_result.parts_buy_total = 100

    # Mock investment
    invest_result = MagicMock()
    invest_result.set_item_id = "invest_c"
    invest_result.display_name = "Invest C"
    invest_result.total_profit = 30
    invest_result.roi_pct = 15.0
    invest_result.buy_cost = 200
    invest_result.strategy = "买套装拆卖"
    invest_result.risk_level = "medium"

    mock_items = [{"id": "test"}]

    # Patch scanners
    import warframe_agent.goals as goals_mod
    original_flip = goals_mod.scan_all_mod_flips
    original_set = goals_mod.scan_all_set_profits
    original_invest = goals_mod.scan_prime_investments

    goals_mod.scan_all_mod_flips = lambda *a, **k: [flip_result]
    goals_mod.scan_all_set_profits = lambda *a, **k: [set_result]
    goals_mod.scan_prime_investments = lambda *a, **k: [invest_result]

    try:
        steps = decompose_platinum_goal(target_amount=100, budget=500, items=mock_items)
        assert len(steps) >= 2
        # 第一步应该是利润最高的
        assert steps[0]["estimated_profit"] >= steps[1]["estimated_profit"]
        # 累计利润应达到目标
        total = sum(s["estimated_profit"] for s in steps)
        assert total >= 100
        # 步骤编号从 1 开始
        assert steps[0]["step"] == 1
    finally:
        goals_mod.scan_all_mod_flips = original_flip
        goals_mod.scan_all_set_profits = original_set
        goals_mod.scan_prime_investments = original_invest


def test_decompose_empty_results():
    """扫描器无结果时返回空列表。"""
    import warframe_agent.goals as goals_mod
    original_flip = goals_mod.scan_all_mod_flips
    original_set = goals_mod.scan_all_set_profits
    original_invest = goals_mod.scan_prime_investments

    goals_mod.scan_all_mod_flips = lambda *a, **k: []
    goals_mod.scan_all_set_profits = lambda *a, **k: []
    goals_mod.scan_prime_investments = lambda *a, **k: []

    try:
        steps = decompose_platinum_goal(target_amount=100, budget=500, items=[])
        assert len(steps) == 0
    finally:
        goals_mod.scan_all_mod_flips = original_flip
        goals_mod.scan_all_set_profits = original_set
        goals_mod.scan_prime_investments = original_invest


# ── track_goal_progress ──

def test_track_goal_progress_basic():
    outcomes = [
        TradeOutcome(
            outcome_id="o1", goal_id="g1", action="bought", item_id="x",
            price=50, expected_profit=30, actual_profit=25, user_feedback="good",
            timestamp="2026-05-01",
        ),
        TradeOutcome(
            outcome_id="o2", goal_id="g1", action="sold", item_id="y",
            price=80, expected_profit=40, actual_profit=35, user_feedback="good",
            timestamp="2026-05-02",
        ),
        TradeOutcome(
            outcome_id="o3", goal_id="g2", action="bought", item_id="z",
            price=100, expected_profit=50, actual_profit=0, user_feedback="ignored",
            timestamp="2026-05-03",
        ),
    ]
    progress = track_goal_progress("g1", 100, outcomes)
    assert progress.current_amount == 60  # 25 + 35
    assert progress.remaining == 40
    assert progress.steps_completed == 2
    assert progress.steps_total == 2


def test_track_goal_progress_achieved():
    outcomes = [
        TradeOutcome(
            outcome_id="o1", goal_id="g1", action="sold", item_id="x",
            price=200, expected_profit=100, actual_profit=150, user_feedback="good",
            timestamp="2026-05-01",
        ),
    ]
    progress = track_goal_progress("g1", 100, outcomes)
    assert progress.current_amount == 150
    assert progress.remaining == 0
    assert "已达成" in progress.estimated_completion


def test_track_goal_progress_no_outcomes():
    progress = track_goal_progress("g1", 100, [])
    assert progress.current_amount == 0
    assert progress.remaining == 100


# ── earn_platinum plan_for_goal ──

def test_plan_for_earn_platinum():
    goal = create_goal(
        goal_type="earn_platinum",
        description="攒 200 白金",
        criteria={"target_amount": 200, "budget": 500},
    )
    plan = plan_for_goal(goal)
    assert len(plan.steps) == 3
    actions = [s.action for s in plan.steps]
    assert "scan_mod_flip" in actions
    assert "scan_set_profit" in actions
    assert "scan_investment" in actions
