# Agent Plan Runtime Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an OpenManus-inspired, read-only `AgentPlan` / `AgentPlanStep` runtime snapshot to the existing ReAct trace, so complex `plan` tool executions are visible without changing the main agent execution path.

**Architecture:** Extend `warframe_agent.tool_router.AgentTrace` with an optional sanitized plan snapshot that is populated only when the existing `plan` tool is parsed and executed. Expose the snapshot through the existing `/api/runtime/status` `agent_trace` object using Web runtime redaction; do not persist full plan data, do not expose raw tool arguments, and do not let the plan view change tool execution.

**Tech Stack:** Python dataclasses, pytest, FastAPI runtime status serializer, existing `tool_router` ReAct loop and `md/rebuilt` documentation.

---

## File Structure

- Modify: `warframe_agent/tool_router.py`
  - Add `AgentPlanStep` and `AgentPlanSnapshot` dataclasses.
  - Add plan lifecycle helpers: register, mark running, mark completed/failed.
  - Attach a plan snapshot to `AgentTrace` during existing `plan` tool execution.
- Modify: `warframe_agent/web/app.py`
  - Serialize the plan snapshot under `agent_trace.plan`.
  - Redact goal, purpose, args summary, and errors with existing runtime-safe helpers.
- Modify: `tests/test_tool_router.py`
  - Add focused tests for successful and failing plan snapshots.
- Modify: `tests/test_web_api.py`
  - Extend the runtime status trace safety test to cover `agent_trace.plan`.
- Create: `githubProduct/personal_agent_warframe_migration_step12_agent_plan_runtime_snapshot_zh.md`
  - Capture the learning note for Step 12.
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/06-tools-models-safety.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

---

### Task 1: Red Tests For Plan Snapshots

**Files:**
- Modify: `tests/test_tool_router.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Add a successful plan snapshot test**

Add to `tests/test_tool_router.py`:

```python
    def test_react_loop_records_agent_plan_snapshot(self):
        from warframe_agent import tool_router

        trace = tool_router.AgentTrace()
        responses = iter([
            '{"tool": "plan", "args": {"goal": "compare two items", "steps": ['
            '{"tool": "query_price", "args": {"item_name": "arcane_energize", "token": "SECRET"}, "purpose": "check price"},'
            '{"tool": "price_trend", "args": {"item_name": "arcane_energize"}, "purpose": "check trend"}'
            ']}}',
            "final answer",
        ])

        result = tool_router.react_loop(
            "compare",
            tool_executor=lambda tc: f"result for {tc.name}",
            model_call=lambda messages: next(responses),
            max_iterations=3,
            trace=trace,
            candidate_tools={"plan"},
        )

        self.assertEqual(result, "final answer")
        self.assertIsNotNone(trace.plan)
        self.assertEqual(trace.plan.goal, "compare two items")
        self.assertEqual(trace.plan.status, "completed")
        self.assertEqual([step.status for step in trace.plan.steps], ["completed", "completed"])
        self.assertEqual([step.tool_name for step in trace.plan.steps], ["query_price", "price_trend"])
        self.assertEqual(trace.plan.steps[0].args_summary["token"], "[REDACTED]")
        self.assertEqual(len(trace.steps), 2)
```

- [ ] **Step 2: Add a failing plan snapshot test**

Add:

```python
    def test_react_loop_marks_agent_plan_failed_when_step_errors(self):
        from warframe_agent import tool_router

        trace = tool_router.AgentTrace()

        def execute(tc):
            if tc.name == "price_trend":
                raise RuntimeError("boom token=SECRET")
            return "ok"

        with self.assertRaises(RuntimeError):
            tool_router.react_loop(
                "compare",
                tool_executor=execute,
                model_call=lambda messages: (
                    '{"tool": "plan", "args": {"goal": "compare", "steps": ['
                    '{"tool": "query_price", "args": {"item_name": "arcane_energize"}, "purpose": "check price"},'
                    '{"tool": "price_trend", "args": {"item_name": "arcane_energize"}, "purpose": "check trend"}'
                    ']}}'
                ),
                max_iterations=3,
                trace=trace,
                candidate_tools={"plan"},
            )

        self.assertEqual(trace.status, "error")
        self.assertEqual(trace.termination_reason, "tool_error")
        self.assertEqual(trace.plan.status, "failed")
        self.assertEqual([step.status for step in trace.plan.steps], ["completed", "failed"])
        self.assertFalse(trace.plan.steps[1].ok)
        self.assertTrue(trace.plan.steps[1].error_present)
