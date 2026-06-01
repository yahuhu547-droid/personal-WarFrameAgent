# AGENTS.md 维护与开发执行规范

## 项目概览

- 项目路径：`F:\giteeProject\warframe`
- 项目目标：面向 Warframe 交易、市场分析、个人偏好、目标追踪、复盘记忆和主动推送的个人 Agent。
- 当前主链路：`ChatAgent + ToolRouter + ModelOrchestrator`。
- 当前学习路线：旧个人 Agent 学习借鉴路线已终止于 Step 51；Step 52 / Step 53 只维护终止条件和实现不足复核；Step 54 只做项目整体验收运行与实现真实性复核；Step 55 / Step 56 是项目质量修复，不重启旧学习队列。CowAgent、OpenManus、LangManus、OpenHuman、EchoBot、Open-AutoGLM、OpenClaw、Suna / Kortix 的历史来源仍保留用于审计，新高权限能力必须另开新阶段设计。

## 开发规范与技术栈

- 编码与文档：统一使用 UTF-8。
- 主要语言：Python、JavaScript、Markdown。
- Web 层：FastAPI + 静态 JS。
- 测试：pytest、Playwright。
- 本项目依赖优先安装在项目目录内，例如 `.\.venv`，避免写入 C 盘；如必须写入 C 盘，需要先向用户确认。
- 下载文件优先放到 `D:\Anthony-temp` 或项目根目录，不要给 C 盘造成存储压力。
- 修改原则：
  - 先确认关键假设，再编码。
  - 用最小改动完成当前目标。
  - 只改与任务直接相关的文件。
  - 不顺手重构、不清理无关代码、不回滚用户已有改动。

## 常用命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plan.py tests\test_tool_router.py -k "plan_review or agent_plan" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "ops_health or runtime_status_endpoint or runtime_status_includes_safe_agent_trace_snapshot" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_memory_vault.py tests\test_memory_recall.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "memory_vault or memory_recall_api_returns_safe_trace" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_browser_gui_safety.py tests\test_tool_registry.py -k "browser_gui or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_companion_experience.py tests\test_tool_registry.py -k "companion_experience or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_tool_registry.py -k "gateway_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_plugin_policy.py tests\test_tool_registry.py -k "plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/tool_router.py','warframe_agent/web/app.py','warframe_agent/memory_vault.py','warframe_agent/browser_gui_safety.py','warframe_agent/companion_experience.py','warframe_agent/safety_policy.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
```

备注：普通沙箱导入 Web app 或启动 uvicorn 时可能遇到 SQLite WAL / 数据库文件权限限制；必要时在用户允许后用可写运行环境补跑 Web API / Playwright 目标测试。

## 环境与工具约束

- MySQL 本机默认连接信息仅在任务涉及 MySQL 时使用：

```txt
Host: localhost
User: root
Password: 1234
```

- 三个云端 AI 已作为任务化模型角色纳入边界：
  - `kimi-k2.6`：Mod / 赋能 Scout 预筛。
  - `glm-5.1`：Prime 套装套利预筛。
  - `gpt-5.5`：投资顾问预筛和默认复杂云端分析。
- 所有云端模型调用必须通过 `ModelOrchestrator` / `llm.py`，不得在新角色或 helper 中直接读取 `.env` 或拼接 API header。

## 自动使用子代理规则

- Codex 可根据任务复杂度自动判断是否使用子代理。
- 适合使用子代理的场景：
  - 多模块并行调研。
  - 大范围代码审查。
  - 前后端可独立开发。
  - 测试与实现可并行验证。
  - 需要不同视角交叉检查的任务。
- 子代理结果必须由主线程复核后才能作为最终结论。

## 当前进度

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-27 | 路线账本修复 | 100% | 已完成 | 已创建 `githubProduct/personal_agent_learning_route_ledger_zh.md`，并同步 `md/rebuilt/10-learning-route-audit.md`。 |
| 2026-05-27 | Step 34 多 Agent 角色架构决策 | 100% | 已完成 | 保留单 Agent 主链路，暂不引入完整 LangManus / Suna 式多 Agent runtime。 |
| 2026-05-27 | Step 35 AgentPlan 只读 Reviewer / Verifier | 100% | 已完成 | 已实现 plan review、blocked plan 执行前软拦截、API 安全序列化和 Runtime 面板展示。 |
| 2026-05-28 | Step 36 长期运行与运维健康摘要 | 100% | 已完成 | `/api/runtime/status` 已新增只读 `ops_health`，Runtime 面板已展示 Ops Health 聚合，不新增控制按钮。 |
| 2026-05-28 | Step 37 可检查 Memory Vault 索引 | 100% | 已完成 | 已新增只读 `memory_vault` 聚合层和 `GET /api/memory/vault`，输出安全 entries 与 Markdown preview。 |
| 2026-05-28 | Step 38 Browser / GUI Agent 安全边界 | 100% | 已完成 | 已新增只读 `browser_gui_safety` 行为矩阵，并嵌入 `/api/runtime/status.safety_policy`。 |
| 2026-05-28 | Step 39 语音和陪伴式体验安全边界 | 90% | 待评估 | 已新增只读 `companion_experience` 策略快照，并嵌入 `/api/runtime/status.safety_policy`；按最新指令暂不继续真实语音 / 语音服务方向，Web API 目标测试作为冻结遗留验证。 |
| 2026-05-29 | Step 40 个人 Agent 学习阶段总复盘 | 100% | 已完成 | 已收束 Step 34-39 覆盖矩阵和下一阶段候选分支，不新增运行时代码。 |
| 2026-05-30 | Step 42 ChatAgent 计划确认闭环 | 100% | 已完成 | 已把 Step 41 的底层确认码接入 ChatAgent，用户可用“确认执行 / 取消执行”完成只读计划确认闭环；不展示确认码，不持久化 raw plan。 |
| 2026-05-30 | Step 43 多渠道 Gateway 边界评估 | 100% | 已完成 | 已新增只读 `gateway_policy` 和 `capabilities.multi_channel_gateway`，区分 Web/WS/CLI、Feishu、WxPusher、公共评论、匿名 webhook 和高风险动作边界。 |
| 2026-05-30 | Step 44 Skills / Plugin 生态边界评估 | 100% | 已完成 | 已新增只读 `plugin_policy` 和 `capabilities.skills_plugin_ecosystem`，明确 skills guidance-only、plugins 需 review、connectors 需显式启用和确认。 |
| 2026-05-30 | Step 45 Runtime Policy 可见性 | 100% | 已完成 | 已把 Gateway / Plugin policy 只读展示到 Runtime 面板；JS 语法、静态契约和完整 Playwright 浏览器目标测试均已通过。 |
| 2026-05-30 | Step 46 非语音学习借鉴路线闭环审计 | 100% | 已完成 | 已确认暂不考虑真实语音时，个人 Agent 非语音学习借鉴路线完成代码、文档和 Runtime 面板验证闭环。 |

## Step 35 验证摘要

- 计划 review / trace / blocked plan 软拦截：`10 passed, 43 deselected`。
- Web API runtime snapshot：普通沙箱受 SQLite WAL 限制，提权补跑 `1 passed, 69 deselected`。
- Runtime Playwright 面板：普通沙箱 uvicorn 未就绪，提权补跑 `1 passed`。

## Step 36 验证摘要

- API 红测：`ops_health` 缺失时按预期失败于 `KeyError: 'ops_health'`。
- UI 红测：Runtime 面板缺少 `Ops Health` 时按预期失败。
- API green：提权补跑 `tests/test_web_api.py -k "ops_health or runtime_status_endpoint"` 为 `2 passed, 69 deselected`。
- Runtime Playwright green：提权补跑 `test_runtime_panel_renders_jobs_tasks_and_safe_state` 为 `1 passed`。
- 静态契约：`test_sidebar_static_contracts_match_warframe_player_context` 为 `1 passed`。
- AST / JS / diff：`warframe_agent/web/app.py` 为 `AST OK`；`node --check warframe_agent\web\static\js\app.js` 退出码 0；`git diff --check` 退出码 0，仅有 LF 将被 Git 转 CRLF 的提示。

## Step 37 验证摘要

- 单元红测：`tests/test_memory_vault.py` 初次运行因缺少 `warframe_agent.memory_vault` 按预期失败。
- API 红测：可写运行环境中 `/api/memory/vault` 缺失时按预期失败于 `404 != 200`。
- Unit green：`tests/test_memory_vault.py` 为 `3 passed`，`tests/test_memory_recall.py` 为 `5 passed`。
- Web API green：提权补跑 `tests/test_web_api.py -k "memory_vault or memory_recall_api_returns_safe_trace"` 为 `2 passed, 70 deselected`。
- 安全边界：Vault 只返回 allowlist 摘要和 Markdown preview，不返回 raw user message、assistant reply、raw tool args/result、玩家名、profile URL、`/w`、token、secret、Authorization、cookie、app_secret 或 chat_id。

## Step 38 验证摘要

- 单元红测：`tests/test_browser_gui_safety.py` 初次运行因缺少 `warframe_agent.browser_gui_safety` 按预期失败。
- Runtime policy 红测：`tests/test_tool_registry.py` 初次运行因缺少 `browser_gui_policy` 按预期失败。
- Web API 红测：可写运行环境中 `runtime_status_includes_read_only_safety_policy` 初次运行因缺少 `browser_gui_automation` 按预期失败。
- Green：`tests/test_browser_gui_safety.py` 为 `5 passed`；`tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `1 passed, 33 deselected`；`tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"` 为 `1 passed, 71 deselected`。
- 安全边界：不新增 Browser Agent、Playwright/ADB/HDC executor、exposed Browser/GUI tool、后台 worker 或自动触发器；登录、支付、删除、私信、下单、凭据输入、任意脚本和私网目标默认 blocked。

