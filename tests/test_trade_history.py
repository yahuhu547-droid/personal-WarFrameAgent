from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from warframe_agent.trade_history import TradeHistoryDB, TradeRecord


class TestTradeHistoryDB(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test_trades.db"
        self.db = TradeHistoryDB(db_path=self.db_path)

    def tearDown(self):
        self.db_path.unlink(missing_ok=True)

    def test_add_and_get_recent(self):
        tid = self.db.add_trade("item1", "物品一", "buy", 100, "玩家A", "测试")
        self.assertIsInstance(tid, int)
        trades = self.db.get_recent_trades(limit=10)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].item_id, "item1")
        self.assertEqual(trades[0].trade_type, "buy")
        self.assertEqual(trades[0].price, 100)

    def test_get_trades_by_item(self):
        self.db.add_trade("item1", "物品一", "buy", 100)
        self.db.add_trade("item2", "物品二", "sell", 200)
        self.db.add_trade("item1", "物品一", "sell", 150)

        trades = self.db.get_trades_by_item("item1")
        self.assertEqual(len(trades), 2)
        self.assertTrue(all(t.item_id == "item1" for t in trades))

    def test_delete_trade(self):
        tid = self.db.add_trade("item1", "物品一", "buy", 100)
        self.assertTrue(self.db.delete_trade(tid))
        self.assertEqual(len(self.db.get_recent_trades()), 0)

    def test_delete_nonexistent_trade(self):
        self.assertFalse(self.db.delete_trade(9999))

    def test_trade_stats_empty(self):
        stats = self.db.get_trade_stats()
        self.assertEqual(stats["total_trades"], 0)
        self.assertEqual(stats["buy_count"], 0)
        self.assertEqual(stats["sell_count"], 0)
        self.assertEqual(stats["total_spent"], 0)
        self.assertEqual(stats["total_earned"], 0)
        self.assertEqual(stats["net_profit"], 0)

    def test_trade_stats_with_data(self):
        self.db.add_trade("item1", "物品一", "buy", 100)
        self.db.add_trade("item2", "物品二", "sell", 300)
        self.db.add_trade("item1", "物品一", "buy", 50)

        stats = self.db.get_trade_stats()
        self.assertEqual(stats["total_trades"], 3)
        self.assertEqual(stats["buy_count"], 2)
        self.assertEqual(stats["sell_count"], 1)
        self.assertEqual(stats["total_spent"], 150)
        self.assertEqual(stats["total_earned"], 300)
        self.assertEqual(stats["net_profit"], 150)

    def test_most_traded(self):
        for _ in range(3):
            self.db.add_trade("item1", "物品一", "buy", 100)
        self.db.add_trade("item2", "物品二", "sell", 200)

        stats = self.db.get_trade_stats()
        self.assertTrue(len(stats["most_traded"]) >= 1)
        self.assertEqual(stats["most_traded"][0]["name"], "物品一")
        self.assertEqual(stats["most_traded"][0]["count"], 3)

    def test_trade_record_dataclass(self):
        rec = TradeRecord(1, "id", "name", "buy", 100, "player", "ts", "notes")
        self.assertEqual(rec.id, 1)
        self.assertEqual(rec.item_id, "id")

    def test_recent_trades_limit(self):
        for i in range(5):
            self.db.add_trade(f"item{i}", f"物品{i}", "buy", i * 10)
        trades = self.db.get_recent_trades(limit=3)
        self.assertEqual(len(trades), 3)


if __name__ == "__main__":
    unittest.main()
