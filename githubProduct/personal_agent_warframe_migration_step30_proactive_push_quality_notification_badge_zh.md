# Step 30：主动推送通知卡片展示质量 badge

## 本次借鉴点

- Step 28 已经让主动推送携带 Scout 风格的历史质量聚合，本步把这个信号放到用户实际收到的通知卡片里，减少“为什么推给我”的黑箱感。
- 展示位置选择聊天通知卡片，而不是浏览器 toast：toast 仍保持短文本，聊天卡片能承载更稳定的 badge、复盘数和比例。
- 只显示聚合标签，不显示历史明细。用户看到的是 `表现好 / 需谨慎 / 观察中 / 待复盘`，以及复盘数、好评率和误报率。

## 已完成

- `warframe_agent/web/static/js/app.js`
  - 新增 `getProactivePushQualitySource(...)`，兼容真实 WebSocket payload 中的 `data.push_quality_*` 字段。
  - 新增 `hasProactivePushQualityData(...)`、`formatPushQualityRate(...)`、`getProactivePushQualityBadge(...)` 和 `renderProactivePushQualityBadge(...)`。
  - 在 `handleNotificationMessage(data)` 的 `proactive_push` 分支里，把质量 badge 追加到同一条 agent message，再继续渲染交易计划。
  - 将 `renderProactivePushQualityBadge` 挂到 `window`，便于前端契约测试。

- `tests/test_web_ui_playwright.py`
  - 扩展 `test_websocket_proactive_push_renders_actionable_trade_plan`，模拟真实嵌套 `data.push_quality_*` payload。
  - 断言聊天区显示 `表现好`、`复盘 5`、`好评率 80%`、`误报率 20%`。
  - 断言顶层 `profile_url`、`market_url`、`whisper` 中的 `QualityLeak` 和 `/w QualityLeak` 不会泄漏进聊天文本。
  - 新增静态契约测试，确认质量 badge helper 与 `window.renderProactivePushQualityBadge` 存在。

## 行为边界

- 本步不改变主动推送排序、冷却去重、机会扫描、交易计划生成或任何写入行为。
- badge 只消费 `push_quality_score`、`push_quality_reviewed_count`、`push_quality_good_rate`、`push_quality_false_positive_rate`。
- 不展示 raw metadata、raw orders、玩家名、profile URL、market URL、`/w`、whisper、token 或 raw chat。
- `待复盘` 表示样本还没被用户确认，不代表坏质量。

## 准备继续学习的清单

- 可以继续做 `pending_count`/低复盘样本的确认式复盘入口，但必须由用户确认后写入。
- 可以在 Web 面板中增加 source/strategy 对比排序，帮助用户发现哪个策略更可靠。
- 可以把质量 badge 的负向样本加入更多 UI 测试，覆盖 `需谨慎` 和 `待复盘` 的视觉状态。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_app_static_contracts_include_proactive_push_quality_badge --basetemp .pytest-tmp -p no:cacheprovider
# RED: 1 failed
# GREEN: 1 passed

.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_websocket_proactive_push_renders_actionable_trade_plan --basetemp .pytest-tmp -p no:cacheprovider
# 普通沙箱：Web server did not become ready
# 非沙箱：1 passed
```
