# 06. 工具系统、多模型协作与安全边界

本文说明 Agent 如何选择工具、调用模型，以及如何处理外部不可信数据。

## 1. 工具注册系统

关键文件：`warframe_agent/tool_registry.py`。

### 核心结构

| 结构 | 说明 |
|---|---|
| `ToolSpec` | 工具定义，包括名称、描述、参数、handler、skill、安全等级、副作用和上下文策略。 |
| `ToolExecutionMetadata` | 工具执行元数据。 |
| `ToolResult` | 统一工具返回对象。 |
| `ToolRegistry` | 注册、查找、执行工具。 |

### 已注册工具范围

- `query_price`
- `query_set`
- `query_missing_parts`
- `scan_favorites`
- `set_alert`
- `price_trend`
- `general_chat`
- `mod_flipper`
- `set_profit`
- `investment_advisor`
- `plan`
- `query_events`
- `deep_analysis`
- `market_expert`
- `riven_expert`
- `event_expert`
- `riven_search`
- `relic_value`

基础配卡攻略查询不是模型专家工具；当前由 `ChatAgent` 基于 `data/bilibili_recommendations.json` 的本地 curated/fallback 数据确定性返回视频链接，支持按具体武器、主武器/副武器/近战类别、具体战甲名/别名，以及宠物/同伴/守护/猎犬/恐鸟类别推荐。具体战甲名查询必须命中 `warframes` 或具体别名，具体宠物名查询必须命中 `companions` 或具体别名，不能只靠“战甲”或“宠物/同伴”类别泛匹配；排序优先使用匹配分、`priority` 和 `updated_at`，让当前版本、近期、观看较多或标题更具体的视频排在前面。第一阶段只处理配卡、攻略、视频推荐，不处理流派选择、枪架子、战甲适配或紫卡属性主观判断；`build_expert`、`guide_expert`、`activity_expert` 已移除。

视频画面解析是离线维护能力，不接入普通问答的可信结论路径：`warframe_agent/video_analysis/` 只生成 `data/video_parse_drafts.jsonl` 草稿，由 OCR 读文字、ImageHash/OpenCV 做图标候选、YOLO 或固定区域定位提供候选框，VLM 只能辅助说明画面类型；视频链接和标题可先入库，但所有 MOD、赋能、特殊槽和灵化阶段选择都必须先给用户过目确认，确认前保持 `needs_review: true` / `trusted_for_agent_answers: false`。`tools/review_bilibili_recommendations_with_models.py` 的多模型复核只允许提出标题、BVID、URL、武器名和别名建议；已确认合集的分类以合集来源为准，建议默认不可信且 `approved: false`。

### 执行能力

- required 参数校验。
- handler 绑定。
- 异常捕获。
- 统一 `ToolResult` 返回。
- 执行元数据记录。
- 敏感参数摘要脱敏。
- 成功结果压缩为模型上下文。
- `list_tools` / `list_tool_schemas` 支持按候选工具名或 skill 过滤。
- `candidate_names()` 默认排除外部副作用工具。

工具 skill 目前覆盖 `market_price`、`prime_set`、`monitoring`、`events`、`trading_analysis`、`riven`、`planning` 和 `general`。安全等级用于区分 `read_only`、`local_state_write`、`external_side_effect` 和 `model_only`。

## 2. 工具路由和 ReAct

关键文件：`warframe_agent/tool_router.py`。

能力：

- 构建 router prompt。
- 按用户消息选择候选工具，默认常见意图不超过 6 个工具。
- 只把候选工具 schema 暴露给模型，低置信度时回退核心只读工具。
- 解析 LLM 返回的工具调用，并拒绝候选集外工具。
- 执行单步工具或多轮 ReAct。
- 限制最大工具迭代次数。
- 支持多步骤 `plan`。
- 最近一次 ReAct 会在 `ChatAgent.last_agent_trace` 中保留内存诊断对象；`AgentTrace` 现在包含轻量 AgentRun 生命周期字段（`status`、`started_at`、`ended_at`、`max_iterations`、`duration_ms`），并在现有 `plan` 工具被调用时挂载只读 `AgentPlanSnapshot`。运行态 API 只序列化安全快照，不持久化完整 trace 或 plan。

