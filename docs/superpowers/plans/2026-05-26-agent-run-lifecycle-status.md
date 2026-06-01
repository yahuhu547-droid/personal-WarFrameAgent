# AgentRun Lifecycle Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight OpenManus-inspired AgentRun lifecycle layer to the existing in-memory `AgentTrace`, so runtime status can show whether the latest ReAct run is idle, running, finished, or errored without exposing raw model/tool content.

**Architecture:** Extend the existing `AgentTrace` dataclass instead of introducing a new agent framework. `react_loop(...)` owns lifecycle transitions, `_finish_trace(...)` closes the run on every known exit path, and `/api/runtime/status` exposes only safe scalar lifecycle fields plus the existing redacted trace steps.

**Tech Stack:** Python dataclasses, existing `react_loop` in `warframe_agent/tool_router.py`, FastAPI runtime status serializer, vanilla JS runtime panel, pytest, Node syntax check.

---

## File Structure

- Modify `warframe_agent/tool_router.py`
  - Add lifecycle fields to `AgentTrace`: `status`, `started_at`, `ended_at`, `max_iterations`, `duration_ms`.
  - Add small helpers to start and finish traces.
  - Keep `final_answer` in memory only; do not persist or expose raw final answers through runtime status.
- Modify `tests/test_tool_router.py`
  - Add direct ReAct lifecycle tests that do not import the web app.
- Modify `warframe_agent/web/app.py`
  - Extend `_agent_trace_status_snapshot(agent)` with safe lifecycle scalar fields.
- Modify `warframe_agent/web/static/js/app.js`
  - Render lifecycle status, current iteration, max iterations, and duration in the runtime panel.
- Modify `tests/test_web_api.py`
  - Update the safe Agent Trace runtime test to assert lifecycle fields and continued redaction.
- Modify `tests/test_web_ui_playwright.py`
  - Update the mocked runtime response and UI assertions for lifecycle display.
- Create `githubProduct/personal_agent_warframe_migration_step5_agent_run_lifecycle_zh.md`
  - Record the learning outcome, verification evidence, and next learning item.
- Modify `md/rebuilt/*.md`
  - Synchronize the rebuilt docs after implementation. Do not commit or push to GitHub.

---

### Task 1: AgentTrace Lifecycle Test

**Files:**
- Modify: `tests/test_tool_router.py`

- [x] **Step 1: Write the failing test**

Add this test near the existing ReAct loop tests:

```python
def test_react_loop_records_lifecycle_status_for_final_answer():
    from warframe_agent import tool_router

    trace = tool_router.AgentTrace()

    result = tool_router.react_loop(
        "price check",
        tool_executor=lambda tc: "unused",
        model_call=lambda messages: "direct answer",
        max_iterations=3,
        trace=trace,
        candidate_tools={"query_price"},
    )

    assert result == "direct answer"
    assert trace.status == "finished"
    assert trace.termination_reason == "final_answer"
    assert trace.iterations == 1
    assert trace.max_iterations == 3
    assert trace.started_at is not None
    assert trace.ended_at is not None
    assert trace.ended_at >= trace.started_at
    assert trace.duration_ms is not None
    assert trace.duration_ms >= 0
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_tool_router.py -k "lifecycle_status" -q
```

Expected: fail with `AttributeError` or equivalent because `AgentTrace` does not yet expose lifecycle fields.

---

### Task 2: Minimal Lifecycle Implementation

**Files:**
- Modify: `warframe_agent/tool_router.py`
- Test: `tests/test_tool_router.py`

- [x] **Step 1: Add lifecycle fields**

Extend `AgentTrace` with:

```python
@dataclass
class AgentTrace:
    steps: list[AgentStep] = field(default_factory=list)
    termination_reason: str | None = None
    iterations: int = 0
    final_answer: str | None = None
    status: str = "idle"
    started_at: float | None = None
    ended_at: float | None = None
    max_iterations: int = 0
    duration_ms: float | None = None
```

- [x] **Step 2: Start lifecycle at the beginning of `react_loop`**

Call a helper after `messages` is initialized and before the loop:

```python
_start_trace(trace, max_iterations=max_iterations)
```

The helper:

```python
def _start_trace(trace: AgentTrace | None, *, max_iterations: int) -> None:
    if trace is None:
        return
    now = time.time()
    trace.status = "running"
    trace.started_at = now
    trace.ended_at = None
    trace.duration_ms = None
    trace.max_iterations = max(0, int(max_iterations))
    trace.termination_reason = None
    trace.iterations = 0
    trace.final_answer = None
```

- [x] **Step 3: Finish lifecycle in `_finish_trace`**

Update `_finish_trace(...)` so every existing exit path records status and duration:

```python
def _finish_trace(
    trace: AgentTrace | None,
    reason: str,
    *,
    iteration: int,
    final_answer: str | None = None,
) -> None:
    if trace is None:
        return
    trace.termination_reason = reason
    trace.iterations = max(trace.iterations, iteration)
    trace.status = "error" if reason == "model_error" else "finished"
    trace.ended_at = time.time()
    if trace.started_at is not None:
        trace.duration_ms = max(0.0, (trace.ended_at - trace.started_at) * 1000)
    if final_answer is not None:
        trace.final_answer = final_answer
```

