# 04. Web API 参考

FastAPI 入口：`warframe_agent/web/app.py`。

本文按功能域整理接口，便于查找。接口路径来自当前代码中的路由装饰器。

## 1. 聊天和记忆

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/chat` | 发送聊天请求，返回 Agent 回复。 |
| GET | `/api/memory` | 获取长期记忆摘要。 |
| GET | `/api/memory/recall` | 按 query、item_name、intent 和 tool_names 查询安全的交易记忆召回 trace。 |
| GET | `/api/profile` | 获取安全的个人交易画像摘要；包括风险、预算、偏好品类、JSON 交易结果和 SQLite 机会复盘合并后的聚合 `outcome_feedback`，不返回单次复盘 ID、玩家名、profile 或 whisper。 |
| POST | `/api/profile/preferences` | 更新风险、预算、偏好品类、周转和最低 ROI。 |
| POST | `/api/rate` | 提交回答评分或反馈。 |

## 2. 收藏、提醒、关注和偏好

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/fav` | 添加收藏物品。 |
| DELETE | `/api/fav` | 删除收藏物品。 |
| POST | `/api/alert` | 添加价格提醒。 |
| DELETE | `/api/alert` | 删除价格提醒。 |
| GET | `/api/watchlist` | 获取关注列表。 |
| POST | `/api/watchlist` | 添加关注项。 |
| DELETE | `/api/watchlist/{item_id}` | 删除关注项。 |
| POST | `/api/pref` | 更新用户偏好。 |
| GET | `/api/favorites_prices` | 查询收藏物品当前价格。 |

## 3. 推送和飞书

### WxPusher

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/push/config` | 获取推送配置。 |
| POST | `/api/push/config` | 更新推送配置。 |
| POST | `/api/push/test` | 测试推送。 |
| GET | `/api/push/qrcode` | 获取绑定二维码。 |
| POST | `/api/push/callback` | 接收 WxPusher 回调。 |

`/api/push/config` 中的 `push_proactive` 语义是“主动交易机会推送开关”。关闭后，`proactive_push` 中 `push_type="opportunity"` 的 WebSocket 和 WxPusher 推送都会被跳过；价格提醒、关注推送、日报和风险 warning 不受该开关影响。

主动交易机会广播会在 WebSocket payload 中保留展示层 `trade_plan` 和 `safe_summary`。WxPusher 侧使用 Markdown 格式化 `trade_plan`；飞书侧在已有 `data/feishu_chat_id.txt` 时发送卡片，展示同样的买入/卖出步骤、market/profile 链接和 whisper。记忆写入仍只保存安全摘要。

### 飞书

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/feishu/config` | 获取飞书配置。 |
| POST | `/api/feishu/config` | 更新飞书配置并启停 worker。 |
| POST | `/api/feishu/test` | 测试飞书发送。 |

## 4. 价格历史、交易历史和交易记忆

### 价格历史

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/history/{item_id}` | 查询单物品价格历史。 |
| POST | `/api/history/compare` | 对比多个物品价格历史。 |
| GET | `/api/price/anomalies` | 查询价格异常。 |

### 交易历史

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/trades` | 查询最近交易。 |
| POST | `/api/trades` | 新增交易记录。 |
| DELETE | `/api/trades/{trade_id}` | 删除交易记录。 |
| GET | `/api/trades/stats` | 查询交易统计。 |
| GET | `/api/trades/item/{item_id}` | 查询指定物品交易。 |

