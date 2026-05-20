import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from warframe_agent import config
from warframe_agent.events import BaroItem, GameEvent
from warframe_agent.memory import AgentMemory
from warframe_agent.memory import ProactiveSuggestion
from warframe_agent.monitor import (
    PRICE_MONITOR_DAILY_REPORT_JOB_ID,
    PRICE_MONITOR_EVENT_CHECKS_JOB_ID,
    PRICE_MONITOR_GOAL_GENERATION_JOB_ID,
    PRICE_MONITOR_KNOWLEDGE_UPDATE_JOB_ID,
    PRICE_MONITOR_SCAN_JOB_ID,
    PRICE_MONITOR_SELF_LEARNING_JOB_ID,
    PriceMonitor,
    AlertNotification,
    ScanResult,
    _unique_suggestions,
)


FAKE_ORDERS = [
    {"order_type": "sell", "platinum": 40, "quantity": 1, "user": {"ingame_name": "Seller1", "status": "ingame", "reputation": 5}},
    {"order_type": "buy", "platinum": 30, "quantity": 1, "user": {"ingame_name": "Buyer1", "status": "ingame", "reputation": 3}},
]

EXPENSIVE_ORDERS = [
    {"order_type": "sell", "platinum": 100, "quantity": 1, "user": {"ingame_name": "Seller2", "status": "ingame", "reputation": 5}},
]

BUY_ONLY_ORDERS = [
    {"order_type": "buy", "platinum": 25, "quantity": 1, "user": {"ingame_name": "BuyerOnly", "status": "ingame", "reputation": 4}},
]

CHANGED_ORDERS = [
    {"order_type": "sell", "platinum": 45, "quantity": 1, "user": {"ingame_name": "SellerChanged", "status": "ingame", "reputation": 5}},
    {"order_type": "buy", "platinum": 30, "quantity": 1, "user": {"ingame_name": "BuyerChanged", "status": "ingame", "reputation": 3}},
]

BARO_ORDERS = [
    {"type": "sell", "platinum": 95, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "SellerR10", "status": "ingame", "reputation": 4}},
    {"type": "buy", "platinum": 80, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "BuyerR10", "status": "ingame", "reputation": 3}},
]


def _baro_event(start_time: str = "2026-05-18T10:00:00") -> GameEvent:
    return GameEvent(
        event_type="baro_visit",
        description="Baro active",
        start_time=start_time,
        end_time="2026-05-20T10:00:00",
        baro_items=[
            BaroItem(
                item_type="/Lotus/Upgrades/Mods/PrimedFlow",
                item_name="Primed Flow",
                market_id="primed_flow",
                ducat_cost=350,
                credit_cost=110000,
            ),
        ],
    )


