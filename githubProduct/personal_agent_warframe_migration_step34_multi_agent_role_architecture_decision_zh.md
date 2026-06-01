# Step 34：多 Agent 角色架构决策

生成日期：2026-05-27

## 路线归属

来源项目：LangManus / OpenManus / Suna。

借鉴点：coordinator、planner、supervisor、researcher、browser、reporter、sandbox runtime、planning flow、tool-calling loop。

Warframe 映射：`ChatAgent`、`ToolRouter`、`AgentPlanSnapshot`、Scout 扫描、机会复盘、个人记忆、`ModelOrchestrator`、三个云端 Scout 模型。

安全边界：本轮只做架构决策和文档迁移，不新增执行器，不接管主链路，不启用 Browser/GUI 自动化，不增加外部写入；未来任何角色化执行必须复用确认式写入、runtime safety policy、`tool_context.py` 脱敏和 `ModelOrchestrator` 路由。

验证方式：对照 LangManus、OpenManus、Suna 和本项目现有模型/工具路由，输出角色边界表；确认文档和 `md/rebuilt` 同步。

## 结论

当前不引入完整 LangManus / Suna 式多 Agent 产品架构；保留 `ChatAgent + ToolRouter + ModelOrchestrator` 的单 Agent 主链路。

推荐路线是：

1. 保持 `ChatAgent` 作为唯一用户入口。
2. 把 Planner 做成内部受限计划器，只产出目标、步骤、工具、完成标准和验证说明，不直接写入。
3. 把 Reviewer / Verifier 做成轻量复核层，用于计划、推送、写入确认、长期记忆摘要和交易建议的安全检查。
4. 暂不引入 Browser Agent、Coder Agent、通用 Supervisor、Suna 式 sandbox worker 或任意触发器平台。
5. 三个云端 AI 继续作为任务化模型角色使用，统一经过 `ModelOrchestrator` / `llm.py`，不得由未来角色绕过路由层直接调用。

## 角色边界表

| 候选角色 | 来源项目 | Warframe 映射 | 决策 | 允许输入 | 禁止动作 | 验证路径 |
| --- | --- | --- | --- | --- | --- | --- |
| Coordinator | LangManus | `_classify_chat_mode(...)`、确定性意图优先级 | 暂不单独拆分 | 用户消息、已有聊天模式分类 | 新增一层 LLM 分流、覆盖确定性交易意图 | `warframe_agent/chat.py`、`tests/test_chat.py` |
| Planner | LangManus / OpenManus | `plan` 工具、`ExecutionPlan`、`AgentPlanSnapshot` | 建议后续拆成内部 Planner | 安全摘要、白名单工具列表、用户目标、完成标准 | 直接写入记忆、直接订阅提醒、直接发送推送、调用未候选工具 | `warframe_agent/tool_router.py`、`tests/test_plan.py` |
| Supervisor | LangManus / Suna | 当前无独立产品角色 | 暂不引入完整 Supervisor | Planner 结果、工具执行摘要 | 自主选择高风险角色、循环调度 worker、绕过用户确认 | 暂以文档约束，未来先做 Reviewer |
| Researcher | LangManus | warframe.market、事件、本地导出数据、B 站本地推荐 | 暂不独立拆分 | 只读工具结果、已缓存数据 | 实时网页搜索替代权威 API、把未验证网页内容写入长期记忆 | `warframe_agent/market.py`、`warframe_agent/events.py` |
| Browser | LangManus / OpenManus | 当前 Playwright 主要用于测试 | 暂不引入 Browser Agent | 未来只读网页任务设计 | 登录、下单、私信、付款、删除、访问私网、自动表单提交 | 当前无产品入口；仅保留测试用 Playwright |
| Coder | LangManus / Suna | 无产品内通用代码执行角色 | 不引入通用 Coder | 无 | shell、任意 Python、文件编辑、数据库迁移、外部命令 | 安全策略继续默认禁用 shell / 通用文件写入 |
| Reporter | LangManus | 最终中文回答、Web 质量摘要、复盘总结 | 可借鉴为 Response Composer，不必独立 Agent | 工具安全摘要、聚合数值、来源和时间 | 编造实时价格、隐藏关键来源、输出 raw metadata | `tool_context.py`、`tests/test_chat.py` |
| Reviewer / Verifier | Suna worker 验收思想 | 写入确认、推送质量、长期记忆摘要、计划执行结果 | 建议作为下一个可实现角色 | Planner 输出、执行摘要、敏感字段扫描结果 | 代替用户确认、直接改写计划为高风险动作 | 未来可新增只读校验 helper 和测试 |
| Model Router | 本项目现有架构 | `ModelOrchestrator`、`llm.py`、`SCOUT_MODELS` | 保留为唯一模型路由层 | task、messages、model、routing、复杂度 | 各角色绕过 `ModelOrchestrator` 直接读 `.env` 或直接调用云端 | `tests/test_model_orchestrator.py`、`tests/test_scout.py` |

