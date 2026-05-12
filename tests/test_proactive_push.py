"""Tests for rule-driven proactive push."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from warframe_agent.monitor import (
    PriceMonitor,
    ProactivePush,
    ScanResult,
)
from warframe_agent.rules import MarketState
from warframe_agent.memory import AgentMemory, ProactiveSuggestion, TradingPreferences


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
