from warframe_agent.goals import TradeOutcome
from warframe_agent.memory import AgentMemory
from warframe_agent.personal_profile import build_personal_profile
from warframe_agent.personal_scoring import score_personal_fit


def _memory_with_outcomes(source: str, item_id: str, feedback: str, actual_profit: int, count: int) -> AgentMemory:
    memory = AgentMemory.default()
    for index in range(count):
        memory = memory.with_trade_outcome(
            TradeOutcome(
                outcome_id=f"out{index}",
                goal_id="goal",
                action=source,
                item_id=item_id,
                price=100,
                expected_profit=20,
                actual_profit=actual_profit,
                user_feedback=feedback,
                timestamp="2026-05-26T00:00:00+00:00",
            )
        )
    return memory


def test_personal_fit_rewards_budget_category_roi_and_risk_match():
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="low",
        budget_min=20,
        budget_max=200,
        preferred_categories=["arcane"],
        min_roi_pct=25,
    )
    profile = build_personal_profile(memory)

    score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=45,
        roi_pct=37.5,
        risk_level="low",
        profile=profile,
    )

    assert score.personal_score >= 80
    assert "预算匹配" in score.reasons
    assert "偏好品类匹配" in score.reasons
    assert "ROI 达标" in score.reasons
    assert "风险匹配" in score.reasons


def test_personal_fit_penalizes_budget_overrun_and_risk_mismatch():
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="low",
        budget_min=20,
        budget_max=100,
        preferred_categories=["mod"],
        min_roi_pct=50,
    )
    profile = build_personal_profile(memory)

    score = score_personal_fit(
        item_id="gauss_prime_set",
        source="set_profit",
        strategy="buy_set_sell_parts",
        total_cost=350,
        profit=20,
        roi_pct=6.0,
        risk_level="high",
        profile=profile,
    )

    assert score.personal_score <= 35
    assert "超出预算" in score.reasons
    assert "ROI 未达偏好" in score.reasons
    assert "风险偏高" in score.reasons


def test_personal_fit_rewards_repeated_good_outcome_feedback():
    good_memory = _memory_with_outcomes("mod_flipper", "arcane_energize", "good", 35, count=3)
    good_memory = good_memory.with_updated_preferences(preferred_categories=["arcane"])
    neutral_memory = AgentMemory.default().with_updated_preferences(preferred_categories=["arcane"])
    good_profile = build_personal_profile(good_memory)
    neutral_profile = build_personal_profile(neutral_memory)

    good_score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=5,
        roi_pct=35,
        risk_level="medium",
        profile=good_profile,
    )
    neutral_score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=5,
        roi_pct=35,
        risk_level="medium",
        profile=neutral_profile,
    )

    assert good_score.personal_score > neutral_score.personal_score
    assert "历史策略表现好" in good_score.reasons


def test_personal_fit_penalizes_repeated_bad_outcome_feedback():
    bad_memory = _memory_with_outcomes("set_profit", "gauss_prime_set", "bad", -15, count=3)
    bad_memory = bad_memory.with_updated_preferences(preferred_categories=["prime_set"])
    neutral_memory = AgentMemory.default().with_updated_preferences(preferred_categories=["prime_set"])
    bad_profile = build_personal_profile(bad_memory)
    neutral_profile = build_personal_profile(neutral_memory)

    bad_score = score_personal_fit(
        item_id="gauss_prime_set",
        source="set_profit",
        strategy="buy_parts_sell_set",
        total_cost=160,
        profit=25,
        roi_pct=15,
        risk_level="medium",
        profile=bad_profile,
    )
    neutral_score = score_personal_fit(
        item_id="gauss_prime_set",
        source="set_profit",
        strategy="buy_parts_sell_set",
        total_cost=160,
        profit=25,
        roi_pct=15,
        risk_level="medium",
        profile=neutral_profile,
    )

    assert bad_score.personal_score < neutral_score.personal_score
    assert "历史策略需谨慎" in bad_score.reasons


def test_personal_fit_ignores_sparse_outcome_feedback():
    sparse_memory = _memory_with_outcomes("mod_flipper", "arcane_energize", "good", 35, count=1)
    sparse_memory = sparse_memory.with_updated_preferences(preferred_categories=["arcane"])
    neutral_memory = AgentMemory.default().with_updated_preferences(preferred_categories=["arcane"])
    sparse_profile = build_personal_profile(sparse_memory)
    neutral_profile = build_personal_profile(neutral_memory)

    sparse_score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=5,
        roi_pct=35,
        risk_level="medium",
        profile=sparse_profile,
    )
    neutral_score = score_personal_fit(
        item_id="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        total_cost=120,
        profit=5,
        roi_pct=35,
        risk_level="medium",
        profile=neutral_profile,
    )

    assert sparse_score.personal_score == neutral_score.personal_score
    assert "历史策略表现好" not in sparse_score.reasons
