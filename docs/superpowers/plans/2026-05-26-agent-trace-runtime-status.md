# Agent Trace Runtime Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the latest ReAct `AgentTrace` as a safe, read-only snapshot in the runtime status API and Web status panel.

**Architecture:** Keep `AgentTrace` as an in-memory diagnostic object on `ChatAgent`; serialize only a small redacted snapshot through `/api/runtime/status`. The snapshot redacts sensitive keys, bearer tokens, Warframe Market profile URLs with or without protocol, and full-line `/w` whisper fragments. It exposes only `error_present`, not tool error text. The frontend renders the snapshot inside the existing runtime status panel without changing chat answers, conversation logs, or model context.

**Tech Stack:** Python 3.14 test venv, FastAPI `JSONResponse`, existing `ChatAgent.last_agent_trace`, vanilla JS runtime panel, pytest, Playwright.

---

## File Structure

- Modify `warframe_agent/web/app.py`
  - Add `_agent_trace_status_snapshot(agent)` and `_safe_agent_trace_step(step)`.
  - Extend runtime redaction for profile URLs and `/w` whisper fragments.
  - Include `"agent_trace": ...` in `/api/runtime/status`.
- Modify `tests/test_web_api.py`
  - Add runtime status tests proving trace serialization is present, bounded, and redacted.
- Modify `warframe_agent/web/static/js/app.js`
  - Render an "Agent Trace" summary card and detail section in `renderRuntimeStatusPanel(data)`.
  - Add `renderRuntimeAgentTrace(trace)` and `renderRuntimeAgentTraceStep(step)`.
- Modify `tests/test_web_ui_playwright.py`
  - Add mocked `agent_trace` data to runtime status fixture.
  - Assert runtime status panel shows trace summary and hides sensitive/raw fields.
- Create `githubProduct/personal_agent_warframe_migration_step4_runtime_trace_zh.md`
  - Record the learning outcome, tests run, and next checklist item.

---

### Task 1: Backend Agent Trace Snapshot

**Files:**
- Modify: `warframe_agent/web/app.py`
- Test: `tests/test_web_api.py`

- [x] **Step 1: Write the failing API test**

Add this test near the existing runtime status tests in `tests/test_web_api.py`:

```python
    @patch("warframe_agent.web.app.feishu_bot")
    @patch("warframe_agent.web.app.monitor")
    def test_runtime_status_includes_safe_agent_trace_snapshot(self, mock_monitor, mock_feishu):
        from warframe_agent.tool_router import AgentStep, AgentTrace
        from warframe_agent.web import app as web_app

        mock_feishu.status_snapshot.return_value = {"enabled": False, "configured": False, "available": True, "managed_running": False}
        mock_monitor.scheduler_status_snapshot.return_value = {"running": True, "has_scheduler": True, "total": 0, "jobs": []}
        mock_monitor.daily_report_status_snapshot.return_value = {"enabled": False, "report_time": None, "should_send_now": False, "last_report_date": None}

        trace = AgentTrace(
            termination_reason="final_answer",
            iterations=2,
            final_answer="secret final answer should not leak",
        )
        trace.steps.append(AgentStep(
            iteration=1,
            tool_name="query_price",
            args_summary={
                "item_name": "arcane_energize",
                "question": "/w SecretSeller " + ("x" * 160) + " tail_secret token=abc",
                "profile": "warframe.market/profile/SecretSeller",
                "profile_www": "www.warframe.market/profile/SecretSeller",
                "token": "[REDACTED]",
            },
            raw_arguments_safe=False,
            raw_arguments=None,
            ok=True,
            error="/w ErrorSeller " + ("x" * 160) + " error_tail_secret Bearer abc123 failed",
            duration_ms=12.5,
            result_summary="token=secret-token /w PlayerSecret hi https://warframe.market/profile/PlayerSecret",
        ))
        old_trace = getattr(web_app.chat_agent, "last_agent_trace", None)
        web_app.chat_agent.last_agent_trace = trace
        try:
            response = self.client.get("/api/runtime/status")
        finally:
            web_app.chat_agent.last_agent_trace = old_trace

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("agent_trace", data)
        self.assertTrue(data["agent_trace"]["present"])
        self.assertTrue(data["agent_trace"]["final_answer_present"])
        self.assertEqual(data["agent_trace"]["termination_reason"], "final_answer")
        self.assertEqual(data["agent_trace"]["iterations"], 2)
        self.assertEqual(data["agent_trace"]["step_count"], 1)
        self.assertEqual(data["agent_trace"]["steps"][0]["tool_name"], "query_price")
        self.assertEqual(data["agent_trace"]["steps"][0]["args_summary"]["item_name"], "arcane_energize")
        self.assertNotIn("token", data["agent_trace"]["steps"][0]["args_summary"])
        self.assertTrue(data["agent_trace"]["steps"][0]["error_present"])
        self.assertNotIn("error_summary", data["agent_trace"]["steps"][0])
        self.assertTrue(data["agent_trace"]["steps"][0]["has_result"])
        self.assertGreater(data["agent_trace"]["steps"][0]["result_chars"], 0)
        serialized = str(data)
        for forbidden in ["secret final answer", "result_summary", "raw_arguments", "secret-token", "PlayerSecret", "SecretSeller", "ErrorSeller", "tail_secret", "error_tail_secret", "/w ", "warframe.market/profile", "Bearer", "token=secret"]:
            self.assertNotIn(forbidden, serialized)
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "agent_trace_snapshot" -q
```

