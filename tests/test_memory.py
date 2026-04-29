import json
import tempfile
import unittest
from pathlib import Path

from warframe_agent.memory import AgentMemory, PriceAlert, TradingPreferences


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


if __name__ == "__main__":
    unittest.main()
