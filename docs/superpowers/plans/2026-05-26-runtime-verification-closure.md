# Runtime Verification Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the verification gap for the Step 4-13 personal-agent runtime, safety, profile feedback, and Web UI work before adding new feature scope.

**Architecture:** This is a verification-first learning migration step. It does not introduce new runtime behavior unless tests reveal a real defect; it runs focused Web API, Playwright, ToolRegistry, profile, and review-command checks, then records the verified state in `githubProduct` and `md/rebuilt`.

**Tech Stack:** Python pytest in the project `.venv`, Playwright UI tests through existing fixtures, Node syntax check, Markdown documentation.

---

## File Structure

- Create: `githubProduct/personal_agent_warframe_migration_step14_runtime_verification_closure_zh.md`
  - Record the verification closure, commands, pass/fail results, and next remaining learning tasks.
- Modify: `md/rebuilt/07-operations-testing.md`
  - Add the focused Step 14 command set and the observed sandbox/escalation note.
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - Add the Step 14 verification closure note.
- Modify only if a test exposes a real bug:
  - `warframe_agent/web/app.py`
  - `warframe_agent/web/static/js/app.js`
  - `warframe_agent/tool_router.py`
  - `warframe_agent/chat.py`
  - corresponding `tests/*.py`

No package install is planned. No Git commit or GitHub push is planned.

---

### Task 1: Runtime And Safety API Verification

**Files:**
- Read: `tests/test_web_api.py`
- Read: `tests/test_tool_registry.py`
- Modify only if failing for a product bug: `warframe_agent/web/app.py`, `warframe_agent/safety_policy.py`, `warframe_agent/tool_registry.py`

- [x] **Step 1: Run runtime status Web API checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k "runtime_status" -q
```

Expected: all selected tests pass. If the ordinary sandbox fails while importing the Web app with `sqlite3.OperationalError: unable to open database file`, rerun the same command in the approved writable environment and record that reason.

- [x] **Step 2: Run ToolRegistry safety summary checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_registry.py -k "tool_registry_safety_summary or runtime_safety_policy_embeds_tool_registry_summary" -q
```

Expected: both selected tests pass and no handler, raw parameter schema, raw args, `ToolResult`, or model context is exposed through the safety summary.

---

### Task 2: Runtime Web UI Verification

**Files:**
- Read: `tests/test_web_ui_playwright.py`
- Read: `warframe_agent/web/static/js/app.js`
- Modify only if failing for a product bug: `warframe_agent/web/static/js/app.js`, `tests/test_web_ui_playwright.py`

- [x] **Step 1: Run focused runtime Playwright checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py -k "runtime_panel" -q
```

Expected: runtime panel tests pass, including the AgentTrace and AgentPlan safe rendering checks. If local Uvicorn/Playwright cannot become ready in the ordinary sandbox, rerun the same command in the approved writable environment and record that reason.

- [x] **Step 2: Run JavaScript syntax check**

Run:

```powershell
node --check warframe_agent/web/static/js/app.js
```

Expected: exit code 0.

---

### Task 3: Profile Feedback And Review Command Verification

**Files:**
- Read: `tests/test_personal_profile.py`
- Read: `tests/test_chat_memory_commands.py`
- Modify only if failing for a product bug: `warframe_agent/personal_profile.py`, `warframe_agent/chat.py`, `warframe_agent/trading_memory.py`

- [x] **Step 1: Run SQLite opportunity outcome profile checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py -k "sqlite_opportunity_outcomes or outcome_feedback" -q
```

Expected: selected profile tests pass and sensitive outcome metadata is not echoed.

- [x] **Step 2: Run review command and SQLite outcome checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "sqlite_outcomes or review" -q
```

Expected: selected command tests pass; `/review done OPID actual_profit [feedback]` records only safe summaries and `/review completed` remains a status filter.

---

### Task 4: Documentation Sync

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step14_runtime_verification_closure_zh.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: Write the Step 14 migration note**

Document:

```markdown
# Step 14: 运行态验证闭环

- 本步不新增能力，目标是补齐 Step 4-13 的 Web/API/UI/记忆验证闭环。
- 记录已运行命令、通过结果、普通沙箱限制和可写环境重跑情况。
- 记录下一轮剩余学习任务：普通物品交易辅助意图扩展、长期记忆 vault 化、Scout 推送质量评估、聊天模式分层。
```

- [x] **Step 2: Update rebuilt operations docs**

Append the focused Step 14 command set to `md/rebuilt/07-operations-testing.md`.

- [x] **Step 3: Update personal-agent foundation docs**

Append a short Step 14 verification closure section to `md/rebuilt/09-personal-agent-foundation.md`.

---

### Task 5: Final Verification

**Files:**
- All files listed above.

- [x] **Step 1: Run AST checks for touched Python tests**

Run:

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['tests/test_web_api.py','tests/test_tool_registry.py','tests/test_web_ui_playwright.py','tests/test_personal_profile.py','tests/test_chat_memory_commands.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

Expected: `AST OK`.

- [x] **Step 2: Run diff whitespace check**

Run:

```powershell
git diff --check -- docs/superpowers/plans/2026-05-26-runtime-verification-closure.md githubProduct/personal_agent_warframe_migration_step14_runtime_verification_closure_zh.md md/rebuilt/07-operations-testing.md md/rebuilt/09-personal-agent-foundation.md
```

Expected: exit code 0, with CRLF warnings allowed.

## Self-review

- Spec coverage: covers runtime API, ToolRegistry safety, Playwright UI, profile feedback, review command, and docs sync.
- Placeholder scan: no TBD/TODO/fill-later placeholders.
- Type consistency: no new API shape is introduced; this plan only verifies existing tests unless a product bug is found.
