# Step 25 - Natural Language Goal Status Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users complete or abandon goals with normal chat, such as `完成第1个目标` and `放弃第1个目标`, but require confirmation before changing goal status.

**Architecture:** Add a small pending confirmation state in `ChatAgent` for goal status changes. Natural-language requests resolve to one active goal by index, ID prefix, or description fragment, then ask for confirmation; existing `/goal done ID` and `/goal drop ID` remain immediate explicit commands.

**Tech Stack:** Python `ChatAgent`, `GoalTracker`, pytest via project `.venv`.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/test_chat_memory_commands.py`

- [x] Add fake goal tracker support for `update_goal_status(...)` and `generate_review(...)`.
- [x] Add a test that `完成第1个目标` asks for confirmation and keeps the goal active.
- [x] Add a test that `确认完成` after the prompt marks the goal `achieved`.
- [x] Add a test that `取消` after the prompt keeps the goal active.
- [x] Add a test that `放弃第1个目标` followed by `确认放弃` marks the goal `abandoned`.
- [x] Add `answer_stream(...)` parity coverage.
- [x] Add guard coverage that questions and `/goal done ID` are not routed through the natural-language confirmation path.

### Task 2: Implement Parser, Resolver, And Pending State

**Files:**
- Modify: `warframe_agent/chat.py`

- [x] Add `PendingGoalStatusConfirmation`.
- [x] Add `_parse_natural_language_goal_status(...)` for `complete/drop` action phrases.
- [x] Resolve a target by active-goal index (`第1个目标`), goal ID prefix, or description fragment.
- [x] Return a clear ambiguity/not-found message when natural language does not identify exactly one active goal.
- [x] Add `_try_goal_status_confirmation_response(...)` and call it before existing goal-creation confirmation.
- [x] Add `_try_goal_status_intent(...)` after slash commands and before planning/normal routing.
- [x] Execute confirmed updates via `GoalTracker.update_goal_status(...)`; for completion reuse `generate_review(...)`.

### Task 3: Sync Learning Docs

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step25_natural_language_goal_status_confirmation_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/02-feature-scope.md`

- [x] Record why destructive/high-impact memory updates need confirmation.
- [x] Record supported target selectors and guard rules.
- [x] Record verification commands and results.

### Task 4: Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "goal_status_confirmation or goal_confirmation or goal_set" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```
