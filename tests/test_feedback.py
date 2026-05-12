"""Tests for feedback analyzer."""
import pytest
from warframe_agent.feedback import FeedbackAnalyzer, StrategyFeedback, ItemFeedback
from warframe_agent.goals import TradeOutcome


def _outcome(item_id="item_a", actual_profit=10, expected_profit=20, action="bought", goal_id="goal_mod_1", outcome_id="o1"):
    return TradeOutcome(
        outcome_id=outcome_id,
        goal_id=goal_id,
        action=action,
        item_id=item_id,
        price=100,
        expected_profit=expected_profit,
        actual_profit=actual_profit,
        user_feedback="good" if actual_profit > 0 else "bad",
        timestamp="2025-01-01T00:00:00",
    )


class TestAnalyzeStrategies:
    def test_basic(self):
        outcomes = [
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_1"),
            _outcome(actual_profit=15, expected_profit=20, goal_id="goal_mod_2", outcome_id="o2"),
            _outcome(actual_profit=-5, expected_profit=20, goal_id="goal_mod_3", outcome_id="o3"),
        ]
        fb = FeedbackAnalyzer().analyze_strategies(outcomes)
        assert len(fb) == 1
        mod = fb[0]
        assert mod.strategy == "mod_flip"
        assert mod.win_rate == pytest.approx(2 / 3, abs=0.01)
        assert mod.sample_size == 3
        assert mod.confidence == "medium"

    def test_empty_outcomes(self):
        fb = FeedbackAnalyzer().analyze_strategies([])
        assert fb == []

    def test_low_confidence(self):
        outcomes = [
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_1"),
        ]
        fb = FeedbackAnalyzer().analyze_strategies(outcomes)
        assert fb[0].confidence == "low"
        assert fb[0].sample_size == 1

    def test_high_confidence(self):
        outcomes = [
            _outcome(actual_profit=10, expected_profit=20, goal_id=f"goal_mod_{i}", outcome_id=f"o{i}")
            for i in range(10)
        ]
        fb = FeedbackAnalyzer().analyze_strategies(outcomes)
        assert fb[0].confidence == "high"

    def test_recommended_threshold(self):
        # win_rate > 0.5 and avg_profit > 5
        outcomes = [
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_1"),
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_2", outcome_id="o2"),
        ]
        fb = FeedbackAnalyzer().analyze_strategies(outcomes)
        assert fb[0].recommended is True

    def test_not_recommended_low_win_rate(self):
        outcomes = [
            _outcome(actual_profit=-10, expected_profit=20, goal_id="goal_mod_1"),
            _outcome(actual_profit=-10, expected_profit=20, goal_id="goal_mod_2", outcome_id="o2"),
        ]
        fb = FeedbackAnalyzer().analyze_strategies(outcomes)
        assert fb[0].recommended is False

    def test_not_recommended_low_profit(self):
        # win_rate = 1.0 but avg_profit <= 5
        outcomes = [
            _outcome(actual_profit=3, expected_profit=20, goal_id="goal_mod_1"),
            _outcome(actual_profit=3, expected_profit=20, goal_id="goal_mod_2", outcome_id="o2"),
        ]
        fb = FeedbackAnalyzer().analyze_strategies(outcomes)
        assert fb[0].recommended is False

    def test_multiple_strategies(self):
        outcomes = [
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_1"),
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_2", outcome_id="o2"),
            _outcome(actual_profit=20, expected_profit=30, goal_id="goal_set_1", outcome_id="o3"),
            _outcome(actual_profit=-5, expected_profit=30, goal_id="goal_set_2", outcome_id="o4"),
        ]
        fb = FeedbackAnalyzer().analyze_strategies(outcomes)
        strategies = {f.strategy for f in fb}
        assert "mod_flip" in strategies
        assert "set_build" in strategies


class TestAnalyzeItems:
    def test_basic(self):
        outcomes = [
            _outcome(item_id="serration", actual_profit=10, goal_id="goal_mod_1"),
            _outcome(item_id="serration", actual_profit=-5, goal_id="goal_mod_2", outcome_id="o2"),
            _outcome(item_id="vitality", actual_profit=20, goal_id="goal_mod_3", outcome_id="o3"),
        ]
        fb = FeedbackAnalyzer().analyze_items(outcomes)
        items = {f.item_id: f for f in fb}
        assert "serration" in items
        assert "vitality" in items
        assert items["serration"].times_traded == 2
        assert items["serration"].total_profit == 5
        assert items["serration"].win_rate == pytest.approx(0.5, abs=0.01)
        assert items["vitality"].win_rate == 1.0

    def test_empty(self):
        fb = FeedbackAnalyzer().analyze_items([])
        assert fb == []

    def test_best_strategy(self):
        outcomes = [
            _outcome(item_id="item_a", actual_profit=10, action="mod_flip", goal_id="goal_mod_1"),
            _outcome(item_id="item_a", actual_profit=30, action="set_build", goal_id="goal_set_1", outcome_id="o2"),
        ]
        fb = FeedbackAnalyzer().analyze_items(outcomes)
        assert fb[0].best_strategy == "set_build"  # higher avg profit


class TestGetStrategyRanking:
    def test_recommended_first(self):
        outcomes = [
            # mod_flip: profitable → recommended
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_1"),
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_2", outcome_id="o2"),
            # set_build: loss → not recommended
            _outcome(actual_profit=-10, expected_profit=30, goal_id="goal_set_1", outcome_id="o3"),
            _outcome(actual_profit=-10, expected_profit=30, goal_id="goal_set_2", outcome_id="o4"),
        ]
        ranking = FeedbackAnalyzer().get_strategy_ranking(outcomes)
        assert ranking[0] == "mod_flip"

    def test_empty(self):
        assert FeedbackAnalyzer().get_strategy_ranking([]) == []


class TestGetFeedbackFor:
    def test_found(self):
        outcomes = [
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_1"),
        ]
        fb = FeedbackAnalyzer().get_feedback_for(outcomes, "mod_flip")
        assert fb is not None
        assert fb.strategy == "mod_flip"

    def test_not_found(self):
        outcomes = [
            _outcome(actual_profit=10, expected_profit=20, goal_id="goal_mod_1"),
        ]
        fb = FeedbackAnalyzer().get_feedback_for(outcomes, "set_build")
        assert fb is None

    def test_empty(self):
        fb = FeedbackAnalyzer().get_feedback_for([], "mod_flip")
        assert fb is None
