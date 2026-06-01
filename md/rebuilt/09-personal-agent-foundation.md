# 09. 个人化交易 Agent 基础完成记录

这是一页完成记录，记录本轮“个人 Agent 基础”已经落地的内容和最终验证结果。更详细的接口、记忆和运行说明仍以 `02-feature-scope.md`、`03-user-interfaces.md`、`04-web-api-reference.md`、`05-data-memory.md`、`07-operations-testing.md` 为准。

> 当前权威状态（2026-05-31）：旧个人 Agent 学习借鉴路线已完成并终止于 Step 51；Step 52 / Step 53 只维护终止条件、实现不足复核和历史文案防误读标注。本文早期“后续 / 剩余任务 / 下一阶段”语句为历史记录，不再表示当前待办队列。

## 完成内容

- 明确的个人交易偏好：风险、预算、偏好品类、周转周期、最低 ROI。
- 安全个人画像：`/profile`、`/api/profile` 只输出脱敏摘要。
- 机会复盘：`opportunity_outcomes` 支持写入、查询和清理，且会过滤 `profile` 链接、`/w`、token 等敏感内容。
- 个人评分：Mod/赋能、Prime 套装和投资扫描都会根据个人画像重新排序，并输出原因。
- 交互入口：`/pref`、`/review`、`/profile` 和对应 Web API 已接通。
- 运行态诊断：`/api/runtime/status` 与 Web 运行态详情面板可查看最近一次 ReAct `agent_trace` 安全快照，用于排查个人 Agent 工具链是否实际调用了目标工具。
- 文档同步：功能范围、界面、API、数据记忆和运行测试文档都已更新。

## 验证记录

个人 Agent 基础阶段的目标测试集合包括：

- `tests/test_personal_profile.py`
- `tests/test_personal_scoring.py`
- `tests/test_trading_memory.py`
- `tests/test_chat_memory_commands.py`
- `tests/test_web_api.py`
- `tests/test_mod_flipper.py`
- `tests/test_set_profit.py`
- `tests/test_investment.py`
- `tests/test_memory.py`
- `tests/test_memory_recall.py`
- `tests/test_rules.py`
- `tests/test_goals.py`

2026-05-26 后续增量任务按各自步骤记录实际重跑命令和结果，不再把上述集合笼统表述为“本轮均已通过”。其中 Web API 目标在当前普通沙箱会在导入 Web app 时触发 SQLite WAL 的 `sqlite3.OperationalError: unable to open database file`，需要在可写数据目录环境中补跑。

2026-05-26 追加的 Agent Trace 运行态面板已完成代码和文档同步；当前普通沙箱仍会在 SQLite WAL 处阻塞 Web API/Playwright pytest，已用 Python AST、JS `node --check` 和正则样例验证做局部确认，完整 pytest 需在可写数据目录的环境中补跑。

## 结果

这一轮任务可以视为完成。后续如果要继续扩展，更适合从独立 roadmap 里拆下一步，而不是回到这条基础链路上继续堆东西。

## 2026-05-26 追加：AgentRun 生命周期状态

在 Runtime Agent Trace 面板之后，新增轻量 AgentRun 生命周期字段：`status`、`started_at`、`ended_at`、`max_iterations` 和 `duration_ms`。本步只扩展现有 `AgentTrace` 与 `/api/runtime/status` 安全快照，不复制 OpenManus 的完整 Agent 类继承体系，也不持久化完整 trace。工具异常路径会把 trace 收口为 `status="error"` 与 `termination_reason="tool_error"`，避免运行态页面长期停留在 running。

## 2026-05-26 追加：投资顾问默认读取个人偏好

投资顾问现在会在缺省参数时读取个人偏好：聊天工具 `investment_advisor` 和 Web `/api/investment` 在没有显式传 `budget` 或 `min_roi_pct` 时，使用 `TradingPreferences.budget_max` 与 `min_roi_pct`；空字符串也按缺省处理，显式 `0` 和其他显式传参仍然优先。Web 侧默认入口不再强行发送 `budget=500&min_roi_pct=10`，汇总区缺省时显示“偏好预算”，避免覆盖或误导用户通过 `/pref budget` 和 `/pref min_roi` 设置的个人画像。

## 2026-05-26 追加：运行态安全策略快照

`/api/runtime/status` 现在包含只读 `safety_policy`：shell、通用文件写入、浏览器私网和任意调度器默认不可用；市场网络读取为只读，项目数据写入受限，scheduler jobs 与外部推送只暴露启用状态。Web 运行态详情面板会展示这些边界，但不会提供开关，也不会返回 Push token、UID、Feishu app_secret 或 chat_id。

## 2026-05-26 追加：ToolRegistry 安全统计摘要

`safety_policy.tool_registry` 现在包含工具注册表的聚合安全分布：工具总数、schema 暴露/隐藏数量、副作用工具数量，以及 `safety_level`、`skill` 和 `context_policy` 计数。该摘要不返回单个工具名、description、parameters、handler、raw args、ToolResult 或 model_context，只用于确认当前 Agent 能力面是否仍保持只读优先。

## 2026-05-26 追加：机会复盘反馈进入个人评分

个人画像现在会从 `AgentMemory.trade_outcomes` 中生成聚合 `outcome_feedback`，只包含来源、策略、品类、样本数、胜负数、平均实际利润和好结果比例。个人评分在同类反馈样本达到 3 条后才做小幅调权：历史表现好的策略会增加个人分并标注“历史策略表现好”，历史亏损或差评多的策略会降低个人分并标注“历史策略需谨慎”。该闭环不读取 raw orders、OP 短期详情、玩家名、profile 链接、`/w` 私聊命令、token、`outcome_id` 或 `goal_id`。

本步已用 `.venv\Scripts\python.exe` 验证 `tests/test_personal_profile.py tests/test_personal_scoring.py -q` 为 `12 passed`，并分别验证 `test_mod_flipper.py`、`test_set_profit.py`、`test_investment.py` 中 `personal_score` 相关窄测通过。普通 `python` 当前指向旧 Python/pytest 组合，会在收集阶段卡住；Web API 目标仍需在可写数据目录环境中单独补跑。

## 2026-05-26 追加：SQLite 机会复盘注入个人画像

`build_personal_profile(...)` 现在可接收显式 `opportunity_outcomes`，用于把 SQLite `TradingMemoryDB.get_opportunity_outcomes(...)` 的长期机会复盘注入个人画像。ChatAgent 会通过注入的 `trading_memory_db` 构建画像；Web `/api/profile`、`/api/profile/preferences` 和三个扫描端点使用只读 `TradingMemoryDB.open_readonly_if_exists()` 读取复盘。扫描器仍然只接收 `PersonalTradingProfile`，不直接读 SQLite；画像摘要不返回 OP ID、玩家名、profile、whisper、token 或 raw metadata。

## 2026-05-26 追加：真实 OP 机会复盘记录入口

聊天命令新增 `/review done OP8K3A2Q 45 good` 和中文 `/复盘 完成 OP8K3A2Q 45`。记录前会先从 `OpportunityLookupStore` 读取未过期 OP 机会，再提取 `trade_plan.safe_summary` 写入 `TradingMemoryDB.opportunity_outcomes`；长期库只保存 OP ID、item_id、source、strategy、预期利润、实际利润、反馈和安全摘要，不保存玩家名、profile、`/w`、buy/sell steps 或 raw orders。`/review completed` 仍保持状态筛选语义。

## 2026-05-26 追加：AgentPlan 运行态只读快照

`AgentTrace` 现在会在现有 `plan` 工具被调用时记录 `AgentPlanSnapshot`，包括 goal、步骤工具名、purpose、安全参数摘要、状态、耗时、是否成功和是否有结果。Web `/api/runtime/status` 把该快照放在 `agent_trace.plan` 下，只用于排障“是否进入多步骤计划、哪一步失败”，不展示 raw arguments、完整 result summary、final answer、玩家 profile、`/w` 或 token，也不改变工具执行顺序。

## 2026-05-26 追加：AgentPlan Web 运行态面板

Web 运行态详情面板现在已经把 `agent_trace.plan` 从后端安全快照接入 UI：摘要卡展示计划是否存在、计划状态、goal 是否存在和步骤数量；详情区展示每个计划步骤的工具名、purpose、状态、耗时、是否有结果和是否有错误。该实现只用于调试多步 Agent 是否按预期规划和执行，不改变工具执行顺序，也不持久化完整 trace。

