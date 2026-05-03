import json
import tempfile
import unittest
from pathlib import Path

from warframe_agent.memory import AgentMemory, PriceAlert, TradingPreferences, UserProfile


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
