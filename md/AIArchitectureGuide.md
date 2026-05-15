# Warframe 交易助手项目 -- 完整技术文档

## 一、项目概述

本项目是一个基于 Python 的 Warframe 游戏交易辅助智能体（Agent），通过对话式交互帮助玩家查询市场价格、搜索紫卡（Riven）、分析投资机会、监控价格变动。系统融合了本地 Ollama 模型和云端大语言模型（LLM），结合 warframe.market API 实现实时数据查询，并通过 WebSocket 提供流式对话体验。

### 核心能力

- **对话式交易助手**：用户通过自然语言（中文/英文）查询物品价格、对比买卖、获取私聊命令
- **紫卡（Riven）搜索**：按武器名、正/负属性、价格上限过滤 warframe.market 拍卖
- **价格监控与提醒**：后台定时轮询，价格触及阈值时主动推送
- **投资顾问**：Prime 套装套利分析（散买部件 vs 整套卖出），按 ROI 排序
- **Mod 翻转器**：找出低级买、满级卖利润最高的 Mod
- **套装利润计算器**：对比整套买卖 vs 拆件买卖的利润差异
- **飞书机器人**：WebSocket 长连接模式，无需公网 IP
- **微信推送（WxPusher）**：每日价格报告、价格提醒推送到微信
- **多模型协作**：本地 Ollama（qwen3:8b）处理简单查询，云端 API 处理复杂分析
- **游戏事件追踪**：Baro 虚空商人来访、Prime Vault 回归、虚空裂缝等
- **RAG 物品检索**：基于 n-gram 和语义 embedding 的物品名模糊匹配

### 技术栈

- **语言**：Python 3.10+
- **Web 框架**：FastAPI + Uvicorn
- **实时通信**：WebSocket（FastAPI 原生）
- **LLM**：Ollama 本地模型（warframe-agent / qwen3:8b）+ 云端 OpenAI 兼容 API
- **数据源**：warframe.market v1/v2 API、Warframe 官方 World State API
- **存储**：SQLite（价格缓存、价格历史、交易历史）、JSON 文件（配置、记忆、别名）
- **前端**：原生 HTML/CSS/JS，WebSocket 通信
- **其他**：Playwright（浏览器抓取备选）、numpy（语义搜索）、lark-oapi（飞书 SDK）

---

## 二、项目结构

```
F:\giteeProject\warframe\
├── main.py                          # CLI 入口，菜单式交互
├── start_web.py                     # Web 服务启动脚本（uvicorn）
├── requirements.txt                 # Python 依赖
├── .env                             # 环境变量（云端 API 配置）
│
├── warframe_agent/                  # 主包
│   ├── __init__.py
│   ├── config.py                    # 全局配置（路径、模型、阈值、缓存TTL）
│   ├── agent.py                     # WarframeAgent — 物品查询、日报生成
│   ├── chat.py                      # ChatAgent — 对话式交易助手核心（~2100行）
│   ├── session.py                   # SessionContext — 多轮对话上下文管理
│   ├── dictionary.py                # ItemResolver — 物品名解析（别名→market_id）
│   ├── names.py                     # 物品显示名（中文优先）
│   ├── market.py                    # warframe.market API 客户端（订单、统计、缓存）
│   ├── riven.py                     # 紫卡搜索（属性解析、API 查询、过滤）
│   ├── llm.py                       # LLM 统一接口（本地/云端路由、流式输出）
│   ├── monitor.py                   # PriceMonitor — 后台价格监控线程
│   ├── scanner.py                   # OpportunityScanner — 机会扫描器
│   ├── investment.py                # Prime 套装投资分析
│   ├── mod_flipper.py               # Mod 翻转分析器
│   ├── set_profit.py                # Prime 套装利润计算器
│   ├── strategies.py                # 交易策略模板（低/中/高风险）
│   ├── scout.py                     # 多模型智能预筛选（用云端 LLM 缩小候选范围）
│   ├── knowledge.py                 # MarketKnowledge — 结构化知识库
│   ├── memory.py                    # AgentMemory — 持久化记忆（收藏、提醒、目标）
│   ├── goals.py                     # 目标引擎（创建、规划、执行、反馈）
│   ├── rules.py                     # 规则引擎（替代 LLM 的市场决策）
│   ├── feedback.py                  # 反馈分析器（策略胜率、自学习）
│   ├── patterns.py                  # 模式学习（从交易历史提取规律）
│   ├── events.py                    # EventTracker — 游戏事件追踪
│   ├── baro.py                      # Baro 虚空商人库存分析
│   ├── game_data.py                 # GameDataStore — 游戏数据查询（Mod效果、杜卡特值）
│   ├── price_history.py             # PriceHistoryDB — 价格历史 SQLite
│   ├── trade_history.py             # TradeHistoryDB — 交易历史 SQLite
│   ├── trade_intent.py              # 交易意图检测（买/卖/价差/趋势）
│   ├── conversation_log.py          # 对话日志（JSONL 格式）
│   ├── formatter.py                 # 输出格式化（私聊命令、订单表格）
│   ├── rag.py                       # RAG 物品检索（n-gram + 语义搜索）
│   ├── relics.py                    # 遗物掉落数据库
│   ├── scraper.py                   # Playwright 浏览器抓取（备选方案）
│   ├── tool_router.py               # 工具路由器（LLM function calling）
│   ├── push.py                      # WxPusher 微信推送
│   ├── feishu.py                    # 飞书机器人（WebSocket 长连接）
│   ├── warframes.py                 # Prime 套装解析（部件识别、套装分组）
│   ├── report.py                    # 日报生成
│   └── web/
│       ├── app.py                   # FastAPI 应用（REST API + WebSocket）
│       └── static/
│           ├── index.html           # 前端主页
│           ├── js/                  # app.js, chat.js, sidebar.js, chart.js
│           └── css/                 # style.css, variables.css, animations.css, responsive.css
│
├── tests/                           # pytest 测试套件（55+ 个测试文件）
├── data/                            # 数据目录
│   ├── item_aliases.json            # 手动别名映射（中文→market_id）
│   ├── generated_aliases.json       # 自动生成的别名（~739KB）
│   ├── items_full.json              # 完整物品数据（~1.3MB）
│   ├── rag_items.jsonl              # RAG 检索语料（~1.4MB）
│   ├── watchlist.json               # 关注列表
│   ├── agent_memory.json            # Agent 持久化记忆
│   ├── conversation_logs.jsonl      # 对话日志
│   ├── price_cache.db               # 市场价格 SQLite 缓存
│   ├── price_history.db             # 价格历史 SQLite
│   ├── trade_history.db             # 交易历史 SQLite
│   ├── game_events_cache.json       # 游戏事件缓存
│   ├── feishu_config.json           # 飞书配置
│   ├── push_config.json             # 微信推送配置
│   ├── goals.json                   # Agent 目标
│   ├── ducat_values.json            # 杜卡特价值映射
│   ├── relic_sources.json           # 遗物来源数据
│   ├── relic_vault_status.json      # 遗物 Vault 状态
│   ├── relics_drop_data.json        # 遗物掉落数据
│   └── export/                      # Warframe 游戏导出数据（多语言JSON）
│       ├── ExportRelicArcane_zh.json / _en.json
│       ├── ExportUpgrades_zh.json / _en.json
│       ├── ExportWarframes_zh.json / _en.json
│       └── ...
│
├── scripts/                         # 辅助脚本
├── tools/                           # 构建工具（build_item_data.py）
├── githubProduct/                   # 第三方数据源（warframe-items, warframe-drop-data）
└── docs/                            # 文档
```

