# Step 29：Scout 推送质量 Web badge 展示

## 本次借鉴点

- 推送质量进入排序后，用户还需要一个只读观察面板来理解“为什么某类机会更常被优先推”。这次学习的是把 Agent 的反馈闭环透明化，而不是增加新的自动决策。
- 质量展示应放在长期交易记忆面板中，作为 `push_history` 和 `opportunity_outcomes` 上方的聚合观察，不应混进单条推送历史里。
- UI 只展示聚合统计和 badge：发送数、复盘数、待复盘数、好评率、误报率、利润偏差、完成/拒绝/好坏结果数。不能展示 raw metadata、raw orders、玩家名、profile URL、market URL、`/w` 私聊或 token。

## 已完成

- `warframe_agent/web/static/js/sidebar.js`
  - 在 `TRADING_MEMORY_TABS` 中新增 `push-quality` 标签页。
  - 复用 `GET /api/trading-memory/push-quality`，filter 中的类型输入映射为 `source` 参数。
  - 新增 `renderPushQuality(records)`，用卡片展示聚合质量。
  - 新增 `renderPushQualityBadge(record)`：
    - 未复盘：`待复盘`。
    - 误报率高或好评率低：`需谨慎`。
    - 好评率高且误报率低：`表现好`。
    - 其他：`观察中`。
  - 新增 `formatQualityRate(...)` 和 `formatProfitDelta(...)`，把比例和利润偏差显示成用户可扫读的格式。

- `tests/test_web_ui_playwright.py`
  - Playwright mock 新增 `/api/trading-memory/push-quality` 响应。
  - 交易记忆面板测试覆盖 `推送质量` tab、`表现好`、`待复盘`、`好评率 80%`、`误报率 20%`、`利润偏差 +11p`。
  - filter 测试覆盖 `source=spread`。
  - 错误态测试覆盖 `加载推送质量失败`。
  - 静态契约测试要求 `push-quality` tab、endpoint、responseKey 和 renderer 存在。

- `tests/test_web_api.py`
  - `test_trading_memory_endpoints_are_read_only` 增加 `/api/trading-memory/push-quality`，确认它只调用 `summarize_push_quality`，不调用任何 `record_` 写入方法。

## 行为边界

- Web badge 是观察层，不会改变主动推送排序、冷却去重、用户偏好或机会扫描。
- `pending_count` 表示“等待复盘”，不是“坏质量”。
- 前端所有字段仍走 `escapeHtml`，测试继续用 XSS payload 验证不会生成图片节点。
- 后端已有序列化边界保持不变，只返回 `PushQualitySignal` 聚合字段。

## 准备继续学习的清单

- 可继续把 `pending_count` 变成“复盘提醒”入口，但必须仍然确认后写入。
- 可把质量 badge 轻量展示到主动推送通知卡片里，但只显示聚合标签，不显示历史明细。
- 可在 Web 面板中增加 source/strategy 的对比排序，但不要引入 raw 历史明细。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# RED: 1 failed
# GREEN: 1 passed

.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_trading_memory_panel_renders_tabs_safely_and_read_only tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context --basetemp .pytest-tmp -p no:cacheprovider
# 2 passed

.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "push_quality or trading_memory_endpoints_are_read_only" --basetemp .pytest-tmp -p no:cacheprovider
# 2 passed, 68 deselected
```

普通沙箱下 Web app 导入仍会因 SQLite WAL 报 `sqlite3.OperationalError: unable to open database file`；上述 Web/UI 与 API 验证是在非沙箱下用项目内 `.venv` 跑通的。较宽的 `whisper_compare` 选择集中有一个既有 XSS 断言失败，发生在进入交易记忆面板前，不属于本步改动。
