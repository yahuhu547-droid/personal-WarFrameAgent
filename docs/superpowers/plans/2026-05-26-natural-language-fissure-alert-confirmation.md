# Step 27 - Natural Language Fissure Alert Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users subscribe or unsubscribe fissure alerts with normal chat, such as `提醒我钢铁后纪歼灭裂缝` and `取消第1个裂缝提醒`, while requiring confirmation before changing memory.

**Architecture:** Add a conservative parser for explicit fissure alert subscription phrases. Natural-language requests build a pending confirmation; confirmation reuses existing `_add_fissure_alert(...)` and `_remove_fissure_alert(...)` so memory persistence and dedupe remain unchanged.

**Tech Stack:** Python `ChatAgent`, `AgentMemory.FissureAlert`, pytest via project `.venv`.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/test_chat_memory_commands.py`

- [x] Add a test that `提醒我钢铁后纪歼灭裂缝` asks for confirmation and does not write immediately.
- [x] Add a test that `确认订阅` after the prompt writes one `FissureAlert`.
- [x] Add a test that `取消` after the prompt does not write.
- [x] Add a test that `取消第1个裂缝提醒` asks for confirmation and `确认取消` removes it.
- [x] Add a test that `answer_stream(...)` matches regular answer behavior.
- [x] Add guard tests that fissure queries like `现在有什么裂缝` do not create a pending subscription.
- [x] Add coverage that explicit `/fissure add ...` and `/fissure remove 1` still execute immediately.

### Task 2: Implement Parser And Pending Confirmation

**Files:**
- Modify: `warframe_agent/chat.py`

- [x] Add `FissureAlertIntent` and `PendingFissureAlertConfirmation`.
- [x] Add `_parse_natural_language_fissure_alert(...)` to require fissure wording plus an explicit subscribe/cancel term.
- [x] Support add tokens for tier, mission, node, and steel/normal using existing `_add_fissure_alert(...)` parser.
- [x] Support remove by ordinal/index, such as `取消第1个裂缝提醒`.
- [x] Add `_try_fissure_alert_confirmation_response(...)` and call it before other generic confirmations.
- [x] Add `_try_fissure_alert_intent(...)` before generic event/fissure query routing.
- [x] Confirmed add calls `_add_fissure_alert(tokens)`; confirmed remove calls `_remove_fissure_alert([index])`.

### Task 3: Sync Learning Docs

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step27_natural_language_fissure_alert_confirmation_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/02-feature-scope.md`

- [x] Record why alert subscriptions need confirmation.
- [x] Record supported fissure filters and guard rules.
- [x] Record verification commands and results.

### Task 4: Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "fissure_alert_natural_language or fissure_command" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```