本步额外收紧了前端诊断面板的兜底脱敏：运行态 `args_summary` 会跳过 token、secret、chat_id、app_secret、profile、whisper、raw、result_summary、final_answer 等敏感键，并把包含 Bearer、`/w`、secret-token、PlayerSecret 等可疑文本的值替换为 `[REDACTED]`。Agent Trace 不再把 `final_answer` 字面量显示到 DOM，只显示 `reason=answered` 和 `answer_present=true/false`。

## 2026-05-26 追加：运行态验证闭环

Step 14 没有新增大功能，而是补齐 Step 4-13 的验证闭环：Web API runtime status、Web Runtime 面板、ToolRegistry 安全摘要、SQLite 机会复盘画像反馈和 `/review` 命令都已用项目内 `.venv` 跑过目标测试。普通沙箱导入 Web app 时仍会遇到 SQLite WAL 写目录限制；Web API 和 Playwright 目标需要在可写数据目录环境中补跑。

本轮验证抓到并修复了两个运行态安全摘要问题：最近工具调用的 `args_summary` 会过滤 `message_context`、`prompt`、`raw_arguments`、`result_summary`、`display_content`、`model_context`、`final_answer`、`profile`、`whisper` 等键；ToolRegistry 聚合摘要使用 `private_schema_count` 表示未暴露 schema 的数量，避免 `hidden_schema_count` 与敏感测试值 `hidden` 撞名。下一轮更适合继续普通物品交易辅助意图扩展、长期记忆 vault 化、Scout 推送质量评估或聊天模式分层。

## 2026-05-26 追加：普通物品交易辅助意图优先级

普通物品交易辅助 Step 15 已完成：`ChatAgent` 会把“市场链接/最低卖家/砍价”等直接市场意图放在 B 站直出推荐之前处理，避免用户混入“攻略视频/B站”时丢失明确交易请求；在直接市场意图内部，“最低卖家/砍价”会优先于单纯链接，返回卖家、价格、复制用私聊和 market URL。`answer_stream` 已补普通物品市场链接和最低卖家的回归测试。

本步验证使用项目内 `.venv\Scripts\python.exe`，聚焦用例 `4 passed`，市场/B站周边守护用例 `16 passed`。后续剩余学习任务可以继续拆长期记忆 vault 化、Scout 推送质量评估或聊天模式分层。

## 2026-05-26 追加：Conversation Log 默认安全写入

长期记忆 vault 化 Step 16 已完成第一段：`conversation_logs.jsonl` 不再直接保存 raw `user_message` 和 `assistant_reply`，而是在 `log_conversation(...)` 写入点生成 `summary:v1 role=...` 安全摘要。即时聊天仍可向用户展示玩家名、market 链接和复制用 `/w`，但普通长期日志会过滤玩家身份、profile、market URL、token、`message_context`、`raw_arguments`、`model_context`、`result_summary`、`final_answer` 等字段。

本步验证使用项目内 `.venv\Scripts\python.exe`：`tests/test_conversation_log.py` 为 `12 passed`，聊天安全记忆窄测为 `5 passed`，ToolRouter 日志窄测为 `2 passed`。后续剩余学习任务建议继续 Scout 推送质量评估或聊天模式分层。

## 2026-05-26 追加：Scout 推送质量评估

Scout 推送质量 Step 17 已完成：`TradingMemoryDB.summarize_push_quality(...)` 会复用现有 `push_history` 和 `opportunity_outcomes`，按安全的 `item_name/source/strategy/category` 分桶生成 `PushQualitySignal`。信号包含发送数、复盘数、完成/接受/拒绝/待处理数、好坏结果数、预期/实际利润均值、利润偏差、好结果率、完成率、拒绝率和误报率。Web 新增 `GET /api/trading-memory/push-quality`，只返回聚合字段，不返回 raw metadata、玩家名、profile、market URL、`/w`、token 或 raw orders。

本步已用项目内 `.venv\Scripts\python.exe` 完成红绿验证：`tests/test_trading_memory.py -k "push_quality"` 为 `2 passed`，proactive push 相关窄测为 `3 passed`，Web API `push_quality` 窄测为 `1 passed`。后续剩余学习任务建议继续“聊天模式分层”，再考虑把推送质量聚合温和接入主动推送优先级。

## 2026-05-26 追加：聊天模式分层

聊天模式分层 Step 18 已完成第一段：`ChatAgent` 新增轻量 `_classify_chat_mode(...)`，用于区分 `trade_execution`、`market_analysis`、`guide_video`、`trading_tool`、`event` 和 `general`。B 站直出推荐和回答后追加推荐现在只在 `guide_video` 模式触发；当用户把“多少钱/价格/趋势”等市场词和“攻略视频/B站”混在一起时，市场分析优先，返回实时订单摘要，不被 B 站视频或“暂未收录”抢答。`answer_stream` 走同样优先级。

本步已用项目内 `.venv\Scripts\python.exe` 完成红绿验证：分类器窄测为 `1 passed`，混合价格/视频的普通回答和流式回答窄测为 `2 passed`。后续可继续自然语言目标/计划模式，或者把 Scout 推送质量聚合接入主动推送优先级。

## 2026-05-26 追加：自然语言目标 / 计划模式

自然语言 planning Step 19 已完成第一段：`_classify_chat_mode(...)` 新增 `planning`，识别“计划/规划/目标/路线图/plan”以及“一周 + 赚/盈利/500p”这类目标计划请求。`ChatAgent.answer(...)` 和 `answer_stream(...)` 会在直接市场意图之后、B 站攻略之前返回安全计划草案，明确“不会直接下单、不会生成购买私聊”，并提示用户用 `/goal set ...` 显式创建跟踪目标。该模式不自动抓订单、不自动创建目标、不返回 B 站视频。

同时 `tool_router.select_candidate_tools(...)` 对计划请求加入 `plan` 候选，后续若要做确认式多步骤执行可以复用现有 AgentPlan trace。当前验证：planning 分类窄测 `1 passed`，planning 普通/流式回答窄测 `2 passed`，Router planning 候选窄测 `1 passed`。后续可继续增强 `/goal set` 的自然语言解析，提取目标金额、周期、预算和风险。

## 2026-05-26 追加：`/goal set` 自然语言目标解析

Step 20 已完成：`warframe_agent.goals.parse_goal_description_criteria(...)` 现在能从常见中文目标句中解析收益目标、周期、预算、风险和最低 ROI，并把收益目标同时保存为 `target_profit` 与兼容进度追踪的 `target_amount`。`format_goal_criteria_summary(...)` 会把保存结果转成回执摘要，方便用户确认 Agent 是否理解正确。

聊天命令 `/goal set|add|新建` 已接入该解析：明确包含“赚/盈利/攒 500p”这类收益目标时创建 `earn_platinum`；普通“找高利润倒卖机会”仍保持旧的 `maximize_profit` 与默认 `budget=500/min_roi=10`。自然语言 planning 仍不会自动创建目标，只继续提示用户用显式 `/goal set ...`。

本步验证使用项目内 `.venv\Scripts\python.exe`：`tests/test_chat_memory_commands.py` 为 `18 passed`，`tests/test_goals.py` 为 `20 passed`，planning/市场/B站优先级窄测为 `6 passed`，并完成 `warframe_agent` AST 检查。后续剩余学习任务建议继续 Web/API 目标创建入口复用解析 helper，或让 `/goal` 状态展示结构化 criteria 摘要。

## 2026-05-26 追加：确认式目标创建与命令式入口审计

Step 21 回答了“用户总不能一直 `/goal set ...`”这个 UX 问题：`/goal set` 继续作为底层显式入口，但自然语言 planning 现在会在识别到可追踪目标时生成待确认目标摘要。用户回复“确认创建/确认/可以/好的”后才写入 `GoalTracker`；回复“取消/不创建/算了”会清除待确认状态。该流程仍不会在初次 planning 请求里抓订单、生成 `/w` 或自动持久化目标。

同时已审计当前命令式入口：`/push opportunity`、`/cycle`、部分 `/trade add` 和直接 OP ID 已有自然语言桥；`/fav`、`/alert`、`/pref`、`/goal done/drop`、`/review done`、`/fissure add/remove` 仍偏命令式。后续最适合先改 `/alert` 和 `/fav`，再做 `/pref` 与 `/review done` 的确认式自然语言交互。