- [x] **Step 4: Run the lifecycle test**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_tool_router.py -k "lifecycle_status" -q
```

Expected: pass.

---

### Task 3: Runtime API Lifecycle Snapshot

**Files:**
- Modify: `warframe_agent/web/app.py`
- Modify: `tests/test_web_api.py`

- [x] **Step 1: Update the web API test**

In `test_runtime_status_includes_safe_agent_trace_snapshot`, construct `AgentTrace` with lifecycle fields:

```python
trace = AgentTrace(
    termination_reason="final_answer",
    iterations=2,
    final_answer="secret final answer should not leak",
    status="finished",
    started_at=100.0,
    ended_at=102.5,
    max_iterations=3,
    duration_ms=2500.0,
)
```

Then assert:

```python
self.assertEqual(data["agent_trace"]["status"], "finished")
self.assertEqual(data["agent_trace"]["max_iterations"], 3)
self.assertEqual(data["agent_trace"]["duration_ms"], 2500.0)
self.assertEqual(data["agent_trace"]["started_at"], 100.0)
self.assertEqual(data["agent_trace"]["ended_at"], 102.5)
```

- [x] **Step 2: Add safe fields to serializer**

Extend `_agent_trace_status_snapshot(agent)` with:

```python
"status": _runtime_redact_text(getattr(trace, "status", "idle"), max_chars=40),
"started_at": getattr(trace, "started_at", None),
"ended_at": getattr(trace, "ended_at", None),
"max_iterations": getattr(trace, "max_iterations", 0),
"duration_ms": getattr(trace, "duration_ms", None),
```

Keep excluding `final_answer`, `raw_arguments`, `result_summary`, and tool error strings.

---

### Task 4: Runtime UI Lifecycle Display

**Files:**
- Modify: `warframe_agent/web/static/js/app.js`
- Modify: `tests/test_web_ui_playwright.py`

- [x] **Step 1: Update mocked runtime fixture**

Add these fields to the mocked `agent_trace` object:

```python
"status": "finished",
"started_at": 100.0,
"ended_at": 102.5,
"max_iterations": 3,
"duration_ms": 2500.0,
```

- [x] **Step 2: Add UI assertions**

Extend the runtime status Playwright test with:

```python
expect(content).to_contain_text("status=finished")
expect(content).to_contain_text("max=3")
expect(content).to_contain_text("duration=2500")
```

- [x] **Step 3: Render lifecycle fields**

Update `renderRuntimeStatusPanel(data)` and `renderRuntimeAgentTrace(trace)` so the Agent Trace summary shows:

```javascript
`status=${agentTrace.status || '-'}`
`iter=${agentTrace.iterations ?? 0}/${agentTrace.max_iterations ?? '-'}`
`duration=${agentTrace.duration_ms ?? '-'}ms`
```

Use `escapeHtml(...)` for every dynamic value.

---

### Task 5: Documentation Sync

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step5_agent_run_lifecycle_zh.md`
- Modify: `md/rebuilt/02-feature-scope.md`
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/04-web-api-reference.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/06-tools-models-safety.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: Write the learning note**

Record:

```markdown
# Step 5: AgentRun 生命周期状态

本步借鉴 OpenManus 的 Agent 生命周期思想，但只采用轻量运行态字段：`status`、`started_at`、`ended_at`、`max_iterations`、`duration_ms`。实现仍保留现有 `ChatAgent -> react_loop -> ToolRegistry` 链路，不复制 OpenManus 的完整类继承体系。
```

- [x] **Step 2: Update rebuilt docs**

Add concise notes that runtime status now includes lifecycle metadata and still hides raw final answers, tool arguments, result summaries, and tool error bodies.

---

### Task 6: Verification

**Files:**
- No production edits.

- [x] **Step 1: Run targeted unit tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_tool_router.py -k "lifecycle_status or trace" -q
```

- [x] **Step 2: Run static checks**

```powershell
& .\.venv\Scripts\python.exe -m py_compile warframe_agent\tool_router.py warframe_agent\web\app.py tests\test_tool_router.py tests\test_web_api.py tests\test_web_ui_playwright.py
```

```powershell
node --check warframe_agent\web\static\js\app.js
```

- [x] **Step 3: Record known limits**

If full web tests still fail because the sandbox cannot open the SQLite WAL database at `data/price_history.db`, record that limitation in the final response and in the learning note.

Actual result on 2026-05-26: `tests/test_tool_router.py -k "lifecycle"` passed; AST parse and `node --check` passed. `tests/test_web_api.py -k "agent_trace_snapshot"` failed during app import with SQLite WAL `unable to open database file`; the Playwright runtime panel target also failed because the uvicorn fixture did not become ready in this sandbox.

---

## Self-Review

- Spec coverage: Covers lifecycle state, safe runtime exposure, UI display, docs sync, and no GitHub submission.
- Placeholder scan: No unresolved placeholders are present.
- Type consistency: Lifecycle fields are Python floats/ints/strings in `AgentTrace`, serialized unchanged by the web API, and rendered as escaped text by the frontend.
