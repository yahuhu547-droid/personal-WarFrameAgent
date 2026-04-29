import tempfile
import time
import unittest
from pathlib import Path

from warframe_agent.memory import AgentMemory
from warframe_agent.monitor import PriceMonitor, AlertNotification, ScanResult


FAKE_ORDERS = [
    {"order_type": "sell", "platinum": 40, "quantity": 1, "user": {"ingame_name": "Seller1", "status": "ingame", "reputation": 5}},
    {"order_type": "buy", "platinum": 30, "quantity": 1, "user": {"ingame_name": "Buyer1", "status": "ingame", "reputation": 3}},
]

EXPENSIVE_ORDERS = [
    {"order_type": "sell", "platinum": 100, "quantity": 1, "user": {"ingame_name": "Seller2", "status": "ingame", "reputation": 5}},
]


class MonitorScanTests(unittest.TestCase):
    def _setup_memory(self, tmp_dir: str) -> Path:
        memory_path = Path(tmp_dir) / "memory.json"
        memory = AgentMemory.default()
        memory = memory.with_favorite_item("arcane_energize")
        memory = memory.with_price_alert("arcane_energize", "below", 45, "充沛低于45提醒")
        memory.save(memory_path)
        return memory_path

    def test_scan_once_detects_triggered_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
            )
            result = monitor.scan_once()

        self.assertEqual(len(result.triggered_alerts), 1)
        self.assertEqual(result.triggered_alerts[0].current_price, 40)
        self.assertIn("充沛", result.triggered_alerts[0].alert.note)

    def test_scan_once_ignores_non_triggered_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: EXPENSIVE_ORDERS,
                memory_path=memory_path,
            )
            result = monitor.scan_once()

        self.assertEqual(len(result.triggered_alerts), 0)

    def test_scan_once_collects_favorite_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
            )
            result = monitor.scan_once()

        self.assertEqual(len(result.favorite_snapshots), 1)
        self.assertEqual(result.favorite_snapshots[0].sell_price, 40)
        self.assertEqual(result.favorite_snapshots[0].buy_price, 30)

    def test_scan_once_handles_network_error_gracefully(self):
        def failing_fetcher(item_id):
            raise ConnectionError("network down")

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=failing_fetcher,
                memory_path=memory_path,
            )
            result = monitor.scan_once()

        self.assertEqual(len(result.triggered_alerts), 0)
        self.assertTrue(len(result.errors) > 0)

    def test_drain_notifications_clears_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                interval_seconds=1,
            )
            monitor.start()
            time.sleep(2)
            first = monitor.drain_notifications()
            second = monitor.drain_notifications()
            monitor.stop()

        self.assertTrue(len(first) > 0)
        self.assertEqual(len(second), 0)

    def test_monitor_thread_starts_and_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: [],
                memory_path=memory_path,
                interval_seconds=60,
            )
            monitor.start()
            self.assertTrue(monitor._thread.is_alive())
            monitor.stop()
            self.assertFalse(monitor._thread.is_alive())


class ScanCommandTests(unittest.TestCase):
    def test_scan_command_shows_favorite_prices(self):
        from warframe_agent.chat import ChatAgent

        class FakeResolver:
            aliases = {}
            generated_aliases = {}
            def resolve(self, name):
                raise LookupError(name)

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default().with_favorite_item("arcane_energize")
            memory.save(memory_path)
            agent = ChatAgent(
                resolver=FakeResolver(),
                order_fetcher=lambda item_id: FAKE_ORDERS,
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )
            answer = agent.answer("/scan")

        self.assertIn("扫描结果", answer)
        self.assertIn("40p", answer)

    def test_scan_command_shows_triggered_alerts(self):
        from warframe_agent.chat import ChatAgent

        class FakeResolver:
            aliases = {}
            generated_aliases = {}
            def resolve(self, name):
                raise LookupError(name)

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default()
            memory = memory.with_price_alert("arcane_energize", "below", 45, "充沛低于45提醒")
            memory.save(memory_path)
            agent = ChatAgent(
                resolver=FakeResolver(),
                order_fetcher=lambda item_id: FAKE_ORDERS,
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )
            answer = agent.answer("/scan")

        self.assertIn("触发的提醒", answer)
        self.assertIn("40p", answer)

    def test_scan_command_empty_lists(self):
        from warframe_agent.chat import ChatAgent

        class FakeResolver:
            aliases = {}
            generated_aliases = {}
            def resolve(self, name):
                raise LookupError(name)

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            AgentMemory.default().save(memory_path)
            agent = ChatAgent(
                resolver=FakeResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )
            answer = agent.answer("/scan")

        self.assertIn("关注列表和提醒均为空", answer)


if __name__ == "__main__":
    unittest.main()
