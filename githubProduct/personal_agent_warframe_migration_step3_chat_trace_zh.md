# Personal Agent 学习迁移 Step 3：ChatAgent Trace 接入

日期：2026-05-26

## 本步目标

把 Step 2 的 `AgentTrace` 以只读旁路形式接到 `ChatAgent`：

- `ChatAgent` 每次运行 ReAct 循环后保存 `last_agent_trace`。
- 不改变 `_try_react_loop(...)` 的返回值。
- 不把 trace、耗时、参数摘要或敏感参数写入用户回答。
- 不改变既有 `tool_execution_metadata` 和 conversation log 记录路径。

## 已落地内容

- `ChatAgent.__init__`
  - 新增 `self.last_agent_trace = None`。
- `ChatAgent._try_react_loop(...)`
  - 创建 `AgentTrace()`。
  - 调用 `react_loop(..., trace=trace)`。
  - 异常路径也保留本次 trace 对象，方便排查 `model_error` 或工具异常前已记录的步骤。

## 测试记录

新增测试：

- `test_chat_agent_react_loop_saves_last_agent_trace_without_leaking`

验证命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_router.py -k "last_agent_trace" -q
& .\.venv\Scripts\python.exe -m pytest tests\test_router.py tests\test_plan.py tests\test_tool_router.py -q
```

结果：

- ChatAgent trace 新增测试：1 passed, 27 deselected。
- Router / plan / tool-router 相关测试：68 passed。
- 仍有 `.pytest_cache` 缓存目录写入 warning，不影响测试结论。

## 下一步清单

1. 给 Web 状态页增加只读展示：最后一次 ReAct 终止原因、迭代次数、工具步骤。
2. 只展示脱敏摘要，不展示 `raw_arguments`，除非 `raw_arguments_safe=True` 且只在本地调试面板显示。
3. 保持 conversation log 继续走 `tool_execution_metadata`，不要直接持久化完整 trace。