## 三个云端 AI 对架构的影响

本项目已经有任务化云端模型角色，但它们不是要复制成独立多 Agent：

| 任务 | 默认模型 | 当前入口 | 决策 |
| --- | --- | --- | --- |
| Mod/赋能倒卖预筛 | `kimi-k2.6` | `config.SCOUT_MODELS["mod_flipper"]`、`scout_mod_candidates(...)` | 保留为 Scout 模型角色 |
| Prime 套装套利预筛 | `glm-5.1` | `config.SCOUT_MODELS["set_profit"]`、`scout_set_candidates(...)` | 保留为 Scout 模型角色 |
| 投资顾问预筛 / 默认复杂云端分析 | `gpt-5.5` | `config.SCOUT_MODELS["investment"]`、`CLOUD_MODEL`、`ModelOrchestrator` | 保留为云端复杂分析角色 |

云端调用统一使用 OpenAI-compatible `CLOUD_API_BASE` 和 `CLOUD_API_KEY`。API Key 只允许来自环境变量；文档和日志不得回显真实值。普通 ChatAgent 的云端/本地选择由 `ModelOrchestrator` 的 `MODEL_ROUTING`、任务名、复杂度阈值和是否存在 `CLOUD_API_KEY` 决定；ReAct 工具路由默认仍走本地 `qwen3:8b`。

因此未来若引入 Planner / Reviewer，它们也只能提交 `ModelRequest` 给 `ModelOrchestrator`，不能各自读取 `.env`、拼 Authorization header 或绕过 `llm.py`。

## 为什么不复制完整多 Agent

LangManus 的 coordinator / planner / supervisor / researcher / coder / browser / reporter 适合深度研究和报告型工作流；Suna 的 sandbox runtime 和 worker 适合 24/7 通用工作平台。Warframe Agent 的核心任务不同：交易、价格、活动、提醒、复盘和个人偏好都更依赖确定性 API、受限工具和安全确认。

完整多 Agent 在本项目里的主要代价是：

- 简单查价、提醒、收藏会变慢。
- LLM 分流层可能覆盖现有确定性规则。
- Browser / Coder / sandbox worker 会扩大权限面。
- 多模型互评会增加成本，并可能产生“模型互相说服”的错误闭环。
- 计划持久化、worker 队列和恢复机制会把当前桌面/本地项目变成重型平台。

## 可借鉴但暂缓的能力

- LangManus 的 planner prompt 中“browser 慢且贵、reporter 只能最后使用一次”的约束值得保留。
- OpenManus 的 `PlanningFlow`、step status、blocked reason 和 max steps 适合用于增强现有 `AgentPlanSnapshot`。
- Suna 的 runtime health 分层可用于后续扩展 `/api/runtime/status`，区分 Agent、scheduler、push、DB、market API 和 Web。
- Suna 的 trigger 思想可用于抽象价格提醒、裂缝提醒和主动推送，但不能开放任意 command/webhook/action dispatcher。

## 安全默认值

- 保留单 Agent 主入口，不新增无人值守写入角色。
- Planner 只能产出计划草案和验证条件。
- Reviewer 只能标记风险、缺口和是否需要用户确认。
- 所有写入继续走现有确认式链路，例如目标、复盘、裂缝提醒、收藏、偏好。
- 所有模型输入只使用 `tool_context.py` 和业务 formatter 允许的安全摘要。
- 云端模型调用必须经过 `ModelOrchestrator` / `llm.py`。
- Browser、Coder、通用 shell、任意文件写入、私网访问和自动下单继续默认不可用。

## 后续推荐

下一步若继续实现代码，最小安全方向不是“上多 Agent”，而是：

1. 给现有 `AgentPlanSnapshot` 增加更明确的 `verification_note` 或 `blocked_reason`。
2. 增加只读 Reviewer / Verifier helper，检查计划是否包含高风险工具、敏感字段或缺少用户确认。
3. 在 Web runtime panel 展示 Reviewer 的只读摘要。

如果继续学习而不写代码，下一条路线建议转向“长期运行和运维控制面”，来源项目为 CowAgent / Suna / OpenClaw。

## 本轮验证

本轮只读审计和文档迁移，没有运行外部项目、没有安装依赖、没有新增业务代码。外部参考项目和本项目证据来自：

- `githubProduct/langmanus/src/graph/nodes.py`
- `githubProduct/langmanus/src/prompts/planner.md`
- `githubProduct/OpenManus/app/flow/planning.py`
- `githubProduct/OpenManus/app/agent/toolcall.py`
- `githubProduct/suna/README.md`
- `warframe_agent/tool_router.py`
- `warframe_agent/model_orchestrator.py`
- `warframe_agent/llm.py`
- `warframe_agent/scout.py`
- `warframe_agent/config.py`