本步验证使用项目内 `.venv\Scripts\python.exe`：确认/命令目标窄测为 `7 passed`，聊天命令全量为 `21 passed`，planning 回归为 `2 passed`，并完成 `warframe_agent` AST 检查。

## 2026-05-26 追加：自然语言价格提醒

Step 22 已完成：用户现在可以直接说“充沛低于45p提醒我”“充沛高于100p通知我”来创建价格提醒，也可以说“取消充沛低于45p提醒”移除精确匹配的提醒。`/alert add/remove ...` 仍保留为底层命令入口。

该解析器保持保守：必须同时出现提醒词、方向词和价格数字才会写入 `AgentMemory.price_alerts`；普通问题如“充沛低于45p了吗”不会创建提醒，模糊“取消提醒”也不会删除已有提醒。处理顺序放在周期提醒之后，避免“地球变黑夜提醒我”这类周期订阅被价格提醒抢走。

本步验证使用项目内 `.venv\Scripts\python.exe`：自然语言提醒窄测为 `7 passed`，聊天命令全量为 `27 passed`，并完成 `warframe_agent` AST 检查。后续最适合继续 `/fav add/remove` 自然语言化，然后做 `/pref` 自然语言偏好更新。

## 2026-05-26 追加：自然语言收藏关注

Step 23 已完成：用户现在可以直接说“帮我关注充沛”“帮我收藏充沛”把物品加入收藏，也可以说“取消关注充沛”“取消收藏充沛”移除收藏。`/fav add/remove ...` 仍保留为底层显式入口，便于脚本、调试和精确命令使用。

该解析器同样保持保守：精确“关注列表/扫描关注/每日关注”仍走关注扫描；“充沛值得关注吗”这类问题不会写入记忆；“充沛低于45p提醒我”先由价格提醒处理，不会顺手加入收藏。实现上复用 `_handle_favorite_command(...)`，继续使用 `AgentMemory.with_favorite_item(...)` 去重和 `without_favorite_item(...)` 移除。

本步验证使用项目内 `.venv\Scripts\python.exe`：收藏相关窄测为 `7 passed`，聊天命令全量为 `33 passed`，并完成 `warframe_agent` AST 检查。后续最适合继续 `/pref` 自然语言偏好更新，然后做 `/goal done/drop` 或 `/review done` 这类需要确认的写入动作。

## 2026-05-26 追加：自然语言偏好更新

Step 24 已完成：用户现在可以直接说“我的预算300p，偏低风险，最低利润15%”“我偏好mod和赋能，最长周转3天”“平台设为xbox，关闭跨平台，最多显示10个结果”来更新长期交易偏好。`/pref ...` 仍保留为底层显式入口。

本步的关键规则是“长期偏好需要写入锚点”：只有出现“我的、偏好、设置、以后、平台、跨平台、最多显示”等明确长期设置语气时才写入 `AgentMemory.preferences`。普通问题如“300p预算买什么好”、价格提醒如“充沛低于45p提醒我”、收藏如“帮我收藏充沛”、交易机会控制如“交易机会只检测MOD”都会优先交给原有入口。

实现上新增 `PreferenceIntent` 与 `_parse_natural_language_preference(...)`，并在 `answer(...)` / `answer_stream(...)` 的价格提醒和收藏之后、普通问答之前接入。偏好写入复用 `AgentMemory.with_updated_preferences(...)`，覆盖预算、风险、最低 ROI、最长周转、品类、平台、跨平台和最大结果数。

本步验证使用项目内 `.venv\Scripts\python.exe`：偏好相关窄测为 `7 passed`，聊天命令全量为 `38 passed`，并完成 `warframe_agent` AST 检查。后续最适合继续 `/goal done/drop` 或 `/review done` 这类需要确认的自然语言写入。

## 2026-05-26 追加：自然语言目标完成/放弃确认

Step 25 已完成：用户现在可以说“完成第1个目标”或“放弃第1个目标”来发起目标状态更新，但不会立刻写入。Agent 会展示目标描述、目标 ID 和将变更的状态，用户回复“确认完成/确认放弃/确认”后才调用 `GoalTracker.update_goal_status(...)`。

本步把目标状态更新和目标创建确认分开：新增 `PendingGoalStatusConfirmation`，优先处理状态确认，再处理原有目标创建确认。自然语言状态入口只匹配活跃目标，支持序号、目标 ID 前缀和描述片段；疑问句如“完成目标了吗”不会创建待确认状态。显式 `/goal done ID` 与 `/goal drop ID` 仍保留即时命令行为。

本步验证使用项目内 `.venv\Scripts\python.exe`：目标状态相关窄测为 `12 passed`，聊天命令全量为 `45 passed`，并完成 `warframe_agent` AST 检查。后续最适合继续 `/review done` 自然语言交易复盘，因为它同样属于需要确认的写入动作。

## 2026-05-26 追加：自然语言交易复盘确认

Step 26 已完成：用户现在可以说“OP8K3A2Q 实际赚45p，结果不错，帮我复盘”发起机会复盘记录。Agent 会先展示机会 ID、物品、预期利润、实际利润和反馈，用户回复“确认复盘/确认记录/确认”后才写入 `TradingMemoryDB`。

本步延续确认式写入模式：新增 `ReviewDoneIntent` 与 `PendingReviewDoneConfirmation`，自然语言入口必须同时包含有效 OPID 和实际利润。确认写入复用 `_handle_review_record_command(...)`，因此长期记忆仍只保存 `_opportunity_review_safe_summary(...)` 允许的字段，不把 lookup 短期详情里的 whisper、profile 或玩家名写入长期记忆。

守卫规则保持保守：缺 OPID、缺有效利润、问句、教程文本和普通市场聊天不创建 pending；`answer_stream(...)` 与普通 `answer(...)` 走同一确认路径。显式 `/review done OPID 45 good` 仍保留即时命令行为。

本步验证使用项目内 `.venv\Scripts\python.exe`：复盘相关窄测为 `8 passed`，聊天命令全量为 `50 passed`，并完成 `warframe_agent` AST 检查。后续最适合继续 `/fissure add/remove` 自然语言裂缝订阅确认。

## 2026-05-26 追加：自然语言裂缝提醒确认

Step 27 已完成：用户现在可以说“提醒我钢铁后纪歼灭裂缝”发起裂缝提醒订阅。Agent 会先展示过滤条件，用户回复“确认订阅/确认”后才写入 `AgentMemory.fissure_alerts`；用户回复“取消”则清除待确认状态，不写入。

本步延续确认式写入模式：新增 `FissureAlertIntent` 与 `PendingFissureAlertConfirmation`，自然语言入口只解析裂缝订阅草案；确认后复用 `_add_fissure_alert(...)`，取消后复用 `_remove_fissure_alert(...)`，因此仍沿用原来的纪元、任务、地点、钢铁/普通过滤解析、去重、序号校验和持久化路径。

守卫规则保持保守：查询类句子如“现在有什么裂缝”不会创建 pending；“取消提醒”这种没有序号的模糊删除不会移除订阅；`热美亚裂缝`、收益问题和刷取问题不进入虚空裂缝提醒订阅。显式 `/fissure add ...` 与 `/fissure remove 1` 仍保留即时命令行为。

本步验证使用项目内 `.venv\Scripts\python.exe`：裂缝提醒自然语言窄测为 `6 passed`，聊天命令全量为 `56 passed`，并完成 `warframe_agent` AST 检查。`git diff --check` 对本步相关文件退出码为 0，仅有 CRLF 转换提示。

## 2026-05-27 追加：Scout 推送质量接入主动推送优先级

Step 28 已完成：`PriceMonitor._run_proactive_push(...)` 现在会在生成 `high_priority` 后读取 `TradingMemoryDB.summarize_push_quality(...)`，把历史推送复盘聚合转成 `push_quality_score=-1/0/1`。该分数只在相同 `priority` 的机会之间做稳定排序：好历史轻微前移，差历史轻微后移，低样本或无样本保持原顺序。

