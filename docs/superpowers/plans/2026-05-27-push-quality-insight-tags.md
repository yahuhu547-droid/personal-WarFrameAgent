# Push Quality Insight Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `推送质量` 面板里新增只读策略摘要标签，让用户一眼看出聚合记录是“样本不足 / 稳定盈利 / 高误报 / 观察中”。

**Architecture:** 只改 Web 前端。摘要标签由 `renderPushQuality(records)` 基于现有聚合字段本地计算，不新增后端字段、不新增 API 参数、不改变主动推送排序或复盘写入链路。标签只使用 `reviewed_count`、`pending_count`、`good_rate`、`false_positive_rate`、`avg_profit_delta`、`bad_count` 等安全聚合字段。

**Tech Stack:** 原生 JavaScript sidebar panel、Playwright UI tests、pytest、项目内 `.venv`。

---

### Task 1: 红测策略摘要标签

**Files:**
- Modify: `tests/test_web_ui_playwright.py`

- [x] **Step 1: 扩展面板行为测试**

在 `test_trading_memory_panel_renders_tabs_safely_and_read_only` 的 `推送质量` tab 断言中增加：

```python
expect(content).to_contain_text("样本不足")
expect(content).to_contain_text("稳定盈利")
expect(content).to_contain_text("高误报")
expect(content).to_contain_text("待补复盘")
assert "QualityLeak" not in content.locator("#trading-memory-results").inner_text()
assert "/w QualityLeak" not in content.locator("#trading-memory-results").inner_text()
```

基于现有 mock：
- `arcane_pending` 应显示 `样本不足` 与 `待补复盘`。
- `arcane_good` 应显示 `稳定盈利`。
- `arcane_risky` 应显示 `高误报`。
- `arcane_observe` 应显示 `观察中`。

- [x] **Step 2: 扩展静态契约测试**

在 `test_sidebar_static_contracts_match_warframe_player_context` 增加：

```python
assert "function renderPushQualityInsightTags" in sidebar_script
assert "function getPushQualityInsightTags" in sidebar_script
assert "样本不足" in sidebar_script
assert "稳定盈利" in sidebar_script
assert "高误报" in sidebar_script
assert "待补复盘" in sidebar_script
```

- [x] **Step 3: 运行红测**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: FAIL，因为 sidebar 还没有策略摘要 helper。

Actual RED:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# 1 failed
```

---

### Task 2: 实现只读摘要标签

**Files:**
- Modify: `warframe_agent/web/static/js/sidebar.js`

- [x] **Step 1: 新增摘要 helper**

在 `renderPushQuality(records)` 附近新增：

```javascript
function getPushQualityInsightTags(record) { ... }
function renderPushQualityInsightTags(record) { ... }
```

规则：
- `reviewed_count < 5`：`样本不足` / `badge-muted`。
- `pending_count > 0`：`待补复盘` / `badge-gold`。
- `reviewed_count >= 5 && good_rate >= 0.6 && false_positive_rate <= 0.25 && avg_profit_delta >= 0`：`稳定盈利` / `badge-green`。
- `reviewed_count > 0 && (false_positive_rate >= 0.5 || good_rate <= 0.25 || bad_count >= good_count + 2)`：`高误报` / `badge-red`。
- 如果没有其它标签：`观察中` / `badge-gold`。

- [x] **Step 2: 插入质量卡片**

在 `renderPushQuality(records)` 的统计 chips 后、复盘提醒前加入：

```javascript
${renderPushQualityInsightTags(record)}
```

- [x] **Step 3: 保持安全边界**

Helper 只读取聚合数字字段，不读取 `metadata`、`profile_url`、`market_url`、`whisper`、`player_name` 或 raw 文本。所有标签走 `escapeHtml`。

---

### Task 3: 文档同步与验证

**Files:**
- Add: `githubProduct/personal_agent_warframe_migration_step33_push_quality_insight_tags_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `docs/superpowers/plans/2026-05-27-push-quality-insight-tags.md`

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
git diff --check -- warframe_agent\web\static\js\sidebar.js tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-27-push-quality-insight-tags.md githubProduct\personal_agent_warframe_migration_step33_push_quality_insight_tags_zh.md md\rebuilt\09-personal-agent-foundation.md
# exit 0; only LF -> CRLF warnings for existing tracked JS/test files
```

- [x] **Step 3: 更新学习记录**

记录本步是“聚合摘要标签”，不是新决策逻辑；同步到 `githubProduct` 和 `md/rebuilt`。
