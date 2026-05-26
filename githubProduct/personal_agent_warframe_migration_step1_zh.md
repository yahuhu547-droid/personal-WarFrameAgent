# Personal Agent 学习迁移 Step 1：ToolRegistry 兼容层

日期：2026-05-26

## 本步目标

把 OpenManus 的 `ToolCollection` 学习结果先以低风险方式落到 WarFrameAgent：

- 不重写 `ChatAgent` 主链路。
- 不改变现有工具注册、路由和执行语义。
- 给 `ToolRegistry` 增加 OpenManus 风格的薄兼容入口，方便后续引入 `think / act / run` 循环实验。

## 已落地内容

- `ToolRegistry.to_params(...)`
  - 作为 `list_tool_schemas(...)` 的兼容别名。
  - 对齐 OpenManus `available_tools.to_params()` 的调用习惯。
- `ToolRegistry.get_tool(name)`
  - 作为 `get(name)` 的兼容别名。
  - 方便后续用统一工具集合接口做适配。
- `ToolRegistry.tool_map`
  - 返回只读映射，暴露注册工具表。
  - 避免外部直接修改内部 `_tools`。
- `ToolRegistry.execute(..., tool_input={...})`
  - 保留原有 `execute(name, arguments)` 调用。
  - 新增 OpenManus 风格 `execute(name="...", tool_input={...})` 调用。

## 测试记录

新增测试：

- `test_to_params_exports_openmanus_function_format`
- `test_get_tool_and_tool_map_expose_registered_specs_read_only`
- `test_execute_accepts_openmanus_style_tool_input_keyword`

验证命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "to_params or get_tool or tool_input" -q
& .\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py tests\test_tool_router.py -q
```

结果：

- 新增兼容测试：4 passed, 28 deselected。
- 工具注册与路由相关测试：62 passed。
- 仅有 `.pytest_cache` 缓存目录写入 warning，不影响测试结论。

## 下一步清单

1. 抽一个最小 `AgentStep` / `AgentTrace` 结构，记录工具选择、参数、结果摘要和耗时。
2. 在 `ToolRouter.react_loop(...)` 外层补一个可选 trace，不改变现有输出格式。
3. 参考 OpenManus 的 `max_steps` / `special_tools`，把终止原因结构化，便于 Web UI 展示和排错。
4. 再评估是否需要新增独立 `ReActAgent` 类；目前不急，先让现有链路可观测。
