# Personal Agent 学习迁移 Step 2：ReAct Trace 可观测性

日期：2026-05-26

## 本步目标

参考 OpenManus 的 `run -> step -> think/act` 可观测思路，先给 WarFrameAgent 现有 `react_loop(...)` 增加旁路 trace：

- 默认不启用，保持 `react_loop(...) -> str | None` 返回契约不变。
- 不把 trace 注入模型消息、用户回答、session history 或 conversation log。
- 只记录工具循环里的结构化事实，便于后续 Web UI 或调试面板查看。

## 子代理审阅

子代理 Ohm 做了只读审阅，建议：

- `AgentTrace` 作为可选参数传入 `react_loop(...)`。
- `AgentStep` 记录 iteration、tool name、参数摘要、raw 参数安全状态、ok/error、duration。
- 敏感参数命中 token / secret / password / api_key / cookie / authorization 时，不保存 raw arguments。
- 不改 `ChatAgent._run_tool_call(...)` 的 `tool_execution_metadata` 路径，避免重复记录。

本步采纳了 router 层设计；`ChatAgent.last_agent_trace` 暂不接入，因为 `chat.py` 当前已有较多未提交改动，本步先保持写入范围小。

## 已落地内容

- 新增 `AgentStep`
  - `iteration`
  - `tool_name`
  - `args_summary`
  - `raw_arguments_safe`
  - `raw_arguments`
  - `ok`
  - `error`
  - `duration_ms`
  - `result_summary`
- 新增 `AgentTrace`
  - `steps`
  - `termination_reason`
  - `iterations`
  - `final_answer`
- `react_loop(..., trace=trace)`
  - final answer 时记录 `termination_reason="final_answer"`。
  - 模型异常时记录 `model_error`。
  - 工具调用解析失败时记录 `tool_call_parse_failed`。
  - 空响应时记录 `empty_response`。
  - 达到最大轮数时记录 `max_iterations`。
- `execute_plan(...)`
  - 增加可选 trace 参数，plan 子步骤也会记录为普通工具 step。

## 测试记录

新增测试：

- `test_react_loop_records_agent_trace_for_tool_call`
- `test_react_loop_trace_records_max_iteration_stop`

验证命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_router.py -k "trace" -q
& .\.venv\Scripts\python.exe -m pytest tests\test_router.py tests\test_plan.py tests\test_tool_router.py -q
```

结果：

- Trace 新增测试：2 passed, 25 deselected。
- Router / plan / tool-router 相关测试：67 passed。
- 仍有 `.pytest_cache` 缓存目录写入 warning，不影响测试结论。

## 下一步清单

1. 等 `chat.py` 当前未提交改动稳定后，把 `AgentTrace` 接进 `ChatAgent.last_agent_trace`。
2. 给 Web 状态页增加只读 trace 快照，优先展示最后一次 ReAct 终止原因和工具步骤。
3. 让 conversation log 继续只保存安全 `tool_execution_metadata`，trace 不直接入日志，避免泄漏和重复。
4. 如果后续需要更完整借鉴 OpenManus，再把 `termination_reason` 和 `AgentStep` 映射到一个独立 `AgentRun` 视图。
