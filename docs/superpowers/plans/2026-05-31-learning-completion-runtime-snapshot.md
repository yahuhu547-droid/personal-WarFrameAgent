# Learning Completion Runtime Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only runtime snapshot proving the GitHub personal Agent learning-borrowing route and Step 48/49 improvements are complete without enabling any future high-privilege runtime feature.

**Architecture:** Add a pure `learning_completion` snapshot module, embed it as top-level `learning_completion` in `/api/runtime/status`, and render a compact read-only section in the Runtime panel. The snapshot contains only safe aggregate status, step IDs, frozen boundaries, and next-stage guardrails; it does not read raw docs, secrets, local paths, or runtime tool data.

**Tech Stack:** Python, FastAPI runtime status API, JavaScript Runtime panel, pytest, Playwright, Markdown route ledger and rebuilt docs.

---

## File Structure

- `warframe_agent/learning_completion.py`: new pure snapshot builder for route/improvement completion.
- `tests/test_learning_completion.py`: unit tests for snapshot status, boundary fields, and redaction.
- `warframe_agent/web/app.py`: include `learning_completion` in `/api/runtime/status`.
- `tests/test_web_api.py`: assert the runtime API exposes the completion snapshot safely.
- `warframe_agent/web/static/js/app.js`: render Learning Completion in the Runtime panel.
- `tests/test_web_ui_playwright.py`: static and full Runtime panel rendering assertions.
- `docs/superpowers/plans/2026-05-31-learning-completion-runtime-snapshot.md`: this plan and execution ledger.
- `githubProduct/personal_agent_warframe_migration_step50_learning_completion_runtime_snapshot_zh.md`: Step 50 report.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: route ledger Step 50 update.
- `md/rebuilt/06-tools-models-safety.md`: safety docs update.
- `md/rebuilt/09-personal-agent-foundation.md`: foundation docs update.
- `md/rebuilt/10-learning-route-audit.md`: route audit update.
- `AGENTS.md`: cross-session progress and commands.

## Execution Sequence

### Task 50: Learning Completion Runtime Snapshot

**Files:**
- Create: `warframe_agent/learning_completion.py`
- Create: `tests/test_learning_completion.py`
- Modify: `warframe_agent/web/app.py`
- Modify: `tests/test_web_api.py`
- Modify: `warframe_agent/web/static/js/app.js`
- Modify: `tests/test_web_ui_playwright.py`
- Create: `githubProduct/personal_agent_warframe_migration_step50_learning_completion_runtime_snapshot_zh.md`
- Modify docs listed above.

- [x] **Step 1: Write failing unit tests**

Create `tests/test_learning_completion.py`:

```python
from warframe_agent.learning_completion import build_learning_completion_snapshot


def test_learning_completion_snapshot_marks_route_and_improvements_complete():
    snapshot = build_learning_completion_snapshot()

    assert snapshot["status"] == "complete"
    assert snapshot["legacy_non_voice_learning_complete"] is True
    assert snapshot["improvement_closure_complete"] is True
    assert snapshot["runtime_enablement_changed"] is False
    assert snapshot["completed_step_count"] >= 16
    assert "step49_future_capability_runtime_visibility" in snapshot["completed_steps"]
    assert "step48_future_capability_admission" in snapshot["improvement_steps"]


def test_learning_completion_snapshot_keeps_future_high_privilege_as_next_stage():
    snapshot = build_learning_completion_snapshot()

    assert "browser_gui_executor" in snapshot["next_stage_required"]
    assert "service_recovery" in snapshot["next_stage_required"]
    assert "plugin_install" in snapshot["next_stage_required"]
    assert "connector_enable" in snapshot["next_stage_required"]
    assert "real_voice_runtime" in snapshot["frozen_surfaces"]


def test_learning_completion_snapshot_is_safe_aggregate_only():
    snapshot = build_learning_completion_snapshot()
    serialized = str(snapshot)

    for forbidden in (
        "token",
        "secret",
        "api_key",
        "Authorization",
        "cookie",
        "account_id",
        "raw_payload",
        "raw_plan",
        "handler",
        "params",
        "/w",
        "C:\\\\Users",
        "127.0.0.1",
    ):
        assert forbidden not in serialized
```

- [x] **Step 2: Run red unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step50-red -p no:cacheprovider
```

Expected: fail because `warframe_agent.learning_completion` does not exist.

Observed: failed with `ModuleNotFoundError: No module named 'warframe_agent.learning_completion'`.

- [x] **Step 3: Implement pure snapshot builder**

Create `warframe_agent/learning_completion.py` with:

```python
POLICY_VERSION = "2026-05-31.learning-completion-v1"