本步保持保守边界：不改 Scout 预筛选，不改 ROI/收益扫描，不绕过用户偏好过滤、`push_proactive` 开关、冷却去重和机会类别过滤，也不会因为坏历史直接过滤机会。写入推送历史的质量标注只包含 `push_quality_score`、`push_quality_reason`、`push_quality_reviewed_count`、`push_quality_good_rate` 和 `push_quality_false_positive_rate`，不包含 raw 订单、玩家名、profile、market URL、`/w` 或 token。

本步已用项目内 `.venv\Scripts\python.exe` 完成红绿验证：主动推送质量窄测先出现预期红测 `1 failed, 1 passed`，实现后为 `2 passed`；`tests/test_proactive_push.py -k "not scan_cycle"` 为 `24 passed, 1 deselected`；`tests/test_trading_memory.py -k "push_quality or opportunity_outcome"` 为 `6 passed, 14 deselected`；并完成 `warframe_agent` AST 检查。`git diff --check` 对本步相关文件退出码为 0，仅提示 `monitor.py` 和 `test_proactive_push.py` 下次 Git 触碰时 LF 会替换为 CRLF。后续若继续学习借鉴，更适合做质量 badge/Web 展示，或把低样本的 `pending_count` 做成“需要复盘”的提示，而不是进一步加重自动过滤。

## 2026-05-27 追加：Scout 推送质量 Web badge 展示

Step 29 已完成：长期交易记忆 Web 面板现在新增 `推送质量` 标签页，直接读取已有 `GET /api/trading-memory/push-quality`。用户可以在同一个观察面板里查看 `item_name/source/strategy/category` 分桶后的发送数、复盘数、待复盘数、好评率、误报率、利润偏差和好坏结果计数。

本步只做观察层透明化，不改变主动推送排序、冷却去重、用户偏好或机会扫描。前端将聚合质量转成 badge：未复盘显示 `待复盘`，好评率高且误报率低显示 `表现好`，误报率高或好评率低显示 `需谨慎`，其他显示 `观察中`。`pending_count` 被解释为“需要复盘”，不是坏质量。

安全边界保持不变：Web 只展示 `PushQualitySignal` 聚合字段，所有字段继续走 `escapeHtml`；不展示 raw metadata、raw orders、玩家名、profile URL、market URL、`/w`、whisper、token 或 raw chat。`tests/test_web_api.py` 也把 `/api/trading-memory/push-quality` 纳入 read-only 端点集合，确认它只调用 `summarize_push_quality`。

本步验证使用项目内 `.venv\Scripts\python.exe`：静态契约先出现预期红测 `1 failed`，实现后 `1 passed`；非沙箱 Playwright 定向验证 `test_trading_memory_panel_renders_tabs_safely_and_read_only` 与静态契约为 `2 passed`；非沙箱 Web API `push_quality or trading_memory_endpoints_are_read_only` 为 `2 passed, 68 deselected`。普通沙箱仍会在 Web app 导入时触发 SQLite WAL `unable to open database file`；较宽的 `whisper_compare` 选择集中有一个既有 XSS 断言失败，发生在进入交易记忆面板前，不属于本步改动。

## 2026-05-27 追加：主动推送通知卡片质量 badge

Step 30 已完成：Web 主动推送聊天通知卡片现在会读取真实 WebSocket payload 中的 `data.push_quality_*` 聚合字段，并在同一条 agent message 中显示轻量质量 badge。用户收到机会时可以直接看到 `表现好 / 需谨慎 / 观察中 / 待复盘`，以及复盘数、好评率和误报率。

本步只做展示层透明化，不改变主动推送排序、冷却去重、机会扫描、交易计划生成或任何写入行为。前端新增 `renderProactivePushQualityBadge(...)`，只消费 `push_quality_score`、`push_quality_reviewed_count`、`push_quality_good_rate` 和 `push_quality_false_positive_rate`；顶层或嵌套 payload 中的 profile URL、market URL、`/w`、whisper、玩家名、token、raw metadata 和 raw orders 都不会进入质量 badge。

本步验证使用项目内 `.venv\Scripts\python.exe`：静态契约先出现预期红测 `1 failed`，实现后为 `1 passed`；普通沙箱运行目标 Playwright 时 Web server 未就绪，按既有 SQLite/WAL 环境限制在非沙箱补跑 `test_websocket_proactive_push_renders_actionable_trade_plan`，结果为 `1 passed`。后续最适合继续做低复盘样本的确认式“复盘提醒”入口，或在 Web 面板中增加 source/strategy 对比排序。

## 2026-05-27 追加：推送质量面板复盘提醒入口

Step 31 已完成：`推送质量` 面板现在会在 `pending_count > 0` 或复盘样本少于 5 条时显示 `复盘提醒`。用户点击“填入复盘模板”后，Web 只把自然语言草稿填入聊天输入框，例如 `OP______ 实际赚__p，结果 good/bad/neutral，帮我复盘`，不会自动发送、不会调用写入 API，也不会生成会直接写库的 `/review done ...` 命令。

本步修正了一个重要边界：`push_quality` 是按 `item_name/source/strategy/category` 分桶的聚合信号，本身没有具体 OPID，因此不能假装直接复盘某条机会。入口只使用经过过滤的聚合字段 `item_name/source/strategy/pending_count/reviewed_count`；profile URL、market URL、`/w`、whisper、玩家名、token、raw metadata 和 XSS payload 都不会进入草稿。

写入链路仍复用 Step 26 的自然语言复盘确认：用户补上真实 OPID 和实际利润并发送后，ChatAgent 先创建待确认状态；只有用户再回复“确认复盘”才写入 `TradingMemoryDB.opportunity_outcomes`。本步验证使用项目内 `.venv\Scripts\python.exe`：静态契约先出现预期红测 `1 failed`，实现后为 `1 passed`；普通沙箱运行面板 Playwright 时 Web server 未就绪，非沙箱补跑 `test_trading_memory_panel_renders_tabs_safely_and_read_only` 为 `1 passed`。

## 2026-05-27 追加：推送质量 source/strategy 对比排序

Step 32 已完成：`推送质量` 面板现在新增本地排序控件，支持 `待复盘优先`、`表现最好` 和 `风险最高`。用户可以在同一批聚合质量记录中快速比较不同 source/strategy：哪些样本少需要复盘，哪些好评率高且误报低，哪些误报率或坏结果较高。

本步仍然只做只读观察层：不改后端 API，不新增 `sort` 参数，不改变 `TradingMemoryDB.summarize_push_quality(...)` 聚合逻辑，也不影响主动推送排序。排序只使用 `pending_count`、`reviewed_count`、`sent_count`、`good_rate`、`false_positive_rate`、`bad_count` 和 `avg_profit_delta` 等聚合字段；不展示 raw metadata、raw orders、玩家名、profile URL、market URL、`/w`、whisper 或 token。

本步验证使用项目内 `.venv\Scripts\python.exe`：静态契约先出现预期红测 `1 failed`，实现后为 `1 passed`；普通沙箱运行面板 Playwright 时 Web server 未就绪，非沙箱补跑 `test_trading_memory_panel_renders_tabs_safely_and_read_only` 为 `1 passed`，并确认切换排序不会向后端 URL 添加 `sort=`。

## 2026-05-27 追加：推送质量策略摘要标签

Step 33 已完成：`推送质量` 面板现在会为每条聚合记录显示只读摘要标签，包括 `样本不足`、`待补复盘`、`稳定盈利`、`高误报` 和 `观察中`。这些标签帮助用户快速扫读 source/strategy 的质量状态，而不是引入新的自动决策。

本步不改后端 API、不新增字段、不新增写入端点，也不影响主动推送排序、推送质量排序或复盘确认链路。摘要标签只使用 `reviewed_count`、`pending_count`、`good_rate`、`false_positive_rate`、`avg_profit_delta`、`good_count` 和 `bad_count` 等聚合数字字段；不读取或展示 raw metadata、raw orders、玩家名、profile URL、market URL、`/w`、whisper 或 token。

本步验证使用项目内 `.venv\Scripts\python.exe`：静态契约先出现预期红测 `1 failed`，实现后为 `1 passed`；普通沙箱运行面板 Playwright 时 Web server 未就绪，非沙箱补跑 `test_trading_memory_panel_renders_tabs_safely_and_read_only` 为 `1 passed`。测试覆盖 `样本不足`、`待补复盘`、`稳定盈利`、`高误报` 和 `观察中`，并确认摘要 helper 不引用敏感字段名。