### 交易记忆

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/trading-memory/market-snapshots` | 查询历史市场快照。 |
| GET | `/api/trading-memory/recommendations` | 查询推荐记录。 |
| GET | `/api/trading-memory/push-history` | 查询推送历史。 |
| GET | `/api/trading-memory/push-quality` | 查询主动机会推送质量聚合，支持 push_type、item_name、source、since 和 limit 过滤；只返回发送数、复盘数、完成/拒绝/待处理数、好坏结果数、利润均值和质量率，不返回原始 metadata、玩家名、profile、market URL 或 `/w`。 |
| GET | `/api/opportunity-outcomes` | 查询机会复盘记录，支持 status、item_name、source 和 limit 过滤；只返回安全元数据。 |
| GET | `/api/memory/vault` | 查询只读 Memory Vault 索引，返回安全 entries、source_counts 和 Markdown preview；聚合 user_query、market_snapshot、recommendation、push_history、opportunity_outcome 和 conversation_log，不返回 raw user message、assistant reply、raw tool args/result、玩家名、profile URL、`/w` 或 token。 |

## 5. 活动、裂缝和报告

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/fissures` | 查询虚空裂缝。 |
| GET | `/api/fissures/relics` | 查询裂缝相关遗物。 |
| GET | `/api/events` | 查询世界状态/活动摘要；聊天和工具层会把中文活动别名规范化到已支持事件类型，未支持的午夜电波、仲裁、突击、Darvo/每日特惠、扎里曼/赏金会明确提示数据源暂不支持。 |
| GET | `/api/report` | 获取报告。 |
| GET | `/api/scheduler/status` | 查询后台调度状态。 |
| GET | `/api/runtime/status` | 查询 Web、飞书 worker、scheduler、日报、WxPusher、后台任务、最近工具调用、最近 Agent Trace 和 `safety_policy` 的安全运行态摘要；`safety_policy.tool_registry` 只包含聚合计数和分布，`safety_policy.browser_gui_policy` 只包含 Browser/GUI 行为安全矩阵，`safety_policy.companion_experience_policy` 只包含语音/陪伴体验的只读边界。 |
| GET | `/api/tool-calls/history` | 查询最近工具调用历史，支持 tool_name、ok、session_id 和 limit 过滤。 |
| GET | `/api/tool-calls/stats` | 查询工具调用统计，包括成功率、失败数、耗时和按工具聚合。 |

## 6. 物品详情、杜卡特、别名和搜索

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/item_detail/{item_id}` | 查询物品详情。 |
| GET | `/api/ducats/{item_id}` | 查询单物品杜卡特信息。 |
| POST | `/api/ducats/batch` | 批量查询杜卡特信息。 |
| GET | `/api/aliases` | 查询自定义别名。 |
| POST | `/api/aliases` | 新增或更新自定义别名。 |
| DELETE | `/api/aliases` | 删除自定义别名。 |
| GET | `/api/search_items` | 搜索物品。 |
| GET | `/api/resolve/{name}` | 解析名称到物品。 |

## 7. 倒卖、套利、投资和扫描任务

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/mod_flipper` | 扫描 Mod/赋能 R0 到满级倒卖机会；结果包含 `required_quantity` 和 `trade_plan`。赋能的 `trade_plan.buy_steps` 会按卖家 quantity 聚合买够满级所需 R0。 |
| GET | `/api/set_profit` | 扫描 Prime 套装/部件套利机会；结果包含 `best_cost`、`best_revenue`、`roi_pct`、`liquidity_score`、`risk_level`、`risk_score`、`opportunity_score`、`supply_count`、`demand_count` 和 `trade_plan`，且只包含当前盈利策略的买入/卖出步骤，例如买部件卖整套时不返回整套卖家作为主路径。 |
| GET | `/api/investment` | 运行投资顾问；结果包含 `trade_plan`、`set_item_id` 和 `part_details`，前端优先用 `trade_plan` 展示可执行买卖路径。`budget` 和 `min_roi_pct` 省略或为空字符串时使用个人偏好中的预算上限和最低 ROI，显式传参优先，显式 `0` 会保留。 |
| GET | `/api/scan_status/{task_id}` | 查询异步扫描任务状态。 |
| POST | `/api/profit/calculate` | 计算指定机会收益。 |
| GET | `/api/suggest` | 获取主动建议。 |
| POST | `/api/compare` | 对比多个候选物品。 |
| POST | `/api/batch_query` | 批量查询物品。 |

## 8. 目标和模式

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/goals` | 获取目标列表。 |
| POST | `/api/goals` | 创建目标。 |
| DELETE | `/api/goals/{goal_id}` | 删除目标。 |
| POST | `/api/goals/{goal_id}/execute` | 执行目标。 |
| GET | `/api/goals/execute_status/{task_id}` | 查询目标执行状态。 |
| POST | `/api/goals/{goal_id}/outcome` | 记录目标结果。 |
| GET | `/api/goals/summary` | 获取目标摘要。 |
| POST | `/api/goals/earn` | 记录收益。 |
| GET | `/api/goals/{goal_id}/progress` | 查询目标进度。 |
| GET | `/api/patterns` | 查询学习到的模式。 |

## 9. Wiki、紫卡、市场抓取和遗物

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/wiki/warframes` | 查询战甲 Wiki/导出数据。 |
| GET | `/api/wiki/weapons` | 查询武器 Wiki/导出数据。 |
| GET | `/api/wiki/mods` | 查询 Mod Wiki/导出数据。 |
| GET | `/api/riven/auctions` | 查询紫卡拍卖。 |
| GET | `/api/market/scrape/{item_url_name}` | 抓取或补充市场数据。 |
| GET | `/api/relic/search` | 搜索遗物。 |
| GET | `/api/relic/sources/{relic_name}` | 查询遗物来源。 |
| GET | `/api/farming-route` | 按 target 查询 Prime 部件或遗物的刷取路线，返回排序后的遗物、掉率、来源、当前同纪元裂缝、入库状态、期望白金/杜卡德和建议。 |
| GET | `/api/relic/drops/{tier}/{relic_name}` | 查询遗物掉落。 |
| GET | `/api/relic/value/{tier}/{relic_name}` | 查询遗物奖励价值、期望白金、期望杜卡德、杜卡德效率和数据提示。 |

