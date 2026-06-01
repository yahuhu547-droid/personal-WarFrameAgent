"""测试 plan 工具：解析、执行、集成到 react_loop。"""
from __future__ import annotations

from warframe_agent.tool_router import (
    AgentTrace,
    ExecutionPlan,
    PlanStep,
    ToolCall,
    build_plan_confirmation_request,
    _format_plan_results,
    _parse_plan,
    execute_plan,
    react_loop,
    review_execution_plan,
)
from warframe_agent.tool_registry import ToolRegistry, ToolSpec


# ── _parse_plan ──

def test_parse_plan_extracts_steps():
    tc = ToolCall(name="plan", arguments={
        "goal": "对比充沛和优雅的价格",
        "steps": [
            {"tool": "query_price", "args": {"item_name": "充沛"}, "purpose": "查充沛价格"},
            {"tool": "query_price", "args": {"item_name": "优雅"}, "purpose": "查优雅价格"},
        ],
    })
    plan = _parse_plan(tc)
    assert plan is not None
    assert plan.goal == "对比充沛和优雅的价格"
    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "query_price"
    assert plan.steps[0].arguments == {"item_name": "充沛"}
    assert plan.steps[1].purpose == "查优雅价格"


def test_parse_plan_returns_none_for_empty_goal():
    tc = ToolCall(name="plan", arguments={"goal": "", "steps": [{"tool": "query_price", "args": {}}]})
    assert _parse_plan(tc) is None


def test_parse_plan_returns_none_for_no_steps():
    tc = ToolCall(name="plan", arguments={"goal": "test", "steps": []})
    assert _parse_plan(tc) is None


def test_parse_plan_skips_invalid_steps():
    tc = ToolCall(name="plan", arguments={
        "goal": "test",
        "steps": [
            "not a dict",
            {"tool": "query_price", "args": {"item_name": "充沛"}},
        ],
    })
    plan = _parse_plan(tc)
    assert plan is not None
    assert len(plan.steps) == 1


# ── execute_plan ──

def test_execute_plan_runs_sequentially():
    call_order = []

    def executor(tc: ToolCall) -> str:
        call_order.append(tc.name)
        return f"result_{tc.name}"

    plan = ExecutionPlan(goal="test", steps=[
        PlanStep(tool="query_price", arguments={"item_name": "a"}),
        PlanStep(tool="price_trend", arguments={"item_name": "b"}),
    ])
    results = execute_plan(plan, executor)

    assert call_order == ["query_price", "price_trend"]
    assert len(results) == 2
    assert results[0][1] == "result_query_price"
    assert results[1][1] == "result_price_trend"


def test_plan_with_failing_step():
    def executor(tc: ToolCall) -> str | None:
        if tc.name == "query_price":
            raise RuntimeError("network error")
        return "ok"

    plan = ExecutionPlan(goal="test", steps=[
        PlanStep(tool="query_price", arguments={"item_name": "a"}),
        PlanStep(tool="price_trend", arguments={"item_name": "b"}),
    ])
    # execute_plan 本身不捕获异常，调用方负责
    results = []
    for step in plan.steps:
        tc = ToolCall(name=step.tool, arguments=step.arguments)
        try:
            result = executor(tc)
        except Exception:
            result = None
        results.append((step, result))

    assert results[0][1] is None  # 失败
    assert results[1][1] == "ok"  # 不受影响


# ── _format_plan_results ──

def test_format_plan_results():
    plan = ExecutionPlan(goal="对比价格", steps=[
        PlanStep(tool="query_price", arguments={"item_name": "充沛"}, purpose="查充沛"),
        PlanStep(tool="query_price", arguments={"item_name": "优雅"}, purpose="查优雅"),
    ])
    results = [
        (plan.steps[0], "充沛: 最低卖价 45p"),
        (plan.steps[1], "优雅: 最低卖价 30p"),
    ]
    text = _format_plan_results(plan.goal, results)
    assert "对比价格" in text
    assert "步骤 1" in text
    assert "充沛: 最低卖价 45p" in text
    assert "步骤 2" in text
    assert "优雅: 最低卖价 30p" in text
    assert "综合回答" in text