## Step 39 验证摘要

- 单元红测：`tests/test_companion_experience.py` 初次运行因缺少 `warframe_agent.companion_experience` 按预期失败。
- Runtime policy 红测：`tests/test_tool_registry.py` 初次运行因缺少 `companion_experience_policy` 按预期失败。
- Green：`tests/test_companion_experience.py` 为 `6 passed`；`tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `1 passed, 33 deselected`。
- Web API 目标测试：普通沙箱导入 Web app 时仍受既有 SQLite WAL 权限限制；2026-05-29 可写环境补跑请求被用户中断，需要在可写运行环境中补跑。
- 安全边界：不新增 TTS/STT、麦克风、录音、后台监听、Live2D、平台 token、模型下载、前端按钮、ToolRegistry 工具或后台 worker；私聊、下单和交易动作继续 blocked。

## Step 40 验证摘要

- 文档输出：已新增 `githubProduct/personal_agent_warframe_migration_step40_learning_phase_review_zh.md`，并同步 `githubProduct/personal_agent_learning_route_ledger_zh.md`、`md/rebuilt/09-personal-agent-foundation.md`、`md/rebuilt/10-learning-route-audit.md` 和 `githubProduct/download_summary.json`。
- 路线结论：Step 34-39 已基本覆盖个人 Agent 主线学习队列；后续改为下一阶段候选分支，而不是机械继续旧队列。
- 保留债务：Step 39 Web API 可写环境补跑仍未完成，不能把 Step 39 标为 100%。
- 安全边界：本步不新增业务代码、API、运行时 executor、下载、依赖安装或 GitHub 推送。

## 下一步计划

- 优先候选：Step 45 Playwright 目标测试已在可写运行环境补跑通过，非语音学习借鉴路线已完成；后续若继续，应作为新阶段另开。
- 冻结候选：按最新用户指令，暂不考虑语音对话服务和真实语音；Step 39 Web API 补跑仅作为遗留验证，不作为当前优先任务。
- 高权限候选：真实 Browser/GUI 自动化、服务恢复和任意触发器平台必须先做权限、确认、可中断和审计设计。
## 2026-05-29 Step 41：受控执行确认链路

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-29 | Step 41 AgentPlan 受控执行确认链路 | 100% | 已完成 | 已实现 `PlanConfirmationRequest`、`build_plan_confirmation_request(...)` 和 `react_loop(..., plan_confirmation_token=...)`，只允许 `missing_verification` 的只读计划在确认码匹配并重新 review 后执行。 |

### Step 41 修改原因

- 修改原因：Step 35 已能软拦截 blocked plan，但缺少“软拦截 -> 用户确认 -> 受控执行”的底层门禁。
- 修改目标：先在 `ToolRouter` 单元层实现最小确认链路，不扩展 Web UI 或持久化 pending plan。
- 影响范围：`warframe_agent/tool_router.py`、`tests/test_plan.py`、Step 41 学习文档、`md/rebuilt` 和路线账本。

### Step 41 安全边界

- 仅 `missing_verification` 可确认执行。
- `unknown_tool`、`non_exposed_tool`、`side_effect_tool`、`sensitive_arguments` 继续硬拦。
- 不新增 Browser/GUI/shell/scheduler executor，不新增 Web 确认按钮，不持久化 raw plan。
- 确认码绑定当前 plan 指纹；plan 内容变化后旧确认码失效。

### Step 41 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plan.py -k "plan_confirmation or confirmed_missing_verification" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`6 passed, 17 deselected`。

### 下一步准备

- 若继续此分支，下一步应单独设计 ChatAgent / Web API 的 pending confirmation 状态，确保真实用户确认只传递安全字段，不持久化 raw sensitive plan。
- Step 39 Web API 可写环境补跑仍是遗留验证候选，不影响 Step 41 已完成状态。

## 2026-05-30 Step 42：ChatAgent 计划确认闭环

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-30 | Step 42 ChatAgent 计划确认闭环 | 100% | 已完成 | 已实现 `PendingAgentPlanConfirmation`、聊天层 pending confirmation、`确认执行 / 取消执行` 入口，并把 `plan_confirmation_token` 受控传回 `react_loop(...)`。 |

### Step 42 修改原因

- 修改原因：Step 41 已有 `ToolRouter` 底层确认码，但真实用户不应复制或看到 `plan_confirm_*`，聊天层也不能把“确认执行”误路由成普通市场问题。
- 修改目标：用最小改动补齐 `ChatAgent` 层的 pending confirmation 闭环，只处理 `missing_verification` 的只读计划。
- 影响范围：`warframe_agent/chat.py`、`tests/test_chat.py`、Step 42 学习文档、`md/rebuilt`、路线账本和 `AGENTS.md`。

### Step 42 安全边界

- 只在 `ToolRouter` 明确返回 `confirmation_required=true`、`confirmable_reason=missing_verification` 且 trace review 阻断原因一致时保存 pending confirmation。
- pending 状态只保存原始用户消息、候选工具名、阻断原因和确认码；不保存 raw plan、raw tool args、raw result、玩家名、profile、`/w`、token 或 secret。
- 用户回复必须是明确的“确认执行 / 执行计划 / 确认计划 / 继续执行 / 确认运行”才会触发计划确认；普通“确认”不触发，避免和目标、复盘、提醒等确认语义冲突。
- 不新增 Web UI 按钮、Browser/GUI/shell/scheduler executor、语音服务、TTS/STT、麦克风、录音、Live2D 或后台监听。

### Step 42 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "agent_plan_confirmation" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`5 passed, 69 deselected`。

补充联跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py tests\test_plan.py -k "agent_plan_confirmation or plan_confirmation or confirmed_missing_verification" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\chat.py tests\test_chat.py docs\superpowers\plans\2026-05-30-agent-plan-chat-confirmation.md githubProduct\personal_agent_warframe_migration_step42_chat_plan_confirmation_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md md\rebuilt\06-tools-models-safety.md AGENTS.md
```

结果：`11 passed, 86 deselected`；AST OK；`git diff --check` 退出码 0，仅提示部分文件下次由 Git 转换 LF/CRLF。

### 下一步准备

- 继续学习借鉴时，优先选择非语音分支：多渠道 Gateway 边界评估，或 skills / plugin 生态如何映射成受控工具入口。
- 若后续要继续确认链路，可单独设计 Web API / Runtime 面板的 pending confirmation 安全字段展示，但不得持久化 raw sensitive plan。
- 语音对话服务和真实语音按最新用户指令暂不推进；Step 39 保持 90% / 待评估，不作为当前主线。

## 2026-05-30 Step 43：多渠道 Gateway 边界评估

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-30 | Step 43 多渠道 Gateway 边界评估 | 100% | 已完成 | 已实现 `gateway_policy` 只读策略矩阵，并嵌入 `build_runtime_safety_policy(...)`。 |

### Step 43 修改原因