```

- [ ] **Step 3: Extend Web runtime safety test**

In `tests/test_web_api.py::test_runtime_status_includes_safe_agent_trace_snapshot`, import `AgentPlanSnapshot` and `AgentPlanStep`, attach a plan to `trace`, then assert:

```python
        trace.plan = AgentPlanSnapshot(
            goal="compare token=SECRET /w SecretSeller hi",
            status="completed",
            iteration=1,
            steps=[
                AgentPlanStep(
                    index=1,
                    tool_name="query_price",
                    purpose="check https://warframe.market/profile/SecretSeller",
                    args_summary={"item_name": "arcane_energize", "token": "[REDACTED]"},
                    status="completed",
                    ok=True,
                    error_present=False,
                    duration_ms=5.0,
                    result_present=True,
                )
            ],
        )
```

Assert the response contains `agent_trace.plan.present == True`, plan status, step count, and no raw secret strings.

- [ ] **Step 4: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "agent_plan" -q
```

Expected before implementation: import/attribute failures for the new plan dataclasses and `trace.plan`.

---

### Task 2: Implement Trace Plan Snapshot

**Files:**
- Modify: `warframe_agent/tool_router.py`

- [ ] **Step 1: Add plan dataclasses**

Add after `AgentStep`:

```python
@dataclass
class AgentPlanStep:
    index: int
    tool_name: str
    purpose: str
    args_summary: dict[str, Any]
    status: str = "pending"
    ok: bool | None = None
    error_present: bool = False
    duration_ms: float | None = None
    result_present: bool = False


@dataclass
class AgentPlanSnapshot:
    goal: str
    steps: list[AgentPlanStep] = field(default_factory=list)
    status: str = "idle"
    iteration: int = 0
```

Add `plan: AgentPlanSnapshot | None = None` to `AgentTrace`.

- [ ] **Step 2: Reset plan at trace start**

In `_start_trace`, add:

```python
    trace.plan = None
```

- [ ] **Step 3: Register a parsed plan**

Before `execute_plan(...)` in `react_loop`, add:

```python
                _register_trace_plan(trace, plan, iteration=iteration)
```

Add helper:

```python
def _register_trace_plan(trace: AgentTrace | None, plan: ExecutionPlan, *, iteration: int) -> None:
    if trace is None:
        return
    trace.plan = AgentPlanSnapshot(
        goal=str(plan.goal or ""),
        status="running",
        iteration=iteration,
        steps=[
            AgentPlanStep(
                index=index,
                tool_name=step.tool,
                purpose=str(step.purpose or ""),
                args_summary=_summarize_trace_arguments(step.arguments),
            )
            for index, step in enumerate(plan.steps, start=1)
        ],
    )
```

- [ ] **Step 4: Mark plan step lifecycle in `execute_plan`**

Change `execute_plan` to enumerate steps and wrap execution:

```python
    for index, step in enumerate(plan.steps, start=1):
        tc = ToolCall(name=step.tool, arguments=step.arguments)
        _mark_trace_plan_step(trace, index, status="running")
        started = time.perf_counter()
        try:
            result = _execute_tool_call_with_trace(tc, tool_executor, trace=trace, iteration=iteration)
        except Exception:
            _mark_trace_plan_step(
                trace,
                index,
                status="failed",
                ok=False,
                error_present=True,
                duration_ms=_elapsed_ms(started),
                result_present=False,
            )
            if trace is not None and trace.plan is not None:
                trace.plan.status = "failed"
            raise
        _mark_trace_plan_step(
            trace,
            index,
            status="completed",
            ok=_tool_result_ok(result),
            error_present=bool(_tool_result_error(result)),
            duration_ms=_elapsed_ms(started),
            result_present=result is not None,
        )
        results.append((step, result))
    if trace is not None and trace.plan is not None and trace.plan.status != "failed":
        trace.plan.status = "completed"
```

Add helper:

```python
def _mark_trace_plan_step(trace: AgentTrace | None, index: int, **updates) -> None:
    plan = getattr(trace, "plan", None) if trace is not None else None
    if plan is None:
        return
    for step in plan.steps:
        if step.index == index:
            for key, value in updates.items():
                if hasattr(step, key):
                    setattr(step, key, value)
            return
```

