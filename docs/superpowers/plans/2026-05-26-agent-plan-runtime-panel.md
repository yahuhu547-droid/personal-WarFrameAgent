# Agent Plan Runtime Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the Step 12 `agent_trace.plan` snapshot in the Web runtime detail panel, so users can see multi-step plan status without exposing raw tool data.

**Architecture:** Keep all changes in the existing runtime panel renderer in `warframe_agent/web/static/js/app.js`. The panel will read the already-safe `/api/runtime/status` payload, add a compact AgentPlan summary card, and render plan steps with the same card/list style as Agent Trace; Playwright fixture tests will provide a mocked `agent_trace.plan`.

**Tech Stack:** Vanilla JavaScript, existing Web runtime panel CSS/classes, Playwright UI tests, Node syntax check.

---

## File Structure

- Modify: `warframe_agent/web/static/js/app.js`
  - Add an AgentPlan summary card to the runtime grid.
  - Add a new "Agent Plan" section between Agent Trace and recent tool calls.
  - Add `renderRuntimeAgentPlan(...)` and `renderRuntimeAgentPlanStep(...)`.
- Modify: `tests/test_web_ui_playwright.py`
  - Extend the mocked `/api/runtime/status` response with a safe and intentionally noisy `agent_trace.plan`.
  - Assert the runtime panel displays plan summary and steps.
  - Assert raw unsafe fields are not rendered.
- Create: `githubProduct/personal_agent_warframe_migration_step13_agent_plan_runtime_panel_zh.md`
  - Record the learning migration note.
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

---

### Task 1: Red Playwright Coverage

**Files:**
- Modify: `tests/test_web_ui_playwright.py`

- [ ] **Step 1: Add plan payload to runtime fixture**

Inside the existing `agent_trace` object in `_configure_page`, add:

```python
"plan": {
    "present": True,
    "status": "completed",
    "iteration": 1,
    "goal_present": True,
    "goal": "比较两个物品 [REDACTED]",
    "step_count": 2,
    "raw_arguments": {"token": "secret-token"},
    "result_summary": "secret-token PlayerSecret /w leak",
    "steps": [
        {
            "index": 1,
            "tool_name": "query_price",
            "purpose": "查价",
            "args_summary": {"item_name": "arcane_energize"},
            "status": "completed",
            "ok": True,
            "error_present": False,
            "duration_ms": 6.5,
            "result_present": True,
            "raw_arguments": {"token": "secret-token"},
            "result_summary": "secret-token PlayerSecret /w leak",
        },
        {
            "index": 2,
            "tool_name": "price_trend",
            "purpose": "看趋势",
            "args_summary": {"item_name": "arcane_energize"},
            "status": "failed",
            "ok": False,
            "error_present": True,
            "duration_ms": 3.2,
            "result_present": False,
        },
    ],
},
```

- [ ] **Step 2: Extend runtime panel test**

In `test_runtime_panel_renders_jobs_tasks_and_safe_state`, add assertions:

```python
    expect(content).to_contain_text("Agent Plan")
    expect(content).to_contain_text("plan_status=completed")
    expect(content).to_contain_text("goal_present=true")
    expect(content).to_contain_text("plan_steps=2")
    expect(content).to_contain_text("查价")
    expect(content).to_contain_text("看趋势")
    expect(content).to_contain_text("price_trend")
    expect(content).to_contain_text("result_present=false")
```

The existing forbidden-string loop should continue to reject `secret-token`, `raw_arguments`, `result_summary`, `PlayerSecret`, and `/w`.