class MonitorScanTests(unittest.TestCase):
    def test_unique_suggestions_uses_dedupe_key_source_and_strategy(self):
        suggestions = [
            ProactiveSuggestion(
                item_id="carrier_prime_set",
                suggestion_type="goal_opportunity",
                priority=1,
                message="set strategy",
                data={"source": "set_profit", "strategy": "buy_parts_sell_set"},
            ),
            ProactiveSuggestion(
                item_id="carrier_prime_set",
                suggestion_type="goal_opportunity",
                priority=1,
                message="investment strategy",
                data={"source": "investment", "strategy": "buy_parts_sell_set"},
            ),
            ProactiveSuggestion(
                item_id="carrier_prime_set",
                suggestion_type="goal_opportunity",
                priority=1,
                message="duplicate key first",
                data={"dedupe_key": "same-opportunity", "source": "set_profit", "strategy": "buy_set_sell_parts"},
            ),
            ProactiveSuggestion(
                item_id="carrier_prime_set",
                suggestion_type="goal_opportunity",
                priority=1,
                message="duplicate key second",
                data={"dedupe_key": "same-opportunity", "source": "investment", "strategy": "buy_set_sell_parts"},
            ),
        ]

        unique = _unique_suggestions(suggestions)

        self.assertEqual([item.message for item in unique], ["set strategy", "investment strategy", "duplicate key first"])

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

    def test_monitor_builds_scheduler_with_immediate_scan_and_event_checks_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                interval_seconds=60,
            )
            scheduler = monitor._build_scheduler()
            scan_job = scheduler.get_job(PRICE_MONITOR_SCAN_JOB_ID)
            event_job = scheduler.get_job(PRICE_MONITOR_EVENT_CHECKS_JOB_ID)
            daily_job = scheduler.get_job(PRICE_MONITOR_DAILY_REPORT_JOB_ID)

        self.assertIsNotNone(scan_job)
        self.assertIsNotNone(event_job)
        self.assertIsNotNone(daily_job)
        self.assertEqual(scan_job.schedule.seconds, 60)
        self.assertEqual(event_job.schedule.seconds, 60)
        self.assertEqual(daily_job.schedule.seconds, 60)
        self.assertTrue(scan_job.schedule.run_immediately)
        self.assertTrue(event_job.schedule.run_immediately)
        self.assertFalse(daily_job.schedule.run_immediately)
        self.assertEqual(
            [job.job_id for job in scheduler.due_jobs()],
            [PRICE_MONITOR_SCAN_JOB_ID, PRICE_MONITOR_EVENT_CHECKS_JOB_ID],
        )

    def test_monitor_builds_scheduler_with_deferred_maintenance_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                interval_seconds=60,
            )
            scheduler = monitor._build_scheduler()
            knowledge_job = scheduler.get_job(PRICE_MONITOR_KNOWLEDGE_UPDATE_JOB_ID)
            goal_job = scheduler.get_job(PRICE_MONITOR_GOAL_GENERATION_JOB_ID)
            self_learning_job = scheduler.get_job(PRICE_MONITOR_SELF_LEARNING_JOB_ID)

        self.assertIsNotNone(knowledge_job)
        self.assertIsNotNone(goal_job)
        self.assertIsNotNone(self_learning_job)
        self.assertEqual(knowledge_job.schedule.seconds, 60 * config.KNOWLEDGE_UPDATE_INTERVAL)
        self.assertEqual(goal_job.schedule.seconds, 60 * config.GOAL_GENERATION_INTERVAL)
        self.assertEqual(self_learning_job.schedule.seconds, 60 * config.PATTERN_DISCOVERY_INTERVAL)
        self.assertFalse(knowledge_job.schedule.run_immediately)
        self.assertFalse(goal_job.schedule.run_immediately)
        self.assertFalse(self_learning_job.schedule.run_immediately)
        self.assertEqual(
            [job.job_id for job in scheduler.due_jobs()],
            [PRICE_MONITOR_SCAN_JOB_ID, PRICE_MONITOR_EVENT_CHECKS_JOB_ID],
        )

    def test_scheduler_status_snapshot_returns_empty_before_scheduler_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            snapshot = monitor.scheduler_status_snapshot()

        self.assertFalse(snapshot["running"])
        self.assertFalse(snapshot["has_scheduler"])
        self.assertEqual(snapshot["total"], 0)
        self.assertEqual(snapshot["jobs"], [])

    def test_scheduler_status_snapshot_serializes_existing_scheduler_without_running_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            scheduler = monitor._build_scheduler()
            monitor._scheduler = scheduler
            before_counts = [job.run_count for job in scheduler.list_jobs()]
            snapshot = monitor.scheduler_status_snapshot()
            after_counts = [job.run_count for job in scheduler.list_jobs()]

        self.assertTrue(snapshot["has_scheduler"])
        self.assertFalse(snapshot["running"])
        self.assertEqual(snapshot["total"], 6)
        self.assertEqual(
            [job["job_id"] for job in snapshot["jobs"]],
            [
                PRICE_MONITOR_SCAN_JOB_ID,
                PRICE_MONITOR_EVENT_CHECKS_JOB_ID,
                PRICE_MONITOR_DAILY_REPORT_JOB_ID,
                PRICE_MONITOR_KNOWLEDGE_UPDATE_JOB_ID,
                PRICE_MONITOR_GOAL_GENERATION_JOB_ID,
                PRICE_MONITOR_SELF_LEARNING_JOB_ID,
            ],
        )
        self.assertEqual(before_counts, [0, 0, 0, 0, 0, 0])
        self.assertEqual(after_counts, before_counts)
        self.assertTrue(all(job["last_run_at"] is None for job in snapshot["jobs"]))
        self.assertTrue(all("running" in job for job in snapshot["jobs"]))
        self.assertTrue(all("last_success" in job for job in snapshot["jobs"]))
        self.assertTrue(all("safety_level" in job for job in snapshot["jobs"]))
        self.assertTrue(all(job["external_side_effect"] is False for job in snapshot["jobs"]))

    def test_scheduler_status_snapshot_includes_last_result_without_sensitive_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            scheduler = monitor._build_scheduler()
            monitor._scheduler = scheduler

            def failing_scan():
                raise RuntimeError("token=secret-token cookie=sid-secret authorization=Bearer abc app_secret=hidden chat_id=oc_123")

            scheduler.get_job(PRICE_MONITOR_SCAN_JOB_ID).callback = failing_scan
            scheduler.tick()
            snapshot = monitor.scheduler_status_snapshot()

        scan_job = snapshot["jobs"][0]
        self.assertFalse(scan_job["last_success"])
        self.assertIn("RuntimeError", scan_job["last_error_summary"])
        serialized = str(snapshot)
        for forbidden in ["secret-token", "sid-secret", "Bearer abc", "hidden", "oc_123", "token=", "cookie=", "app_secret=", "chat_id="]:
            self.assertNotIn(forbidden, serialized)

    def test_daily_report_job_calls_check_daily_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path, interval_seconds=60)
            monitor._check_daily_report = MagicMock()
            scheduler = monitor._build_scheduler()
            job = scheduler.get_job(PRICE_MONITOR_DAILY_REPORT_JOB_ID)

        self.assertIsNotNone(job)
        job.callback()
        monitor._check_daily_report.assert_called_once_with()

    @patch("warframe_agent.push.should_send_daily_report", return_value=True)
    @patch("warframe_agent.push.PushConfig.load")
    def test_daily_report_status_snapshot(self, load_config, should_send):
        cfg = MagicMock()
        cfg.enabled = True
        cfg.push_daily_report = True
        cfg.report_time = "12:30"
        load_config.return_value = cfg
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            monitor._last_report_date = "2026-05-19"
            snapshot = monitor.daily_report_status_snapshot()

        self.assertTrue(snapshot["enabled"])
        self.assertEqual(snapshot["report_time"], "12:30")
        self.assertTrue(snapshot["should_send_now"])
        self.assertEqual(snapshot["last_report_date"], "2026-05-19")
        should_send.assert_called_once_with(cfg)

    def test_run_scan_cycle_preserves_alert_queue_and_callback_behavior(self):
        callbacks = []
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                on_alert=callbacks.append,
            )
            monitor._run_scan_cycle()
            first = monitor.drain_notifications()
            second = monitor.drain_notifications()

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].current_price, 40)
        self.assertEqual(len(second), 0)

    def test_scheduler_first_tick_runs_scan_before_event_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path, interval_seconds=60)
            calls = []

            def scan_cycle():
                calls.append("scan")
                monitor._scan_cycle_count += 1

            def event_checks():
                calls.append("event_checks")

            monitor._run_scan_cycle = scan_cycle
            monitor._run_event_checks_job = event_checks
            scheduler = monitor._build_scheduler()
            results = scheduler.tick()

        self.assertEqual(calls, ["scan", "event_checks"])
        self.assertEqual(
            [result.job_id for result in results],
            [PRICE_MONITOR_SCAN_JOB_ID, PRICE_MONITOR_EVENT_CHECKS_JOB_ID],
        )

    def test_event_checks_job_calls_event_checks_in_existing_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            monitor._scan_cycle_count = 1
            calls = []
            with patch.object(monitor, "_check_fissure_alerts", side_effect=lambda: calls.append("fissure")), \
                 patch.object(monitor, "_check_cycle_alerts", side_effect=lambda: calls.append("cycle")), \
                 patch.object(monitor, "_check_baro_recommendation", side_effect=lambda: calls.append("baro")), \
                 patch.object(monitor, "_check_event_driven_push", side_effect=lambda: calls.append("event_driven")), \
                 patch.object(monitor, "_check_daily_report", side_effect=lambda: calls.append("daily")):
                monitor._run_event_checks_job()

        self.assertEqual(calls, ["fissure", "cycle", "baro", "event_driven", "daily"])

    def test_run_scan_cycle_records_latest_scan_without_inline_maintenance_or_event_checks(self):
        callbacks = []
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                on_alert=callbacks.append,
            )
            with patch.object(config, "KNOWLEDGE_UPDATE_INTERVAL", 1), \
                 patch.object(config, "GOAL_GENERATION_INTERVAL", 1), \
                 patch.object(config, "PATTERN_DISCOVERY_INTERVAL", 1), \
                 patch.object(monitor, "_run_knowledge_update") as knowledge_update, \
                 patch.object(monitor, "_run_goal_generation") as goal_generation, \
                 patch.object(monitor, "_run_self_learning") as self_learning, \
                 patch.object(monitor, "_check_fissure_alerts") as fissure_alerts, \
                 patch.object(monitor, "_check_cycle_alerts") as cycle_alerts, \
                 patch.object(monitor, "_check_baro_recommendation") as baro_recommendation, \
                 patch.object(monitor, "_check_event_driven_push") as event_driven_push, \
                 patch.object(monitor, "_check_daily_report") as daily_report:
                monitor._run_scan_cycle()
            first = monitor.drain_notifications()

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(first), 1)
        self.assertIsNotNone(monitor._last_scan_result)
        knowledge_update.assert_not_called()
        goal_generation.assert_not_called()
        self_learning.assert_not_called()
        fissure_alerts.assert_not_called()
        cycle_alerts.assert_not_called()
        baro_recommendation.assert_not_called()
        event_driven_push.assert_not_called()
        daily_report.assert_not_called()

    def test_event_checks_job_skips_before_completed_scan_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            with patch.object(monitor, "_check_fissure_alerts") as fissure_alerts, \
                 patch.object(monitor, "_check_cycle_alerts") as cycle_alerts, \
                 patch.object(monitor, "_check_baro_recommendation") as baro_recommendation, \
                 patch.object(monitor, "_check_event_driven_push") as event_driven_push, \
                 patch.object(monitor, "_check_daily_report") as daily_report:
                monitor._run_event_checks_job()

        fissure_alerts.assert_not_called()
        cycle_alerts.assert_not_called()
        baro_recommendation.assert_not_called()
        event_driven_push.assert_not_called()
        daily_report.assert_not_called()

    def test_event_checks_job_logs_and_reraises_unhandled_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            monitor._scan_cycle_count = 1
            with patch.object(monitor, "_check_fissure_alerts", side_effect=RuntimeError("boom")):
                with self.assertLogs("warframe_agent.monitor", level="WARNING") as logs:
                    with self.assertRaises(RuntimeError):
                        monitor._run_event_checks_job()

        self.assertTrue(any("事件检查任务异常" in message for message in logs.output))

    def test_knowledge_update_job_uses_latest_successful_scan_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            scan = ScanResult()
            monitor._last_scan_result = scan
            with patch.object(monitor, "_run_knowledge_update") as knowledge_update:
                monitor._run_knowledge_update_job()

        knowledge_update.assert_called_once_with(scan)

    def test_knowledge_update_job_skips_before_first_successful_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            with patch.object(monitor, "_run_knowledge_update") as knowledge_update:
                monitor._run_knowledge_update_job()

        knowledge_update.assert_not_called()

    def test_self_learning_job_loads_fresh_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(memory_path=memory_path)
            loaded_memory = AgentMemory.default()
            with patch("warframe_agent.monitor.AgentMemory.load", return_value=loaded_memory) as load_memory, \
                 patch.object(monitor, "_run_self_learning") as self_learning:
                monitor._run_self_learning_job()

        load_memory.assert_called_once_with(monitor.memory_path)
        self_learning.assert_called_once_with(loaded_memory)

    def test_run_scan_cycle_exception_is_logged_and_does_not_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
            )

            def failing_scan_once():
                raise RuntimeError("scan failed")

            monitor.scan_once = failing_scan_once
            with self.assertLogs("warframe_agent.monitor", level="WARNING") as logs:
                monitor._run_scan_cycle()

        self.assertTrue(any("监控主循环异常" in message for message in logs.output))

    def test_monitor_start_is_idempotent_with_scheduler(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: [],
                memory_path=memory_path,
                interval_seconds=60,
            )
            monitor.start()
            first_thread = monitor._thread
            first_scheduler = monitor._scheduler
            monitor.start()

            self.assertIs(monitor._thread, first_thread)
            self.assertIs(monitor._scheduler, first_scheduler)
            self.assertTrue(monitor._thread.is_alive())
            monitor.stop()
            self.assertFalse(monitor._thread.is_alive())

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

    def test_scan_once_with_price_db_records_data(self):
        from warframe_agent.price_history import PriceHistoryDB

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            db = PriceHistoryDB(db_path=Path(tmp) / "prices.db")
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                price_db=db,
            )
            monitor.scan_once()
            snapshots = db.recent("arcane_energize")
            db.close()

            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].sell_price, 40)

    def test_scan_once_detects_watchlist_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default()
            memory = memory.with_watch_item("primed_flow", "川流不息 Prime")
            memory.save(memory_path)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
            )
            result = monitor.scan_once()

        self.assertEqual(len(result.favorite_snapshots), 1)
        self.assertEqual(result.favorite_snapshots[0].item_id, "primed_flow")

    def test_scan_once_records_market_snapshot_memory_for_favorite_item(self):
        from warframe_agent.trading_memory import TradingMemoryDB

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            db = TradingMemoryDB(db_path=Path(tmp) / "trading_memory.db")
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                trading_memory_db=db,
            )
            monitor.scan_once()
            records = db.get_market_snapshots(item_name="arcane_energize", source="price_monitor.scan")
            db.close()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].item_name, "arcane_energize")
        self.assertEqual(records[0].source, "price_monitor.scan")
        self.assertEqual(records[0].payload, {
            "source": "price_monitor.scan",
            "item_id": "arcane_energize",
            "sell_price": 40,
            "buy_price": 30,
            "spread": 10,
        })

    def test_scan_once_market_snapshot_memory_omits_private_watchlist_fields(self):
        from warframe_agent.trading_memory import TradingMemoryDB

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default().with_watch_item(
                "primed_flow",
                "用户自定义关注名 Prime",
                content="用户自定义关注内容 top3_buyers",
            )
            memory.save(memory_path)
            db = TradingMemoryDB(db_path=Path(tmp) / "trading_memory.db")
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                trading_memory_db=db,
            )
            monitor.scan_once()
            records = db.get_market_snapshots(item_name="primed_flow", source="price_monitor.scan")
            db.close()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].item_name, "primed_flow")
        payload = records[0].payload
        self.assertEqual(set(payload), {"source", "item_id", "sell_price", "buy_price", "spread"})
        serialized = json.dumps(payload, ensure_ascii=False)
        for forbidden in [
            "用户自定义关注名",
            "用户自定义关注内容",
            "Seller1",
            "Buyer1",
            "orders",
            "buyers",
            "sellers",
            "profile",
            "whisper",
            "prompt",
            "reply",
            "raw_chat",
        ]:
            self.assertNotIn(forbidden, serialized)

    def test_scan_once_skips_empty_market_snapshot_memory(self):
        from warframe_agent.trading_memory import TradingMemoryDB

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            db = TradingMemoryDB(db_path=Path(tmp) / "trading_memory.db")
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: [],
                memory_path=memory_path,
                trading_memory_db=db,
            )
            result = monitor.scan_once()
            records = db.get_market_snapshots(item_name="arcane_energize", source="price_monitor.scan")
            db.close()

        self.assertEqual(len(result.favorite_snapshots), 1)
        self.assertEqual(len(records), 0)

    def test_scan_once_records_one_sided_market_snapshot_memory(self):
        from warframe_agent.trading_memory import TradingMemoryDB

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            db = TradingMemoryDB(db_path=Path(tmp) / "trading_memory.db")
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: BUY_ONLY_ORDERS,
                memory_path=memory_path,
                trading_memory_db=db,
            )
            monitor.scan_once()
            records = db.get_market_snapshots(item_name="arcane_energize", source="price_monitor.scan")
            db.close()

        self.assertEqual(len(records), 1)
        payload = records[0].payload
        self.assertIsNone(payload["sell_price"])
        self.assertEqual(payload["buy_price"], 25)
        self.assertIsNone(payload["spread"])

    def test_market_snapshot_memory_write_failure_does_not_block_scan_once(self):
        failing_db = MagicMock()
        failing_db.record_market_snapshot.side_effect = RuntimeError("db down")
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                trading_memory_db=failing_db,
            )
            result = monitor.scan_once()

        self.assertEqual(len(result.favorite_snapshots), 1)
        failing_db.record_market_snapshot.assert_called_once()

    def test_market_snapshot_memory_skips_exact_duplicate_within_rate_limit(self):
        from warframe_agent.trading_memory import TradingMemoryDB

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = self._setup_memory(tmp)
            db = TradingMemoryDB(db_path=Path(tmp) / "trading_memory.db")
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: FAKE_ORDERS,
                memory_path=memory_path,
                trading_memory_db=db,
            )
            monitor.scan_once()
            monitor.scan_once()
            records = db.get_market_snapshots(item_name="arcane_energize", source="price_monitor.scan")
            db.close()

        self.assertEqual(len(records), 1)

    def test_market_snapshot_memory_records_changed_price_within_rate_limit(self):
        from warframe_agent.trading_memory import TradingMemoryDB

        orders = [FAKE_ORDERS, CHANGED_ORDERS]

        def fetcher(item_id):
            return orders.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default().with_favorite_item("arcane_energize")
            memory.save(memory_path)
            db = TradingMemoryDB(db_path=Path(tmp) / "trading_memory.db")
            monitor = PriceMonitor(
                order_fetcher=fetcher,
                memory_path=memory_path,
                trading_memory_db=db,
            )
            monitor.scan_once()
            monitor.scan_once()
            records = db.get_market_snapshots(item_name="arcane_energize", source="price_monitor.scan")
            db.close()

        self.assertEqual(len(records), 2)

    def test_scan_once_goal_opportunity_includes_rationale_and_data(self):
        from warframe_agent.goals import create_goal

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default().with_goal(create_goal("earn_platinum", "攒 100 白金"))
            memory.save(memory_path)
            monitor = PriceMonitor(memory_path=memory_path)
            monitor._load_items = MagicMock(return_value=[])
            goal_results = [{
                "source": "set_profit",
                "strategy": "buy_parts_sell_set",
                "item_id": "carrier_prime_set",
                "item_name": "搬运者 Prime",
                "profit": 56,
                "roi_pct": 21.2,
                "buy_cost": 100,
                "sell_price": 156,
                "risk": "medium",
            }]
            with patch("warframe_agent.monitor.execute_plan", return_value=goal_results):
                result = monitor.scan_once()

        suggestion = next(s for s in result.suggestions if s.suggestion_type == "goal_opportunity")
        self.assertIn("原因", suggestion.message)
        self.assertEqual(suggestion.data["source"], "set_profit")
        self.assertEqual(suggestion.data["strategy"], "buy_parts_sell_set")
        self.assertEqual(suggestion.data["profit"], 56)
        self.assertEqual(suggestion.data["roi_pct"], 21.2)
        self.assertEqual(suggestion.data["buy_cost"], 100)
        self.assertEqual(suggestion.data["sell_price"], 156)
        self.assertEqual(suggestion.data["risk"], "medium")

    @patch("warframe_agent.monitor.load_item_data")
    def test_scan_once_goal_opportunity_filter_mod_excludes_sets_and_arcanes(self, load_item_data_mock):
        from warframe_agent.goals import create_goal

        load_item_data_mock.return_value = {
            "primed_flow": {"item_id": "primed_flow", "tags": ["mod"], "tradable": True, "modMaxRank": 10},
            "arcane_energize": {"item_id": "arcane_energize", "tags": ["arcane_enhancement"]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default().with_updated_preferences(opportunity_filter="mod")
            memory = memory.with_goal(create_goal("earn_platinum", "攒 100 白金"))
            memory.save(memory_path)
            monitor = PriceMonitor(memory_path=memory_path)
            monitor._load_items = MagicMock(return_value=[])
            goal_results = [
                {"source": "mod_flip", "item_id": "primed_flow", "item_name": "Primed Flow", "profit": 30, "roi_pct": 50, "buy_cost": 10, "sell_price": 40, "risk": "medium"},
                {"source": "mod_flip", "item_id": "arcane_energize", "item_name": "Arcane Energize", "profit": 50, "roi_pct": 80, "buy_cost": 20, "sell_price": 70, "risk": "medium"},
                {"source": "set_profit", "item_id": "carrier_prime_set", "item_name": "Carrier Prime", "profit": 56, "roi_pct": 21, "buy_cost": 100, "sell_price": 156, "risk": "medium"},
            ]
            with patch("warframe_agent.monitor.execute_plan", return_value=goal_results):
                result = monitor.scan_once()

        self.assertEqual(
            [s.item_id for s in result.suggestions if s.suggestion_type == "goal_opportunity"],
            ["primed_flow"],
        )

    def test_scan_once_merges_duplicate_active_goal_opportunities(self):
        from warframe_agent.goals import create_goal

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default()
            memory = memory.with_goal(create_goal(
                "earn_platinum", "攒 100 白金", criteria={"target_amount": 100, "budget": 500}
            ))
            memory = memory.with_goal(create_goal(
                "earn_platinum", "攒 100 白金", criteria={"target_amount": 100, "budget": 500}
            ))
            memory.save(memory_path)
            monitor = PriceMonitor(memory_path=memory_path)
            monitor._load_items = MagicMock(return_value=[])

            goal_results = [
                {"item_id": "carrier_prime_set", "item_name": "搬运者 prime", "profit": 56, "roi_pct": 21.2},
                {"item_id": "akarius_prime_set", "item_name": "阿利乌双枪 prime", "profit": 247, "roi_pct": 51.4},
            ]
            with patch("warframe_agent.monitor.execute_plan", return_value=goal_results) as execute:
                result = monitor.scan_once()

        self.assertEqual(execute.call_count, 1)
        self.assertEqual(
            [s.item_id for s in result.suggestions if s.suggestion_type == "goal_opportunity"],
            ["carrier_prime_set", "akarius_prime_set"],
        )

    def test_baro_recommendation_records_structured_memory(self):
        from warframe_agent.trading_memory import TradingMemoryDB

        reports = []
        with tempfile.TemporaryDirectory() as tmp:
            db = TradingMemoryDB(db_path=Path(tmp) / "trading_memory.db")
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: BARO_ORDERS,
                trading_memory_db=db,
                on_baro_recommendation=reports.append,
            )
            monitor.event_tracker.get_active_events = lambda: [_baro_event()]
            with patch("warframe_agent.baro._item_info", return_value={"type": "mod", "max_rank": 10}):
                monitor._check_baro_recommendation()
            records = db.get_recommendations(item_name="primed_flow", recommendation_type="baro")
            db.close()

        self.assertEqual(len(reports), 1)
        self.assertIn("Baro Mod", reports[0])
        self.assertEqual(len(records), 1)
        payload = records[0].payload
        self.assertEqual(records[0].reason, "Baro 兑换成本和 warframe.market 当前订单")
        self.assertEqual(payload["source"], "baro_recommendation")
        self.assertEqual(payload["event_type"], "baro_visit")
        self.assertEqual(payload["event_description"], "Baro active")
        self.assertEqual(payload["baro_start_time"], "2026-05-18T10:00:00")
        self.assertEqual(payload["baro_end_time"], "2026-05-20T10:00:00")
        self.assertEqual(payload["item_name"], "Primed Flow")
        self.assertEqual(payload["market_id"], "primed_flow")
        self.assertEqual(payload["ducat_cost"], 350)
        self.assertEqual(payload["credit_cost"], 110000)
        self.assertEqual(payload["rank"], 10)
        self.assertEqual(payload["max_rank"], 10)
        self.assertEqual(payload["item_kind"], "mod")
        self.assertEqual(payload["best_buy_price"], 80)
        self.assertEqual(payload["best_sell_price"], 95)
        for forbidden in ["buyers", "sellers", "profile", "whisper", "Baro Mod", "raw_chat"]:
            self.assertNotIn(forbidden, payload)

    def test_baro_recommendation_memory_write_failure_does_not_block_callback(self):
        reports = []
        failing_db = MagicMock()
        failing_db.record_recommendation.side_effect = RuntimeError("db down")
        monitor = PriceMonitor(
            order_fetcher=lambda item_id: BARO_ORDERS,
            trading_memory_db=failing_db,
            on_baro_recommendation=reports.append,
        )
        monitor.event_tracker.get_active_events = lambda: [_baro_event()]

        with patch("warframe_agent.baro._item_info", return_value={"type": "mod", "max_rank": 10}):
            monitor._check_baro_recommendation()

        self.assertEqual(len(reports), 1)
        failing_db.record_recommendation.assert_called_once()

    def test_baro_recommendation_memory_records_once_per_baro_start_time(self):
        from warframe_agent.trading_memory import TradingMemoryDB

        with tempfile.TemporaryDirectory() as tmp:
            db = TradingMemoryDB(db_path=Path(tmp) / "trading_memory.db")
            monitor = PriceMonitor(
                order_fetcher=lambda item_id: BARO_ORDERS,
                trading_memory_db=db,
                on_baro_recommendation=lambda report: None,
            )
            monitor.event_tracker.get_active_events = lambda: [_baro_event()]
            with patch("warframe_agent.baro._item_info", return_value={"type": "mod", "max_rank": 10}):
                monitor._check_baro_recommendation()
                monitor._check_baro_recommendation()
            records = db.get_recommendations(item_name="primed_flow", recommendation_type="baro")
            db.close()

        self.assertEqual(len(records), 1)

    def test_baro_recommendation_without_trading_memory_keeps_existing_behavior(self):
        reports = []
        monitor = PriceMonitor(
            order_fetcher=lambda item_id: BARO_ORDERS,
            on_baro_recommendation=reports.append,
        )
        monitor.event_tracker.get_active_events = lambda: [_baro_event()]

        with patch("warframe_agent.baro._item_info", return_value={"type": "mod", "max_rank": 10}):
            monitor._check_baro_recommendation()

        self.assertEqual(len(reports), 1)
        self.assertIn("Baro Mod", reports[0])


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
