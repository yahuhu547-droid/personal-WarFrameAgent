"""Tests for rule-driven proactive push."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from warframe_agent.monitor import (
    PRICE_MONITOR_EVENT_CHECKS_JOB_ID,
    PRICE_MONITOR_SCAN_JOB_ID,
    PriceMonitor,
    ProactivePush,
    ScanResult,
)
from warframe_agent.rules import MarketState
from warframe_agent.events import GameEvent, WorldCycle
from warframe_agent.memory import AgentMemory, CycleAlert, ProactiveSuggestion, TradingPreferences
from warframe_agent.trading_memory import TradingMemoryDB


# ── ProactivePush dataclass ──

def test_proactive_push_creation():
    push = ProactivePush(
        item_id="test_item",
        item_display="Test Item",
        push_type="opportunity",
        priority=1,
        message="Good deal",
        action_suggestion="buy now",
    )
    assert push.item_id == "test_item"
    assert push.priority == 1
    assert push.action_suggestion == "buy now"
    assert push.data == {}


def test_proactive_push_with_data():
    push = ProactivePush(
        item_id="x", item_display="X", push_type="warning",
        priority=2, message="msg", action_suggestion="watch",
        data={"key": "value"},
    )
    assert push.data["key"] == "value"


def test_check_cycle_alerts_pushes_only_on_transition(tmp_path):
    memory = AgentMemory.default().with_cycle_alert(CycleAlert("earth", "night", "地球变为黑夜", 1.0))
    memory.save(tmp_path / "memory.json")
    pushed = MagicMock()
    monitor = PriceMonitor(memory_path=tmp_path / "memory.json", on_cycle=pushed)
    monitor.event_tracker.get_cycles = MagicMock(return_value=[
        WorldCycle("earth", "地球", "day", "白天", activation="1000", expiry="2000"),
    ])

    monitor._check_cycle_alerts()
    pushed.assert_not_called()

    monitor.event_tracker.get_cycles = MagicMock(return_value=[
        WorldCycle("earth", "地球", "night", "黑夜", activation="3000", expiry="4000"),
    ])
    monitor._check_cycle_alerts()
    pushed.assert_called_once()
    assert "已变为黑夜" in pushed.call_args[0][0]

    monitor._check_cycle_alerts()
    pushed.assert_called_once()


def test_check_cycle_alerts_skips_current_phase_created_after_activation(tmp_path):
    memory = AgentMemory.default().with_cycle_alert(CycleAlert("earth", "night", "地球变为黑夜", 3500.0))
    memory.save(tmp_path / "memory.json")
    pushed = MagicMock()
    monitor = PriceMonitor(memory_path=tmp_path / "memory.json", on_cycle=pushed)
    monitor._cycle_last_state["earth"] = "day"
    monitor.event_tracker.get_cycles = MagicMock(return_value=[
        WorldCycle("earth", "地球", "night", "黑夜", activation="3000", expiry="4000"),
    ])

    monitor._check_cycle_alerts()

    pushed.assert_not_called()


def test_event_checks_first_tick_baselines_cycle_without_notification(tmp_path):
    memory = AgentMemory.default().with_cycle_alert(CycleAlert("earth", "night", "地球变为黑夜", 1.0))
    memory.save(tmp_path / "memory.json")
    pushed = MagicMock()
    monitor = PriceMonitor(memory_path=tmp_path / "memory.json", on_cycle=pushed)

    def scan_cycle():
        monitor._scan_cycle_count += 1

    monitor._run_scan_cycle = scan_cycle
    monitor.event_tracker.get_cycles = MagicMock(return_value=[
        WorldCycle("earth", "地球", "night", "黑夜", activation="3000", expiry="4000"),
    ])
    monitor._check_fissure_alerts = MagicMock()
    monitor._check_baro_recommendation = MagicMock()
    monitor._check_event_driven_push = MagicMock()
    monitor._check_daily_report = MagicMock()

    scheduler = monitor._build_scheduler()
    results = scheduler.tick()

    assert [result.job_id for result in results] == [
        PRICE_MONITOR_SCAN_JOB_ID,
        PRICE_MONITOR_EVENT_CHECKS_JOB_ID,
    ]
    pushed.assert_not_called()
    assert monitor._cycle_last_state["earth"] == "night"


# ── _run_proactive_push (rule-based) ──

def test_price_monitor_does_not_create_trading_memory_by_default():
    monitor = PriceMonitor()

    assert monitor.trading_memory_db is None


def test_run_proactive_push_no_callback():
    monitor = PriceMonitor(on_proactive_push=None)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(item_id="x", suggestion_type="anomaly", priority=1, message="test"),
    ])
    # Should not raise
    monitor._run_proactive_push(scan)


def test_run_proactive_push_no_high_priority():
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(item_id="x", suggestion_type="anomaly", priority=3, message="low"),
    ])
    monitor._run_proactive_push(scan)
    push_fn.assert_not_called()


@patch("warframe_agent.push.PushConfig.load")
@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_skips_opportunity_when_push_proactive_disabled(mock_load, mock_push_load):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    cfg = MagicMock()
    cfg.push_proactive = False
    mock_push_load.return_value = cfg
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(item_id="arcane_energize", suggestion_type="opportunity", priority=2, message="利润 50p"),
        ProactiveSuggestion(item_id="arcane_energize", suggestion_type="anomaly", priority=1, message="暴跌"),
    ])

    monitor._run_proactive_push(scan, MarketState())

    assert [call.args[0].push_type for call in push_fn.call_args_list] == ["warning"]


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_anomaly(mock_load):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )

    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize", suggestion_type="anomaly",
            priority=1, message="arcane_energize 价格暴跌！当前 30p，均值 50p，偏差 -40%",
        ),
    ])
    market_state = MarketState(volatility_index=20)
    monitor._run_proactive_push(scan, market_state)
    push_fn.assert_called_once()
    push = push_fn.call_args[0][0]
    assert push.item_id == "arcane_energize"
    assert push.push_type == "warning"
    assert "暴跌" in push.message


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_records_to_injected_trading_memory_db(mock_load, tmp_path):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    db = TradingMemoryDB(db_path=tmp_path / "trading_memory.db")
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn, trading_memory_db=db)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize", suggestion_type="opportunity",
            priority=2, message="利润 50p",
        ),
    ])

    monitor._run_proactive_push(scan, MarketState())

    push_fn.assert_called_once()
    records = db.get_push_history(item_name="arcane_energize")
    db.close()
    assert len(records) == 1
    assert records[0].push_type == "opportunity"
    assert "利润" in records[0].message
    assert records[0].metadata["source"] == "rule_proactive_push"
    assert records[0].metadata["item_id"] == "arcane_energize"
    assert records[0].metadata["priority"] == 2
    assert records[0].metadata["action_suggestion"] == "watch"
    assert records[0].metadata["suggestion_type"] == "opportunity"
    for forbidden in ["query_text", "reply", "raw_message", "chat_message", "prompt"]:
        assert forbidden not in records[0].metadata


def _unsafe_trade_plan(player: str = "UnsafeSeller"):
    return {
        "schema_version": 1,
        "source": "arcane_flip",
        "strategy": "arcane_r0_to_r5",
        "item_id": "arcane_energize",
        "display_name": "Arcane Energize",
        "required_quantity": 21,
        "buy_steps": [
            {
                "side": "buy",
                "player": player,
                "market_url": "https://warframe.market/items/arcane_energize",
                "profile_url": f"https://warframe.market/profile/{player}",
                "whisper": f"/w {player} Hi! I want to buy.",
                "quantity": 21,
                "unit_price": 5,
                "subtotal": 105,
            }
        ],
        "sell_steps": [
            {
                "side": "sell",
                "player": "UnsafeBuyer",
                "market_url": "https://warframe.market/items/arcane_energize",
                "profile_url": "https://warframe.market/profile/UnsafeBuyer",
                "whisper": "/w UnsafeBuyer Hi! I want to sell.",
                "quantity": 1,
                "unit_price": 150,
                "subtotal": 150,
            }
        ],
        "total_cost": 105,
        "total_revenue": 150,
        "profit": 45,
        "roi_pct": 42.9,
        "profit_bucket": "40_50",
        "plan_signature": "sig-display-only",
        "risk_level": "medium",
        "safe_summary": {
            "schema_version": 1,
            "source": "arcane_flip",
            "strategy": "arcane_r0_to_r5",
            "item_id": "arcane_energize",
            "display_name": "Arcane Energize",
            "required_quantity": 21,
            "buy_step_count": 1,
            "sell_step_count": 1,
            "total_cost": 105,
            "total_revenue": 150,
            "profit": 45,
            "roi_pct": 42.9,
            "risk_level": "medium",
            "profit_bucket": "40_50",
            "plan_signature": "sig-display-only",
        },
    }


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_sanitizes_trade_plan_before_recording(mock_load, tmp_path):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    db = TradingMemoryDB(db_path=tmp_path / "trading_memory.db")
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn, trading_memory_db=db)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="opportunity",
            priority=2,
            message="利润 45p",
            data={"trade_plan": _unsafe_trade_plan(), "source": "arcane_flip"},
        ),
    ])

    monitor._run_proactive_push(scan, MarketState())

    push_fn.assert_called_once()
    records = db.get_push_history(item_name="arcane_energize")
    db.close()
    assert len(records) == 1
    metadata = records[0].metadata
    assert metadata["opportunity_source"] == "arcane_flip"
    assert metadata["source"] == "rule_proactive_push"
    assert metadata["strategy"] == "arcane_r0_to_r5"
    assert metadata["required_quantity"] == 21
    assert metadata["total_cost"] == 105
    assert metadata["total_revenue"] == 150
    assert metadata["profit"] == 45
    assert metadata["roi_pct"] == 42.9
    assert metadata["profit_bucket"] == "40_50"
    assert metadata["plan_signature"] == "sig-display-only"
    assert "trade_plan" not in metadata
    assert "buy_steps" not in metadata
    assert "sell_steps" not in metadata
    encoded = json.dumps(metadata, ensure_ascii=False)
    for forbidden in [
        "UnsafeSeller",
        "UnsafeBuyer",
        "warframe.market",
        "profile_url",
        "market_url",
        "whisper",
        "/w",
    ]:
        assert forbidden not in encoded


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_suppresses_trade_plan_player_only_change(mock_load, tmp_path):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    db = TradingMemoryDB(db_path=tmp_path / "trading_memory.db")
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn, trading_memory_db=db)
    first = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="opportunity",
            priority=2,
            message="利润 45p",
            data={"trade_plan": _unsafe_trade_plan("SellerA"), "source": "arcane_flip"},
        ),
    ])
    second = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="opportunity",
            priority=2,
            message="利润 45p",
            data={"trade_plan": _unsafe_trade_plan("SellerB"), "source": "arcane_flip"},
        ),
    ])

    monitor._run_proactive_push(first, MarketState())
    monitor._run_proactive_push(second, MarketState())

    push_fn.assert_called_once()
    records = db.get_push_history(item_name="arcane_energize")
    db.close()
    assert len(records) == 1


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_suppresses_duplicate_opportunity_with_trading_memory(mock_load, tmp_path):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    db = TradingMemoryDB(db_path=tmp_path / "trading_memory.db")
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn, trading_memory_db=db)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="opportunity",
            priority=2,
            message="利润 50p",
            data={"source": "spread", "profit": 50, "dedupe_key": "opportunity:opportunity:arcane_energize:spread"},
        ),
    ])

    monitor._run_proactive_push(scan, MarketState())
    monitor._run_proactive_push(scan, MarketState())

    push_fn.assert_called_once()
    records = db.get_push_history(item_name="arcane_energize")
    db.close()
    assert len(records) == 1


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_allows_duplicate_after_cooldown(mock_load, tmp_path):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    db = TradingMemoryDB(db_path=tmp_path / "trading_memory.db")
    old_timestamp = (datetime.now() - timedelta(hours=13)).isoformat()
    db.record_push(
        "opportunity",
        "利润 50p",
        item_name="arcane_energize",
        metadata={
            "dedupe_key": "opportunity:opportunity:arcane_energize:spread",
            "suggestion_type": "opportunity",
            "source": "spread",
            "profit": 50,
        },
    )
    conn = db._get_conn()
    conn.execute("UPDATE push_history SET timestamp = ?", (old_timestamp,))
    conn.commit()
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn, trading_memory_db=db)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="opportunity",
            priority=2,
            message="利润 50p",
            data={"source": "spread", "profit": 50, "dedupe_key": "opportunity:opportunity:arcane_energize:spread"},
        ),
    ])

    monitor._run_proactive_push(scan, MarketState())

    push_fn.assert_called_once()
    db.close()


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_allows_material_profit_change(mock_load, tmp_path):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    db = TradingMemoryDB(db_path=tmp_path / "trading_memory.db")
    db.record_push(
        "opportunity",
        "利润 50p",
        item_name="arcane_energize",
        metadata={
            "dedupe_key": "opportunity:opportunity:arcane_energize:spread",
            "suggestion_type": "opportunity",
            "source": "spread",
            "profit": 50,
        },
    )
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn, trading_memory_db=db)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="opportunity",
            priority=2,
            message="利润 70p",
            data={"source": "spread", "profit": 70, "dedupe_key": "opportunity:opportunity:arcane_energize:spread"},
        ),
    ])

    monitor._run_proactive_push(scan, MarketState())

    push_fn.assert_called_once()
    db.close()


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_memory_cooldown_without_db(mock_load):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="goal_opportunity",
            priority=2,
            message="利润 50p",
            data={"source": "mod_flip", "profit": 50, "dedupe_key": "opportunity:goal_opportunity:arcane_energize:mod_flip"},
        ),
    ])

    monitor._run_proactive_push(scan, MarketState())
    monitor._run_proactive_push(scan, MarketState())

    push_fn.assert_called_once()


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_does_not_suppress_anomaly(mock_load):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(item_id="arcane_energize", suggestion_type="anomaly", priority=1, message="暴跌"),
    ])

    monitor._run_proactive_push(scan, MarketState())
    monitor._run_proactive_push(scan, MarketState())

    assert push_fn.call_count == 2


@patch("warframe_agent.monitor.AgentMemory.load")
def test_trading_memory_write_failure_does_not_prevent_proactive_push_callback(mock_load):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    failing_db = MagicMock()
    failing_db.record_push.side_effect = RuntimeError("db down")
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn, trading_memory_db=failing_db)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize", suggestion_type="opportunity",
            priority=2, message="利润 50p",
        ),
    ])

    monitor._run_proactive_push(scan, MarketState())

    push_fn.assert_called_once()
    failing_db.record_push.assert_called_once()


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_deduplicates_before_limit(mock_load):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(item_id="carrier_prime_set", suggestion_type="goal_opportunity", priority=2, message="搬运者 +56p"),
        ProactiveSuggestion(item_id="carrier_prime_set", suggestion_type="goal_opportunity", priority=2, message="搬运者 +119p"),
        ProactiveSuggestion(item_id="akarius_prime_set", suggestion_type="goal_opportunity", priority=2, message="阿利乌双枪 +247p"),
        ProactiveSuggestion(item_id="akarius_prime_set", suggestion_type="goal_opportunity", priority=2, message="阿利乌双枪 +234p"),
        ProactiveSuggestion(item_id="volt_prime_set", suggestion_type="goal_opportunity", priority=2, message="伏特 +80p"),
    ])

    monitor._run_proactive_push(scan, MarketState())

    assert [call.args[0].item_id for call in push_fn.call_args_list] == [
        "carrier_prime_set", "akarius_prime_set", "volt_prime_set",
    ]


@patch("warframe_agent.monitor.evaluate_market_state", return_value=MarketState())
@patch("warframe_agent.monitor.AgentMemory.load")
def test_scan_cycle_does_not_emit_duplicate_goal_opportunity_channel(mock_load, _eval, tmp_path):
    memory_path = tmp_path / "memory.json"
    AgentMemory.default().save(memory_path)
    mock_load.return_value = AgentMemory.default()
    proactive_fn = MagicMock()
    goal_fn = MagicMock()
    monitor = PriceMonitor(
        memory_path=memory_path,
        on_proactive_push=proactive_fn,
        on_goal_opportunity=goal_fn,
    )
    monitor.scan_once = MagicMock(return_value=ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="arcane_energize",
            suggestion_type="goal_opportunity",
            priority=2,
            message="目标机会",
            data={"source": "mod_flip"},
        ),
    ]))
    monitor._check_price_spikes = MagicMock(return_value=[])

    monitor._run_scan_cycle()

    proactive_fn.assert_called_once()
    goal_fn.assert_not_called()


def test_event_driven_push_records_to_injected_trading_memory_db(tmp_path):
    db = TradingMemoryDB(db_path=tmp_path / "trading_memory.db")
    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn, trading_memory_db=db)
    monitor.event_tracker.get_active_events = MagicMock(return_value=[
        GameEvent(
            event_type="prime_vault",
            description="Rhino Prime Vault",
            items_affected=["rhino_prime_set"],
        )
    ])

    monitor._check_event_driven_push()

    push_fn.assert_called_once()
    records = db.get_push_history(item_name="rhino_prime_set")
    db.close()
    assert len(records) == 1
    assert records[0].push_type == "opportunity"
    assert records[0].metadata["source"] == "event_driven_push"
    assert records[0].metadata["event_type"] == "prime_vault"
    assert records[0].metadata["event_description"] == "Rhino Prime Vault"
    assert records[0].metadata["items_affected"] == ["rhino_prime_set"]
    for forbidden in ["query_text", "reply", "raw_message", "chat_message", "prompt"]:
        assert forbidden not in records[0].metadata


@patch("warframe_agent.monitor.AgentMemory.load")
def test_run_proactive_push_opportunity(mock_load):
    mock_load.return_value = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )

    push_fn = MagicMock()
    monitor = PriceMonitor(on_proactive_push=push_fn)
    scan = ScanResult(suggestions=[
        ProactiveSuggestion(
            item_id="test_item", suggestion_type="opportunity",
            priority=2, message="利润 50p",
        ),
    ])
    market_state = MarketState()
    monitor._run_proactive_push(scan, market_state)
    push_fn.assert_called_once()
    push = push_fn.call_args[0][0]
    assert push.push_type == "opportunity"
    assert push.action_suggestion == "watch"
