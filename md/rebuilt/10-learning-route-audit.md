# 10. 个人 Agent 学习路线压缩后审计

生成日期：2026-05-27

> 当前权威状态（2026-05-31）：本文件前半段的“清洁下一步 / 剩余学习队列 / 下一阶段建议”是历史审计记录；当前以 Step 52 / Step 53 为准，旧学习借鉴路线已完成并终止于 Step 51，`learning_completion.status=complete` 与 `acceptance_status=accepted` 是当前完成锚点。

## 最新请求

本轮审计只回答一个问题：经历多次上下文压缩后，从最初“搜索、下载、学习个人 Agent 项目，并把可借鉴点迁移到 Warframe Agent”的路线，到当前 Step 33 为止，路线是否已经弯曲。

## 使用的校准方法

- 以最新用户指令优先：不继续开新功能，先检查路线。
- 以本地文件为证据：对照 `githubProduct` 学习清单、下载摘要、Step 1-33 迁移记录、`docs/superpowers/plans` 和 `md/rebuilt`。
- 不把压缩摘要当作事实本身：只把摘要作为检索线索，再用当前文件系统核验。

## 总结判断

路线有局部弯曲，但没有完全跑偏。

原始目标是学习个人 Agent 项目，包括 CowAgent、OpenManus、LangManus、OpenHuman、EchoBot、Open-AutoGLM、OpenClaw 和 Suna/Kortix，并把个人助手产品形态、Agent Harness、记忆/知识库、多 Agent 协作、浏览器/GUI 自动化、语音陪伴和长期运行部署等能力迁移到本项目。

实际执行到 Step 33 后，路线逐渐从“逐个对比外部项目”转向“在 Warframe Agent 内连续落地个人 Agent 能力”。这条落地线主要覆盖了运行态 trace、AgentPlan、工具安全边界、个人画像、机会复盘、自然语言命令桥接、确认式写入、Scout 推送质量反馈和 Web 透明度。

因此当前状态更像是：学习路线没有断，但学习源项目的显式对照被压缩和连续实现冲淡了；后半段尤其集中在 Scout 推送质量闭环，是一条合理分支，但已经偏离了“继续横向研究个人 Agent 项目”的原始节奏。

## 证据

- `githubProduct/personal_agent_learning_checklist_zh.md` 记录的原始学习对象是 CowAgent、OpenManus、LangManus、OpenHuman、EchoBot、Open-AutoGLM、OpenClaw、Suna/Kortix。
- `githubProduct/download_summary.json` 的更新时间是 2026-05-21，当前仍主要记录 OCR、视频识别、Warframe 市场参考项目，没有同步后来的个人 Agent 项目清单。
- `githubProduct/personal_agent_warframe_migration_step1_zh.md` 到 Step 33 说明学习已经进入本项目迁移阶段。
- `docs/superpowers/plans` 中 2026-05-25 到 2026-05-27 的计划显示，路线从 personal-agent-foundation 逐步进入运行态、自然语言入口和推送质量闭环。
- `md/rebuilt/09-personal-agent-foundation.md` 已把 Step 1-33 串成一条本项目落地记录。

## 已覆盖的原始学习主题

| 原始主题 | 当前覆盖情况 | 说明 |
| --- | --- | --- |
| 个人助手产品形态 | 部分覆盖 | Web 运行态、聊天入口、自然语言确认、复盘入口已经落地，但多渠道入口和陪伴体验还不完整。 |
| Agent Harness 架构 | 覆盖较多 | Agent Trace、AgentRun、AgentPlan、安全策略、ToolRegistry 聚合快照已经形成核心骨架。 |
| 记忆和知识库 | 覆盖较多 | 个人画像、长期偏好、交易复盘、conversation log safe vault、SQLite outcome feedback 已经落地。 |
| 多 Agent 协作 | 部分覆盖 | 使用了子代理协作方式，但项目内部尚未明确 LangManus/OpenManus/Suna 式角色架构是否需要产品化。 |
| 浏览器、手机和 GUI 自动化 | 覆盖较少 | Playwright 主要用于验证 Web UI，还没有迁移 OpenManus/Open-AutoGLM 式 GUI/browser agent 能力。 |
| 语音和陪伴式体验 | 已覆盖安全边界 | Step 39 已把 EchoBot/OpenHuman/OpenClaw 的 voice、Live2D、persona response、后台任务分离收束为 text-only 策略快照。 |
| 部署和长期运行 | 部分覆盖 | runtime status、安全策略、scheduler 状态有进展，但 Suna/CowAgent/OpenClaw 式长期运行运维方案还未独立展开。 |

## 明显弯曲点

1. `download_summary.json` 与 2026-05-25 的个人 Agent 清单不同步。它更像早期视频/OCR/Warframe 参考项目摘要，不再能代表当前个人 Agent 学习路线。
2. Step 28-33 连续聚焦 Scout 推送质量，已经从“个人 Agent 横向学习”转成了“本项目交易推送质量体验打磨”。
3. 很多后续任务是高价值落地，但文档中没有始终保留“来源项目 -> 借鉴点 -> Warframe 映射 -> 安全边界 -> 验证”的固定格式，导致上下文压缩后容易只记得实现任务，不记得学习来源。

## 没有跑偏的部分

- 用户曾明确提出“用户和项目聊天时总不能 `/goal set` 然后就接语句吧”，后续 Step 21-27 把目标、提醒、收藏、偏好、复盘、裂缝提醒逐步做成自然语言和确认式写入，这条路线是直接回应用户关切。
- 推送质量闭环虽然集中，但它属于个人 Agent 的自我反馈和复盘能力，不是无关功能。
- 最近任务持续同步到 `md/rebuilt`，并且没有按旧指令继续推 GitHub，符合后续用户修正。
- 安全边界一直在延续：敏感字段、玩家名、profile、market URL、`/w`、token 和 raw metadata 没有被纳入长期记忆或质量展示。

