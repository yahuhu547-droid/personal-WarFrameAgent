# 02. 功能范围

本文按业务范围描述当前项目能力，并标出关键实现文件和测试入口。

## 1. 聊天 Agent 与多轮上下文

| 能力 | 说明 | 关键文件 | 测试 |
|---|---|---|---|
| 自然语言问答 | 支持普通回答、流式回答、LLM 回退。 | `warframe_agent/chat.py` | `tests/test_chat.py` |
| 多轮上下文 | 保存最近物品、最近意图、最近紫卡查询、follow-up 判断。 | `warframe_agent/session.py` | `tests/test_multiturn.py`、`tests/test_session_context.py` |
| Slash Command | `/help`、`/memory`、`/fav`、`/alert`、`/pref`、`/scan`、`/goal`、`/fissure`、`/cycle`、`/trade`、`/relic`、`/strategy`、`/vault`、`/resurgence` 等；`/goal set` 可从中文目标句解析收益目标、周期、预算、风险和最低 ROI；常见价格提醒、收藏关注、个人偏好、目标完成/放弃和交易复盘可用自然语言创建/更新/确认。 | `warframe_agent/chat.py` | `tests/test_chat_memory_commands.py` |
| 聊天模式分层 | 用轻量 `_classify_chat_mode(...)` 在 ChatAgent 内区分直接交易、自然语言计划、市场分析、B 站攻略、交易工具、事件和普通问答；当前先解决“价格/交易词 + 攻略视频词”和“计划/目标 + 交易/攻略词”的冲突。直接市场意图优先；自然语言 planning 返回安全计划草案，并在可解析目标时走“确认创建”流程；首轮不自动下单、不自动写目标；B 站只在 guide_video 模式直出或追加。 | `warframe_agent/chat.py` | `tests/test_chat.py`、`tests/test_chat_memory_commands.py` |
| RAG 回退 | 物品字面检索、normalize lookup、可选 embedding 检索。 | `warframe_agent/rag.py` | `tests/test_chat_rag_fallback.py` |
| 对话日志 | 保存消息、工具调用、上下文、评分、会话 ID。 | `warframe_agent/conversation_log.py` | `tests/test_conversation_log.py` |

## 2. 市场价格查询

| 能力 | 说明 | 关键文件 | 测试 |
|---|---|---|---|
| 订单查询 | 查询 warframe.market 订单，过滤在线买家/卖家。 | `warframe_agent/market.py` | `tests/test_market_client.py` |
| 统计查询 | 查询成交统计和 48 小时成交量。 | `warframe_agent/market.py` | `tests/test_market_client.py` |
| 买入方案 | 构建批量购买方案和最低成本组合。 | `warframe_agent/market.py` | `tests/test_market_formatter.py` |
| 名称解析 | 中文/英文别名、生成别名、自定义别名、短名回归。 | `warframe_agent/names.py`、`warframe_agent/dictionary.py` | `tests/test_names.py`、`tests/test_generated_alias_resolver.py` |
| 价格历史 | 记录快照、趋势摘要、移动平均、异常检测、预测。 | `warframe_agent/price_history.py` | `tests/test_price_history.py` |
| 直接交易辅助 | 普通物品和 Prime 物品都支持“市场链接”“最低卖家”“砍价”等确定性意图；流式回答走同一路径。交易意图优先于 B 站视频推荐，且“最低卖家/砍价”优先于单纯链接。 | `warframe_agent/chat.py` | `tests/test_chat.py` |

## 3. Prime 套装、部件、缺件和遗物

