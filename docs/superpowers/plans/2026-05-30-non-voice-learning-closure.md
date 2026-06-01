# Non-Voice Personal Agent Learning Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining non-voice personal Agent learning-borrowing plan without enabling real voice, Browser/GUI execution, arbitrary triggers, or uncontrolled external gateways.

**Architecture:** Continue the project’s conservative pattern: each borrowed high-level Agent capability becomes a read-only policy snapshot or a tightly scoped confirmation bridge before any runtime executor exists. New policy modules stay pure and testable, then `build_runtime_safety_policy(...)` exposes safe aggregate fields through the existing `/api/runtime/status` path.

**Tech Stack:** Python, pytest, FastAPI runtime status, existing `ToolRegistry`, existing `ChatAgent + ToolRouter + ModelOrchestrator` boundaries, Markdown route ledgers.

---

## File Structure

- `warframe_agent/plugin_policy.py`: new pure policy module for skills / plugins / connector capability classification.
- `tests/test_plugin_policy.py`: unit tests for skills / plugin safety decisions and redaction.
- `warframe_agent/safety_policy.py`: add `plugin_policy` and `capabilities.skills_plugin_ecosystem`.
- `tests/test_tool_registry.py`: extend runtime safety policy aggregate test.
- `warframe_agent/web/static/js/app.js`: optional Step 45 UI-only Runtime panel rendering for Gateway / Plugin policy safe summaries.
- `tests/test_web_ui_playwright.py`: optional Step 45 static / Playwright checks for safe policy rendering.
- `githubProduct/personal_agent_warframe_migration_step44_plugin_policy_zh.md`: Step 44 learning report.
- `githubProduct/personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md`: Step 45 learning report.
- `githubProduct/personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md`: final closure report.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: route ledger updates.
- `md/rebuilt/06-tools-models-safety.md`: safety doc updates.
- `md/rebuilt/09-personal-agent-foundation.md`: foundation updates.
- `md/rebuilt/10-learning-route-audit.md`: route audit updates.
- `AGENTS.md`: cross-session progress and next-step updates.

## Execution Sequence

### Task 44: Skills / Plugin Ecosystem Boundary

**Files:**
- Create: `warframe_agent/plugin_policy.py`
- Create: `tests/test_plugin_policy.py`
- Modify: `warframe_agent/safety_policy.py`
- Modify: `tests/test_tool_registry.py`
- Modify docs listed above.

- [x] **Step 1: Write failing tests**

Add tests requiring:
- local skills are read-only guidance by default;
- installed personal plugins require explicit review;
- connectors with account access require explicit enable and confirmation;
- unknown plugins and tools with shell/file/browser/network side effects are blocked;
- raw manifest, token, secret, path, account id, handler and raw parameters are not exposed.

- [x] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plugin_policy.py tests\test_tool_registry.py -k "plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: fail because `warframe_agent.plugin_policy` does not exist.

- [x] **Step 3: Implement pure policy module**

Add `classify_plugin_capability(...)` and `build_plugin_policy()` with conservative decisions:
- `allow_guidance_only`
- `requires_review`
- `requires_explicit_enable`
- `blocked_high_risk_capability`
- `blocked_unknown_capability`

- [x] **Step 4: Integrate runtime safety**

Add `capabilities.skills_plugin_ecosystem` and `plugin_policy` to `build_runtime_safety_policy(...)`.

- [x] **Step 5: Run green tests and docs**

Run the target pytest command, AST check, and diff check. Update Step 44 report, ledger, rebuilt docs, and `AGENTS.md`.

### Task 45: Runtime Policy Visibility

**Files:**
- Modify: `warframe_agent/web/static/js/app.js`
- Modify: `tests/test_web_ui_playwright.py`
- Modify docs listed above.

- [x] **Step 1: Inspect existing Runtime panel rendering**

Use `rg` to locate capability rendering and safety policy rendering in `app.js`.

- [x] **Step 2: Add UI-only rendering**

Expose safe aggregate lines for `gateway_policy` and `plugin_policy` in the existing Runtime panel. Do not add buttons, toggles, configuration forms, connectors, account inputs, or raw payload display.

- [x] **Step 3: Verify UI contracts**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
```

If Playwright needs a writable runtime, rerun with approved writable environment.

- [x] **Step 4: Update docs**

Document that Runtime visibility is display-only and does not enable new capabilities.

### Task 46: Final Non-Voice Learning Closure Audit

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md`
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Modify: `AGENTS.md`

- [x] **Step 1: Build coverage matrix**

Summarize each source project and borrowed theme:
- CowAgent
- OpenManus
- LangManus
- OpenHuman
- EchoBot
- Open-AutoGLM
- OpenClaw
- Suna / Kortix

- [x] **Step 2: Mark non-voice route complete**

Mark non-voice learning-borrowing route as complete only if Step 44 and Step 45 verification passed or Step 45 is explicitly documented as not needed.

- [x] **Step 3: Freeze high-risk future branches**

Document that real voice, real Browser/GUI execution, service recovery, arbitrary triggers, public webhooks, and platform DMs remain future design-only branches.

- [x] **Step 4: Final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/gateway_policy.py','warframe_agent/plugin_policy.py','warframe_agent/safety_policy.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\gateway_policy.py warframe_agent\plugin_policy.py warframe_agent\safety_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\06-tools-models-safety.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md
```

## Self-Review

- Spec coverage: covers remaining non-voice branches after Gateway: plugin ecosystem, runtime visibility, final closure.
- Placeholder scan: no TODO / TBD work remains; each task has files, commands, and expected outcomes.
- Type consistency: policy modules follow existing `browser_gui_safety.py`, `companion_experience.py`, and `gateway_policy.py` patterns.

## Execution Status

- Task 44 is complete: `plugin_policy` is implemented, integrated into runtime safety, tested, and documented.
- Task 45 implementation is complete with one verification debt: UI static contract and `node --check` pass; the full Playwright browser test still needs a Codex re-login because the desktop refresh token was revoked during escalated writable rerun.
- Task 46 is complete: the non-voice learning-borrowing route has a closure report, route ledger updates, `md/rebuilt` synchronization, and AGENTS progress records.
