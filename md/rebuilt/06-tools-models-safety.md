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

攻略视频推荐不是模型专家工具，也不在用户提问时实时抓取 B 站；它是 `ChatAgent` 基于 `data/bilibili_recommendations.json` 的本地 curated 确定性能力，支持按具体武器或主武器/副武器/近战类别推荐；`build_expert`、`guide_expert`、`activity_expert` 已移除。

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
- 攻略、配卡、打法类问题会在适用时追加本地 curated B 站视频链接推荐；“主武器/副武器/近战配卡视频”会按本地 `category` 分类返回，不依赖实时网页抓取。
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
| 投资顾问 | 预筛选预算内投资机会。 |

Scout 会结合事件上下文、用户偏好、价格趋势，并记录反馈用于统计准确率。

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
| 运行态/工具调用 | 可展示 job、task、tool_name、ok、duration、安全 args summary 和聚合统计。 | 不给密钥、消息内容、完整 traceback 或外部原始响应。 |
| 专家分析 | 用户只看综合建议。 | 输入必须是清洗过的事实候选。 |

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
