"""Tests for dynamic execution planning (Layer 2)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from warframe_agent.goals import (
    AgentGoal,
    _build_next_step_prompt,
    _parse_next_step,
    _execute_single_step,
    execute_goal_dynamic,
    plan_for_goal,
)


# ── _build_next_step_prompt ──

def test_next_step_prompt_contains_goal():
    goal = AgentGoal(
        goal_id="g1", goal_type="mod_flip", description="test",
        target="all", criteria={}, status="active",
        created_at="2026-05-05", results=[],
    )
    prompt = _build_next_step_prompt(goal, [], [], 1, 3)
    assert "mod_flip" in prompt
    assert "JSON" in prompt


# ── _parse_next_step ──

def test_parse_next_step_stop():
    response = json.dumps({"action": "stop", "reason": "done"})
    action, params, reason = _parse_next_step(response)
    assert action == "stop"
    assert reason == "done"


def test_parse_next_step_scan():
    response = json.dumps({"action": "scan_mod_flip", "params": {"min_roi_pct": 50}, "reason": "try lower"})
    action, params, reason = _parse_next_step(response)
    assert action == "scan_mod_flip"
    assert params["min_roi_pct"] == 50


def test_parse_next_step_invalid_json():
    action, params, reason = _parse_next_step("not json")
    assert action == "stop"


def test_parse_next_step_empty():
    action, params, reason = _parse_next_step("")
    assert action == "stop"


# ── _execute_single_step ──

def test_execute_single_step_mod_flip():
    items = [{"item_id": "test_mod", "tags": ["mod"]}]
    order_fetcher = MagicMock(return_value=[])

    results = _execute_single_step("scan_mod_flip", items, order_fetcher, {})
    assert isinstance(results, list)


def test_execute_single_step_unknown():
    results = _execute_single_step("unknown_action", [], MagicMock(), {})
    assert results == []


# ── execute_goal_dynamic (fallback) ──

def test_dynamic_plan_fallback_no_llm():
    goal = AgentGoal(
        goal_id="g1", goal_type="mod_flip", description="test",
        target="all", criteria={}, status="active",
        created_at="2026-05-05", results=[],
    )
    items = []
    order_fetcher = MagicMock(return_value=[])

    # No LLM → falls back to static plan_for_goal
    results = execute_goal_dynamic(goal, items, order_fetcher, llm_caller=None)
    assert isinstance(results, list)


def test_dynamic_plan_fallback_llm_empty():
    goal = AgentGoal(
        goal_id="g1", goal_type="mod_flip", description="test",
        target="all", criteria={}, status="active",
        created_at="2026-05-05", results=[],
    )
    items = []
    order_fetcher = MagicMock(return_value=[])

    def empty_llm(messages):
        return ""

    results = execute_goal_dynamic(goal, items, order_fetcher, llm_caller=empty_llm)
    assert isinstance(results, list)


def test_dynamic_plan_with_llm_stop():
    goal = AgentGoal(
        goal_id="g1", goal_type="mod_flip", description="test",
        target="all", criteria={}, status="active",
        created_at="2026-05-05", results=[],
    )
    items = []
    order_fetcher = MagicMock(return_value=[])

    stop_response = json.dumps({"action": "stop", "reason": "no data"})

    def llm(messages):
        return stop_response

    results = execute_goal_dynamic(goal, items, order_fetcher, llm_caller=llm, max_iterations=2)
    assert isinstance(results, list)


def test_dynamic_plan_timeout():
    goal = AgentGoal(
        goal_id="g1", goal_type="mod_flip", description="test",
        target="all", criteria={}, status="active",
        created_at="2026-05-05", results=[],
    )
    items = []
    order_fetcher = MagicMock(return_value=[])

    # Very short timeout should trigger fallback
    results = execute_goal_dynamic(
        goal, items, order_fetcher,
        llm_caller=None,
        timeout_seconds=0,
    )
    assert isinstance(results, list)