def test_format_plan_results_with_failure():
    step = PlanStep(tool="query_price", arguments={})
    results = [(step, None)]
    text = _format_plan_results("test", results)
    assert "执行失败或无结果" in text


# ── plan review ──

def test_plan_review_allows_read_only_known_tools():
    plan = ExecutionPlan(
        goal="compare",
        steps=[
            PlanStep(tool="query_price", arguments={"item_name": "arcane_energize"}, purpose="check price"),
            PlanStep(tool="price_trend", arguments={"item_name": "arcane_energize"}, purpose="verify trend"),
        ],
    )

    review = review_execution_plan(plan)

    assert review.status == "ok"
    assert review.blocked_reason == ""
    assert review.verification_note == "plan_review=ok; issues=0; unknown=0; side_effect=0; sensitive_args=0; verification=0"
    assert review.issue_count == 0
    assert review.unknown_tool_count == 0
    assert review.side_effect_tool_count == 0
    assert review.sensitive_argument_count == 0
    assert review.verification_gap_count == 0
    assert review.issues == ()


def test_plan_review_blocks_unknown_tool():
    plan = ExecutionPlan(goal="compare", steps=[PlanStep(tool="missing_tool", arguments={}, purpose="check")])

    review = review_execution_plan(plan)

    assert review.status == "blocked"
    assert review.blocked_reason == "unknown_tool"
    assert review.issue_count == 1
    assert review.unknown_tool_count == 1
    assert review.issues[0].step_index == 1
    assert review.issues[0].tool_name == "missing_tool"
    assert review.issues[0].code == "unknown_tool"


def test_plan_review_blocks_non_exposed_tool():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="internal_lookup",
        description="internal only",
        parameters={},
        expose_schema=False,
        safety_level="read_only",
    ))
    plan = ExecutionPlan(goal="check", steps=[PlanStep(tool="internal_lookup", arguments={}, purpose="check")])

    review = review_execution_plan(plan, registry)

    assert review.status == "blocked"
    assert review.blocked_reason == "non_exposed_tool"
    assert review.issue_count == 1
    assert review.non_exposed_tool_count == 1
    assert review.issues[0].code == "non_exposed_tool"


def test_plan_review_blocks_side_effect_tools_by_metadata():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="notify",
        description="send notification",
        parameters={},
        side_effect=True,
        safety_level="external_side_effect",
    ))
    registry.register(ToolSpec(
        name="set_alert",
        description="write local alert",
        parameters={},
        safety_level="local_state_write",
    ))
    plan = ExecutionPlan(
        goal="notify",
        steps=[
            PlanStep(tool="notify", arguments={}, purpose="send notification"),
            PlanStep(tool="set_alert", arguments={}, purpose="write alert"),
        ],
    )

    review = review_execution_plan(plan, registry)

    assert review.status == "blocked"
    assert review.blocked_reason == "side_effect_tool"
    assert review.issue_count == 2
    assert review.side_effect_tool_count == 2
    assert [issue.code for issue in review.issues] == ["side_effect_tool", "side_effect_tool"]


def test_plan_review_blocks_nested_sensitive_argument_keys():
    plan = ExecutionPlan(
        goal="check",
        steps=[
            PlanStep(
                tool="query_price",
                arguments={"filters": {"authToken": "SECRET", "nested": [{"cookieValue": "SECRET"}]}},
                purpose="check",
            )
        ],
    )

    review = review_execution_plan(plan)

    assert review.status == "blocked"
    assert review.blocked_reason == "sensitive_arguments"
    assert review.issue_count == 1
    assert review.sensitive_argument_count == 1
    assert review.issues[0].code == "sensitive_arguments"


def test_plan_review_flags_missing_verification_purpose():
    plan = ExecutionPlan(goal="check", steps=[PlanStep(tool="query_price", arguments={"item_name": "arcane_energize"})])

    review = review_execution_plan(plan)

    assert review.status == "blocked"
    assert review.blocked_reason == "missing_verification"
    assert review.issue_count == 1
    assert review.verification_gap_count == 1
    assert review.issues[0].code == "missing_verification"


# ── react_loop 集成 ──