---

## 三、模块详解

### 3.1 `config.py` -- 全局配置

路径：`warframe_agent/config.py`

所有可调参数集中管理，通过环境变量和硬编码默认值配置：

- **路径常量**：`DATA_DIR`、`REPORT_DIR`、`EXPORT_DIR`、各 JSON 文件路径
- **模型配置**：
  - `MODEL_NAME = "warframe-agent"`（Ollama 本地对话模型）
  - `ROUTER_MODEL_NAME = "qwen3:8b"`（路由器模型）
  - `CLOUD_API_BASE`、`CLOUD_API_KEY`、`CLOUD_MODEL`（云端 API，从 `.env` 读取）
  - `MODEL_ROUTING = "auto"`（"auto"/"local"/"cloud"，控制路由策略）
  - `COMPLEXITY_THRESHOLD = 3`（复杂度分数阈值，超过则切换云端）
- **缓存配置**：`ORDER_CACHE_TTL=60s`、`STATS_CACHE_TTL=300s`、`CACHE_MAX_SIZE=200`
- **多轮对话**：`CONTEXT_WINDOW=6`（注入 LLM 的历史轮数）、`MAX_HISTORY_MESSAGES=20`
- **主动智能**：`TREND_THRESHOLD_PERCENT=15`、`ANOMALY_THRESHOLD_PERCENT=30`
- **语义 RAG**：`EMBEDDING_MODEL="nomic-embed-text"`、`EMBEDDING_ENABLED=True`
- **推理规划**：`MAX_TOOL_ITERATIONS=3`、`REACT_MODEL="qwen3:8b"`
- **深层智能**：`PATTERN_DISCOVERY_INTERVAL=12`（每12次扫描发现模式）、`GOAL_GENERATION_INTERVAL=6`
- **多模型预筛选**：`SCOUT_MODELS`（mod_flipper→kimi-k2.6、set_profit→glm-5.1、investment→gpt-5.5）
- **Export 文件对**：`EXPORT_FILE_PAIRS` 定义中英文导出文件对应关系

### 3.2 `agent.py` -- WarframeAgent

路径：`warframe_agent/agent.py`

顶层 Agent 类，提供基础查询能力：

- `WarframeAgent.__init__(resolver)`：初始化物品解析器，fallback 为 LLM 解析
- `lookup_item(name)`：查询物品价格，返回 `LookupResult`（含 item_id、来源、格式化文本、私聊命令）
- `rebuild_dictionary()`：重建本地物品字典缓存
- `generate_daily_report()`：根据 watchlist.json 生成每日价格报告
- `_llm_and_validate(name)`：静态方法，用 Ollama 解析物品名并验证 market_id 有效性

### 3.3 `chat.py` -- ChatAgent（核心模块）

路径：`warframe_agent/chat.py`

这是整个系统最核心的模块（约2100行），实现对话式交易助手的全部逻辑。

#### 3.3.1 ChatAgent 类

构造函数接收多个可注入依赖：`resolver`（物品解析器）、`order_fetcher`（订单获取）、`model_call`（LLM 调用）、`memory`（记忆）、`rag_search`（RAG 检索）、`price_db`（价格历史）、`router_call`（路由器调用）、`knowledge`（知识库）、`event_tracker`（事件追踪器）。

**核心方法 `answer(message)`** 的处理流程（优先级从高到低）：

