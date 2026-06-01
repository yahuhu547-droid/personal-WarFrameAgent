# Future Capability Runtime Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show Step 48 `future_capability_policy` in the Runtime panel as read-only safety information without enabling any high-privilege runtime feature.

**Architecture:** Reuse the existing Runtime policy UI pattern for Gateway and Plugin policy. The frontend reads `data.safety_policy.future_capability_policy`, renders a summary card and a capped matrix with safe fields only, and continues to filter sensitive keys and text before display. Backend behavior remains policy-only; no tools, executors, connectors, services, buttons, or controls are added.

**Tech Stack:** JavaScript frontend in `warframe_agent/web/static/js/app.js`, pytest static and Playwright tests, FastAPI runtime status API contract tests, Markdown route ledger and rebuilt docs.

---

## File Structure

- `warframe_agent/web/static/js/app.js`: add Future Capability Policy summary and detail rendering.
- `tests/test_web_ui_playwright.py`: add static contract assertions and extend Runtime panel browser fixture/assertions.
- `tests/test_web_api.py`: lock the runtime status API contract for `future_capability_policy` and `future_capability_admission.enabled=False`.
- `docs/superpowers/plans/2026-05-31-future-capability-runtime-visibility.md`: this plan and execution ledger.
- `githubProduct/personal_agent_warframe_migration_step49_future_capability_runtime_visibility_zh.md`: Step 49 learning report.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: route ledger Step 49 update.
- `md/rebuilt/06-tools-models-safety.md`: safety docs update.
- `md/rebuilt/09-personal-agent-foundation.md`: foundation docs update.
- `md/rebuilt/10-learning-route-audit.md`: route audit update.
- `AGENTS.md`: cross-session progress and commands.

## Execution Sequence

### Task 49: Future Capability Runtime Visibility

**Files:**
- Modify: `tests/test_web_ui_playwright.py`
- Modify: `tests/test_web_api.py`
- Modify: `warframe_agent/web/static/js/app.js`
- Create: `githubProduct/personal_agent_warframe_migration_step49_future_capability_runtime_visibility_zh.md`
- Modify docs listed above.

- [x] **Step 1: Write failing frontend static contract tests**

Extend the Runtime panel static contract to require:

```python
assert "function renderRuntimeFutureCapabilityPolicy" in app_script
assert "function renderRuntimeFutureCapabilityPolicyItem" in app_script
assert "Future Capability Policy" in app_script
assert "future_capability_policy" in app_script
assert "future_capability_admission" in app_script
assert "runtime_enablement_allowed" in app_script
assert "design_required_before_runtime" in app_script
assert "credential" in app_script
assert "private[_-]?network" in app_script
assert "local[_-]?path" in app_script
assert "user[_-]?id" in app_script
```

- [x] **Step 2: Extend Playwright fixture and visible assertions**

Add to the mocked `/api/runtime/status.safety_policy`:

```python
"future_capability_admission": {
    "available": True,
    "default": "design_required",
    "requires_explicit_enable": True,
    "enabled": False,
    "scope": "future_high_risk_features_policy_only",
},
"future_capability_policy": {
    "default_mode": "design_required_before_runtime",
    "runtime_enablement_allowed": False,
    "automatic_enable_enabled": False,
    "design_review_required": True,
    "human_confirmation_required_before_runtime": True,
    "decision_counts": {
        "requires_new_stage_design": 1,
        "blocked_uncontrolled_runtime": 1,
    },
    "capability_matrix": [
        {
            "capability": "browser_gui_executor",
            "decision": "requires_new_stage_design",
            "trust_boundary": "future_high_privilege_surface",
            "runtime_enabled": False,
            "requires_explicit_user_approval": True,
            "reason": "future_capability_requires_permissions_confirmation_interrupts_and_audit_design",
            "raw_plan": "token=secret-token /w PlayerSecret",
            "private_network_url": "http://127.0.0.1/admin",
        },
        {
            "capability": "shell",
            "decision": "blocked_uncontrolled_runtime",
            "trust_boundary": "uncontrolled_runtime_surface",
            "runtime_enabled": False,
            "requires_explicit_user_approval": True,
            "reason": "uncontrolled_runtime_capability_not_exposed",
            "params": "api_key=secret-token account_id=user-123",
        },
    ],
}
```