- [ ] **Step 3: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q
```

Expected before implementation: fail because `Agent Plan`, `plan_status`, and plan steps are not rendered.

---

### Task 2: Render AgentPlan In Runtime Panel

**Files:**
- Modify: `warframe_agent/web/static/js/app.js`

- [ ] **Step 1: Add plan summary to runtime grid**

In `renderRuntimeStatusPanel(data)`, define:

```javascript
const agentPlan = agentTrace && agentTrace.plan ? agentTrace.plan : {};
```

Add a summary card after `Agent Trace`:

```javascript
${renderRuntimeSummaryCard('Agent Plan', [
    `present=${Boolean(agentPlan.present)}`,
    `plan_status=${agentPlan.status || '-'}`,
    `goal_present=${Boolean(agentPlan.goal_present)}`,
    `plan_steps=${agentPlan.step_count ?? 0}`
])}
```

- [ ] **Step 2: Add Agent Plan section**

After `renderRuntimeAgentTrace(agentTrace)`:

```javascript
<h3 class="runtime-section-title">Agent Plan</h3>
${renderRuntimeAgentPlan(agentPlan)}
```

- [ ] **Step 3: Add plan render functions**

Add after `renderRuntimeAgentTraceStep`:

```javascript
function renderRuntimeAgentPlan(plan) {
    if (!plan || !plan.present) {
        return `<div class="trading-memory-list">${renderRuntimeEmpty('No agent plan yet')}</div>`;
    }
    const steps = Array.isArray(plan.steps) ? plan.steps : [];
    return `<div class="trading-memory-list">
        <div class="card trading-memory-record"><div class="card-body">
            <div class="trading-memory-record-header">
                <div>
                    <div class="trading-memory-name">Agent Plan</div>
                    <div class="trading-memory-meta">plan_status=${escapeHtml(plan.status || '-')} | iteration=${escapeHtml(plan.iteration ?? '-')} | goal_present=${escapeHtml(Boolean(plan.goal_present))} | plan_steps=${escapeHtml(plan.step_count ?? steps.length)}</div>
                </div>
                <span class="badge ${plan.status === 'failed' ? 'badge-red' : plan.status === 'completed' ? 'badge-green' : plan.status === 'running' ? 'badge-gold' : 'badge-muted'}">${escapeHtml(plan.status || '-')}</span>
            </div>
            ${plan.goal ? `<div class="trading-memory-message">goal: ${escapeHtml(plan.goal)}</div>` : ''}
        </div></div>
        ${steps.length ? steps.map(renderRuntimeAgentPlanStep).join('') : renderRuntimeEmpty('No plan steps')}
    </div>`;
}

function renderRuntimeAgentPlanStep(step) {
    const args = renderRuntimeObject(step.args_summary || {});
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(step.index ?? '-')} · ${escapeHtml(step.tool_name || '-')}</div>
                <div class="trading-memory-meta">status=${escapeHtml(step.status || '-')} | purpose=${escapeHtml(step.purpose || '-')}</div>
            </div>
            <span class="badge ${step.ok === false ? 'badge-red' : step.ok === true ? 'badge-green' : 'badge-muted'}">${step.ok === false ? 'failed' : step.ok === true ? 'ok' : escapeHtml(step.status || 'unknown')}</span>
        </div>
        <div class="trading-memory-prices">
            <span>duration=${escapeHtml(step.duration_ms ?? '-')}ms</span>
            <span>result_present=${escapeHtml(Boolean(step.result_present))}</span>
            <span>error_present=${escapeHtml(Boolean(step.error_present))}</span>
        </div>
        ${args ? `<div class="trading-memory-message">args: ${args}</div>` : ''}
    </div></div>`;
}
```

- [ ] **Step 4: Run green test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q
node --check warframe_agent/web/static/js/app.js
```

---

### Task 3: Documentation Sync

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step13_agent_plan_runtime_panel_zh.md`
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [ ] **Step 1: Add Step 13 migration note**

Document:

```markdown
# Step 13: AgentPlan Web 运行态面板

- Web 运行态详情新增 Agent Plan summary 和步骤列表。
- 只读取 `/api/runtime/status.agent_trace.plan` 的安全字段。
- 不渲染 raw arguments、result_summary、final_answer、profile、whisper 或 token。
```

- [ ] **Step 2: Update rebuilt docs**

Add that the runtime panel visibly displays AgentPlan status, goal presence, step count, purpose, status, duration, and result/error presence.

- [ ] **Step 3: Add verification commands**

Add:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q
node --check warframe_agent/web/static/js/app.js
```

---

### Task 4: Final Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "agent_plan or lifecycle" -q
node --check warframe_agent/web/static/js/app.js
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['tests/test_web_ui_playwright.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent/web/static/js/app.js tests/test_web_ui_playwright.py docs/superpowers/plans/2026-05-26-agent-plan-runtime-panel.md githubProduct/personal_agent_warframe_migration_step13_agent_plan_runtime_panel_zh.md md/rebuilt/03-user-interfaces.md md/rebuilt/07-operations-testing.md md/rebuilt/09-personal-agent-foundation.md
```

## Self-review

- Scope is a frontend visibility follow-up to Step 12.
- Uses existing runtime panel classes; no new dependencies or package installs.
- Plan data remains read-only and frontend ignores raw unsafe fields even if they appear in a mocked payload.
- No GitHub submit or commit.