- [ ] **Step 5: Run green tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "agent_plan or lifecycle" -q
```

---

### Task 3: Expose Safe Runtime Plan View

**Files:**
- Modify: `warframe_agent/web/app.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Add safe plan serializers**

Add near `_safe_agent_trace_step`:

```python
def _safe_agent_plan_step(step: Any) -> dict[str, Any]:
    return {
        "index": getattr(step, "index", None),
        "tool_name": _runtime_redact_text(getattr(step, "tool_name", ""), max_chars=80),
        "purpose": _runtime_redact_text(getattr(step, "purpose", ""), max_chars=160),
        "args_summary": _safe_runtime_value(getattr(step, "args_summary", {})),
        "status": _runtime_redact_text(getattr(step, "status", ""), max_chars=40),
        "ok": getattr(step, "ok", None),
        "error_present": bool(getattr(step, "error_present", False)),
        "duration_ms": getattr(step, "duration_ms", None),
        "result_present": bool(getattr(step, "result_present", False)),
    }


def _safe_agent_plan_snapshot(plan: Any) -> dict[str, Any]:
    if plan is None:
        return {"present": False, "status": "idle", "goal_present": False, "step_count": 0, "steps": []}
    raw_steps = list(getattr(plan, "steps", []) or [])
    return {
        "present": True,
        "status": _runtime_redact_text(getattr(plan, "status", "idle") or "idle", max_chars=40),
        "iteration": getattr(plan, "iteration", 0),
        "goal_present": bool(getattr(plan, "goal", "")),
        "goal": _runtime_redact_text(getattr(plan, "goal", ""), max_chars=160),
        "step_count": len(raw_steps),
        "steps": [_safe_agent_plan_step(step) for step in raw_steps[:10]],
    }
```

- [ ] **Step 2: Include plan in `_agent_trace_status_snapshot`**

Add:

```python
        "plan": _safe_agent_plan_snapshot(getattr(trace, "plan", None)),
```

For the no-trace response, add:

```python
            "plan": _safe_agent_plan_snapshot(None),
```

- [ ] **Step 3: Run focused Web runtime test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k "runtime_status_includes_safe_agent_trace_snapshot" -q
```

If the environment hits SQLite WAL import issues, record that and rely on AST plus `tests/test_tool_router.py` for core behavior.

---

### Task 4: Documentation Sync And Verification

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step12_agent_plan_runtime_snapshot_zh.md`
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/06-tools-models-safety.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [ ] **Step 1: Add Step 12 migration note**

Document:

```markdown
# Step 12: AgentPlan 运行态只读快照

- 借鉴 OpenManus 的 plan/step 可观测性。
- 只在现有 `plan` 工具被调用时生成快照。
- Web runtime 只展示 goal 是否存在、最多 10 个步骤、工具名、安全参数摘要、状态、耗时和是否有结果。
- 不展示 raw arguments、完整 result_summary、final_answer、玩家 profile、whisper 或 token。
```

- [ ] **Step 2: Update rebuilt docs**

Add concise entries to:

- `03-user-interfaces.md`: runtime detail panel includes AgentPlan snapshot.
- `06-tools-models-safety.md`: plan snapshot is read-only and redacted.
- `07-operations-testing.md`: focused pytest and AST commands.
- `09-personal-agent-foundation.md`: Step 12 completion note.

- [ ] **Step 3: Run final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "agent_plan or lifecycle" -q
.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k "runtime_status_includes_safe_agent_trace_snapshot" -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/tool_router.py','warframe_agent/web/app.py','tests/test_tool_router.py','tests/test_web_api.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent/tool_router.py warframe_agent/web/app.py tests/test_tool_router.py tests/test_web_api.py docs/superpowers/plans/2026-05-26-agent-plan-runtime-snapshot.md githubProduct/personal_agent_warframe_migration_step12_agent_plan_runtime_snapshot_zh.md md/rebuilt/03-user-interfaces.md md/rebuilt/06-tools-models-safety.md md/rebuilt/07-operations-testing.md md/rebuilt/09-personal-agent-foundation.md
```

## Self-review

- Scope is a single subsystem: runtime plan observability.
- No new dependencies, no package install, no GitHub submit.
- Plan snapshot is read-only and redacted; it does not change tool execution or scanner DB boundaries.
- Web API verification may be environment-sensitive; report actual command output rather than implying success.