COMPLETED_STEPS = (
    "step34_multi_agent_architecture_decision",
    "step35_plan_reviewer_verifier",
    "step36_ops_health_summary",
    "step37_memory_vault_index",
    "step38_browser_gui_safety_boundary",
    "step39_companion_experience_boundary_text_only",
    "step40_learning_phase_review",
    "step41_controlled_plan_confirmation",
    "step42_chat_plan_confirmation",
    "step43_gateway_boundary",
    "step44_plugin_policy",
    "step45_runtime_policy_visibility",
    "step46_non_voice_learning_closure",
    "step47_final_playwright_closure",
    "step48_future_capability_admission",
    "step49_future_capability_runtime_visibility",
)

def build_learning_completion_snapshot() -> dict[str, object]:
    return {
        "policy_version": POLICY_VERSION,
        "status": "complete",
        "legacy_non_voice_learning_complete": True,
        "improvement_closure_complete": True,
        "runtime_enablement_changed": False,
        "completed_step_count": len(COMPLETED_STEPS),
        "completed_steps": list(COMPLETED_STEPS),
        "improvement_steps": [
            "step48_future_capability_admission",
            "step49_future_capability_runtime_visibility",
        ],
        "frozen_surfaces": [
            "real_voice_runtime",
            "tts",
            "stt",
            "microphone",
            "recording",
            "live2d",
            "background_listening",
        ],
        "next_stage_required": [
            "browser_gui_executor",
            "service_recovery",
            "arbitrary_trigger_platform",
            "plugin_install",
            "connector_enable",
            "webhook_command_entry",
            "dm_command_entry",
        ],
        "guardrails": [
            "Completed learning-borrowing work does not enable future high-privilege runtime features.",
            "Future high-privilege capabilities require a separate design stage.",
            "Real voice and companion runtime remain frozen by current user instruction.",
        ],
    }
```

- [x] **Step 4: Integrate runtime API**

In `warframe_agent/web/app.py`:

```python
from ..learning_completion import build_learning_completion_snapshot
...
learning_completion_snapshot = build_learning_completion_snapshot()
...
"learning_completion": learning_completion_snapshot,
```

Extend `tests/test_web_api.py` to assert:

```python
completion = data["learning_completion"]
self.assertEqual(completion["status"], "complete")
self.assertTrue(completion["legacy_non_voice_learning_complete"])
self.assertTrue(completion["improvement_closure_complete"])
self.assertFalse(completion["runtime_enablement_changed"])
self.assertIn("step49_future_capability_runtime_visibility", completion["completed_steps"])
self.assertIn("browser_gui_executor", completion["next_stage_required"])
```

- [x] **Step 5: Integrate Runtime panel UI**

In `warframe_agent/web/static/js/app.js`, add:

```javascript
const learningCompletion = data && data.learning_completion ? data.learning_completion : {};
...
${renderRuntimeSummaryCard('Learning Completion', [`status=${learningCompletion.status || '-'}`, `steps=${learningCompletion.completed_step_count ?? 0}`, `improvements=${Array.isArray(learningCompletion.improvement_steps) ? learningCompletion.improvement_steps.length : 0}`])}
...
<h3 class="runtime-section-title">Learning Completion</h3>
${renderRuntimeLearningCompletion(learningCompletion)}
```

Add:

```javascript
function renderRuntimeLearningCompletion(snapshot) {
    if (!snapshot || !snapshot.status) return renderRuntimeEmpty('No learning completion snapshot');
    const details = [
        `status=${formatRuntimeSafeText(snapshot.status || '-')}`,
        `legacy_complete=${Boolean(snapshot.legacy_non_voice_learning_complete)}`,
        `improvement_complete=${Boolean(snapshot.improvement_closure_complete)}`,
        `runtime_changed=${Boolean(snapshot.runtime_enablement_changed)}`,
        `completed_steps=${snapshot.completed_step_count ?? 0}`,
    ];
    const steps = Array.isArray(snapshot.completed_steps) ? snapshot.completed_steps.slice(-6) : [];
    const nextStage = Array.isArray(snapshot.next_stage_required) ? snapshot.next_stage_required.slice(0, 8) : [];
    return `<div class="trading-memory-list">
        ${renderRuntimePolicySummary('Learning Completion', details)}
        ${steps.length ? steps.map(step => renderRuntimeLearningCompletionItem(step, 'completed')).join('') : renderRuntimeEmpty('No completed steps')}
        ${nextStage.length ? nextStage.map(step => renderRuntimeLearningCompletionItem(step, 'next-stage')).join('') : ''}
    </div>`;
}