Assert visible Runtime panel content includes:

```python
expect(content).to_contain_text("Future Capability Policy")
expect(content).to_contain_text("future_capability_admission")
expect(content).to_contain_text("design_required")
expect(content).to_contain_text("runtime_enablement_allowed=false")
expect(content).to_contain_text("requires_new_stage_design")
expect(content).to_contain_text("blocked_uncontrolled_runtime")
```

Add forbidden rendered text:

```python
"raw_plan", "private_network_url", "127.0.0.1", "user-123", "account_id"
```

- [x] **Step 3: Extend Web API safety contract**

In `test_runtime_status_includes_read_only_safety_policy`, assert:

```python
self.assertIn("future_capability_admission", caps)
self.assertEqual(caps["future_capability_admission"]["default"], "design_required")
self.assertFalse(caps["future_capability_admission"]["enabled"])
future_policy = policy["future_capability_policy"]
self.assertEqual(future_policy["default_mode"], "design_required_before_runtime")
self.assertFalse(future_policy["runtime_enablement_allowed"])
self.assertFalse(future_policy["automatic_enable_enabled"])
self.assertGreaterEqual(future_policy["decision_counts"]["requires_new_stage_design"], 1)
self.assertGreaterEqual(future_policy["decision_counts"]["blocked_uncontrolled_runtime"], 1)
```

- [x] **Step 4: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step49-red-static -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step49-red-api -p no:cacheprovider
```

Expected: static test fails because Future Capability render functions and strings are missing. Web API may pass if Step 48 already exposed the backend contract; ordinary sandbox may fail on SQLite WAL and should be rerun in writable environment only when needed.

Observed: static test failed because `renderRuntimeFutureCapabilityPolicy` was missing. Web API ordinary sandbox failed on SQLite WAL database open.

- [x] **Step 5: Implement Runtime panel rendering**

In `renderRuntimeStatusPanel(data)`:

```javascript
const futureCapabilityPolicy = safetyPolicy && safetyPolicy.future_capability_policy ? safetyPolicy.future_capability_policy : {};
...
${renderRuntimeSummaryCard('Future Capability Policy', [`mode=${futureCapabilityPolicy.default_mode || '-'}`, `runtime=${Boolean(futureCapabilityPolicy.runtime_enablement_allowed)}`, `blocked=${policyDecisionCount(futureCapabilityPolicy, 'blocked_uncontrolled_runtime')}`])}
...
<h3 class="runtime-section-title">Future Capability Policy</h3>
${renderRuntimeFutureCapabilityPolicy(futureCapabilityPolicy)}
```

Add:

```javascript
function renderRuntimeFutureCapabilityPolicy(policy) {
    if (!policy || !policy.default_mode) return renderRuntimeEmpty('No future capability policy snapshot');
    const details = [
        `default=${formatRuntimeSafeText(policy.default_mode || '-')}`,
        `runtime_enablement_allowed=${Boolean(policy.runtime_enablement_allowed)}`,
        `automatic_enable=${Boolean(policy.automatic_enable_enabled)}`,
        `design_review=${Boolean(policy.design_review_required)}`,
        `human_confirmation=${Boolean(policy.human_confirmation_required_before_runtime)}`,
        `decisions=${formatRuntimeDistribution(policy.decision_counts || {})}`,
    ];
    const matrix = Array.isArray(policy.capability_matrix) ? policy.capability_matrix.slice(0, 8) : [];
    return `<div class="trading-memory-list">
        ${renderRuntimePolicySummary('Future Capability Policy', details)}
        ${matrix.length ? matrix.map(item => renderRuntimeFutureCapabilityPolicyItem(item || {})).join('') : renderRuntimeEmpty('No future capability matrix')}
    </div>`;
}

