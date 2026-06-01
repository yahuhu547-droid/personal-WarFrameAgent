# Learning Completion Acceptance Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only machine-checkable acceptance snapshot proving the learning-borrowing route and Step 48/49 improvements are accepted as complete.

**Architecture:** Extend the existing pure `learning_completion` snapshot with safe aggregate acceptance fields. Reuse the existing `/api/runtime/status.learning_completion` API and Runtime panel section; do not create a new endpoint, control, executor, connector, scheduler, or background worker.

**Tech Stack:** Python, FastAPI runtime status API, JavaScript Runtime panel, pytest, Playwright, Markdown route ledger and rebuilt docs.

---

## File Structure

- `warframe_agent/learning_completion.py`: extend the pure snapshot builder with acceptance status and checklist.
- `tests/test_learning_completion.py`: add red/green tests for acceptance checklist shape, Step 50 anchor, high-risk runtime not enabled, and safe aggregate output.
- `tests/test_web_api.py`: assert runtime status exposes acceptance snapshot safely.
- `warframe_agent/web/static/js/app.js`: render acceptance summary and checklist inside the existing Learning Completion section.
- `tests/test_web_ui_playwright.py`: extend mocked runtime payload, static contract, and Runtime panel assertions.
- `githubProduct/personal_agent_warframe_migration_step51_learning_completion_acceptance_snapshot_zh.md`: Step 51 report.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: route ledger Step 51 update.
- `md/rebuilt/06-tools-models-safety.md`: safety docs update.
- `md/rebuilt/09-personal-agent-foundation.md`: foundation docs update.
- `md/rebuilt/10-learning-route-audit.md`: route audit update.
- `AGENTS.md`: cross-session progress, verification, and next-step state.

## Execution Sequence

### Task 51: Learning Completion Acceptance Snapshot

**Files:**
- Modify: `warframe_agent/learning_completion.py`
- Modify: `tests/test_learning_completion.py`
- Modify: `tests/test_web_api.py`
- Modify: `warframe_agent/web/static/js/app.js`
- Modify: `tests/test_web_ui_playwright.py`
- Create: `githubProduct/personal_agent_warframe_migration_step51_learning_completion_acceptance_snapshot_zh.md`
- Modify docs listed above.

- [x] **Step 1: Write failing acceptance tests**

Add tests asserting:

```python
def test_learning_completion_acceptance_snapshot_anchors_step50_closure():
    snapshot = build_learning_completion_snapshot()

    assert snapshot["acceptance_status"] == "accepted"
    acceptance = snapshot["acceptance_snapshot"]
    assert acceptance["latest_closure_step"] == "step50_learning_completion_runtime_snapshot"
    assert acceptance["acceptance_record_step"] == "step51_learning_completion_acceptance_snapshot"
    assert acceptance["all_items_passed"] is True
    assert acceptance["checklist_count"] >= 7
    assert "step50_learning_completion_runtime_snapshot" in snapshot["completed_steps"]


def test_learning_completion_acceptance_checklist_keeps_runtime_high_risk_disabled():
    snapshot = build_learning_completion_snapshot()
    checklist = snapshot["acceptance_snapshot"]["checklist"]

    by_id = {item["id"]: item for item in checklist}
    assert by_id["runtime_high_privilege_not_enabled"]["status"] == "passed"
    assert by_id["runtime_high_privilege_not_enabled"]["runtime_enabled"] is False
    assert by_id["real_voice_runtime_frozen"]["runtime_enabled"] is False
    assert by_id["future_capabilities_require_new_stage"]["runtime_enabled"] is False
    assert by_id["step50_closure_snapshot_present"]["evidence"] == "step50_learning_completion_runtime_snapshot"
```

- [x] **Step 2: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step51-red -p no:cacheprovider
```

Expected: fail because `acceptance_status` / `acceptance_snapshot` are missing.

Observed: failed as expected with `KeyError: 'acceptance_status'` and `KeyError: 'acceptance_snapshot'`.

- [x] **Step 3: Implement acceptance snapshot**

In `warframe_agent/learning_completion.py`:

- Add `"step50_learning_completion_runtime_snapshot"` to `COMPLETED_STEPS`.
- Add immutable `ACCEPTANCE_CHECKLIST` with safe aggregate items:
  - `legacy_non_voice_learning_route_complete`
  - `step48_49_improvements_complete`
  - `runtime_status_api_exposes_completion`
  - `runtime_panel_exposes_completion`
  - `runtime_high_privilege_not_enabled`
  - `real_voice_runtime_frozen`
  - `future_capabilities_require_new_stage`
  - `step50_closure_snapshot_present`
- Return:

```python
"acceptance_status": "accepted",
"acceptance_snapshot": {
    "latest_closure_step": "step50_learning_completion_runtime_snapshot",
    "acceptance_record_step": "step51_learning_completion_acceptance_snapshot",
    "all_items_passed": True,
    "checklist_count": len(ACCEPTANCE_CHECKLIST),
    "checklist": [dict(item) for item in ACCEPTANCE_CHECKLIST],
},
```

- [x] **Step 4: Run green unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step51-learning -p no:cacheprovider
```

