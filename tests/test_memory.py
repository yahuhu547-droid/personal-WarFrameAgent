import json
import tempfile
import unittest
from pathlib import Path

from warframe_agent.memory import AgentMemory, CycleAlert, PriceAlert, ProactiveSuggestion, TradingPreferences, UserProfile


class MemoryTests(unittest.TestCase):
    def test_memory_loads_preferences_and_alerts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.json"
            path.write_text(json.dumps({
                "preferences": {"platform": "pc", "crossplay": True, "max_results": 5},
                "price_alerts": [{"item_id": "arcane_energize", "direction": "below", "price": 45, "note": "低于45提醒"}],
                "favorite_items": ["arcane_energize"],
                "common_questions": ["充沛现在价格怎么样"],
            }, ensure_ascii=False), encoding="utf-8")

            memory = AgentMemory.load(path)

        self.assertEqual(memory.preferences.platform, "pc")
        self.assertTrue(memory.preferences.crossplay)
        self.assertEqual(memory.price_alerts[0].item_id, "arcane_energize")
        self.assertIn("充沛现在价格怎么样", memory.common_questions)

    def test_price_alert_matches_current_price(self):
        alert = PriceAlert("arcane_energize", "below", 45, "低于45提醒")

        self.assertTrue(alert.matches(40))
        self.assertFalse(alert.matches(50))

    def test_opportunity_filter_defaults_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.json"
            path.write_text(json.dumps({
                "preferences": {"platform": "pc", "crossplay": True, "max_results": 5},
                "price_alerts": [],
                "favorite_items": [],
                "common_questions": [],
                "watchlist": [],
            }, ensure_ascii=False), encoding="utf-8")

            memory = AgentMemory.load(path)
            self.assertEqual(memory.preferences.opportunity_filter, "all")
            updated = memory.with_updated_preferences(opportunity_filter="mod")
            updated.save(path)
            loaded = AgentMemory.load(path)

        self.assertEqual(loaded.preferences.opportunity_filter, "mod")
        self.assertEqual(loaded.to_dict()["preferences"]["opportunity_filter"], "mod")

    def test_invalid_opportunity_filter_normalizes_to_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.json"
            path.write_text(json.dumps({
                "preferences": {"opportunity_filter": "everything"},
                "price_alerts": [],
                "favorite_items": [],
                "common_questions": [],
                "watchlist": [],
            }, ensure_ascii=False), encoding="utf-8")

            memory = AgentMemory.load(path)

        self.assertEqual(memory.preferences.opportunity_filter, "all")

    def test_recent_suggestions_deduplicate_by_opportunity_identity(self):
        memory = AgentMemory.default()
        first = ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="opportunity",
            priority=2,
            message="旧机会",
            data={"source": "spread", "dedupe_key": "opportunity:arcane_energize:spread"},
        )
        second = ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="opportunity",
            priority=2,
            message="新机会",
            data={"source": "spread", "dedupe_key": "opportunity:arcane_energize:spread"},
        )

        memory = memory.with_suggestion(first).with_suggestion(second)

        self.assertEqual(len(memory.recent_suggestions), 1)
        self.assertEqual(memory.recent_suggestions[0].message, "新机会")

    def test_cycle_alert_round_trip_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.json"
            alert = CycleAlert("earth", "night", "地球变为黑夜", 123.0)
            memory = AgentMemory.default().with_cycle_alert(alert).with_cycle_alert(alert)
            self.assertEqual(len(memory.cycle_alerts), 1)
            self.assertTrue(memory.cycle_alerts[0].matches_cycle("earth", "night"))
            memory.save(path)
            loaded = AgentMemory.load(path)

        self.assertEqual(len(loaded.cycle_alerts), 1)
        self.assertEqual(loaded.cycle_alerts[0].cycle, "earth")
        self.assertEqual(loaded.cycle_alerts[0].target_state, "night")
        self.assertEqual(loaded.without_cycle_alert(0).cycle_alerts, [])


class UserProfileTests(unittest.TestCase):
    def test_from_questions_buy_bias(self):
        questions = ["买充沛多少钱", "收川流不息", "买mod价格", "卖一个赋能", "买p套"]
        profile = UserProfile.from_questions(questions)
        self.assertEqual(profile.preferred_trade_type, "buy")
        self.assertEqual(profile.total_queries, 5)

    def test_from_questions_sell_bias(self):
        questions = ["卖充沛多少钱", "出川流不息", "有人收mod吗", "最高收多少"]
        profile = UserProfile.from_questions(questions)
        self.assertEqual(profile.preferred_trade_type, "sell")

    def test_from_questions_neutral(self):
        questions = ["充沛多少钱", "川流不息怎么样"]
        profile = UserProfile.from_questions(questions)
        self.assertEqual(profile.preferred_trade_type, "neutral")

    def test_from_questions_detects_categories(self):
        questions = ["买赋能", "赋能价格", "mod多少钱", "一套p套价格"]
        profile = UserProfile.from_questions(questions)
        self.assertIn("arcane", profile.favorite_categories)
        self.assertIn("mod", profile.favorite_categories)
        self.assertIn("prime_set", profile.favorite_categories)

    def test_from_questions_empty(self):
        profile = UserProfile.from_questions([])
        self.assertEqual(profile.preferred_trade_type, "neutral")
        self.assertEqual(profile.total_queries, 0)
        self.assertEqual(profile.queried_items, {})

    def test_memory_round_trip_with_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.json"
            memory = AgentMemory.default()
            memory = memory.with_common_question("买充沛多少钱")
            memory = memory.with_common_question("赋能价格")
            memory = memory.analyze_and_update_profile()
            self.assertIsNotNone(memory.user_profile)
            self.assertEqual(memory.user_profile.preferred_trade_type, "buy")
            memory.save(path)
            loaded = AgentMemory.load(path)
            self.assertIsNotNone(loaded.user_profile)
            self.assertEqual(loaded.user_profile.preferred_trade_type, "buy")
            self.assertEqual(loaded.user_profile.total_queries, 2)

    def test_analyze_and_update_profile_no_questions(self):
        memory = AgentMemory.default()
        result = memory.analyze_and_update_profile()
        self.assertIsNone(result.user_profile)


if __name__ == "__main__":
    unittest.main()