1. **命令处理**：以 `/` 开头的命令（如 `/memory`、`/fav add`、`/alert add`、`/scan`、`/pref`）
2. **关注列表扫描**：匹配 "扫描关注" 等关键词
3. **紫卡查询**：检测紫卡关键词（"紫卡"、"裂罅"、"riven"），优先确定性解析
4. **紫卡追问**：基于上一次紫卡查询的上下文过滤（如 "在线的"、"便宜的"）
5. **事件/工具查询**：检测事件类关键词或交易工具类关键词，走路由器
6. **Warframe 套装查询**：`price_warframe_query` 处理 Prime 套装相关查询
7. **追问检测**：`is_followup` 检测短追问（如 "呢"、"那"、"多少了"），复用上下文
8. **物品匹配与 LLM 回答**：解析物品名 → 获取订单 → 构建上下文 → 调用 LLM
9. **路由器兜底**：物品匹配失败时尝试 tool_router
10. **最终兜底**：提示用户输入有效物品名

**流式版本 `answer_stream(message)`**：逻辑与 `answer` 一致，但使用 `AsyncIterator[str]` 逐 token 输出。

#### 3.3.2 辅助函数

- `build_system_context()`：构建注入 LLM 的富上下文（市场概况、游戏事件、交易统计、策略反馈）
- `build_chat_messages()`：组装 LLM 消息列表（system prompt + 历史 + 当前查询 + 物品上下文）
- `build_item_context()`：为单个物品构建价格上下文（卖价、买价、价差、私聊命令）
- `fallback_answer()`：LLM 不可用时的确定性回答
- `_deterministic_trade_intent_answer()`：根据交易意图（买/卖/价差/趋势）生成确定性回答
- `_self_check()`：LLM 输出自检，纠正价格数据不一致
- `is_chat_exit()`：检测退出命令（q/quit/exit/退出）
- `call_ollama_router()`：调用路由器模型进行意图分类

### 3.4 `session.py` -- 会话上下文

路径：`warframe_agent/session.py`

- `SessionContext` 数据类：维护 `last_item_ids`、`last_query_type`、`last_intent`、`history`
- `to_messages(limit, current_query)`：将历史对话转为 Ollama messages 格式，支持按相关性排序（关键词重叠 + 时间衰减）
- `is_followup(message)`：检测追问语句（长度 <= 40 且包含 "那"、"呢"、"多少了" 等关键词）
- `FOLLOWUP_TERMS`：30+ 个追问关键词列表

### 3.5 `dictionary.py` -- 物品名解析

路径：`warframe_agent/dictionary.py`

`ItemResolver` 类实现多层解析策略：

1. **手动别名**（`item_aliases.json`）：最高优先级，用户自定义映射
2. **字典匹配**（`item_dictionary_cache.json`）：从游戏导出数据构建的中英文名→market_id 映射
3. **自动生成别名**（`generated_aliases.json`）：仅对含 CJK 字符的输入生效
4. **规范化**：直接将输入转为 market_id 格式（小写、下划线分隔）
5. **LLM 兜底**：调用 Ollama 解析并验证

关键函数：
- `normalize_lookup_key(value)`：去空格、转小写
- `normalize_market_id(value)`：转小写、非字母数字替换为下划线
- `_build_dictionary()`：从 Export 文件对（中英文）构建字典

### 3.6 `market.py` -- 市场 API 客户端

路径：`warframe_agent/market.py`

与 warframe.market API 交互的核心模块：

- **双层缓存**：内存 LRU 缓存（`OrderedDict`）+ SQLite 持久化缓存（`price_cache.db`）
- **速率限制**：线程安全的 `_wait_for_rate_limit()`，~3 req/s，带随机抖动
- **重试机制**：最多 3 次重试，429 时指数退避
- `fetch_orders(item_id)`：获取物品订单（v2 API），自动缓存
- `fetch_item_statistics(item_id)`：获取 48 小时成交量（v1 API）
- `best_sellers(orders, limit, rank_filter)`：筛选最低卖价的在线卖家
- `best_buyers(orders, limit, rank_filter)`：筛选最高收价的在线买家
- `build_buy_plan(orders, needed)`：贪心算法组合购买计划
- `fetch_orders_async(item_id)`：异步版本（`asyncio.to_thread` 包装）
- `warm_persistent_cache()`：启动时从 SQLite 预热内存缓存

数据类：`MarketOrder`（订单）、`BuyPlanEntry`（购买计划条目）、`BuyPlan`（购买计划）

### 3.7 `riven.py` -- 紫卡搜索

路径：`warframe_agent/riven.py`

完整的紫卡拍卖搜索系统：

- **属性映射**：`RIVEN_ATTRIBUTES`（30+ 个中文属性名→API url_name）、`COMPOUND_KEYWORDS`（"双爆"→暴击率+暴伤）
- **查询解析**：`parse_riven_query(message, weapon_resolver)` 从自然语言提取武器名、正/负属性、价格上限
- **API 查询**：`fetch_riven_auctions(weapon_url_name)` 从 warframe.market v1 拍卖 API 获取数据
- **过滤逻辑**：`search_rivens(query)` 按正属性包含、无负/指定负属性、价格上限过滤
- **格式化**：`format_riven_results()` 生成用户可读的搜索结果

关键数据类：`RivenQuery`（查询参数）、`RivenResult`（搜索结果）

#### 紫卡武器名解析（v16.1 加固）

紫卡 API 只接受 415 个**普通版**武器名（无 `sancti_/vaykor_/prisma_/wraith_/vandal_/mutalist_/kuva_/tenet_/dex_/secura_/rakta_/telos_/cobra_` 等变体前缀）。`chat.py` 内置三层守护：

1. `_resolve_weapon_for_riven(name)`：别名 → 字典 → normalize 三级回退
2. `_extract_riven_base_from_set(item_id)`：把 `cernos_prime_set` 这类指向"一套"的别名自动剥离 `_prime/_set` 后缀，提取基础武器名 `cernos`
3. `_normalize_riven_weapon_url(weapon_url)`：把变体武器名（如 `sancti_magistar`）剥离前缀，还原为基础版（`magistar`）

