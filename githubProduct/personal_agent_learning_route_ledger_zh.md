# 个人 Agent 学习路线账本

生成日期：2026-05-27

## 路线结论

**2026-05-31 当前权威状态**：旧个人 Agent 学习借鉴路线已经完成并终止于 Step 51；Step 52 是终止条件和新阶段入口规则，Step 53 是实现不足复核和历史文案防误读标注。下方 2026-05-27 的“剩余缺口 / 下一步”内容保留为历史审计记录，不再表示当前待办队列。

本账本用于上下文压缩后恢复路线，不代替具体 Step 文档。当前结论是：个人 Agent 学习路线没有断，但后半段从“继续横向学习外部个人 Agent 项目”弯向了“在 Warframe Agent 内连续落地功能”，尤其 Step 28-33 集中在 Scout 推送质量闭环。

本轮修复的目标是把外部项目、已学证据、已迁移能力、剩余缺口和下一步任务重新放到同一个控制面里。后续每个学习借鉴任务都必须先写明：

`来源项目 / 借鉴点 / Warframe 映射 / 安全边界 / 验证方式`

## 项目库存

| 项目 | 本地目录 | 当前状态 | 已学习证据 | 已迁移证据 | 剩余缺口 |
| --- | --- | --- | --- | --- | --- |
| CowAgent | `githubProduct/CowAgent` | 已下载，已研读 | `personal_agent_learning_run_report_zh.md`、`personal_agent_projects_study_notes.md` | 间接映射到 runtime safety policy、ToolRegistry、安全默认策略 | 多渠道入口、scheduler、skills、MCP 热加载尚未产品化 |
| OpenManus | `githubProduct/OpenManus` | 已下载，已建 `.venv-py312`，导入烟测通过 | `personal_agent_learning_execution_status_zh.md`、`personal_agent_learning_run_report_zh.md` | Step 1-5、Step 12-14 的 ToolRegistry、Trace、AgentRun、AgentPlan | 未跑真实 `main.py`；缺真实 LLM key 或本地模型；Browser Agent 仍未作为用户功能开放 |
| LangManus | `githubProduct/langmanus` | 已下载，已研读 | `personal_agent_learning_run_report_zh.md`、`personal_agent_projects_study_notes.md` | 仅作为多 Agent 角色架构参考，尚未专项迁移 | 需要决策是否引入 coordinator/planner/supervisor/reporter |
| OpenHuman | `githubProduct/OpenHuman` | 已下载，已研读 | `personal_agent_learning_run_report_zh.md`、`personal_agent_projects_study_notes.md` | 间接映射到个人画像、conversation log safe vault、记忆召回 | Markdown/Obsidian 式可检查知识库和个人数据连接器尚未实现 |
| EchoBot | `githubProduct/EchoBot` | 已下载，已研读 | `personal_agent_learning_run_report_zh.md`、`personal_agent_projects_study_notes.md` | 间接映射到 chat mode layering 和确认式写入 | Decision/Roleplay/Agent 三层、语音、Live2D、陪伴回复与后台任务分离尚未迁移 |
| Open-AutoGLM | `githubProduct/Open-AutoGLM` | 已下载，暂缓运行 | `personal_agent_learning_run_report_zh.md`、`personal_agent_projects_study_notes.md` | 暂无专项迁移 | 需要真实设备、ADB/HDC、VLM 或模型服务；Warframe Agent 还没有 GUI/手机动作闭环 |
| OpenClaw | `githubProduct/OpenClaw` | 已下载，已研读 | `personal_agent_learning_run_report_zh.md`、`personal_agent_projects_study_notes.md` | 间接映射到 runtime control、安全策略、未来技能/插件边界 | Gateway、channels、extensions、plugins、voice、canvas 尚未成为本项目产品层 |
| Suna / Kortix | `githubProduct/suna` | 已下载，暂缓运行 | `personal_agent_learning_run_report_zh.md`、`personal_agent_projects_study_notes.md` | 仅作为长期运行和 sandbox runtime 参考 | 持久沙盒电脑、24/7 triggers、服务恢复、部署运维入口尚未实现 |

## 原始主题覆盖

| 原始学习主题 | 当前覆盖 | 代表成果 | 后续动作 |
| --- | --- | --- | --- |
| 个人助手产品形态 | 部分覆盖 | Chat UI、Web 面板、自然语言确认、复盘入口 | 继续评估多渠道入口和陪伴体验是否值得进入 Warframe Agent |
| Agent Harness 架构 | 覆盖较多 | Agent Trace、AgentRun、AgentPlan、ToolRegistry、安全策略 | 下一步做多 Agent 角色架构决策，而不是继续堆 UI 微功能 |
| 记忆和知识库 | 覆盖较多 | 个人画像、长期偏好、交易复盘、安全 conversation log、推送质量反馈 | 后续可做 Markdown/Obsidian 式可检查知识库 |
| 多 Agent 协作 | 部分覆盖 | 开发过程中使用子代理；产品内有 AgentPlan 快照 | 需要明确是否引入 LangManus 式 coordinator/planner/supervisor |
| 浏览器、手机和 GUI 自动化 | 覆盖较少 | Playwright 主要用于 Web UI 验证 | 暂不启用 GUI 自动执行；先做安全边界和价值判断 |
| 语音和陪伴式体验 | 已覆盖安全边界 | Step 39 已新增 text-only 体验策略、语音/Live2D/后台监听禁用边界和游戏同伴术语区分 | 如要真实接入语音，需要另开权限、录音和确认链路设计 |
| 部署和长期运行 | 部分覆盖 | runtime status、scheduler 可见性、安全策略 | 后续学习 CowAgent/Suna/OpenClaw 的 service health、恢复和运维入口 |

## 已完成迁移地图

