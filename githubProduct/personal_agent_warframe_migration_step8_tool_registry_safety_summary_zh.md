# Personal Agent 学习迁移 Step 8: ToolRegistry 安全统计摘要

日期: 2026-05-26

## 借鉴点

个人 Agent / 插件型项目通常需要一张“能力清单”，但直接暴露工具详情会把 prompt、参数名、handler 或上下文带到运行态页面。本步借鉴插件能力 inventory 的思路，只迁移聚合统计：工具总数、schema 暴露数量、副作用工具数量，以及 `skill`、`safety_level`、`context_policy` 分布。

## 已落地内容

- `warframe_agent/safety_policy.py` 新增 `summarize_tool_registry_safety(...)`。
- `build_runtime_safety_policy(...)` 新增 `tool_registry` 聚合摘要。
- `/api/runtime/status` 将 `chat_agent.tool_registry` 传入安全策略构建器。
- Web 运行态详情面板新增 Tool Registry 汇总卡片和“工具安全分布”区块。

## 安全边界

- 只返回聚合计数，不返回单个工具名、description、parameters、handler、raw args、ToolResult、model_context 或 message_context。
- 即使工具参数里未来出现 `api_key`、`token` 等敏感参数名，也不会进入 `safety_policy.tool_registry`。
- 本步不新增任何工具执行能力，也不改变 `candidate_names()` 的副作用工具过滤策略。

## 本轮验证

- 已红绿验证: `pytest tests/test_tool_registry.py -k "tool_registry_safety_summary" -q`
- 已通过: `pytest tests/test_tool_registry.py -k "tool_registry_safety_summary or runtime_safety_policy_embeds_tool_registry_summary" -q`
- 已通过: `node --check warframe_agent/web/static/js/app.js`
- 已通过: Python AST 只读解析 `warframe_agent/safety_policy.py`、`warframe_agent/web/app.py`、`tests/test_tool_registry.py`、`tests/test_web_api.py`
- 未重跑: `pytest tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q`。沙箱外运行申请被当前 Codex 用量限制拒绝；普通沙箱此前会在 Web app 导入阶段触发 SQLite WAL 的 `sqlite3.OperationalError: unable to open database file`。

## 下一步建议

1. 后续可把 ToolRegistry 安全分布纳入 Playwright 运行态面板测试。
2. 再推进机会复盘闭环：把 OP ID 的真实 outcome 反馈给个人评分。
3. 如果要做安全开关页面，先做只读预览和确认流，不要直接接执行权限。