function renderRuntimeFutureCapabilityPolicyItem(item) {
    const decision = formatRuntimeSafeText(item.decision || '-');
    const badgeClass = String(decision).startsWith('blocked') ? 'badge-red' : decision === 'requires_new_stage_design' || decision === 'frozen_by_current_user_instruction' ? 'badge-gold' : 'badge-green';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(formatRuntimeSafeText(item.capability || '-'))}</div>
                <div class="trading-memory-meta">trust=${escapeHtml(formatRuntimeSafeText(item.trust_boundary || '-'))} | runtime_enabled=${escapeHtml(Boolean(item.runtime_enabled))} | approval=${escapeHtml(Boolean(item.requires_explicit_user_approval))} | reason=${escapeHtml(formatRuntimeSafeText(item.reason || '-'))}</div>
            </div>
            <span class="badge ${badgeClass}">${escapeHtml(decision)}</span>
        </div>
    </div></div>`;
}
```

Extend sensitive filters with:

```javascript
credential|user[_-]?id|private[_-]?network|local[_-]?path
raw_plan|raw_config|credential|webhook_secret|connector_token|private_network_url|local_path|user_id
```

- [x] **Step 6: Run green target tests**

Run:

```powershell
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step49-static -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step49-api -p no:cacheprovider
```

Expected: node syntax passes; static contract passes; Web API passes in writable environment if ordinary sandbox is blocked by SQLite WAL.

Observed: `node --check` exited 0; static contract `1 passed`; Web API writable rerun `1 passed, 71 deselected`.

- [x] **Step 7: Run full Runtime browser target test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-step49-playwright -p no:cacheprovider
```

Expected: in ordinary sandbox this may fail because the local server does not become ready. If it fails for that known environment reason, rerun in writable environment.

Observed: ordinary sandbox failed with `RuntimeError: Web server did not become ready`; writable environment rerun `1 passed`.

- [x] **Step 8: Update documentation**

Document Step 49 in:
- `githubProduct/personal_agent_warframe_migration_step49_future_capability_runtime_visibility_zh.md`
- `githubProduct/personal_agent_learning_route_ledger_zh.md`
- `md/rebuilt/06-tools-models-safety.md`
- `md/rebuilt/09-personal-agent-foundation.md`
- `md/rebuilt/10-learning-route-audit.md`
- `AGENTS.md`

Required wording:
- Step 49 is Step 48 Runtime visibility completion, not old learning queue debt.
- `future_capability_admission.enabled=False` remains unchanged.
- No Browser/GUI executor, shell, file write, service recovery, trigger platform, plugin install, connector, webhook, DM command, backend worker, or real voice runtime is enabled.
- Real voice, TTS/STT, microphone, recording, Live2D, and background listening remain frozen.

- [x] **Step 9: Final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step49-policy -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step49-static-final -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/future_capability_policy.py','warframe_agent/safety_policy.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
git diff --check -- warframe_agent\web\static\js\app.js tests\test_web_ui_playwright.py tests\test_web_api.py docs\superpowers\plans\2026-05-31-future-capability-runtime-visibility.md githubProduct\personal_agent_warframe_migration_step49_future_capability_runtime_visibility_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\06-tools-models-safety.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

Expected: policy tests pass, static Runtime contract passes, AST OK, JS syntax OK, diff check exits 0. LF/CRLF warnings are acceptable.

Observed: policy tests `20 passed, 33 deselected`; Runtime static contract `1 passed`; AST OK; `node --check` exited 0; `git diff --check` exited 0 with LF/CRLF warnings only.

## Self-Review

- Spec coverage: covers the requested next-step planning and execution after Step 48, with a concrete improvement that completes Runtime visibility for the safety admission layer.
- Placeholder scan: no TBD/TODO/fill-later items remain.
- Type consistency: frontend uses existing `policyDecisionCount`, `formatRuntimeDistribution`, `formatRuntimeSafeText`, `renderRuntimePolicySummary`, and `renderRuntimeEmpty` helpers.
- Safety boundary: this plan is visibility-only and does not enable high-risk capabilities, external connectors, shell/file writes, webhook/DM command entrypoints, or real voice.
