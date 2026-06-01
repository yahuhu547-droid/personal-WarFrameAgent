# Step 26 - Natural Language Review Done Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users record opportunity outcomes with normal chat, such as `OP8K3A2Q 实际赚45p，结果不错，帮我复盘`, while requiring confirmation before writing trading memory.

**Architecture:** Add a deterministic parser that extracts an opportunity ID, actual profit, and optional feedback from natural language. Store the parsed outcome in a pending confirmation state; on confirmation, reuse the same safe write path as `/review done OPID profit feedback`.

**Tech Stack:** Python `ChatAgent`, `OpportunityLookupStore`, `TradingMemoryDB`, pytest via project `.venv`.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/test_chat_memory_commands.py`

- [x] Add a test that `OPID 实际赚45p，结果不错，帮我复盘` asks for confirmation and does not write immediately.
- [x] Add a test that `确认复盘` after the prompt writes one completed opportunity outcome.
- [x] Add a test that `取消` after the prompt does not write.
- [x] Add a test that `answer_stream(...)` matches regular answer behavior.
- [x] Add guard tests that missing OP ID, malformed profit, or normal market chat does not create pending review state.
- [x] Add coverage that explicit `/review done OPID 45 good` still writes immediately.

### Task 2: Implement Parser And Pending Confirmation

**Files:**
- Modify: `warframe_agent/chat.py`

- [x] Add `ReviewDoneIntent` and `PendingReviewDoneConfirmation`.
- [x] Add `_parse_natural_language_review_done(...)` to require a valid opportunity ID and an integer profit.
- [x] Normalize Chinese feedback words: `不错/很好/成功/赚了` -> `good`; `亏/失败/不好` -> `bad`; `忽略/没做` -> `ignored`; otherwise default from profit.
- [x] Add `_try_review_done_confirmation_response(...)` and call it before goal confirmations.
- [x] Add `_try_review_done_intent(...)` after slash commands and before generic routing.
- [x] Reuse `_handle_review_record_command([lookup_id, profit, feedback])` for the confirmed write.

### Task 3: Sync Learning Docs

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step26_natural_language_review_done_confirmation_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/02-feature-scope.md`

- [x] Record why trade memory writes need confirmation.
- [x] Record supported profit/feedback phrases and guard rules.
- [x] Record verification commands and results.

### Task 4: Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "review_done_natural_language or review_done_command" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```
