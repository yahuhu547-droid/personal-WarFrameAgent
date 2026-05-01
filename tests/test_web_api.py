from __future__ import annotations

import unittest
from unittest.mock import Mock, patch
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
        mock_memory_class.load.return_value = mock_memory

        response = self.client.get("/api/memory")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("favorites", data)
        self.assertIn("alerts", data)
        self.assertIn("preferences", data)

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


if __name__ == "__main__":
    unittest.main()