| Step 范围 | 已迁移能力 | 主要来源倾向 | 状态 |
| --- | --- | --- | --- |
| Step 1-5 | ToolRegistry、Trace、AgentRun 生命周期 | OpenManus、CowAgent | 已落地 |
| Step 6-11 | 个人偏好、机会复盘、个人评分 | OpenHuman、CowAgent | 已落地 |
| Step 12-14 | AgentPlan 快照、Web runtime panel、验证闭环 | OpenManus、LangManus | 已落地，但还不是多角色产品架构 |
| Step 15-18 | 交易入口优先级、conversation log safe vault、Scout 推送质量、聊天模式分层 | EchoBot、OpenHuman、Warframe 市场参考项目 | 已落地 |
| Step 19-27 | 自然语言 planning、目标、价格提醒、收藏、偏好、目标状态、复盘、裂缝提醒确认 | CowAgent、EchoBot、OpenManus | 已落地 |
| Step 28-33 | 推送质量优先级、Web badge、通知 badge、复盘提醒、排序、摘要标签 | 个人 Agent 反馈闭环 + Warframe 市场实践 | 已落地，但连续聚焦较窄 |

## 历史剩余学习队列与当前状态

说明：以下队列是 2026-05-27 路线账本修复时的剩余主题。到 Step 39 为止，主线学习队列已基本覆盖；到 Step 51 为止，非语音学习借鉴路线已完成并验收；到 Step 52 / Step 53 为止，已补齐终止条件和实现不足复核。下列条目仅保留用于追溯来源，不再表示必须按顺序继续执行。

1. **多 Agent 角色架构决策**
   - 来源项目：LangManus / OpenManus / Suna
   - 借鉴点：coordinator、planner、supervisor、researcher、browser、reporter 的职责拆分
   - Warframe 映射：`ChatAgent`、`ToolRouter`、`AgentPlanSnapshot`、Scout 扫描、复盘/记忆链路
   - 安全边界：只读审计，不新增执行器，不启用浏览器/GUI 自动化，不增加外部写入
   - 验证方式：输出角色边界表，判断“保持单 Agent / 可拆 Planner / 可拆 Reviewer / 暂不引入 Browser”

2. **长期运行和运维控制面**
   - 来源项目：CowAgent / Suna / OpenClaw
   - 借鉴点：service health、scheduler、triggers、恢复、长期 workspace
   - Warframe 映射：runtime status、scheduler jobs、后台任务、WxPusher/飞书状态
   - 安全边界：只做状态和控制面设计，写入和外部推送继续走确认/配置开关
   - 验证方式：新增或更新运维设计文档，再决定是否进入代码

3. **语音和陪伴式体验评估**
   - 来源项目：EchoBot / OpenHuman / OpenClaw
   - 借鉴点：persona response、voice、Live2D、fast reply vs slow task
   - Warframe 映射：聊天模式分层、用户偏好、后台任务提醒
   - 安全边界：Step 39 已落地为 text-only 策略快照；不下载大模型，不接平台 token，不启用真实语音服务
   - 验证方式：已通过 companion 分类器和 runtime safety policy 目标测试；Web API 目标测试仍需可写环境补跑

4. **Browser / GUI Agent 安全边界评估**
   - 来源项目：OpenManus / Open-AutoGLM
   - 借鉴点：浏览器状态回灌、VLM 屏幕理解、ADB/HDC 动作、人类接管
   - Warframe 映射：可能用于网页市场检查、攻略页阅读或本地 UI 辅助
   - 安全边界：默认只读；登录、支付、删除、私信、下单等动作必须人类确认
   - 验证方式：只写风险矩阵和最小只读 demo 设计

5. **可检查知识库和记忆 vault**
   - 来源项目：OpenHuman / CowAgent
   - 借鉴点：Markdown vault、memory tree、SQLite metadata、向量/关键词混合检索
   - Warframe 映射：交易知识、个人偏好、复盘总结、攻略笔记
   - 安全边界：长期记忆只保存摘要，不保存玩家名、profile、`/w`、token 或 raw orders
   - 验证方式：先做数据结构和迁移计划，再写测试

## 下一任务建议

历史建议曾是：

**LangManus / OpenManus / Suna 多 Agent 角色架构决策**

目标不是立刻实现多 Agent，而是回答 Warframe Agent 是否真的需要显式多角色。如果需要，先确定哪些角色只做只读计划/复盘，哪些角色绝不能直接写入；如果不需要，也要记录“单 Agent + 工具路由更稳”的原因，避免之后反复回到同一个岔路口。

该建议已由 Step 34-35 覆盖。当前下一阶段建议见文末 Step 40。

## 压缩后恢复规则

上下文压缩后，先读本文件，再读 `md/rebuilt/10-learning-route-audit.md`。不要直接从 Step 33 后继续微调 Scout UI，除非用户明确指定。

恢复时只需要确认三件事：

1. 当前用户最新指令是否覆盖本账本。
2. 下一个任务是否属于“剩余学习队列”之一。
3. 是否写明 `来源项目 / 借鉴点 / Warframe 映射 / 安全边界 / 验证方式`。

## 2026-05-27 Step 34：多 Agent 角色架构决策

决策文档：`githubProduct/personal_agent_warframe_migration_step34_multi_agent_role_architecture_decision_zh.md`。

结论：当前不引入完整 LangManus / Suna 式多 Agent 产品架构；保留 `ChatAgent + ToolRouter + ModelOrchestrator` 的单 Agent 主链路。后续如果实现代码，优先做内部受限 Planner 和只读 Reviewer / Verifier，不引入 Browser Agent、Coder Agent、通用 Supervisor、Suna sandbox worker 或任意触发器平台。

用户补充的三个云端 AI 已纳入边界：`kimi-k2.6` 负责 Mod/赋能 Scout 预筛，`glm-5.1` 负责 Prime 套装套利预筛，`gpt-5.5` 负责投资顾问预筛和默认复杂云端分析。它们是任务化模型角色，不是独立多 Agent；任何未来角色都必须通过 `ModelOrchestrator` / `llm.py` 调用云端模型，不得直接读取 `.env` 或拼接 API header。

