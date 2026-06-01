# Step 23 - Natural Language Favorites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users add and remove favorite items with normal chat, such as `帮我关注充沛` and `取消关注充沛`, while keeping `/fav add/remove ...` as the explicit fallback command.

**Architecture:** Add a deterministic natural-language parser in `ChatAgent` that only fires on explicit favorite action phrases. Reuse `AgentMemory.with_favorite_item(...)` and `without_favorite_item(...)`; do not alter watchlist, alerts, or Web APIs.

**Tech Stack:** Python `ChatAgent`, `AgentMemory.favorite_items`, pytest via project `.venv`.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/test_chat_memory_commands.py`

- [x] Add a test for `帮我关注充沛` creating a favorite.
- [x] Add a test for `取消关注充沛` removing the favorite.
- [x] Add a test for `answer_stream("帮我收藏充沛")` matching regular answer behavior.
- [x] Add guard tests that `关注列表` and `充沛值得关注吗` do not create favorites.
- [x] Add guard tests that price alerts do not add favorites and repeated favorites dedupe.

### Task 2: Implement Parser And Handler

**Files:**
- Modify: `warframe_agent/chat.py`

- [x] Add `FavoriteIntent` and `_parse_natural_language_favorite(...)`.
- [x] Add `_try_favorite_intent(...)` on `ChatAgent`.
- [x] Insert the handler after watchlist/cycle/price-alert handling and before generic item routing.
- [x] Reuse the same persistence behavior as `/fav`.

### Task 3: Sync Learning Docs

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step23_natural_language_favorites_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/02-feature-scope.md`

- [x] Record the command-to-chat UX lesson.
- [x] Record remaining follow-up candidates.
- [x] Record verification commands and results.

### Task 4: Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_favorite or favorite" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```
