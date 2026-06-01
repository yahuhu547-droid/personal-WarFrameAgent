# 05. 数据、缓存与记忆系统

本项目同时使用静态数据、外部 API 缓存、JSON 长期记忆、SQLite 历史库和 JSONL 对话日志。

## 1. 静态和构建数据

| 文件/目录 | 用途 |
|---|---|
| `data/items_full.json` | 物品全量数据，Prime 分组、名称解析、市场查询的重要基础。 |
| `data/rag_items.jsonl` | RAG 检索语料。 |
| `data/generated_aliases.json` | 生成别名。 |
| `data/item_dictionary_cache.json` | 物品字典缓存。 |
| `data/item_aliases.json` | 手工或基础别名。 |
| `data/custom_aliases.json` | Web/API 可维护的自定义别名。 |
| `data/ducat_values.json` | 杜卡特价值。 |
| `data/relics_list.json` | 遗物列表。 |
| `data/relics_drop_data.json` | 遗物掉落。 |
| `data/relic_vault_status.json` | 遗物封存状态。 |
| `data/relic_sources.json` | 遗物来源；刷取路线推荐会读取它来说明某遗物可从哪些任务获得。 |
| `data/bilibili_recommendations.json` | 基础配卡攻略查询的本地 fallback 视频库；可先保存标题、BVID、URL、分类、武器名、战甲名、同伴名、别名和优先级等视频元数据。 |
| `data/video_parse_drafts.jsonl` | 视频画面解析草稿；MOD、赋能、灵化选择等识别结果默认只是候选，需用户过目确认后才能写入可信数据。 |
| `Extra Resource/exports/bilibili_metadata/fallback_inventory_report.json` | B 站候选元数据与正式推荐库的覆盖报告，列出已入库、自动可入库和需复核视频。 |
| `Extra Resource/exports/bilibili_metadata/bilibili_recommendation_candidates.json` | 从候选元数据生成的推荐记录草稿；`needs_review: true` 的候选不进入正式推荐结果。 |
| `Extra Resource/exports/bilibili_metadata/bilibili_recommendation_model_suggestions.json` | 多模型复核建议；合集来源分类视为可信，模型只辅助提取武器名和别名；默认 `approved: false`，只有人工改为 `approved: true` 后才能被应用为视频元数据。 |
| `Extra Resource/exports/bilibili_metadata/companion_build_links_final.json` | 已通过搜索筛选的宠物/同伴/守护/猎犬/恐鸟视频清单；可由构建工具转成 `category: companion` 的正式推荐记录。 |
| `Extra Resource/exports/bilibili_metadata/companion_build_import_report.json` | companion 视频导入报告，记录最终清单中自动入库、待复核和已追加 BVID。 |
| `Extra Resource/exports/bilibili_metadata/warframe_search_results.json` | 战甲视频首批搜索/合集元数据；当前由本地 B 站“战甲合集”导出生成，实时 Playwright 搜索网络可用后可扩展覆盖。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_links_curated.json` | 战甲视频筛选清单；只保留标题、BVID、URL、作者、播放量文本等视频元数据。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_links_final.json` | 战甲视频最终清单；可由构建工具转成 `category: warframe`、`warframes`、`aliases`、`priority` 的正式推荐记录。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_import_report.json` | warframe 视频导入报告，记录最终清单中自动入库、待复核和已追加 BVID。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_candidates.json` | 战甲视频导入生成的推荐记录候选。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_review_summary.json` | 战甲视频导入的复核摘要；`needs_review_new_count` 应为 0 后才作为正式问答依据。 |
| `tools/build_bilibili_recommendations.py` | 可重复生成 B 站 fallback 覆盖报告和推荐记录候选；只有显式 `--append-approved` 或应用人工确认建议才会追加视频链接元数据。 |
| `tools/review_bilibili_recommendations_with_models.py` | 使用多模型对待复核候选生成武器名/分类/别名建议；不修改正式推荐库。 |

相关构建工具：

- `tools/build_item_data.py`
- `tools/build_ollama_model.py`
- `tools/build_embeddings.py`
- `tools/generate_training_data.py`
- `tools/merge_training_data.py`
- `tools/finetune.py`
- `tools/rebuild_ollama_model.py`

### B 站配卡数据确认边界

- 视频链接、标题、BVID、分类、武器名和别名属于视频元数据，可以先写入 `data/bilibili_recommendations.json` 作为本地兜底。
- 宠物/同伴/守护/猎犬/恐鸟最终筛选清单可写入 `companions`、`aliases`、`category: companion`、`priority` 和 `updated_at`；具体宠物问题必须靠具体同伴名或别名命中，不能只靠“宠物/同伴”泛类别命中。
- 战甲最终筛选清单可写入 `warframes`、`aliases`、`category: warframe`、`priority` 和 `updated_at`；具体战甲问题必须靠具体战甲名或别名命中，不能只靠“战甲”泛类别命中。当前首批战甲数据来自本地已抓取的 B 站“战甲合集”，只代表视频链接元数据，不代表 MOD/赋能/灵化配置已可信。
- 从画面 OCR/图像识别提取出的 MOD、赋能、特殊槽、灵化阶段选择只能先进入草稿或候选结果。
- 候选结果必须保持 `needs_review: true` 和 `trusted_for_agent_answers: false`，直到用户过目确认。
- 多模型复核只能生成视频元数据建议；已确认合集的主手/副手/近战分类以合集来源为准，模型不重新否决分类；建议默认 `approved: false`，不得直接进入 Agent 回答或正式推荐库。
- 未确认候选不得作为长期可信知识或确定性配卡结论注入普通问答。

## 2. 外部 API 缓存

| 缓存 | 用途 | 相关模块 |
|---|---|---|
| `data/price_cache.db` | warframe.market 价格缓存。 | `warframe_agent/market.py` |
| `data/game_events_cache.json` | 世界状态解析缓存。 | `warframe_agent/events.py` |
| `data/worldstate_raw.json` | 原始世界状态数据。 | `warframe_agent/events.py` |

`market.py` 还包含内存缓存和速率限制，用于减少重复请求和外部 API 压力。

## 3. Agent 长期记忆

实现文件：`warframe_agent/memory.py`。

默认数据文件：`data/agent_memory.json`。

### 主要数据结构

| 结构 | 内容 |
|---|---|
| `UserProfile` | 用户画像。 |
| `TradingPreferences` | 交易偏好。 |
| `PriceAlert` | 价格提醒。 |
| `WatchItem` | 关注物品。 |
| `FissureAlert` | 裂缝订阅。 |
| `CycleAlert` | 开放世界周期订阅。 |
| `ProactiveSuggestion` | 主动建议记录。 |
| `AgentMemory` | 统一记忆对象。 |

### 记忆内容

- 收藏物品。
- 价格提醒。
- 交易偏好；`TradingPreferences.opportunity_filter` 支持 `all`、`mod`、`arcane`，用于控制交易机会检测范围。
- 个人交易画像偏好：风险、预算区间、偏好品类、可接受周转和最低 ROI；`budget_max` 和 `min_roi_pct` 会作为投资顾问缺省扫描参数，只有聊天工具参数或 Web query 显式传值时才被覆盖。
- 关注列表。
- 最近主动建议；`ProactiveSuggestion.data` 保存机会来源、策略、利润、ROI、rationale、`dedupe_key`、`profit_bucket` 和 `plan_signature` 等结构化字段。扫描内去重优先使用 `dedupe_key`，否则按 item、suggestion_type、source、strategy 区分，避免同一物品不同来源/策略的机会互相覆盖。
- 活跃目标。
- 交易结果；个人画像会从 `trade_outcomes` 中提炼聚合 outcome feedback，只保留来源、策略、品类、样本数、胜负数、平均实际利润和好结果比例。
- 学到的模式。
- 常见问题。
- 裂缝和周期订阅。

## 4. 交易记忆

实现文件：`warframe_agent/trading_memory.py`。

### 表范围

| 表 | 用途 |
|---|---|
| `user_queries` | 用户查询摘要。 |
| `market_snapshots` | 市场快照。 |
| `recommendations` | 推荐记录。 |
| `push_history` | 推送历史。 |
| `opportunity_outcomes` | 机会复盘记录，保存 OP ID、来源、策略、状态、预期/实际利润、用户反馈和安全元数据。 |

### 设计特点

- 使用 SQLite。
- 默认保留 180 天。
- 支持只读打开。
- 用户查询只保存 deterministic summary，不保存完整原始 query/reply。
- metadata 有白名单和安全过滤。
- 当前个人评分闭环会消费 JSON 记忆里的 `AgentMemory.trade_outcomes`，也会由 Chat/Web 层把 SQLite `opportunity_outcomes` 显式注入 `build_personal_profile(...)`。扫描器仍然只接收 `PersonalTradingProfile`，不直接读库；画像摘要只保留聚合的来源、策略、品类、样本数、胜负数、平均实际利润和好结果比例。
- 聊天命令 `/review done OP8K3A2Q 45 good` 会先用 `OpportunityLookupStore.get(OPID)` 校验短期机会仍存在，再把 `trade_plan.safe_summary` 写入 `opportunity_outcomes`；不会把玩家名、profile 链接、`/w`、buy/sell steps 或 raw orders 写入长期库。
- `push_history` 会记录主动交易机会的 `dedupe_key`、来源、策略、利润/ROI、`profit_bucket`、`required_quantity`、`plan_signature` 和建议类型；监控器用它做跨扫描 cooldown 去重，Web 服务重启后仍能抑制近期重复机会，且允许同一物品在不同 source/strategy 下保留不同机会。
- 主动机会如果携带展示层 `trade_plan`，写入 `push_history` 前会改用 `trade_plan.safe_summary`，不会持久化玩家名、market/profile URL、whisper、buy/sell steps 或 raw orders；玩家变化但 source/item/strategy/profit bucket/quantity/signature 无实质变化时不会重复推送。
- `summarize_push_quality(...)` 会在不新增表结构的前提下，把 `push_history` 和 `opportunity_outcomes` 按安全的 `(item_name, source, strategy, category)` 分桶聚合为 `PushQualitySignal`。该信号只包含发送数、复盘数、完成/接受/拒绝/待处理数、好坏结果数、预期/实际利润均值、利润偏差、好结果率、完成率、拒绝率和误报率；Web 端点为 `GET /api/trading-memory/push-quality`。它不读取或返回玩家名、profile、market URL、`/w`、raw orders 或 raw metadata。

### 安全召回

实现文件：`warframe_agent/memory_recall.py`。

`MemoryRecallService` 在 `user_queries`、`market_snapshots`、`recommendations` 和 `push_history` 上做只读召回，评分为：

```text
score = relevance * 0.6 + recency * 0.2 + salience * 0.2
```

Trace 只返回安全解释字段，例如 `item_match`、`intent_match`、`tool_match`、`recency`、`salience_reason`。ChatAgent 注入模型上下文时只使用 `format_for_model()` 生成的匿名摘要；Web 只读端点为 `GET /api/memory/recall`。

### 机会 ID 短期详情

交易机会推送如果带有可执行 `trade_plan`，系统会生成 `OPxxxxxx` 短 ID，并把完整买卖计划快照保存到 `data/opportunity_lookup.db`。该库用于飞书/聊天输入 ID 后返回 warframe.market 链接、玩家主页和游戏内私聊命令，默认 48 小时过期，并在读写时清理。ID 回复会按 `trade_plan.source`/`strategy` 展示不同计划，并在机会标题中优先显示英文 market 名，后跟游戏内中文名，例如 `Arcane Energize（游戏内：充沛赋能）`：Prime 武器/战甲按完整套装订单说明部件交付；赋能按 R0 数量阶梯聚合买入并显示满级卖出买家；普通 MOD 显示 R0/低级买入与满级卖出，不按赋能的 21 个 R0 合成规则计算。用户完成交易后可用 `/review done OPID 实际利润 [反馈]` 把该短期机会的安全摘要写入长期 `opportunity_outcomes`。长期 `push_history` 和 `opportunity_outcomes` 都不保存玩家名、链接或 whisper。

## 5. 交易历史

实现文件：`warframe_agent/trade_history.py`。

用途：保存用户实际买入/卖出记录。

能力：

- 新增 buy/sell 交易。
- 查询最近交易。
- 查询指定物品交易。
- 统计总花费、总收入、净利润。
- 统计常交易物品。
- 删除交易。

Web API：

- `GET /api/trades`
- `POST /api/trades`
- `DELETE /api/trades/{trade_id}`
- `GET /api/trades/stats`
- `GET /api/trades/item/{item_id}`

## 6. 价格历史

实现文件：`warframe_agent/price_history.py`。

默认数据文件：`data/price_history.db`。

能力：

- 记录卖价和买价快照。
- 查询近期价格。
- 趋势摘要。
- 移动平均。
- 异常检测。
- 线性趋势预测。
- 结合事件上下文修正预测。
- 清理旧数据。

Web API：

- `GET /api/history/{item_id}`
- `POST /api/history/compare`
- `GET /api/price/anomalies`

## 7. 对话日志

实现文件：`warframe_agent/conversation_log.py`。

默认数据文件：`data/conversation_logs.jsonl`。

记录内容：

- 用户消息安全摘要，默认写为 `summary:v1 role=user ...`，不保存完整 raw prompt。
- 助手回复安全摘要，默认写为 `summary:v1 role=assistant ...`，不保存完整 raw answer。
- 工具调用安全摘要，只保留工具名、脱敏参数摘要、执行状态、耗时和时间戳等字段。
- 安全上下文 item_id。
- 评分。
- 会话 ID。

写入 `conversation_logs.jsonl` 前会过滤 `/w` 私聊、玩家 profile、warframe.market 原始链接、玩家标签、token/secret/Authorization/Bearer/cookie/app_secret/chat_id、`message_context`、`prompt`、`raw_arguments`、`content`、`display_content`、`model_context`、`result_summary` 和 `final_answer` 等字段。用户可见聊天回复仍可以展示复制用私聊和 market 链接，但普通长期日志只保存安全摘要。

`ChatAgent.last_agent_trace` 是最近一次 ReAct 的内存诊断对象，不写入 `conversation_logs.jsonl`。Web 运行态只通过 `/api/runtime/status` 暴露安全快照：保留 `status`、开始/结束时间、最大轮次、工具名、迭代、耗时、`has_result`、`result_chars` 和 `error_present`，不返回 `final_answer` 原文、`raw_arguments`、完整 `result_summary`、工具错误正文、profile 链接或 `/w` 私聊片段。

用途：

- 排查回答问题。
- 统计工具调用。
- 回看用户反馈。
- 支撑后续质量分析。

## 8. 知识库和学习系统

| 模块 | 用途 |
|---|---|
| `warframe_agent/knowledge.py` | 市场知识、品类健康度、均价、波动率、趋势、成交量趋势。 |
| `warframe_agent/patterns.py` | 学习到的交易模式。 |
| `warframe_agent/rules.py` | 主动推送和机会判断规则。 |
| `warframe_agent/feedback.py` | 用户反馈和策略效果反馈。 |
| `warframe_agent/goals.py` | 交易目标、进度和结果。 |
| `warframe_agent/bilibili_recommendations.py` | 本地 curated B 站攻略视频推荐；数据来自 `data/bilibili_recommendations.json`，只保存标题、链接、适用主题、别名、武器分类和同伴分类等元数据。 |
| `warframe_agent/video_analysis/` | 离线视频解析维护工具，输出待人工确认的画面/OCR/图标候选草稿。 |

`data/bilibili_recommendations.json` 不作为主观知识库使用，不保存视频画面中识别到的 Mod、赋能、灵化阶段或其他不稳定判断。每条记录可用 `category` 标注 `primary`、`secondary`、`melee`、`warframe`、`companion`，供“主武器/副武器/近战配卡视频”“战甲攻略视频”或“宠物攻略视频”这类泛分类问题匹配；具体物品、具体战甲或具体宠物查询需要命中 `weapons`、`warframes`、`companions` 或具体别名，避免只因同属 warframe/companion 类别而返回不相关视频。`needs_review: true` 的记录会被加载器跳过，避免未确认标题或名称进入推荐。

`data/video_parse_drafts.jsonl` 保存 B 站公开视频的离线解析草稿，例如帧时间点、候选区域、OCR 文本候选和图标匹配候选；这些记录默认 `needs_review: true` 且 `trusted_for_agent_answers: false`，只能作为人工确认材料，不能直接进入用户回答、长期记忆或主观攻略知识。

### 可检查 Memory Vault 索引

实现文件：`warframe_agent/memory_vault.py`。

Web API：

- `GET /api/memory/vault`

该索引借鉴 OpenHuman / CowAgent 的可检查个人记忆思路，但当前只做只读聚合层，不引入向量库、不导出 Obsidian 文件树、不调用云端模型。它会把已有安全来源转换为统一 `MemoryVaultEntry`：

- `user_query`
- `market_snapshot`
- `recommendation`
- `push_history`
- `opportunity_outcome`
- `conversation_log`

API 返回 `generated_at`、`total`、`source_counts`、`entries` 和 `markdown_preview`。Markdown 预览用于人工审查和跨会话恢复，只展示来源、物品、标题和 allowlist facts。

安全边界：

- 不保存或返回原始用户消息。
- 不保存或返回原始助手回复。
- 不返回 raw tool arguments、raw result、`args_summary` 或完整 trace。
- 不返回玩家名、profile URL、`/w`、whisper、token、secret、Authorization、cookie、app_secret 或 chat_id。
- 对话日志进入 vault 时只保留上下文数量、工具数量、工具名和安全 session id。
- 角色前缀和常见注入短语会被中和，避免 `system:`、`assistant:` 或 `ignore previous instructions` 进入 vault 预览。

## 9. 数据安全边界

- API Key、token、cookie、authorization 等敏感字段不应进入日志、模型上下文或文档。
- 外部数据进入模型上下文前应使用 `tool_context.py` 清洗。
- 交易记忆避免保存完整用户原文和完整回复，只保存摘要和结构化字段。
- 对话日志也按默认安全摘要写入，不能把即时回答中的玩家名、profile、market URL、`/w` 或 raw tool payload 当作长期日志内容。
- 记忆召回、运行态 API 和最近工具调用视图都必须过滤敏感参数、消息原文、玩家名、profile 和私聊命令。
- Riven、Baro、遗物价值等市场结果给模型时应去除玩家身份信息、profile 链接和 `/w` 私聊命令；遗物价值模型上下文只包含奖励 market_id、价格聚合、掉率、杜卡德值、EV 和建议。
- 交易机会的展示层 `trade_plan` 可以包含玩家名、market URL、profile URL 和 whisper；写入模型上下文、长期记忆、交易记忆或工具观测时只能使用 `safe_summary`，不能保存 raw orders 或具体玩家身份。
- 视频解析草稿中的 OCR、图标匹配、VLM 判断和 YOLO 区域定位都属于不可信候选；只有人工确认后的结构化记录才允许进入可被 Agent 用于回答的数据源。