## 2026-05-27 追加：Step 34 多 Agent 角色架构决策

Step 34 没有新增业务代码，而是完成 LangManus / OpenManus / Suna 多 Agent 架构的学习借鉴决策。结论是暂不复制完整多 Agent 产品架构，继续保留 `ChatAgent + ToolRouter + ModelOrchestrator` 的单 Agent 主链路；后续若进入实现，优先拆内部受限 Planner 和只读 Reviewer / Verifier，不引入 Browser Agent、Coder Agent、通用 Supervisor 或 Suna sandbox worker。

本轮同时把用户新增的三个云端 AI 纳入架构边界：`kimi-k2.6`、`glm-5.1`、`gpt-5.5` 继续作为 Scout / 复杂分析的任务化模型角色，统一通过 `ModelOrchestrator` 和 `llm.py` 调用；未来任何角色不得绕过模型路由直接读取 `.env` 或调用云端接口。详细决策见 `githubProduct/personal_agent_warframe_migration_step34_multi_agent_role_architecture_decision_zh.md`。

## 2026-05-27 追加：Step 35 AgentPlan 只读 Reviewer / Verifier 摘要

Step 35 已把 Step 34 的“先做内部受限 Planner 与只读 Reviewer / Verifier”落成最小代码能力。`AgentPlanSnapshot` 现在包含 `verification_note`、`blocked_reason` 和只读 `review` 摘要；`AgentPlanStep` 也包含步骤级 verification note 和 blocked reason。`review_execution_plan(...)` 只读取 `ExecutionPlan` 与 `ToolRegistry` 元数据，检查未知工具、未暴露工具、副作用工具、非只读 `safety_level`、递归敏感参数 key 和缺少 purpose 的步骤。

该实现仍然保持单 Agent 主链路：不引入 LangManus / Suna 式完整多 Agent runtime，不新增 Browser Agent、Coder Agent、通用 Supervisor 或 sandbox worker。通过审查的计划仍按原顺序执行；`review.status == "blocked"` 的计划会在执行前软拦截，不调用 executor，不执行任何计划步骤。三个云端 AI `kimi-k2.6`、`glm-5.1`、`gpt-5.5` 继续作为任务化模型角色保留在 `ModelOrchestrator` / `llm.py` 边界内，Reviewer 本身不调用云端模型、不读取 `.env`、不拼接 API header。

Web `/api/runtime/status` 和 Runtime Agent Plan 面板只展示安全摘要字段，不展示 raw arguments、result summary、final answer、model context、玩家 profile、`/w` 或 token。本步验证记录见 `githubProduct/personal_agent_warframe_migration_step35_plan_reviewer_verifier_zh.md`；普通沙箱仍会在 Web app 导入或 uvicorn 启动时触发既有 SQLite WAL 限制，Web API 与 Playwright 目标用例已在可写运行环境中补跑通过。

## 2026-05-28 追加：Step 36 长期运行与运维健康摘要

Step 36 回到 CowAgent / Suna / OpenClaw 的长期运行与运维控制面学习队列，落地为 `/api/runtime/status` 的只读 `ops_health` 聚合。它把 scheduler、background tasks、Feishu、WxPusher 和 daily report 的状态收敛为 `status`、`reason_count`、`reasons` 与 `components`，用于快速判断运行态是否退化。

本步只吸收 service health、trigger visibility 和 recovery reason summary 的可观测性，不引入控制能力。新增 reason code 包括 `scheduler_stopped`、`scheduler_job_failed`、`background_task_error` 和 `feishu_not_running`；组件详情只展示计数和布尔值，不展示单个 job id、task id、错误详情或任务结果。

Web Runtime 面板新增 `Ops Health` 摘要卡和只读详情区，继续使用前端脱敏和 `escapeHtml` 渲染。该面板不提供 start / stop / retry / repair 按钮，不调用 shell、Browser / GUI 自动化或云端模型，也不返回 Push token、UID、Feishu app_secret、chat_id、profile URL、`/w` 或 token。

验证记录见 `githubProduct/personal_agent_warframe_migration_step36_ops_health_summary_zh.md`：API 红测和 UI 红测均先按预期失败，随后 API 目标测试 `2 passed, 69 deselected`，Runtime Playwright 目标测试 `1 passed`，静态契约 `1 passed`，AST / JS 语法 / `git diff --check` 均通过。普通沙箱仍可能受既有 SQLite WAL / uvicorn 可写环境限制影响。

## 2026-05-28 追加：Step 37 可检查 Memory Vault 索引

Step 37 回到 OpenHuman / CowAgent 的可检查个人记忆学习队列，落地为 `warframe_agent.memory_vault` 和只读 `GET /api/memory/vault`。它把已有安全记忆来源聚合成 `MemoryVaultEntry`：`user_query`、`market_snapshot`、`recommendation`、`push_history`、`opportunity_outcome` 和 `conversation_log`。

本步只吸收 inspectable memory、source index 和 Markdown preview 的能力，不引入向量库、不新增 Obsidian 导出目录、不调用云端模型、不新增写入链路。API 返回 `generated_at`、`total`、`source_counts`、`entries` 和 `markdown_preview`，用于人工审查、调试和后续跨会话恢复。

安全边界保持保守：Vault 不返回原始用户消息、原始助手回复、raw tool arguments、raw result、玩家名、profile URL、`/w`、whisper、token、secret、Authorization、cookie、app_secret 或 chat_id。对话日志只进入工具名、上下文数量、工具数量和安全 session id，不导出 `user_message` 或 `assistant_reply` 字段。

验证记录见 `githubProduct/personal_agent_warframe_migration_step37_memory_vault_index_zh.md`：单元红测先失败于缺少 `memory_vault` 模块，API 红测在可写运行环境中先失败于 `404 != 200`；实现后 `tests/test_memory_vault.py` 为 `3 passed`，`tests/test_memory_recall.py` 为 `5 passed`，Web API 目标测试为 `2 passed, 70 deselected`。

## 2026-05-28 追加：Step 38 Browser / GUI Agent 安全边界

Step 38 回到 OpenManus / Open-AutoGLM 的 Browser / GUI Agent 学习队列，落地为 `warframe_agent.browser_gui_safety` 和 `/api/runtime/status.safety_policy.browser_gui_policy`。它先定义动作安全矩阵，而不是启用浏览器或桌面自动执行。

本步只吸收浏览器状态回灌、GUI 动作空间、人类接管和禁止动作边界。`allow_read_only` 覆盖公共页面读取、文本提取、截图和 DOM 检查；`requires_human_confirmation` 覆盖点击、输入、提交表单、下载、上传和剪贴板写入；`blocked` 覆盖登录、支付、删除、私信、下单、凭据输入、任意脚本和私网目标。

安全边界保持清晰：不新增 Browser Agent，不新增 Playwright / ADB / HDC executor，不注册 exposed tool，不改 `ChatAgent` 主链路，不新增自动触发器。Runtime 只返回聚合矩阵和安全示例，不返回真实 URL、DOM 原文、截图 OCR、cookie、localStorage、玩家 profile、`/w`、token 或 raw arguments。

验证记录见 `githubProduct/personal_agent_warframe_migration_step38_browser_gui_safety_boundary_zh.md`：单元红测先失败于缺少 `browser_gui_safety` 模块，runtime policy 红测先失败于缺少 `browser_gui_policy`，Web API 红测在可写运行环境中先失败于缺少 `browser_gui_automation`；实现后目标测试分别为 `5 passed`、`1 passed, 33 deselected`、`1 passed, 71 deselected`。

## 2026-05-28 追加：Step 39 语音和陪伴式体验安全边界

Step 39 回到 EchoBot / OpenHuman / OpenClaw 的语音和陪伴式体验学习队列，落地为 `warframe_agent.companion_experience` 和 `/api/runtime/status.safety_policy.companion_experience_policy`。它先定义 text-only 默认模式和高权限体验禁用边界，而不是启用真实语音、Live2D 或后台监听。

本步只吸收 persona response、voice、Live2D、fast reply vs slow task 的边界拆分：文本陪伴可以留在普通聊天路径；“一边陪我刷图一边后台盯价提醒”这类请求必须复用已有确认式提醒和任务；语音、麦克风、录音、Live2D、后台监听和平台 token 默认不可用；私聊、下单、联系卖家等交易动作继续阻断。