常见路由目标：

- 单物品价格查询。
- Prime 套装查询。
- 缺件查询。
- Mod/赋能倒卖。
- 套装套利。
- 投资顾问。
- 活动查询。
- 价格趋势。
- 紫卡查询。
- 通用聊天。

## 3. ChatAgent 的确定性优先策略

`warframe_agent/chat.py` 会优先处理确定性场景：

- Slash Command。
- 紫卡 fast path 和追问。
- Baro 查询和追问。
- Prime 套装、部件、缺件。
- 市场链接、最低卖家、砍价等实时交易辅助；这些回复应走确定性订单数据路径，不交给 LLM 编造。
- 活动、裂缝、周期、Prime 重生、Vault。
- 基础配卡攻略查询会在适用时追加本地 curated B 站视频链接推荐；“主武器/副武器/近战配卡视频”“战甲攻略视频”和“宠物/同伴/守护/猎犬/恐鸟攻略视频”会按本地 `category` 分类返回，不依赖实时网页抓取；“夜灵配卡”“毒妈攻略视频”这类具体战甲问题必须命中具体 `warframes` 或别名，“铁甲狐配卡”“死亡魔方同伴配卡”这类具体宠物问题必须命中具体同伴名或别名；泛泛的“怎么玩”不自动触发配卡视频推荐。
- 关注、提醒、收藏、交易记录。
- 价格趋势和历史。

只有当确定性规则或工具无法覆盖时，才构造上下文并调用 LLM 进行综合回答。

## 4. 多模型架构

### 本地模型

关键文件：`warframe_agent/llm.py`。

用途：

- 本地 Ollama chat。
- 流式输出。
- embedding。
- 物品名解析。
- 低复杂度问答。

### 云端模型

同样由 `warframe_agent/llm.py` 和 `warframe_agent/model_orchestrator.py` 统一调用。

特点：

- 使用 OpenAI 兼容 API。
- 支持同步和异步流式。
- 支持按任务指定模型。
- 云端失败可回退本地。
- 内置 TTL 缓存。

### 模型路由

关键文件：`warframe_agent/model_orchestrator.py`。

路由规则：

1. request 明确指定 `local` 或 `cloud` 时强制路由。
2. scout 任务命中指定模型且云端 key 可用时使用云端模型。
3. 全局 `MODEL_ROUTING` 可配置为 `local`、`cloud` 或 `auto`。
4. `auto` 模式按复杂度阈值决定本地或云端。
5. 云端失败时回退本地。

### Scout 预筛选

关键文件：`warframe_agent/scout.py`。

| 任务 | 默认模型用途 |
|---|---|
| Mod/赋能倒卖 | 预筛选高流动性、高 ROI 候选。 |
| 套装套利 | 预筛选 Prime 套装候选。 |
| 投资顾问 | 预筛选预算内投资机会；缺省预算/ROI 从个人偏好读取，显式工具参数优先。 |
| B 站候选复核 | 对待复核视频标题提出武器名和别名建议；已确认合集分类直接沿用来源分类，默认不入库。 |

Scout 会结合事件上下文、用户偏好、价格趋势，并记录反馈用于统计准确率。B 站候选复核通过本地 OpenAI-compatible 中转站调用第三方模型时，应优先使用 `CLOUD_API_BASE=http://localhost:8080`，失败再尝试 `/v1`；API Key 只通过环境变量提供，不写入项目文件。

### 专家子代理

关键文件：`warframe_agent/experts.py`。

专家域：

- `market`
- `riven`
- `event`

约束：

- 只做分析和综合。
- 不执行工具。
- 不做状态变更。
- 外部数据只作为事实候选材料。
- 禁止输出玩家名、profile 链接和 `/w` 私聊命令。

## 5. 工具上下文安全

关键文件：`warframe_agent/tool_context.py`。

### 需要防护的风险