下一条学习路线可从剩余队列里选择：长期运行和运维控制面、语音和陪伴式体验、Browser / GUI Agent 安全边界、可检查知识库和记忆 vault。若要继续代码实现，建议先做“计划 verification note / blocked reason”和只读 Reviewer helper。

## 2026-05-27 Step 35：AgentPlan 只读 Reviewer / Verifier 摘要

执行文档：`githubProduct/personal_agent_warframe_migration_step35_plan_reviewer_verifier_zh.md`。
借鉴来源：LangManus / OpenManus / Suna。借鉴点是 planner/reviewer/verification summary，而不是完整多 Agent runtime。

已落地能力：
- `AgentPlanSnapshot` 增加 `verification_note`、`blocked_reason` 和只读 `review`。
- `AgentPlanStep` 增加步骤级 `verification_note` 和 `blocked_reason`。
- `review_execution_plan(...)` 会检查未知工具、未暴露工具、副作用工具、非只读 `safety_level`、递归敏感参数 key 和缺少 purpose 的计划步骤。
- `/api/runtime/status` 和 Runtime Agent Plan 面板只展示安全摘要，不展示 raw arguments、result summary、final answer、model context、profile、`/w` 或 token。

验证结果：
- 计划 review / trace 快照 / blocked plan 软拦截目标测试：`10 passed, 43 deselected`。
- Web API runtime snapshot 单测在普通沙箱触发既有 SQLite WAL 文件权限问题，提权重跑通过：`1 passed, 69 deselected`。
- Playwright runtime 面板单测在普通沙箱 uvicorn 未就绪，提权重跑通过：`1 passed`。

当前路线状态：多 Agent 角色架构学习已经从 Step 34 的决策文档推进到 Step 35 的最小代码落地。仍然不引入 Browser Agent、Coder Agent、通用 Supervisor 或 Suna sandbox worker。blocked plan 现在会在执行前软拦截，不调用 executor；后续如果继续此方向，应先设计“软拦截 -> 用户确认 -> 受控执行”的流程；否则建议回到剩余队列中的长期运行/运维控制面、可检查知识库与记忆 vault、Browser/GUI 安全边界。

## 2026-05-28 Step 36：长期运行与运维健康摘要

执行文档：`githubProduct/personal_agent_warframe_migration_step36_ops_health_summary_zh.md`。来源项目：CowAgent / Suna / OpenClaw。借鉴点是 service health、scheduler trigger visibility、后台任务退化原因摘要和长期运行可观测性。

已落地能力：
- `/api/runtime/status` 新增只读 `ops_health` 聚合，覆盖 scheduler、background_tasks、Feishu、WxPusher 和 daily_report。
- `ops_health.reasons` 只返回短 reason code，例如 `scheduler_stopped`、`scheduler_job_failed`、`background_task_error`、`feishu_not_running`。
- Runtime 面板新增 `Ops Health` 摘要卡和只读组件详情。

安全边界：本步没有新增 scheduler 控制端点，没有新增 start/stop/retry 按钮，没有引入 Browser / GUI 自动化、shell 或云端模型调用。`ops_health` 不暴露单个 job id、task id、错误摘要、raw result、profile URL、`/w`、token、Push token、UID、Feishu app_secret 或 chat_id。

验证结果：API 红测先失败于缺少 `ops_health`，UI 红测先失败于缺少 `Ops Health`；实现后 `tests/test_web_api.py -k "ops_health or runtime_status_endpoint"` 为 `2 passed, 69 deselected`，`test_runtime_panel_renders_jobs_tasks_and_safe_state` 为 `1 passed`，静态契约为 `1 passed`，AST / JS 语法 / `git diff --check` 均通过。普通沙箱仍可能遇到既有 SQLite WAL / uvicorn 可写环境限制，Web API 和 Playwright 目标测试需在项目可写环境中补跑。

当前路线状态：Step 36 回到了此前路线审计指出的“长期运行和运维控制面”剩余队列，路线没有继续偏向 Scout UI 微调。后续更适合继续“可检查知识库与记忆 vault”、Browser/GUI 安全边界或语音陪伴式体验评估；若回到 Step 35 分支，则应先做用户确认后的受控执行链路。

## 2026-05-28 Step 37：可检查 Memory Vault 索引

执行文档：`githubProduct/personal_agent_warframe_migration_step37_memory_vault_index_zh.md`。来源项目：OpenHuman / CowAgent。借鉴点是可检查个人记忆、memory tree/source index 和安全摘要化知识沉淀。

已落地能力：
- 新增 `warframe_agent/memory_vault.py`，把 `user_query`、`market_snapshot`、`recommendation`、`push_history`、`opportunity_outcome` 和 `conversation_log` 转换为安全 `MemoryVaultEntry`。
- 新增 `GET /api/memory/vault`，返回 `generated_at`、`total`、`source_counts`、`entries` 和 `markdown_preview`。
- Markdown preview 只展示来源、物品、标题和 allowlist facts，便于后续人工审查和跨会话恢复。

安全边界：本步只做只读聚合，不引入向量库、不调用云端模型、不导出原始聊天全文、不新增写入链路。Vault 不暴露 raw user message、assistant reply、raw tool arguments/result、玩家名、profile URL、`/w`、token、secret、Authorization、cookie、app_secret 或 chat_id。

验证结果：单元红测先失败于缺少 `memory_vault` 模块，API 红测在可写运行环境中先失败于 `404 != 200`；实现后 `tests/test_memory_vault.py` 为 `3 passed`，`tests/test_memory_recall.py` 为 `5 passed`，`tests/test_web_api.py -k "memory_vault or memory_recall_api_returns_safe_trace"` 为 `2 passed, 70 deselected`。