def test_plan_confirmation_request_allows_only_missing_verification_read_only_plan():
    plan = ExecutionPlan(
        goal="compare",
        steps=[PlanStep(tool="query_price", arguments={"item_name": "arcane_energize"})],
    )
    review = review_execution_plan(plan)

    request = build_plan_confirmation_request(plan, review)

    assert request.status == "requires_confirmation"
    assert request.confirmable is True
    assert request.blocked_reason == "missing_verification"
    assert request.confirmation_token.startswith("plan_confirm_")
    assert "query_price" not in request.confirmation_token
    assert "arcane_energize" not in request.confirmation_token
    assert "missing_verification" in request.verification_note


def test_plan_confirmation_request_rejects_side_effect_and_sensitive_plans():
    side_effect_registry = ToolRegistry()
    side_effect_registry.register(ToolSpec(
        name="notify",
        description="send notification",
        parameters={},
        side_effect=True,
        safety_level="external_side_effect",
    ))
    side_effect_plan = ExecutionPlan(
        goal="notify",
        steps=[PlanStep(tool="notify", arguments={}, purpose="send notification")],
    )
    sensitive_plan = ExecutionPlan(
        goal="check",
        steps=[PlanStep(
            tool="query_price",
            arguments={"item_name": "arcane_energize", "authToken": "SECRET"},
        )],
    )

    side_effect_review = review_execution_plan(side_effect_plan, side_effect_registry)
    side_effect_request = build_plan_confirmation_request(side_effect_plan, side_effect_review, side_effect_registry)
    sensitive_review = review_execution_plan(sensitive_plan)
    sensitive_request = build_plan_confirmation_request(sensitive_plan, sensitive_review)

    assert side_effect_request.status == "not_confirmable"
    assert side_effect_request.confirmable is False
    assert side_effect_request.confirmation_token == ""
    assert side_effect_request.blocked_reason == "side_effect_tool"
    assert sensitive_request.status == "not_confirmable"
    assert sensitive_request.confirmable is False
    assert sensitive_request.confirmation_token == ""
    assert sensitive_request.blocked_reason == "sensitive_arguments"
    assert "SECRET" not in repr(sensitive_request)


def test_plan_confirmation_request_rejects_unknown_and_non_exposed_plans():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="internal_lookup",
        description="internal only",
        parameters={},
        expose_schema=False,
        safety_level="read_only",
    ))
    unknown_plan = ExecutionPlan(
        goal="check",
        steps=[PlanStep(tool="missing_tool", arguments={}, purpose="check")],
    )
    non_exposed_plan = ExecutionPlan(
        goal="check",
        steps=[PlanStep(tool="internal_lookup", arguments={}, purpose="check")],
    )

    unknown_review = review_execution_plan(unknown_plan, registry)
    non_exposed_review = review_execution_plan(non_exposed_plan, registry)

    unknown_request = build_plan_confirmation_request(unknown_plan, unknown_review, registry)
    non_exposed_request = build_plan_confirmation_request(non_exposed_plan, non_exposed_review, registry)

    assert unknown_request.status == "not_confirmable"
    assert unknown_request.confirmation_token == ""
    assert unknown_request.blocked_reason == "unknown_tool"
    assert non_exposed_request.status == "not_confirmable"
    assert non_exposed_request.confirmation_token == ""
    assert non_exposed_request.blocked_reason == "non_exposed_tool"


def test_react_loop_executes_confirmed_missing_verification_plan():
    plan = ExecutionPlan(
        goal="compare",
        steps=[PlanStep(tool="query_price", arguments={"item_name": "arcane_energize"})],
    )
    request = build_plan_confirmation_request(plan, review_execution_plan(plan))
    responses = iter([
        '{"tool": "plan", "args": {"goal": "compare", "steps": ['
        '{"tool": "query_price", "args": {"item_name": "arcane_energize"}}'
        ']}}',
        "confirmed final answer",
    ])
    trace = AgentTrace()
    tool_calls_seen = []

    result = react_loop(
        "compare",
        lambda tc: tool_calls_seen.append(tc.name) or "price result",
        model_call=lambda messages: next(responses),
        candidate_tools={"plan"},
        trace=trace,
        plan_confirmation_token=request.confirmation_token,
    )

    assert result == "confirmed final answer"
    assert tool_calls_seen == ["query_price"]
    assert trace.termination_reason == "final_answer"
    assert trace.plan is not None
    assert trace.plan.status == "completed"
    assert trace.plan.blocked_reason == ""
    assert "confirmed" in trace.plan.verification_note
    assert trace.plan.steps[0].status == "completed"