## 10. API 设计注意事项

- Pydantic 请求模型使用 `extra="forbid"` 的接口会拒绝未知字段。
- API 响应不应缓存，`NoCacheAPIMiddleware` 会为 `/api` 响应设置禁用缓存头。
- 推送、飞书、聊天接口会触发外部请求或后台 worker 状态变化，修改前应注意副作用。
- `/api/runtime/status` 只暴露安全运行态摘要，不应返回密钥、chat_id、token、完整 traceback、完整消息内容或外部原始响应。`safety_policy` 只返回能力名、默认模式、可用状态、启用布尔值和固定 scope；`safety_policy.tool_registry` 只返回工具总数、schema 暴露/隐藏数量、副作用工具数量，以及 `safety_level`、`skill`、`context_policy` 的聚合分布，不返回单个工具名、description、parameters、handler、raw args 或 ToolResult。`safety_policy.browser_gui_policy` 只返回 Browser/GUI 行为分类和聚合计数，不返回真实 URL、DOM 原文、截图 OCR、cookie、localStorage、玩家 profile、`/w` 或 token。`safety_policy.companion_experience_policy` 只返回 text-only 默认模式、禁用的语音/麦克风/录音/Live2D/后台监听能力、聚合决策计数和安全示例，不返回原始消息、音频 URL、录音路径、平台 token、玩家 profile、`/w` 或 token。`agent_trace` 只返回 `present`、`status`、`started_at`、`ended_at`、`max_iterations`、`duration_ms`、`termination_reason`、`iterations`、`step_count`、最近步骤的 `tool_name`、`args_summary`、`ok`、`duration_ms`、`has_result`、`result_chars`、`error_present` 和 `final_answer_present`；不得返回 `final_answer` 原文、`raw_arguments`、完整 `result_summary` 或工具错误正文。运行态文本清洗需要覆盖敏感 key、Bearer token、带协议/不带协议的 warframe.market profile URL 和整行 `/w` 私聊片段。
- `/api/tool-calls/history` 和 `/api/tool-calls/stats` 只返回工具名、成功状态、耗时、安全参数摘要和聚合指标，不返回原始消息、密钥或完整异常。
- `/api/memory/recall` 只返回清洗后的事实摘要和 explainable trace，不返回 raw query、assistant reply、玩家名、profile 或私聊命令。
- `/api/memory/vault` 只返回 allowlist 结构化摘要和 Markdown preview；conversation_log 只进入工具名、上下文数量、工具数量和安全 session id，不返回 `user_message`、`assistant_reply`、`args_summary`、玩家名、profile、`/w`、token、secret 或 raw result。
- 交易机会 API 可以返回用户可见的玩家名、市场链接和 `/w` 私聊命令摘要；`trade_plan` 是展示层结构，包含 `buy_steps`、`sell_steps`、`total_cost`、`total_revenue`、`profit`、`roi_pct`、`risk_level` 和 `safe_summary`。套装套利额外返回机会分数、流动性、风险分、当前盈利路径成本/收入和供需步骤数。
- `trade_plan.safe_summary`、工具模型上下文和记忆只应保存来源、策略、item_id、数量、成本、收入、利润、ROI、风险、profit bucket 和签名，不保存玩家名、profile、market URL、`/w` 或 raw orders。
- 刷取路线 API 和 `farming_route` 工具模型上下文只应返回遗物名、纪元、部件 item_id、掉率、来源数量、当前裂缝数量、入库状态、期望白金/杜卡德和路线分数，不返回 raw orders、玩家名、profile、market URL 或 `/w`。
- 市场、紫卡、活动和 Wiki 数据都可能来自外部源，进入模型上下文前应经过清洗或摘要。