| 能力 | 说明 | 关键文件 | 测试 |
|---|---|---|---|
| Prime 套装识别 | 从 `items_full.json` 构建战甲/武器 Prime 组。 | `warframe_agent/warframes.py` | `tests/test_warframe_sets.py` |
| 部件查询 | 支持蓝图、机体、头部、系统、枪管、枪机、枪托等中文/英文部件。 | `warframe_agent/warframes.py` | `tests/test_prime_set_generalization.py` |
| 缺件补齐 | 根据已有部件计算剩余缺件和补齐成本。 | `warframe_agent/warframes.py` | `tests/test_missing_parts.py` |
| 套装套利 | 买部件卖整套、买整套拆件卖，计算最佳策略、ROI、流动性、风险等级和机会分数，并生成只包含当前盈利路径的可执行交易计划。 | `warframe_agent/set_profit.py` | `tests/test_set_profit.py` |
| 投资顾问 | 预算、ROI、风险、可买套数、预估利润，并复用可执行交易计划展示具体买卖路径；当聊天工具或 Web 默认入口没有显式传预算/ROI 时，使用个人偏好的预算上限和最低 ROI。 | `warframe_agent/investment.py` | `tests/test_investment.py` |
| 遗物查询 | 按部件查遗物、按遗物查掉落、纪元中文映射。 | `warframe_agent/relics.py` | `tests/test_relics.py` |
| 遗物价值助手 | 计算遗物奖励最低卖价、最高收价、保守估值、杜卡德值、杜卡德/白金效率、期望白金和期望杜卡德；未知杜卡德不猜值。 | `warframe_agent/relic_value.py`、`warframe_agent/chat.py`、`warframe_agent/web/app.py` | `tests/test_relic_value.py`、`tests/test_chat.py`、`tests/test_web_api.py` |
| 刷取路线推荐 | 按 Prime 部件反查遗物、按遗物列出奖励路线，结合遗物来源、当前同纪元裂缝、掉率、入库状态、期望白金和期望杜卡德生成排序建议；数据不足时明确提示。 | `warframe_agent/farming_route.py`、`warframe_agent/chat.py`、`warframe_agent/web/app.py` | `tests/test_farming_route.py`、`tests/test_chat.py`、`tests/test_tool_router.py`、`tests/test_web_api.py` |

## 4. Riven 紫卡

| 能力 | 说明 | 关键文件 | 测试 |
|---|---|---|---|
| 自然语言解析 | 解析武器名、正属性、负属性、无负、价格上限。 | `warframe_agent/riven.py` | `tests/test_riven.py` |
| 属性映射 | 中文属性映射到 API url_name，支持“双爆/双暴”等复合词。 | `warframe_agent/riven.py` | `tests/test_riven.py` |
| 拍卖搜索 | 调用 warframe.market auction search，支持分页和过滤。 | `warframe_agent/riven.py` | `tests/test_riven_weapon_normalize.py` |
| 紫卡评分 | 对正负属性、当前挂牌区间、样本量生成属性评分、价格位置、置信度和“非真实成交价”提示。 | `warframe_agent/riven.py` | `tests/test_riven.py` |
| 安全上下文 | 模型上下文不包含玩家名、profile 链接、私聊命令或 auction id；只包含匿名价格、属性、评分、价格位置和置信度。 | `warframe_agent/riven.py`、`warframe_agent/experts.py` | `tests/test_tool_context.py` |

## 5. Baro Ki'Teer 虚空商人

| 能力 | 说明 | 关键文件 | 测试 |
|---|---|---|---|
| 库存解析 | 解析当前 Baro 库存、到达时间、离开时间。 | `warframe_agent/events.py` | `tests/test_events.py` |
| 市场推荐 | 对库存 Mod/赋能查询市场价并生成推荐。 | `warframe_agent/baro.py` | `tests/test_baro.py` |
| 等级处理 | 支持 R0、满级和指定 rank 查询。 | `warframe_agent/baro.py` | `tests/test_baro.py` |
| 追问详情 | 支持按序号或名称追问推荐项买家/卖家。 | `warframe_agent/chat.py`、`warframe_agent/baro.py` | `tests/test_baro.py` |

## 6. 世界状态和活动