## 建议的路线修正

后续每个“继续下个学习借鉴任务”都先补一行路线归属：

`来源项目 / 借鉴点 / Warframe 映射 / 安全边界 / 验证方式`

下一阶段建议暂时不要继续细拆 Scout 推送质量 UI，除非用户明确指定。更应该回到尚未覆盖充分的原始学习主题：

1. LangManus / OpenManus / Suna：审查本项目是否需要显式多角色架构，而不是只靠当前单 Agent 加工具。
2. CowAgent / Suna / OpenClaw：补长期运行、服务健康、任务恢复、调度控制和运维入口。
3. EchoBot / OpenHuman / OpenClaw：评估人格回复、语音入口和后台任务分离是否适合 Warframe 助手。
4. OpenManus / Open-AutoGLM：评估浏览器或 GUI 自动化是否应该进入本项目，尤其是安全确认和只读优先边界。
5. 对齐 `download_summary.json`：要么更新为当前个人 Agent 项目下载/学习状态，要么明确标注旧摘要只属于早期视频/OCR/Warframe 参考阶段。

## 清洁下一步

下一次继续执行前，建议先做一个小的“路线账本修复”任务：更新或新增个人 Agent 项目下载/学习状态摘要，把 CowAgent、OpenManus、LangManus、OpenHuman、EchoBot、Open-AutoGLM、OpenClaw、Suna/Kortix 的本地状态、已读内容、已借鉴点和未覆盖点放到同一张表里。这样之后再开子代理并行学习时，路线不会被压缩后的局部功能任务牵着走。

## 2026-05-27 追加：路线账本修复

已按本审计建议补齐路线控制面：`githubProduct/personal_agent_learning_route_ledger_zh.md` 现在统一记录 8 个个人 Agent 项目的本地状态、已学习证据、已迁移能力、剩余缺口和下一步队列；`githubProduct/download_summary.json` 也已补充 `personal_agent_projects` 与 `route_repair`，避免它继续停留在早期 OCR/视频/Warframe 市场参考摘要。

后续继续学习借鉴时，优先执行“LangManus / OpenManus / Suna 多 Agent 角色架构决策”，先判断 Warframe Agent 是否需要显式 coordinator、planner、supervisor、reporter 分层，或者继续保持单 Agent + 工具路由。每个新任务仍需先写明：`来源项目 / 借鉴点 / Warframe 映射 / 安全边界 / 验证方式`。

## 2026-05-27 追加：Step 34 已执行

已执行“LangManus / OpenManus / Suna 多 Agent 角色架构决策”，结果记录在 `githubProduct/personal_agent_warframe_migration_step34_multi_agent_role_architecture_decision_zh.md`。结论是当前不引入完整多 Agent 产品架构，继续保留单 Agent 主链路；下一步若写代码，应优先做内部受限 Planner 和只读 Reviewer / Verifier。

用户补充的三个云端 AI 已纳入决策：`kimi-k2.6`、`glm-5.1`、`gpt-5.5` 作为 Scout / 复杂分析的任务化模型角色保留，所有未来角色都必须通过 `ModelOrchestrator` / `llm.py` 调用云端模型。后续学习路线可继续从“长期运行和运维控制面”“语音和陪伴式体验”“Browser / GUI Agent 安全边界”“可检查知识库和记忆 vault”中选择。

## 2026-05-27 追加：Step 35 已执行

已执行“AgentPlan 只读 Reviewer / Verifier 摘要”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step35_plan_reviewer_verifier_zh.md`。这一步不是继续写计划，而是把 Step 34 的多 Agent 角色架构决策落成最小代码能力：`review_execution_plan(...)`、`AgentPlanSnapshot.review`、步骤级 verification note、Web API 安全序列化和 Runtime Agent Plan 面板展示都已完成。

路线判断：当前路线没有偏离。Step 35 仍然属于 LangManus / OpenManus / Suna 多 Agent 角色架构学习的保守落地，只吸收 planner/reviewer/verification summary 的可观测性，不引入完整多 Agent runtime、Browser Agent、Coder Agent、通用 Supervisor 或 Suna sandbox worker。三个云端 AI 的边界保持不变：`kimi-k2.6`、`glm-5.1`、`gpt-5.5` 继续通过 `ModelOrchestrator` / `llm.py` 作为任务化模型角色使用。

验证情况：计划 review、trace 快照和 blocked plan 执行前软拦截目标测试为 `10 passed, 43 deselected`；Web API 与 Playwright runtime panel 在普通沙箱分别受 SQLite WAL / uvicorn 启动限制，提权重跑后分别为 `1 passed, 69 deselected` 和 `1 passed`。后续若继续此分支，应先设计“软拦截 -> 用户确认 -> 受控执行”的确认链路；否则建议回到剩余学习队列的长期运行/运维控制面或可检查知识库与记忆 vault。

## 2026-05-28 追加：Step 36 已执行

已执行“CowAgent / Suna / OpenClaw 长期运行与运维健康摘要”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step36_ops_health_summary_zh.md`。这一步没有继续 Scout UI 微调，而是回到路线审计建议的剩余学习主题：长期运行、服务健康、scheduler trigger 可见性和后台任务退化原因摘要。

路线判断：当前路线没有偏离。Step 36 把外部个人 Agent 项目的运维可观测性借鉴为 Warframe Agent 的只读 `ops_health`，但没有引入控制面副作用：不新增 scheduler 控制端点，不新增 start / stop / retry 按钮，不启用 shell、Browser / GUI 自动化或云端模型调用。

已落地能力：`/api/runtime/status` 新增 `ops_health` 聚合，Runtime 面板显示 `Ops Health` 摘要卡与组件详情。该摘要只返回 reason code、聚合计数和布尔状态，不返回 job id、task id、错误摘要、raw result、profile URL、`/w`、token、Push token、UID、Feishu app_secret 或 chat_id。