function renderRuntimeLearningCompletionItem(name, label) {
    const badgeClass = label === 'completed' ? 'badge-green' : 'badge-gold';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(formatRuntimeSafeText(name || '-'))}</div>
                <div class="trading-memory-meta">learning_completion=${escapeHtml(label)}</div>
            </div>
            <span class="badge ${badgeClass}">${escapeHtml(label)}</span>
        </div>
    </div></div>`;
}
```

- [x] **Step 6: Extend UI tests**

In the mocked runtime status payload add `learning_completion`. Extend static contract assertions:

```python
assert "function renderRuntimeLearningCompletion" in app_script
assert "function renderRuntimeLearningCompletionItem" in app_script
assert "Learning Completion" in app_script
assert "learning_completion" in app_script
assert "legacy_non_voice_learning_complete" in app_script
assert "improvement_closure_complete" in app_script
```

Extend full Runtime panel assertions:

```python
expect(content).to_contain_text("Learning Completion")
expect(content).to_contain_text("status=complete")
expect(content).to_contain_text("legacy_complete=true")
expect(content).to_contain_text("improvement_complete=true")
expect(content).to_contain_text("runtime_changed=false")
expect(content).to_contain_text("step49_future_capability_runtime_visibility")
```

- [x] **Step 7: Run green target tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step50-learning -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step50-static -p no:cacheprovider
```

Expected: tests pass and JS syntax passes.

Observed: learning completion unit tests `3 passed`; Runtime static contract `1 passed`; `node --check` exited 0.

- [x] **Step 8: Run Web API and Runtime panel target tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_endpoint or runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step50-api -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-step50-playwright -p no:cacheprovider
```

Expected: ordinary sandbox may fail on SQLite WAL or uvicorn readiness; rerun in writable environment when needed.

Observed: ordinary sandbox failed on SQLite WAL and uvicorn readiness; writable environment reruns passed with Web API `2 passed, 70 deselected` and Runtime Playwright `1 passed`.

- [x] **Step 9: Update documentation**

Document Step 50 in:
- `githubProduct/personal_agent_warframe_migration_step50_learning_completion_runtime_snapshot_zh.md`
- `githubProduct/personal_agent_learning_route_ledger_zh.md`
- `md/rebuilt/06-tools-models-safety.md`
- `md/rebuilt/09-personal-agent-foundation.md`
- `md/rebuilt/10-learning-route-audit.md`
- `AGENTS.md`

Required wording:
- Step 50 is a final completion snapshot, not an old queue fix and not high-privilege enablement.
- GitHub personal Agent non-voice learning-borrowing route remains complete.
- Step 48/49 improvements are complete.
- Future high-privilege capabilities still require separate design and approval.

- [x] **Step 10: Final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "learning_completion or future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step50-policy -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step50-static-final -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/learning_completion.py','warframe_agent/future_capability_policy.py','warframe_agent/safety_policy.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
git diff --check -- warframe_agent\learning_completion.py warframe_agent\web\app.py warframe_agent\web\static\js\app.js tests\test_learning_completion.py tests\test_web_api.py tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-31-learning-completion-runtime-snapshot.md githubProduct\personal_agent_warframe_migration_step50_learning_completion_runtime_snapshot_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\06-tools-models-safety.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

Expected: policy/unit tests pass, static Runtime contract passes, AST OK, JS syntax OK, diff check exits 0. LF/CRLF warnings are acceptable.

Observed: policy/unit final run `23 passed, 33 deselected`; Runtime static contract `1 passed`; AST OK; `node --check` exited 0; `git diff --check` exited 0 with only LF/CRLF warnings. Web API and full Runtime Playwright target tests were already rerun in writable environment and passed with `2 passed, 70 deselected` and `1 passed`.

## Self-Review

- Spec coverage: covers the user's request to plan and execute until the learning-borrowing plan and improvements are complete.
- Placeholder scan: no TBD/TODO/fill-later items remain.
- Type consistency: snapshot keys match Web API and Runtime UI assertions.
- Safety boundary: this plan is visibility-only and does not enable high-risk capabilities, external connectors, shell/file writes, webhook/DM command entrypoints, or real voice.