Expected: fail because `/api/runtime/status` does not yet include `agent_trace`.

- [x] **Step 3: Implement safe serializer**

In `warframe_agent/web/app.py`, add profile/whisper runtime redaction and helpers after `_recent_tool_calls_status_snapshot(...)`:

```python
def _safe_agent_trace_step(step: Any) -> dict[str, Any]:
    safe_step = {
        "iteration": getattr(step, "iteration", None),
        "tool_name": _runtime_redact_text(getattr(step, "tool_name", ""), max_chars=80),
        "args_summary": _safe_runtime_value(getattr(step, "args_summary", {})),
        "ok": getattr(step, "ok", None),
        "duration_ms": getattr(step, "duration_ms", None),
    }
    safe_step["error_present"] = bool(getattr(step, "error", None))
    result_summary = getattr(step, "result_summary", None)
    if result_summary:
        safe_step["has_result"] = True
        safe_step["result_chars"] = len(str(result_summary))
    else:
        safe_step["has_result"] = False
        safe_step["result_chars"] = 0
    return safe_step


def _agent_trace_status_snapshot(agent: Any) -> dict[str, Any]:
    trace = getattr(agent, "last_agent_trace", None)
    if trace is None:
        return {"present": False, "step_count": 0, "steps": []}
    raw_steps = list(getattr(trace, "steps", []) or [])
    steps = [_safe_agent_trace_step(step) for step in raw_steps[-5:]]
    return {
        "present": True,
        "termination_reason": _runtime_redact_text(getattr(trace, "termination_reason", None), max_chars=80),
        "iterations": getattr(trace, "iterations", 0),
        "step_count": len(raw_steps),
        "steps": steps,
        "final_answer_present": bool(getattr(trace, "final_answer", None)),
    }
```

Then include the snapshot in `runtime_status()`:

```python
agent_trace_snapshot = _agent_trace_status_snapshot(chat_agent)
...
"agent_trace": agent_trace_snapshot,
```

- [ ] **Step 4: Run backend tests**

Status on 2026-05-26: blocked in normal sandbox by SQLite WAL (`sqlite3.OperationalError: unable to open database file`). Escalated pytest was requested but rejected by the Codex desktop usage limit, so this remains pending until escalation is available.

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status" -q
```

Expected: all selected runtime status tests pass.

---

### Task 2: Frontend Runtime Panel Trace Section

**Files:**
- Modify: `warframe_agent/web/static/js/app.js`
- Test: `tests/test_web_ui_playwright.py`

- [x] **Step 1: Write the failing Playwright test/fixture update**

Update the mocked `/api/runtime/status` response in `tests/test_web_ui_playwright.py` to include:

```python
"agent_trace": {
    "present": True,
    "termination_reason": "final_answer",
    "iterations": 2,
    "step_count": 1,
    "steps": [{
        "iteration": 1,
        "tool_name": "query_price",
        "ok": True,
        "duration_ms": 8.5,
        "args_summary": {"item_name": "arcane_energize", "token": "[REDACTED]"},
        "has_result": True,
        "result_chars": 20,
        "error_present": True,
        "error_summary": "secret-token ErrorSeller /w leak",
        "raw_arguments": {"token": "secret-token"},
        "result_summary": "secret-token PlayerSecret /w leak",
    }],
    "final_answer_present": True,
    "final_answer": "secret final answer",
},
```

Add a test near the runtime status panel tests:

```python
def test_runtime_status_panel_shows_agent_trace(page):
    setup_page(page)

    page.locator(".status-indicator").click()

    content = page.locator(".detail-panel")
    expect(content).to_contain_text("Agent Trace")
    expect(content).to_contain_text("final_answer")
    expect(content).to_contain_text("query_price")
    expect(content).to_contain_text("arcane_energize")
    expect(content).to_contain_text("[REDACTED]")
    expect(content).to_contain_text("result_chars=20")
    expect(content).to_contain_text("error_present=true")
    expect(content).not_to_contain_text("secret-token")
    expect(content).not_to_contain_text("raw_arguments")
    expect(content).not_to_contain_text("result_summary")
```

- [ ] **Step 2: Run Playwright test to verify it fails**

Status on 2026-05-26: attempted, but the fixture could not start uvicorn because importing `warframe_agent.web.app` triggers SQLite WAL and fails in the normal sandbox. This requires the same escalated pytest path as backend tests.

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py -k "agent_trace" -q
```

Expected: fail because the runtime panel does not render an Agent Trace section yet.

- [x] **Step 3: Implement runtime panel rendering**

In `warframe_agent/web/static/js/app.js`, inside `renderRuntimeStatusPanel(data)` add:

```javascript
const agentTrace = data && data.agent_trace ? data.agent_trace : {};
...
${renderRuntimeSummaryCard('Agent Trace', [`present=${Boolean(agentTrace.present)}`, `reason=${agentTrace.termination_reason || '-'}`, `steps=${agentTrace.step_count ?? 0}`])}
...
<h3 class="runtime-section-title">Agent Trace</h3>
${renderRuntimeAgentTrace(agentTrace)}
```

Add helper functions after `renderRuntimeToolCall(call)`:

```javascript
function renderRuntimeAgentTrace(trace) {
    if (!trace || !trace.present) return renderRuntimeEmpty('暂无 ReAct trace');
    const steps = Array.isArray(trace.steps) ? trace.steps : [];
    return `
        <div class="trading-memory-list">
            <div class="card trading-memory-record"><div class="card-body">
                <div class="trading-memory-record-header">
                    <div>
                        <div class="trading-memory-name">Agent Trace</div>
                        <div class="trading-memory-meta">reason=${escapeHtml(trace.termination_reason || '-')} · iterations=${escapeHtml(trace.iterations ?? '-')} · steps=${escapeHtml(trace.step_count ?? steps.length)}</div>
                    </div>
                    <span class="badge ${trace.termination_reason === 'final_answer' ? 'badge-green' : 'badge-gold'}">${escapeHtml(trace.termination_reason || 'unknown')}</span>
                </div>
            </div></div>
            ${steps.length ? steps.map(renderRuntimeAgentTraceStep).join('') : renderRuntimeEmpty('暂无工具步骤')}
        </div>
    `;
}

function renderRuntimeAgentTraceStep(step) {
    const args = renderRuntimeObject(step.args_summary || {});
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(step.tool_name || '-')}</div>
                <div class="trading-memory-meta">iteration=${escapeHtml(step.iteration ?? '-')} · result_chars=${escapeHtml(step.result_chars ?? 0)}</div>
            </div>
            <span class="badge ${step.ok === false ? 'badge-red' : step.ok === true ? 'badge-green' : 'badge-muted'}">${step.ok === false ? 'failed' : step.ok === true ? 'ok' : 'unknown'}</span>
        </div>
        <div class="trading-memory-prices">
            <span>duration=${escapeHtml(step.duration_ms ?? '-')}ms</span>
            <span>has_result=${escapeHtml(Boolean(step.has_result))}</span>
            <span>error_present=${escapeHtml(Boolean(step.error_present))}</span>
        </div>
        ${args ? `<div class="trading-memory-message">args: ${args}</div>` : ''}
    </div></div>`;
}
```

- [ ] **Step 4: Run frontend tests**

Status on 2026-05-26: pending for the same SQLite WAL sandbox reason; `node --check warframe_agent/web/static/js/app.js` passed.

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py -k "runtime_status or agent_trace" -q
```

Expected: selected runtime status UI tests pass.

---

### Task 3: Documentation, Verification, Commit

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step4_runtime_trace_zh.md`
- Modify: `docs/superpowers/plans/2026-05-26-agent-trace-runtime-status.md`

- [ ] **Step 1: Write execution note**

Create:

```markdown
# Personal Agent 学习迁移 Step 4：Runtime Agent Trace 面板

日期：2026-05-26

## 已落地内容

- `/api/runtime/status` 返回 `agent_trace` 安全快照。
- Web 运行态详情面板展示 Agent Trace 摘要和最近工具步骤。
- 不返回 `final_answer`、`raw_arguments` 或敏感 token。

## 验证命令

- `& .\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status" -q`
- `& .\.venv\Scripts\python.exe -m pytest tests\test_router.py tests\test_plan.py tests\test_tool_router.py -q`
- `& .\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py -k "runtime_status or agent_trace" -q`

## 下一步

继续评估是否需要把 `AgentTrace` 抽成更完整的 `AgentRun` 视图；暂时不持久化 trace。
```

- [ ] **Step 2: Run final verification**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status" -q
& .\.venv\Scripts\python.exe -m pytest tests\test_router.py tests\test_plan.py tests\test_tool_router.py -q
```

If Playwright dependencies are available, also run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py -k "runtime_status or agent_trace" -q
```

- [ ] **Step 3: White-list stage and commit**

Stage only these files:

```powershell
git add -- docs/superpowers/plans/2026-05-26-agent-trace-runtime-status.md githubProduct/personal_agent_warframe_migration_step4_runtime_trace_zh.md warframe_agent/web/app.py warframe_agent/web/static/js/app.js tests/test_web_api.py tests/test_web_ui_playwright.py
```

Commit:

```powershell
git commit -m "feat: show agent trace in runtime status"
```

Push:

```powershell
git push personal codex-personal-agent-foundation:main
```

---

## Self-Review

- Spec coverage: Covers backend snapshot, frontend display, tests, docs, and push workflow.
- Placeholder scan: No TBD/TODO/fill-later placeholders.
- Type consistency: Uses `AgentTrace`, `AgentStep`, `termination_reason`, `iterations`, `steps`, and `args_summary` exactly as implemented in Step 2/3.
- Scope control: Keeps trace in memory and does not persist it to conversation log.
