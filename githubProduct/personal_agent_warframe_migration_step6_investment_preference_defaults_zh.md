# Personal Agent 学习迁移 Step 6: 投资顾问默认读取个人偏好

日期: 2026-05-26

## 借鉴点

个人 Agent 的工具默认行为应该来自用户画像，而不是长期固定在通用参数上。本步采纳 Harvey 子代理建议：把投资工具缺省预算和最低 ROI 接入 `TradingPreferences`，让 `/pref budget` 和 `/pref min_roi` 真正影响默认投资扫描。

## 已落地内容

- `warframe_agent/investment.py` 新增 `resolve_investment_preference_defaults(...)`。
- `ChatAgent._tool_investment_advisor(...)` 在缺少 `budget` 或 `min_roi` 参数时读取：
  - `memory.preferences.budget_max`
  - `memory.preferences.min_roi_pct`
- Web `/api/investment` 将 `budget` 和 `min_roi_pct` 改为可省略参数；省略或传空字符串时使用个人偏好，显式传参仍然优先。
- Web 投资顾问默认入口不再强行发送 `budget=500&min_roi_pct=10`，只发送 `limit=30`；用户在预算输入框点击扫描时才显式覆盖预算，汇总区缺省时显示“偏好预算”而不是假定 500p。

## 安全边界

- 本步只改变工具参数默认值，不改变交易计划展示层。
- 模型上下文仍只接收投资结果摘要，不接收玩家名、profile 链接、market URL、`/w` 私聊命令或 raw orders。
- 显式用户输入优先，避免个人偏好覆盖用户本次明确指定的预算或 ROI。
- 显式 `0` 会被保留为空预算/空 ROI 边界值；空字符串才视为缺省。

## 本轮验证

- 已通过: `pytest tests/test_investment.py -k "resolve_investment_preference_defaults" -q`
- 已通过: `pytest tests/test_chat_memory_commands.py -k "investment_tool_uses_preference_defaults or investment_tool_treats_blank_args or scan_tools_pass_personal_profile" -q`
- 已通过: `pytest tests/test_web_api.py -k "investment_api_uses_preference_defaults or investment_api_http_query_omitted_and_empty_use_preference_defaults or investment_api_http_query_preserves_explicit_zero" -q`
- 已通过: `node --check warframe_agent/web/static/js/sidebar.js`
- 已通过: Python AST 只读解析 `warframe_agent/investment.py`、`warframe_agent/chat.py`、`warframe_agent/web/app.py`、`tests/test_investment.py`、`tests/test_chat_memory_commands.py`、`tests/test_web_api.py`
- 说明: 普通沙箱运行 Web API pytest 时可能在导入 Web app 阶段触发 SQLite WAL 的 `sqlite3.OperationalError: unable to open database file`；同一组 Web API 回归已在沙箱外可写环境中通过。

## 下一步建议

1. 推进 Ohm 子代理建议的安全开关面板：shell/file/cron/web 私网默认关闭或只读。
2. 推进 OpenManus 风格的可更新 `AgentPlan/AgentPlanStep`，但只做只读计划视图，不改主链路。
3. 推进机会复盘闭环：把 OP ID 的 outcome 写回个人评分，让偏好从“静态设置”逐渐变成“结果驱动”。