- 外部 API 返回内容中的 prompt injection。
- 玩家名、profile、私聊命令被错误暴露给模型。
- API Key、token、cookie、authorization 等敏感字段泄漏。
- 工具结果过长导致上下文污染或成本过高。

### 已实现能力

| 能力 | 说明 |
|---|---|
| 敏感字段脱敏 | password、token、secret、api_key、apikey、authorization、cookie 等。 |
| Bearer token 脱敏 | 清洗 Authorization 类文本。 |
| 控制字符清理 | 移除不可见控制字符。 |
| 角色前缀中和 | 中和 `system:`、`developer:`、`assistant:`、`user:`、`tool:` 等前缀。 |
| XML 角色标签中和 | 中和伪造角色标签。 |
| JSON tool 字段中和 | 降低工具调用注入风险。 |
| 代码围栏替换 | 降低外部内容影响 prompt 结构的风险。 |
| 不可信数据包裹 | 明确标记外部模型文本或外部 API 文本。 |
| 工具结果压缩 | 按字符数和行数限制。 |
| plan 预算控制 | 多步骤计划结果按总预算截断。 |
| 参数摘要过滤 | 过滤内部上下文字段和敏感参数。 |

## 6. 用户展示与模型上下文分离

| 场景 | 用户展示 | 模型上下文 |
|---|---|---|
| 普通市场订单 | 可展示价格、买卖方向、必要的玩家交易信息。 | 只给价格、数量、趋势和匿名摘要。 |
| 交易机会工具 | 可展示 `trade_plan`：买入/卖出步骤、玩家名、quantity、subtotal、market/profile 链接和 `/w`；赋能按 R0 数量聚合买入，Prime 只展示当前盈利策略路径，并可展示 ROI、流动性、风险等级和机会分数。 | 只给 safe summary 和聚合指标：source、strategy、item_id、required_quantity、total_cost、total_revenue、profit、ROI、成交量、风险、profit_bucket、签名、机会分数、流动性和供需步骤数，不给玩家名、market URL、profile、私聊命令或 raw orders。 |
| Riven 拍卖 | 可展示卖家、价格、私聊命令、属性评分、价格位置、置信度和“当前挂牌参考”提示。 | 不给玩家名、profile、私聊命令、auction id 或 raw auction；只给匿名价格、属性、评分、价格位置、置信度，并明确不代表真实成交价。 |
| 遗物价值 | 可展示奖励、掉率、最低卖价、最高收价、杜卡德值、期望白金和期望杜卡德。 | 只给 market_id、价格聚合、掉率、杜卡德、EV 和建议；不给玩家名、profile、whisper 或 raw order。 |
| Baro 推荐详情 | 可展示买家/卖家、ranked whisper。 | 不给玩家标识和私聊命令。 |
| 记忆召回 | 可在 Web 展示安全 trace。 | 只给清洗后的事实摘要和 trace，不给原始 query/reply。 |
| 运行态/工具调用 | 可展示 job、task、tool_name、ok、duration、安全 args summary、聚合统计、`safety_policy` 能力边界、ToolRegistry 聚合分布，以及最近 Agent Trace 的 status、termination_reason、开始/结束时间、最大轮次、迭代次数、result_chars、has_result、error_present 和只读 AgentPlan 步骤状态。 | 不给密钥、消息内容、完整 traceback、外部原始响应、final_answer 原文、raw_arguments、完整 result_summary、工具错误正文、Push token、UID、Feishu app_secret、chat_id、工具 handler、工具参数 schema 或 ToolResult。 |
| 专家分析 | 用户只看综合建议。 | 输入必须是清洗过的事实候选。 |
| 视频解析草稿 | 仅维护者查看帧、区域、OCR 和图标候选。 | 不进入模型上下文；人工确认前不得作为事实材料。 |

### 运行态安全策略快照

关键文件：`warframe_agent/safety_policy.py`。

`/api/runtime/status` 返回的 `safety_policy` 是只读快照，不是能力开关。当前默认策略：

