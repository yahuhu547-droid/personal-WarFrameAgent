# Personal Agent 学习迁移 Step 4: Runtime Agent Trace 面板

日期: 2026-05-26

## 已落地内容

- `/api/runtime/status` 增加 `agent_trace` 安全快照，用来查看最近一次 ReAct 循环是否执行、执行了几轮、调用了哪些工具。
- Web 运行状态详情面板增加 `Agent Trace` summary card 和步骤列表，复用现有 runtime/trading-memory 样式。
- 快照不返回 `final_answer`、`raw_arguments`、完整 `result_summary` 或工具 error 正文。
- 文本清洗覆盖敏感 key、Bearer token、带协议/不带协议的 Warframe Market profile URL、整行 `/w` 私聊片段。

## 可学习点

- 诊断面板只暴露“形状”和“计数”，不暴露原文，是个人 Agent 做可观测性的第一层安全边界。
- `has_result` 和 `result_chars` 比直接显示工具结果更适合运行状态页。
- `error_present` 比 `error_summary` 更安全；详细错误可以留给本地日志或受控调试入口。
- 前端只渲染白名单字段，不消费 mock 中故意放入的 `raw_arguments/result_summary/final_answer`。

## 本轮验证

- 已完成: `node --check warframe_agent/web/static/js/app.js`
- 已完成: Python AST 只读解析 `warframe_agent/web/app.py`、`tests/test_web_api.py`、`tests/test_web_ui_playwright.py`
- 已确认阻塞: 普通沙箱下 SQLite WAL 会报 `sqlite3.OperationalError: unable to open database file`
- 未完成: `pytest tests/test_web_api.py -k "runtime_status" -q`
- 未完成: `pytest tests/test_web_ui_playwright.py -k "runtime_status or agent_trace" -q`

## 下一步

- 等 Codex 桌面可再次批准提权后，补跑后端 runtime status 测试和 Playwright runtime panel 测试。
- 若测试通过，再推进 Step 5: 把 trace 诊断和任务级 AgentRun/GoalRun 视图关联，但暂不持久化完整 trace。