**别名覆盖**：414/415 (99.8%) 紫卡武器有中文别名映射，从 `data/export/ExportWeapons_zh.json` 自动构建。`item_aliases.json` 中针对每种变体前缀都有"中文短名→基础版"的明确覆盖（如"圣洁执法者→magistar"、"勇气海克→hek"），优先级高于 `generated_aliases.json`。

### 3.8 `llm.py` -- LLM 统一接口

路径：`warframe_agent/llm.py`

双模型路由系统：

- **复杂度评估**：`estimate_complexity(message)` 基于长度、分析关键词、投资关键词、多物品检测计算分数
- **路由决策**：`should_use_cloud(message)` 根据 `MODEL_ROUTING` 配置和复杂度阈值决定使用本地/云端
- **同步接口**：`chat_with_model(messages, model)` -- "local"/"cloud"/None(自动)
- **流式接口**：`stream_chat_model(messages, model)` -- 同上，AsyncIterator 版本
- **云端实现**：`_cloud_chat_sync()`（urllib）、`_cloud_chat_stream()`（httpx 异步流式）
- **本地实现**：`chat_with_ollama()`、`stream_chat_ollama()`、`resolve_with_ollama()`
- **容错**：云端失败自动回退本地

### 3.9 `monitor.py` -- 价格监控器

路径：`warframe_agent/monitor.py`

`PriceMonitor` 类在后台守护线程中运行，每 300 秒扫描一次：

- **价格提醒**：检查 `PriceAlert` 是否触发（above/below 阈值）
- **收藏夹快照**：获取收藏物品的当前卖价/买价
- **定时关注**：按小时/天/周频率推送关注物品价格
- **异常检测**：价格历史偏差超过 30% 触发建议
- **价格突变**：3 小时内涨跌 >20% 触发推送
- **目标驱动扫描**：为活跃目标执行计划，发现机会
- **知识库更新**：每 N 次扫描更新 MarketKnowledge
- **自动目标生成**：规则引擎评估市场状态，创建新目标
- **自学习闭环**：从交易结果提炼规律，更新置信度
- **裂缝订阅**：匹配虚空裂缝条件时推送
- **Baro 推荐**：Baro 活跃时自动分析库存
- **事件驱动推送**：Vault 回归、Prime Access 上线
- **每日报告**：定时推送到微信

回调机制：`on_alert`、`on_watch`、`on_goal_opportunity`、`on_proactive_push`、`on_daily_report`、`on_fissure`、`on_baro_recommendation`

### 3.10 `investment.py` -- 投资顾问

路径：`warframe_agent/investment.py`

Prime 套装套利分析：

- `analyze_prime_investment(group, order_fetcher, budget)`：分析单个套装的两种策略
  - 策略 A：散买部件 → 整套卖出
  - 策略 B：整套买入 → 散卖部件
  - 计算 ROI%、风险等级、预算内可买套数
- `scan_prime_investments(items, ...)`：扫描所有 Prime 套装，支持 Scout 预筛选
- `_fetch_prices_parallel()`：并发获取多个物品订单（ThreadPoolExecutor）
- `_assess_risk()`：基于成交量和供需比评估风险

### 3.11 `mod_flipper.py` -- Mod 翻转分析器

路径：`warframe_agent/mod_flipper.py`

- `analyze_mod_flip(item_id, max_rank, rarity)`：分析单个 Mod 的翻转利润（R0 买 → R10 卖）
- `scan_all_mod_flips(items, ...)`：扫描所有可交易 Mod
- 内融消耗表 `ENDO_COST_TABLE`：不同等级/稀有度的升级成本
- 计算指标：利润、ROI%、每千内融白金价值

### 3.12 `set_profit.py` -- 套装利润计算器

路径：`warframe_agent/set_profit.py`

- `analyze_set_profit(group, order_fetcher)`：对比整套买卖 vs 拆件买卖的利润
- `scan_all_set_profits(items, ...)`：扫描所有 Prime 套装

### 3.13 `strategies.py` -- 交易策略模板

路径：`warframe_agent/strategies.py`

预设三种策略：
1. **低风险赋能翻转**：高流动性赋能 Mod（R0 买 R5 卖）
2. **中风险 Prime 拆件**：热门 Prime 套装拆件买卖
3. **高风险 Vault 投机**：即将 Vault 的 Prime 套装囤货

`run_strategy(strategy)` 执行指定策略扫描，`format_strategy_result()` 格式化输出。

### 3.14 `scout.py` -- 多模型智能预筛选

路径：`warframe_agent/scout.py`

用云端 LLM 从大量候选中筛选最值得关注的物品，减少 warframe.market API 调用量：

- `scout_mod_candidates()`：用 kimi-k2.6 模型筛选 Mod 候选
- `scout_set_candidates()`：用 glm-5.1 模型筛选 Prime 套装候选
- `scout_investment_candidates()`：用 gpt-5.5 模型筛选投资候选
- 结果缓存 10 分钟（`SCOUT_CACHE_TTL = 600`）

### 3.15 `knowledge.py` -- 结构化知识库

路径：`warframe_agent/knowledge.py`

`MarketKnowledge` 类随时间积累市场智能：

- `ItemKnowledge`：单个物品的知识（滚动均价、波动率、趋势、成交量趋势、事件上下文）
- `CategoryHealth`：品类健康度（机会数、平均 ROI、趋势）
- `update_from_scan()`：从扫描结果更新知识
- `get_market_summary()`：获取市场概况
- 持久化到 `knowledge_base.json`，TTL 30 天