- `shell`、`generic_file_write`、`browser_private_network`、`arbitrary_scheduler` 均为 `disabled`，需要未来显式设计后才能开启。
- `browser_gui_automation` 为 `disabled`，当前只暴露 `browser_gui_policy` 行为矩阵，不暴露任何 Browser/GUI executor。
- `voice_companion_experience` 为 `disabled`，当前只暴露 `companion_experience_policy` 体验边界，不暴露语音、麦克风、录音、Live2D 或后台监听 executor。
- `market_network` 为 `read_only`，只覆盖 warframe.market 和游戏数据读取。
- `project_data_write` 为 `restricted`，只覆盖已有项目数据 API，例如记忆、偏好、提醒和配置。
- `scheduler_jobs` 只反映已注册任务是否运行，不允许任意创建任务。
- `external_push` 只反映 Feishu/WxPusher 是否配置启用，不返回 token、UID、app_secret 或 chat_id。
- `multi_channel_gateway` 为 `restricted`，当前只说明 Web chat、WebSocket、local CLI、Feishu 和 WxPusher 的入口 / 出口边界，不新增任何真实平台连接器。
- `skills_plugin_ecosystem` 为 `guidance_only`，当前只说明 skills / plugins / connectors 的审查边界，不安装或启用插件。
- `tool_registry` 只反映聚合安全统计：工具总数、schema 暴露/隐藏数量、副作用工具数量，以及 `safety_level`、`skill`、`context_policy` 计数；不返回单个工具名、description、parameters、handler 或执行结果。

### 多渠道 Gateway 边界

关键文件：`warframe_agent/gateway_policy.py`。

该边界借鉴 CowAgent / Suna / OpenClaw 的多入口个人 Agent 思路，但当前只输出只读策略矩阵，不启用新平台账号、Webhook handler、社交抓取或后台监听。`/api/runtime/status.safety_policy.gateway_policy` 用于说明入口信任边界：

| 决策 | 行为 | 当前处理 |
|---|---|---|
| `allow_interactive_chat` | Web chat、WebSocket chat、local CLI 的用户主动输入。 | 允许进入现有聊天路径。 |
| `requires_existing_confirmation_flow` | 已配置的 Feishu bot 入站消息。 | 必须复用现有确认式任务和写入链路。 |
| `allow_outbound_notification` | WxPusher / Feishu push 出站通知。 | 只作为通知出口，不作为入站命令入口。 |
| `blocked_public_or_anonymous_inbound` | Bilibili 评论、匿名 webhook、GitHub issue、卖家 / 买家私信。 | 默认阻断。 |
| `blocked_sensitive_action` | 任意工具执行、shell、浏览器控制、文件写入、下单、私信等动作。 | 默认阻断。 |

policy 输出只包含 channel、action、decision、trust boundary、reason 和安全摘要，不返回 raw payload、handler、token、secret、app_secret、chat_id、玩家名、profile URL 或 `/w`。

未来如果真的开放外部入口，必须另开步骤，并先设计鉴权、绑定用户、可撤销授权、速率限制、用户确认、可中断和审计摘要。

### Skills / Plugin 生态边界

关键文件：`warframe_agent/plugin_policy.py`。

该边界借鉴 OpenManus / Suna / OpenClaw / Codex skills 的可扩展能力生态，但当前只输出只读策略矩阵，不安装插件、不请求 plugin install、不启用外部账号 connector，也不把插件能力自动映射到 ToolRegistry。`/api/runtime/status.safety_policy.plugin_policy` 用于说明扩展能力边界：

| 决策 | 行为 | 当前处理 |
|---|---|---|
| `allow_guidance_only` | local / system / project skills 的 prompt、workflow、template 指导。 | 只作为上下文指导，不作为运行时工具。 |
| `requires_review` | personal / Codex / local plugin 的 tool provider、UI extension、MCP server、resource provider。 | 需要人工 review 后才能设计 ToolRegistry 映射。 |
| `requires_explicit_enable` | 外部 connector 的账号访问、外部 API、平台读取。 | 必须显式启用并经用户确认。 |
| `blocked_high_risk_capability` | shell、文件写入、浏览器控制、scheduler 创建、凭据访问、社交发帖、交易动作。 | 默认阻断。 |
| `blocked_unknown_capability` | 未知插件或未知能力。 | 默认阻断。 |