安全边界保持清晰：不新增 TTS/STT、模型下载、平台 token、前端控制按钮、ToolRegistry 工具、后台 worker 或 `ChatAgent` 主链路改动。Warframe 游戏内“同伴/宠物/库娃/库狛/守护”按普通游戏建议处理，不误判为人格陪伴或语音入口。

验证记录见 `githubProduct/personal_agent_warframe_migration_step39_companion_experience_boundary_zh.md`：单元红测先失败于缺少 `companion_experience` 模块，runtime policy 红测先失败于缺少 `companion_experience_policy`；实现后 `tests/test_companion_experience.py` 为 `6 passed`，runtime policy 目标测试为 `1 passed, 33 deselected`。Web API 目标测试在普通沙箱仍受 SQLite WAL 权限限制，本次提权重跑因本地 Codex 登录 token 失效未能执行，需要在可写运行环境中补跑。

## 2026-05-29 追加：Step 40 个人 Agent 学习阶段总复盘

Step 40 没有新增运行时代码，而是收束 Step 34-39 的个人 Agent 学习借鉴路线。总复盘记录在 `githubProduct/personal_agent_warframe_migration_step40_learning_phase_review_zh.md`，用于跨会话恢复“已覆盖主题、验证债务、下一阶段候选任务”。

本步结论是：主线学习队列已基本覆盖。多 Agent 架构、只读 Reviewer、长期运行健康摘要、可检查 Memory Vault、Browser/GUI 安全边界、语音和陪伴体验安全边界都已经落地为文档或最小代码能力。仍未产品化的方向包括多渠道 Gateway、skills / plugin 生态、真实语音、真实 Browser/GUI 自动执行、服务恢复和任意触发器平台。

下一阶段不再建议机械执行“剩余学习队列”，而应按候选分支选择：优先做 Step 35 的“软拦截 -> 用户确认 -> 受控执行”确认链路；其次在可写环境补跑 Step 39 Web API 验证；高权限能力必须先做权限、确认、可中断和不落盘 raw data 的设计。
## 2026-05-29 追加：Step 41 AgentPlan 受控执行确认链路

Step 41 回到 Step 35 的 `AgentPlan` 分支，把“blocked plan 只软拦截”推进为第一阶段受控确认执行。新增 `PlanConfirmationRequest` 和 `build_plan_confirmation_request(...)`，只允许 `missing_verification` 这种低风险缺口进入确认请求；确认码绑定当前 plan 的 goal、tool、arguments、purpose 和原始阻断原因。

`react_loop(...)` 新增可选 `plan_confirmation_token`。当确认码与当前 plan 指纹匹配时，系统会先用 `require_verification=False` 重新 review，确认仍为只读安全计划后才调用 `tool_executor`；确认码错误、plan 内容变化、或阻断原因是 `unknown_tool`、`non_exposed_tool`、`side_effect_tool`、`sensitive_arguments` 时仍保持 `plan_blocked`，不执行任何子工具。

本步没有新增 Web UI、pending plan 持久化、Browser/GUI/shell/scheduler executor，也没有放开 `set_alert`、私信、下单、登录、支付、删除、凭据输入等副作用动作。验证记录见 `githubProduct/personal_agent_warframe_migration_step41_controlled_plan_confirmation_zh.md`；目标测试 `tests/test_plan.py -k "plan_confirmation or confirmed_missing_verification"` 为 `6 passed, 17 deselected`。

## 2026-05-30 追加：Step 42 ChatAgent 计划确认闭环

Step 42 把 Step 41 的底层确认码接入 `ChatAgent`。当 `ToolRouter` 因 `missing_verification` 软拦截一个只读 plan 时，`ChatAgent` 会保存 `PendingAgentPlanConfirmation`，只记录原始用户消息、候选工具名、阻断原因和确认码，不保存 raw plan 或 raw tool args。

用户现在可以回复“确认执行”让 ChatAgent 重新调用原始消息，并把确认码传给 `react_loop(...)`；最终是否执行仍由 `ToolRouter` 重新做 plan 指纹匹配和 relaxed review 决定。用户回复“取消执行”会清空 pending 状态。普通“确认”不会触发计划执行，避免和目标、复盘、裂缝订阅等确认流混淆。

按最新用户指令，本步明确不考虑语音对话服务和真实语音，不新增 TTS/STT、麦克风、录音、Live2D 或常驻陪伴。验证记录见 `githubProduct/personal_agent_warframe_migration_step42_chat_plan_confirmation_zh.md`；目标测试 `tests/test_chat.py -k "agent_plan_confirmation"` 为 `5 passed, 69 deselected`。

## 2026-05-30 追加：Step 43 多渠道 Gateway 边界评估

Step 43 继续非语音学习借鉴路线，来源是 CowAgent / Suna / OpenClaw 的多入口个人 Agent 经验。它不新增真实平台连接器，而是先把 Web chat、WebSocket、local CLI、Feishu、WxPusher、未来社交评论和匿名 webhook 的入口 / 出口边界整理成只读 `gateway_policy`。

已落地 `warframe_agent.gateway_policy`，并在 `build_runtime_safety_policy(...)` 中新增 `gateway_policy` 和 `capabilities.multi_channel_gateway`。Web chat、WebSocket 和 local CLI 视为交互式用户输入；Feishu bot 只能复用已有确认流程；WxPusher / Feishu push 只作为出站通知；Bilibili 评论、匿名 webhook、GitHub issue、卖家 / 买家私信以及 shell、浏览器控制、文件写入、任意工具执行等动作默认阻断。

本步按最新用户指令继续避开语音对话服务和真实语音，不新增 TTS/STT、麦克风、录音、Live2D 或后台监听。验证记录见 `githubProduct/personal_agent_warframe_migration_step43_gateway_boundary_zh.md`；目标测试 `tests/test_gateway_policy.py tests/test_tool_registry.py -k "gateway_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `6 passed, 33 deselected`。

## 2026-05-30 追加：Step 44 Skills / Plugin 生态边界评估

Step 44 继续非语音学习借鉴路线，来源是 OpenManus / Suna / OpenClaw / Codex skills 的可扩展能力生态。它没有安装插件或启用 connector，而是先定义 skills、plugins、connectors 在进入运行时前的审查和权限边界。

已落地 `warframe_agent.plugin_policy`，并在 `build_runtime_safety_policy(...)` 中新增 `plugin_policy` 和 `capabilities.skills_plugin_ecosystem`。local/system/project skills 只作为 guidance；personal/local/Codex plugin 已安装后仍需 review；外部 connector 必须显式启用并确认；shell、文件写入、浏览器控制、scheduler 创建、凭据访问、社交发帖和交易动作默认阻断。

本步继续避开语音对话服务和真实语音，不新增 TTS/STT、麦克风、录音、Live2D 或后台监听。验证记录见 `githubProduct/personal_agent_warframe_migration_step44_plugin_policy_zh.md`；目标测试 `tests/test_plugin_policy.py tests/test_tool_registry.py -k "plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 为 `7 passed, 33 deselected`，Web API 可写环境补跑 `runtime_status_includes_read_only_safety_policy` 为 `1 passed, 71 deselected`。

## 2026-05-30 追加：Step 45 Runtime Policy 可见性

Step 45 继续非语音学习借鉴路线，来源是 Suna / OpenManus / OpenClaw 的运行态控制面透明化思路。它只把 Step 43 的 `gateway_policy` 和 Step 44 的 `plugin_policy` 以安全聚合字段展示到 Runtime 面板，不新增按钮、开关、安装入口、账号输入或任何真实外部入口。

已在 `warframe_agent/web/static/js/app.js` 新增 `Gateway Policy` / `Plugin Policy` 摘要卡和只读详情渲染函数，并补充前端敏感字段过滤，覆盖 `account_id`、`api_key`、`handler`、`params`、`manifest`、`payload` 等插件 / Gateway 相关 key。

验证记录见 `githubProduct/personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md`；`node --check warframe_agent\web\static\js\app.js` 退出码 0，静态契约测试 `test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections` 为 `1 passed`。完整 Playwright 浏览器目标测试在普通沙箱中仍复现 uvicorn 未就绪，随后在可写运行环境补跑通过，结果为 `1 passed`。

## 2026-05-30 追加：Step 46 非语音学习借鉴路线闭环审计

