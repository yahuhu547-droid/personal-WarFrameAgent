"""Tests for pattern learning (Layer 3)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from warframe_agent.patterns import (
    extract_time_patterns,
    extract_item_patterns,
    extract_strategy_patterns,
    build_pattern_discovery_prompt,
    parse_patterns,
    discover_patterns,
)
from warframe_agent.goals import TradeOutcome


# ── extract_time_patterns ──

def test_extract_time_patterns_empty():
    trade_db = MagicMock()
    trade_db.get_recent_trades.return_value = []
    result = extract_time_patterns(trade_db, MagicMock())
    assert result["trade_count"] == 0
    assert result["by_weekday"] == {}


def test_extract_time_patterns_with_trades():
    trade = MagicMock()
    trade.timestamp = "2026-05-05T14:30:00+00:00"
    trade.price = 100

    trade_db = MagicMock()
    trade_db.get_recent_trades.return_value = [trade]

    result = extract_time_patterns(trade_db, MagicMock())
    assert result["trade_count"] == 1
    assert "周一" in result["by_weekday"] or "周二" in result["by_weekday"] or "周三" in result["by_weekday"] or "周四" in result["by_weekday"] or "周五" in result["by_weekday"] or "周六" in result["by_weekday"] or "周日" in result["by_weekday"]
    assert "14:00" in result["by_hour"]


# ── extract_item_patterns ──

def test_extract_item_patterns_empty():
    trade_db = MagicMock()
    trade_db.get_recent_trades.return_value = []
    result = extract_item_patterns(trade_db, MagicMock())
    assert result["item_count"] == 0
    assert result["items"] == []


def test_extract_item_patterns_with_trades():
    trade = MagicMock()
    trade.item_id = "ember_prime_set"
    trade.item_name = "Ember Prime Set"
    trade.price = 200

    trade_db = MagicMock()
    trade_db.get_recent_trades.return_value = [trade]

    result = extract_item_patterns(trade_db, MagicMock())
    assert result["item_count"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["item_id"] == "ember_prime_set"
    assert result["items"][0]["avg_price"] == 200


# ── extract_strategy_patterns ──

def test_extract_strategy_patterns_empty():
    result = extract_strategy_patterns([])
    assert result["total"] == 0
    assert result["by_source"] == {}


def test_extract_strategy_patterns_mod_flip():
    outcome = TradeOutcome(
        outcome_id="o1",
        goal_id="g1",
        action="buy",
        item_id="primed_continuity",
        price=50,
        expected_profit=100,
        actual_profit=80,
        user_feedback="good",
        timestamp="2026-05-05T10:00:00",
    )
    result = extract_strategy_patterns([outcome])
    assert result["total"] == 1
    assert "mod_flip" in result["by_source"]
    assert result["by_source"]["mod_flip"]["good"] == 1


def test_extract_strategy_patterns_set_profit():
    outcome = TradeOutcome(
        outcome_id="o2",
        goal_id="g1",
        action="buy",
        item_id="ember_prime_set",
        price=200,
        expected_profit=50,
        actual_profit=30,
        user_feedback="good",
        timestamp="2026-05-05T10:00:00",
    )
    result = extract_strategy_patterns([outcome])
    assert "set_profit" in result["by_source"]


# ── build_pattern_discovery_prompt ──

def test_build_prompt_contains_data():
    prompt = build_pattern_discovery_prompt(
        {"trade_count": 10, "by_weekday": {}, "by_hour": {}},
        {"item_count": 5, "items": []},
        {"total": 3, "by_source": {}},
    )
    assert "交易时间分布" in prompt
    assert "热门交易物品" in prompt
    assert "策略表现" in prompt
    assert "JSON" in prompt


# ── parse_patterns ──

def test_parse_patterns_valid():
    response = json.dumps([
        {"category": "time", "description": "周末交易更多", "confidence": 0.8, "evidence": "数据"},
        {"category": "item", "description": "Ember 需求稳定", "confidence": 0.6, "evidence": "10笔"},
    ])
    patterns = parse_patterns(response)
    assert len(patterns) == 2
    assert patterns[0]["category"] == "time"
    assert patterns[0]["confidence"] == 0.8


def test_parse_patterns_invalid_json():
    assert parse_patterns("not json") == []


def test_parse_patterns_empty_array():
    assert parse_patterns("[]") == []


def test_parse_patterns_clamps_confidence():
    response = json.dumps([{"category": "time", "description": "test", "confidence": 1.5}])
    patterns = parse_patterns(response)
    assert patterns[0]["confidence"] == 1.0


def test_parse_patterns_missing_description():
    response = json.dumps([{"category": "time", "confidence": 0.5}])
    patterns = parse_patterns(response)
    assert len(patterns) == 0


# ── discover_patterns ──

def test_discover_patterns_too_few_trades():
    trade_db = MagicMock()
    trade_db.get_recent_trades.return_value = []
    price_db = MagicMock()
    llm = MagicMock()

    result = discover_patterns(trade_db, price_db, [], llm)
    assert result == []
    llm.assert_not_called()


def test_discover_patterns_llm_failure():
    trade = MagicMock()
    trade.timestamp = "2026-05-05T14:30:00+00:00"
    trade.price = 100
    trade.item_id = "test_item"
    trade.item_name = "Test"

    trade_db = MagicMock()
    trade_db.get_recent_trades.return_value = [trade] * 5
    price_db = MagicMock()

    def failing_llm(messages):
        raise RuntimeError("LLM down")

    result = discover_patterns(trade_db, price_db, [], failing_llm)
    assert result == []


def test_discover_patterns_success():
    trade = MagicMock()
    trade.timestamp = "2026-05-05T14:30:00+00:00"
    trade.price = 100
    trade.item_id = "test_item"
    trade.item_name = "Test"

    trade_db = MagicMock()
    trade_db.get_recent_trades.return_value = [trade] * 5
    price_db = MagicMock()

    llm_response = json.dumps([
        {"category": "time", "description": "下午交易多", "confidence": 0.7, "evidence": "5笔"}
    ])

    def mock_llm(messages):
        return llm_response

    result = discover_patterns(trade_db, price_db, [], mock_llm)
    assert len(result) == 1
    assert result[0]["category"] == "time"
    assert "pattern_id" in result[0]
    assert "discovered_at" in result[0]
