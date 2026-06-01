# Step 24 - Natural Language Preferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users update long-term trading preferences with normal chat, such as `我的预算300p，偏低风险，最低利润15%`, while keeping `/pref ...` as the explicit fallback command.

**Architecture:** Add a conservative deterministic parser in `ChatAgent` that extracts only explicit preference-setting phrases into `TradingPreferences` updates. Reuse `AgentMemory.with_updated_preferences(...)` and the existing persistence path; do not change scanner APIs, Web APIs, or one-off market query behavior.

**Tech Stack:** Python `ChatAgent`, `AgentMemory.TradingPreferences`, pytest via project `.venv`.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/test_chat_memory_commands.py`

- [x] Add a test for `我的预算300p，偏低风险，最低利润15%` updating `budget_max=300`, `risk_appetite=low`, and `min_roi_pct=15`.
- [x] Add a test for `我偏好mod和赋能，最长周转3天` updating `preferred_categories=["mod", "arcane"]` and `max_turnaround_days=3`.
- [x] Add a test for `平台设为xbox，关闭跨平台，最多显示10个结果`.
- [x] Add a test for `answer_stream("我预算30到150p，最低ROI25%")` matching regular answer behavior.
- [x] Add guard tests that `300p预算买什么好`, `充沛低于45p提醒我`, `帮我收藏充沛`, and `交易机会只检测MOD` do not update long-term preferences.

### Task 2: Implement Parser And Handler

**Files:**
- Modify: `warframe_agent/chat.py`

- [x] Add `PreferenceIntent` and `_parse_natural_language_preference(...)`.
- [x] Support risk words: `低风险/保守/稳健`, `中风险/均衡`, `高风险/激进`.
- [x] Support budget ranges and single upper budgets: `预算300p`, `预算30到150p`.
- [x] Support `最低ROI25%`, `最低利润15%`, and `最长周转3天`.
- [x] Support category words: `mod`, `赋能`, `prime套`, `prime部件`, `紫卡`, `虚空商人`.
- [x] Support explicit platform/crossplay/max-result settings when present.
- [x] Insert the handler after price alert and favorite handling, before generic item routing.

### Task 3: Sync Learning Docs

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step24_natural_language_preferences_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/02-feature-scope.md`

- [x] Record the command-to-chat UX lesson for preference memory.
- [x] Record guard rules for one-off questions vs long-term preferences.
- [x] Record verification commands and results.

### Task 4: Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_preference or profile_pref" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```
