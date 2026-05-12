"""Tests for LLM-driven goal generation (Layer 1)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from warframe_agent.goals import (
    MarketContext,
    _build_goal_generation_prompt,
    _parse_generated_goals,
    generate_goals_from_market,
    AgentGoal,
    TradeOutcome,
)
from warframe_agent.memory import UserProfile


# ── MarketContext ──

def test_market_context_creation():
    ctx = MarketContext(
        top_mod_flips=[{"item_name": "Primed Continuity", "roi_pct": 200}],
        top_set_profits=[],
        top_investments=[],
        anomalies=[],
        active_goals=[],
        trade_outcomes=[],
        user_profile=None,
        learned_patterns=[],
    )
    assert len(ctx.top_mod_flips) == 1
    assert ctx.user_profile is None


# ── _build_goal_generation_prompt ──

def test_goal_prompt_contains_market_data():
    ctx = MarketContext(
        top_mod_flips=[{"item_name": "Mod A", "roi_pct": 150, "profit": 30}],
        top_set_profits=[{"item_name": "Set B", "profit": 50, "strategy": "buy_parts"}],
        top_investments=[],
        anomalies=[{"item_id": "x", "direction": "spike", "current": 200, "average": 100, "deviation_pct": 100}],
        active_goals=[],
        trade_outcomes=[],
        user_profile=None,
        learned_patterns=[{"description": "周末交易多"}],
    )
    prompt = _build_goal_generation_prompt(ctx)
    assert "Mod A" in prompt
    assert "Set B" in prompt
    assert "周末交易多" in prompt
    assert "JSON" in prompt


# ── _parse_generated_goals ──

def test_parse_goals_valid():
    response = json.dumps([
        {"goal_type": "flip_mod", "description": "翻转 Primed Mod", "target": "all", "criteria": {"min_roi_pct": 100}},
    ])
    goals = _parse_generated_goals(response, [])
    assert len(goals) == 1
    assert goals[0].goal_type == "flip_mod"
    assert goals[0].description.startswith("[自动]")


def test_parse_goals_deduplicates():
    existing = AgentGoal(
        goal_id="g1",
        goal_type="flip_mod",
        description="[自动] existing",
        target="all",
        criteria={},
        status="active",
        created_at="2026-05-05",
        results=[],
    )
    response = json.dumps([
        {"goal_type": "flip_mod", "description": "翻转", "target": "all", "criteria": {}},
    ])
    goals = _parse_generated_goals(response, [existing])
    assert len(goals) == 0


def test_parse_goals_invalid_json():
    assert _parse_generated_goals("not json", []) == []


def test_parse_goals_empty():
    assert _parse_generated_goals("[]", []) == []


def test_parse_goals_max_three():
    response = json.dumps([
        {"goal_type": "flip_mod", "description": "a", "target": "all", "criteria": {}},
        {"goal_type": "build_set", "description": "b", "target": "all", "criteria": {}},
        {"goal_type": "maximize_profit", "description": "c", "target": "all", "criteria": {}},
        {"goal_type": "find_bargain", "description": "d", "target": "all", "criteria": {}},
    ])
    goals = _parse_generated_goals(response, [])
    assert len(goals) <= 3


# ── generate_goals_from_market ──

def test_generate_goals_no_llm():
    ctx = MarketContext(
        top_mod_flips=[], top_set_profits=[], top_investments=[],
        anomalies=[], active_goals=[], trade_outcomes=[],
        user_profile=None, learned_patterns=[],
    )

    def empty_llm(messages):
        return ""

    goals = generate_goals_from_market(ctx, empty_llm)
    # Empty LLM response should return empty
    assert goals == []


def test_generate_goals_success():
    ctx = MarketContext(
        top_mod_flips=[{"item_name": "Mod A", "roi_pct": 200, "profit": 40}],
        top_set_profits=[], top_investments=[],
        anomalies=[], active_goals=[], trade_outcomes=[],
        user_profile=None, learned_patterns=[],
    )

    llm_response = json.dumps([
        {"goal_type": "flip_mod", "description": "翻转高ROI Mod", "target": "all", "criteria": {"min_roi_pct": 150}},
    ])

    def mock_llm(messages):
        return llm_response

    goals = generate_goals_from_market(ctx, mock_llm)
    assert len(goals) == 1
    assert goals[0].goal_type == "flip_mod"


def test_generate_goals_llm_failure():
    ctx = MarketContext(
        top_mod_flips=[], top_set_profits=[], top_investments=[],
        anomalies=[], active_goals=[], trade_outcomes=[],
        user_profile=None, learned_patterns=[],
    )

    def failing_llm(messages):
        raise RuntimeError("LLM error")

    goals = generate_goals_from_market(ctx, failing_llm)
    assert goals == []