policy 输出只包含 source、capability、decision、trust boundary、reason 和安全摘要，不返回 raw manifest、handler、params、token、secret、api_key、account_id、真实本机路径或用户账号标识。

未来如果真的启用插件或 connector，必须另开步骤，并先设计 manifest 审查、权限白名单、ToolRegistry metadata、AgentPlan review、用户确认和撤销机制。

### Browser / GUI Agent 安全边界

关键文件：`warframe_agent/browser_gui_safety.py`。

该边界借鉴 OpenManus / Open-AutoGLM，但当前不启用 Browser Agent、Playwright executor、ADB/HDC 或任意 GUI 控制工具。`/api/runtime/status.safety_policy.browser_gui_policy` 只用于说明未来行为分类：

| 决策 | 行为 | 当前处理 |
|---|---|---|
| `allow_read_only` | 公共页面读取、文本提取、截图、DOM 检查。 | 只作为未来候选；当前没有 executor。 |
| `requires_human_confirmation` | 点击、输入、提交表单、下载、上传、剪贴板写入。 | 必须先有人类确认和专门流程设计。 |
| `blocked` | 登录、支付、删除、私信、下单、凭据输入、任意脚本、私网目标。 | 默认阻断。 |

当前 policy 输出只包含动作类别、目标范围、决策、是否需要人工确认、是否 blocked 和 reason。它不返回真实 URL、URL query、cookie、localStorage、sessionStorage、DOM 原文、截图 OCR、账号名、玩家 profile、`/w`、token、secret、Authorization 或 raw arguments。

未来如果真的接入 Browser/GUI 自动化，必须另开步骤，并先设计“软拦截 -> 用户确认 -> 受控执行 -> 可中断/可复盘”的链路。

### 语音和陪伴式体验安全边界

关键文件：`warframe_agent/companion_experience.py`。

该边界借鉴 EchoBot / OpenHuman / OpenClaw，但当前不启用真实语音服务、TTS/STT、麦克风、录音、Live2D、平台 token 或后台监听。`/api/runtime/status.safety_policy.companion_experience_policy` 只用于说明体验分类：

| 决策 | 行为 | 当前处理 |
|---|---|---|
| `allow_text_only` | 文本陪伴、轻量鼓励、心态复盘。 | 留在普通聊天路径，不新增语音运行时。 |
| `requires_existing_confirmation_flow` | “陪我刷图并后台盯价提醒”这类陪伴式后台任务。 | 只能复用已有提醒、任务和用户确认流程。 |
| `blocked_unavailable_runtime` | 语音回复、麦克风、录音、Live2D、后台监听。 | 默认阻断，直到另开设计。 |
| `blocked_sensitive_action` | 私聊卖家、下单、联系买家等交易动作。 | 默认阻断，不因“陪伴”措辞放行。 |
| `route_general_chat` | Warframe 游戏内同伴、宠物、守护、库娃、库狛攻略。 | 作为普通游戏建议，不当作语音陪伴入口。 |

当前 policy 输出只包含类别、决策、是否需要人工确认、是否 blocked、reason 和安全标签。它不返回原始消息、玩家名、profile、`/w`、token、音频 URL、录音路径、平台凭据或对话全文。

未来如果真的接入语音或 Live2D，必须另开步骤，并先设计“显式开启 -> 麦克风/录音权限确认 -> 可中断 -> 不落盘原始音频 -> 安全摘要入记忆”的链路。

## 7. 配置项范围

关键文件：`warframe_agent/config.py`。

包含：

- 本地模型名。
- Router 模型名。
- 云端 API base。
- 云端 API key。
- 云端模型。
- 模型路由策略。
- ReAct 最大迭代次数。
- 工具上下文最大字符数。
- plan 上下文预算。
- scout 模型配置。
- embedding 配置。

配置文档只应说明字段用途，不应写入真实密钥。
### AgentPlan 受控执行确认

关键文件：`warframe_agent/tool_router.py`。

Step 41 在 Step 35 的计划审查基础上新增第一阶段确认门禁：