Step 46 没有新增运行时代码，而是对 CowAgent、OpenManus、LangManus、OpenHuman、EchoBot、Open-AutoGLM、OpenClaw、Suna / Kortix 的非语音学习借鉴路线做最终闭环审计。结论记录在 `githubProduct/personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md`：在暂不考虑语音对话服务和真实语音的前提下，本项目的非语音个人 Agent 学习借鉴路线已完成代码与文档闭环。

已完成能力包括：单 Agent 主链路保留、内部受限 AgentPlan reviewer / verifier、计划确认闭环、长期运行健康摘要、可检查 Memory Vault、Browser / GUI 安全边界、text-only 陪伴边界、多渠道 Gateway 边界、Skills / Plugin 生态边界，以及 Runtime 面板只读可见性。真实语音、真实 Browser / GUI executor、服务恢复 / 任意触发器平台、公共 webhook、平台私信和受控插件安装仍作为未来新阶段设计，不在当前闭环内推进。

最终验证记录见路线账本和 Step 46 报告：Gateway / Plugin / runtime policy 联跑为 `12 passed, 33 deselected`；Runtime 静态契约测试为 `1 passed`；Runtime 完整 Playwright 浏览器目标测试为 `1 passed`；相关 Python 文件 AST OK；`node --check warframe_agent\web\static\js\app.js` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。非语音学习借鉴路线不再保留未完成验证债务。

## 2026-05-30 追加：Step 47 最终 Playwright 验证债务收束

Step 47 只做验证和文档状态收束，不新增运行时代码。计划记录在 `docs/superpowers/plans/2026-05-30-learning-borrowing-final-playwright-closure.md`。

普通沙箱补跑 `tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state` 仍失败于 `RuntimeError: Web server did not become ready`；可写运行环境补跑同一目标测试通过，结果为 `1 passed`。因此 Step 45 Runtime Policy 可见性可以从 `90% / 待评估` 更新为 `100% / 已完成`。

## 2026-05-30 追加：Step 48 未来高权限能力准入策略

Step 48 是非语音学习借鉴路线完成后的新阶段安全基座，不是旧队列的补课。它借鉴 OpenManus / Suna / OpenClaw 中 sandbox、worker、browser、plugin、connector 和触发器的高权限边界思路，但只在本项目中落为只读准入策略。

已新增 `warframe_agent.future_capability_policy`，并把 `future_capability_policy` 嵌入 `build_runtime_safety_policy(...)`。Runtime safety 中的 `future_capability_admission` 仅表示“准入策略可见”，`enabled=False` 表示未来高权限运行时能力未启用。

分类结果覆盖 `allow_design_only`、`requires_new_stage_design`、`frozen_by_current_user_instruction`、`blocked_public_or_private_inbound` 和 `blocked_uncontrolled_runtime`。真实语音、TTS/STT、麦克风、录音、Live2D、后台监听继续冻结；Browser/GUI executor、服务恢复、任意触发器、插件安装、connector 启用、匿名 webhook、公共评论命令、平台私信命令、shell 和通用文件写入都没有进入运行时。

子代理复核发现敏感 capability 名和 `enabled=True` 语义风险；已补测试并修复：疑似 token / secret / api_key 的 capability 名统一归一为 `unknown_future_capability`，`future_capability_admission.enabled` 改为 `False`。目标补测为 `9 passed, 33 deselected`；最终 policy 联跑为 `20 passed, 33 deselected`；Web API 可写运行环境补跑为 `1 passed, 71 deselected`；AST OK。

## 2026-05-31 追加：Step 49 Future Capability Runtime 可见性补齐

Step 49 不是旧学习借鉴队列的补课，而是 Step 48 新阶段安全准入层的 UI 可见性改善。它把 `future_capability_policy` 以只读摘要和矩阵展示到 Runtime 面板，让未来高权限候选能力的状态能被用户检查。

已在 Runtime 面板新增 `Future Capability Policy` 摘要卡和详情区，展示 `future_capability_admission`、`design_required_before_runtime`、`runtime_enablement_allowed=false`、`requires_new_stage_design` 和 `blocked_uncontrolled_runtime`。`future_capability_admission.enabled=False` 继续表示策略可见但运行时入口未启用。

本步没有新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端控制按钮、后台 worker 或真实语音能力。真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续冻结。

验证记录：静态红测先失败于缺少 `renderRuntimeFutureCapabilityPolicy`；实现后 `node --check` 退出码 0，Runtime 静态契约 `1 passed`，完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`，Web API 可写环境补跑 `1 passed, 71 deselected`。

## 2026-05-31 追加：Step 50 学习借鉴与改善完成 Runtime 快照

Step 50 把“旧非语音学习借鉴路线已完成，Step48/49 改善已完成”从文档结论提升为 `/api/runtime/status.learning_completion` 和 Runtime 面板可见的只读快照。它不是旧队列补课，也不是高权限能力启用。

已新增 `warframe_agent.learning_completion`，并在 Runtime 面板新增 `Learning Completion` 摘要卡和详情区。快照显示 `status=complete`、`legacy_non_voice_learning_complete=true`、`improvement_closure_complete=true`、`runtime_enablement_changed=false`、最近完成步骤和仍需另开设计的高权限候选能力。

安全边界保持不变：没有新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端控制按钮、后台 worker 或真实语音能力。真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续冻结。

验证摘要：`tests/test_learning_completion.py` 为 `3 passed`；Web API 可写环境补跑 `2 passed, 70 deselected`；完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`；最终 policy / gateway / plugin / runtime safety 联跑 `23 passed, 33 deselected`；Runtime 静态契约复核 `1 passed`；AST OK；`node --check` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

验证记录：`tests/test_learning_completion.py` 为 `3 passed`；`node --check` 退出码 0；Runtime 静态契约 `1 passed`；Web API 可写环境补跑 `2 passed, 70 deselected`；完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`。

## 2026-05-31 追加：Step 51 学习借鉴完成验收清单快照

Step 51 不是继续旧学习队列，而是在 Step 50 的完成快照上补一层机器可读验收清单。它把“为什么算完成”结构化为 `acceptance_status=accepted`、`latest_closure_step=step50_learning_completion_runtime_snapshot`、`acceptance_record_step=step51_learning_completion_acceptance_snapshot` 和安全 checklist。

已新增的 checklist 覆盖：旧非语音学习路线完成、Step 48 / Step 49 改善完成、Runtime API 暴露完成快照、Runtime 面板展示完成快照、高权限运行时未启用、真实语音继续冻结、未来高权限能力必须另开新阶段，以及 Step 50 闭环快照已存在。

安全边界保持不变：没有新增 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口、前端控制按钮、后台 worker 或真实语音能力。真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续冻结。

验证摘要：`tests/test_learning_completion.py` 为 `5 passed`；`node --check` 退出码 0；Runtime 静态契约 `1 passed`；Web API 可写环境补跑 `2 passed, 70 deselected`；完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`；最终 policy / gateway / plugin / runtime safety 联跑 `25 passed, 33 deselected`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

## 2026-05-31 追加：Step 52 学习路线终止条件与新阶段入口

Step 52 只做文档级终止条件收束，不改运行时代码。当前个人 Agent 非语音学习借鉴路线已完成并验收：Step 50 是完成闭环，Step 51 是机器可读验收记录，旧学习借鉴路线终止于 Step 51。

后续如果再次出现“继续下一步规划直到借鉴完成 / 改善完成 / 开始执行”这类同义请求，默认应先复核 `learning_completion.status=complete`、`acceptance_status=accepted`、`latest_closure_step=step50_learning_completion_runtime_snapshot` 和 `acceptance_record_step=step51_learning_completion_acceptance_snapshot`，然后维护终止条件，而不是继续往旧学习队列追加运行时代码。

真实 Browser / GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装、connector 启用、webhook / DM 命令入口都必须作为独立新阶段另开设计；`future_capability_admission.enabled=False` 继续表示这些能力没有启用。

## 2026-05-31 追加：Step 53 学习路线实现不足复核

Step 53 是全路线实现不足复核和历史文案防误读标注，不是旧学习借鉴队列补课，也不是运行时代码改动。复核结论记录在 `githubProduct/personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md`。