- 修改原因：Step 40 后仍有非语音候选分支“多渠道 Gateway”，需要先明确未来 Web、CLI、IM、推送、社交评论、webhook 等入口的信任边界。
- 修改目标：只输出安全策略快照，不新增真实平台连接器、webhook handler 或后台监听。
- 影响范围：`warframe_agent/gateway_policy.py`、`warframe_agent/safety_policy.py`、`tests/test_gateway_policy.py`、`tests/test_tool_registry.py`、Step 43 学习文档、`md/rebuilt`、路线账本和 `AGENTS.md`。

### Step 43 安全边界

- `web_chat`、`websocket_chat`、`local_cli` 视为交互式用户输入。
- `feishu_bot` 视为配置过的外部入口，但必须复用已有确认流程，不能绕过 `ToolRouter`、`AgentPlan` review 或用户确认。
- `wxpusher`、`feishu_push` 只作为出站通知出口，不作为入站命令入口。
- Bilibili 评论、匿名 webhook、GitHub issue、卖家 / 买家私信默认 blocked。
- 任意工具执行、shell、浏览器控制、文件写入、下单、私信等高风险动作默认 blocked。
- policy 不返回 raw payload、handler、token、secret、app_secret、chat_id、玩家名、profile URL 或 `/w`。
- 本步不新增语音对话服务、真实语音、TTS/STT、麦克风、录音、Live2D 或后台监听。

### Step 43 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_tool_registry.py -k "gateway_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`6 passed, 33 deselected`。

补充 Web API 可写环境验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`1 passed, 71 deselected`。普通沙箱因 SQLite WAL 数据库文件无法打开而失败，已在可写运行环境补跑通过。

### 下一步准备

- 继续非语音学习借鉴时，优先评估 skills / plugin 生态边界，明确插件能力如何映射到 ToolRegistry、AgentPlan review 和用户确认。
- 也可以把 `gateway_policy` 安全字段展示到 Runtime 面板，但不新增任何真实外部入口。
- 服务恢复、任意触发器平台和真实 Browser/GUI 自动化仍需另开设计，不能由 Gateway policy 直接放开。

## 2026-05-30 Step 44：Skills / Plugin 生态边界评估

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-30 | Step 44 Skills / Plugin 生态边界评估 | 100% | 已完成 | 已实现 `plugin_policy` 只读策略矩阵，并嵌入 `build_runtime_safety_policy(...)`。 |

### Step 44 修改原因

- 修改原因：Step 43 之后还剩非语音候选分支“skills / plugin 生态”，需要先明确 skills、plugins、connectors 进入运行时前的审查边界。
- 修改目标：只输出安全策略快照，不安装插件、不请求 plugin install、不启用 connector、不读取账号 token。
- 影响范围：`warframe_agent/plugin_policy.py`、`warframe_agent/safety_policy.py`、`tests/test_plugin_policy.py`、`tests/test_tool_registry.py`、`tests/test_web_api.py`、Step 44 学习文档、`md/rebuilt`、路线账本和 `AGENTS.md`。

### Step 44 安全边界

- local/system/project skills 只作为 guidance，不直接映射成 `ToolRegistry` handler。
- personal/local/Codex plugins 已安装后仍需 review，不能自动进入运行时。
- account connectors 必须显式启用并经用户确认。
- shell、file write、browser control、scheduler create、credential access、social post、trade action 默认 blocked。
- 插件未来若要进入运行时，必须继续经过 `ToolRegistry -> AgentPlan review -> 用户确认`。
- 所有云端模型调用继续通过 `ModelOrchestrator` / `llm.py`；插件不得直接读取 `.env`、拼 API header 或绕过模型编排。
- policy 不返回 raw manifest、handler、params、token、secret、api_key、account_id、真实本机路径或用户账号标识。
- 本步不新增语音对话服务、真实语音、TTS/STT、麦克风、录音、Live2D 或后台监听。

### Step 44 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plugin_policy.py tests\test_tool_registry.py -k "plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`7 passed, 33 deselected`；Web API 可写环境补跑 `1 passed, 71 deselected`。

### 下一步准备

- 继续执行 Step 45：把 `gateway_policy` 和 `plugin_policy` 以安全聚合字段展示到 Runtime 面板。
- Step 45 只做只读展示，不新增开关按钮、安装按钮、账号输入、connector、webhook 或真实外部入口。
- Step 45 完成后执行 Step 46：非语音学习借鉴路线最终闭环审计。

## 2026-05-30 Step 45：Runtime Policy 可见性

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-30 | Step 45 Runtime Policy 可见性 | 100% | 已完成 | 已实现 Gateway / Plugin policy 只读 Runtime 展示；完整 Playwright 浏览器目标测试已在可写运行环境补跑通过。 |

### Step 45 修改原因

- 修改原因：Step 43 / Step 44 已形成 Gateway / Plugin policy，但用户在 Runtime 面板中只能看到 capability，缺少更细的只读边界可见性。
- 修改目标：只展示安全聚合字段，不新增任何控制按钮、开关、安装入口、账号输入或外部入口。
- 影响范围：`warframe_agent/web/static/js/app.js`、`tests/test_web_ui_playwright.py`、Step 45 学习文档、`md/rebuilt`、路线账本和 `AGENTS.md`。

### Step 45 安全边界

- Runtime 面板只显示 default、runtime enabled、decision counts、channel / capability、decision、trust boundary 和 reason。
- 前端过滤 `raw_*`、`handler`、`params`、`manifest`、`payload`、`token`、`secret`、`account_id`、`api_key` 等字段。
- 不新增按钮、开关、安装入口、账号输入、Webhook、connector、Browser/GUI executor、scheduler executor 或真实外部入口。
- 本步不新增语音对话服务、真实语音、TTS/STT、麦克风、录音、Live2D 或后台监听。

### Step 45 验证摘要

```powershell
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`node --check` 退出码 0；静态契约测试 `1 passed`。

Playwright 目标测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp -p no:cacheprovider
```

当前状态：普通沙箱中仍会出现 uvicorn 未就绪；已在可写运行环境补跑通过，结果为 `1 passed`。

### 下一步准备

- 执行 Step 46：非语音学习路线最终闭环审计。
- Step 46 应明确“非语音借鉴路线代码、文档和 Runtime 面板浏览器验证均已覆盖”。

## 2026-05-30 Step 46：非语音学习借鉴路线闭环审计

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-30 | Step 46 非语音学习借鉴路线闭环审计 | 100% | 已完成 | 已输出闭环审计报告，确认非语音学习借鉴路线完成代码、文档和 Runtime 面板验证闭环。 |

### Step 46 结论

- 在暂不考虑语音对话服务和真实语音的前提下，个人 Agent 学习借鉴路线已完成代码与文档闭环。
- 已覆盖 CowAgent、OpenManus、LangManus、OpenHuman、EchoBot、Open-AutoGLM、OpenClaw、Suna / Kortix 的主要非语音主题。
- 已覆盖能力包括：单 Agent 主链路、多 Agent planner/reviewer/verifier 思路、受控计划确认、长期运行健康、可检查记忆、Browser/GUI 安全边界、text-only 陪伴边界、多渠道 Gateway 边界、skills/plugin 生态边界和 Runtime 可见性。

### Step 46 验证债务收束

- Step 45 Playwright 目标测试 `tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state` 已在可写运行环境补跑通过。
- 普通沙箱中仍会出现 uvicorn 未就绪，因此完整浏览器目标测试保留“可写运行环境补跑”要求，但不再是未完成债务。
- 该补跑只验证 Runtime 面板浏览器渲染，不新增 Gateway、Plugin、Browser/GUI executor、connector、webhook 或任何外部入口。

### Step 46 最终验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/gateway_policy.py','warframe_agent/plugin_policy.py','warframe_agent/safety_policy.py','warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
git diff --check -- warframe_agent\gateway_policy.py warframe_agent\plugin_policy.py warframe_agent\safety_policy.py warframe_agent\web\static\js\app.js warframe_agent\chat.py warframe_agent\tool_router.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py tests\test_web_api.py tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-30-multi-channel-gateway-boundary.md docs\superpowers\plans\2026-05-30-non-voice-learning-closure.md githubProduct\personal_agent_warframe_migration_step43_gateway_boundary_zh.md githubProduct\personal_agent_warframe_migration_step44_plugin_policy_zh.md githubProduct\personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md githubProduct\personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\06-tools-models-safety.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