- `build_plan_confirmation_request(...)` 只为全部 issue 都是 `missing_verification` 的只读计划生成确认请求。
- 确认码绑定当前 plan 的 `goal`、每一步 `tool`、`arguments`、`purpose` 和原始阻断原因；plan 改动后旧确认码失效。
- `react_loop(..., plan_confirmation_token=...)` 只有在确认码匹配后才会重新以 `require_verification=False` review，并在 relaxed review 通过后执行。
- 确认执行后 `trace.plan.verification_note` 会记录 `plan_review=confirmed`，用于运行态审计。

不可确认执行的阻断原因：

| blocked_reason | 处理 |
|---|---|
| `unknown_tool` | 不生成确认码，不执行。 |
| `non_exposed_tool` | 不生成确认码，不执行。 |
| `side_effect_tool` | 不生成确认码，不执行。 |
| `sensitive_arguments` | 不生成确认码，不执行。 |

本能力不新增 Web UI、pending plan 持久化、Browser/GUI/shell/scheduler executor，也不允许私信、下单、登录、支付、删除、凭据输入或 `set_alert` 等副作用动作通过确认码执行。

### ChatAgent 计划确认闭环

关键文件：`warframe_agent/chat.py`、`warframe_agent/tool_router.py`。

Step 42 把 Step 41 的底层确认码接入聊天层，但不把确认码展示给用户：
- `ChatAgent` 只在 `ToolRouter` 返回 `confirmation_required=true`、`confirmable_reason=missing_verification` 且 trace review 阻断原因一致时保存 `PendingAgentPlanConfirmation`。
- pending 状态只保存原始用户消息、候选工具名、阻断原因和确认码；不保存 raw plan、raw tool args、raw result、玩家名、profile、`/w`、token、secret 或 Authorization。
- 用户必须回复明确短语“确认执行 / 执行计划 / 确认计划 / 继续执行 / 确认运行”才会触发重新审查并执行；普通“确认”不触发，避免误用其他确认入口。
- “取消执行 / 取消计划 / 不执行 / 不执行计划 / 放弃执行”会清空 pending plan，不执行任何步骤。

当前能力仍然只覆盖 `missing_verification` 的只读计划。`side_effect_tool`、`sensitive_arguments`、`unknown_tool` 和 `non_exposed_tool` 继续硬拦；本步不新增 Web UI 按钮、Browser/GUI/shell/scheduler executor、语音服务、TTS/STT、麦克风、录音、Live2D 或后台监听。

### 未来高权限能力准入策略

关键文件：`warframe_agent/future_capability_policy.py`、`warframe_agent/safety_policy.py`。

Step 48 新增只读 `future_capability_policy`，用于把未来高权限候选能力先纳入准入矩阵，而不是直接进入 ToolRegistry 或运行时。它只提供分类和安全摘要，不注册 handler，不安装插件，不启用 connector，不启动后台 worker。

当前分类：

| decision | 适用能力 | 当前处理 |
|---|---|---|
| `allow_design_only` | 设计文档、权限设计、风险评审 | 允许做文档，不启用 runtime |
| `requires_new_stage_design` | Browser/GUI executor、服务恢复、任意触发器、plugin install、connector enable | 必须另开新阶段设计 |
| `frozen_by_current_user_instruction` | 真实语音、TTS/STT、麦克风、录音、Live2D、后台监听 | 按用户当前指令冻结 |
| `blocked_public_or_private_inbound` | 匿名 webhook、公共评论命令、买家 / 卖家 / 平台私信命令 | 默认阻断 |
| `blocked_uncontrolled_runtime` | shell、通用文件写入、凭据访问、社交发帖、交易动作 | 默认阻断 |

`build_runtime_safety_policy(...)` 中的 `capabilities.future_capability_admission` 只表示准入策略可见，`enabled=False` 表示未来高权限运行时能力没有启用。policy 输出会过滤 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_manifest、raw_arguments、handler、params、profile、`/w`、本机路径和私网地址；疑似敏感的 capability 名会归一为 `unknown_future_capability`。

