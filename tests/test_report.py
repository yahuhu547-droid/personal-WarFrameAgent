import tempfile
import unittest
from pathlib import Path

from warframe_agent.market import MarketOrder
from warframe_agent.report import render_daily_report, write_daily_report


class ReportTests(unittest.TestCase):
    def test_render_daily_report_contains_categories_and_spread(self):
        items = [
            {
                "category": "赋能",
                "item_id": "arcane_energize",
                "sellers": [MarketOrder("sell", 30, 1, "Seller", "ingame", 10)],
                "buyers": [MarketOrder("buy", 20, 1, "Buyer", "ingame", 5)],
                "error": None,
            }
        ]

        markdown = render_daily_report(items, report_date="2026-04-28")

        self.assertIn("# Warframe 每日价格表 - 2026-04-28", markdown)
        self.assertIn("赋能", markdown)
        self.assertIn("arcane_energize", markdown)
        self.assertIn("10p", markdown)

    def test_write_daily_report_creates_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_daily_report([], output_dir=Path(tmp), report_date="2026-04-28")

            self.assertTrue(path.exists())
            self.assertEqual(path.name, "daily-2026-04-28.md")


if __name__ == "__main__":
    unittest.main()
