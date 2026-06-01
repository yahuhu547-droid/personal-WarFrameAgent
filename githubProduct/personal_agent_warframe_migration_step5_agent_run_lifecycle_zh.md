# Personal Agent 学习迁移 Step 5: AgentRun 生命周期状态

日期: 2026-05-26

## 借鉴来源

- OpenManus 的 Agent 运行生命周期思想：一个 AgentRun 应该能表达运行中、结束、错误、终止原因和步数。
- 当前 WarFrameAgent 已经有 `AgentTrace`、`AgentStep`、`ChatAgent.last_agent_trace` 和 Runtime Agent Trace 面板，因此本步只做轻量增量，不引入新的 Agent 继承体系。

## 已落地内容

- `AgentTrace` 新增轻量生命周期字段：
  - `status`
  - `started_at`
  - `ended_at`
  - `max_iterations`
  - `duration_ms`
- `react_loop(...)` 在进入循环前把 trace 标记为 `running`，在所有已知退出路径通过 `_finish_trace(...)` 收口。
- 模型异常会记录 `termination_reason="model_error"` 且 `status="error"`。
- 工具异常会保持原有抛出语义，同时记录 `termination_reason="tool_error"` 且 `status="error"`，避免运行态 UI 长期停在 running。
- `/api/runtime/status` 的 `agent_trace` 安全快照增加生命周期标量字段。
- Web 运行态详情面板显示 `status`、当前轮次/最大轮次、`duration_ms`、开始/结束时间。

## 安全边界

- 仍不返回 `final_answer` 原文。
- 仍不返回 `raw_arguments`。
- 仍不返回完整 `result_summary`、工具输出、模型上下文或工具错误正文。
- `status` 和 `termination_reason` 只使用枚举式短字符串，不承载异常全文。
- `started_at`、`ended_at`、`duration_ms` 和 `max_iterations` 是诊断标量，可以进入 runtime status。
- runtime status 的参数摘要会过滤 `authToken`、`secretToken`、`authorizationHeader`、`cookieValue`、`chatId` 这类驼峰或组合敏感 key。

## 可学习点

- 运行态诊断先做“状态机 + 安全快照”，比复制大型 Agent 框架更适合现有项目。
- 生命周期字段应由 `react_loop` 入口和统一收口函数维护，不能靠构造时间推断。
- 工具异常路径必须显式结束 trace，否则监控 UI 会误判 Agent 仍在运行。
- Web API 继续保持白名单序列化，不能直接返回 `trace.__dict__`。

## 本轮验证

- 已通过: `pytest tests/test_tool_router.py -k "lifecycle" -q`
- 已通过: `python -B -c "... ast.parse(...)"` 只读解析 `warframe_agent/tool_router.py`、`warframe_agent/web/app.py`、`tests/test_tool_router.py`、`tests/test_web_api.py`、`tests/test_web_ui_playwright.py`
- 已通过: `node --check warframe_agent/web/static/js/app.js`
- 未通过: `pytest tests/test_web_api.py -k "agent_trace_snapshot" -q`，导入 Web app 时触发 SQLite WAL 的 `sqlite3.OperationalError: unable to open database file`
- 未通过: `pytest tests/test_web_ui_playwright.py -k "runtime_panel_renders_jobs_tasks_and_safe_state" -q`，测试 fixture 启动 `uvicorn warframe_agent.web.app:app` 后服务未就绪；与 Web app 导入/数据目录限制相关，需要在可写数据目录环境中补跑。

## 下一步建议

1. 把 AgentRun 生命周期状态与后台任务、目标执行任务形成统一只读视图。
2. 再推进 Ohm 子代理建议的安全开关面板：shell/file/cron/web 私网默认关闭或只读。
3. 再推进 Harvey 子代理建议的个性化预算/ROI 默认参数接入，让投资工具默认使用个人偏好。