def test_react_loop_rejects_wrong_plan_confirmation_token_without_execution():
    trace = AgentTrace()
    tool_calls_seen = []

    result = react_loop(
        "compare",
        lambda tc: tool_calls_seen.append(tc.name) or "price result",
        model_call=lambda messages: (
            '{"tool": "plan", "args": {"goal": "compare", "steps": ['
            '{"tool": "query_price", "args": {"item_name": "arcane_energize"}}'
            ']}}'
        ),
        candidate_tools={"plan"},
        trace=trace,
        plan_confirmation_token="plan_confirm_wrong",
    )

    assert "missing_verification" in result
    assert tool_calls_seen == []
    assert trace.termination_reason == "plan_blocked"
    assert trace.plan is not None
    assert trace.plan.status == "blocked"
    assert trace.plan.review is not None
    assert trace.plan.review.blocked_reason == "missing_verification"


def test_react_loop_rejects_side_effect_plan_even_with_confirmation_token():
    trace = AgentTrace()
    tool_calls_seen = []

    result = react_loop(
        "set alert",
        lambda tc: tool_calls_seen.append(tc.name) or "alert set",
        model_call=lambda messages: (
            '{"tool": "plan", "args": {"goal": "set alert", "steps": ['
            '{"tool": "set_alert", "args": {"item_name": "arcane_energize", "threshold": 50}, "purpose": "write alert"}'
            ']}}'
        ),
        candidate_tools={"plan"},
        trace=trace,
        plan_confirmation_token="plan_confirm_anything",
    )

    assert "side_effect_tool" in result
    assert tool_calls_seen == []
    assert trace.termination_reason == "plan_blocked"
    assert trace.plan is not None
    assert trace.plan.status == "blocked"
    assert trace.plan.review is not None
    assert trace.plan.review.blocked_reason == "side_effect_tool"


def test_react_loop_rejects_plan_confirmation_token_for_changed_plan():
    original_plan = ExecutionPlan(
        goal="compare",
        steps=[PlanStep(tool="query_price", arguments={"item_name": "arcane_energize"})],
    )
    original_request = build_plan_confirmation_request(original_plan, review_execution_plan(original_plan))
    trace = AgentTrace()
    tool_calls_seen = []

    result = react_loop(
        "compare",
        lambda tc: tool_calls_seen.append(tc.name) or "price result",
        model_call=lambda messages: (
            '{"tool": "plan", "args": {"goal": "compare", "steps": ['
            '{"tool": "query_price", "args": {"item_name": "arcane_grace"}}'
            ']}}'
        ),
        candidate_tools={"plan"},
        trace=trace,
        plan_confirmation_token=original_request.confirmation_token,
    )

    assert "missing_verification" in result
    assert tool_calls_seen == []
    assert trace.termination_reason == "plan_blocked"
    assert trace.plan is not None
    assert trace.plan.status == "blocked"


def test_react_loop_with_plan():
    """mock LLM 返回 plan 调用，验证子工具被执行且 LLM 收到聚合结果。"""
    call_count = [0]
    tool_calls_seen = []

    def mock_model(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            # 第一次：返回 plan 调用（parse_tool_call 期望 {"tool": ..., "args": ...} 格式）
            return '{"tool": "plan", "args": {"goal": "对比", "steps": [{"tool": "query_price", "args": {"item_name": "充沛"}, "purpose": "查充沛"}]}}'
        # 第二次：LLM 根据聚合结果回答
        return "充沛当前卖价 45p"

    def mock_executor(tc: ToolCall) -> str:
        tool_calls_seen.append(tc.name)
        return f"result_for_{tc.name}"

    result = react_loop("对比充沛价格", mock_executor, model_call=mock_model)
    assert result == "充沛当前卖价 45p"
    assert "query_price" in tool_calls_seen


def test_react_loop_no_tool_returns_text():
    def mock_model(messages):
        return "你好，有什么可以帮你的？"

    result = react_loop("你好", lambda tc: "", model_call=mock_model)
    assert result == "你好，有什么可以帮你的？"
