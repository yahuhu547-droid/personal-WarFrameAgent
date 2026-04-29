import tempfile
import unittest
from pathlib import Path

from warframe_agent.price_history import PriceHistoryDB


class PriceHistoryTests(unittest.TestCase):
    def test_record_and_retrieve_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 45, 38)
            snapshots = db.recent("arcane_energize")

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].item_id, "arcane_energize")
        self.assertEqual(snapshots[0].sell_price, 45)
        self.assertEqual(snapshots[0].buy_price, 38)

    def test_recent_limits_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            for i in range(20):
                db.record("arcane_energize", 40 + i, 30 + i)
            snapshots = db.recent("arcane_energize", limit=5)

        self.assertEqual(len(snapshots), 5)
        self.assertEqual(snapshots[0].sell_price, 59)

    def test_trend_summary_shows_increase(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 40, 30)
            db.record("arcane_energize", 42, 32)
            db.record("arcane_energize", 45, 35)
            trend = db.trend_summary("arcane_energize")

        self.assertIn("上涨", trend)
        self.assertIn("+5p", trend)

    def test_trend_summary_shows_decrease(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 50, 40)
            db.record("arcane_energize", 48, 38)
            db.record("arcane_energize", 45, 35)
            trend = db.trend_summary("arcane_energize")

        self.assertIn("下跌", trend)
        self.assertIn("-5p", trend)

    def test_trend_summary_returns_none_for_single_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 45, 38)
            trend = db.trend_summary("arcane_energize")

        self.assertIsNone(trend)

    def test_trend_summary_shows_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 45, 38)
            db.record("arcane_energize", 45, 38)
            trend = db.trend_summary("arcane_energize")

        self.assertIn("持平", trend)


if __name__ == "__main__":
    unittest.main()