验证情况：API 红测先失败于缺少 `ops_health`，UI 红测先失败于缺少 `Ops Health`；实现后 API 目标测试为 `2 passed, 69 deselected`，Runtime Playwright 目标测试为 `1 passed`，静态契约为 `1 passed`，`warframe_agent/web/app.py` AST OK，`node --check` 退出码 0，`git diff --check` 退出码 0。普通沙箱仍存在既有 SQLite WAL / uvicorn 可写环境限制，相关 Web 测试需要在项目可写运行环境中补跑。

剩余学习队列建议：优先继续“可检查知识库与记忆 vault”；也可以评估 Browser / GUI Agent 安全边界或语音和陪伴式体验。若回到 Step 35 的计划执行分支，应先设计用户确认后的受控执行链路。

## 2026-05-28 追加：Step 37 已执行

已执行“OpenHuman / CowAgent 可检查 Memory Vault 索引”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step37_memory_vault_index_zh.md`。这一步覆盖了此前剩余学习队列中的“可检查知识库与记忆 vault”，没有继续 Scout UI 微调。

路线判断：当前路线没有偏离。Step 37 把外部个人 Agent 项目的可检查记忆思路借鉴为本项目的只读 vault index，而不是复制完整 Obsidian/Markdown vault、向量库或多 Agent 记忆系统。它复用现有 `TradingMemoryDB` 和 `conversation_log` 的安全摘要，只提供可审查的聚合视图。

已落地能力：新增 `warframe_agent/memory_vault.py` 和 `GET /api/memory/vault`。API 返回 `generated_at`、`total`、`source_counts`、`entries` 和 `markdown_preview`，覆盖 `user_query`、`market_snapshot`、`recommendation`、`push_history`、`opportunity_outcome` 与 `conversation_log`。

安全边界：不新增写入链路，不调用云端模型，不读取 `.env`，不导出 raw user message、assistant reply、raw tool arguments/result、玩家名、profile URL、`/w`、whisper、token、secret、Authorization、cookie、app_secret 或 chat_id。

验证情况：单元红测先失败于缺少 `memory_vault` 模块，API 红测在可写运行环境中先失败于 `404 != 200`；实现后 `tests/test_memory_vault.py` 为 `3 passed`，`tests/test_memory_recall.py` 为 `5 passed`，`tests/test_web_api.py -k "memory_vault or memory_recall_api_returns_safe_trace"` 为 `2 passed, 70 deselected`。普通沙箱仍存在既有 SQLite WAL 可写环境限制，Web API 目标测试需在项目可写运行环境中补跑。

剩余学习队列建议：下一步优先评估 Browser / GUI Agent 安全边界或语音和陪伴式体验；若回到 Step 35 计划执行分支，应先设计“软拦截 -> 用户确认 -> 受控执行”的确认链路。

## 2026-05-28 追加：Step 38 已执行

已执行“OpenManus / Open-AutoGLM Browser / GUI Agent 安全边界”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step38_browser_gui_safety_boundary_zh.md`。这一步覆盖了此前剩余学习队列中的 Browser / GUI Agent 安全边界评估。

路线判断：当前路线没有偏离。Step 38 没有把浏览器自动化作为用户功能开放，而是先补动作分级和 runtime 可见性，为未来可能的 Browser/GUI Agent 接入设置前置刹车。

已落地能力：新增 `warframe_agent/browser_gui_safety.py`，提供 `classify_browser_gui_action(...)` 和 `build_browser_gui_safety_policy()`；`/api/runtime/status.safety_policy` 新增 `browser_gui_policy` 和 `browser_gui_automation` capability。

安全边界：不新增 Playwright/ADB/HDC executor，不注册 exposed Browser/GUI tool，不改 `ChatAgent` 主链路，不新增后台 worker 或自动触发器。登录、支付、删除、私信、下单、凭据输入、任意脚本和私网目标默认 blocked；点击、输入、下载、上传和剪贴板写入必须人工确认。

验证情况：`tests/test_browser_gui_safety.py` 为 `5 passed`，`tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `1 passed, 33 deselected`，`tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"` 为 `1 passed, 71 deselected`。普通沙箱仍存在既有 SQLite WAL 可写环境限制，Web API 目标测试需在项目可写运行环境中补跑。

剩余学习队列建议：下一步优先做语音和陪伴式体验评估；若回到 Step 35 计划执行分支，应先设计“软拦截 -> 用户确认 -> 受控执行”的确认链路。

## 2026-05-28 追加：Step 39 已执行

已执行“EchoBot / OpenHuman / OpenClaw 语音和陪伴式体验安全边界”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step39_companion_experience_boundary_zh.md`。这一步覆盖了此前剩余学习队列中的语音和陪伴式体验评估。

路线判断：当前路线没有偏离。Step 39 没有把语音、Live2D 或常驻陪伴作为真实产品功能开放，而是先补 text-only 默认模式和运行态安全快照，为未来可能的语音/陪伴体验接入设置前置边界。

已落地能力：新增 `warframe_agent/companion_experience.py`，提供 `classify_companion_experience_request(...)` 和 `build_companion_experience_policy()`；`/api/runtime/status.safety_policy` 新增 `companion_experience_policy` 和 `voice_companion_experience` capability。

安全边界：不新增 TTS/STT、麦克风、录音、后台监听、Live2D、平台 token、模型下载、前端控制按钮、ToolRegistry 工具或后台 worker。陪伴式后台任务只能复用已有确认式提醒和任务；私聊、下单和交易动作继续 blocked；Warframe 游戏内同伴/宠物/守护按普通游戏建议处理。

验证情况：`tests/test_companion_experience.py` 为 `6 passed`，`tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `1 passed, 33 deselected`。普通沙箱仍存在既有 SQLite WAL 可写环境限制，Web API 目标测试需在可写运行环境中补跑；本次提权重跑因本地 Codex 登录 token 失效未能执行。

