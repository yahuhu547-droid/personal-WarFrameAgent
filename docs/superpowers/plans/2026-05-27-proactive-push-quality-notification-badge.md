# Proactive Push Quality Notification Badge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Step 28 已写入主动推送 payload 的 Scout 推送质量聚合信号，轻量展示到 Web 主动推送聊天通知卡片里，让用户收到机会时能看到“表现好 / 需谨慎 / 观察中 / 待复盘”的历史质量提示。

**Architecture:** 只改前端通知展示层。`handleNotificationMessage(data)` 继续接收 WebSocket `proactive_push`，新增一个只读 helper 将 `push_quality_*` 聚合字段转成 badge + 简短统计行，然后插入同一条 agent message。该展示不改变推送排序、冷却、机会扫描、交易计划或任何写入行为。

**Safety Boundary:** 质量 badge 只展示聚合字段：`push_quality_score`、`push_quality_reviewed_count`、`push_quality_good_rate`、`push_quality_false_positive_rate`。不展示 raw metadata、raw orders、玩家名、profile URL、market URL、`/w`、whisper、token 或聊天原文；所有文本继续走 `escapeHtml`。

**Tech Stack:** 原生 JavaScript Web UI、Playwright UI tests、pytest。

---

### Task 1: 红测主动推送质量 badge

**Files:**
- Modify: `tests/test_web_ui_playwright.py`

- [x] **Step 1: 扩展主动推送 WebSocket 测试 payload**

在 `test_websocket_proactive_push_renders_actionable_trade_plan` 的 `window.handleNotificationMessage(...)` payload 中增加：

```javascript
data: {
    push_quality_score: 1,
    push_quality_reason: 'good_quality_history',
    push_quality_reviewed_count: 5,
    push_quality_good_rate: 0.8,
    push_quality_false_positive_rate: 0.2,
    profile_url: 'https://warframe.market/profile/QualityLeak',
    market_url: 'https://warframe.market/items/quality_leak',
    whisper: '/w QualityLeak secret'
},
```

- [x] **Step 2: 新增断言**

断言聊天区包含：

```python
expect(chat).to_contain_text("表现好")
expect(chat).to_contain_text("复盘 5")
expect(chat).to_contain_text("好评率 80%")
expect(chat).to_contain_text("误报率 20%")
```

同时断言质量 badge 不泄漏额外字段：

```python
assert "QualityLeak" not in chat.evaluate("node => node.textContent")
assert "/w QualityLeak" not in chat.evaluate("node => node.textContent")
```

- [x] **Step 3: 运行红测**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_websocket_proactive_push_renders_actionable_trade_plan --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: FAIL，因为前端还没有主动推送质量 badge helper。

Actual RED:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_app_static_contracts_include_proactive_push_quality_badge --basetemp .pytest-tmp -p no:cacheprovider
# 1 failed
```

---

### Task 2: 前端实现质量 badge helper

**Files:**
- Modify: `warframe_agent/web/static/js/app.js`

- [x] **Step 1: 新增格式化 helper**

新增：

```javascript
function formatPushQualityRate(value) { ... }
function getProactivePushQualityBadge(data) { ... }
function renderProactivePushQualityBadge(data) { ... }
```

规则：
- `push_quality_reviewed_count <= 0`：`待复盘` / `badge-muted`。
- `push_quality_score > 0`：`表现好` / `badge-green`。
- `push_quality_score < 0`：`需谨慎` / `badge-red`。
- 其他有聚合字段的情况：`观察中` / `badge-gold`。

- [x] **Step 2: 插入通知聊天卡**

在 `handleNotificationMessage(data)` 的 `proactive_push` 分支里，`addChatMessage('agent', msg)` 后，将 `renderProactivePushQualityBadge(data)` append 到 `.message-content`，再继续追加 `trade_plan`。

- [x] **Step 3: 暴露静态契约**

将 `renderProactivePushQualityBadge` 挂到 `window`，便于 Playwright/静态契约验证。

---

### Task 3: 绿色验证与文档同步

**Files:**
- Modify: `tests/test_web_ui_playwright.py`
- Modify: `warframe_agent/web/static/js/app.js`
- Add: `githubProduct/personal_agent_warframe_migration_step30_proactive_push_quality_notification_badge_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: 跑目标 Playwright 测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_websocket_proactive_push_renders_actionable_trade_plan --basetemp .pytest-tmp -p no:cacheprovider
```

- [x] **Step 2: 跑静态/语法验证**

```powershell
.\.venv\Scripts\python.exe -m py_compile warframe_agent\web\app.py
```

普通沙箱下默认 `__pycache__` 输出遇到权限限制，已改为项目内 `.pytest-tmp` 输出补跑：

```powershell
.\.venv\Scripts\python.exe -c "import py_compile; py_compile.compile(r'warframe_agent\web\app.py', cfile=r'.pytest-tmp\app.pyc', doraise=True); print('py_compile ok')"
# py_compile ok
```

```powershell
node --check warframe_agent\web\static\js\app.js
# passed
```

```powershell
git diff --check -- warframe_agent\web\static\js\app.js tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-27-proactive-push-quality-notification-badge.md githubProduct\personal_agent_warframe_migration_step30_proactive_push_quality_notification_badge_zh.md md\rebuilt\09-personal-agent-foundation.md
# exit 0; only LF -> CRLF warnings for existing tracked JS/test files
```

- [x] **Step 3: 更新学习记录**

在 `githubProduct` 新增 Step 30 总结，并在 `md/rebuilt/09-personal-agent-foundation.md` 追加本步完成内容与剩余后续项。
