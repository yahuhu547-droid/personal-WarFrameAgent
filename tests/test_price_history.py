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
            db.close()

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
            db.close()

            self.assertEqual(len(snapshots), 5)
            self.assertEqual(snapshots[0].sell_price, 59)

    def test_trend_summary_shows_increase(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 40, 30)
            db.record("arcane_energize", 42, 32)
            db.record("arcane_energize", 45, 35)
            trend = db.trend_summary("arcane_energize")
            db.close()

            self.assertIn("上涨", trend)
            self.assertIn("+5p", trend)

    def test_trend_summary_shows_decrease(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 50, 40)
            db.record("arcane_energize", 48, 38)
            db.record("arcane_energize", 45, 35)
            trend = db.trend_summary("arcane_energize")
            db.close()

            self.assertIn("下跌", trend)
            self.assertIn("-5p", trend)

    def test_trend_summary_returns_none_for_single_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 45, 38)
            trend = db.trend_summary("arcane_energize")
            db.close()

            self.assertIsNone(trend)

    def test_trend_summary_shows_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 45, 38)
            db.record("arcane_energize", 45, 38)
            trend = db.trend_summary("arcane_energize")
            db.close()

            self.assertIn("持平", trend)

    def test_rolling_average_returns_average(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 40, 30)
            db.record("arcane_energize", 50, 40)
            db.record("arcane_energize", 60, 50)
            avg = db.rolling_average("arcane_energize")
            db.close()

            self.assertEqual(avg, 50.0)

    def test_rolling_average_returns_none_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            avg = db.rolling_average("arcane_energize")
            db.close()

            self.assertIsNone(avg)

    def test_detect_anomaly_spike(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            for _ in range(5):
                db.record("arcane_energize", 40, 30)
            db.record("arcane_energize", 60, 50)  # 50% spike
            anomaly = db.detect_anomaly("arcane_energize", threshold_pct=30)
            db.close()

            self.assertIsNotNone(anomaly)
            self.assertEqual(anomaly["direction"], "spike")
            self.assertGreater(anomaly["deviation_pct"], 30)

    def test_detect_anomaly_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            for _ in range(5):
                db.record("arcane_energize", 50, 40)
            db.record("arcane_energize", 30, 20)  # 40% drop
            anomaly = db.detect_anomaly("arcane_energize", threshold_pct=30)
            db.close()

            self.assertIsNotNone(anomaly)
            self.assertEqual(anomaly["direction"], "drop")

    def test_detect_anomaly_none_for_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            for _ in range(5):
                db.record("arcane_energize", 40, 30)
            anomaly = db.detect_anomaly("arcane_energize", threshold_pct=30)
            db.close()

            self.assertIsNone(anomaly)

    def test_detect_anomaly_none_for_insufficient_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = PriceHistoryDB(db_path=Path(tmp) / "test.db")
            db.record("arcane_energize", 40, 30)
            anomaly = db.detect_anomaly("arcane_energize", threshold_pct=30)
            db.close()

            self.assertIsNone(anomaly)


if __name__ == "__main__":
    unittest.main()