剩余学习队列建议：个人 Agent 主线学习队列已基本覆盖。下一步建议做总账本复盘，或回到 Step 35 分支设计“软拦截 -> 用户确认 -> 受控执行”的受控执行链路。

## 2026-05-29 追加：Step 40 已执行

已执行“个人 Agent 学习阶段总复盘”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step40_learning_phase_review_zh.md`。这一步不新增业务代码，而是把 Step 34-39 的学习路线收束为覆盖矩阵、验证残留和下一阶段候选分支。

路线判断：当前路线没有偏离。Step 34-39 已覆盖此前路线修正建议中的主要剩余主题：多 Agent 架构决策和只读 Reviewer、长期运行健康摘要、可检查 Memory Vault、Browser/GUI 安全边界、语音和陪伴体验安全边界。主线学习队列已经基本完成。

仍未产品化的方向包括多渠道 Gateway、skills / plugin 生态、真实语音、真实 Browser/GUI 自动执行、服务恢复和任意触发器平台。这些不再作为“剩余学习队列”机械执行，而是进入“下一阶段候选分支”模式。

验证债务：Step 39 的 `tests/test_companion_experience.py` 和 runtime policy 目标测试已通过；Web API 目标测试仍需可写运行环境补跑。2026-05-29 的可写环境补跑请求被用户中断，因此不把 Step 39 标为 100%，但也不阻塞 Step 40 的文档收束。

下一阶段建议：优先回到 Step 35 分支设计“软拦截 -> 用户确认 -> 受控执行”的受控执行链路；其次在可写运行环境补跑 Step 39 Web API 验证；其余高权限方向需先做权限、确认、可中断和不落盘 raw data 的设计。
## 2026-05-29 追加：Step 41 已执行

已执行“受控执行确认链路”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step41_controlled_plan_confirmation_zh.md`。这一步没有偏离原路线：它是 Step 35 “只读 Reviewer / Verifier”之后自然需要补齐的确认门禁，而不是新增高权限自动化。

路线判断：
- 来源项目仍是 LangManus / OpenManus / Suna 的 planner-reviewer-verifier 思路。
- Warframe 映射是 `ToolRouter` 内部的 plan review 和确认执行门禁。
- 安全边界保持收窄：只有 `missing_verification` 可确认；未知工具、未暴露工具、副作用工具、敏感参数继续硬拦。
- 本步不新增 Web UI、不持久化 raw plan、不新增 Browser/GUI/shell/scheduler executor。

验证摘要：新增测试先红测失败于缺少 `build_plan_confirmation_request`；实现后 `tests/test_plan.py -k "plan_confirmation or confirmed_missing_verification"` 为 `6 passed, 17 deselected`。后续如果继续此分支，应设计 ChatAgent / Web API 层的 pending confirmation 状态，并确保 UI 只消费安全字段。

## 2026-05-30 追加：Step 42 已执行

已执行“ChatAgent 计划确认闭环”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step42_chat_plan_confirmation_zh.md`。这一步继续 Step 41 的受控执行分支，把底层 `plan_confirmation_token` 接到聊天入口，用户只需要回复“确认执行”或“取消执行”，不需要看到或复制确认码。

路线判断：当前路线没有偏离。Step 42 仍来自 LangManus / OpenManus / Suna 的 planner-reviewer-user-confirmation 思路，Warframe 映射是 `ChatAgent + ToolRouter` 的只读计划确认闭环。它没有新增高权限自动化，也没有把被 `side_effect_tool`、`sensitive_arguments`、`unknown_tool` 或 `non_exposed_tool` 阻断的计划放行。

安全边界：`ChatAgent` 只在 `confirmable_reason=missing_verification` 且 trace review 阻断原因一致时保存 pending confirmation；pending 只包含原始用户消息、候选工具名、阻断原因和确认码，不保存 raw plan、raw tool args 或 raw result。确认短语必须是明确的“确认执行 / 执行计划 / 确认计划 / 继续执行 / 确认运行”，普通“确认”不触发计划执行，避免和目标、提醒、复盘等确认入口混淆。

按最新用户指令，后续暂不考虑语音对话服务和真实语音。Step 39 的语音 / 陪伴体验 Web API 补跑保留为冻结遗留验证，不再作为当前优先路线；下一阶段优先继续非语音分支，例如多渠道 Gateway 边界评估、skills / plugin 生态边界评估，或 Web API / Runtime 面板的 pending confirmation 安全展示设计。

验证摘要：`tests/test_chat.py -k "agent_plan_confirmation"` 为 `5 passed, 69 deselected`。最终联跑 Step 41 / Step 42 目标测试 `tests/test_chat.py tests/test_plan.py -k "agent_plan_confirmation or plan_confirmation or confirmed_missing_verification"` 为 `11 passed, 86 deselected`；`warframe_agent/chat.py` 和 `warframe_agent/tool_router.py` AST OK；`git diff --check` 退出码 0，仅提示部分文件下次由 Git 转换 LF/CRLF。

## 2026-05-30 追加：Step 43 已执行

已执行“多渠道 Gateway 边界评估”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step43_gateway_boundary_zh.md`。这一步承接 Step 40 的非语音候选分支，把 CowAgent / Suna / OpenClaw 的多入口个人 Agent 思路收束为本项目的入口信任边界，而不是新增真实平台连接器。

路线判断：当前路线没有偏离。Step 43 明确区分“用户主动交互入口”“配置过的外部入口”“出站通知出口”“公共或匿名入站面”和“高风险动作”。Warframe 映射是 `gateway_policy` 与 runtime safety snapshot，不是开放 webhook、社交评论、私信或任意工具执行。

安全边界：本步不新增平台账号、Webhook handler、社交抓取、Browser/GUI executor、scheduler executor、语音入口或后台监听。policy 不返回 raw payload、handler、token、secret、app_secret、chat_id、玩家名、profile URL 或 `/w`。外部入口即使已配置，也只能复用既有确认式聊天 / 任务链路。