### 3.16 `memory.py` -- Agent 记忆系统

路径：`warframe_agent/memory.py`

`AgentMemory` 数据类，JSON 持久化：

- `TradingPreferences`：平台、跨平台、最大结果数
- `PriceAlert`：价格提醒（item_id、direction、price）
- `WatchItem`：定时关注（频率、时间、内容类型）
- `FissureAlert`：裂缝订阅（节点、任务类型、等级、钢铁模式）
- `UserProfile`：用户画像（交易偏好、查询历史、品类偏好）
- `ProactiveSuggestion`：主动建议（异常、趋势、机会）
- `AgentGoal`：Agent 目标
- `TradeOutcome`：交易结果
- 不可变数据结构，所有修改返回新实例（`with_xxx()` 方法）

### 3.17 `goals.py` -- 目标引擎

路径：`warframe_agent/goals.py`

Agent 自主目标管理系统：

- `create_goal()`：创建目标（maximize_profit / find_bargain / build_set / flip_mod）
- `plan_for_goal()`：根据目标类型生成执行计划（步骤列表）
- `execute_plan()`：执行计划步骤
- `record_trade_outcome()`：记录交易结果用于反馈学习
- `TradeOutcome`：交易结果数据类（action、price、expected_profit、actual_profit、user_feedback）

### 3.18 `rules.py` -- 规则引擎

路径：`warframe_agent/rules.py`

替代监控器中所有 LLM 决策的纯规则系统：

- `evaluate_market_state()`：纯计算评估市场状态（波动率、趋势、活跃度）
- `generate_auto_goals()`：从市场状态自动生成目标
- `generate_proactive_message()`：模板化生成推送消息（无需 LLM）
- `AdaptiveThresholds`：根据知识库动态计算阈值（替代硬编码常量）
- `MarketState`：市场状态数据类

### 3.19 `events.py` -- 游戏事件追踪

路径：`warframe_agent/events.py`

`EventTracker` 类从 Warframe 官方 World State API 获取活动信息：

- **Baro 虚空商人**：来访时间、库存物品列表（含杜卡特/现金成本）、market_id 映射
- **虚空裂缝**：节点、任务类型、等级（古纪/前纪/中纪/后纪/遗珍）、钢铁模式
- **虚空风暴**、**警报**、**入侵**、**Prime Vault 回归**、**Prime Access**
- 缓存机制：30 分钟 TTL，持久化到 `game_events_cache.json`
- 兼容官方 API 和 warframestat.us 两种数据格式

### 3.20 `baro.py` -- Baro 库存分析

路径：`warframe_agent/baro.py`

- `analyze_baro_inventory()`：分析 Baro 库存，对比杜卡特成本和市场白金价格
- 杜卡特→白金隐含汇率阈值：市场价 > 杜卡特/3 则建议从 Baro 购买
- `BaroRecommendation`：推荐结果（buy/skip/consider + 原因）

### 3.21 `tool_router.py` -- 工具路由器

路径：`warframe_agent/tool_router.py`

基于 LLM function calling 的意图路由系统：

- **工具定义**（`TOOL_SCHEMAS`）：query_price、query_set、query_missing_parts、scan_favorites、set_alert、price_trend、mod_flipper、set_profit、investment_advisor、plan 等
- `build_router_prompt()`：构建包含工具描述的路由器 prompt
- `parse_tool_call()`：解析 LLM 输出的工具调用（支持 JSON 和正则提取）
- `execute_tool_call()`：执行工具调用并返回结果

### 3.22 `feishu.py` -- 飞书机器人

路径：`warframe_agent/feishu.py`

- `FeishuBot` 类：WebSocket 长连接模式，无需公网 IP
- 启动独立子进程运行飞书 WebSocket 客户端
- 消息去重：持久化到磁盘（`feishu_processed_ids.json`），10 分钟 TTL
- 拒绝启动前创建的旧消息
- 子进程通过 HTTP POST 调用 Web API（`http://127.0.0.1:8000/api/chat`）
- 支持文本消息和交互式卡片消息（`send_card`、`reply_card`）
- `_kill_old_workers()`：清理旧的飞书 worker 进程防止重复响应

### 3.23 `push.py` -- 微信推送

路径：`warframe_agent/push.py`

- `WxPusher` 类：通过 WxPusher API 推送到微信
- `PushConfig`：推送配置（app_token、uids、各类推送开关、报告时间）
- `should_send_daily_report()`：检查是否到每日报告时间（±6 分钟容差）
- `format_buyers_with_whisper()` / `format_sellers_with_whisper()`：格式化买家/卖家列表附带私聊命令

### 3.24 `price_history.py` -- 价格历史数据库

路径：`warframe_agent/price_history.py`

`PriceHistoryDB` 类，SQLite 存储：

- `record(item_id, sell_price, buy_price)`：记录价格快照
- `recent(item_id, limit)`：获取最近 N 条记录
- `recent_since(item_id, hours)`：获取最近 N 小时的记录
- `detect_anomaly(item_id, threshold)`：检测价格异常（偏离均值百分比）
- TTL 30 天自动清理

### 3.25 `warframes.py` -- Prime 套装解析

路径：`warframe_agent/warframes.py`

- `PARTS` 字典：30+ 种部件类型（blueprint、chassis、neuroptics、barrel、receiver 等），每种含后缀、中文标签、搜索关键词
- `PrimeGroup` 数据类：base_id、items（部件→item_id 映射）、tags、中英文标题
- `build_prime_groups(items)`：从 items_full.json 构建 Prime 套装分组
- `parse_warframe_query(message)`：从自然语言解析战甲/武器查询
- `price_warframe_query()`：处理 Prime 套装价格查询（含套装总价、部件散买、缺件计算）
- `COMMON_WARFRAME_ALIASES`：常见战甲中文别名（"电男"→volt、"毒妈"→saryn 等）

