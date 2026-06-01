# Step 21 - Confirmed Goal Creation And Command UX Audit

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let normal chat create trackable goals through an explicit confirmation turn, and document the remaining command-first UX surfaces.

**Architecture:** Keep `/goal set` as the safe low-level command, but have natural-language planning store an in-memory pending goal preview on the `ChatAgent` instance. A later confirmation phrase creates the same `GoalTracker` goal; a cancellation phrase clears it. The command audit is documentation only in this step.

**Tech Stack:** Python `ChatAgent`, existing `goals.py` parser, pytest, local `.venv`.

---

### Task 1: Red Tests For Confirmed Goal Creation

**Files:**
- Modify: `tests/test_chat_memory_commands.py`

- [x] Add tests showing natural-language planning asks for confirmation without writing a goal.
- [x] Add tests showing `确认创建` writes the parsed goal.
- [x] Add tests showing `取消` clears pending confirmation.

### Task 2: ChatAgent Pending Goal Confirmation

**Files:**
- Modify: `warframe_agent/chat.py`

- [x] Add an in-memory pending goal confirmation dataclass.
- [x] Let `_try_planning_intent(...)` populate pending state only when the parsed description contains trackable signals.
- [x] Add `_try_goal_confirmation_response(...)` before the normal routing path.
- [x] Reuse the same goal creation helper for `/goal set` and confirmation.

### Task 3: Command UX Audit

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step21_confirmed_goal_creation_and_command_audit_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/07-operations-testing.md`

- [x] Document which commands are already natural-language friendly.
- [x] Document which commands still require Slash Command syntax.
- [x] Rank follow-up candidates by risk and user impact.

### Task 4: Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "goal_confirmation or goal_set" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "planning_mode" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```
