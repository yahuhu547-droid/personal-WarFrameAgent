# Step55 Playwright And Full Regression Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Step55 verification debt by proving the two patched frontend Playwright regressions and the full `pytest tests` suite status with fresh evidence.

**Architecture:** Treat this as a verification-first project quality task, not a restart of the old personal-Agent learning queue. Reproduce the two UI regressions first, expose server startup evidence if the fixture fails before browser assertions, then make the smallest code or fixture fix only when root-cause evidence points to it. After target green, run static checks and full pytest, then synchronize `AGENTS.md` and `md/rebuilt` with exact results.

**Tech Stack:** Python `pytest`, FastAPI / `uvicorn`, Playwright Python sync API, browser JavaScript (`chat.js`, `chart.js`), Markdown documentation.

---

### Task 1: Baseline And Progress Ledger

**Files:**
- Modify: `AGENTS.md`
- Create: `docs/superpowers/plans/2026-06-01-step55-playwright-full-regression-closure.md`

- [x] **Step 1: Confirm current Step55 debt**

Run:

```powershell
rg -n "Step 55|Step55|Playwright|全量 pytest|全量回归" AGENTS.md docs githubProduct md -S
```

Expected: Step55 is still marked as needing two frontend Playwright target tests plus full `pytest tests` rerun. Step57 must remain complete and must not change Step55 status.

- [x] **Step 2: Inspect target test entry points**

Run:

```powershell
rg -n "test_chat_websocket_error_stops_loading_and_renders_message|test_chat_response_whisper_compare_and_chart_are_xss_safe|web_server|APP_URL|uvicorn" tests\test_web_ui_playwright.py
rg -n "stripUnsafeInlineHtml|renderMarkdown|getChatErrorMessage|renderCurrentStreamError|chatWsState|waitForChatWsOpen|handleSend" warframe_agent\web\static\js\chat.js
```

Expected: `web_server()` starts `uvicorn` on `127.0.0.1:8000`; target UI assertions cover WebSocket error handling and XSS-safe chat / whisper / compare / chart rendering.

- [x] **Step 3: Record Step58 start in `AGENTS.md`**

Append a dated section that marks this task as `10% / 进行中`, states the completion criteria, and preserves the boundary that no new high-privilege runtime, external connector, dependency download, or GitHub upload is part of this work.

### Task 2: Target Playwright Reproduction

**Files:**
- Read: `tests/test_web_ui_playwright.py`
- Read: `warframe_agent/web/static/js/chat.js`
- Read: `warframe_agent/web/static/js/chart.js`

- [x] **Step 1: Run the two target Playwright tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message tests\test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe -q --basetemp .pytest-tmp-step58-ui-targets -p no:cacheprovider
```

Expected if Step55 patches are valid and the environment is available: `2 passed`.

Expected if the known sandbox issue remains: setup fails with `RuntimeError: Web server did not become ready`. In that case, do not claim UI failure or success; proceed to server diagnostics.

Result: ordinary sandbox failed at setup with `RuntimeError: Web server did not become ready`; writable environment entered browser assertions and produced `1 passed, 1 failed`, with the remaining failure in chat XSS-safe DOM storage.

- [x] **Step 2: If setup fails, expose server startup evidence**

Run a direct server startup smoke test, keeping output visible:

```powershell
.\.venv\Scripts\python.exe -m uvicorn warframe_agent.web.app:app --host 127.0.0.1 --port 8000 --log-level info
```

Expected: either the server starts and listens, or stderr identifies the root cause such as port collision, SQLite WAL permission, import failure, or missing browser/runtime dependency.

Result: direct `uvicorn` startup in ordinary sandbox failed while importing `warframe_agent.web.app`, at `TradeHistoryDB()` -> `PRAGMA journal_mode=WAL`, with `sqlite3.OperationalError: unable to open database file`.

- [x] **Step 3: If target assertions fail, classify the failing layer**

Read the pytest failure and classify exactly one of these layers before editing:

```text
websocket_error_path: chat.js WebSocket readyState/error/loading behavior
chat_xss_path: chat.js markdown sanitizer or whisper extraction behavior
compare_chart_xss_path: chart.js compare/detail/chart safe DOM rendering
fixture_timing_path: test fixture wait condition or server startup visibility
environment_path: sandbox, port, database, browser, or quota restriction
```

Expected: one layer has direct failure evidence. Do not edit unrelated backend, Step57 activity/Baro logic, ToolRouter, or safety policy files unless the traceback explicitly points there.

Result: classified as `chat_xss_path`. The visible message content was sanitized, but `data-raw` on the message DOM still stored the raw escaped `<img ... data-xss=...>` payload.

### Task 3: Minimal Fix Or Environment Closure

**Files:**
- Modify only if evidence requires it: `tests/test_web_ui_playwright.py`
- Modify only if evidence requires it: `warframe_agent/web/static/js/chat.js`
- Modify only if evidence requires it: `warframe_agent/web/static/js/chart.js`

- [x] **Step 1: For fixture startup evidence, improve diagnostics instead of product behavior**

If the only root cause is hidden `uvicorn` stderr or fixed port collision, apply the smallest test fixture improvement:

```python
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "warframe_agent.web.app:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    errors="replace",
)
```

When readiness times out, read bounded stderr/stdout and include it in the raised `RuntimeError`. Expected result: future setup failures explain the startup cause instead of hiding it.

Result: no fixture patch was needed for closure because direct uvicorn diagnostics identified the ordinary sandbox WAL limitation, and writable environment successfully started the server.

- [x] **Step 2: For WebSocket behavior, fix only `chat.js` send/error/loading state**

If the failure shows REST fallback or loading residue during the mocked WebSocket path, adjust only the current helpers around `waitForChatWsOpen(...)`, `isChatWsOpen(...)`, `renderCurrentStreamError(...)`, and `handleSend()`.

Expected user-visible behavior: a backend WebSocket error renders the backend message, removes `.loading`, and a second send still works.

Result: no additional WebSocket code change was needed in Step58; the Step55 WebSocket patch passed in the target Playwright run.

- [x] **Step 3: For chat XSS behavior, fix only `chat.js` safe rendering**

If the failure shows raw `data-xss`, event attributes, or injected `<img>` in the chat message DOM, adjust only `stripUnsafeInlineHtml(...)`, `renderMarkdown(...)`, or whisper command extraction.

Expected user-visible behavior: safe text remains visible, whisper copy still copies `WHISPER_TEXT`, and no executable payload or `data-xss` attribute reaches DOM.

Result: added `safeChatRawText(...)` and stored sanitized agent `data-raw` values so stripped inline HTML does not remain in DOM attributes while whisper detection and history persistence keep working.

- [x] **Step 4: For compare/chart XSS behavior, fix only `chart.js` DOM rendering**

If the failure shows compare suggestions, legends, or item detail cards render unsafe HTML, replace the specific `innerHTML` path with safe DOM creation or `textContent` in the smallest affected function.

Expected user-visible behavior: compare and chart details still show the mocked item names and legends, while injected image payloads remain inert text or are removed.

Result: no `chart.js` code change was needed; compare/chart assertions passed after the chat `data-raw` fix.

### Task 4: Verification And Documentation Sync

**Files:**
- Modify: `AGENTS.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Create or modify: `githubProduct/personal_agent_warframe_migration_step58_step55_playwright_full_regression_closure_zh.md`