### 3.26 其他模块

- **`trade_intent.py`**：交易意图检测（buy/sell/spread/overview）、趋势查询检测、对比查询检测、已完成交易检测
- **`conversation_log.py`**：对话日志记录（JSONL 格式），支持评分
- **`formatter.py`**：输出格式化（私聊命令 `/w username`、订单表格）
- **`rag.py`**：RAG 物品检索，先语义搜索（`SemanticRAG`，基于 numpy + Ollama embedding），无结果回退 n-gram
- **`relics.py`**：遗物掉落数据库，从游戏导出数据构建遗物↔部件索引
- **`scraper.py`**：Playwright 浏览器抓取（绕过 Cloudflare 的备选方案）
- **`game_data.py`**：`GameDataStore` 懒加载游戏数据（Mod 效果、战甲技能、杜卡特值、Vault 状态）
- **`feedback.py`**：`FeedbackAnalyzer` 从交易结果分析策略胜率、自学习闭环
- **`patterns.py`**：模式学习，从交易历史提取时间/物品/策略规律
- **`names.py`**：物品显示名（中文优先，格式：`中文名 / English / item_id`）
- **`report.py`**：日报生成

### 3.27 `web/app.py` -- FastAPI Web 应用

路径：`warframe_agent/web/app.py`

REST API + WebSocket 服务：

**API 端点**：
- `POST /api/chat`：对话接口（同步调用 `chat_agent.answer`）
- `GET /api/memory`：获取 Agent 记忆
- `POST /api/favorites`：添加/删除收藏
- `POST /api/alerts`：添加/删除价格提醒
- `POST /api/preferences`：更新偏好设置
- `POST /api/watchlist`：管理定时关注
- `GET /api/price/{item_id}`：查询物品价格
- `POST /api/riven/search`：紫卡搜索
- `POST /api/mod-flip`：Mod 翻转扫描
- `POST /api/set-profit`：套装利润扫描
- `POST /api/investment`：投资顾问扫描
- `POST /api/goals`：目标管理
- `POST /api/trade-history`：交易历史
- `POST /api/feedback`：提交交易反馈
- `POST /api/fissure-alerts`：裂缝订阅管理
- `POST /api/events`：游戏事件查询
- `POST /api/relics`：遗物查询
- `POST /api/baro`：Baro 分析
- `POST /api/strategies`：策略扫描
- `POST /api/scan`：机会扫描
- `POST /api/ducat`：杜卡特效率计算
- `POST /api/scout`：预筛选
- `POST /api/custom-aliases`：自定义别名管理
- `POST /api/push/config`：推送配置
- `POST /api/push/test`：测试推送
- `POST /api/feishu/config`：飞书配置
- `POST /api/feishu/card`：飞书卡片消息
- `GET /api/ws`：WebSocket 端点（流式对话）

**生命周期**：
- 启动时：注入自定义别名、启动监控线程、启动飞书 WebSocket、预热缓存（并发加载 Export 文件、wiki 数据、遗物数据）
- 关闭时：停止飞书 bot、停止监控器

**中间件**：`NoCacheAPIMiddleware` 为所有 `/api/` 路径添加禁缓存头

### 3.28 前端

路径：`warframe_agent/web/static/`

- `index.html`：主页面，Tenno 科技终端风格 UI
- `js/chat.js`：对话模块，WebSocket 通信、流式渲染、Markdown 渲染（marked.js + DOMPurify）、对话历史持久化（localStorage）
- `js/sidebar.js`：侧边栏（收藏、提醒、关注、设置）
- `js/app.js`：应用主逻辑
- `js/chart.js`：价格趋势图表
- `css/style.css`：主样式
- `css/variables.css`：CSS 变量（主题色）
- `css/animations.css`：动画效果
- `css/responsive.css`：响应式布局

---

## 四、数据流：用户消息处理全流程

以下是一条用户消息从输入到响应的完整处理流程：

### 4.1 WebSocket 路径（Web 界面）

```
用户输入 → 浏览器 JS → WebSocket → app.py /api/ws
  → chat_agent.answer_stream(message)
  → 逐 token 流式返回 → 浏览器实时渲染
```

### 4.2 ChatAgent.answer() 内部流程

```
1. _reload_memory()                          # 重新加载记忆文件
2. 命令检测（/开头）                           # → _handle_agent_command()
3. 关注列表扫描检测                            # → scan_watchlist()
4. 紫卡查询检测                               # → _try_deterministic_riven()
   └─ parse_riven_query() → search_rivens()  # 确定性解析+API查询
5. 紫卡追问检测                               # → _try_riven_followup()
6. 事件/工具查询检测                           # → _try_router()
7. Warframe 套装查询                          # → price_warframe_query()
8. 追问检测 + 上下文复用                       # → _contexts_for_items()
9. 物品名解析                                 # → resolver.resolve() (多层策略)
10. 订单获取                                  # → fetch_orders() (API + 缓存)
11. 交易意图检测                              # → detect_trade_intent()
12. 确定性回答（买/卖/价差/趋势）              # → _deterministic_trade_intent_answer()
13. LLM 回答                                  # → build_chat_messages() → _call_llm_messages()
    ├─ 自动路由：简单→本地Ollama，复杂→云端API
    └─ _self_check() 自检纠正
14. 兜底回答                                  # → fallback_answer()
15. 记录对话                                  # → _log_answer() → conversation_logs.jsonl
16. 更新会话上下文                            # → session.add_exchange()
```

### 4.3 LLM 路由决策

