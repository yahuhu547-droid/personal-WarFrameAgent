"""Tests for rule-driven proactive push."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from warframe_agent.monitor import (
    PriceMonitor,
    ProactivePush,
    ScanResult,
)
from warframe_agent.rules import MarketState
from warframe_agent.events import WorldCycle
from warframe_agent.memory import AgentMemory, CycleAlert, ProactiveSuggestion, TradingPreferences


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


# ── _run_proactive_push (rule-based) ──

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