当前路线状态：Step 37 已覆盖剩余学习队列中的“可检查知识库与记忆 vault”。后续更适合继续 Browser / GUI Agent 安全边界评估、语音和陪伴式体验评估，或回到 Step 35 分支设计用户确认后的受控执行链路。

## 2026-05-28 Step 38：Browser / GUI Agent 安全边界

执行文档：`githubProduct/personal_agent_warframe_migration_step38_browser_gui_safety_boundary_zh.md`。来源项目：OpenManus / Open-AutoGLM。借鉴点是浏览器状态回灌、GUI 动作空间、人类接管和禁止动作边界。

已落地能力：
- 新增 `warframe_agent/browser_gui_safety.py`，提供 `classify_browser_gui_action(...)` 和 `build_browser_gui_safety_policy()`。
- `/api/runtime/status.safety_policy` 新增只读 `browser_gui_policy` 和 `browser_gui_automation` capability。
- 行为分级为 `allow_read_only`、`requires_human_confirmation` 和 `blocked`。

安全边界：本步不新增 Browser Agent，不新增 Playwright / ADB / HDC 执行器，不把 Browser/GUI 注册成 exposed tool，不改 `ChatAgent` 主链路。公共页面读取是未来候选；点击、输入、下载、上传、剪贴板写入必须人工确认；登录、支付、删除、私信、下单、凭据输入、任意脚本和私网目标默认 blocked。

验证结果：单元红测先失败于缺少 `browser_gui_safety` 模块；runtime policy 红测先失败于缺少 `browser_gui_policy`；Web API 红测在可写运行环境中先失败于缺少 `browser_gui_automation`。实现后 `tests/test_browser_gui_safety.py` 为 `5 passed`，`tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `1 passed, 33 deselected`，`tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"` 为 `1 passed, 71 deselected`。

当前路线状态：Step 38 已覆盖 Browser / GUI Agent 安全边界评估。剩余学习队列主要是语音和陪伴式体验评估；若回到 Step 35 分支，则应继续设计用户确认后的受控执行链路。

## 2026-05-28 Step 39：语音和陪伴式体验安全边界

执行文档：`githubProduct/personal_agent_warframe_migration_step39_companion_experience_boundary_zh.md`。来源项目：EchoBot / OpenHuman / OpenClaw。借鉴点是 persona response、voice、Live2D、fast reply vs slow task 的边界拆分。

已落地能力：
- 新增 `warframe_agent/companion_experience.py`，提供 `classify_companion_experience_request(...)` 和 `build_companion_experience_policy()`。
- `/api/runtime/status.safety_policy` 新增只读 `companion_experience_policy` 和 `voice_companion_experience` capability。
- 行为分级为 `allow_text_only`、`blocked_unavailable_runtime`、`requires_existing_confirmation_flow`、`blocked_sensitive_action` 和 `route_general_chat`。

安全边界：本步不新增语音服务、TTS/STT、麦克风、录音、后台监听、Live2D、平台 token、前端按钮、ToolRegistry 工具、后台 worker 或模型下载。文本陪伴留在普通聊天路径；陪伴式后台任务只能复用既有确认式提醒和任务；私聊、下单、交易动作继续 blocked；Warframe 游戏内同伴/宠物/库娃/库狛/守护按普通游戏建议处理。

