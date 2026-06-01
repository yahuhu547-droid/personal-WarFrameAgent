# Push Quality Comparison Sort Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `推送质量` 面板中新增 source/strategy 对比排序，让用户能按“待复盘优先 / 表现最好 / 风险最高”快速查看聚合质量。

**Architecture:** 只改 Web 前端。`GET /api/trading-memory/push-quality` 继续返回同一批安全聚合字段；排序在浏览器本地完成，不向后端新增 `sort` 参数、不新增写入端点。排序仅使用 `pending_count`、`reviewed_count`、`good_rate`、`false_positive_rate`、`bad_count`、`avg_profit_delta` 等聚合字段。

**Tech Stack:** 原生 JavaScript sidebar panel、Playwright UI tests、pytest、项目内 `.venv`。

---

### Task 1: 红测推送质量排序

**Files:**
- Modify: `tests/test_web_ui_playwright.py`

- [x] **Step 1: 扩展 push-quality mock**

把 mock 改成三条可排序记录：

```python
{
    "item_name": "arcane_pending",
    "source": "spread",
    "strategy": "quality_flip",
    "pending_count": 3,
    "reviewed_count": 0,
    "good_rate": 0.0,
    "false_positive_rate": 0.0,
    ...
},
{
    "item_name": "arcane_good",
    "source": "spread",
    "strategy": "good_flip",
    "pending_count": 0,
    "reviewed_count": 5,
    "good_rate": 0.8,
    "false_positive_rate": 0.2,
    "avg_profit_delta": 11.0,
    ...
},
{
    "item_name": "arcane_risky",
    "source": "auction",
    "strategy": "risky_flip",
    "pending_count": 0,
    "reviewed_count": 4,
    "good_rate": 0.1,
    "false_positive_rate": 0.75,
    ...
}
```

敏感字段继续放在其中一条记录上，验证排序不会使用或泄漏它们。

- [x] **Step 2: 扩展面板行为测试**

在 `test_trading_memory_panel_renders_tabs_safely_and_read_only` 中：

```python
cards = content.locator("#trading-memory-results .trading-memory-record")
expect(page.locator("#push-quality-sort-filter")).to_have_value("review")
expect(cards.first()).to_contain_text("arcane_pending")

page.locator("#push-quality-sort-filter").select_option("quality")
expect(cards.first()).to_contain_text("arcane_good")

page.locator("#push-quality-sort-filter").select_option("risk")
expect(cards.first()).to_contain_text("arcane_risky")

assert "sort=" not in state["trading_memory_requests"][-1]["url"]
```

- [x] **Step 3: 扩展静态契约测试**

在 `test_sidebar_static_contracts_match_warframe_player_context` 增加：

```python
assert "id=\"push-quality-sort-filter\"" in sidebar_script
assert "function getPushQualitySortMode" in sidebar_script
assert "function sortPushQualityRecords" in sidebar_script
assert "待复盘优先" in sidebar_script
assert "表现最好" in sidebar_script
assert "风险最高" in sidebar_script
```

- [x] **Step 4: 运行红测**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: FAIL，因为 sidebar 还没有排序控件和排序 helper。

Actual RED:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# 1 failed
```

---

### Task 2: 实现前端本地排序

**Files:**
- Modify: `warframe_agent/web/static/js/sidebar.js`

- [x] **Step 1: 新增排序控件**

在 `renderTradingMemoryShell(...)` 的 filter 区域中，只有 `activeTab === 'push-quality'` 时插入：

```html
<select id="push-quality-sort-filter" aria-label="推送质量排序">
    <option value="review" selected>待复盘优先</option>
    <option value="quality">表现最好</option>
    <option value="risk">风险最高</option>
</select>
```

- [x] **Step 2: 绑定排序变化**

在 `bindTradingMemoryControls(content)` 中对 `#push-quality-sort-filter` 绑定 `change`，调用 `fetchTradingMemoryTab(tradingMemoryActiveTab)`。

- [x] **Step 3: 新增排序 helper**

新增：

```javascript
function getPushQualitySortMode() { ... }
function pushQualityNumber(value, fallback = 0) { ... }
function pushQualityName(value) { ... }
function sortPushQualityRecords(records, mode) { ... }
```

规则：
- `review`：`pending_count` 降序、`reviewed_count` 升序、`sent_count` 降序。
- `quality`：`good_rate` 降序、`false_positive_rate` 升序、`reviewed_count` 降序、`avg_profit_delta` 降序。
- `risk`：`false_positive_rate` 降序、`bad_count` 降序、`good_rate` 升序。
- 最后用 `item_name/source/strategy` 做稳定字母序兜底。

- [x] **Step 4: 接入渲染**

在 `fetchTradingMemoryTab(tab)` 的 `push-quality` 分支中：

```javascript
results.innerHTML = renderPushQuality(sortPushQualityRecords(records, getPushQualitySortMode()));
```

---

### Task 3: 文档同步与验证

**Files:**
- Add: `githubProduct/personal_agent_warframe_migration_step32_push_quality_comparison_sort_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `docs/superpowers/plans/2026-05-27-push-quality-comparison-sort.md`

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
git diff --check -- warframe_agent\web\static\js\sidebar.js tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-27-push-quality-comparison-sort.md githubProduct\personal_agent_warframe_migration_step32_push_quality_comparison_sort_zh.md md\rebuilt\09-personal-agent-foundation.md
# exit 0; only LF -> CRLF warnings for existing tracked JS/test files
```

- [x] **Step 3: 更新学习记录**

记录本步是“本地只读排序”，不改变后端聚合、不写入、不展示 raw 历史；同步到 `githubProduct` 和 `md/rebuilt`。