- [x] **Step 1: Run JavaScript syntax checks**

Run:

```powershell
node --check warframe_agent\web\static\js\chat.js
node --check warframe_agent\web\static\js\chart.js
```

Expected: both commands exit 0.

Result: both commands exited 0.

- [x] **Step 2: Re-run the two target Playwright tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message tests\test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe -q --basetemp .pytest-tmp-step58-ui-targets-final -p no:cacheprovider
```

Expected: `2 passed`. If the environment still blocks server startup, record the exact startup evidence and keep Step55 verification debt open.

Result: writable environment rerun produced `2 passed in 28.70s`.

- [x] **Step 3: Run full project pytest**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp-step58-full-final -p no:cacheprovider
```

Expected if all Step55 debt is closed: full suite exits 0. If failures remain, record exact failed test names and decide whether they are Step55 regressions or separate project quality debt.

Result: writable environment full suite produced `1182 passed, 7 warnings in 331.32s`.

- [x] **Step 4: Run Python AST and diff checks**

Run:

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/baro.py','warframe_agent/events.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
git diff --check -- AGENTS.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md githubProduct\personal_agent_warframe_migration_step58_step55_playwright_full_regression_closure_zh.md docs\superpowers\plans\2026-06-01-step55-playwright-full-regression-closure.md tests\test_web_ui_playwright.py warframe_agent\web\static\js\chat.js warframe_agent\web\static\js\chart.js
```

Expected: `AST OK`; `git diff --check` exits 0 except acceptable LF/CRLF warnings.

Result: AST check returned `AST OK`; `git diff --check` exited 0 with LF/CRLF warnings for existing working-copy files.

- [x] **Step 5: Synchronize final status**

Update `AGENTS.md`, `md/rebuilt/09-personal-agent-foundation.md`, `md/rebuilt/10-learning-route-audit.md`, and the Step58 report with exact command results.

Expected if verification passes: Step58 is `100% / 已完成`, and Step55 remaining Playwright / full pytest debt is recorded as closed.

Expected if verification is blocked: Step58 remains `待评估`, with the exact blocking error, and no completion claim is made.

Result: Step58 final report, `AGENTS.md`, and `md/rebuilt` were synchronized with the passing target Playwright and full pytest evidence.

---

## Completion Criteria

- The two Step55 UI target tests have fresh results.
- Full `pytest tests` has fresh results.
- Any remaining failures are named explicitly and are not hidden behind generic wording.
- `AGENTS.md` and `md/rebuilt` are synchronized.
- No dependency is installed outside the project, no file is downloaded to C:, no GitHub upload is performed, and no new high-privilege runtime capability is enabled.
