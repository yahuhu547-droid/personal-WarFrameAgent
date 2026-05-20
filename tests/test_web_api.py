from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from fastapi.testclient import TestClient

from warframe_agent.push import PushConfig
from warframe_agent.relics import RelicDrop, RelicInfo
from warframe_agent.rules import ProactivePush
from warframe_agent.trading_memory import MarketSnapshotMemory, PushHistoryMemory, RecommendationMemory, TradingMemoryDB
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

    @patch("warframe_agent.web.app.fetch_orders")
    @patch("warframe_agent.web.app.EventTracker")
    @patch("warframe_agent.web.app.game_data")
    @patch("warframe_agent.relics.get_relic_db")
    def test_farming_route_api_returns_ranked_routes(self, mock_get_db, mock_game_data, mock_tracker, mock_fetch_orders):
        relic = RelicInfo(
            name="Lith B1",
            tier="Lith",
            is_vaulted=False,
            drops=[RelicDrop("Lith B1", "Lith", "Braton Prime Blueprint", "braton_prime_blueprint", "COMMON", 0.2533)],
        )
        fake_db = Mock()
        fake_db.load.return_value = None
        fake_db.find_by_part.return_value = relic.drops
        fake_db.find_by_relic.return_value = None
        mock_get_db.return_value = fake_db
        mock_game_data.get_relic_sources.return_value = ["Hepit, Void 捕获"]
        mock_game_data.is_vaulted.return_value = False
        mock_game_data.get_ducat_value.return_value = 15
        mock_tracker.return_value.get_void_fissures.return_value = []
        mock_fetch_orders.return_value = [
            {"type": "sell", "platinum": 8, "user": {"ingameName": "Seller_ROUTE_RAW"}},
            {"type": "buy", "platinum": 5, "user": {"ingameName": "Buyer_ROUTE_RAW"}},
        ]

        response = self.client.get("/api/farming-route?target=braton_prime_blueprint")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["target"], "braton_prime_blueprint")
        self.assertEqual(data["queryType"], "part")
        self.assertEqual(data["routes"][0]["relicName"], "Lith B1")
        self.assertEqual(data["routes"][0]["dropRate"], 0.2533)
        self.assertIn("score", data["routes"][0])
        self.assertIn("sources", data["routes"][0])
        self.assertNotIn("ROUTE_RAW", json.dumps(data, ensure_ascii=False))

    @patch("warframe_agent.web.app.fetch_orders")
    @patch("warframe_agent.web.app.game_data")
    @patch("warframe_agent.relics.get_relic_db")
    def test_relic_value_api_returns_ev_ducats_and_rewards(self, mock_get_db, mock_game_data, mock_fetch_orders):
        relic = RelicInfo(
            name="Lith B1",
            tier="Lith",
            is_vaulted=False,
            drops=[
                RelicDrop("Lith B1", "Lith", "Braton Prime Blueprint", "braton_prime_blueprint", "COMMON", 0.2533),
                RelicDrop("Lith B1", "Lith", "Forma Blueprint", "forma_blueprint", "RARE", 0.02),
            ],
        )
        fake_db = Mock()
        fake_db.load.return_value = None
        fake_db.find_by_relic.return_value = relic
        mock_get_db.return_value = fake_db
        mock_game_data.get_ducat_value.side_effect = lambda item_id: {"braton_prime_blueprint": 15}.get(item_id)
        mock_fetch_orders.side_effect = lambda item_id: [
            {"type": "sell", "platinum": 8, "quantity": 1, "user": {"ingameName": "Seller_API_RAW", "status": "ingame"}},
            {"type": "buy", "platinum": 5, "quantity": 1, "user": {"ingameName": "Buyer_API_RAW", "status": "ingame"}},
        ]

        response = self.client.get("/api/relic/value/Lith/B1")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tier"], "Lith")
        self.assertEqual(data["relicName"], "B1")
        self.assertIn("expectedPlatinum", data)
        self.assertIn("expectedDucats", data)
        self.assertEqual(data["rewards"][0]["highestBuyPrice"], 5)
        self.assertEqual(data["rewards"][0]["valuationSource"], "highest_buy")
        self.assertIsNone(data["rewards"][1]["ducatValue"])
        self.assertIn("未知杜卡德值", data["rewards"][1]["warnings"])
        self.assertNotIn("Seller_API_RAW", json.dumps(data, ensure_ascii=False))

    @patch("warframe_agent.web.app.fetch_orders")
    @patch("warframe_agent.set_profit.fetch_item_statistics", return_value={"volume_48h": 10})
    @patch("warframe_agent.scout.scout_set_candidates")
    @patch("warframe_agent.web.app._load_items_full")
    def test_set_profit_api_returns_actionable_trade_plan(self, mock_load_items, mock_scout, mock_stats, mock_fetch_orders):
        from warframe_agent.web import app as web_app

        mock_load_items.return_value = [
            {"item_id": "rhino_prime_set", "tags": ["prime"], "en_name": "Rhino Prime Set"},
            {"item_id": "rhino_prime_blueprint", "tags": ["prime"], "en_name": "Rhino Prime Blueprint"},
            {"item_id": "rhino_prime_chassis_blueprint", "tags": ["prime"], "en_name": "Rhino Prime Chassis Blueprint"},
            {"item_id": "rhino_prime_neuroptics_blueprint", "tags": ["prime"], "en_name": "Rhino Prime Neuroptics Blueprint"},
            {"item_id": "rhino_prime_systems_blueprint", "tags": ["prime"], "en_name": "Rhino Prime Systems Blueprint"},
        ]
        mock_scout.return_value = ["rhino_prime"]

        def fake_orders(item_id):
            data = {
                "rhino_prime_set": [
                    {"order_type": "sell", "platinum": 90, "quantity": 1, "user": {"ingame_name": "SetSeller_API", "status": "ingame", "reputation": 5}},
                    {"order_type": "buy", "platinum": 95, "quantity": 1, "user": {"ingame_name": "SetBuyer_API", "status": "ingame", "reputation": 5}},
                ],
                "rhino_prime_blueprint": [
                    {"order_type": "sell", "platinum": 10, "quantity": 1, "user": {"ingame_name": "BpSeller_API", "status": "ingame", "reputation": 5}},
                    {"order_type": "buy", "platinum": 8, "quantity": 1, "user": {"ingame_name": "BpBuyer_API", "status": "ingame", "reputation": 5}},
                ],
                "rhino_prime_chassis_blueprint": [
                    {"order_type": "sell", "platinum": 15, "quantity": 1, "user": {"ingame_name": "ChassisSeller_API", "status": "ingame", "reputation": 5}},
                    {"order_type": "buy", "platinum": 12, "quantity": 1, "user": {"ingame_name": "ChassisBuyer_API", "status": "ingame", "reputation": 5}},
                ],
                "rhino_prime_neuroptics_blueprint": [
                    {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "NeuroSeller_API", "status": "ingame", "reputation": 5}},
                    {"order_type": "buy", "platinum": 15, "quantity": 1, "user": {"ingame_name": "NeuroBuyer_API", "status": "ingame", "reputation": 5}},
                ],
                "rhino_prime_systems_blueprint": [
                    {"order_type": "sell", "platinum": 25, "quantity": 1, "user": {"ingame_name": "SystemsSeller_API", "status": "ingame", "reputation": 5}},
                    {"order_type": "buy", "platinum": 20, "quantity": 1, "user": {"ingame_name": "SystemsBuyer_API", "status": "ingame", "reputation": 5}},
                ],
            }
            return data.get(item_id, [])

        async def run_request():
            mock_fetch_orders.side_effect = fake_orders
            web_app._scan_cache.clear()
            web_app._bg_tasks.clear()
            try:
                response = await web_app.set_profit_endpoint(min_profit=5, limit=5)
                start_data = json.loads(response.body.decode("utf-8"))
                self.assertEqual(start_data["status"], "running")
                for _ in range(20):
                    await asyncio.sleep(0.05)
                    task = web_app._bg_tasks[start_data["task_id"]]
                    if task["status"] != "running":
                        return task
                return web_app._bg_tasks[start_data["task_id"]]
            finally:
                web_app._scan_cache.clear()
                web_app._bg_tasks.clear()

        task = asyncio.run(run_request())
        self.assertEqual(task["status"], "done")
        result = task["result"]["results"][0]
        plan = result["trade_plan"]
        self.assertEqual(plan["strategy"], "buy_parts_sell_set")
        self.assertEqual(plan["total_cost"], 70)
        self.assertEqual(plan["total_revenue"], 95)
        self.assertEqual(result["best_cost"], 70)
        self.assertEqual(result["best_revenue"], 95)
        self.assertEqual(result["roi_pct"], 35.7)
        self.assertGreater(result["liquidity_score"], 0)
        self.assertIn(result["risk_level"], {"low", "medium", "high"})
        self.assertGreater(result["opportunity_score"], result["best_profit"])
        self.assertEqual(plan["roi_pct"], result["roi_pct"])
        self.assertEqual(plan["risk_level"], result["risk_level"])
        self.assertEqual([step["player"] for step in plan["buy_steps"]], [
            "BpSeller_API", "ChassisSeller_API", "NeuroSeller_API", "SystemsSeller_API",
        ])
        self.assertEqual([step["player"] for step in plan["sell_steps"]], ["SetBuyer_API"])
        serialized_plan = str(plan)
        self.assertNotIn("SetSeller_API", serialized_plan)
        for buyer in ["BpBuyer_API", "ChassisBuyer_API", "NeuroBuyer_API", "SystemsBuyer_API"]:
            self.assertNotIn(buyer, serialized_plan)

    @patch("warframe_agent.web.app.fetch_orders")
    @patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 20})
    @patch("warframe_agent.scout.scout_investment_candidates")
    @patch("warframe_agent.web.app._load_items_full")
    def test_investment_api_returns_actionable_trade_plan(self, mock_load_items, mock_scout, mock_stats, mock_fetch_orders):
        from warframe_agent.web import app as web_app

        mock_load_items.return_value = [
            {"item_id": "rhino_prime_set", "tags": ["prime", "warframe", "set"], "en_name": "Rhino Prime Set"},
            {"item_id": "rhino_prime_blueprint", "tags": ["prime", "warframe", "blueprint"], "en_name": "Rhino Prime Blueprint"},
            {"item_id": "rhino_prime_chassis_blueprint", "tags": ["prime", "warframe", "blueprint"], "en_name": "Rhino Prime Chassis Blueprint"},
            {"item_id": "rhino_prime_neuroptics_blueprint", "tags": ["prime", "warframe", "blueprint"], "en_name": "Rhino Prime Neuroptics Blueprint"},
            {"item_id": "rhino_prime_systems_blueprint", "tags": ["prime", "warframe", "blueprint"], "en_name": "Rhino Prime Systems Blueprint"},
        ]
        mock_scout.return_value = ["rhino_prime"]

        def fake_orders(item_id):
            if item_id == "rhino_prime_set":
                return [
                    {"order_type": "sell", "platinum": 90, "quantity": 1, "user": {"ingame_name": "SetSeller_INV_API", "status": "ingame", "reputation": 5}},
                    {"order_type": "buy", "platinum": 150, "quantity": 1, "user": {"ingame_name": "SetBuyer_INV_API", "status": "ingame", "reputation": 5}},
                ]
            return [
                {"order_type": "sell", "platinum": 10, "quantity": 1, "user": {"ingame_name": f"Seller_{item_id}", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 4, "quantity": 1, "user": {"ingame_name": f"Buyer_{item_id}", "status": "ingame", "reputation": 5}},
            ]

        async def run_request():
            mock_fetch_orders.side_effect = fake_orders
            web_app._scan_cache.clear()
            web_app._bg_tasks.clear()
            try:
                response = await web_app.investment_endpoint(budget=500, min_roi_pct=10.0, limit=5)
                start_data = json.loads(response.body.decode("utf-8"))
                for _ in range(20):
                    await asyncio.sleep(0.05)
                    task = web_app._bg_tasks[start_data["task_id"]]
                    if task["status"] != "running":
                        return task
                return web_app._bg_tasks[start_data["task_id"]]
            finally:
                web_app._scan_cache.clear()
                web_app._bg_tasks.clear()

        task = asyncio.run(run_request())
        self.assertEqual(task["status"], "done")
        result = task["result"]["results"][0]
        plan = result["trade_plan"]
        self.assertEqual(plan["source"], "investment")
        self.assertEqual(plan["strategy"], "buy_parts_sell_set")
        self.assertIn("SetBuyer_INV_API", str(plan))
        self.assertNotIn("SetSeller_INV_API", str(plan))
        self.assertIn("safe_summary", plan)

    @patch("warframe_agent.web.app.feishu_bot")
    @patch("warframe_agent.web.app.monitor")
    def test_runtime_status_endpoint(self, mock_monitor, mock_feishu):
        mock_feishu.status_snapshot.return_value = {"enabled": True, "configured": True, "available": True, "managed_running": True}
        mock_monitor.scheduler_status_snapshot.return_value = {"running": True, "has_scheduler": True, "total": 6, "jobs": []}
        mock_monitor.daily_report_status_snapshot.return_value = {"enabled": True, "report_time": "12:30", "should_send_now": False, "last_report_date": None}

        response = self.client.get("/api/runtime/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("web", data)
        self.assertIn("uptime_seconds", data["web"])
        self.assertEqual(data["feishu"]["managed_running"], True)
        self.assertEqual(data["scheduler"]["total"], 6)
        self.assertEqual(data["daily_report"]["report_time"], "12:30")
        self.assertIn("wxpusher", data)
        self.assertIn("background_tasks", data)

    @patch("warframe_agent.web.app.push_client")
    @patch("warframe_agent.web.app.feishu_bot")
    @patch("warframe_agent.web.app.monitor")
    def test_runtime_status_includes_safe_tasks_and_wxpusher_view(self, mock_monitor, mock_feishu, mock_push_client):
        from warframe_agent.conversation_log import ConversationEntry, log_conversation
        from warframe_agent.web import app as web_app
        import warframe_agent.conversation_log as conversation_log

        mock_feishu.status_snapshot.return_value = {"enabled": True, "configured": True, "available": True, "managed_running": True, "app_secret": "LEAK_SECRET", "chat_id": "oc_leak"}
        mock_monitor.scheduler_status_snapshot.return_value = {"running": True, "has_scheduler": True, "total": 1, "jobs": []}
        mock_monitor.daily_report_status_snapshot.return_value = {"enabled": True, "report_time": "12:30", "should_send_now": False, "last_report_date": None}
        mock_push_client.available = True
        mock_push_client.config.enabled = True
        mock_push_client.config.app_token = "AT_SECRET"
        mock_push_client.config.uids = ["UID_SECRET"]
        mock_push_client.config.push_alerts = True
        mock_push_client.config.push_watches = False
        mock_push_client.config.push_proactive = True
        mock_push_client.config.push_daily_report = True
        web_app._bg_tasks.clear()
        web_app._bg_tasks["task_secret"] = {
            "status": "error",
            "goal_id": "goal-1",
            "result": {"total": 99, "secret": "LEAK_RESULT"},
            "error": "token=secret-token Authorization: Bearer abc app_secret=hidden chat_id=oc_123",
            "created_at": time.time(),
        }
        with tempfile.TemporaryDirectory() as tmp:
            old_log_path = conversation_log.LOG_PATH
            conversation_log.LOG_PATH = Path(tmp) / "conversation_logs.jsonl"
            log_conversation(ConversationEntry(
                user_message="secret user message",
                assistant_reply="secret assistant reply",
                tool_calls=[{
                    "tool_name": "query_price",
                    "args_summary": {"item_name": "arcane_energize", "token": "SECRET_ARG"},
                    "ok": False,
                    "error": "Authorization: Bearer abc token=secret-token",
                    "duration_ms": 12.3,
                    "timestamp": "tool-time",
                    "message_context": "secret user message",
                    "prompt": "raw prompt",
                }],
            ))
            try:
                response = self.client.get("/api/runtime/status")
            finally:
                conversation_log.LOG_PATH = old_log_path
                web_app._bg_tasks.clear()

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["wxpusher"]["enabled"])
        self.assertTrue(data["wxpusher"]["configured"])
        self.assertTrue(data["wxpusher"]["available"])
        self.assertEqual(data["background_tasks"]["total"], 1)
        self.assertIn("recent_tool_calls", data)
        self.assertEqual(data["recent_tool_calls"]["count"], 1)
        self.assertEqual(data["recent_tool_calls"]["items"][0]["tool_name"], "query_price")
        self.assertIn("error_summary", data["recent_tool_calls"]["items"][0])
        task = data["background_tasks"]["tasks"][0]
        self.assertEqual(task["task_id"], "task_secret")
        self.assertEqual(task["status"], "error")
        self.assertEqual(task["goal_id"], "goal-1")
        self.assertIn("error_summary", task)
        serialized = str(data)
        for forbidden in ["AT_SECRET", "UID_SECRET", "LEAK_SECRET", "oc_leak", "LEAK_RESULT", "secret-token", "SECRET_ARG", "Bearer abc", "hidden", "oc_123", "token=", "app_secret=", "chat_id=", "secret user message", "secret assistant reply", "raw prompt", "message_context"]:
            self.assertNotIn(forbidden, serialized)

    def test_tool_call_history_api_returns_safe_filtered_records(self):
        from warframe_agent.conversation_log import ConversationEntry, log_conversation
        import warframe_agent.conversation_log as conversation_log

        with tempfile.TemporaryDirectory() as tmp:
            old_log_path = conversation_log.LOG_PATH
            conversation_log.LOG_PATH = Path(tmp) / "conversation_logs.jsonl"
            log_conversation(ConversationEntry(
                user_message="secret user message",
                assistant_reply="secret assistant reply",
                session_id="s1",
                timestamp="2026-05-18T10:00:00",
                tool_calls=[
                    {
                        "tool_name": "query_price",
                        "args_summary": {"item_name": "arcane_energize", "token": "SECRET_ARG"},
                        "ok": True,
                        "duration_ms": 10.5,
                        "timestamp": "tool-time-1",
                        "error": None,
                        "message_context": "secret user message",
                    },
                    {
                        "tool_name": "query_events",
                        "args_summary": {"source": "baro"},
                        "ok": False,
                        "duration_ms": 30,
                        "timestamp": "tool-time-2",
                        "error": "Authorization: Bearer abc token=secret-token",
                    },
                ],
            ))
            try:
                response = self.client.get("/api/tool-calls/history?tool_name=query_price&ok=true&limit=5")
            finally:
                conversation_log.LOG_PATH = old_log_path

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["tool_name"], "query_price")
        self.assertTrue(data["items"][0]["ok"])
        serialized = str(data)
        for forbidden in ["SECRET_ARG", "secret-token", "Bearer abc", "token=", "secret user message", "secret assistant reply", "message_context"]:
            self.assertNotIn(forbidden, serialized)

    def test_tool_call_stats_api_returns_safe_summary(self):
        from warframe_agent.conversation_log import ConversationEntry, log_conversation
        import warframe_agent.conversation_log as conversation_log

        with tempfile.TemporaryDirectory() as tmp:
            old_log_path = conversation_log.LOG_PATH
            conversation_log.LOG_PATH = Path(tmp) / "conversation_logs.jsonl"
            log_conversation(ConversationEntry(
                user_message="secret user message",
                assistant_reply="secret assistant reply",
                session_id="s1",
                tool_calls=[
                    {"tool_name": "query_price", "ok": True, "duration_ms": 10.0, "args_summary": {"token": "SECRET_ARG"}},
                    {"tool_name": "query_price", "ok": False, "duration_ms": 20.0, "error": "token=secret-token"},
                    {"tool_name": "query_events", "ok": True, "duration_ms": 30.0},
                ],
            ))
            try:
                response = self.client.get("/api/tool-calls/stats?limit=10")
            finally:
                conversation_log.LOG_PATH = old_log_path

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_calls"], 3)
        self.assertEqual(data["by_tool"]["query_price"]["total_calls"], 2)
        self.assertEqual(data["top_tools"][0]["tool_name"], "query_price")
        serialized = str(data)
        for forbidden in ["SECRET_ARG", "secret-token", "token=", "secret user message", "secret assistant reply"]:
            self.assertNotIn(forbidden, serialized)

    @patch("warframe_agent.web.app.TradingMemoryDB.open_readonly_if_exists")
    def test_memory_recall_api_returns_safe_trace(self, mock_open):
        db = TradingMemoryDB(db_path=Path(tempfile.gettempdir()) / "web_memory_recall_test.db")
        try:
            db.record_market_snapshot(
                "arcane_energize",
                "price_monitor.scan",
                {"item_id": "arcane_energize", "sell_price": 45, "buy_price": 38, "token": "secret-token", "seller": "Seller_RAW", "whisper": "/w Seller_RAW hi"},
            )
            mock_open.return_value = db

            response = self.client.get("/api/memory/recall?query=充沛机会&item_name=arcane_energize&intent=price_check&tool_names=query_price")
        finally:
            db.close()
            try:
                (Path(tempfile.gettempdir()) / "web_memory_recall_test.db").unlink()
            except OSError:
                pass

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["item_name"], "arcane_energize")
        self.assertIn("trace", data["items"][0])
        serialized = str(data)
        for forbidden in ["secret-token", "Seller_RAW", "/w", "token=", "whisper"]:
            self.assertNotIn(forbidden, serialized)

    @patch("warframe_agent.web.app.feishu_bot")
    @patch("warframe_agent.web.app.monitor")
    def test_runtime_status_degraded_when_enabled_feishu_not_running(self, mock_monitor, mock_feishu):
        mock_feishu.status_snapshot.return_value = {"enabled": True, "configured": True, "available": True, "managed_running": False}
        mock_monitor.scheduler_status_snapshot.return_value = {"running": True, "has_scheduler": True, "total": 6, "jobs": []}
        mock_monitor.daily_report_status_snapshot.return_value = {"enabled": True, "report_time": "12:30", "should_send_now": False, "last_report_date": None}

        response = self.client.get("/api/runtime/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "degraded")


class TestProactivePushBroadcast(unittest.IsolatedAsyncioTestCase):
    def _trade_plan(self):
        return {
            "source": "arcane_flip",
            "strategy": "arcane_r0_to_r5",
            "display_strategy": "买 21 个 R0 -> 合成 R5 -> 卖出",
            "item_id": "arcane_energize",
            "display_name": "Arcane Energize",
            "required_quantity": 21,
            "total_cost": 105,
            "total_revenue": 150,
            "profit": 45,
            "roi_pct": 42.9,
            "risk_level": "medium",
            "profit_bucket": "40_50",
            "plan_signature": "sig-ws",
            "buy_steps": [{
                "label": "买入 R0",
                "player": "SellerWS",
                "unit_price": 5,
                "quantity": 21,
                "subtotal": 105,
                "market_url": "https://warframe.market/items/arcane_energize",
                "profile_url": "https://warframe.market/profile/SellerWS",
                "whisper": "/w SellerWS Hi! I want to buy.",
            }],
            "sell_steps": [{
                "label": "出售 R5",
                "player": "BuyerWS",
                "unit_price": 150,
                "quantity": 1,
                "subtotal": 150,
                "market_url": "https://warframe.market/items/arcane_energize",
                "profile_url": "https://warframe.market/profile/BuyerWS",
                "whisper": "/w BuyerWS Hi! I want to sell.",
            }],
            "safe_summary": {
                "source": "arcane_flip",
                "strategy": "arcane_r0_to_r5",
                "item_id": "arcane_energize",
                "required_quantity": 21,
                "total_cost": 105,
                "total_revenue": 150,
                "profit": 45,
                "roi_pct": 42.9,
                "profit_bucket": "40_50",
                "plan_signature": "sig-ws",
            },
        }

    @patch("warframe_agent.web.app.PushConfig.load")
    @patch("warframe_agent.web.app.push_client")
    async def test_broadcast_proactive_push_skips_paused_opportunity(self, mock_client, mock_load):
        from warframe_agent.web import app as web_app

        mock_load.return_value = PushConfig(push_proactive=False)
        ws = AsyncMock()
        web_app.ws_connections.append(ws)
        try:
            await web_app.broadcast_proactive_push(ProactivePush(
                item_id="arcane_energize",
                item_display="Arcane Energize",
                push_type="opportunity",
                priority=2,
                message="机会",
                action_suggestion="watch",
            ))
        finally:
            web_app.ws_connections.remove(ws)

        ws.send_json.assert_not_called()
        mock_client.send_text.assert_not_called()

    @patch("warframe_agent.web.app.PushConfig.load")
    @patch("warframe_agent.web.app.push_client")
    async def test_broadcast_proactive_push_keeps_warning_when_opportunities_paused(self, mock_client, mock_load):
        from warframe_agent.web import app as web_app

        mock_load.return_value = PushConfig(push_proactive=False)
        mock_client.available = False
        ws = AsyncMock()
        web_app.ws_connections.append(ws)
        try:
            await web_app.broadcast_proactive_push(ProactivePush(
                item_id="arcane_energize",
                item_display="Arcane Energize",
                push_type="warning",
                priority=1,
                message="暴跌",
                action_suggestion="watch",
            ))
        finally:
            web_app.ws_connections.remove(ws)

        ws.send_json.assert_called_once()
        self.assertEqual(ws.send_json.call_args.args[0]["push_type"], "warning")

    @patch("warframe_agent.web.app.feishu_bot")
    @patch("warframe_agent.web.app.FeishuConfig.load")
    @patch("warframe_agent.web.app.PushConfig.load")
    @patch("warframe_agent.web.app.push_client")
    async def test_broadcast_proactive_push_formats_trade_plan_for_channels(self, mock_client, mock_load, mock_feishu_load, mock_feishu):
        from warframe_agent.web import app as web_app

        mock_load.return_value = PushConfig(push_proactive=True)
        mock_client.available = True
        mock_client.send_markdown = Mock(return_value=True)
        mock_feishu_load.return_value = SimpleNamespace(enabled=True)
        mock_feishu.available = True
        mock_feishu.send_card = Mock(return_value=True)
        chat_id_path = web_app.config.DATA_DIR / "feishu_chat_id.txt"
        old_chat_id = chat_id_path.read_text(encoding="utf-8") if chat_id_path.exists() else None
        chat_id_path.write_text("oc_trade_plan", encoding="utf-8")
        ws = AsyncMock()
        web_app.ws_connections.append(ws)
        try:
            await web_app.broadcast_proactive_push(ProactivePush(
                item_id="arcane_energize",
                item_display="Arcane Energize",
                push_type="opportunity",
                priority=2,
                message="利润 45p",
                action_suggestion="watch",
                data={"trade_plan": self._trade_plan()},
            ))
        finally:
            web_app.ws_connections.remove(ws)
            if old_chat_id is None:
                try:
                    chat_id_path.unlink()
                except FileNotFoundError:
                    pass
            else:
                chat_id_path.write_text(old_chat_id, encoding="utf-8")

        ws.send_json.assert_called_once()
        payload = ws.send_json.call_args.args[0]
        self.assertEqual(payload["trade_plan"]["required_quantity"], 21)
        self.assertEqual(payload["safe_summary"]["profit_bucket"], "40_50")
        self.assertNotIn("trade_plan", payload["data"])
        self.assertIn("SellerWS", str(payload["trade_plan"]))
        mock_client.send_markdown.assert_called_once()
        wx_title, wx_body = mock_client.send_markdown.call_args.args
        self.assertEqual(wx_title, "交易机会: Arcane Energize")
        self.assertIn("## 交易机会：Arcane Energize", wx_body)
        self.assertIn("SellerWS：5p × 21 = 105p", wx_body)
        self.assertIn("`/w BuyerWS Hi! I want to sell.`", wx_body)
        mock_client.send_text.assert_not_called()
        mock_feishu.send_card.assert_called_once()
        self.assertEqual(mock_feishu.send_card.call_args.args[0], "oc_trade_plan")
        self.assertIn("交易机会: Arcane Energize", mock_feishu.send_card.call_args.args[1])
        self.assertIn("SellerWS：5p × 21 = 105p", json.dumps(mock_feishu.send_card.call_args.args[2], ensure_ascii=False))


class TestWebSocketChatAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _assert_invalid_ws_payload(self, payload):
        with patch("warframe_agent.web.app.chat_agent") as mock_agent:
            with self.client.websocket_connect("/ws/chat") as websocket:
                if isinstance(payload, str):
                    websocket.send_text(payload)
                else:
                    websocket.send_json(payload)
                data = websocket.receive_json()

            self.assertEqual(data["status"], "error")
            self.assertIn("message", data)
            mock_agent.answer_stream.assert_not_called()
            mock_agent.answer.assert_not_called()

    def test_ws_chat_rejects_invalid_json_without_calling_agent(self):
        self._assert_invalid_ws_payload("{not-json")

    def test_ws_chat_rejects_non_object_payload_without_calling_agent(self):
        self._assert_invalid_ws_payload(["not", "object"])

    def test_ws_chat_rejects_missing_message_without_calling_agent(self):
        self._assert_invalid_ws_payload({})

    def test_ws_chat_rejects_non_string_message_without_calling_agent(self):
        self._assert_invalid_ws_payload({"message": 123})

    def test_ws_chat_rejects_blank_message_without_calling_agent(self):
        self._assert_invalid_ws_payload({"message": "   "})

    def test_ws_chat_rejects_overlong_message_without_calling_agent(self):
        self._assert_invalid_ws_payload({"message": "x" * 2001})

    @patch("warframe_agent.web.app.chat_agent")
    def test_ws_chat_valid_message_streams_tokens(self, mock_agent):
        async def fake_stream(message):
            yield "充沛"
            yield " 45p"

        mock_agent.answer_stream.side_effect = fake_stream

        with self.client.websocket_connect("/ws/chat") as websocket:
            websocket.send_json({"message": "  充沛多少钱  "})
            self.assertEqual(websocket.receive_json(), {"status": "processing"})
            self.assertEqual(websocket.receive_json(), {"token": "充沛"})
            self.assertEqual(websocket.receive_json(), {"token": " 45p"})
            self.assertEqual(websocket.receive_json(), {"done": True, "reply": "充沛 45p"})

        mock_agent.answer_stream.assert_called_once_with("充沛多少钱")
        mock_agent.answer.assert_not_called()


class TestConfigSecurityAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def assertNoRawSensitiveConfigKeys(self, data):
        raw_sensitive_keys = [
            key for key in data
            if any(marker in key.lower() for marker in ("token", "secret", "password"))
            and not key.endswith("_masked")
            and not key.endswith("_configured")
        ]
        self.assertEqual(raw_sensitive_keys, [])

    @patch("warframe_agent.web.app.PushConfig.load")
    def test_push_config_masks_and_allowlists_secret_fields(self, mock_load):
        raw_token = "AT_1234567890SECRET"
        mock_load.return_value = SimpleNamespace(
            enabled=True,
            app_token=raw_token,
            uids=["UID_123"],
            push_alerts=True,
            push_watches=False,
            push_proactive=True,
            push_daily_report=False,
            report_time="09:30",
            api_token="LEAK_TOKEN",
            webhook_secret="LEAK_SECRET",
            db_password="LEAK_PASSWORD",
        )

        response = self.client.get("/api/push/config")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["enabled"], True)
        self.assertEqual(data["uids"], ["UID_123"])
        self.assertEqual(data["report_time"], "09:30")
        self.assertTrue(data["app_token_configured"])
        self.assertIn("app_token_masked", data)
        self.assertNotEqual(data["app_token_masked"], raw_token)
        self.assertNoRawSensitiveConfigKeys(data)
        serialized = str(data)
        for forbidden in [raw_token, "LEAK_TOKEN", "LEAK_SECRET", "LEAK_PASSWORD"]:
            self.assertNotIn(forbidden, serialized)

    @patch("warframe_agent.web.app.FeishuConfig.load")
    def test_feishu_config_masks_and_allowlists_secret_fields(self, mock_load):
        raw_secret = "fs_app_secret_123456"
        mock_load.return_value = SimpleNamespace(
            enabled=True,
            app_id="cli_aabbcc",
            app_secret=raw_secret,
            access_token="LEAK_TOKEN",
            signing_secret="LEAK_SECRET",
            admin_password="LEAK_PASSWORD",
        )

        response = self.client.get("/api/feishu/config")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["enabled"], True)
        self.assertEqual(data["app_id"], "cli_aabbcc")
        self.assertTrue(data["app_secret_configured"])
        self.assertIn("app_secret_masked", data)
        self.assertNotEqual(data["app_secret_masked"], raw_secret)
        self.assertNoRawSensitiveConfigKeys(data)
        serialized = str(data)
        for forbidden in [raw_secret, "LEAK_TOKEN", "LEAK_SECRET", "LEAK_PASSWORD"]:
            self.assertNotIn(forbidden, serialized)


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


class TestDucatAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("warframe_agent.web.app.fetch_orders_async", new_callable=AsyncMock)
    @patch("warframe_agent.web.app.game_data")
    def test_ducat_endpoint_uses_authoritative_game_data(self, mock_game_data, mock_fetch_orders):
        mock_game_data.get_ducat_value.return_value = 100
        mock_fetch_orders.return_value = [
            {
                "order_type": "sell",
                "platinum": 20,
                "quantity": 1,
                "user": {"ingame_name": "Seller1", "status": "ingame", "reputation": 5},
            }
        ]

        response = self.client.get("/api/ducats/known_prime_part")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["has_ducat"])
        self.assertEqual(data["ducat_value"], 100)
        self.assertEqual(data["efficiency"]["ducats_per_plat"], 5)
        self.assertEqual(data["recommendation"], "建议拆成杜卡特")
        mock_game_data.get_ducat_value.assert_called_once_with("known_prime_part")

    @patch("warframe_agent.web.app.fetch_orders_async", new_callable=AsyncMock)
    @patch("warframe_agent.web.app.game_data")
    def test_unknown_prime_part_is_not_guessed_as_45_ducats(self, mock_game_data, mock_fetch_orders):
        mock_game_data.get_ducat_value.return_value = None

        response = self.client.get("/api/ducats/mystery_prime_blueprint")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["has_ducat"])
        self.assertNotIn("ducat_value", data)
        self.assertNotIn("recommendation", data)
        self.assertIn("暂无可靠杜卡特数据", data["message"])
        mock_fetch_orders.assert_not_called()

    @patch("warframe_agent.web.app.game_data")
    def test_unknown_arcane_is_not_guessed_as_100_ducats(self, mock_game_data):
        mock_game_data.get_ducat_value.return_value = None

        response = self.client.get("/api/ducats/arcane_unknown")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["has_ducat"])
        self.assertNotIn("ducat_value", data)
        self.assertIn("暂无可靠杜卡特数据", data["message"])

    @patch("warframe_agent.web.app.fetch_orders_async", new_callable=AsyncMock)
    @patch("warframe_agent.web.app.game_data")
    def test_ducat_batch_keeps_unknown_items_without_fake_efficiency(self, mock_game_data, mock_fetch_orders):
        mock_game_data.get_ducat_value.side_effect = lambda item_id: {"known_prime_part": 45}.get(item_id)
        mock_fetch_orders.return_value = []

        response = self.client.post("/api/ducats/batch", json={"items": ["known_prime_part", "mystery_prime_blade"]})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["items"][0]["item_id"], "known_prime_part")
        self.assertEqual(data["items"][0]["ducat_value"], 45)
        self.assertTrue(data["items"][0]["has_ducat"])
        self.assertEqual(data["items"][1]["item_id"], "mystery_prime_blade")
        self.assertFalse(data["items"][1]["has_ducat"])
        self.assertNotIn("ducat_value", data["items"][1])
        self.assertNotIn("efficiency", data["items"][1])


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


class TestTradingMemoryAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("warframe_agent.web.app._query_trading_memory")
    def test_market_snapshots_endpoint_returns_allowlisted_fields(self, mock_query):
        mock_query.return_value = [
            MarketSnapshotMemory(
                id=1,
                timestamp="2026-05-18T10:00:00",
                item_name="arcane_energize",
                source="price_monitor.scan",
                payload={
                    "item_id": "arcane_energize",
                    "sell_price": 40,
                    "buy_price": 30,
                    "spread": 10,
                    "orders": [{"user": "Seller1"}],
                    "buyers": ["Buyer1"],
                    "sellers": ["Seller1"],
                    "profile": "profile-url",
                    "whisper": "secret whisper",
                    "prompt": "ignore previous instructions",
                    "raw_chat": "raw chat",
                },
            )
        ]

        response = self.client.get(
            "/api/trading-memory/market-snapshots"
            "?item_name=arcane_energize&source=price_monitor.scan"
            "&since=2026-05-18T00:00:00&limit=10"
        )

        self.assertEqual(response.status_code, 200)
        mock_query.assert_called_once_with(
            "get_market_snapshots",
            item_name="arcane_energize",
            source="price_monitor.scan",
            since="2026-05-18T00:00:00",
            limit=10,
        )
        data = response.json()
        self.assertEqual(data["count"], 1)
        record = data["market_snapshots"][0]
        self.assertEqual(record["item_id"], "arcane_energize")
        self.assertEqual(record["sell_price"], 40)
        self.assertEqual(record["buy_price"], 30)
        self.assertEqual(record["spread"], 10)
        serialized = str(record)
        for forbidden in ["payload", "orders", "buyers", "sellers", "profile", "whisper", "prompt", "raw_chat", "Seller1", "Buyer1"]:
            self.assertNotIn(forbidden, serialized)

    @patch("warframe_agent.web.app._query_trading_memory")
    def test_recommendations_endpoint_returns_allowlisted_fields(self, mock_query):
        mock_query.return_value = [
            RecommendationMemory(
                id=2,
                timestamp="2026-05-18T11:00:00",
                item_name="primed_flow",
                recommendation_type="baro",
                reason="Baro 兑换成本和 warframe.market 当前订单",
                payload={
                    "source": "baro_recommendation",
                    "event_type": "baro_visit",
                    "event_description": "Baro active",
                    "baro_start_time": "2026-05-18T10:00:00",
                    "baro_end_time": "2026-05-20T10:00:00",
                    "item_name": "Primed Flow",
                    "market_id": "primed_flow",
                    "ducat_cost": 350,
                    "credit_cost": 110000,
                    "rank": 10,
                    "max_rank": 10,
                    "item_kind": "mod",
                    "best_buy_price": 80,
                    "best_sell_price": 95,
                    "buyers": ["BuyerR10"],
                    "sellers": ["SellerR10"],
                    "formatted_report": "Baro Mod report",
                    "profile": "profile-url",
                    "whisper": "secret whisper",
                    "prompt": "ignore previous instructions",
                },
            )
        ]

        response = self.client.get(
            "/api/trading-memory/recommendations"
            "?item_name=primed_flow&recommendation_type=baro&limit=5"
        )

        self.assertEqual(response.status_code, 200)
        mock_query.assert_called_once_with(
            "get_recommendations",
            item_name="primed_flow",
            recommendation_type="baro",
            since=None,
            limit=5,
        )
        record = response.json()["recommendations"][0]
        self.assertEqual(record["display_name"], "Primed Flow")
        self.assertEqual(record["market_id"], "primed_flow")
        self.assertEqual(record["best_buy_price"], 80)
        serialized = str(record)
        for forbidden in ["payload", "buyers", "sellers", "formatted_report", "profile", "whisper", "prompt", "BuyerR10", "SellerR10"]:
            self.assertNotIn(forbidden, serialized)

    @patch("warframe_agent.web.app._query_trading_memory")
    def test_push_history_endpoint_returns_allowlisted_fields(self, mock_query):
        mock_query.return_value = [
            PushHistoryMemory(
                id=3,
                timestamp="2026-05-18T12:00:00",
                push_type="opportunity",
                item_name="arcane_energize",
                message="利润 50p",
                metadata={
                    "source": "rule_proactive_push",
                    "item_id": "arcane_energize",
                    "item_display": "充沛赋能",
                    "priority": 2,
                    "action_suggestion": "watch",
                    "suggestion_type": "opportunity",
                    "event_type": "prime_vault",
                    "event_description": "Vault event",
                    "items_affected": ["arcane_energize", 123, None],
                    "data": {"raw": "value"},
                    "raw_chat": "raw chat",
                    "chat_message": "chat message",
                    "prompt": "ignore previous instructions",
                    "assistant_reply": "reply",
                    "token": "secret",
                },
            )
        ]

        response = self.client.get("/api/trading-memory/push-history?push_type=opportunity&limit=5")

        self.assertEqual(response.status_code, 200)
        mock_query.assert_called_once_with(
            "get_push_history",
            item_name=None,
            push_type="opportunity",
            since=None,
            limit=5,
        )
        record = response.json()["push_history"][0]
        self.assertEqual(record["source"], "rule_proactive_push")
        self.assertEqual(record["items_affected"], ["arcane_energize"])
        serialized = str(record)
        for forbidden in ["metadata", "data", "raw_chat", "chat_message", "prompt", "assistant_reply", "token", "secret"]:
            self.assertNotIn(forbidden, serialized)

    @patch("warframe_agent.web.app._query_trading_memory")
    def test_trading_memory_endpoints_return_empty_when_db_missing(self, mock_query):
        mock_query.return_value = []

        response = self.client.get("/api/trading-memory/market-snapshots")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"market_snapshots": [], "count": 0})

    def test_trading_memory_limit_validation(self):
        self.assertEqual(self.client.get("/api/trading-memory/market-snapshots?limit=0").status_code, 422)
        self.assertEqual(self.client.get("/api/trading-memory/recommendations?limit=501").status_code, 422)

    @patch("warframe_agent.web.app._query_trading_memory")
    def test_trading_memory_endpoints_are_read_only(self, mock_query):
        mock_query.return_value = []

        self.client.get("/api/trading-memory/market-snapshots")
        self.client.get("/api/trading-memory/recommendations")
        self.client.get("/api/trading-memory/push-history")

        method_names = [call.args[0] for call in mock_query.call_args_list]
        self.assertEqual(method_names, ["get_market_snapshots", "get_recommendations", "get_push_history"])
        for method_name in method_names:
            self.assertFalse(method_name.startswith("record_"))
            self.assertNotEqual(method_name, "cleanup_old_data")

    @patch("warframe_agent.web.app._query_trading_memory")
    def test_user_query_memory_endpoint_is_not_exposed(self, mock_query):
        response = self.client.get("/api/trading-memory/user-queries")

        self.assertEqual(response.status_code, 404)
        mock_query.assert_not_called()


class TestSchedulerStatusAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("warframe_agent.web.app.monitor")
    def test_scheduler_status_endpoint_returns_monitor_snapshot(self, mock_monitor):
        snapshot = {
            "running": True,
            "has_scheduler": True,
            "total": 1,
            "jobs": [
                {
                    "job_id": "price_monitor.scan",
                    "name": "Price monitor scan",
                    "enabled": True,
                    "schedule": {"type": "interval", "seconds": 60, "run_immediately": True},
                    "next_run_at": "2026-05-17T10:00:00",
                    "last_run_at": None,
                    "run_count": 0,
                    "error_count": 0,
                }
            ],
        }
        mock_monitor.scheduler_status_snapshot.return_value = snapshot

        response = self.client.get("/api/scheduler/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), snapshot)
        mock_monitor.scheduler_status_snapshot.assert_called_once_with()

    @patch("warframe_agent.web.app.monitor")
    def test_scheduler_status_endpoint_is_read_only(self, mock_monitor):
        mock_monitor.scheduler_status_snapshot.return_value = {
            "running": False,
            "has_scheduler": False,
            "total": 0,
            "jobs": [],
        }
        mock_monitor._scheduler = MagicMock()

        response = self.client.get("/api/scheduler/status")

        self.assertEqual(response.status_code, 200)
        mock_monitor.scheduler_status_snapshot.assert_called_once_with()
        mock_monitor.start.assert_not_called()
        mock_monitor.stop.assert_not_called()
        mock_monitor._build_scheduler.assert_not_called()
        mock_monitor._scheduler.tick.assert_not_called()


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
