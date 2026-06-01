# Step 13: AgentPlan Web 运行态面板

## 本步目标

把 Step 12 已经暴露到 `/api/runtime/status.agent_trace.plan` 的安全快照，真正显示到 Web 运行态详情面板中。这样排查个人 Agent 多步工具计划时，可以直接看到计划是否生成、当前状态、步骤数量以及每一步执行状态。

## 借鉴点

- Agent 的内部计划需要可观察，但不应直接暴露完整工具入参、模型最终回答或工具原始结果。
- 运行态面板适合展示短摘要：`plan_status`、`goal_present`、`plan_steps`、步骤工具名、purpose、状态、耗时、`result_present` 和 `error_present`。
- 前端只读取后端已经安全化的字段，保持 API 脱敏边界在后端，UI 不绕过安全快照。
- Playwright fixture 中加入故意嘈杂的 `raw_arguments`、`result_summary`、token、玩家名和 `/w` 文本，用回归测试确保这些字段不会进入 DOM。

## 已落地文件

- `warframe_agent/web/static/js/app.js`
  - Runtime summary grid 新增 `Agent Plan` 卡片。
  - Agent Trace 后新增 `Agent Plan` 详情段落。
  - 新增 `renderRuntimeAgentPlan(...)` 和 `renderRuntimeAgentPlanStep(...)`。
- `tests/test_web_ui_playwright.py`
  - Runtime fixture 增加 `agent_trace.plan`。
  - 断言 `Agent Plan`、`plan_status=completed`、`goal_present=true`、`plan_steps=2`、步骤 purpose、工具名和 `result_present=false` 可见。
  - 继续断言 token、raw arguments、result summary、final answer、`final_answer` 字面字段、玩家名和 `/w` 不可见。

## 安全边界

Web 面板只渲染：

- `present`
- `status`
- `iteration`
- `goal_present`
- 已脱敏的 `goal`
- `step_count`
- `steps[].index`
- `steps[].tool_name`
- `steps[].purpose`
- `steps[].args_summary`
- `steps[].status`
- `steps[].ok`
- `steps[].duration_ms`
- `steps[].result_present`
- `steps[].error_present`

Web 面板不渲染：

- `raw_arguments`
- `result_summary`
- `final_answer`
- profile 链接
- `/w` 私聊命令
- token、chat_id、app_secret 等敏感值

前端还会对运行态 `args_summary` 做二次兜底：敏感键会被跳过，可疑敏感值会显示为 `[REDACTED]`。Agent Trace 的 `termination_reason="final_answer"` 会规范化为 `reason=answered`，并只显示 `answer_present=true/false`。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q
node --check warframe_agent/web/static/js/app.js
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['tests/test_web_ui_playwright.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

本步未安装新包，也未提交或推送 GitHub。
