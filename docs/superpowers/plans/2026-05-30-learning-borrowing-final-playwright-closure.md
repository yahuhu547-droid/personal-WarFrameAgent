# Learning Borrowing Final Playwright Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Step 45 Playwright verification debt so the non-voice GitHub personal Agent learning-borrowing route can be marked complete without adding new runtime capabilities.

**Architecture:** This is a verification-and-documentation closure. The Runtime panel code is already implemented; this plan only reruns the full browser test and updates Markdown status records according to evidence.

**Tech Stack:** Python, pytest, Playwright, Node.js syntax check, Markdown route ledger, `AGENTS.md`.

---

## File Structure

- `tests/test_web_ui_playwright.py`: existing full browser target test for Runtime policy visibility.
- `warframe_agent/web/static/js/app.js`: existing Runtime panel implementation, syntax-checked only.
- `docs/superpowers/plans/2026-05-30-learning-borrowing-final-playwright-closure.md`: this execution plan.
- `AGENTS.md`: cross-session progress and final verification status.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: route ledger status.
- `githubProduct/personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md`: Step 45 report status.
- `githubProduct/personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md`: final closure report status.
- `md/rebuilt/09-personal-agent-foundation.md`: rebuilt foundation summary.
- `md/rebuilt/10-learning-route-audit.md`: rebuilt route audit summary.

## Execution Sequence

### Task 47: Step 45 Full Playwright Verification Closure

**Files:**
- Test: `tests/test_web_ui_playwright.py`
- Inspect: `warframe_agent/web/static/js/app.js`
- Modify on pass or blocked result: docs listed above.

- [x] **Step 1: Confirm the remaining debt**

Run:

```powershell
rg -n "Step 45|Playwright|唯一保留债务|待评估|90%" AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md githubProduct\personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md githubProduct\personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md
```

Expected: the only active non-voice learning-borrowing debt is `tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state`.

- [x] **Step 2: Run the full browser target test in the current project environment**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-final-playwright -p no:cacheprovider
```

Expected if environment is ready: `1 passed`.

If this fails because uvicorn cannot become ready, SQLite WAL cannot be opened, or Codex desktop writable escalation is unavailable, record the exact failure and do not mark Step 45 as complete.

- [x] **Step 3: If Step 2 passes, mark the route complete**

Update these records:
- `AGENTS.md`: change Step 45 from `90% / 待评估` to `100% / 已完成`; add Step 47 closure row.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: add Step 47 note that Step 45 full Playwright verification passed.
- `githubProduct/personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md`: replace the pending Playwright note with the fresh pass result.
- `githubProduct/personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md`: remove "唯一保留债务" wording and state the non-voice route is fully verified.
- `md/rebuilt/09-personal-agent-foundation.md`: update Step 45 / Step 46 verification wording.
- `md/rebuilt/10-learning-route-audit.md`: update Step 45 / Step 46 verification wording.

- [x] **Step 4: If Step 2 is blocked by environment, mark the route blocked-by-environment**

Update these records:
- `AGENTS.md`: add Step 47 row as `90% / 待评估` or `阻塞待用户处理`, keeping Step 45 at `90% / 待评估`.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: add the exact failed command and failure reason.
- `md/rebuilt/10-learning-route-audit.md`: keep the route code/docs closed but not fully browser-verified.
- Do not change Step 45 to `100%`.

- [x] **Step 5: Final verification after any documentation update**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-final-policy -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-final-static -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/gateway_policy.py','warframe_agent/plugin_policy.py','warframe_agent/safety_policy.py','warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
git diff --check -- warframe_agent\gateway_policy.py warframe_agent\plugin_policy.py warframe_agent\safety_policy.py warframe_agent\web\static\js\app.js warframe_agent\chat.py warframe_agent\tool_router.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py tests\test_web_api.py tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-30-learning-borrowing-final-playwright-closure.md githubProduct\personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md githubProduct\personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

Expected: policy tests pass, static Runtime contract passes, AST OK, Node syntax check exits 0, diff check exits 0. LF/CRLF warnings are acceptable.

## Self-Review

- Spec coverage: this plan addresses the only remaining non-voice learning-borrowing debt named in Step 46.
- Placeholder scan: no open-ended implementation steps are left; each branch has concrete file updates and commands.
- Safety boundary: this plan does not enable voice, Browser/GUI execution, connectors, webhooks, shell, scheduler control, or plugin installation.

## Execution Status

- Ordinary sandbox run reproduced the old environment issue: `RuntimeError: Web server did not become ready`.
- Writable runtime rerun passed: `tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state` -> `1 passed`.
- Documentation was updated through the pass branch.
- Final verification after documentation updates passed: policy tests `12 passed, 33 deselected`; static Runtime contract `1 passed`; full Playwright browser target `1 passed`; AST OK; `node --check` exited 0; `git diff --check` exited 0 with LF/CRLF warnings only.