按最新用户指令，语音对话服务和真实语音继续冻结。下一阶段可继续 skills / plugin 生态边界评估，或把 Gateway policy 的安全字段展示到 Runtime 面板；真实 Browser/GUI 自动化、服务恢复和任意触发器平台仍需单独设计。

验证摘要：红测先失败于缺少 `warframe_agent.gateway_policy`；实现后 `tests/test_gateway_policy.py tests/test_tool_registry.py -k "gateway_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `6 passed, 33 deselected`；可写环境补跑 `tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"` 为 `1 passed, 71 deselected`。

## 2026-05-30 追加：Step 44 已执行

已执行“Skills / Plugin 生态边界评估”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step44_plugin_policy_zh.md`。这一步承接 Step 43 的非语音候选分支，把 OpenManus / Suna / OpenClaw / Codex skills 的可扩展能力生态收束为本项目的插件能力审查边界。

路线判断：当前路线没有偏离。Step 44 没有安装插件、启用 connector 或新增平台账号，而是先定义 local skills、personal plugins、account connectors 和高风险 capabilities 的运行时边界。Warframe 映射是 `plugin_policy` 与 runtime safety snapshot，不是开放任意插件执行。

安全边界：本步不安装插件、不请求 plugin install、不新增 connector、不读取账号 token、不新增平台 API。policy 不返回 raw manifest、handler、params、token、secret、api_key、account_id、真实本机路径或用户账号标识。插件能力未来若要进入运行时，必须先映射到 ToolRegistry metadata、AgentPlan review 和用户确认链路。

按最新用户指令，语音对话服务和真实语音继续冻结。下一阶段建议把 `gateway_policy` 和 `plugin_policy` 以只读安全字段展示到 Runtime 面板，然后做非语音学习路线最终闭环审计。

验证摘要：红测先失败于缺少 `warframe_agent.plugin_policy`；实现后 `tests/test_plugin_policy.py tests/test_tool_registry.py -k "plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `7 passed, 33 deselected`；可写环境补跑 `tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"` 为 `1 passed, 71 deselected`。

## 2026-05-30 追加：Step 45 已执行

已执行“Runtime Policy 可见性”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md`。这一步承接 Step 43 / Step 44，把 Gateway / Plugin 两类 policy 的安全字段展示到 Runtime 面板。

路线判断：当前路线没有偏离。Step 45 只是控制面可见性，不新增 Gateway 入口、插件安装、connector、账号配置、Browser/GUI executor、scheduler executor 或真实外部入口。Warframe 映射是“只读运行态透明度”，不是能力开关。

安全边界：Runtime 面板只显示 default、runtime enabled、decision counts、channel / capability、decision、trust boundary 和 reason；前端过滤 `raw_*`、`handler`、`params`、`manifest`、`payload`、`token`、`secret`、`account_id`、`api_key` 等字段。语音对话服务和真实语音继续冻结。

验证摘要：`node --check warframe_agent\web\static\js\app.js` 退出码 0；静态契约测试 `test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections` 为 `1 passed`。Playwright 目标测试 `test_runtime_panel_renders_jobs_tasks_and_safe_state` 的旧 UI 红测已证明缺少 Gateway Policy 展示；实现后普通沙箱 uvicorn 未就绪，2026-05-30 可写运行环境补跑通过，结果为 `1 passed`。

## 2026-05-30 追加：Step 46 已执行

已执行“非语音学习借鉴路线闭环审计”任务，结果记录在 `githubProduct/personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md`。

路线判断：在“暂不考虑语音对话服务和真实语音”的前提下，个人 Agent 学习借鉴路线已经完成代码与文档闭环。CowAgent、OpenManus、LangManus、OpenHuman、EchoBot、Open-AutoGLM、OpenClaw、Suna / Kortix 的主要非语音主题都已有 Warframe 映射：运行态、记忆、计划审查、确认链路、Gateway、Plugin、Browser/GUI 安全边界和 Runtime 可见性。

最终补跑：Step 45 Runtime 面板 Playwright 目标测试 `test_runtime_panel_renders_jobs_tasks_and_safe_state` 已在 2026-05-30 可写运行环境补跑通过，结果为 `1 passed`。普通沙箱仍会出现 uvicorn 未就绪，因此后续同类测试仍需可写运行环境。

最终验证：Gateway / Plugin / runtime policy 联跑 `12 passed, 33 deselected`；Runtime 静态契约测试 `1 passed`；Runtime 完整 Playwright 浏览器目标测试 `1 passed`；AST OK；`node --check warframe_agent\web\static\js\app.js` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

## 2026-05-30 追加：Step 47 已执行

已执行“最终 Playwright 验证债务收束”任务，计划记录在 `docs/superpowers/plans/2026-05-30-learning-borrowing-final-playwright-closure.md`。

路线判断：当前路线没有偏离。Step 47 没有新增功能，只把 Step 45 Runtime 面板完整浏览器目标测试在可写运行环境中补跑通过，并同步状态文档。

结论：在暂不考虑语音对话服务和真实语音的前提下，GitHub 项目个人 Agent 非语音学习借鉴计划已经完成；后续若继续，应作为新阶段另开。

后续路线：不再机械继续旧学习队列。若未来继续，应另开新阶段，分别设计真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装和 connector 启用。

## 2026-05-30 追加：Step 48 已执行

已执行“未来高权限能力准入策略”任务，计划记录在 `docs/superpowers/plans/2026-05-30-future-capability-admission-policy.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step48_future_capability_admission_zh.md`。

路线判断：当前路线没有偏离。Step 48 明确作为新阶段安全准入层，而不是继续旧的 GitHub 项目个人 Agent 非语音学习借鉴队列。旧队列在 Step 47 已完成，Step 48 的作用是防止未来高权限候选能力被误认为已经启用。

