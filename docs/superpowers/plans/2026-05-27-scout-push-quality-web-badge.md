# Scout Push Quality Web Badge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在长期交易记忆 Web 面板中新增 Scout 推送质量只读展示，让用户看到机会推送的聚合质量 badge 和“需要复盘”提示。

**Architecture:** 复用现有 `GET /api/trading-memory/push-quality`，前端新增 `push-quality` tab、filter 参数和渲染函数。展示只使用聚合字段，不展示 raw metadata、玩家名、profile、market URL、`/w` 或 token；不新增任何写入行为。

**Tech Stack:** FastAPI 已有 API、原生 JavaScript sidebar panel、Playwright UI tests、pytest。

---

### Task 1: Web UI 红测

**Files:**
- Modify: `tests/test_web_ui_playwright.py`

- [x] **Step 1: 扩展 mock API 返回推送质量聚合**

在 `page_with_api` 的 `/api/trading-memory/` 分支里，新增 `push-quality` 响应：

```python
elif "push-quality" in url:
    json_response(route, {
        "push_quality": [] if state["trading_memory_empty"] else [
            {
                "item_name": XSS_TEXT,
                "source": "spread",
                "strategy": "quality_flip",
                "category": "arcane",
                "sent_count": 8,
                "reviewed_count": 5,
                "completed_count": 4,
                "accepted_count": 0,
                "rejected_count": 1,
                "pending_count": 3,
                "good_count": 4,
                "bad_count": 1,
                "avg_expected_profit": 50.0,
                "avg_actual_profit": 61.0,
                "avg_profit_delta": 11.0,
                "good_rate": 0.8,
                "completion_rate": 0.8,
                "rejection_rate": 0.2,
                "false_positive_rate": 0.2,
            },
            {
                "item_name": "arcane_pending",
                "source": "spread",
                "strategy": "quality_flip",
                "category": "arcane",
                "sent_count": 3,
                "reviewed_count": 0,
                "completed_count": 0,
                "accepted_count": 0,
                "rejected_count": 0,
                "pending_count": 3,
                "good_count": 0,
                "bad_count": 0,
                "avg_expected_profit": 0.0,
                "avg_actual_profit": 0.0,
                "avg_profit_delta": 0.0,
                "good_rate": 0.0,
                "completion_rate": 0.0,
                "rejection_rate": 0.0,
                "false_positive_rate": 0.0,
            },
        ],
        "count": 0 if state["trading_memory_empty"] else 2,
    })
```

- [x] **Step 2: 扩展交易记忆面板测试**

在 `test_trading_memory_panel_renders_tabs_safely_and_read_only` 中点击 `#trading-memory-tab-push-quality`，断言页面包含：

```python
expect(content).to_contain_text("推送质量")
expect(content).to_contain_text("表现好")
expect(content).to_contain_text("待复盘")
expect(content).to_contain_text("好评率 80%")
expect(content).to_contain_text("误报率 20%")
expect(content).to_contain_text("利润偏差 +11p")
```

并继续断言 XSS payload 不会生成图片节点、请求都是 `GET`。

- [x] **Step 3: 扩展 filter/error 测试**

在现有交易记忆过滤测试片段中点击 `#trading-memory-tab-push-quality`，填入 source，刷新后断言 URL 包含：

```python
assert "source=spread" in state["trading_memory_requests"][-1]["url"]
```

并设置 `trading_memory_error_endpoint = "push-quality"`，断言页面显示 `加载推送质量失败`。

- [x] **Step 4: 运行红测**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# RED: 1 failed
```

Expected: FAIL，因为前端还没有 `push-quality` tab 和 renderer。普通沙箱下 Playwright server 用例会先遇到 SQLite WAL `unable to open database file`，因此以静态契约作为红测。

### Task 2: 前端只读质量 badge 实现

**Files:**
- Modify: `warframe_agent/web/static/js/sidebar.js`

- [x] **Step 1: 新增 tab 配置**

在 `TRADING_MEMORY_TABS` 中新增：

```javascript
'push-quality': {
    label: '推送质量',
    endpoint: '/api/trading-memory/push-quality',
    responseKey: 'push_quality',
    typeParam: 'source',
    typeLabel: '来源',
    placeholder: 'spread'
}
```

- [x] **Step 2: 接入 renderer**

在 `fetchTradingMemoryTab(...)` 中增加分支：

```javascript
} else if (tab === 'push-quality') {
    results.innerHTML = renderPushQuality(records);
}
```

- [x] **Step 3: 新增安全渲染 helper**

新增：

```javascript
function renderPushQuality(records) { ... }
function renderPushQualityBadge(record) { ... }
function formatQualityRate(value) { ... }
function formatProfitDelta(value) { ... }
```

规则：
- `reviewed_count <= 0`：badge `待复盘` / muted。
- `false_positive_rate >= 0.5` 或 `good_rate <= 0.25` 且已复盘：badge `需谨慎` / red。
- `good_rate >= 0.6` 且 `false_positive_rate <= 0.25`：badge `表现好` / green。
- 其他：badge `观察中` / gold。

所有字段使用 `escapeHtml`，只显示聚合数值。

- [x] **Step 4: 运行绿测**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# GREEN: 1 passed
```

Expected: PASS。

### Task 3: 学习记录同步

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step29_scout_push_quality_web_badge_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: 新增 Step 29 学习记录**

记录：质量 badge 是聚合观察面板，不是推送决策本身；pending_count 用于提醒“需要复盘”；不展示 raw 历史。

- [x] **Step 2: 更新 rebuilt**

追加 Step 29 完成说明、行为边界和验证命令。

### Task 4: 回归验证

**Files:**
- Verify only

- [x] **Step 1: 运行定向 UI 和 API 测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_trading_memory_panel_renders_tabs_safely_and_read_only tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# 2 passed

.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "push_quality or trading_memory_endpoints_are_read_only" --basetemp .pytest-tmp -p no:cacheprovider
# 2 passed, 68 deselected
```

Note: 上述 UI/API 验证需要非沙箱执行；普通沙箱导入 Web app 时会触发 SQLite WAL `unable to open database file`。较宽的 `whisper_compare` 选择集还有一个既有 XSS 断言失败，发生在进入交易记忆面板前，不属于本步改动。

- [x] **Step 2: 静态检查**

Run:

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
git diff --check -- warframe_agent\web\static\js\sidebar.js tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-27-scout-push-quality-web-badge.md githubProduct\personal_agent_warframe_migration_step29_scout_push_quality_web_badge_zh.md md\rebuilt\09-personal-agent-foundation.md
```

Expected: exit code 0；普通沙箱若 Web API 导入触发 SQLite WAL 问题，记录边界并保留 UI mock 验证。
