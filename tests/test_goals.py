"""测试目标引擎 — Agent 目标、执行计划、反馈学习。"""
from __future__ import annotations

from unittest.mock import patch

from warframe_agent.goals import (
    AgentGoal,
    ExecutionStep,
    GoalExecutionPlan,
    TradeOutcome,
    calculate_opportunity_score,
    create_goal,
    execute_plan,
    format_goal_criteria_summary,
    plan_for_goal,
    parse_goal_description_criteria,
    record_trade_outcome,
)
from warframe_agent.memory import AgentMemory
from warframe_agent.set_profit import SetProfitResult


# ── 目标创建 ──────────────────────────────────────────────

def test_create_goal_basic():
    goal = create_goal("maximize_profit", "找高利润机会", "prime_sets", {"budget": 500})
    assert goal.goal_type == "maximize_profit"
    assert goal.description == "找高利润机会"
    assert goal.target == "prime_sets"
    assert goal.criteria == {"budget": 500}
    assert goal.status == "active"
    assert len(goal.goal_id) == 12
    assert goal.created_at  # 非空时间戳
    assert goal.results == []


def test_create_goal_defaults():
    goal = create_goal("flip_mod", "翻转 Mod")
    assert goal.target == "all"
    assert goal.criteria == {}


def test_parse_goal_description_criteria_supports_chinese_numerals_and_defaults():
    criteria = parse_goal_description_criteria("一个月攒五百白金，预算三百，稳健，ROI二十%")

    assert criteria["target_profit"] == 500
    assert criteria["target_amount"] == 500
    assert criteria["timeframe_days"] == 30
    assert criteria["budget"] == 300
    assert criteria["risk"] == "low"
    assert criteria["min_roi"] == 20


def test_parse_goal_description_criteria_supports_risk_aliases_and_summary():
    criteria = parse_goal_description_criteria("三天赚100p，激进，至少30% ROI")

    assert criteria["target_profit"] == 100
    assert criteria["timeframe_days"] == 3
    assert criteria["risk"] == "high"
    assert criteria["min_roi"] == 30
    assert criteria["budget"] == 500
    assert format_goal_criteria_summary(criteria) == "目标利润 100p；周期 3 天；预算 500p；高风险；最低 ROI 30%"


# ── 计划生成 ──────────────────────────────────────────────

def test_plan_for_maximize_profit():
    goal = create_goal("maximize_profit", "最大化利润", criteria={"budget": 1000, "min_roi": 50})
    plan = plan_for_goal(goal)
    assert plan.goal_id == goal.goal_id
    assert len(plan.steps) == 4
    actions = [s.action for s in plan.steps]
    assert actions == ["scan_mod_flip", "scan_set_profit", "scan_investment", "rank_results"]


def test_plan_for_flip_mod():
    goal = create_goal("flip_mod", "Mod 翻转", criteria={"min_roi": 100})
    plan = plan_for_goal(goal)
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "scan_mod_flip"
    assert plan.steps[0].params["min_roi_pct"] == 100


def test_plan_for_build_set():
    goal = create_goal("build_set", "凑套装", criteria={"budget": 300})
    plan = plan_for_goal(goal)
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "scan_investment"
    assert plan.steps[0].params["budget"] == 300


def test_plan_for_find_bargain():
    goal = create_goal("find_bargain", "找便宜货")
    plan = plan_for_goal(goal)
    assert len(plan.steps) == 2
    assert plan.steps[0].action == "scan_investment"
    assert plan.steps[1].action == "scan_mod_flip"


def test_plan_for_unknown_type():
    goal = create_goal("unknown", "未知类型")
    plan = plan_for_goal(goal)
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "scan_investment"


# ── 计划执行 ──────────────────────────────────────────────