| 能力 | 说明 | 关键文件 | 测试 |
|---|---|---|---|
| 官方 World State | 解析 Baro、裂缝、警报、入侵、虚空风暴、Prime 重生、运营活动；支持常见中文别名，数据源缺字段时明确说明暂不支持且不编造。 | `warframe_agent/events.py` | `tests/test_events.py` |
| Prime Resurgence | 当前轮换、下一轮、相关物品。 | `warframe_agent/events.py` | `tests/test_events.py` |
| Prime Vault / Access | 回归、入库、Prime Access 相关事件。 | `warframe_agent/events.py` | `tests/test_events.py` |
| 开放世界周期 | 地球、希图斯/平原、金星/奥布山谷/福尔图娜、火卫二/魔胎之境等周期。 | `warframe_agent/events.py`、`warframe_agent/chat.py` | `tests/test_events.py`、`tests/test_chat.py` |
| 事件推送 | 裂缝订阅、周期订阅、Baro 推荐、Vault 推送。 | `warframe_agent/monitor.py` | `tests/test_monitor.py` |
| 自然语言裂缝提醒 | 用户可说“提醒我钢铁后纪歼灭裂缝”生成待确认订阅；“确认订阅”后写入，按“取消第1个裂缝提醒/确认取消”移除。查询类裂缝问题不写入。 | `warframe_agent/chat.py`、`warframe_agent/memory.py` | `tests/test_chat_memory_commands.py` |

## 7. 倒卖、投资、扫描和主动智能

| 能力 | 说明 | 关键文件 | 测试 |
|---|---|---|---|
| Mod/赋能倒卖 | Mod 按单张 R0 买入满级卖出；赋能按满级所需 R0 数量聚合买入，考虑卖家 quantity、最后卖家部分成交、总成本、ROI 和 value score。 | `warframe_agent/mod_flipper.py` | `tests/test_mod_flipper.py` |
| 套装套利 | Prime 套装/部件双向利润扫描；按机会分数、利润和 ROI 排序，结果必须能形成完整买卖路径，展示只保留当前盈利策略。 | `warframe_agent/set_profit.py` | `tests/test_set_profit.py` |
| 投资顾问 | 按预算和风险筛选机会，并返回与套装套利一致的 `trade_plan`；缺省预算/ROI 来自 `TradingPreferences.budget_max` 和 `min_roi_pct`，显式传参优先。 | `warframe_agent/investment.py`、`warframe_agent/chat.py`、`warframe_agent/web/app.py`、`warframe_agent/web/static/js/sidebar.js` | `tests/test_investment.py`、`tests/test_chat_memory_commands.py`、`tests/test_web_api.py` |
| 个人化交易画像与机会评分 | 保存风险、预算、偏好品类、周转和最低 ROI；结合历史复盘生成安全画像；从已记录交易结果中聚合 `source`、`strategy`、`category`、胜负和平均利润反馈，并为 Mod/赋能、Prime 套装和投资机会输出个人评分及原因。 | `warframe_agent/personal_profile.py`、`warframe_agent/personal_scoring.py`、`warframe_agent/memory.py`、`warframe_agent/trading_memory.py` | `tests/test_personal_profile.py`、`tests/test_personal_scoring.py`、`tests/test_trading_memory.py` |
| 机会扫描 | 高价差、低挂单、趋势反转、价格下跌。 | `warframe_agent/scanner.py` | `tests/test_patterns.py` |
| 交易策略 | 低风险赋能翻转、中风险 Prime 拆件、高风险 Vault 投机模板。 | `warframe_agent/strategies.py` | `tests/test_rules.py` |
| 主动监控 | 收藏、价格提醒、关注列表、异常、目标相关机会。 | `warframe_agent/monitor.py` | `tests/test_monitor.py` |
| 目标系统 | 活跃目标、自然语言目标解析、自动生成、执行、进度、收益记录；收益目标会保存为 `target_amount` 供进度和复盘使用。 | `warframe_agent/goals.py` | `tests/test_goals.py`、`tests/test_chat_memory_commands.py` |
| 自学习 | 反馈、规则、模式、客观市场知识库滚动更新。 | `warframe_agent/feedback.py`、`warframe_agent/rules.py`、`warframe_agent/patterns.py`、`warframe_agent/knowledge.py` | `tests/test_feedback.py`、`tests/test_knowledge.py` |
| 运行态安全策略快照 | `/api/runtime/status` 暴露只读 `safety_policy`，说明 shell、通用文件写入、浏览器私网和任意调度器默认不可用，市场网络读取、项目数据写入、注册调度任务、外部推送和 ToolRegistry 聚合安全分布的边界可见。 | `warframe_agent/safety_policy.py`、`warframe_agent/web/app.py`、`warframe_agent/web/static/js/app.js` | `tests/test_tool_registry.py`、`tests/test_web_api.py` |
| 基础配卡攻略查询 | 配卡/攻略/视频类问题自动推荐本地维护的 B 站公开视频链接；支持具体武器、主武器/副武器/近战分类、具体战甲名/别名，以及宠物/同伴/守护/猎犬/恐鸟相关视频推荐。用户问具体战甲或具体宠物名时必须命中对应 `warframes`/`companions` 或具体别名，优先返回当前版本、近期、观看较多或标题更具体的攻略视频；泛问“战甲攻略视频”“宠物攻略视频”才按类别返回。流派选择、枪架子、战甲适配和紫卡主观判断暂不处理；视频链接可先入库，画面识别出的 MOD、赋能或灵化选择必须经用户过目确认后才可写入可信数据。 | `warframe_agent/bilibili_recommendations.py`、`data/bilibili_recommendations.json`、`warframe_agent/chat.py` | `tests/test_bilibili_recommendations.py`、`tests/test_build_bilibili_recommendations.py`、`tests/test_chat.py` |