```
用户消息 → estimate_complexity(message)
  ├─ 长度 > 50 字符: +1
  ├─ 分析关键词（对比/推荐/投资）: +2
  ├─ 投资关键词（预算/ROI/利润）: +2
  └─ 多物品检测: +N

分数 >= COMPLEXITY_THRESHOLD(3) → 云端 API
分数 < 3 → 本地 Ollama
云端失败 → 自动回退本地
```

---

## 五、配置与环境变量

### 5.1 `.env` 文件

```
CLOUD_API_BASE=https://gpt-agent.cc/v1
CLOUD_API_KEY=sk-xxx
CLOUD_MODEL=gpt-5.5
MODEL_ROUTING=auto
```

### 5.2 可选环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CLOUD_API_BASE` | `https://gpt-agent.cc/v1` | 云端 API 地址 |
| `CLOUD_API_KEY` | 空 | 云端 API 密钥 |
| `CLOUD_MODEL` | `gpt-5.5` | 云端模型名 |
| `MODEL_ROUTING` | `auto` | 路由策略：auto/local/cloud |
| `SCOUT_MOD_MODEL` | `kimi-k2.6` | Mod 预筛选云端模型 |
| `SCOUT_SET_MODEL` | `glm-5.1` | 套装预筛选云端模型 |
| `SCOUT_INV_MODEL` | `gpt-5.5` | 投资预筛选云端模型 |

### 5.3 JSON 配置文件

- `data/feishu_config.json`：飞书 app_id、app_secret
- `data/push_config.json`：WxPusher app_token、uids、推送开关
- `data/custom_aliases.json`：用户自定义别名
- `data/watchlist.json`：关注列表（按类别分组的 item_id 列表）

---

## 六、数据文件详解

### 6.1 核心数据文件

| 文件 | 大小 | 格式 | 说明 |
|------|------|------|------|
| `items_full.json` | ~1.3MB | JSON 数组 | 完整物品数据（item_id、en_name、zh_name、tags、tradable） |
| `item_aliases.json` | ~40KB | JSON 对象 | 手动别名映射（中文名→market_id） |
| `generated_aliases.json` | ~739KB | JSON 对象 | 自动生成的别名 |
| `rag_items.jsonl` | ~1.4MB | JSONL | RAG 检索语料（每行：{id, text}） |
| `agent_memory.json` | ~9KB | JSON 对象 | Agent 持久化记忆 |
| `conversation_logs.jsonl` | ~1.2MB | JSONL | 对话日志 |
| `watchlist.json` | ~506B | JSON 对象 | 关注列表 |
| `goals.json` | ~1KB | JSON 对象 | Agent 目标 |

### 6.2 SQLite 数据库

| 文件 | 说明 | 主要表 |
|------|------|--------|
| `price_cache.db` | 市场价格缓存 | `market_cache`（item_id, cache_type, data_json, updated_at） |
| `price_history.db` | 价格历史 | `price_snapshots`（item_id, sell_price, buy_price, timestamp） |
| `trade_history.db` | 交易历史 | `trade_history`（item_id, item_name, trade_type, price, player_name, timestamp） |

### 6.3 游戏导出数据 (`data/export/`)

多语言 JSON 文件，来自 Warframe 游戏数据导出：

- `ExportRelicArcane_{lang}.json`：赋能和遗物数据
- `ExportUpgrades_{lang}.json`：Mod 数据
- `ExportWarframes_{lang}.json`：战甲数据
- `ExportWeapons_{lang}.json`：武器数据
- `ExportRecipes.json`：制造配方
- `ExportManifest.json`：资源清单

使用的文件对（中英文）在 `config.EXPORT_FILE_PAIRS` 中定义。

### 6.4 其他数据文件

- `game_events_cache.json`：游戏事件缓存（Baro、Vault、裂缝等）
- `relic_sources.json`：遗物来源数据
- `relic_vault_status.json`：遗物 Vault 状态
- `relics_drop_data.json`：遗物掉落数据
- `ducat_values.json`：杜卡特价值映射
- `feature_list.json`：功能列表
- `worldstate_raw.json`：世界状态原始数据缓存

---

## 七、测试

### 7.1 测试结构

路径：`tests/`

55+ 个测试文件，使用 pytest 框架，覆盖：

- **核心功能**：test_chat.py、test_chat_alias_priority.py、test_chat_memory_commands.py、test_chat_memory_integration.py
- **物品解析**：test_names.py、test_dictionary.py、test_generated_alias_resolver.py、test_alias_conflicts.py
- **市场数据**：test_market_client.py、test_market_formatter.py、test_price_history.py
- **紫卡搜索**：test_riven.py（~13KB，最全面的测试之一）
- **交易策略**：test_investment.py、test_mod_flipper.py、test_set_profit.py
- **监控系统**：test_monitor.py、test_enriched_monitor.py、test_proactive_push.py
- **目标系统**：test_goals.py、test_goal_generation.py、test_goal_decompose.py、test_dynamic_plan.py
- **事件系统**：test_events.py
- **知识库**：test_knowledge.py
- **规则引擎**：test_rules.py
- **反馈系统**：test_feedback.py
- **Prime 套装**：test_warframe_sets.py、test_warframe_chat_integration.py、test_prime_set_generalization.py
- **路由器**：test_router.py、test_tool_router.py
- **会话上下文**：test_session_context.py、test_multiturn.py
- **RAG**：test_rag.py、test_chat_rag_fallback.py
- **Web API**：test_web_api.py（~12KB）、test_web_ui_playwright.py
- **端到端**：test_phase35_e2e.py（~10KB）
- **其他**：test_relics.py、test_push.py、test_feishu.py、test_trade_intent.py、test_trade_history.py