复核结果：没有发现需要新增代码、API、Runtime UI 或测试覆盖的缺口；`learning_completion.status=complete`、`acceptance_status=accepted`、`acceptance_snapshot`、`future_capability_admission.enabled=False` 和 Runtime 面板只读展示已经能证明学习借鉴与改善闭环。唯一需要改善的是文档顶部和历史段落的可读性：早期“剩余队列 / 下一步 / 债务”语句必须明确标注为历史记录。

验证摘要：policy / gateway / plugin / future capability / learning completion 联跑 `25 passed, 33 deselected`；Runtime 静态契约 `1 passed`；AST OK；`node --check` 退出码 0；文档关键语义和 `git diff --check` 均通过。

本步已在本文顶部加入当前权威状态说明。后续如果再次出现同义“继续到借鉴完成并执行”的请求，默认动作仍是复核完成态并维护终止条件，而不是从历史队列继续追加运行时代码。

## 2026-05-31 追加：Step 54 项目整体验收运行与实现真实性复核

Step 54 是项目运行验收，不是旧学习借鉴队列补课。它响应用户要求，实际运行全量测试、重点策略测试、Runtime 静态契约、JS/AST 检查和本地 uvicorn 烟测，检查此前实现是否真实存在。

复核结果：学习借鉴相关实现真实落地。`warframe_agent.learning_completion`、`future_capability_policy`、`gateway_policy`、`plugin_policy`、`safety_policy`、`/api/runtime/status` 和 Runtime 面板展示均有真实代码与测试覆盖；服务烟测返回 `learning_status=complete`、`acceptance_status=accepted`、`future_enabled=False`。

风险结果：项目全量测试仍未全绿。可写运行环境全量 `pytest tests` 结果为 `8 failed, 1162 passed, 7 warnings`，失败集中在聊天查价直答与旧 prompt 断言冲突、ToolRouter 安全策略旧期望、WebSocket 错误路径和前端 XSS 文本泄漏。

安全边界保持不变：本步未安装依赖、未下载文件、未上传 GitHub，未新增或启用 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。

下一步应作为普通缺陷修复任务处理全量测试失败，优先修复前端 XSS 文本泄漏和 WebSocket 错误路径；学习借鉴路线仍保持完成和验收状态。

## 2026-05-31 追加：Step 55 全量测试失败修复

Step 55 是项目质量修复，不是旧学习借鉴路线补课。它针对 Step 54 发现的 8 个失败做最小修复，并保持高权限能力冻结。

已完成并验证的部分：聊天别名 / RAG / 记忆 prompt 相关 5 个失败已修复，Router plan 聚合旧测试契约已更新；聊天广域回归 `79 passed`，Router / plan / tool context 回归 `37 passed`，6 个非 UI 旧失败定向验证 `6 passed`。

前端补丁已实现但待验证：`chat.js` 新增 unsafe inline HTML 剥离和 WebSocket readyState 兼容 helper，用于修复 XSS 文本泄漏和 WebSocket 错误路径 race。普通沙箱仍无法启动 Playwright web server，可写环境复跑被 quota / approval 限制拒绝，因此这 2 个 UI 用例和全量 suite 不能标为已通过。

安全边界保持不变：没有安装依赖、下载文件或上传 GitHub；没有启用 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力；ToolRouter 对敏感 plan 参数的阻断没有放宽。

## 2026-05-31 追加：Step 56 虚空裂缝聊天查询修复

Step 56 是项目质量修复，不是旧学习借鉴路线补课。它响应用户反馈，修复聊天中“虚空裂缝 / 裂隙 / 裂缝”提问返回内容缺少和不符合筛选的问题。

根因是聊天层虽然已能把“虚空裂缝”归一到 `void_fissure`，但此前只使用 `GameEvent.description` 展示，不能根据原始消息里的 `古纪 / 后纪 / 钢铁 / 普通 / 捕获 / 生存` 等筛选词过滤，也缺少结构化结束时间。

已落地内容：`ChatAgent._query_events_result(...)` 新增 `source_query`；`void_fissure` 查询优先使用 `EventTracker.get_active_fissures()` 的结构化数据；裂缝回答按纪元、任务类型、普通 / 钢铁模式过滤，并展示 `纪元 任务类型 普通/钢铁 @ 节点 | 结束: UTC 时间`。

验证摘要：新增红测先以 `2 failed` 复现筛选不生效和详情缺失；修复后裂缝目标聊天回归 `4 passed, 72 deselected`，事件格式化回归 `4 passed, 21 deselected`，ToolRouter 事件 / farming route 回归 `3 passed, 34 deselected`，裂缝提醒守卫 `6 passed, 50 deselected`，`tests/test_chat.py` 全量 `76 passed`，ReAct query_events 安全上下文 `1 passed`，AST OK。

安全边界保持不变：未安装依赖、未下载文件、未上传 GitHub；未新增 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。Step 55 的前端 Playwright 剩余验证状态不因本步改变。

## 2026-06-01 追加：Step 57 活动与虚空商人回复体检已执行

Step 57 已执行完成。它响应用户要求，系统检查活动查询、具体事件、Baro / 虚空商人 MOD 和库存、玩家链接追问、不支持活动以及跨意图优先级的用户回复是否存在答非所问、内容缺失或措辞误导。

新增 `tests/test_chat_event_replies.py` 多问法矩阵后，红测确认了四类真实问题：虚空商人库存式问法没有明确“仅展示可分析的 Mod / 赋能”；`热美亚裂缝现在有吗` 曾被 `裂缝` 误抢到虚空裂缝；具体限时活动问法会混入其他限时活动；Baro 后续玩家链接状态会污染后续普通市场链接查询。修复后，`钢铁歼灭现在有吗` 也会进入结构化虚空裂缝详情，而不是限时活动。

已完成最小修改：`warframe_agent/baro.py` 增加 Baro 可分析范围说明；`warframe_agent/chat.py` 增加限时活动专用别名、具体活动过滤、Baro 后续让路直接市场物品查询、以及裂缝详情问法识别。执行记录已写入 `githubProduct/personal_agent_warframe_migration_step57_event_baro_response_audit_zh.md`。

验证摘要：补充红测修复前 `2 failed`；修复后对应红测 `2 passed`；Step57 回复矩阵 `10 passed`；Baro / events / ToolRouter / Step57 focused suites `83 passed`；聊天广义回归 `18 passed, 114 deselected`；AST OK。

安全边界保持不变：未安装依赖、未下载文件、未上传 GitHub；未新增 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。

## 2026-06-01 追加：Step 58 已关闭 Step55 Playwright / 全量回归债务

已执行“Step55 Playwright 与全量回归收尾”任务，计划记录在 `docs/superpowers/plans/2026-06-01-step55-playwright-full-regression-closure.md`，执行报告记录在 `githubProduct/personal_agent_warframe_migration_step58_step55_playwright_full_regression_closure_zh.md`。

路线判断：当前路线没有偏离。Step 58 是 Step 55 项目质量修复的验证收尾，不是旧学习借鉴队列重启，也不是高权限能力启用。

根因复核：普通沙箱中两个 Playwright 目标测试仍失败于 `RuntimeError: Web server did not become ready`；直接启动 uvicorn 后确认是 `TradeHistoryDB()` 在 `PRAGMA journal_mode=WAL` 时触发 `sqlite3.OperationalError: unable to open database file`，属于 SQLite WAL / 数据目录写入限制。可写环境中测试进入浏览器断言，唯一剩余失败是聊天消息 DOM 的 `data-raw` 属性仍保存转义后的 `data-xss` 文本。

已完成最小修复：`warframe_agent/web/static/js/chat.js` 新增 `safeChatRawText(...)`，让 agent 消息 `data-raw`、WebSocket token 累积、done reply、direct reply 和 REST fallback reply 都保存剥离危险 inline HTML 后的安全文本；保留 whisper 命令识别、复制按钮和聊天历史持久化行为。

验证结果：`node --check warframe_agent\web\static\js\chat.js` 和 `node --check warframe_agent\web\static\js\chart.js` 均退出码 0；两个 Step55 Playwright 目标测试 `2 passed in 28.70s`；完整 `pytest tests` 为 `1182 passed, 7 warnings in 331.32s`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

安全边界：未安装依赖、未下载文件、未上传 GitHub；未新增 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力；未放宽 XSS 断言。

最终结论：Step55 遗留的两个前端 Playwright 目标测试和完整全量回归债务已关闭。后续若继续项目质量修复，应基于新的用户反馈或新的测试失败另开计划。