## 8. 推送与外部入口

| 能力 | 说明 | 关键文件 | 测试 |
|---|---|---|---|
| WxPusher | 文本/Markdown 推送、二维码、回调、每日报告窗口。 | `warframe_agent/push.py` | `tests/test_push.py` |
| 飞书机器人 | WebSocket 长连接、消息去重、回复卡片、本地 API 转发。 | `warframe_agent/feishu.py` | `tests/test_feishu.py` |
| Web API | FastAPI JSON 接口和静态资源。 | `warframe_agent/web/app.py` | `tests/test_web_api.py` |
| Web UI | 聊天、关注、配置、图表、交易记忆、Dashboard。 | `warframe_agent/web/static/` | `tests/test_web_ui_playwright.py` |
| 运行态 Agent Trace / AgentRun | `/api/runtime/status` 和运行态详情面板展示最近一次 ReAct 的安全诊断快照与 `safety_policy`；只返回 `status`、开始/结束时间、最大轮次、当前迭代、工具名、耗时、结果长度、错误是否存在、能力边界和工具聚合分布，不返回原始参数、完整结果、最终答案原文、工具错误正文、工具参数 schema 或凭据。 | `warframe_agent/chat.py`、`warframe_agent/tool_router.py`、`warframe_agent/safety_policy.py`、`warframe_agent/web/app.py`、`warframe_agent/web/static/js/app.js` | `tests/test_tool_router.py`、`tests/test_tool_registry.py`、`tests/test_web_api.py`、`tests/test_web_ui_playwright.py` |

## 9. 游戏数据补充能力

| 能力 | 说明 | 关键文件 | 测试 |
|---|---|---|---|
| Mod/赋能/战甲数据 | 查询 Mod 效果、赋能效果、战甲技能。 | `warframe_agent/game_data.py` | `tests/test_game_data.py` |
| 杜卡特 | 单物品和批量杜卡特价值、效率计算。 | `warframe_agent/game_data.py`、`warframe_agent/web/app.py` | `tests/test_web_api.py` |
| Wiki/导出数据 | 预加载 export/wiki/relic 缓存，供 Web API 查询。 | `warframe_agent/game_data.py`、`warframe_agent/web/app.py` | `tests/test_game_data.py` |

## 覆盖面提示

当前测试覆盖单元测试、集成测试、Web API 测试、Playwright UI 测试和端到端测试。本文只说明代码中存在的能力，不代表当前工作区测试已经在本次文档重构中重新运行。