验证结果：单元红测先失败于缺少 `companion_experience` 模块；runtime policy 红测先失败于缺少 `companion_experience_policy`。实现后 `tests/test_companion_experience.py` 为 `6 passed`，`tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `1 passed, 33 deselected`。Web API 目标测试在普通沙箱仍受既有 SQLite WAL 权限限制，提权重跑因本地 Codex 登录 token 失效未能执行，需要在可写运行环境中补跑。

当前路线状态：Step 39 已覆盖剩余学习队列中的语音和陪伴式体验评估。主线学习队列已基本完成；若继续学习借鉴，建议下一步做总账本复盘，或回到 Step 35 分支设计“软拦截 -> 用户确认 -> 受控执行”的确认链路。

## 2026-05-29 Step 40：个人 Agent 学习阶段总复盘

执行文档：`githubProduct/personal_agent_warframe_migration_step40_learning_phase_review_zh.md`。本步不是新增业务能力，而是收束 Step 34-39 的学习路线，明确已覆盖主题、验证债务和下一阶段候选分支。

阶段结论：
- 主线学习队列已基本覆盖：多 Agent 架构决策、只读 Reviewer / Verifier、长期运行健康摘要、可检查 Memory Vault、Browser/GUI 安全边界、语音/陪伴体验安全边界均已形成文档或最小代码落地。
- 仍未产品化的方向包括多渠道 Gateway、skills / plugin 生态、真实语音、真实 Browser/GUI 自动执行、服务恢复和任意触发器平台。
- Step 39 Web API 目标测试仍是验证债务：普通沙箱受 SQLite WAL 权限限制，2026-05-29 可写环境补跑请求被用户中断；因此 Step 39 在 `AGENTS.md` 中继续保持 90%。

下一阶段候选分支：
1. **受控执行确认链路**：回到 Step 35 分支，设计并实现 blocked plan 的“软拦截 -> 用户确认 -> 受控执行”最小闭环。
2. **Step 39 Web API 可写环境补跑**：在可写运行环境补跑 `runtime_status_includes_read_only_safety_policy`，仅用于验证收尾。
3. **多渠道 / Gateway 边界评估**：评估 Web、飞书、WxPusher、未来桌面入口是否需要统一 Gateway。
4. **skills / plugin 生态边界评估**：判断是否需要项目内技能注册、启停和安全摘要。
5. **高权限能力专项设计**：真实语音、Browser/GUI 或服务恢复都必须先写权限、确认、可中断和不落盘 raw data 的设计。

安全边界：不推送 GitHub，不下载新项目或模型，不新增 shell、Browser/GUI、语音、任意 scheduler 或平台私信 executor；所有云端模型继续通过 `ModelOrchestrator` / `llm.py` 调用；长期记忆和 runtime 摘要继续禁止 raw chat、玩家名、profile、`/w`、token 和 raw orders。
## 2026-05-29 Step 41：受控执行确认链路

执行文档：`githubProduct/personal_agent_warframe_migration_step41_controlled_plan_confirmation_zh.md`。

路线归属：这是 Step 35 `AgentPlan` 只读 Reviewer / Verifier 的后续分支，来源仍是 LangManus / OpenManus / Suna 的 planner-reviewer-verifier 思路，但只吸收“执行前审查与确认”的安全形态，不引入完整多 Agent runtime。

已落地能力：
- `build_plan_confirmation_request(...)` 只为 `missing_verification` 的只读计划生成确认请求。
- `react_loop(..., plan_confirmation_token=...)` 会在确认码匹配当前 plan 指纹后重新 review，再受控执行。
- `unknown_tool`、`non_exposed_tool`、`side_effect_tool`、`sensitive_arguments` 不可确认执行。

安全边界：本步不新增 Web UI、pending plan 持久化、Browser/GUI/shell/scheduler executor，也不放开私信、下单、登录、支付、删除、凭据输入或 `set_alert` 等副作用动作。确认码不暴露 raw args；敏感参数计划不会生成确认码。

验证摘要：红测先失败于缺少 `build_plan_confirmation_request`；实现后 `tests/test_plan.py -k "plan_confirmation or confirmed_missing_verification"` 为 `6 passed, 17 deselected`。后续若要进入真实用户聊天闭环，应单独设计 ChatAgent / Web API 的 pending confirmation 状态，而不是直接持久化 raw plan。

## 2026-05-30 Step 42：ChatAgent 计划确认闭环

执行文档：`githubProduct/personal_agent_warframe_migration_step42_chat_plan_confirmation_zh.md`。

路线归属：这是 Step 41 的产品层闭环补齐，来源仍是 LangManus / OpenManus / Suna 的 planner-reviewer-user-confirmation 思路。用户已明确暂时不考虑语音对话服务和真实语音，因此本步完全避开 TTS/STT、麦克风、录音、Live2D 和常驻陪伴。

已落地能力：
- 新增 `PendingAgentPlanConfirmation`，只保存原始消息、候选工具名、阻断原因和确认码，不保存 raw plan。
- `ChatAgent.answer(...)` 和 `answer_stream(...)` 支持“确认执行 / 取消执行”。
- 确认执行时重新调用原始消息，并由 `ToolRouter` 继续做 plan 指纹匹配和 relaxed review。
- 副作用、敏感参数、未知工具和未暴露工具不会进入待确认状态。

验证摘要：红测先失败于 ChatAgent 暴露底层确认码且没有 pending 状态；实现后 `tests/test_chat.py -k "agent_plan_confirmation"` 为 `5 passed, 69 deselected`。补充联跑 `tests/test_chat.py tests/test_plan.py -k "agent_plan_confirmation or plan_confirmation or confirmed_missing_verification"` 为 `11 passed, 86 deselected`；`warframe_agent/chat.py` 和 `warframe_agent/tool_router.py` AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

下一阶段候选分支：优先在非语音范围内继续多渠道 Gateway 边界评估或 skills / plugin 生态边界评估；真实 Browser/GUI 自动化、服务恢复和任意触发器平台仍需先做权限、确认、可中断和审计设计。

## 2026-05-30 Step 43：多渠道 Gateway 边界评估

执行文档：`githubProduct/personal_agent_warframe_migration_step43_gateway_boundary_zh.md`。

路线归属：来源于 CowAgent / Suna / OpenClaw 的多入口个人 Agent 思路，但本项目先只迁移“入口信任边界和动作权限矩阵”，不新增任何真实平台连接器。

已落地能力：

- 新增 `warframe_agent.gateway_policy`，提供 `classify_gateway_request(...)` 和 `build_gateway_policy()`。
- `build_runtime_safety_policy(...)` 新增 `gateway_policy` 和 `capabilities.multi_channel_gateway`。
- Web chat、WebSocket chat、local CLI 视为交互式用户输入；Feishu bot 视为配置过的外部入口，必须复用已有确认流程；WxPusher / Feishu push 只作为出站通知。
- Bilibili 评论、匿名 webhook、GitHub issue、卖家 / 买家私信，以及任意工具执行、shell、浏览器控制、文件写入、下单和私信动作默认 blocked。

安全边界：本步不新增平台账号、Webhook handler、社交抓取、Browser/GUI executor、scheduler executor、语音入口或后台监听；policy 输出不包含 raw payload、handler、token、secret、app_secret、chat_id、玩家名、profile URL 或 `/w`。

验证摘要：红测先失败于缺少 `warframe_agent.gateway_policy`；实现后 `tests/test_gateway_policy.py tests/test_tool_registry.py -k "gateway_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `6 passed, 33 deselected`；可写环境补跑 `tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"` 为 `1 passed, 71 deselected`。

下一阶段候选分支：继续非语音方向，优先做 skills / plugin 生态边界评估，或把 Gateway policy 以安全字段展示到 Runtime 面板；真实 Browser/GUI 自动化、服务恢复和任意触发器平台仍需单独设计。

## 2026-05-30 Step 44：Skills / Plugin 生态边界评估

执行文档：`githubProduct/personal_agent_warframe_migration_step44_plugin_policy_zh.md`。

路线归属：来源于 OpenManus / Suna / OpenClaw / Codex skills 的可扩展能力生态，但本项目先只迁移“插件能力进入运行时前必须被审查、确认和权限约束”的边界。

已落地能力：

- 新增 `warframe_agent.plugin_policy`，提供 `classify_plugin_capability(...)` 和 `build_plugin_policy()`。
- `build_runtime_safety_policy(...)` 新增 `plugin_policy` 和 `capabilities.skills_plugin_ecosystem`。
- local/system/project skills 只作为 guidance；personal/local/Codex plugin 已安装后仍需 review；connector 必须显式启用并确认。
- shell、文件写入、浏览器控制、scheduler 创建、凭据访问、社交发帖和交易动作默认 blocked。

安全边界：本步不安装插件、不请求 plugin install、不新增 connector、不读取账号 token、不新增平台 API；policy 不返回 raw manifest、handler、params、token、secret、api_key、account_id、真实本机路径或用户账号标识。

验证摘要：红测先失败于缺少 `warframe_agent.plugin_policy`；实现后 `tests/test_plugin_policy.py tests/test_tool_registry.py -k "plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `7 passed, 33 deselected`；可写环境补跑 `tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"` 为 `1 passed, 71 deselected`。

下一阶段候选分支：把 `gateway_policy` 和 `plugin_policy` 以只读安全字段展示到 Runtime 面板；随后执行非语音学习路线最终闭环审计。

## 2026-05-30 Step 45：Runtime Policy 可见性

执行文档：`githubProduct/personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md`。

路线归属：来源于 Suna / OpenManus / OpenClaw 的运行态控制面透明化思路，本项目只迁移“展示能力边界”，不新增控制按钮或 executor。

已落地能力：

- Runtime 摘要卡新增 `Gateway Policy` 和 `Plugin Policy`。
- Runtime 详情新增 `renderRuntimeGatewayPolicy(...)` 和 `renderRuntimePluginPolicy(...)`，只显示安全聚合字段。
- 前端敏感字段过滤补充 `account_id`、`api_key`、`handler`、`params`、`manifest`、`payload` 等插件 / Gateway 相关 key。

安全边界：本步只做只读展示，不新增按钮、开关、安装入口、账号输入、Webhook、connector、Browser/GUI executor、scheduler executor 或真实外部入口。

验证摘要：`node --check warframe_agent\web\static\js\app.js` 退出码 0；静态契约测试 `test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections` 为 `1 passed`。Playwright 目标测试 `test_runtime_panel_renders_jobs_tasks_and_safe_state` 普通沙箱中 uvicorn 未就绪；2026-05-30 可写运行环境补跑通过，结果为 `1 passed`。

下一阶段候选分支：执行非语音学习路线最终闭环审计；Step 45 Playwright 补跑已在 Step 47 收束。

## 2026-05-30 Step 46：非语音学习借鉴路线闭环审计

执行文档：`githubProduct/personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md`。

结论：按用户最新指令暂不考虑语音对话服务和真实语音时，个人 Agent 学习借鉴路线已经完成代码与文档闭环。CowAgent、OpenManus、LangManus、OpenHuman、EchoBot、Open-AutoGLM、OpenClaw、Suna / Kortix 的主要非语音借鉴主题都已映射到本项目。

已覆盖主题：单 Agent 主链路、多 Agent planner/reviewer/verifier 思路、受控计划确认、长期运行健康、可检查记忆、Browser/GUI 安全边界、text-only 陪伴边界、多渠道 Gateway 边界、skills/plugin 生态边界和 Runtime 可见性。

最终补跑：Step 45 Playwright 目标测试 `test_runtime_panel_renders_jobs_tasks_and_safe_state` 已在 2026-05-30 可写运行环境补跑通过。普通沙箱仍会出现 uvicorn 未就绪，因此该类浏览器目标测试后续仍应在可写运行环境补跑。

最终验证：Gateway / Plugin / runtime policy 联跑 `12 passed, 33 deselected`；Runtime 静态契约测试 `1 passed`；Runtime 完整 Playwright 浏览器目标测试 `1 passed`；`warframe_agent/gateway_policy.py`、`warframe_agent/plugin_policy.py`、`warframe_agent/safety_policy.py`、`warframe_agent/chat.py`、`warframe_agent/tool_router.py` AST OK；`node --check warframe_agent\web\static\js\app.js` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

## 2026-05-30 Step 47：最终 Playwright 验证债务收束

执行计划：`docs/superpowers/plans/2026-05-30-learning-borrowing-final-playwright-closure.md`。

执行结果：普通沙箱运行 `tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state` 仍失败于 `RuntimeError: Web server did not become ready`；按既有环境约束在可写运行环境补跑后通过，结果为 `1 passed`。

路线结论：在暂不考虑语音对话服务和真实语音的前提下，GitHub 项目个人 Agent 非语音学习借鉴计划已经完成。后续若继续学习，应作为新阶段另开，不再沿旧队列机械推进。

下一阶段：不再机械继续旧学习队列。若未来继续，应另开新阶段，分别设计真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装和 connector 启用。

## 2026-05-30 Step 48：未来高权限能力准入策略

执行计划：`docs/superpowers/plans/2026-05-30-future-capability-admission-policy.md`。
执行文档：`githubProduct/personal_agent_warframe_migration_step48_future_capability_admission_zh.md`。

路线归属：Step 48 是 Step 46 / Step 47 之后的新阶段安全准入层，不属于旧非语音学习借鉴队列的未完成项。旧的 GitHub 项目个人 Agent 非语音学习借鉴计划仍按 Step 47 结论保持完成。

已落地能力：

- 新增 `warframe_agent.future_capability_policy`，提供 `classify_future_capability(...)` 和 `build_future_capability_policy()`。
- `build_runtime_safety_policy(...)` 新增只读 `future_capability_policy`，以及策略可见但运行时未启用的 `capabilities.future_capability_admission`。
- 新增 / 扩展测试覆盖 Browser/GUI executor、真实语音冻结、匿名 webhook / 评论 / 私信入口、shell / 通用文件写入 / 凭据访问 / 交易动作、设计文档只读允许、敏感 capability 名脱敏和 runtime safety 嵌入。

安全边界：本步不注册 ToolRegistry 工具，不新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端按钮、后台 worker 或真实语音能力。真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续按用户当前指令冻结。

验证摘要：初始红测按预期失败于缺少 `warframe_agent.future_capability_policy`；初始绿测为 `7 passed, 33 deselected`。子代理复核后补充敏感 capability 名和 `future_capability_admission.enabled` 语义红测，先复现 `2 failed`；修复后目标绿测为 `9 passed, 33 deselected`。最终 policy 联跑为 `20 passed, 33 deselected`；Web API 普通沙箱复现 SQLite WAL 数据库文件无法打开，可写运行环境补跑 `1 passed, 71 deselected`；AST OK。

下一阶段：后续若要真正推进高权限能力，应分别另开权限、确认、可中断执行、审计和回滚设计；不能由 Step 48 的只读 policy 直接放开运行时入口。

## 2026-05-31 Step 49：Future Capability Runtime 可见性补齐

执行计划：`docs/superpowers/plans/2026-05-31-future-capability-runtime-visibility.md`。
执行文档：`githubProduct/personal_agent_warframe_migration_step49_future_capability_runtime_visibility_zh.md`。

路线归属：Step 49 是 Step 48 新阶段安全准入层的 Runtime 可见性改善，不属于旧非语音学习借鉴队列的补课。旧的 GitHub 项目个人 Agent 非语音学习借鉴计划仍按 Step 47 结论保持完成。

已落地能力：

- `warframe_agent/web/static/js/app.js` 新增 `Future Capability Policy` 摘要卡、详情区和 `renderRuntimeFutureCapabilityPolicy(...)` / `renderRuntimeFutureCapabilityPolicyItem(...)`。
- Runtime 面板展示 `future_capability_admission`、`design_required_before_runtime`、`runtime_enablement_allowed=false`、`requires_new_stage_design` 和 `blocked_uncontrolled_runtime`。
- 前端敏感过滤补充 `credential`、`user_id`、`private_network_url`、`local_path`、`raw_plan`、`raw_config`、`connector_token` 等未来高权限场景相关泄露形态。
- `tests/test_web_ui_playwright.py` 和 `tests/test_web_api.py` 已补充 Future Capability Runtime 可见性契约。

安全边界：本步只做只读 Runtime 展示，不新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端控制按钮、后台 worker 或真实语音能力。`future_capability_admission.enabled=False` 保持不变；真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续冻结。

验证摘要：前端静态红测先失败于缺少 `renderRuntimeFutureCapabilityPolicy`；实现后 `node --check warframe_agent\web\static\js\app.js` 退出码 0，静态契约 `1 passed`。完整 Runtime 面板 Playwright 普通沙箱失败于 uvicorn 未就绪，可写环境补跑 `1 passed`；Web API 普通沙箱失败于 SQLite WAL 数据库文件无法打开，可写环境补跑 `1 passed, 71 deselected`；最终 policy 联跑 `20 passed, 33 deselected`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

下一阶段：高权限能力若要从“可见策略”进入真实运行时，仍必须另开设计并补齐权限、确认、可中断执行、审计和回滚策略。

## 2026-05-31 Step 50：学习借鉴与改善完成 Runtime 快照

执行计划：`docs/superpowers/plans/2026-05-31-learning-completion-runtime-snapshot.md`。
执行文档：`githubProduct/personal_agent_warframe_migration_step50_learning_completion_runtime_snapshot_zh.md`。

路线归属：Step 50 是“学习借鉴与改善完成快照”，不是旧队列补课，也不是高权限能力启用。旧的 GitHub 项目个人 Agent 非语音学习借鉴计划仍按 Step 47 结论保持完成；Step 48 / Step 49 是完成后的新阶段安全准入和 Runtime 可见性改善。

已落地能力：

- 新增 `warframe_agent.learning_completion`，提供 `build_learning_completion_snapshot()`。
- `/api/runtime/status` 新增 top-level `learning_completion`。
- Runtime 面板新增 `Learning Completion` 摘要卡和详情区，展示完成状态、已完成步骤、改善步骤和仍需另开设计的高权限候选能力。
- 新增 `tests/test_learning_completion.py`，并扩展 Web API / Runtime 面板契约测试。

安全边界：本步只新增只读完成状态快照，不注册 ToolRegistry 工具，不新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端控制按钮、后台 worker 或真实语音能力。`future_capability_admission.enabled=False` 保持不变；真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续冻结。

验证摘要：单元红测先失败于缺少 `warframe_agent.learning_completion`；实现后 `tests/test_learning_completion.py` 为 `3 passed`，`node --check warframe_agent\web\static\js\app.js` 退出码 0，Runtime 静态契约 `1 passed`。Web API 普通沙箱失败于 SQLite WAL 数据库文件无法打开，可写环境补跑 `2 passed, 70 deselected`；完整 Runtime 面板 Playwright 普通沙箱失败于 uvicorn 未就绪，可写环境补跑 `1 passed`。最终复核中 policy / gateway / plugin / runtime safety 联跑 `23 passed, 33 deselected`；Runtime 静态契约复核 `1 passed`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

最终结论：到 Step 50 为止，“GitHub 个人 Agent 非语音学习借鉴计划完成 + Step 48/49 改善完成”已经具备代码、API、Runtime UI 和文档四层闭环。后续若要推进真实高权限能力，必须另开权限、确认、可中断执行、审计和回滚设计。

## 2026-05-31 Step 51：学习借鉴完成验收清单快照

执行计划：`docs/superpowers/plans/2026-05-31-learning-completion-acceptance-snapshot.md`。
执行文档：`githubProduct/personal_agent_warframe_migration_step51_learning_completion_acceptance_snapshot_zh.md`。

路线归属：Step 51 是完成态验收防漂移改善，不是旧学习借鉴队列补课，也不是高权限运行时能力启用。Step 50 仍是最新闭环步骤；Step 51 只记录机器可读验收依据。

已落地能力：

- `learning_completion` 新增 `acceptance_status=accepted`。
- `acceptance_snapshot` 新增 `latest_closure_step=step50_learning_completion_runtime_snapshot`、`acceptance_record_step=step51_learning_completion_acceptance_snapshot`、`all_items_passed=true` 和安全聚合 checklist。
- `completed_steps` 补入 `step50_learning_completion_runtime_snapshot`，避免未来上下文只看到 Step49 而误解 Step50 未完成。
- Runtime 面板展示 acceptance 状态、closure step、acceptance record 和验收 checklist。

安全边界：本步只扩展只读完成验收快照，不新增端点、按钮、开关、ToolRegistry 工具、Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、后台 worker 或真实语音能力。`future_capability_admission.enabled=False` 保持不变；真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续冻结。

验证摘要：单元红测先失败于 `KeyError: 'acceptance_status'` 和 `KeyError: 'acceptance_snapshot'`；实现后 `tests/test_learning_completion.py` 为 `5 passed`，`node --check` 退出码 0，Runtime 静态契约 `1 passed`。Web API 普通沙箱失败于 SQLite WAL 数据库文件无法打开，可写环境补跑 `2 passed, 70 deselected`；完整 Runtime 面板 Playwright 普通沙箱失败于 uvicorn 未就绪，可写环境补跑 `1 passed`。最终 policy / gateway / plugin / runtime safety 联跑 `25 passed, 33 deselected`；Runtime 静态契约复核 `1 passed`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

最终结论：到 Step 51 为止，“GitHub 个人 Agent 非语音学习借鉴计划完成 + Step 48/49 改善完成 + Step 50 完成态验收”已具备代码、API、Runtime UI、测试和文档闭环。后续不再机械执行旧队列；真实高权限能力必须另开设计。

## 2026-05-31 Step 52：学习路线终止条件与新阶段入口收束

执行计划：`docs/superpowers/plans/2026-05-31-learning-route-termination-and-new-stage-entry.md`。
执行文档：`githubProduct/personal_agent_warframe_migration_step52_learning_route_termination_zh.md`。

路线归属：Step 52 是文档级终止条件收束，不是旧学习借鉴队列补课，也不是运行时代码改动。Step 50 是最新完成闭环，Step 51 是机器可读验收记录，旧学习借鉴路线终止于 Step 51。

终止条件：

- 旧学习借鉴路线终止于 Step 51。
- 如果用户再次提出“继续下一步规划直到借鉴完成 / 改善完成 / 开始执行”这类同义请求，默认解释为检查完成态并维护终止条件，而不是继续新增 Step53 / Step54 运行时代码。
- 不得从早期“剩余学习队列”重新循环执行已经由 Step 34-51 覆盖的主题。
- `future_capability_admission.enabled=False` 是未来高权限运行时未启用的证据，不是待补实现项。
- Step 39 真实语音继续冻结，不得因“路线完成”反向推进真实语音。

新阶段入口：只有用户明确指定并确认愿意进入真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装、connector 启用、webhook / DM 命令入口等新阶段能力时，才允许另开设计。新阶段必须先写清目标、权限边界、用户确认链路、可中断执行、审计摘要、回滚策略和测试方式。

安全边界：本步不修改运行时代码、API、前端 JS、测试或配置；不新增端点、按钮、开关、ToolRegistry 工具、executor、后台 worker、scheduler、webhook、connector 或插件安装能力；不下载依赖，不上传 GitHub。

验证摘要：使用 `rg` 检查 Step 52、终止条件、新阶段入口、不再机械执行旧队列和 `future_capability_admission.enabled=False` 关键语义；使用 `git diff --check` 检查相关文档格式。

最终结论：到 Step 52 为止，学习借鉴路线不仅完成，而且已经具备防循环终止条件。后续不再机械执行旧队列；真实高权限能力必须作为独立新阶段另开设计。

## 2026-05-31 Step 53：学习路线实现不足复核与历史文案防误读标注

执行计划：`docs/superpowers/plans/2026-05-31-learning-route-implementation-gap-audit.md`。
执行文档：`githubProduct/personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md`。

路线归属：Step 53 是全路线实现不足复核，不是旧学习借鉴队列补课，也不是新运行时代码改动。它响应“如果没有推荐的下一步，就查看整个计划实现有没有不足”的请求。

复核结论：

- 未发现需要新增代码、API、Runtime UI 或测试覆盖的缺口。
- `learning_completion.status=complete`、`acceptance_status=accepted`、`acceptance_snapshot`、`runtime_enablement_changed=false` 和 `future_capability_admission.enabled=False` 仍是当前完成和未启用高权限运行时的关键锚点。
- 早期“剩余队列 / 下一步 / 债务”语句保留为历史记录，但已补充当前权威状态，避免后续上下文压缩后误读为当前待办。

已处理内容：

- `AGENTS.md` 顶部学习路线说明已改为完成态和终止态。
- 本路线账本的历史剩余队列已增加当前权威状态说明。
- `md/rebuilt/09-personal-agent-foundation.md` 和 `md/rebuilt/10-learning-route-audit.md` 顶部已加入历史记录防误读提示。
- Step 53 报告已记录无代码缺口、文档不足、当前权威结论和安全边界。

安全边界：本步不修改运行时代码、API、前端 JS、测试或配置；不新增端点、按钮、开关、ToolRegistry 工具、executor、后台 worker、scheduler、webhook、connector、插件安装或真实语音能力；不下载依赖，不上传 GitHub。

验证摘要：policy / gateway / plugin / future capability / learning completion 联跑 `25 passed, 33 deselected`；Runtime 静态契约 `1 passed`；AST OK；`node --check warframe_agent\web\static\js\app.js` 退出码 0；关键文档语义 `rg` 可检索；`git diff --check` 退出码 0。

最终结论：到 Step 53 为止，学习借鉴路线已完成、验收、具备防循环终止条件，并且历史文案中的主要误读点已被标注。后续不再机械执行旧学习借鉴队列；真实高权限能力必须作为独立新阶段另开设计。
