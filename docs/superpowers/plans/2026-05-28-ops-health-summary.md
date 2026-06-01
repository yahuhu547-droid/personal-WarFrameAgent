# Ops Health Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Step 36 from the personal-agent learning route: add a read-only operations health summary to the existing runtime status panel.

**Architecture:** Keep the current FastAPI `/api/runtime/status` endpoint as the single runtime observation surface. Add a small deterministic `_ops_health_snapshot(...)` helper in `warframe_agent/web/app.py` that consumes already-safe scheduler, background task, Feishu, WxPusher, and daily report snapshots, then expose only aggregate counts and short reason codes. Render the summary in the existing runtime panel without adding any start/stop/retry controls.

**Tech Stack:** Python helper functions, FastAPI JSON response, existing static JavaScript runtime panel, pytest, Playwright static/runtime tests, Markdown docs.

---

## Route Assignment

来源项目：CowAgent / Suna / OpenClaw。

借鉴点：service health, scheduler health, trigger visibility, recovery reason summaries, long-running workspace observability.

Warframe 映射：`/api/runtime/status` gains an `ops_health` summary; Web runtime panel displays it as a read-only operations overview.

安全边界：no new scheduler control endpoint, no retry/start/stop button, no shell, no Browser/GUI automation, no direct cloud model calls, no secret/profile/raw result exposure.

验证方式：Web API unit tests for safe `ops_health`, runtime panel test for rendering, AST / JS syntax / diff checks.

---

## Files

- Modify: `F:\giteeProject\warframe\warframe_agent\web\app.py`
- Modify: `F:\giteeProject\warframe\warframe_agent\web\static\js\app.js`
- Modify: `F:\giteeProject\warframe\tests\test_web_api.py`
- Modify: `F:\giteeProject\warframe\tests\test_web_ui_playwright.py`
- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_warframe_migration_step36_ops_health_summary_zh.md`
- Modify: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\09-personal-agent-foundation.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`
- Modify: `F:\giteeProject\warframe\AGENTS.md`

Do not edit external reference repos. Do not add package dependencies.

---

### Task 1: Red Tests For Ops Health API

**Files:**
- Modify: `F:\giteeProject\warframe\tests\test_web_api.py`

- [ ] **Step 1: Add a runtime status test for degraded ops health**

Add a test that mocks:

```python
mock_monitor.scheduler_status_snapshot.return_value = {
    "running": False,
    "has_scheduler": True,
    "total": 2,
    "jobs": [
        {"job_id": "scan", "running": False, "last_success": True, "error_count": 0, "last_error_summary": None},
        {"job_id": "daily_report", "running": False, "last_success": False, "error_count": 2, "last_error_summary": "token=secret Bearer abc"},
    ],
}
mock_feishu.status_snapshot.return_value = {"enabled": True, "configured": True, "available": True, "managed_running": False, "app_secret": "LEAK"}
```

Temporarily insert one `_bg_tasks` error with a sensitive error string.

Assert:

- `data["ops_health"]["status"] == "degraded"`
- component summaries include scheduler, background_tasks, feishu, wxpusher, daily_report
- reason codes include `scheduler_stopped`, `scheduler_job_failed`, `background_task_error`, `feishu_not_running`
- serialized response does not include `LEAK`, `secret`, `Bearer`, `app_secret`, raw result keys, or task result contents

- [ ] **Step 2: Run the focused red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "ops_health" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected before implementation: fails because `ops_health` is missing.

### Task 2: Implement Safe Ops Health Snapshot

**Files:**
- Modify: `F:\giteeProject\warframe\warframe_agent\web\app.py`

- [ ] **Step 1: Add `_ops_health_snapshot(...)`**

Implement a pure helper near runtime snapshot helpers:

```python
def _ops_health_snapshot(
    *,
    scheduler_snapshot: dict[str, Any],
    background_tasks_snapshot: dict[str, Any],
    feishu_snapshot: dict[str, Any],
    wxpusher_snapshot: dict[str, Any],
    daily_report_snapshot: dict[str, Any],
) -> dict[str, Any]:
    ...
```

The helper returns:

```python
{
    "status": "ok" | "degraded",
    "reason_count": int,
    "reasons": ["scheduler_stopped", ...],
    "components": {
        "scheduler": {"status": "...", "running": bool, "job_count": int, "failed_job_count": int, "running_job_count": int},
        "background_tasks": {"status": "...", "running": int, "error": int, "total": int},
        "feishu": {"status": "...", "enabled": bool, "configured": bool, "running": bool},
        "wxpusher": {"status": "...", "enabled": bool, "configured": bool, "available": bool},
        "daily_report": {"status": "...", "enabled": bool, "should_send_now": bool},
    },
}
```

Do not include job names, error summaries, task IDs, raw results, profile URLs, `/w`, token, or provider secrets.

- [ ] **Step 2: Include it in `/api/runtime/status`**

Build `ops_health_snapshot` after all component snapshots are available and return it as `ops_health`.

- [ ] **Step 3: Run API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "ops_health or runtime_status_endpoint" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: pass in a writable Web app environment. If ordinary sandbox hits SQLite WAL import failure, rerun with approved escalation and record that.

### Task 3: Runtime Panel Display

**Files:**
- Modify: `F:\giteeProject\warframe\warframe_agent\web\static\js\app.js`
- Modify: `F:\giteeProject\warframe\tests\test_web_ui_playwright.py`

- [ ] **Step 1: Update Playwright mock payload**

Add `ops_health` to the runtime mock payload with:

```json
{
  "status": "degraded",
  "reason_count": 3,
  "reasons": ["scheduler_job_failed", "background_task_error", "feishu_not_running"],
  "components": {
    "scheduler": {"status": "degraded", "running": true, "job_count": 2, "failed_job_count": 1, "running_job_count": 0},
    "background_tasks": {"status": "degraded", "running": 1, "error": 1, "total": 2},
    "feishu": {"status": "ok", "enabled": true, "configured": true, "running": true},
    "wxpusher": {"status": "ok", "enabled": true, "configured": true, "available": true},
    "daily_report": {"status": "ok", "enabled": true, "should_send_now": false}
  }
}
```

Assert the runtime panel contains `Ops Health`, `ops_status=degraded`, `reason_count=3`, `scheduler_job_failed`, and `background_task_error`, while still hiding raw secrets.

- [ ] **Step 2: Render ops health**

In `renderRuntimeStatusPanel(data)`, read `data.ops_health` and add:

- a summary card: `Ops Health`
- a read-only section rendered by `renderRuntimeOpsHealth(opsHealth)`
- component cards from `renderRuntimeOpsComponent(name, component)`

Render only allowed fields and use `escapeHtml`.

- [ ] **Step 3: Run runtime panel tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: pass in a writable Web app environment; static contract should pass in ordinary sandbox.

### Task 4: Documentation Sync

**Files:**
- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_warframe_migration_step36_ops_health_summary_zh.md`
- Modify: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\09-personal-agent-foundation.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`
- Modify: `F:\giteeProject\warframe\AGENTS.md`

- [ ] **Step 1: Write Step 36 learning record**

Document:

- source projects: CowAgent / Suna / OpenClaw
- borrowed ideas: service health, scheduler trigger visibility, recovery reason summary
- Warframe mapping: `ops_health`
- safety boundary: read-only, no controls
- verification commands and results

- [ ] **Step 2: Update route documents**

Append Step 36 to the route ledger and `md/rebuilt` files. Update `AGENTS.md` progress table from 35 to 36.

### Task 5: Final Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "ops_health or runtime_status_endpoint" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
git diff --check -- warframe_agent/web/app.py warframe_agent/web/static/js/app.js tests/test_web_api.py tests/test_web_ui_playwright.py githubProduct/personal_agent_warframe_migration_step36_ops_health_summary_zh.md githubProduct/personal_agent_learning_route_ledger_zh.md md/rebuilt/09-personal-agent-foundation.md md/rebuilt/10-learning-route-audit.md AGENTS.md docs/superpowers/plans/2026-05-28-ops-health-summary.md
```

---

## Completion Criteria

- `/api/runtime/status` includes a safe `ops_health` aggregate.
- Runtime panel displays the aggregate without controls.
- No secrets, raw results, profile URLs, `/w`, token, or provider credentials appear in `ops_health`.
- No new package dependencies, cloud calls, scheduler control actions, or external repo edits.
- `md/rebuilt` and `AGENTS.md` are synced.
