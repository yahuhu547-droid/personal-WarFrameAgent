# Runtime Safety Policy Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only runtime safety policy snapshot that makes the current Agent capability boundaries visible without enabling new shell, file, browser, private-network, or scheduler powers.

**Architecture:** Keep the policy as deterministic local data in a small module, combine it with safe runtime snapshots for scheduler, Feishu, and WxPusher, and expose it through `/api/runtime/status`. The Web runtime panel renders the policy as status cards, and rebuilt docs record this as Step 7 of the personal Agent learning migration.

**Tech Stack:** Python pure functions, FastAPI runtime status, existing Web static JavaScript, pytest, `node --check`, AST syntax checks.

---

## File Structure

- Create `warframe_agent/safety_policy.py`
  - Build static capability defaults and dynamic runtime flags from safe snapshots.
- Modify `warframe_agent/web/app.py`
  - Include `safety_policy` in `/api/runtime/status`.
- Modify `warframe_agent/web/static/js/app.js`
  - Render a compact safety policy section in the runtime panel.
- Modify `tests/test_web_api.py`
  - Assert runtime status includes safe capability defaults and no secrets.
- Create `githubProduct/personal_agent_warframe_migration_step7_runtime_safety_policy_zh.md`
  - Record the learning point, implemented boundaries, and verification.
- Modify `md/rebuilt/*.md`
  - Synchronize feature, UI, API, safety, and testing docs. Do not commit or push.

---

### Task 1: Safety Policy Snapshot

**Files:**
- Create: `warframe_agent/safety_policy.py`
- Modify: `tests/test_web_api.py`

- [x] **Step 1: Write failing runtime status test**

Add a test that calls `/api/runtime/status` with mocked Feishu, scheduler, and WxPusher snapshots. Assert:

- `data["safety_policy"]["default_mode"] == "read_only"`
- `shell`, `generic_file_write`, `browser_private_network`, and `arbitrary_scheduler` are unavailable/disabled.
- `market_network`, `scheduler_jobs`, `external_push`, and `project_data_write` expose only safe booleans/modes.
- Serialized response does not contain app token, UID, chat id, app secret, or other sensitive values.

- [x] **Step 2: Implement pure builder**

Create `build_runtime_safety_policy(...)` returning:

```python
{
    "policy_version": "2026-05-26.personal-agent-safety-v1",
    "default_mode": "read_only",
    "capabilities": {
        "shell": {"available": False, "default": "disabled", "requires_explicit_enable": True},
        "generic_file_write": {"available": False, "default": "disabled", "requires_explicit_enable": True},
        "browser_private_network": {"available": False, "default": "disabled", "requires_explicit_enable": True},
        "arbitrary_scheduler": {"available": False, "default": "disabled", "requires_explicit_enable": True},
        "market_network": {"available": True, "default": "read_only", "requires_explicit_enable": False},
        "project_data_write": {"available": True, "default": "restricted", "requires_explicit_enable": False},
        "scheduler_jobs": {"available": True, "default": "restricted", "enabled": <bool>},
        "external_push": {"available": True, "default": "explicit_config", "enabled": <bool>},
    },
    "guardrails": [...]
}
```

No secrets or raw config values should enter this structure.

---

### Task 2: Runtime Status and Web UI

**Files:**
- Modify: `warframe_agent/web/app.py`
- Modify: `warframe_agent/web/static/js/app.js`

- [x] **Step 1: Wire into `/api/runtime/status`**

After collecting safe scheduler, Feishu, daily report, and WxPusher snapshots, call `build_runtime_safety_policy(...)` and add it to the response as `safety_policy`.

- [x] **Step 2: Render runtime panel**

Add one summary card for safety default mode and a `安全策略` section listing capability name, default mode, availability, and enabled state.

---

### Task 3: Documentation Sync

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step7_runtime_safety_policy_zh.md`
- Modify: `md/rebuilt/02-feature-scope.md`
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/04-web-api-reference.md`
- Modify: `md/rebuilt/06-tools-models-safety.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: Write learning note**

Record that Step 7 borrows the read-only-first safety policy idea from personal Agent projects but does not add general shell/file/browser/scheduler execution powers.

- [x] **Step 2: Update rebuilt docs**

Mention `safety_policy` under runtime status, Web UI runtime panel, API docs, and safety testing commands.

---

### Task 4: Verification

**Files:**
- No production edits.

- [x] **Step 1: Run targeted tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status" -q
```

If ordinary sandbox blocks Web app import at SQLite WAL, run the same target in the sandbox-external writable environment and record both outcomes.

Observed red-green cycle:

```text
pytest tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q
FAILED KeyError: 'safety_policy'
```

After implementation in the sandbox-external writable environment:

```text
pytest tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q
1 passed, 68 deselected

pytest tests/test_web_api.py -k "runtime_status" -q
5 passed, 64 deselected
```

Ordinary sandbox still blocks Web API pytest during app import:

```text
ERROR tests/test_web_api.py - sqlite3.OperationalError: unable to open database file
```

- [x] **Step 2: Run syntax checks**

```powershell
& .\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/safety_policy.py','warframe_agent/web/app.py','tests/test_web_api.py']; [ast.parse(pathlib.Path(f).read_text(encoding='utf-8-sig'), filename=f) for f in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
```

---

## Self-Review

- Spec coverage: Covers static defaults, dynamic safe flags, runtime API, Web UI, docs, and verification.
- Placeholder scan: No unresolved placeholders are present.
- Safety scope: This plan exposes current boundaries only; it does not add new execution capabilities or new credentials.
- GitHub constraint: No commit or push steps are included.