### 7.2 测试方法

- 大量使用 mock（`unittest.mock.patch`）隔离外部依赖（API 调用、LLM 调用、文件 I/O）
- 回归测试：test_short_name_regression.py、test_prime_group_title_regression.py
- 集成测试：test_web_api.py 使用 FastAPI TestClient
- UI 测试：test_web_ui_playwright.py 使用 Playwright

---

## 八、关键设计模式与决策

### 8.1 依赖注入

`ChatAgent` 的构造函数接受多个可选依赖（`resolver`、`order_fetcher`、`model_call`、`memory`、`rag_search` 等），默认值为真实实现，测试时可注入 mock。这是整个项目最核心的设计模式。

### 8.2 不可变数据结构

大量使用 `@dataclass(frozen=True)` 定义不可变数据类（`MarketOrder`、`RivenQuery`、`ItemContext`、`AgentMemory` 等）。修改操作返回新实例（`with_xxx()` 方法），避免状态混乱。

### 8.3 多层缓存策略

- **内存缓存**：LRU `OrderedDict`（订单、统计数据）
- **SQLite 持久化缓存**：`price_cache.db`（启动时预热到内存）
- **文件缓存**：`item_dictionary_cache.json`、`game_events_cache.json`
- **TTL 机制**：每种缓存有独立的 TTL（60s~600s）

### 8.4 确定性优先、LLM 兜底

系统设计遵循"确定性优先"原则：
1. 命令（`/` 开头）→ 确定性处理
2. 紫卡查询 → 确定性解析 + API 查询
3. 交易意图 → 关键词匹配 + 确定性回答
4. Warframe 套装 → 结构化解析 + 确定性回答
5. 追问 → 上下文复用 + 确定性回答
6. 复杂查询 → LLM 回答
7. LLM 失败 → 兜底回答

### 8.5 多模型协作

- **本地 Ollama**（warframe-agent / qwen3:8b）：处理简单查询、路由器意图分类
- **云端 API**（gpt-5.5 / kimi-k2.6 / glm-5.1）：处理复杂分析、预筛选
- **自动路由**：基于复杂度分数自动切换，云端失败回退本地
- **Scout 模式**：用云端 LLM 从大量候选中预筛选，减少 API 调用

### 8.6 规则引擎替代 LLM 决策

`rules.py` 实现纯规则驱动的市场评估和推送生成，避免在监控循环中调用 LLM（节省成本和延迟）：
- `evaluate_market_state()`：纯计算评估
- `generate_proactive_message()`：模板化消息
- `AdaptiveThresholds`：动态阈值

### 8.7 自学习闭环

```
交易结果 → FeedbackAnalyzer → 策略胜率/置信度
         → run_self_learning_cycle() → 新规律发现
         → 更新 AgentMemory.learned_patterns
         → 注入 LLM 上下文影响后续决策
```

### 8.8 进程隔离

飞书 WebSocket 客户端运行在独立子进程中，通过 HTTP 与主进程通信。这样飞书 SDK 的阻塞操作不会影响主服务。启动时自动清理旧的 worker 进程防止重复响应。

### 8.9 速率控制

warframe.market API 有严格的速率限制。系统通过以下方式应对：
- 线程安全的速率限制器（~3 req/s + 随机抖动）
- 429 响应时指数退避（最多 30 秒）
- 多层缓存减少请求量
- Scout 预筛选减少扫描范围

### 8.10 对话上下文管理

`SessionContext` 维护多轮对话状态：
- 追问检测（30+ 个追问关键词）
- 上下文复用（追问时复用上次查询的物品和订单数据）
- 相关性排序（历史对话按关键词重叠 + 时间衰减排序，优先保留相关轮次）

---

## 九、启动方式

### 9.1 CLI 模式

```bash
python main.py
```

菜单选项：1-查询物品、2-每日报告、3-重建字典、4-对话助手、5-Web界面、q-退出

### 9.2 Web 模式

```bash
python start_web.py
# 或
uvicorn warframe_agent.web.app:app --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000`

### 9.3 依赖安装

```bash
pip install -r requirements.txt
```

主要依赖：ollama、requests、httpx、fastapi、pydantic、uvicorn、websockets、aiosqlite、numpy、playwright

---

## 十、关键文件路径速查

| 用途 | 路径 |
|------|------|
| CLI 入口 | `main.py` |
| Web 启动 | `start_web.py` |
| 全局配置 | `warframe_agent/config.py` |
| 对话核心 | `warframe_agent/chat.py` |
| LLM 路由 | `warframe_agent/llm.py` |
| 市场 API | `warframe_agent/market.py` |
| 紫卡搜索 | `warframe_agent/riven.py` |
| 价格监控 | `warframe_agent/monitor.py` |
| 投资分析 | `warframe_agent/investment.py` |
| Mod 翻转 | `warframe_agent/mod_flipper.py` |
| 套装利润 | `warframe_agent/set_profit.py` |
| 飞书机器人 | `warframe_agent/feishu.py` |
| 游戏事件 | `warframe_agent/events.py` |
| 知识库 | `warframe_agent/knowledge.py` |
| Agent 记忆 | `warframe_agent/memory.py` |
| 目标引擎 | `warframe_agent/goals.py` |
| 规则引擎 | `warframe_agent/rules.py` |
| 工具路由 | `warframe_agent/tool_router.py` |
| 物品解析 | `warframe_agent/dictionary.py` |
| Web 应用 | `warframe_agent/web/app.py` |
| 前端主页 | `warframe_agent/web/static/index.html` |
| 环境变量 | `.env` |
| 测试目录 | `tests/` |
| 数据目录 | `data/` |
