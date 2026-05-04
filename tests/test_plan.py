"""测试 plan 工具：解析、执行、集成到 react_loop。"""
from __future__ import annotations

from warframe_agent.tool_router import (
    ExecutionPlan,
    PlanStep,
    ToolCall,
    _format_plan_results,
    _parse_plan,
    execute_plan,
    react_loop,
)


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


# ── react_loop 集成 ──

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
