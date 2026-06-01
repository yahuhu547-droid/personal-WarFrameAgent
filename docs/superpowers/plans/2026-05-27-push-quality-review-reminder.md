# Push Quality Review Reminder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `推送质量` 面板里，把 `pending_count`/低复盘样本变成安全的复盘提醒入口，帮助用户进入现有自然语言“先确认、再写入”的机会复盘流程。

**Architecture:** 只改 Web 前端的长期交易记忆面板。`renderPushQuality(records)` 继续展示聚合质量；当一条聚合记录 `pending_count > 0` 或 `reviewed_count < 5` 时，额外显示一个复盘提醒块和“填入复盘模板”按钮。按钮只把自然语言复盘草稿填进聊天输入框，不发送、不调用 API、不写库；实际写入仍由 ChatAgent 现有自然语言复盘确认链完成。

**Tech Stack:** 原生 JavaScript sidebar panel、Playwright UI tests、pytest、项目内 `.venv`。

---

### Task 1: 红测推送质量复盘入口

**Files:**
- Modify: `tests/test_web_ui_playwright.py`

- [x] **Step 1: 扩展推送质量 mock 的安全边界**

在 `/api/trading-memory/push-quality` mock 的第一条记录里增加不会被入口使用的敏感字段：

```python
"profile_url": "https://warframe.market/profile/QualityLeak",
"market_url": "https://warframe.market/items/quality_leak",
"whisper": "/w QualityLeak secret",
"player_name": "QualityLeak",
"metadata": {"raw": "/w QualityLeak secret"},
```

- [x] **Step 2: 扩展面板行为测试**

在 `test_trading_memory_panel_renders_tabs_safely_and_read_only` 点击 `#trading-memory-tab-push-quality` 后断言：

```python
expect(content).to_contain_text("复盘提醒")
expect(content).to_contain_text("填入复盘模板")
content.locator(".push-quality-review-btn").first.click()
draft = page.locator("#chat-input")
expect(draft).to_have_value(re.compile(r"OP______ 实际赚__p"))
expect(draft).to_have_value(re.compile(r"来源：spread"))
expect(draft).to_have_value(re.compile(r"策略：quality_flip"))
draft_value = draft.input_value()
assert "QualityLeak" not in draft_value
assert "/w QualityLeak" not in draft_value
assert "<img" not in draft_value
assert state["chat_messages"] == []
```

继续保留 `state["trading_memory_requests"]` 全部为 `GET` 的断言，证明入口没有写请求。

- [x] **Step 3: 扩展静态契约测试**

在 `test_sidebar_static_contracts_match_warframe_player_context` 增加：

```python
assert "function renderPushQualityReviewReminder" in sidebar_script
assert "function fillPushQualityReviewTemplateFromButton" in sidebar_script
assert "function buildPushQualityReviewTemplate" in sidebar_script
assert "push-quality-review-btn" in sidebar_script
assert "OP______ 实际赚__p" in sidebar_script
assert "/review done" not in sidebar_script[sidebar_script.index("function buildPushQualityReviewTemplate") : sidebar_script.index("function renderPushQualityBadge")]
```

- [x] **Step 4: 运行红测**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: FAIL，因为 sidebar 还没有复盘提醒 helper。

Actual RED:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# 1 failed
```

---

### Task 2: 实现安全复盘提醒入口

**Files:**
- Modify: `warframe_agent/web/static/js/sidebar.js`

- [x] **Step 1: 新增安全 helper**

在 `renderPushQuality(records)` 附近新增：

```javascript
function shouldShowPushQualityReviewReminder(record) { ... }
function safePushQualityTemplateField(value) { ... }
function buildPushQualityReviewTemplate(record) { ... }
function renderPushQualityReviewReminder(record) { ... }
function fillPushQualityReviewTemplateFromButton(btn) { ... }
```

规则：
- `shouldShow...` 为 `pending_count > 0 || reviewed_count < 5`。
- `safePushQualityTemplateField(...)` 只允许短的安全标识符，拒绝包含 `<`、`/w`、`profile`、`warframe.market`、`token` 的文本。
- 模板固定以 `OP______ 实际赚__p，结果 good/bad/neutral，帮我复盘。` 开头，确保不是会直接写库的 `/review done`。
- 只使用安全的 `source`、`strategy`、`item_name`；不使用 raw metadata、profile、market URL、whisper、玩家名。

- [x] **Step 2: 在质量卡片里渲染提醒**

在 `renderPushQuality(records)` 的质量 chips 后追加：

```javascript
${renderPushQualityReviewReminder(record)}
```

- [x] **Step 3: 挂全局按钮函数**

```javascript
window.fillPushQualityReviewTemplateFromButton = fillPushQualityReviewTemplateFromButton;
```

---

### Task 3: 文档同步与验证

**Files:**
- Add: `githubProduct/personal_agent_warframe_migration_step31_push_quality_review_reminder_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `docs/superpowers/plans/2026-05-27-push-quality-review-reminder.md`

- [x] **Step 1: 运行目标测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_trading_memory_panel_renders_tabs_safely_and_read_only --basetemp .pytest-tmp -p no:cacheprovider
```

- [x] **Step 2: 运行语法与 diff 检查**

```powershell
node --check warframe_agent\web\static\js\sidebar.js
# passed
```

```powershell
git diff --check -- warframe_agent\web\static\js\sidebar.js tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-27-push-quality-review-reminder.md githubProduct\personal_agent_warframe_migration_step31_push_quality_review_reminder_zh.md md\rebuilt\09-personal-agent-foundation.md
# exit 0; only LF -> CRLF warnings for existing tracked JS/test files
```

- [x] **Step 3: 更新学习记录**

记录本步是“聚合提醒 + 自然语言草稿 + 现有确认链路”，不是自动复盘；同步到 `githubProduct` 和 `md/rebuilt`。
