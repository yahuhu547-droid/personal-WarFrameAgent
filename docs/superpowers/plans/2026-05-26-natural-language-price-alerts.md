# Step 22 - Natural Language Price Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users create and remove price alerts with normal chat, such as `充沛低于45p提醒我`, while keeping `/alert add/remove ...` as the explicit fallback command.

**Architecture:** Add a deterministic natural-language parser in `ChatAgent` that only fires when a message contains an alert verb, a direction (`低于/高于`), and a platinum price. Reuse `AgentMemory.with_price_alert(...)` and `without_price_alert(...)`; do not add new storage or background behavior.

**Tech Stack:** Python `ChatAgent`, `AgentMemory.PriceAlert`, pytest via project `.venv`.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/test_chat_memory_commands.py`

- [x] Add a test for `充沛低于45p提醒我` creating a `below` alert.
- [x] Add a test for `充沛高于100p通知我` creating an `above` alert.
- [x] Add a test for `取消充沛低于45p提醒` removing the matching alert.
- [x] Add a guard test that `充沛低于45p了吗` does not create an alert because it lacks a reminder verb.

### Task 2: Implement Parser And Handler

**Files:**
- Modify: `warframe_agent/chat.py`

- [x] Add `_parse_natural_language_price_alert(...)` as a pure helper.
- [x] Add `_try_price_alert_intent(...)` on `ChatAgent`.
- [x] Insert the handler in `answer(...)` and `answer_stream(...)` before generic item routing.
- [x] Reuse existing memory methods and reply wording from `/alert`.

### Task 3: Sync Learning Docs

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step22_natural_language_price_alerts_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/07-operations-testing.md`

- [x] Record the command-to-chat UX lesson.
- [x] Record remaining follow-up candidates.
- [x] Record verification commands and results.

### Task 4: Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_price_alert or add_alert" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```
