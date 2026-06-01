# Step 35：AgentPlan 只读 Reviewer / Verifier 摘要

生成日期：2026-05-27

## 来源项目

- LangManus：借鉴 planner / reviewer / supervisor 的职责拆分，但不复制完整多 Agent 架构。
- OpenManus：借鉴计划状态可观测、步骤级 trace 与执行前约束检查。
- Suna / Kortix：借鉴 worker 执行前后的 verification summary，但不引入 sandbox worker、browser worker 或 24/7 trigger 平台。

## 借鉴点

这一步把 Step 34 的架构结论落成最小代码能力：现有 `AgentPlanSnapshot` 增加一个确定性的只读 review 摘要，用来告诉用户和开发者：

- 计划是否只包含已注册、对模型暴露的工具。
- 是否包含副作用工具或非只读 `safety_level`。
- 参数 key 是否带有 token、secret、authorization、cookie 等敏感字段。
- 每个计划步骤是否至少有可读的 purpose，作为最小 verification 说明。

## Warframe 映射

- `warframe_agent/tool_router.py`
  - 新增 `PlanReviewIssue`、`PlanReviewSummary`。
  - 新增 `review_execution_plan(...)`。
  - 在 `_register_trace_plan(...)` 中把 review 结果挂到 `AgentPlanSnapshot`。
  - 每个 `AgentPlanStep` 增加 `verification_note` 和 `blocked_reason`。
- `warframe_agent/web/app.py`
  - `/api/runtime/status` 只序列化安全 review 摘要，不暴露 `issues` 原始列表、raw arguments、result summary 或 final answer。
- `warframe_agent/web/static/js/app.js`
  - Runtime Agent Plan 面板展示 `review_status`、verification note、blocked reason 和敏感参数 issue 计数。

## 安全边界

- 这一步不新增云端模型调用。
- `kimi-k2.6`、`glm-5.1`、`gpt-5.5` 仍然只是任务化云端 AI 角色，未来必须继续通过 `ModelOrchestrator` / `llm.py` 调用。
- Reviewer 是纯函数、只读、确定性逻辑，不读 `.env`，不拼接 API header。
- 当前阶段会在 plan 执行前做软拦截：`review.status == "blocked"` 时不会调用 executor，不会执行任何计划步骤，只返回安全提示并在 trace 中标记 `termination_reason="plan_blocked"`。这一步仍不改变通过审查的计划执行顺序。
- Web API / UI 只暴露摘要字段，不暴露玩家名、profile URL、`/w`、token、Bearer、raw chat、raw arguments、result summary、model context 或 final answer。

## 验证记录

- `.\.venv\Scripts\python.exe -m pytest tests\test_plan.py tests\test_tool_router.py -k "plan_review or agent_plan" -q --basetemp .pytest-tmp -p no:cacheprovider`
  - 结果：`10 passed, 43 deselected`
- 普通沙箱运行 Web API 单测时遇到已知 SQLite WAL / 数据库文件权限问题。
- 提权重跑：
  - `.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_safe_agent_trace_snapshot" -q --basetemp .pytest-tmp -p no:cacheprovider`
  - 结果：`1 passed, 69 deselected`
- 普通沙箱运行 Playwright runtime panel 时 uvicorn 未能就绪，符合既有 Web app SQLite 环境限制。
- 提权重跑：
  - `.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp -p no:cacheprovider`
  - 结果：`1 passed`

## 学习结论

Step 35 已经从“是否引入多 Agent”的架构决策进入了代码执行：先把 LangManus / OpenManus / Suna 中最值得借鉴的 reviewer / verifier 可观测性压缩为现有单 Agent 主链路的一层只读审查，而不是直接引入完整多 Agent runtime。

下一步更适合继续做“长程运行和运维控制面”或“可检查知识库与记忆 vault”的学习任务；如果继续沿 plan reviewer 走，建议设计“软拦截 -> 用户确认 -> 允许受控副作用”的确认流程，而不是直接放开所有被标记 blocked 的计划。