结果：Gateway / Plugin / runtime policy 联跑 `12 passed, 33 deselected`；Runtime 静态契约测试 `1 passed`；Runtime 完整 Playwright 浏览器目标测试 `1 passed`；AST OK；`node --check` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

### 下一步准备

- Step 45 Playwright 目标测试已在可写运行环境补跑通过，Step 45 已改为 100% / 已完成。
- 后续若继续学习，应作为新阶段另开：真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装和 connector 启用。

## 2026-05-30 中断恢复收尾：Step 46 文档同步复核

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-30 | Step 46 中断恢复与文档同步复核 | 100% | 已完成 | 已补齐 `docs/superpowers/plans/2026-05-30-non-voice-learning-closure.md` 执行勾选和 `md/rebuilt/09-personal-agent-foundation.md` 的 Step 46 收束记录；未改运行时代码。 |

### 中断恢复复核结论

- 当前非语音学习借鉴路线仍按 Step 46 收束：代码与文档闭环已完成。
- 本次恢复只补文档状态一致性，不新增依赖、不下载文件、不提交 GitHub、不推进真实语音。
- Step 45 完整 Playwright 浏览器目标测试已在可写运行环境补跑通过；非语音学习借鉴路线不再保留未完成验证债务。

### 中断恢复验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-final-policy -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-final-static -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/gateway_policy.py','warframe_agent/plugin_policy.py','warframe_agent/safety_policy.py','warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
git diff --check -- warframe_agent\gateway_policy.py warframe_agent\plugin_policy.py warframe_agent\safety_policy.py warframe_agent\web\static\js\app.js warframe_agent\chat.py warframe_agent\tool_router.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py tests\test_web_api.py tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-30-multi-channel-gateway-boundary.md docs\superpowers\plans\2026-05-30-non-voice-learning-closure.md githubProduct\personal_agent_warframe_migration_step43_gateway_boundary_zh.md githubProduct\personal_agent_warframe_migration_step44_plugin_policy_zh.md githubProduct\personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md githubProduct\personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\06-tools-models-safety.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

结果：Gateway / Plugin / runtime policy 联跑 `12 passed, 33 deselected`；Runtime 静态契约测试 `1 passed`；AST OK；`node --check` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

### 下一步准备

- 后续如果继续学习借鉴，应新开阶段设计，不再沿旧队列机械推进。

## 2026-05-30 Step 47：最终 Playwright 验证债务收束

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-30 | Step 47 最终 Playwright 验证债务收束 | 100% | 已完成 | 已按 `docs/superpowers/plans/2026-05-30-learning-borrowing-final-playwright-closure.md` 补跑 Step 45 完整 Runtime 面板浏览器目标测试，并同步学习借鉴路线收束状态。 |

### Step 47 修改原因

- 修改原因：Step 46 之后唯一剩余事项是 Step 45 完整 Playwright 浏览器目标测试未在可写运行环境通过。
- 修改目标：只补验证和文档状态，不新增运行时代码、按钮、开关、connector、webhook、Browser/GUI executor 或语音能力。
- 影响范围：最终闭环计划、`AGENTS.md`、路线账本、Step 45 / Step 46 报告和 `md/rebuilt` 文档。

### Step 47 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-final-playwright -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-final-playwright-writable -p no:cacheprovider
```

结果：普通沙箱复现 `RuntimeError: Web server did not become ready`；可写运行环境补跑通过，`1 passed`。

最终复核：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-final-policy-verify -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-final-static-verify -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-final-playwright-verify -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/gateway_policy.py','warframe_agent/plugin_policy.py','warframe_agent/safety_policy.py','warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
git diff --check -- warframe_agent\gateway_policy.py warframe_agent\plugin_policy.py warframe_agent\safety_policy.py warframe_agent\web\static\js\app.js warframe_agent\chat.py warframe_agent\tool_router.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py tests\test_web_api.py tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-30-learning-borrowing-final-playwright-closure.md githubProduct\personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md githubProduct\personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

结果：policy 联跑 `12 passed, 33 deselected`；Runtime 静态契约 `1 passed`；完整 Playwright 浏览器目标测试可写运行环境复核 `1 passed`；AST OK；`node --check` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

### 下一步准备

- GitHub 项目个人 Agent 非语音学习借鉴计划已经完成，不再有旧队列中的未完成实现项。
- Step 39 语音 / 陪伴 Web API 补跑仍属于冻结遗留验证；按最新用户指令，暂不推进语音对话服务和真实语音。
- 新阶段候选必须另开设计：真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装和 connector 启用。

## 2026-05-30 Step 48：未来高权限能力准入策略

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-30 | Step 48 未来高权限能力准入策略 | 100% | 已完成 | 已新增只读 `future_capability_policy`，把未来 Browser/GUI executor、服务恢复、任意触发器、插件安装、connector 启用、真实语音等高权限候选能力先纳入准入矩阵，不启用运行时入口。 |

### Step 48 修改原因

- 修改原因：Step 47 已确认旧的非语音 GitHub 项目学习借鉴计划完成；后续高权限候选能力必须作为新阶段先做准入策略，避免被误读为已启用功能。
- 修改目标：新增只读未来能力准入策略，明确哪些能力只允许设计、哪些冻结、哪些必须另开新阶段、哪些默认阻断。
- 影响范围：`warframe_agent/future_capability_policy.py`、`warframe_agent/safety_policy.py`、`tests/test_future_capability_policy.py`、`tests/test_tool_registry.py`、Step 48 学习文档、路线账本、`md/rebuilt` 和 `AGENTS.md`。

### Step 48 安全边界

- `future_capability_admission.enabled=False`，只表示准入策略可见，不表示高权限运行时能力已启用。
- 不注册 ToolRegistry 工具，不新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端按钮或后台 worker。
- 真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续按用户当前指令冻结。
- policy 不返回 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_manifest、raw_arguments、handler、params、profile、`/w`、本机路径或私网地址；疑似敏感 capability 名会归一为 `unknown_future_capability`。
- 所有云端模型调用继续只能通过 `ModelOrchestrator` / `llm.py`，不得在策略层或 helper 中读取 `.env` 或拼接 API header。

### Step 48 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_tool_registry.py -k "future_capability or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-review-green -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-final -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step48-web-api-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/future_capability_policy.py','warframe_agent/safety_policy.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

结果：补充目标绿测 `9 passed, 33 deselected`；最终 policy 联跑 `20 passed, 33 deselected`；Web API 可写运行环境补跑 `1 passed, 71 deselected`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。普通沙箱运行 Web API 目标测试仍会因 SQLite WAL 数据库文件无法打开失败，需要可写运行环境。

### 下一步准备

- 旧的非语音学习借鉴路线仍保持完成状态；Step 48 是新阶段安全准入层，不是旧队列补课。
- 后续若继续推进真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装或 connector 启用，必须另开设计并补齐权限、确认、可中断执行、审计和回滚策略。

## 2026-05-31 Step 49：Future Capability Runtime 可见性补齐

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-31 | Step 49 Future Capability Runtime 可见性补齐 | 100% | 已完成 | 已把 Step 48 的 `future_capability_policy` 以只读摘要和矩阵展示到 Runtime 面板，不启用未来高权限运行时入口。 |

### Step 49 修改原因

- 修改原因：Step 48 已新增未来高权限能力准入策略，但 Runtime 面板尚未展示该策略，用户无法在运行态控制面检查未来高权限候选能力的准入状态。
- 修改目标：只补 Runtime 可见性，展示 `future_capability_admission`、`design_required_before_runtime`、`runtime_enablement_allowed=false`、`requires_new_stage_design` 和 `blocked_uncontrolled_runtime`。
- 影响范围：`warframe_agent/web/static/js/app.js`、`tests/test_web_ui_playwright.py`、`tests/test_web_api.py`、Step 49 计划和学习文档、路线账本、`md/rebuilt` 和 `AGENTS.md`。

### Step 49 安全边界

- `future_capability_admission.enabled=False` 保持不变，表示策略可见但未来高权限运行时能力未启用。
- 不注册 ToolRegistry 工具，不新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端控制按钮或后台 worker。
- 真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续按用户当前指令冻结。
- Runtime 面板过滤 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_manifest、raw_arguments、raw_plan、handler、params、profile、`/w`、本机路径和私网地址；新增过滤 `credential`、`user_id`、`private_network_url`、`local_path`、`raw_config`、`webhook_secret` 和 `connector_token`。
- 所有云端模型调用继续只能通过 `ModelOrchestrator` / `llm.py`，不得在展示层、策略 helper 或新组件中读取 `.env` 或拼接 API header。

### Step 49 验证摘要

```powershell
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step49-static -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-step49-playwright-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step49-api-writable -p no:cacheprovider
```

结果：JS 语法检查退出码 0；Runtime 静态契约 `1 passed`；完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`；Web API 可写环境补跑 `1 passed, 71 deselected`；最终 policy 联跑 `20 passed, 33 deselected`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。普通沙箱中 Playwright 仍失败于 uvicorn 未就绪，Web API 仍失败于 SQLite WAL 数据库文件无法打开。