这一步不改变既有模型调用边界：所有云端 AI 仍必须通过 `ModelOrchestrator` / `llm.py`，不得在新策略或 helper 中读取 `.env`、拼接 API header 或绕过模型编排。

### Future Capability Runtime 可见性

关键文件：`warframe_agent/web/static/js/app.js`、`tests/test_web_ui_playwright.py`、`tests/test_web_api.py`。

Step 49 把 Step 48 的 `future_capability_policy` 展示到 Runtime 面板。展示内容包括 `future_capability_admission`、`design_required_before_runtime`、`runtime_enablement_allowed=false`、决策分布，以及最多 8 条 `capability_matrix` 安全条目。

本展示继续是只读控制面：

- `future_capability_admission.enabled=False` 表示策略可见，不代表未来高权限运行时入口已启用。
- 不新增按钮、开关、安装入口、账号输入、webhook、DM 命令入口、connector 启用入口或后台 worker。
- 不注册 ToolRegistry 工具，不新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable 或真实语音能力。
- 真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续按用户当前指令冻结。

前端安全过滤在原有基础上补充 `credential`、`user_id`、`private_network_url`、`local_path`、`raw_plan`、`raw_config`、`webhook_secret` 和 `connector_token` 等未来高权限场景相关形态。Runtime 面板不渲染 token、secret、password、api_key、authorization、cookie、account_id、raw payload / manifest / arguments / plan、handler、params、profile、`/w`、本机路径或私网地址。

### 学习借鉴与改善完成快照

关键文件：`warframe_agent/learning_completion.py`、`warframe_agent/web/app.py`、`warframe_agent/web/static/js/app.js`。

Step 50 新增只读 `learning_completion` 快照，用于在 `/api/runtime/status` 和 Runtime 面板中明确展示：旧的 GitHub 项目个人 Agent 非语音学习借鉴计划已经完成，Step 48 / Step 49 的安全准入和 Runtime 可见性改善也已完成。

该快照只包含安全聚合字段：完成状态、已完成步骤 ID、改善步骤 ID、冻结面、下一阶段需另开设计的高权限能力和 guardrails。它不读取 `.env`，不扫描 raw 文档，不返回 raw diff、raw conversation、玩家名、私信、token、secret、api_key、account_id、handler、params、本机私密路径或私网地址。

安全边界不变：不注册 ToolRegistry 工具，不新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、后台 worker 或真实语音能力。`future_capability_admission.enabled=False` 保持不变；真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续冻结。

验证摘要：Step 50 的只读快照单元测试为 `3 passed`，Web API 可写环境补跑为 `2 passed, 70 deselected`，Runtime 面板 Playwright 可写环境补跑为 `1 passed`；最终 policy / gateway / plugin / runtime safety 联跑为 `23 passed, 33 deselected`，AST / JS / diff 复核均通过。

## 2026-05-31 追加：学习完成验收清单快照

关键文件：`warframe_agent/learning_completion.py`、`warframe_agent/web/static/js/app.js`。

Step 51 在既有只读 `learning_completion` 快照中新增 `acceptance_status=accepted` 和 `acceptance_snapshot`。该验收清单只包含安全聚合字段，用于说明旧非语音学习路线完成、Step 48 / Step 49 改善完成、Runtime API / UI 已暴露完成态、高权限运行时未启用、真实语音继续冻结、未来高权限能力必须另开设计。

安全边界不变：不新增端点、按钮、开关、ToolRegistry 工具、Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、后台 worker 或真实语音能力。验收快照不读取 `.env`，不返回 token、secret、api_key、account_id、raw_payload、raw_plan、handler、params、本机私密路径或私网地址。

验证摘要：单元红测按预期失败于缺少 acceptance 字段；实现后 `tests/test_learning_completion.py` 为 `5 passed`，Web API 可写环境补跑 `2 passed, 70 deselected`，Runtime 面板 Playwright 可写环境补跑 `1 passed`，Runtime 静态契约 `1 passed`，JS 语法检查通过。最终 policy / gateway / plugin / runtime safety 联跑 `25 passed, 33 deselected`，AST / JS / diff 复核均通过。