Expected: all learning completion tests pass.

Observed: `5 passed`.

- [x] **Step 5: Extend Web API and Runtime panel tests**

Extend `tests/test_web_api.py::test_runtime_status_endpoint`:

```python
self.assertEqual(completion["acceptance_status"], "accepted")
acceptance = completion["acceptance_snapshot"]
self.assertEqual(acceptance["latest_closure_step"], "step50_learning_completion_runtime_snapshot")
self.assertEqual(acceptance["acceptance_record_step"], "step51_learning_completion_acceptance_snapshot")
self.assertTrue(acceptance["all_items_passed"])
self.assertIn("step50_learning_completion_runtime_snapshot", completion["completed_steps"])
```

Extend `tests/test_web_ui_playwright.py` mock payload with `acceptance_status` and `acceptance_snapshot`. Extend static contract assertions for `acceptance_snapshot`, `acceptance_status`, `latest_closure_step`, and `acceptance_record_step`. Extend Runtime panel assertions for `acceptance=accepted` and `step50_learning_completion_runtime_snapshot`.

- [x] **Step 6: Run red integration/static tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step51-red-static -p no:cacheprovider
```

Expected: fail until Runtime JS references the new acceptance fields.

Observed: failed as expected because `acceptance_status` was not present in `app.js`.

- [x] **Step 7: Implement Runtime panel rendering**

In `warframe_agent/web/static/js/app.js`:

- Add acceptance to Learning Completion summary card.
- In `renderRuntimeLearningCompletion(...)`, add detail lines:

```javascript
`acceptance=${formatRuntimeSafeText(snapshot.acceptance_status || '-')}`,
`closure_step=${formatRuntimeSafeText(acceptance.latest_closure_step || '-')}`,
```

- Render up to 8 checklist rows using existing `renderRuntimeLearningCompletionItem(name, label)`.
- Keep all output escaped through `formatRuntimeSafeText(...)` / `escapeHtml(...)`.

- [x] **Step 8: Run target green tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step51-learning -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step51-static -p no:cacheprovider
```

Expected: unit tests, JS syntax, and static Runtime contract pass.

Observed: learning completion unit tests `5 passed`; `node --check` exited 0; Runtime static contract `1 passed`.

- [x] **Step 9: Run Web API and Runtime panel targets**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_endpoint or runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step51-api -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-step51-playwright -p no:cacheprovider
```

Expected: ordinary sandbox may fail on SQLite WAL or uvicorn readiness; rerun in writable environment when needed.

Observed: ordinary sandbox failed on SQLite WAL and uvicorn readiness; writable environment reruns passed with Web API `2 passed, 70 deselected` and Runtime Playwright `1 passed`.

- [x] **Step 10: Update documentation**

Document Step 51 in:
- `githubProduct/personal_agent_warframe_migration_step51_learning_completion_acceptance_snapshot_zh.md`
- `githubProduct/personal_agent_learning_route_ledger_zh.md`
- `md/rebuilt/06-tools-models-safety.md`
- `md/rebuilt/09-personal-agent-foundation.md`
- `md/rebuilt/10-learning-route-audit.md`
- `AGENTS.md`

Required wording:
- Step 51 is an acceptance snapshot / anti-drift improvement.
- It does not reopen the old learning queue.
- It does not enable high-privilege runtime capabilities.
- Step 50 remains the latest closure step; Step 51 records acceptance evidence.

- [x] **Step 11: Final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "learning_completion or future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step51-policy -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step51-static-final -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/learning_completion.py','warframe_agent/future_capability_policy.py','warframe_agent/safety_policy.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
git diff --check -- warframe_agent\learning_completion.py warframe_agent\web\static\js\app.js tests\test_learning_completion.py tests\test_web_api.py tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-31-learning-completion-acceptance-snapshot.md githubProduct\personal_agent_warframe_migration_step51_learning_completion_acceptance_snapshot_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\06-tools-models-safety.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

Expected: policy/unit tests pass, static Runtime contract passes, AST OK, JS syntax OK, diff check exits 0. LF/CRLF warnings are acceptable.

Observed: policy/unit final run `25 passed, 33 deselected`; Runtime static contract `1 passed`; AST OK; `node --check` exited 0; `git diff --check` exited 0 with only LF/CRLF warnings. Web API and full Runtime Playwright target tests were already rerun in writable environment and passed with `2 passed, 70 deselected` and `1 passed`.

## Self-Review

- Spec coverage: covers the remaining safe improvement identified by code/API/UI audit.
- Placeholder scan: no TBD/TODO/fill-later items remain.
- Type consistency: acceptance field names are the same in Python snapshot, API tests, UI mock, static assertions, and rendered output.
- Safety boundary: no high-risk runtime feature, external connector, shell/file write, webhook/DM entrypoint, plugin install, GitHub upload, dependency download, or real voice capability is enabled.