def _mock_order_fetcher(item_id):
    """Mock 订单获取器。"""
    return [
        {"order_type": "sell", "platinum": 10, "quantity": 1,
         "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
        {"order_type": "buy", "platinum": 20, "quantity": 1,
         "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
    ]


@patch("warframe_agent.goals.scan_all_mod_flips", return_value=[])
@patch("warframe_agent.goals.scan_all_set_profits", return_value=[])
@patch("warframe_agent.goals.scan_prime_investments", return_value=[])
def test_execute_plan_empty(mock_inv, mock_set, mock_mod):
    goal = create_goal("maximize_profit", "测试")
    plan = plan_for_goal(goal)
    results = execute_plan(plan, [], _mock_order_fetcher)
    assert results == []


@patch("warframe_agent.goals.scan_all_mod_flips", return_value=[])
@patch("warframe_agent.goals.scan_all_set_profits")
@patch("warframe_agent.goals.scan_prime_investments", return_value=[])
def test_execute_plan_set_profit_uses_base_id(mock_inv, mock_set, mock_mod):
    mock_set.return_value = [
        SetProfitResult(
            base_id="rhino_prime",
            display_name="Rhino Prime",
            set_buy_price=80,
            parts_sell_total=70,
            set_sell_price=70,
            parts_buy_total=55,
            profit_buy_parts_sell_set=15,
            profit_buy_set_sell_parts=-10,
            best_strategy="买部件→卖套装",
            best_profit=15,
            volume_48h=12,
            part_count=4,
        ),
    ]
    goal = create_goal("maximize_profit", "测试")
    plan = plan_for_goal(goal)

    results = execute_plan(plan, [], _mock_order_fetcher)

    assert any(r["source"] == "set_profit" and r["item_id"] == "rhino_prime" for r in results)


# ── 反馈学习 ──────────────────────────────────────────────

def test_opportunity_score_no_feedback():
    opp = {"roi_pct": 100, "source": "mod_flip"}
    score = calculate_opportunity_score(opp, [])
    assert score == 100


def test_opportunity_score_good_feedback():
    opp = {"roi_pct": 100, "source": "mod_flip"}
    outcomes = [
        TradeOutcome("1", "g1", "bought", "primed_flow", 50, 100, 80, "good", "2025-01-01"),
        TradeOutcome("2", "g1", "bought", "primed_continuity", 60, 120, 100, "good", "2025-01-02"),
        TradeOutcome("3", "g1", "bought", "some_mod", 30, 50, 40, "good", "2025-01-03"),
    ]
    score = calculate_opportunity_score(opp, outcomes)
    # good_rate = 3/3 = 1.0 > 0.7 → 100 * 1.2 = 120
    assert score == 120


def test_opportunity_score_bad_feedback():
    opp = {"roi_pct": 100, "source": "mod_flip"}
    outcomes = [
        TradeOutcome("1", "g1", "bought", "primed_flow", 50, 100, 80, "bad", "2025-01-01"),
        TradeOutcome("2", "g1", "bought", "primed_continuity", 60, 120, 100, "bad", "2025-01-02"),
        TradeOutcome("3", "g1", "bought", "some_mod", 30, 50, 40, "bad", "2025-01-03"),
    ]
    score = calculate_opportunity_score(opp, outcomes)
    # good_rate = 0/3 = 0 < 0.3 → 100 * 0.7 = 70
    assert score == 70


def test_opportunity_score_neutral_feedback():
    opp = {"roi_pct": 100, "source": "set_profit"}
    outcomes = [
        TradeOutcome("1", "g1", "bought", "atlas_prime_set", 100, 200, 180, "good", "2025-01-01"),
        TradeOutcome("2", "g1", "bought", "volt_prime_set", 80, 150, 120, "bad", "2025-01-02"),
    ]
    score = calculate_opportunity_score(opp, outcomes)
    # good_rate = 0.5 → 保持原分
    assert score == 100


# ── 交易结果记录 ──────────────────────────────────────────

def test_record_trade_outcome():
    outcome = record_trade_outcome(
        goal_id="g123",
        action="bought",
        item_id="primed_flow",
        price=50,
        expected_profit=100,
        actual_profit=80,
        user_feedback="good",
    )
    assert outcome.goal_id == "g123"
    assert outcome.action == "bought"
    assert outcome.item_id == "primed_flow"
    assert outcome.price == 50
    assert outcome.expected_profit == 100
    assert outcome.actual_profit == 80
    assert outcome.user_feedback == "good"
    assert len(outcome.outcome_id) == 12
    assert outcome.timestamp


def test_record_trade_outcome_defaults():
    outcome = record_trade_outcome("g1", "skipped", "test_item", 0)
    assert outcome.expected_profit == 0
    assert outcome.actual_profit == 0
    assert outcome.user_feedback == "ignored"


# ── 目标持久化 ──────────────────────────────────────────

def test_goal_memory_persistence(tmp_path):
    mem_path = tmp_path / "test_memory.json"

    # 创建并保存
    memory = AgentMemory.default()
    goal = create_goal("maximize_profit", "持久化测试", criteria={"budget": 300})
    memory = memory.with_goal(goal)
    outcome = record_trade_outcome(goal.goal_id, "bought", "test", 50, 100, 80, "good")
    memory = memory.with_trade_outcome(outcome)
    memory.save(mem_path)

    # 重新加载
    loaded = AgentMemory.load(mem_path)
    assert len(loaded.active_goals) == 1
    assert loaded.active_goals[0].goal_id == goal.goal_id
    assert loaded.active_goals[0].description == "持久化测试"
    assert len(loaded.trade_outcomes) == 1
    assert loaded.trade_outcomes[0].item_id == "test"


def test_goal_memory_with_goal_result():
    memory = AgentMemory.default()
    goal = create_goal("flip_mod", "测试结果")
    memory = memory.with_goal(goal)

    # 添加执行结果
    memory = memory.with_goal_result(goal.goal_id, {"item": "mod_a", "profit": 50})
    memory = memory.with_goal_result(goal.goal_id, {"item": "mod_b", "profit": 30})

    g = memory.active_goals[0]
    assert len(g.results) == 2
    assert g.results[0]["item"] == "mod_a"
    assert g.results[1]["profit"] == 30


def test_active_goals_list():
    memory = AgentMemory.default()
    g1 = create_goal("maximize_profit", "活跃目标1")
    g2 = create_goal("flip_mod", "活跃目标2")
    memory = memory.with_goal(g1).with_goal(g2)

    active = memory.active_goals_list()
    assert len(active) == 2

    # 放弃一个
    from dataclasses import replace
    goals = [replace(g2, status="abandoned")] + [g1]
    memory = replace(memory, active_goals=goals)

    active = memory.active_goals_list()
    assert len(active) == 1
    assert active[0].goal_id == g1.goal_id
