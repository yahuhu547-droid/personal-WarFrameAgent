from __future__ import annotations

import unittest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from warframe_agent.web.app import app


class TestWebAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("warframe_agent.web.app.chat_agent")
    def test_chat_endpoint(self, mock_agent):
        mock_agent.answer.return_value = "充沛赋能最低卖价 45p"
        response = self.client.post("/api/chat", json={"message": "充沛多少钱"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reply", data)
        self.assertEqual(data["reply"], "充沛赋能最低卖价 45p")

    @patch("warframe_agent.web.app.AgentMemory")
    def test_get_memory(self, mock_memory_class):
        mock_memory = Mock()
        mock_memory.favorite_items = ["arcane_energize"]
        mock_memory.price_alerts = []
        mock_memory.preferences = {"platform": "pc"}
        mock_memory.watchlist = []
        mock_memory_class.load.return_value = mock_memory

        response = self.client.get("/api/memory")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("favorites", data)
        self.assertIn("alerts", data)
        self.assertIn("preferences", data)
        self.assertIn("watchlist", data)

    @patch("warframe_agent.web.app.AgentMemory")
    def test_add_favorite(self, mock_memory_class):
        mock_memory = Mock()
        mock_memory.add_favorite.return_value = mock_memory
        mock_memory_class.load.return_value = mock_memory

        response = self.client.post("/api/fav", json={"item_id": "arcane_energize"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("warframe_agent.web.app.AgentMemory")
    def test_remove_favorite(self, mock_memory_class):
        mock_memory = Mock()
        mock_memory.remove_favorite.return_value = mock_memory
        mock_memory_class.load.return_value = mock_memory

        response = self.client.request("DELETE", "/api/fav", json={"item_id": "arcane_energize"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("warframe_agent.web.app.AgentMemory")
    def test_add_alert(self, mock_memory_class):
        mock_memory = Mock()
        mock_memory.add_alert.return_value = mock_memory
        mock_memory_class.load.return_value = mock_memory

        response = self.client.post("/api/alert", json={
            "item_id": "arcane_energize",
            "direction": "below",
            "price": 45
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("warframe_agent.web.app.AgentMemory")
    def test_set_preference(self, mock_memory_class):
        mock_memory = Mock()
        mock_memory.set_preference.return_value = mock_memory
        mock_memory_class.load.return_value = mock_memory

        response = self.client.post("/api/pref", json={"key": "platform", "value": "pc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_set_preference_invalid_max_results(self):
        response = self.client.post("/api/pref", json={"key": "max_results", "value": "0"})
        self.assertEqual(response.status_code, 422)

    @patch("warframe_agent.web.app.price_db")
    def test_get_history(self, mock_db):
        from warframe_agent.price_history import PriceSnapshot
        mock_db.recent.return_value = [
            PriceSnapshot("arcane_energize", 45, 38, "2026-04-30T10:00:00"),
            PriceSnapshot("arcane_energize", 46, 39, "2026-04-30T11:00:00"),
        ]

        response = self.client.get("/api/history/arcane_energize")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["item_id"], "arcane_energize")
        self.assertEqual(len(data["snapshots"]), 2)


    @patch("warframe_agent.web.app.price_db")
    def test_get_history_invalid_range(self, mock_db):
        response = self.client.get("/api/history/arcane_energize?range=90d")
        self.assertEqual(response.status_code, 422)



class TestWatchlistAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("warframe_agent.web.app.AgentMemory")
    def test_get_watchlist(self, mock_memory_class):
        mock_item = Mock()
        mock_item.item_id = "arcane_energize"
        mock_item.item_name = "充沛赋能"
        mock_item.frequency = "daily"
        mock_item.time = "09:00"
        mock_item.content = "top3_buyers"
        mock_memory = Mock()
        mock_memory.watchlist = [mock_item]
        mock_memory_class.load.return_value = mock_memory

        response = self.client.get("/api/watchlist")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["watchlist"]), 1)
        self.assertEqual(data["watchlist"][0]["item_id"], "arcane_energize")

    @patch("warframe_agent.web.app.AgentMemory")
    def test_add_watch_item(self, mock_memory_class):
        mock_memory = Mock()
        mock_memory.with_watch_item.return_value = mock_memory
        mock_memory_class.load.return_value = mock_memory

        response = self.client.post("/api/watchlist", json={
            "item_id": "arcane_energize",
            "item_name": "充沛赋能",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("warframe_agent.web.app.AgentMemory")
    def test_remove_watch_item(self, mock_memory_class):
        mock_memory = Mock()
        mock_memory.without_watch_item.return_value = mock_memory
        mock_memory_class.load.return_value = mock_memory

        response = self.client.delete("/api/watchlist/arcane_energize")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class TestTradesAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("warframe_agent.web.app.trade_db")
    def test_get_trades(self, mock_db):
        mock_trade = Mock()
        mock_trade.id = 1
        mock_trade.item_id = "item1"
        mock_trade.item_name = "物品一"
        mock_trade.trade_type = "buy"
        mock_trade.price = 100
        mock_trade.player_name = "玩家A"
        mock_trade.timestamp = "2026-05-01T10:00:00"
        mock_trade.notes = ""
        mock_db.get_recent_trades.return_value = [mock_trade]

        response = self.client.get("/api/trades")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["trades"]), 1)
        self.assertEqual(data["trades"][0]["item_id"], "item1")

    @patch("warframe_agent.web.app.trade_db")
    def test_add_trade(self, mock_db):
        mock_db.add_trade.return_value = 42

        response = self.client.post("/api/trades", json={
            "item_id": "item1",
            "item_name": "物品一",
            "trade_type": "buy",
            "price": 100,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["id"], 42)

    @patch("warframe_agent.web.app.trade_db")
    def test_delete_trade(self, mock_db):
        mock_db.delete_trade.return_value = True

        response = self.client.delete("/api/trades/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("warframe_agent.web.app.trade_db")
    def test_delete_trade_not_found(self, mock_db):
        mock_db.delete_trade.return_value = False

        response = self.client.delete("/api/trades/999")
        self.assertEqual(response.status_code, 404)

    def test_add_trade_invalid_trade_type(self):
        response = self.client.post("/api/trades", json={
            "item_id": "item1",
            "item_name": "物品一",
            "trade_type": "hold",
            "price": 100,
        })
        self.assertEqual(response.status_code, 422)

    @patch("warframe_agent.web.app.trade_db")
    def test_get_trades_invalid_limit(self, mock_db):
        response = self.client.get("/api/trades?limit=0")
        self.assertEqual(response.status_code, 422)


    @patch("warframe_agent.web.app.trade_db")
    def test_get_trades_by_item(self, mock_db):
        mock_db.get_trades_by_item.return_value = []

        response = self.client.get("/api/trades/item/item1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["item_id"], "item1")
        self.assertEqual(data["trades"], [])


class TestSuggestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("warframe_agent.web.app.chat_agent")
    def test_suggest_empty_query(self, mock_agent):
        response = self.client.get("/api/suggest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggestions"], [])

    @patch("warframe_agent.web.app.chat_agent")
    def test_suggest_with_results(self, mock_agent):
        mock_resolver = Mock()
        mock_resolver.aliases = {"充沛": "arcane_energize", "充沛赋能": "arcane_energize"}
        mock_resolver.dictionary = {"Arcane Energize": "arcane_energize"}
        mock_agent.resolver = mock_resolver

        response = self.client.get("/api/suggest?q=充沛")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("充沛", data["suggestions"])


class TestAliasesAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("warframe_agent.web.app.inject_custom_aliases")
    @patch("warframe_agent.web.app.save_custom_aliases")
    @patch("warframe_agent.web.app.load_custom_aliases")
    def test_add_alias(self, mock_load, mock_save, mock_inject):
        mock_load.return_value = {}

        response = self.client.post("/api/aliases", json={
            "name": "我的别名",
            "item_id": "arcane_energize",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["name"], "我的别名")

    @patch("warframe_agent.web.app.inject_custom_aliases")
    @patch("warframe_agent.web.app.save_custom_aliases")
    @patch("warframe_agent.web.app.load_custom_aliases")
    def test_add_alias_empty_name(self, mock_load, mock_save, mock_inject):
        mock_load.return_value = {}

        response = self.client.post("/api/aliases", json={
            "name": "",
            "item_id": "arcane_energize",
        })
        self.assertEqual(response.status_code, 422)

    @patch("warframe_agent.web.app.inject_custom_aliases")
    @patch("warframe_agent.web.app.save_custom_aliases")
    @patch("warframe_agent.web.app.load_custom_aliases")
    def test_remove_alias(self, mock_load, mock_save, mock_inject):
        mock_load.return_value = {"我的别名": "arcane_energize"}

        response = self.client.request("DELETE", "/api/aliases", json={"name": "我的别名"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("warframe_agent.web.app.display_item_name")
    @patch("warframe_agent.web.app.load_custom_aliases")
    def test_get_aliases(self, mock_load, mock_display):
        mock_load.return_value = {"我的别名": "arcane_energize"}
        mock_display.return_value = "Arcane Energize"

        response = self.client.get("/api/aliases")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("aliases", data)
        self.assertEqual(len(data["aliases"]), 1)
        self.assertEqual(data["aliases"][0]["name"], "我的别名")
        self.assertEqual(data["aliases"][0]["item_id"], "arcane_energize")


class TestRivenAuctionsAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("warframe_agent.scraper.scrape_sync")
    @patch("warframe_agent.scraper.scrape_riven_auctions")
    def test_riven_auctions_supports_pagination(self, mock_scrape, mock_sync):
        from warframe_agent.scraper import ScrapedRiven, ScrapedRivenPage

        mock_scrape.return_value = object()
        mock_sync.return_value = ScrapedRivenPage(
            rivens=[ScrapedRiven(weapon="strun", mod_name="strun-mod", attributes=[], price=20, seller="Seller")],
            total=25,
            page=2,
            page_size=10,
        )

        response = self.client.get("/api/riven/auctions?weapon=strun&page=2&page_size=10")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 25)
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["page_size"], 10)
        self.assertEqual(len(data["rivens"]), 1)
        mock_scrape.assert_called_once_with("strun", page=2, page_size=10)


if __name__ == "__main__":
    unittest.main()