### 下一步准备

- GitHub 项目个人 Agent 非语音学习借鉴计划仍保持完成；Step 49 是新阶段安全准入层的可见性改善。
- 高权限能力如果要从“可见策略”进入真实运行时，必须另开设计并补齐权限、确认、可中断执行、审计和回滚策略。

## 2026-05-31 Step 50：学习借鉴与改善完成 Runtime 快照

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-31 | Step 50 学习借鉴与改善完成 Runtime 快照 | 100% | 已完成 | 已新增只读 `learning_completion` 快照，把旧非语音学习借鉴路线完成和 Step 48/49 改善完成展示到 `/api/runtime/status` 与 Runtime 面板。 |

### Step 50 修改原因

- 修改原因：Step 47 已确认旧学习借鉴路线完成，Step 48 / Step 49 已完成安全准入和 Runtime 可见性改善；需要一个可被 API/UI 直接验证的完成状态快照，避免跨会话或上下文压缩后误读。
- 修改目标：新增只读学习完成快照，展示 `status=complete`、`legacy_non_voice_learning_complete=true`、`improvement_closure_complete=true`、`runtime_enablement_changed=false`、已完成步骤和下一阶段需另开设计的能力。
- 影响范围：`warframe_agent/learning_completion.py`、`warframe_agent/web/app.py`、`warframe_agent/web/static/js/app.js`、`tests/test_learning_completion.py`、`tests/test_web_api.py`、`tests/test_web_ui_playwright.py`、Step 50 计划和学习文档、路线账本、`md/rebuilt` 和 `AGENTS.md`。

### Step 50 安全边界

- 本步只新增只读完成状态快照，不注册 ToolRegistry 工具，不新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端控制按钮或后台 worker。
- `future_capability_admission.enabled=False` 保持不变，表示策略可见但未来高权限运行时能力未启用。
- 真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续按用户当前指令冻结。
- 快照和文档不记录 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_manifest、raw_arguments、raw_plan、handler、params、profile、`/w`、本机私密路径、私网地址或玩家私信信息。
- 所有云端模型调用继续只能通过 `ModelOrchestrator` / `llm.py`，不得在新快照、展示层或 helper 中读取 `.env` 或拼接 API header。

### Step 50 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step50-learning -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step50-static -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_endpoint or runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step50-api-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-step50-playwright-writable -p no:cacheprovider
```

结果：unit `3 passed`；JS 语法检查退出码 0；Runtime 静态契约 `1 passed`；Web API 可写环境补跑 `2 passed, 70 deselected`；完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`。普通沙箱中 Web API 仍失败于 SQLite WAL 数据库文件无法打开，Playwright 仍失败于 uvicorn 未就绪。

最终复核：policy / gateway / plugin / runtime safety 联跑 `23 passed, 33 deselected`；Runtime 静态契约复核 `1 passed`；`warframe_agent/learning_completion.py`、`warframe_agent/future_capability_policy.py`、`warframe_agent/safety_policy.py`、`warframe_agent/web/app.py` AST OK；`node --check warframe_agent\web\static\js\app.js` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

### 下一步准备

- 到 Step 50 为止，“GitHub 个人 Agent 非语音学习借鉴计划完成 + Step 48/49 改善完成”已经具备代码、API、Runtime UI 和文档四层闭环。
- 后续不再机械执行旧学习借鉴队列；真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装和 connector 启用必须作为独立新阶段设计。

## 2026-05-31 Step 51：学习借鉴完成验收清单快照

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-31 | Step 51 学习借鉴完成验收清单快照 | 100% | 已完成 | 已在只读 `learning_completion` 中新增 `acceptance_status=accepted` 和 `acceptance_snapshot`，把 Step 50 闭环锚点、Step 51 验收记录和安全 checklist 展示到 `/api/runtime/status` 与 Runtime 面板。 |

### Step 51 修改原因

- 修改原因：Step 50 已能展示完成态，但缺少机器可读的“为什么算完成”的验收清单，后续上下文压缩后可能误以为旧学习队列仍有尾巴。
- 修改目标：新增只读 acceptance snapshot，锚定 `latest_closure_step=step50_learning_completion_runtime_snapshot` 和 `acceptance_record_step=step51_learning_completion_acceptance_snapshot`。
- 影响范围：`warframe_agent/learning_completion.py`、`warframe_agent/web/static/js/app.js`、`tests/test_learning_completion.py`、`tests/test_web_api.py`、`tests/test_web_ui_playwright.py`、Step 51 计划和学习文档、路线账本、`md/rebuilt` 和 `AGENTS.md`。

### Step 51 安全边界

- 本步只扩展只读完成验收快照，不注册 ToolRegistry 工具，不新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端控制按钮或后台 worker。
- `future_capability_admission.enabled=False` 保持不变，表示策略可见但未来高权限运行时能力未启用。
- 真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续按用户当前指令冻结。
- 快照和文档不记录 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_manifest、raw_arguments、raw_plan、handler、params、profile、`/w`、本机私密路径、私网地址或玩家私信信息。
- 所有云端模型调用继续只能通过 `ModelOrchestrator` / `llm.py`，不得在新快照、展示层或 helper 中读取 `.env` 或拼接 API header。

### Step 51 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step51-red -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step51-learning -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step51-static -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_endpoint or runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step51-api-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-step51-playwright-writable -p no:cacheprovider
```

结果：红测按预期失败于 `KeyError: 'acceptance_status'` 和 `KeyError: 'acceptance_snapshot'`；实现后 unit `5 passed`；JS 语法检查退出码 0；Runtime 静态契约 `1 passed`；Web API 可写环境补跑 `2 passed, 70 deselected`；完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`。普通沙箱中 Web API 仍失败于 SQLite WAL 数据库文件无法打开，Playwright 仍失败于 uvicorn 未就绪。

最终复核：policy / gateway / plugin / runtime safety 联跑 `25 passed, 33 deselected`；Runtime 静态契约复核 `1 passed`；`warframe_agent/learning_completion.py`、`warframe_agent/future_capability_policy.py`、`warframe_agent/safety_policy.py`、`warframe_agent/web/app.py` AST OK；`node --check warframe_agent\web\static\js\app.js` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

### 下一步准备

- 到 Step 51 为止，“GitHub 个人 Agent 非语音学习借鉴计划完成 + Step 48/49 改善完成 + Step 50 完成态验收”已经具备代码、API、Runtime UI、测试和文档闭环。
- 后续不再机械执行旧学习借鉴队列；真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装和 connector 启用必须作为独立新阶段设计。

## 2026-05-31 Step 52：学习路线终止条件与新阶段入口收束

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-31 | Step 52 学习路线终止条件与新阶段入口收束 | 100% | 已完成 | 已把旧学习借鉴路线终止条件和未来新阶段入口规则写入计划、报告、路线账本、`md/rebuilt` 与 `AGENTS.md`；本步不改运行时代码。 |

### Step 52 修改原因

- 修改原因：Step 51 后，路线已经完成并验收；用户重复提出同义“继续到完成并执行”请求时，需要明确默认动作，避免旧队列被惯性重开。
- 修改目标：文档级记录终止条件和新阶段入口，明确旧学习借鉴路线终止于 Step 51，Step 50 是完成闭环，Step 51 是验收记录。
- 影响范围：`docs/superpowers/plans/2026-05-31-learning-route-termination-and-new-stage-entry.md`、`githubProduct/personal_agent_warframe_migration_step52_learning_route_termination_zh.md`、路线账本、`md/rebuilt/09-personal-agent-foundation.md`、`md/rebuilt/10-learning-route-audit.md` 和 `AGENTS.md`。

