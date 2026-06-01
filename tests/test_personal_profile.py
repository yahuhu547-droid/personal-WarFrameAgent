import tempfile
from pathlib import Path

from warframe_agent.goals import TradeOutcome
from warframe_agent.memory import AgentMemory, TradingPreferences
from warframe_agent.personal_profile import build_personal_profile, format_personal_profile, profile_safe_summary
from warframe_agent.trading_memory import OpportunityOutcomeMemory


def test_trading_preferences_normalize_personal_fields():
    prefs = TradingPreferences(
        risk_appetite="HIGH",
        budget_min=40,
        budget_max=10,
        preferred_categories=["Arcane", "prime_set", "unknown", "mod"],
        max_turnaround_days=0,
        min_roi_pct=-5,
    )

    assert prefs.risk_appetite == "high"
    assert prefs.budget_min == 10
    assert prefs.budget_max == 40
    assert prefs.preferred_categories == ["arcane", "prime_set", "mod"]
    assert prefs.max_turnaround_days == 1
    assert prefs.min_roi_pct == 0


def test_agent_memory_persists_personal_preferences():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "agent_memory.json"
        memory = AgentMemory.default().with_updated_preferences(
            risk_appetite="low",
            budget_min=25,
            budget_max=300,
            preferred_categories=["mod", "arcane"],
            max_turnaround_days=3,
            min_roi_pct=35,
        )

        memory.save(path)
        loaded = AgentMemory.load(path)

    assert loaded.preferences.risk_appetite == "low"
    assert loaded.preferences.budget_min == 25
    assert loaded.preferences.budget_max == 300
    assert loaded.preferences.preferred_categories == ["mod", "arcane"]
    assert loaded.preferences.max_turnaround_days == 3
    assert loaded.preferences.min_roi_pct == 35


def test_set_preference_accepts_personal_profile_keys():
    memory = AgentMemory.default()

    memory = memory.set_preference("risk", "high")
    memory = memory.set_preference("budget", "50-250")
    memory = memory.set_preference("categories", "mod, arcane")
    memory = memory.set_preference("turnaround", "4")
    memory = memory.set_preference("min_roi", "45")

    assert memory.preferences.risk_appetite == "high"
    assert memory.preferences.budget_min == 50
    assert memory.preferences.budget_max == 250
    assert memory.preferences.preferred_categories == ["mod", "arcane"]
    assert memory.preferences.max_turnaround_days == 4
    assert memory.preferences.min_roi_pct == 45


def test_build_personal_profile_combines_explicit_and_derived_data():
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="low",
        budget_min=20,
        budget_max=200,
        preferred_categories=["arcane"],
        max_turnaround_days=2,
        min_roi_pct=25,
    )
    memory = memory.with_common_question("充沛赋能 能倒卖吗")
    memory = memory.with_common_question("高斯 prime 一套多少钱")
    memory = memory.with_trade_outcome(
        TradeOutcome(
            outcome_id="out1",
            goal_id="goal1",
            action="sold",
            item_id="arcane_energize",
            price=100,
            expected_profit=20,
            actual_profit=30,
            user_feedback="good",
            timestamp="2026-05-20T10:00:00+00:00",
        )
    )

    profile = build_personal_profile(memory)

    assert profile.risk_appetite == "low"
    assert profile.budget_label == "20-200p"
    assert profile.preferred_categories == ["arcane"]
    assert profile.derived_categories[0] in {"arcane", "prime_set"}
    assert profile.completed_outcome_count == 1
    assert profile.total_actual_profit == 30
    assert profile.win_rate == 1.0


def test_format_personal_profile_contains_no_player_or_whisper_data():
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="medium",
        budget_min=0,
        budget_max=150,
        preferred_categories=["mod"],
    )

    text = format_personal_profile(build_personal_profile(memory))

    assert "风险偏好" in text
    assert "/w " not in text
    assert "profile" not in text.lower()


def test_personal_profile_aggregates_outcome_feedback_safely():
    memory = AgentMemory.default()
    for index in range(3):
        memory = memory.with_trade_outcome(
            TradeOutcome(
                outcome_id=f"secret-op-{index}",
                goal_id="goal",
                action="mod_flipper",
                item_id="arcane_energize",
                price=50,
                expected_profit=20,
                actual_profit=30,
                user_feedback="good",
                timestamp="2026-05-26T00:00:00+00:00",
            )
        )

    profile = build_personal_profile(memory)

    assert profile.outcome_feedback
    signal = profile.outcome_feedback[0]
    assert signal.count == 3
    assert signal.win_count == 3
    assert signal.avg_actual_profit == 30.0
    assert signal.category == "arcane"
    serialized = str(profile_safe_summary(profile))
    for forbidden in ["secret-op", "profile_url", "/w ", "token", "SellerName"]:
        assert forbidden not in serialized


def test_personal_profile_feedback_summary_does_not_echo_sensitive_outcome_text():
    memory = AgentMemory.default().with_trade_outcome(
        TradeOutcome(
            outcome_id="secret-op-token",
            goal_id="goal-secret-token",
            action="token=SECRET /w SellerName profile_url raw_orders",
            item_id="sensitive_item",
            price=50,
            expected_profit=20,
            actual_profit=30,
            user_feedback="good token=SECRET /w SellerName",
            timestamp="2026-05-26T00:00:00+00:00",
        )
    )

    profile = build_personal_profile(memory)

    assert profile.outcome_feedback[0].source == "unknown"
    assert profile.outcome_feedback[0].strategy == "unknown"
    assert profile.outcome_feedback[0].category == "unknown"
    serialized = str(profile_safe_summary(profile)).lower()
    for forbidden in [
        "secret",
        "sellername",
        "profile_url",
        "/w",
        "token",
        "raw_orders",
        "secret-op",
        "goal-secret",
    ]:
        assert forbidden not in serialized


def test_personal_profile_aggregates_sqlite_opportunity_outcomes_safely():
    memory = AgentMemory.default()
    outcomes = [
        OpportunityOutcomeMemory(
            id=index,
            timestamp="2026-05-26T00:00:00",
            opportunity_id=f"OPSECRET{index}",
            item_name="arcane_energize",
            source="mod_flipper",
            strategy="arcane_rank0_to_max",
            status="completed",
            expected_profit=30,
            actual_profit=40,
            user_feedback="good",
            metadata={
                "safe_summary": {"roi_pct": 40, "risk_level": "low"},
                "profile_url": "https://warframe.market/profile/SecretSeller",
                "whisper": "/w SecretSeller hi",
                "token": "secret-token",
            },
        )
        for index in range(3)
    ]

    profile = build_personal_profile(memory, opportunity_outcomes=outcomes)

    assert profile.completed_outcome_count == 3
    assert profile.total_actual_profit == 120
    assert profile.win_rate == 1.0
    signal = profile.outcome_feedback[0]
    assert signal.source == "mod_flipper"
    assert signal.strategy == "arcane_rank0_to_max"
    assert signal.category == "arcane"
    assert signal.count == 3
    assert signal.win_count == 3
    assert signal.avg_actual_profit == 40.0
    serialized = str(profile_safe_summary(profile)).lower()
    for forbidden in ["opsecret", "secretseller", "profile_url", "/w", "token", "secret-token"]:
        assert forbidden not in serialized
