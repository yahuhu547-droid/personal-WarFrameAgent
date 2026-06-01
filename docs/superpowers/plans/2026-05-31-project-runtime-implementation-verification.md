# Project Runtime Implementation Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the project and verify that the recent learning-borrowing implementations exist in code, API, Runtime UI, and tests.

**Architecture:** This is a verification-only pass. It runs broad pytest coverage, focused Step50-53 policy/runtime tests, JavaScript and AST checks, and a local FastAPI smoke test without enabling any high-privilege runtime capability.

**Tech Stack:** Python `.venv`, pytest, FastAPI / uvicorn, vanilla JavaScript Runtime panel, PowerShell, ripgrep.

---

## File Structure

- `docs/superpowers/plans/2026-05-31-project-runtime-implementation-verification.md`: this execution plan and result ledger.
- `githubProduct/personal_agent_warframe_migration_step54_project_runtime_verification_zh.md`: final verification report.
- `AGENTS.md`: append Step 54 progress and verification summary.
- `md/rebuilt/09-personal-agent-foundation.md`: append Step 54 implementation verification note.
- `md/rebuilt/10-learning-route-audit.md`: append Step 54 route verification note.

## Execution Sequence

### Task 54: Project Runtime And Implementation Verification

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step54_project_runtime_verification_zh.md`
- Modify: `AGENTS.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`

- [x] **Step 1: Confirm scope and dirty tree**

Run:

```powershell
git status --short
rg --files tests | Measure-Object | Select-Object -ExpandProperty Count
```

Expected: worktree may be dirty from existing project history; do not revert unrelated changes.

Result: worktree is very dirty from existing project history and generated files; no unrelated changes were reverted. `rg --files tests` reported `90`.

- [x] **Step 2: Run broad pytest suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp-step54-full -p no:cacheprovider
```

Expected: report the exact result. If failures are environment-specific or pre-existing, record them with the failing tests.

Result: ordinary sandbox collection failed on SQLite WAL / database file access. Writable run completed with `8 failed, 1162 passed, 7 warnings in 342.87s`; failures are recorded in `githubProduct/personal_agent_warframe_migration_step54_project_runtime_verification_zh.md`.

- [x] **Step 3: Run focused learning/runtime policy verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "learning_completion or future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step54-policy -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step54-static -p no:cacheprovider
```

Expected: the focused learning completion and runtime static contracts pass.

Result: focused policy run passed with `25 passed, 33 deselected`; Runtime static contract passed with `1 passed`.

- [x] **Step 4: Run syntax and import-safe checks**

Run:

```powershell
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=[str(path) for path in pathlib.Path('warframe_agent').rglob('*.py')] + [str(path) for path in pathlib.Path('tools').rglob('*.py')]; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print(f'AST OK {len(files)} files')"
```

Expected: JavaScript syntax and Python AST parsing pass.

Result: `node --check` exited 0. Strict `utf-8` AST parsing exposed a historical BOM issue; `utf-8-sig` AST parsing passed for `82` Python files. `compileall` was blocked by `tools\__pycache__` write permissions in the current environment.

- [x] **Step 5: Start local FastAPI server and smoke test runtime endpoint**

Run a temporary local uvicorn process on `127.0.0.1:8765`, request `/api/runtime/status`, verify:

- HTTP status is 200.
- JSON includes `learning_completion`.
- `learning_completion.status == "complete"`.
- `learning_completion.acceptance_status == "accepted"`.
- `safety_policy.capabilities.future_capability_admission.enabled == false`.

Expected: server starts and smoke endpoint returns the expected safe completion fields. Always stop the server process.

Result: writable smoke test returned `HTTP=200`, `learning_status=complete`, `acceptance_status=accepted`, and `future_enabled=False`; the temporary server was stopped and port `8765` was clear afterward.

- [x] **Step 6: Collect subagent findings**

Wait for backend/API and frontend/Runtime read-only subagents, then compare their results with main-thread verification.

Expected: subagent results do not contradict the main-thread evidence. Any conflict must be called out.

Result: backend/API and frontend/Runtime subagents both found that the learning implementations are real in code/API/UI. Their environment caveats matched the main-thread SQLite WAL and uvicorn readiness findings.

- [x] **Step 7: Write final report and sync rebuilt docs**

Write `githubProduct/personal_agent_warframe_migration_step54_project_runtime_verification_zh.md`, append Step 54 to `AGENTS.md`, `md/rebuilt/09-personal-agent-foundation.md`, and `md/rebuilt/10-learning-route-audit.md`.

Expected: docs record exact commands, results, any failures, and the final implementation-realness conclusion.

Result: Step 54 report and sync notes were written to the report, `AGENTS.md`, and `md/rebuilt` docs.

- [x] **Step 8: Run final documentation check**

Run:

```powershell
rg -n "Step 54|整体验收|启动烟测|实现真实|acceptance_status=accepted|future_capability_admission|8 failed" AGENTS.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md githubProduct\personal_agent_warframe_migration_step54_project_runtime_verification_zh.md docs\superpowers\plans\2026-05-31-project-runtime-implementation-verification.md
git diff --check -- AGENTS.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md docs\superpowers\plans\2026-05-31-project-runtime-implementation-verification.md githubProduct\personal_agent_warframe_migration_step54_project_runtime_verification_zh.md
```

Expected: key Step 54 wording is present and `git diff --check` exits 0.

Result: key Step 54 wording is present across `AGENTS.md`, `md/rebuilt`, the plan, and the report. `git diff --check` exited 0.

## Safety Boundary

- Do not install packages or download files.
- Do not upload to GitHub.
- Do not revert unrelated dirty worktree changes.
- Do not enable Browser/GUI executor, shell executor, service recovery, arbitrary trigger platform, plugin install, connector enablement, webhook/DM command entry, or real voice capability.
- Use project-local temporary paths such as `.pytest-tmp-step54-*`.