已落地内容：新增 `warframe_agent.future_capability_policy`，在 runtime safety 中嵌入只读 `future_capability_policy`，并加入 `future_capability_admission` capability。该 capability 的 `enabled=False`，表示只读策略可见，真实高权限运行时入口未启用。

安全边界：没有新增真实 Browser/GUI executor、服务恢复、任意触发器平台、插件安装、connector、webhook、平台私信命令、shell、通用文件写入、前端按钮、后台 worker 或真实语音能力。语音对话服务和真实语音继续按用户指令冻结。

验证摘要：初始红测先失败于缺少 `future_capability_policy` 模块；实现后绿测为 `7 passed, 33 deselected`。子代理复核后补充敏感 capability 名和 runtime enabled 语义红测，先复现 `2 failed`，修复后为 `9 passed, 33 deselected`。最终 policy 联跑为 `20 passed, 33 deselected`；Web API 可写运行环境补跑为 `1 passed, 71 deselected`；AST OK。

## 2026-05-31 追加：Step 49 已执行

已执行“Future Capability Runtime 可见性补齐”任务，计划记录在 `docs/superpowers/plans/2026-05-31-future-capability-runtime-visibility.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step49_future_capability_runtime_visibility_zh.md`。

路线判断：当前路线没有偏离。Step 49 是 Step 48 新阶段安全准入层的只读 Runtime 可见性补齐，不是旧 GitHub 项目个人 Agent 非语音学习借鉴队列的未完成项，也不表示任何未来高权限能力已经启用。

已落地内容：Runtime 面板新增 `Future Capability Policy` 摘要卡和详情区，展示 `future_capability_admission`、`design_required_before_runtime`、`runtime_enablement_allowed=false`、`requires_new_stage_design` 和 `blocked_uncontrolled_runtime`。前端敏感字段过滤补充未来高权限场景常见泄露形态。

安全边界：没有新增真实 Browser/GUI executor、服务恢复、任意触发器平台、插件安装、connector、webhook、平台私信命令、shell、通用文件写入、前端控制按钮、后台 worker 或真实语音能力。`future_capability_admission.enabled=False` 保持不变；语音对话服务和真实语音继续按用户指令冻结。

验证摘要：静态红测先失败于缺少 `renderRuntimeFutureCapabilityPolicy`；实现后 `node --check` 退出码 0，Runtime 静态契约 `1 passed`，完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`，Web API 可写环境补跑 `1 passed, 71 deselected`。

## 2026-05-31 追加：Step 50 已执行

已执行“学习借鉴与改善完成 Runtime 快照”任务，计划记录在 `docs/superpowers/plans/2026-05-31-learning-completion-runtime-snapshot.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step50_learning_completion_runtime_snapshot_zh.md`。

路线判断：当前路线没有偏离。Step 50 是完成状态快照，不是旧队列补课，也不是高权限能力启用。它把 Step 34-49 的完成状态收束到 `/api/runtime/status.learning_completion` 和 Runtime 面板，避免后续上下文压缩后误以为旧学习队列还没完成。

已落地内容：新增 `warframe_agent.learning_completion`，Runtime API 新增 top-level `learning_completion`，Runtime 面板新增 `Learning Completion` 摘要卡和详情区。

安全边界：没有新增真实 Browser/GUI executor、服务恢复、任意触发器平台、插件安装、connector、webhook、平台私信命令、shell、通用文件写入、前端控制按钮、后台 worker 或真实语音能力。`future_capability_admission.enabled=False` 保持不变；语音对话服务和真实语音继续按用户指令冻结。

验证摘要：单元红测先失败于缺少 `warframe_agent.learning_completion`；实现后 `tests/test_learning_completion.py` 为 `3 passed`，`node --check` 退出码 0，Runtime 静态契约 `1 passed`，Web API 可写环境补跑 `2 passed, 70 deselected`，完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`。最终复核中 policy / gateway / plugin / runtime safety 联跑 `23 passed, 33 deselected`；Runtime 静态契约复核 `1 passed`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

最终结论：到 Step 50 为止，“GitHub 个人 Agent 非语音学习借鉴计划完成 + Step 48/49 改善完成”已经具备代码、API、Runtime UI 和文档四层闭环。后续不再机械执行旧队列；真实高权限能力必须另开设计。

## 2026-05-31 追加：Step 51 已执行

已执行“学习借鉴完成验收清单快照”任务，计划记录在 `docs/superpowers/plans/2026-05-31-learning-completion-acceptance-snapshot.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step51_learning_completion_acceptance_snapshot_zh.md`。

路线判断：当前路线没有偏离。Step 51 是完成态验收防漂移改善，不是旧队列补课，也不是高权限能力启用。它把 Step 50 的闭环状态锚定为 `latest_closure_step=step50_learning_completion_runtime_snapshot`，并用 `acceptance_record_step=step51_learning_completion_acceptance_snapshot` 记录本次验收。

已落地内容：`learning_completion` 新增 `acceptance_status=accepted` 和 `acceptance_snapshot`，Runtime 面板展示 acceptance 状态、closure step、acceptance record 和验收 checklist，`completed_steps` 补入 `step50_learning_completion_runtime_snapshot`。

安全边界：没有新增真实 Browser/GUI executor、服务恢复、任意触发器平台、插件安装、connector、webhook、平台私信命令、shell、通用文件写入、前端控制按钮、后台 worker 或真实语音能力。`future_capability_admission.enabled=False` 保持不变；语音对话服务和真实语音继续按用户指令冻结。