### Step 52 终止条件

- 旧学习借鉴路线终止于 Step 51。
- 如果用户再次提出“继续下一步规划直到借鉴完成 / 改善完成 / 开始执行”这类同义请求，默认解释为检查完成态并维护终止条件，而不是继续新增 Step53 / Step54 运行时代码。
- 不得从早期“剩余学习队列”重新循环执行已经由 Step 34-51 覆盖的主题。
- `future_capability_admission.enabled=False` 是未来高权限运行时未启用的证据，不是待补实现项。
- Step 39 真实语音继续冻结，不得因“路线完成”反向推进真实语音。

### Step 52 新阶段入口

- 只有用户明确指定并确认愿意进入真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装、connector 启用、webhook / DM 命令入口等新阶段能力时，才允许另开设计。
- 新阶段必须先写清目标、权限边界、用户确认链路、可中断执行、审计摘要、回滚策略和测试方式。
- 未经新阶段设计，不得把 Step 48 / Step 49 的只读 policy 解释为功能启用依据。

### Step 52 安全边界

- 本步不修改运行时代码、API、前端 JS、测试或配置。
- 不新增端点、按钮、开关、ToolRegistry 工具、executor、后台 worker、scheduler、webhook、connector 或插件安装能力。
- 不启用 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、真实语音、TTS/STT、麦克风、录音、Live2D 或后台监听。
- 不下载依赖，不上传 GitHub。
- 不记录 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_plan、handler、params、profile、`/w`、本机私密路径、私网地址或玩家私信信息。

### Step 52 验证摘要

```powershell
rg -n "Step 52|终止条件|新阶段入口|不再机械执行旧队列|future_capability_admission.enabled=False" AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\10-learning-route-audit.md md\rebuilt\09-personal-agent-foundation.md githubProduct\personal_agent_warframe_migration_step52_learning_route_termination_zh.md
git diff --check -- AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\10-learning-route-audit.md md\rebuilt\09-personal-agent-foundation.md docs\superpowers\plans\2026-05-31-learning-route-termination-and-new-stage-entry.md githubProduct\personal_agent_warframe_migration_step52_learning_route_termination_zh.md
```

### 下一步准备

- 到 Step 52 为止，学习借鉴路线已经完成、验收并具备防循环终止条件。
- 后续不再机械执行旧学习借鉴队列；真实高权限能力必须作为独立新阶段另开设计。

## 2026-05-31 Step 53：学习路线实现不足复核与历史文案防误读标注

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-31 | Step 53 学习路线实现不足复核与历史文案防误读标注 | 100% | 已完成 | 已完成全路线实现不足复核、文档防误读标注和最终验证；未新增运行时代码。 |

### Step 53 修改原因

- 修改原因：Step 52 已定义旧学习路线终止条件，但用户要求如果没有推荐下一步，就检查整个计划实现是否还有不足；子代理和主线程复核后确认没有必须新增运行时代码的缺口，但早期文档仍存在可能误导后续恢复的“剩余队列 / 下一步 / 债务”历史语句。
- 修改目标：保留历史记录，同时在关键文档补充当前权威状态，明确旧学习借鉴路线终止于 Step 51，Step 52 是终止规则，Step 53 是实现不足复核和历史文案防误读标注。
- 影响范围：`docs/superpowers/plans/2026-05-31-learning-route-implementation-gap-audit.md`、`githubProduct/personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md`、路线账本、`md/rebuilt/09-personal-agent-foundation.md`、`md/rebuilt/10-learning-route-audit.md` 和 `AGENTS.md`。

### Step 53 复核结论

- 未发现需要新增代码、API、Runtime UI 或测试覆盖的缺口。
- 当前完成锚点仍是 `learning_completion.status=complete`、`acceptance_status=accepted`、`acceptance_snapshot`、`runtime_enablement_changed=false` 和 `future_capability_admission.enabled=False`。
- 早期“剩余学习队列 / 下一步 / 验证债务”内容保留为历史审计记录，不再表示当前待办。
- 后续同义“继续直到借鉴完成 / 改善完成 / 开始执行”请求默认解释为完成态复核和终止条件维护，而不是继续新增 Step54 运行时代码。

### Step 53 安全边界

- 本步不修改运行时代码、API、前端 JS、测试或配置。
- 不新增端点、按钮、开关、ToolRegistry 工具、executor、后台 worker、scheduler、webhook、connector 或插件安装能力。
- 不启用 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、真实语音、TTS/STT、麦克风、录音、Live2D 或后台监听。
- 不下载依赖，不上传 GitHub。
- 不记录 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_plan、handler、params、profile、`/w`、本机私密路径、私网地址或玩家私信信息。

### Step 53 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "learning_completion or future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step53-policy -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/learning_completion.py','warframe_agent/future_capability_policy.py','warframe_agent/gateway_policy.py','warframe_agent/plugin_policy.py','warframe_agent/safety_policy.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step53-static -p no:cacheprovider
rg -n "Step 53|实现不足复核|历史记录|当前权威|旧学习借鉴路线|acceptance_status=accepted|不再机械执行旧队列" AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md githubProduct\personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md
git diff --check -- AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md docs\superpowers\plans\2026-05-31-learning-route-implementation-gap-audit.md githubProduct\personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md
```

结果：policy / gateway / plugin / future capability / learning completion 联跑 `25 passed, 33 deselected`；Runtime 静态契约 `1 passed`；AST OK；`node --check warframe_agent\web\static\js\app.js` 退出码 0；关键文档语义 `rg` 可检索；`git diff --check` 退出码 0。

### 下一步准备

- 到 Step 53 为止，旧学习借鉴路线已完成、验收、具备终止条件，并且历史文案误读点已标注。
- 后续不再机械执行旧学习借鉴队列；真实高权限能力必须作为独立新阶段另开设计。

## 2026-05-31 Step 54：项目整体验收运行与实现真实性复核

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-31 | Step 54 项目整体验收运行与实现真实性复核 | 100% | 已完成 | 已运行全量 pytest、重点策略测试、Runtime 静态契约、JS/AST 检查和本地 uvicorn 烟测；确认学习借鉴实现真实落地，但项目全量测试仍有 8 个失败。 |

### Step 54 修改原因

- 修改原因：用户要求实际运行项目，检查整体是否有错误，以及此前各种学习借鉴实现是否真正落地。
- 修改目标：只做验收运行和证据记录，明确“实现真实存在”和“项目全量测试是否全绿”两个不同结论。
- 影响范围：`docs/superpowers/plans/2026-05-31-project-runtime-implementation-verification.md`、`githubProduct/personal_agent_warframe_migration_step54_project_runtime_verification_zh.md`、`md/rebuilt/09-personal-agent-foundation.md`、`md/rebuilt/10-learning-route-audit.md` 和 `AGENTS.md`。

### Step 54 复核结论

- 学习借鉴实现真实存在：`warframe_agent.learning_completion`、`future_capability_policy`、`gateway_policy`、`plugin_policy`、`safety_policy`、`/api/runtime/status` 和 Runtime 面板展示均有真实代码与测试覆盖。
- 本地 uvicorn 烟测返回 `HTTP=200`、`learning_status=complete`、`acceptance_status=accepted`、`future_enabled=False`。
- 项目整体不能宣称全量绿色：可写运行环境全量 `pytest tests` 结果为 `8 failed, 1162 passed, 7 warnings`。
- 8 个失败主要集中在聊天查价直答与旧 prompt 断言冲突、ToolRouter 安全策略旧期望、WebSocket 错误路径，以及前端 XSS 文本泄漏。

### Step 54 安全边界

- 本步未安装依赖、未下载文件、未上传 GitHub。
- 本步未新增或启用 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。
- 本步只追加验收计划、报告和 rebuilt / AGENTS 状态记录，未修改运行时代码。

### Step 54 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp-step54-full-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "learning_completion or future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step54-policy -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step54-static -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
```

结果：全量可写环境 `8 failed, 1162 passed, 7 warnings`；重点策略联跑 `25 passed, 33 deselected`；Runtime 静态契约 `1 passed`；`node --check` 退出码 0；`utf-8-sig` AST 扫描 `AST OK 82 files`；uvicorn Runtime 烟测 `HTTP=200` 且完成锚点字段正确。

### 下一步准备

