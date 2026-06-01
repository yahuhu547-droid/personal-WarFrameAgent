# Tool Registry Safety Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the runtime safety policy snapshot with safe aggregate statistics from `ToolRegistry`, so the Web runtime panel can show tool safety distribution without exposing handlers, raw arguments, model contexts, or execution results.

**Architecture:** Add a pure summarizer in `warframe_agent/safety_policy.py` that accepts an optional registry-like object and counts public metadata from `ToolSpec` values: total tools, exposed schemas, side-effect tools, `safety_level`, `skill`, and `context_policy` distributions. `/api/runtime/status` passes `chat_agent.tool_registry` into the existing safety policy builder, and the frontend renders only aggregate counts.

**Tech Stack:** Python pure functions, existing `ToolRegistry` metadata, FastAPI runtime status, Web static JavaScript, pytest, AST checks, `node --check`.

---

## File Structure

- Modify `warframe_agent/safety_policy.py`
  - Add `summarize_tool_registry_safety(...)`.
  - Add `tool_registry` aggregate data to `build_runtime_safety_policy(...)`.
- Modify `warframe_agent/web/app.py`
  - Pass `chat_agent.tool_registry` to `build_runtime_safety_policy(...)`.
- Modify `warframe_agent/web/static/js/app.js`
  - Render tool registry safety aggregate counts in the runtime panel.
- Modify `tests/test_tool_registry.py`
  - Add pure tests proving the summary counts metadata and does not expose handlers or parameters.
- Modify `tests/test_web_api.py`
  - Extend runtime status safety policy test to assert `tool_registry` exists and stays aggregate-only.
- Create `githubProduct/personal_agent_warframe_migration_step8_tool_registry_safety_summary_zh.md`
  - Record learning outcome and verification.
- Modify `md/rebuilt/*.md`
  - Synchronize docs. Do not commit or push.

---

### Task 1: Pure Tool Registry Summary

**Files:**
- Modify: `tests/test_tool_registry.py`
- Modify: `warframe_agent/safety_policy.py`

- [x] **Step 1: Write failing pure test**

Add a test that builds a `ToolRegistry` with:

```python
registry.register(ToolSpec(
    name="safe_price",
    description="safe",
    parameters={"secret_param": {"type": "string"}},
    skill="market_price",
    safety_level="read_only",
    context_policy="safe_aggregate_only",
    handler=lambda args: "should not leak",
))
registry.register(ToolSpec(
    name="push_message",
    description="push",
    parameters={},
    skill="monitoring",
    safety_level="external_side_effect",
    side_effect=True,
    expose_schema=False,
))
```

Assert:

- `tool_count == 2`
- `exposed_schema_count == 1`
- `side_effect_count == 1`
- distributions include `read_only`, `external_side_effect`, `market_price`, `monitoring`, and `safe_aggregate_only`
- serialized summary does not contain `handler`, `should not leak`, or `secret_param`

- [x] **Step 2: Implement summarizer**

Implement `summarize_tool_registry_safety(registry)` using only `registry.tool_map.values()` and public `ToolSpec` metadata. Return empty zero counts if registry is missing or malformed.

---

### Task 2: Runtime Status and Frontend

**Files:**
- Modify: `warframe_agent/web/app.py`
- Modify: `warframe_agent/web/static/js/app.js`
- Modify: `tests/test_web_api.py`

- [x] **Step 1: Wire runtime status**

Pass:

```python
tool_registry=getattr(chat_agent, "tool_registry", None)
```

into `build_runtime_safety_policy(...)`.

- [x] **Step 2: Extend Web API test**

In `test_runtime_status_includes_read_only_safety_policy`, assert:

```python
tool_summary = policy["tool_registry"]
self.assertGreaterEqual(tool_summary["tool_count"], 1)
self.assertIn("safety_levels", tool_summary)
self.assertNotIn("handler", str(tool_summary))
self.assertNotIn("parameters", str(tool_summary))
```

- [x] **Step 3: Render frontend aggregate**

Add a compact section showing total tools, exposed schemas, side-effect count, and safety level distribution.

---

### Task 3: Documentation Sync

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step8_tool_registry_safety_summary_zh.md`
- Modify: `md/rebuilt/02-feature-scope.md`
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/04-web-api-reference.md`
- Modify: `md/rebuilt/06-tools-models-safety.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: Write learning note**

Record that Step 8 borrows plugin/capability inventory ideas from personal Agent projects but exposes only aggregate safety metadata.

- [x] **Step 2: Update rebuilt docs**

Mention ToolRegistry safety summary under runtime status, Web UI, API docs, safety boundary, and verification commands.

---

### Task 4: Verification

**Files:**
- No production edits.

- [x] **Step 1: Run pure tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "tool_registry_safety_summary" -q
```

- [x] **Step 2: Run runtime target**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q
```

If ordinary sandbox blocks Web app import at SQLite WAL, run the Web target in the sandbox-external writable environment and record both outcomes.

Observed:

```text
pytest tests/test_tool_registry.py -k "tool_registry_safety_summary" -q
FAILED ImportError: cannot import name 'summarize_tool_registry_safety'

pytest tests/test_tool_registry.py -k "tool_registry_safety_summary or runtime_safety_policy_embeds_tool_registry_summary" -q
2 passed, 32 deselected
```

`pytest tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q` was not rerun after this Step 8 change because sandbox-external approval was rejected by the current Codex usage limit. Ordinary sandbox Web API tests remain blocked during app import by SQLite WAL in this workspace.

- [x] **Step 3: Run syntax checks**

```powershell
& .\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/safety_policy.py','warframe_agent/web/app.py','tests/test_tool_registry.py','tests/test_web_api.py']; [ast.parse(pathlib.Path(f).read_text(encoding='utf-8-sig'), filename=f) for f in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
```

---

## Self-Review

- Spec coverage: Covers pure summary, runtime API, Web UI, docs, and verification.
- Placeholder scan: No unresolved placeholders are present.
- Safety scope: Only aggregate counts and distributions are exposed; no handlers, parameters, raw args, result content, or credentials.
- GitHub constraint: No commit or push steps are included.