验证摘要：单元红测先失败于缺少 `acceptance_status` 和 `acceptance_snapshot`；实现后 `tests/test_learning_completion.py` 为 `5 passed`，`node --check` 退出码 0，Runtime 静态契约 `1 passed`，Web API 可写环境补跑 `2 passed, 70 deselected`，完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`。最终 policy / gateway / plugin / runtime safety 联跑 `25 passed, 33 deselected`；Runtime 静态契约复核 `1 passed`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

最终结论：到 Step 51 为止，“GitHub 个人 Agent 非语音学习借鉴计划完成 + Step 48/49 改善完成 + Step 50 完成态验收”已经具备代码、API、Runtime UI、测试和文档闭环。后续不再机械执行旧队列；真实高权限能力必须另开设计。

## 2026-05-31 追加：Step 52 已执行

已执行“学习路线终止条件与新阶段入口收束”任务，计划记录在 `docs/superpowers/plans/2026-05-31-learning-route-termination-and-new-stage-entry.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step52_learning_route_termination_zh.md`。

路线判断：当前路线没有偏离，也没有未完成的旧学习借鉴队列。Step 52 是文档级终止条件收束，不是运行时代码改动，不是旧队列补课，也不是高权限能力启用。

终止条件：旧学习借鉴路线终止于 Step 51；Step 50 是完成闭环，Step 51 是验收记录。用户后续再次提出“继续下一步规划直到借鉴完成 / 改善完成 / 开始执行”这类同义请求时，默认动作是检查完成态并维护终止条件，而不是继续新增 Step53 / Step54 运行时代码。

新阶段入口：真实 Browser / GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装、connector 启用、webhook / DM 命令入口必须由用户明确指定并确认进入新阶段后，才能另开设计。新阶段必须先写清目标、权限边界、用户确认链路、可中断执行、审计摘要、回滚策略和测试方式。

安全边界：本步不修改运行时代码、API、前端 JS、测试或配置；不新增端点、按钮、开关、ToolRegistry 工具、executor、后台 worker、scheduler、webhook、connector 或插件安装能力；不下载依赖，不上传 GitHub。`future_capability_admission.enabled=False` 是未来高权限运行时未启用的证据，不是待补实现项。

最终结论：到 Step 52 为止，学习借鉴路线已经完成并具备防循环终止条件。后续不再机械执行旧队列；真实高权限能力必须作为独立新阶段另开设计。

## 2026-05-31 追加：Step 53 已执行

已执行“学习路线实现不足复核与历史文案防误读标注”任务，计划记录在 `docs/superpowers/plans/2026-05-31-learning-route-implementation-gap-audit.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md`。

路线判断：当前路线没有偏离，也没有未完成的旧学习借鉴队列。Step 53 只复核 Step 52 之后是否仍有实现不足；结论是没有代码/API/UI/test 层面的新增缺口，只有历史文案容易被上下文恢复误读的问题。

已处理内容：在 `AGENTS.md`、路线账本、`md/rebuilt/09-personal-agent-foundation.md` 和本文顶部补充当前权威状态，明确早期“剩余队列 / 下一步 / 债务”语句是历史记录，不再表示当前待办。Step 52 仍是路线控制规则，Step 53 是实现不足复核和防误读标注。

安全边界：本步不修改运行时代码、API、前端 JS、测试或配置；不新增端点、按钮、开关、ToolRegistry 工具、executor、后台 worker、scheduler、webhook、connector、插件安装或真实语音能力；不下载依赖，不上传 GitHub。

验证摘要：policy / gateway / plugin / future capability / learning completion 联跑 `25 passed, 33 deselected`；Runtime 静态契约 `1 passed`；AST OK；`node --check` 退出码 0；文档关键语义和 `git diff --check` 均通过。

最终结论：到 Step 53 为止，旧学习借鉴路线不仅完成、验收并具备终止条件，而且历史文案中最容易造成“继续旧队列”的误读点也已被标注。后续不再机械执行旧队列；真实高权限能力必须作为独立新阶段另开设计。

## 2026-05-31 追加：Step 54 已执行

已执行“项目整体验收运行与实现真实性复核”任务，计划记录在 `docs/superpowers/plans/2026-05-31-project-runtime-implementation-verification.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step54_project_runtime_verification_zh.md`。

路线判断：当前路线没有偏离。Step 54 是验收运行和实现真实性复核，不是旧学习借鉴队列补课，也不是高权限能力启用。它用于回答“项目实际跑起来是否有错”和“此前各种实现是否真做了”。

已确认内容：`learning_completion`、`future_capability_policy`、`gateway_policy`、`plugin_policy`、`safety_policy`、`/api/runtime/status` 和 Runtime 面板展示均真实存在；本地 uvicorn 烟测返回 `HTTP=200`、`learning_status=complete`、`acceptance_status=accepted`、`future_enabled=False`。

发现问题：项目全量测试没有全绿。可写运行环境补跑 `pytest tests` 结果为 `8 failed, 1162 passed, 7 warnings`。失败集中在聊天查价直答与旧 prompt 断言冲突、ToolRouter 安全策略旧期望、WebSocket 错误路径和前端 XSS 文本泄漏。

验证摘要：重点策略联跑 `25 passed, 33 deselected`；Runtime 静态契约 `1 passed`；`node --check warframe_agent\web\static\js\app.js` 退出码 0；`utf-8-sig` AST 扫描 `AST OK 82 files`；普通沙箱仍会遇到 SQLite WAL / uvicorn 可写环境限制。

最终结论：学习借鉴路线和改善闭环仍保持完成、验收和终止状态，但项目整体存在需要后续修复的真实测试失败。下一步应单独修复这 8 个失败，优先处理前端 XSS 文本泄漏和 WebSocket 错误路径。

## 2026-05-31 追加：Step 55 已执行

已执行“全量测试失败修复”任务，计划记录在 `docs/superpowers/plans/2026-05-31-step55-full-suite-failure-repair.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step55_full_suite_failure_repair_zh.md`。

路线判断：当前路线没有偏离。Step 55 是 Step 54 之后的项目质量修复，不是旧学习借鉴队列重启，也不是高权限能力启用。

已完成内容：修复聊天查价直答与注入 `model_call` prompt 路径的契约冲突；更新 Router plan 聚合测试以符合当前敏感参数硬拦策略；在 `chat.js` 中补充 XSS 文本收口和 WebSocket mock/native readyState 兼容逻辑。

验证结果：聊天广域回归 `79 passed`；Router / plan / tool context 回归 `37 passed`；6 个非 UI 旧失败定向验证 `6 passed`；`node --check warframe_agent\web\static\js\chat.js` 退出码 0；AST 检查 `AST OK`。

剩余验证：两个前端 Playwright 目标用例和完整 `pytest tests` 尚未在可写环境补跑。普通沙箱仍失败于 `RuntimeError: Web server did not become ready`，可写环境复跑被 quota / approval 层拒绝。因此 Step 55 标记为 `75% / 待评估`，不宣称全量已绿。

## 2026-05-31 追加：Step 56 已执行

已执行“虚空裂缝聊天查询修复”任务，计划记录在 `docs/superpowers/plans/2026-05-31-step56-void-fissure-chat-query-repair.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step56_void_fissure_query_repair_zh.md`。

路线判断：当前路线没有偏离。Step 56 是用户反馈驱动的项目质量修复，不是旧学习借鉴队列重启，也不是高权限能力启用。

已完成内容：聊天层 `void_fissure` 查询现在优先使用结构化 `VoidFissure` 数据，并按原始提问中的纪元、任务类型和普通 / 钢铁模式筛选；`现在有什么虚空裂缝` 展示结构化结束时间；`古纪裂缝有哪些` 和 `钢铁后纪裂缝有哪些` 不再返回不匹配的裂缝。

验证结果：新增红测先 `2 failed`；修复后裂缝目标聊天回归 `4 passed, 72 deselected`，事件格式化回归 `4 passed, 21 deselected`，ToolRouter 事件 / farming route 回归 `3 passed, 34 deselected`，裂缝提醒守卫 `6 passed, 50 deselected`，`tests/test_chat.py` 全量 `76 passed`，ReAct query_events 安全上下文 `1 passed`，AST OK。

安全边界：未安装依赖、未下载文件、未上传 GitHub；未新增 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。Step 55 的前端 Playwright 剩余验证仍按 Step 55 记录处理。

## 2026-06-01 追加：Step 57 已执行完成

已执行“活动与虚空商人回复体检计划”，计划记录在 `docs/superpowers/plans/2026-05-31-step57-event-baro-response-audit.md`，执行报告记录在 `githubProduct/personal_agent_warframe_migration_step57_event_baro_response_audit_zh.md`。

路线判断：当前路线没有偏离。Step 57 是项目质量体检计划，不是旧学习借鉴队列重启，也不是高权限能力启用。

已覆盖：泛活动问法、具体事件问法、Baro 状态、虚空商人 MOD / 赋能价格、虚空商人库存措辞、Baro 买家 / 卖家链接追问、不支持活动别名、市场 / 遗物 / 视频 / 计划等跨意图优先级，以及 `钢铁歼灭` 这类裂缝详情问法。

发现并修复：Baro 库存式问法可分析范围不清、热美亚裂缝误入虚空裂缝、具体限时活动不按标签过滤、Baro 后续追问污染后续普通市场链接查询、钢铁任务类型问法未显式进入裂缝详情。

验证结果：补充红测修复前 `2 failed`；修复后对应红测 `2 passed`；Step57 回复矩阵 `10 passed`；Baro / events / ToolRouter / Step57 focused suites `83 passed`；聊天广义回归 `18 passed, 114 deselected`；AST OK。

安全边界：未安装依赖、未下载文件、未上传 GitHub；未新增 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力，也未放宽 ToolRouter 安全策略。

后续动作：Step 57 已完成。可写 Playwright 环境恢复后，仍优先补跑 Step 55 遗留的 `test_chat_websocket_error_stops_loading_and_renders_message`、`test_chat_response_whisper_compare_and_chart_are_xss_safe` 和完整 `pytest tests`。

## 2026-06-01 追加：Step 58 已执行完成

已执行“Step55 Playwright 与全量回归收尾”任务，计划记录在 `docs/superpowers/plans/2026-06-01-step55-playwright-full-regression-closure.md`，结果记录在 `githubProduct/personal_agent_warframe_migration_step58_step55_playwright_full_regression_closure_zh.md`。

路线判断：当前路线没有偏离。Step 58 是 Step 55 项目质量修复的验证收尾，不是旧学习借鉴队列重启，也不是高权限能力启用。

普通沙箱复现结果：两个 Step55 Playwright 目标测试仍于 setup 阶段失败，直接 uvicorn 诊断确认根因为 SQLite WAL / 数据目录写入限制：`TradeHistoryDB()` 执行 `PRAGMA journal_mode=WAL` 时出现 `sqlite3.OperationalError: unable to open database file`。

可写环境修复结果：目标测试进入浏览器断言后，唯一失败点是聊天消息 DOM 的 `data-raw` 属性残留转义后的 `data-xss` 文本。已在 `warframe_agent/web/static/js/chat.js` 中新增 `safeChatRawText(...)`，让 agent 消息持久化到 DOM 的原文也经过 unsafe inline HTML 剥离。

验证摘要：`node --check warframe_agent\web\static\js\chat.js` 和 `node --check warframe_agent\web\static\js\chart.js` 均退出码 0；两个 Step55 Playwright 目标测试 `2 passed in 28.70s`；完整 `pytest tests` 为 `1182 passed, 7 warnings in 331.32s`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

安全边界：未安装依赖、未下载文件、未上传 GitHub；未新增 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力；未放宽 XSS 断言。

最终结论：Step55 遗留的两个前端 Playwright 目标测试和完整 `pytest tests` 复跑债务已关闭。后续项目质量任务应基于新的测试失败或用户反馈另开计划。