- 学习借鉴路线仍保持完成和验收状态，不因 Step 54 的全量测试失败而重启旧队列。
- 下一步应作为修复任务处理 8 个失败，优先级是前端 XSS 文本泄漏和 WebSocket 错误路径，其次是聊天查价直答与旧 prompt 测试的契约取舍，最后复核 ToolRouter 安全策略旧断言。

## 2026-05-31 Step 55：全量测试失败修复

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-31 | Step 55 全量测试失败修复 | 100% | 已完成 | 已修复并验证 6 个非 UI 失败；2 个前端 Playwright 目标测试和完整 `pytest tests` 已在 Step 58 可写环境收尾复跑通过。 |

### Step 55 修改原因

- 修改原因：Step 54 全量 pytest 在可写环境中发现 `8 failed, 1162 passed, 7 warnings`，用户要求制定计划并开始解决。
- 修改目标：优先修复可复现的 8 个失败根因，同时不放宽安全边界、不重启旧学习借鉴队列。
- 影响范围：`warframe_agent/chat.py`、`tests/test_router.py`、`warframe_agent/web/static/js/chat.js`、Step 55 计划、Step 55 修复报告、`md/rebuilt` 和 `AGENTS.md`。

### Step 55 已修复内容

- 聊天别名 / RAG / 记忆 prompt 失败：`ChatAgent.answer(...)` 现在只在默认 `call_ollama_chat` 生产路径对纯 market analysis 走确定性直答；注入 `model_call` 的纯市场问题继续走 prompt 路径。混入攻略 / 视频词的价格问题仍走确定性价格回答，避免误触发 B 站推荐。
- Router plan 聚合失败：更新过期测试 payload，生产代码仍会阻断含 `token`、`__message`、`message_context` 等敏感参数的 plan。
- WebSocket 错误路径：`chat.js` 新增 WebSocket 状态兼容 helper，兼容原生静态常量和测试 mock 的数字 `readyState`，并等待 connecting socket 短暂打开后再决定是否 REST fallback。
- XSS 文本泄漏：`chat.js` 在 Markdown 渲染前剥离 unsafe inline HTML 片段，并禁止 `data-xss` 属性。

### Step 55 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py tests\test_chat_alias_priority.py tests\test_chat_memory_integration.py tests\test_chat_rag_fallback.py tests\test_short_name_regression.py -q --basetemp .pytest-tmp-step55-chat-broad-2 -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_router.py::ReactLoopTests::test_plan_aggregation_redacts_and_budgets_context tests\test_plan.py tests\test_tool_context.py -q --basetemp .pytest-tmp-step55-router-broad-2 -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_alias_priority.py::ChatAliasPriorityTests::test_manual_alias_key_overrides_generated_duplicate_key tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_generated_alias_substring_is_detected tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_memory_alert_is_added_to_prompt tests\test_chat_rag_fallback.py::ChatRagFallbackTests::test_chat_uses_rag_result_when_alias_lookup_fails tests\test_short_name_regression.py::ShortNameRegressionTests::test_short_chinese_name_inside_sentence_is_resolved tests\test_router.py::ReactLoopTests::test_plan_aggregation_redacts_and_budgets_context -q --basetemp .pytest-tmp-step55-targeted-non-ui -p no:cacheprovider
node --check warframe_agent\web\static\js\chat.js
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
```

结果：聊天广域回归 `79 passed`；Router / plan / tool context 回归 `37 passed`；6 个非 UI 旧失败定向验证 `6 passed`；`node --check` 退出码 0；AST 检查 `AST OK`。

### Step 55 未完成验证

- `tests/test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message` 和 `tests/test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe` 在普通沙箱仍于 setup 阶段失败：`RuntimeError: Web server did not become ready`。
- 可写环境 Playwright / 全量 pytest 复跑请求被本地 quota / approval 层拒绝，因此不能声称这 2 个 UI 用例或全量 suite 已通过。
- 2026-06-01 Step 58 已关闭该验证债务：普通沙箱失败根因为 SQLite WAL / 数据目录写入限制；可写运行环境中两个 Playwright 目标测试 `2 passed`，完整 `pytest tests` 为 `1182 passed, 7 warnings`。

### 下一步准备

- Step 58 已完成可写环境收尾验证；Step 55 不再保留 Playwright / 全量 pytest 未完成债务。
- 后续如果继续项目质量修复，应基于新的用户反馈或新的全量测试失败另开任务，不再沿 Step55 旧债务继续。

## 2026-05-31 Step 56：虚空裂缝聊天查询修复

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-31 | Step 56 虚空裂缝聊天查询修复 | 100% | 已完成 | 已修复裂缝聊天问法的筛选和结构化详情展示，普通活动查询仍不混入虚空裂缝。 |

### Step 56 修改原因

- 修改原因：用户反馈虚空裂缝提问仍有返回内容缺少和不符合筛选的问题。
- 修改目标：让 `现在有什么虚空裂缝`、`古纪裂缝有哪些`、`钢铁后纪裂缝有哪些` 等问法返回匹配的结构化裂缝列表。
- 影响范围：`warframe_agent/chat.py`、`tests/test_chat.py`、Step 56 计划、Step 56 修复报告、`md/rebuilt` 和 `AGENTS.md`。

### Step 56 已修复内容

- `ChatAgent._query_events_result(...)` 新增 `source_query`，让聊天层能按原始提问筛选裂缝。
- `void_fissure` 查询优先使用 `EventTracker.get_active_fissures()` 的结构化数据，按纪元、任务类型和普通 / 钢铁模式过滤。
- 裂缝回答新增 `纪元 + 任务类型 + 普通/钢铁 + 节点 + 结束时间`，不再只依赖 `GameEvent.description`。
- 结构化裂缝为空时仍回退到原有事件格式化，保护缓存和旧行为。

### Step 56 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "void_fissure_query_filters_by_tier_and_mode or void_fissure_query_returns_structured_details_without_limited_events" -q --basetemp .pytest-tmp-step56-red -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "activity_query_returns_only_limited_events or specific_fissure_query_still_returns_fissures or void_fissure_query" -q --basetemp .pytest-tmp-step56-chat -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_events.py -k "limited or void_fissure or query_event_type or format_events_for_display" -q --basetemp .pytest-tmp-step56-events -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_tool_router.py -k "event or farming_route" -q --basetemp .pytest-tmp-step56-router -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "fissure_alert_natural_language" -q --basetemp .pytest-tmp-step56-fissure-alerts -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -q --basetemp .pytest-tmp-step56-chat-all -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_router.py::ReactLoopTests::test_chat_agent_react_query_events_uses_safe_compact_model_context -q --basetemp .pytest-tmp-step56-router-context -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/events.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
```

结果：红测先按预期 `2 failed`；修复后目标聊天回归 `4 passed, 72 deselected`；事件格式化回归 `4 passed, 21 deselected`；ToolRouter 事件 / farming route 回归 `3 passed, 34 deselected`；裂缝提醒守卫 `6 passed, 50 deselected`；`tests/test_chat.py` 全量 `76 passed`；ReAct query_events 安全上下文 `1 passed`；AST OK。

### Step 56 安全边界

- 本步未安装依赖、未下载文件、未上传 GitHub。
- 本步未新增或启用 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。
- 本步不改变 Step 55 的 UI Playwright 剩余验证状态；Step 56 自身目标测试已完成。

### 下一步准备

- 如果继续处理项目质量问题，仍优先回到 Step 55 的两个前端 Playwright 目标测试和完整 `pytest tests` 可写环境复跑。
- 如果要进一步对齐 Web 裂隙面板与聊天裂缝数据源，应另开任务评估 `warframestat.us /pc/fissures` 与官方 worldState 数据源差异。

## 2026-06-01 Step 57：活动与虚空商人回复体检执行

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-06-01 | Step 57 活动与虚空商人回复体检执行 | 100% | 已完成 | 已新增多问法回复矩阵，修复 Baro 库存措辞、限时活动过滤、Baro 后续污染普通市场查询和钢铁裂缝详情路由。 |

### Step 57 修改原因

- 修改原因：用户要求查看其他功能的用户回复是否存在问题，例如活动查询、虚空商人 MOD / 库存等，并考虑多种情况制定详细计划。
- 修改目标：建立多问法回复矩阵，覆盖泛活动、具体事件、Baro 状态、Baro MOD / 赋能价格、Baro 玩家链接追问、不支持活动和跨意图优先级，并只对红测证明的问题做最小修复。
- 影响范围：`warframe_agent/chat.py`、`warframe_agent/baro.py`、`tests/test_chat_event_replies.py`、Step 57 计划、Step 57 报告、`AGENTS.md`、`md/rebuilt/09-personal-agent-foundation.md`、`md/rebuilt/10-learning-route-audit.md`。

