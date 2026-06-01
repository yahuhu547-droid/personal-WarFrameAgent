# Step 40：个人 Agent 学习阶段总复盘

日期：2026-05-29

## 任务定位

本步不是新增业务功能，而是收束 Step 34-39 之后的个人 Agent 学习借鉴路线。目标是把“已经覆盖什么、还剩什么、下一阶段先做什么”写清楚，避免上下文压缩后继续在已覆盖主题里反复绕圈。

本步没有推送 GitHub，没有下载新项目，没有安装依赖，没有新增运行时代码。

## 覆盖矩阵

| 原始学习主题 | 当前状态 | 代表 Step | 结论 |
| --- | --- | --- | --- |
| 多 Agent 协作 | 已做架构决策和只读 Reviewer 最小落地 | Step 34-35 | 保留 `ChatAgent + ToolRouter + ModelOrchestrator` 单 Agent 主链路，不复制完整 LangManus / Suna 多 Agent runtime。 |
| 长期运行和运维控制面 | 已落地只读健康摘要 | Step 36 | `ops_health` 覆盖 scheduler、background tasks、Feishu、WxPusher 和日报状态，但不提供 start/stop/retry 控制。 |
| 可检查知识库和记忆 vault | 已落地只读 Memory Vault 索引 | Step 37 | 已有安全 entries 和 Markdown preview；未引入向量库、Obsidian 导出目录或个人数据连接器。 |
| Browser / GUI Agent 安全边界 | 已落地只读行为矩阵 | Step 38 | Browser/GUI executor 仍未开放；未来若接入必须先走人工确认和可中断设计。 |
| 语音和陪伴式体验 | 已落地 text-only 策略快照 | Step 39 | 语音、麦克风、录音、Live2D、后台监听和平台 token 均默认禁用。 |
| 多渠道入口 / Gateway / 插件生态 | 仍是下一阶段候选 | CowAgent / OpenClaw | 目前只做了 Web、飞书、WxPusher 和项目内工具安全边界，尚未产品化多渠道网关。 |
| 受控执行确认链路 | 部分覆盖 | Step 21-27、Step 35 | 自然语言写入已有确认模式；blocked plan 的“软拦截 -> 用户确认 -> 受控执行”尚未实现。 |

## Step 34-39 复盘

| Step | 来源项目 | 借鉴点 | Warframe 落点 | 安全边界 |
| --- | --- | --- | --- | --- |
| 34 | LangManus / OpenManus / Suna | 多 Agent 角色职责 | 架构决策文档 | 不引入 Browser Agent、Coder Agent、通用 Supervisor 或 sandbox worker。 |
| 35 | LangManus / OpenManus / Suna | planner / reviewer / verifier | `review_execution_plan(...)`、AgentPlan review | Reviewer 只读，不调用云端模型，不读取 `.env`。 |
| 36 | CowAgent / Suna / OpenClaw | service health、trigger visibility | `/api/runtime/status.ops_health` | 只读状态摘要，不新增控制按钮。 |
| 37 | OpenHuman / CowAgent | memory tree、source index | `memory_vault` 和 `/api/memory/vault` | 只输出安全摘要，不导出 raw chat、玩家名、profile、`/w` 或 token。 |
| 38 | OpenManus / Open-AutoGLM | Browser/GUI 动作空间、人类接管 | `browser_gui_safety` 和 `browser_gui_policy` | 不新增 Playwright/ADB/HDC executor。 |
| 39 | EchoBot / OpenHuman / OpenClaw | voice、Live2D、persona response、后台任务分离 | `companion_experience` 和 `companion_experience_policy` | 不新增语音、录音、后台监听、Live2D 或平台 token。 |

## 验证残留

Step 39 的核心单元与 runtime policy 目标测试已通过：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_companion_experience.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
```

残留项是 Web API 目标测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

普通沙箱导入 Web app 时仍受既有 SQLite WAL 权限限制；2026-05-29 的可写环境补跑请求被用户中断，因此本复盘不把 Step 39 标为 100%。这属于环境验证残留，不代表 `companion_experience_policy` 代码路径失败。

## 下一阶段候选任务

| 优先级 | 候选任务 | 来源项目 | 目标 | 为什么排在这里 |
| --- | --- | --- | --- | --- |
| P1 | Step 35 受控执行确认链路 | LangManus / OpenManus / Suna | 设计并实现 blocked plan 的“软拦截 -> 用户确认 -> 受控执行”最小闭环 | 当前已有 Reviewer 和自然语言确认基础，是最自然的下一段代码落地。 |
| P2 | Step 39 Web API 可写环境补跑 | OpenManus / OpenClaw runtime practice | 在可写运行环境补跑 `runtime_status_includes_read_only_safety_policy` | 这是验证收尾，不应和新功能混在一起。 |
| P3 | 多渠道入口 / Gateway 边界评估 | CowAgent / OpenClaw | 评估 Web、飞书、WxPusher、未来本地桌面入口的统一边界 | 需要产品决策，暂不适合直接写 executor。 |
| P4 | 技能 / 插件生态边界评估 | CowAgent / OpenClaw | 判断是否需要项目内技能注册、启停和安全摘要 | 只有在多渠道或受控执行稳定后再进入。 |
| P5 | 真实语音或 Browser/GUI 接入设计 | EchoBot / Open-AutoGLM | 设计高权限入口的确认、可中断、不可落盘 raw data 规则 | 当前只有安全策略，不应直接开放能力。 |

## 下一阶段安全边界

- 不推送 GitHub，除非用户重新明确要求。
- 不下载新项目或模型；如需下载，放在 `D:\Anthony-temp` 或项目根目录。
- 不新增 shell、Browser/GUI、语音、任意 scheduler 或平台私信 executor。
- 所有云端模型继续通过 `ModelOrchestrator` / `llm.py`，不得在新 helper 中直接读取 `.env` 或拼接 API header。
- 所有写入继续走用户确认和项目内 API；玩家名、profile、`/w`、token、raw orders、raw tool result 不进入长期记忆或 runtime 安全摘要。

## 总结

个人 Agent 主线学习队列已经基本覆盖。接下来不建议继续按“剩余学习队列”机械取任务，而应进入“下一阶段候选分支”模式：优先补受控执行确认链路，其次处理 Step 39 Web API 可写环境验证，再根据用户选择进入多渠道、技能插件、真实语音或 Browser/GUI 能力设计。