### Step 57 已修复内容

- `format_baro_report(...)` 现在明确说明虚空商人库存式问法只展示可分析的 Mod / 赋能，装饰和外观等非交易项暂不做价格分析。
- `热美亚裂缝`、`兽之腹`、尸鬼、利刃豺狼、巨人战舰等限时活动关键词优先按限时活动处理，不再被 `裂缝` 误抢为虚空裂缝。
- 具体限时活动问法会按请求标签过滤；例如 `热美亚裂缝现在有吗` 不再混入 `兽之腹`。
- Baro 后续玩家链接查询遇到新的直接市场物品时会让路；例如 Baro 查询后再问 `充沛最便宜卖家链接` 会返回充沛卖家，而不是旧 Baro 推荐。
- `钢铁歼灭现在有吗` 这类“任务类型 + 钢铁 / 纪元 / 裂缝”问法会走结构化虚空裂缝详情。

### Step 57 验证摘要

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py::test_baro_followup_does_not_hijack_later_market_link_query tests\test_chat_event_replies.py::test_event_keywords_do_not_hijack_market_relic_or_video_intents -q --basetemp .pytest-tmp-step57-red-extra -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py::test_baro_followup_does_not_hijack_later_market_link_query tests\test_chat_event_replies.py::test_event_keywords_do_not_hijack_market_relic_or_video_intents -q --basetemp .pytest-tmp-step57-green-extra -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py -q --basetemp .pytest-tmp-step57-event-replies-2 -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_baro.py tests\test_events.py tests\test_tool_router.py tests\test_chat_event_replies.py -q --basetemp .pytest-tmp-step57-focused-2 -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py tests\test_chat_memory_commands.py -k "activity or event or baro or resurgence or fissure" -q --basetemp .pytest-tmp-step57-chat-broad-2 -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/baro.py','warframe_agent/events.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
```

结果：补充红测修复前 `2 failed`；修复后对应红测 `2 passed`；Step57 回复矩阵 `10 passed`；Baro / events / ToolRouter / Step57 focused suites `83 passed`；聊天广义回归 `18 passed, 114 deselected`；AST OK。

### Step 57 安全边界

- 未安装依赖、未下载文件、未上传 GitHub。
- 未新增或启用 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。
- 未放宽 ToolRouter 安全策略，未新增高权限运行时能力。
- 子代理只作为探索 / 只读复核尝试；最后一个只读复核子代理因额度限制报错，没有作为最终证据。

### 下一步准备

- Step 57 已完成。若继续项目质量修复，仍优先处理 Step 55 遗留的两个前端 Playwright 目标测试和完整 `pytest tests` 可写环境复跑。
- 若要继续扩展活动数据源覆盖，应另开任务评估真实 World State 数据源差异，不在 Step 57 中启用新外部入口。

## 2026-06-01 Step 58：Step55 Playwright 与全量回归收尾

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-06-01 | Step 58 Step55 Playwright 与全量回归收尾 | 100% | 已完成 | 已关闭 Step55 遗留的两个前端 Playwright 目标测试和完整 `pytest tests` 复跑债务。 |

### Step 58 修改原因

- 修改原因：Step 55 已修复 6 个非 UI 失败并写入前端补丁，但两个 Playwright 目标用例与完整 `pytest tests` 尚未完成新一轮可验证复跑。
- 修改目标：先复现，再根据证据判断是环境启动失败、fixture 诊断不足、`chat.js` WebSocket / XSS 问题，还是 `chart.js` compare / chart XSS 问题；只对证据指向的范围做最小修复。
- 影响范围：计划文件、`AGENTS.md`、后续验证报告、`md/rebuilt`；只有在目标测试失败证据明确时，才修改 `tests/test_web_ui_playwright.py`、`warframe_agent/web/static/js/chat.js` 或 `warframe_agent/web/static/js/chart.js`。

### Step 58 完成标准

- `tests/test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message` 有新鲜运行结果。
- `tests/test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe` 有新鲜运行结果。
- 完整 `.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp-step58-full-final -p no:cacheprovider` 有新鲜运行结果。
- `AGENTS.md` 与 `md/rebuilt` 同步记录真实结果；若仍被环境阻塞，必须记录明确错误，不声称完成。

### Step 58 安全边界

- 本步不安装依赖、不下载文件到 C 盘、不上传 GitHub。
- 本步不新增或启用 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。
- 本步不放宽 XSS 断言，不允许 `img[data-xss]`、`data-xss`、事件属性或 raw HTML 回到 DOM。
- 子代理仅用于只读审查和风险定位；最终结论必须由主线程复核和验证。

### 下一步准备

- Step 55 的 Playwright / 全量回归债务已经关闭；后续项目质量任务应基于新的失败证据另开计划。

### Step 58 根因与修复

- 普通沙箱复现：两个 Playwright 目标测试仍在 setup 阶段失败于 `RuntimeError: Web server did not become ready`。
- 直接 uvicorn 诊断：导入 `warframe_agent.web.app` 时初始化 `TradeHistoryDB()`，执行 `PRAGMA journal_mode=WAL` 报 `sqlite3.OperationalError: unable to open database file`，确认普通沙箱失败是 SQLite WAL / 数据目录写入限制。
- 可写环境复现：两个目标测试进入浏览器断言，初次结果 `1 passed, 1 failed`；唯一失败是聊天消息 DOM 的 `data-raw` 属性仍保存转义后的 `data-xss` 文本。
- 最小修复：`warframe_agent/web/static/js/chat.js` 新增 `safeChatRawText(...)`，让 agent 消息 `data-raw`、WebSocket token 累积、done reply、direct reply 和 REST fallback reply 都保存剥离危险 inline HTML 后的安全文本。
- 未修改 `tests/test_web_ui_playwright.py`、`chart.js`、Step57 活动 / Baro 逻辑、ChatAgent 后端业务逻辑、ToolRouter 或 safety policy。

### Step 58 验证摘要

```powershell
node --check warframe_agent\web\static\js\chat.js
node --check warframe_agent\web\static\js\chart.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message tests\test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe -q --basetemp .pytest-tmp-step58-ui-targets-final -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp-step58-full-final -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/baro.py','warframe_agent/events.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
git diff --check -- AGENTS.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md githubProduct\personal_agent_warframe_migration_step58_step55_playwright_full_regression_closure_zh.md docs\superpowers\plans\2026-06-01-step55-playwright-full-regression-closure.md tests\test_web_ui_playwright.py warframe_agent\web\static\js\chat.js warframe_agent\web\static\js\chart.js
```

结果：JS 语法检查均退出码 0；两个 Step55 Playwright 目标测试 `2 passed in 28.70s`；完整全量回归 `1182 passed, 7 warnings in 331.32s`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

## 2026-06-01 GitHub 上传执行记录

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-06-01 | 上传当前项目成果到 GitHub personal 远端 | 100% | 已完成 | 按用户要求准备将项目源码、测试、计划、报告、`md/rebuilt` 与 `AGENTS.md` 推送到 `personal` 远端；不包含运行期 `data` 文件、`.pytest-tmp*` 临时目录和外部参考项目删除记录。 |

### 上传范围

- 包含：`warframe_agent/`、`tests/`、`tools/`、`docs/superpowers/plans/`、`docs/superpowers/specs/` 中现存计划/规格、`githubProduct/*.md`、`githubProduct/*.json`、`md/rebuilt/`、`AGENTS.md`、`requirements.txt`。
- 排除：`data/agent_memory.json` 等运行期数据、`data/video_parse_drafts.jsonl`、`.pytest-tmp*` 临时目录、下载参考仓库目录的删除记录和子模块状态变化。
- 远端：`personal`，地址为 `git@github.com:yahuhu547-droid/personal-WarFrameAgent.git`。

### 上传前验证

- Step 58 已完成：两个 Step55 Playwright 目标测试 `2 passed in 28.70s`，完整 `pytest tests` 为 `1182 passed, 7 warnings in 331.32s`。
- 普通沙箱访问 GitHub SSH 被拒绝，已在沙箱外验证 `git ls-remote personal HEAD` 可访问。
