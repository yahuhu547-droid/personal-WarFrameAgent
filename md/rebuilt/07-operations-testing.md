# 07. 运行、测试与维护

本文整理本项目的运行入口、配置范围、测试覆盖和维护注意事项。

## 1. 环境和依赖

依赖文件：`requirements.txt`。

测试配置文件：`pytest.ini`。如果本地虚拟环境缺少 pytest，优先按 `requirements.txt` 安装依赖，再运行测试命令。

项目是 Python/FastAPI 应用，核心依赖范围包括：

- FastAPI / Uvicorn：Web API 和静态 Web UI。
- httpx / requests 类 HTTP 客户端：访问 warframe.market、World State、推送平台等。
- SQLite：价格历史、交易历史、交易记忆、缓存。
- pytest：单元和集成测试。
- Playwright：Web UI 测试。
- Ollama：本地模型和 embedding。

## 2. 运行入口

### Web 服务

FastAPI 应用定义在：

- `warframe_agent/web/app.py`

常见运行方式是用 Uvicorn 加载：

```bash
python -m uvicorn warframe_agent.web.app:app --host 127.0.0.1 --port 8000
```

Web UI 由同一个服务提供静态资源。

### 聊天 Agent

主要类：

- `warframe_agent/chat.py` 中的 `ChatAgent`

它可被 Web API、飞书 worker 或其他 Python 入口复用。

### 后台监控

主要类：

- `warframe_agent/monitor.py` 中的 `PriceMonitor`
- `warframe_agent/scheduler.py` 中的 `SchedulerRunner`

Web 应用 lifespan 会启动和停止监控器及飞书机器人。

## 3. 配置文件和数据文件

| 文件 | 用途 |
|---|---|
| `warframe_agent/config.py` | 模型、API、工具上下文、ReAct、Scout 等全局配置。 |
| `data/agent_memory.json` | Agent 长期记忆。 |
| `data/push_config.json` | WxPusher 配置。 |
| `data/feishu_config.json` | 飞书配置。 |
| `data/custom_aliases.json` | 自定义物品别名。 |
| `data/price_history.db` | 价格历史。 |
| `data/trade_history.db` | 交易历史。 |
| `data/price_cache.db` | 市场价格缓存。 |
| `data/conversation_logs.jsonl` | 对话日志。 |
| `data/bilibili_recommendations.json` | 本地 curated B 站攻略视频推荐数据，包含具体武器、主武器/副武器/近战分类、别名和待确认标记。 |

配置注意事项：

- 不要把真实 API Key 写入文档。
- 推送和飞书配置属于会影响外部系统的状态，修改前应确认目标环境。
- 本地开发时优先使用本机服务地址和测试 token。

## 4. 测试覆盖

### 聊天和会话

- `tests/test_chat.py`
- `tests/test_chat_alias_priority.py`
- `tests/test_chat_memory_integration.py`
- `tests/test_chat_memory_commands.py`
- `tests/test_chat_rag_fallback.py`
- `tests/test_multiturn.py`
- `tests/test_session_context.py`

### 工具系统和路由

- `tests/test_tool_registry.py`
- `tests/test_tool_router.py`
- `tests/test_tool_context.py`
- `tests/test_bilibili_recommendations.py`
- `tests/test_router.py`
- `tests/test_plan.py`
- `tests/test_dynamic_plan.py`

### 市场和名称解析

- `tests/test_market_client.py`
- `tests/test_market_formatter.py`
- `tests/test_dictionary.py`
- `tests/test_names.py`
- `tests/test_generated_alias_resolver.py`
- `tests/test_alias_conflicts.py`
- `tests/test_short_name_regression.py`
- `tests/test_full_item_names.py`
- `tests/test_item_data_builder.py`

### Prime、遗物、缺件

- `tests/test_warframe_sets.py`
- `tests/test_warframe_chat_integration.py`
- `tests/test_prime_set_chat_integration.py`
- `tests/test_prime_set_generalization.py`
- `tests/test_prime_group_title_regression.py`
- `tests/test_missing_parts.py`
- `tests/test_relics.py`
- `tests/test_relic_value.py`
- `tests/test_farming_route.py`

### Riven、Baro、活动

- `tests/test_riven.py`（覆盖紫卡解析、格式化、属性评分、价格位置、置信度和安全模型上下文）
- `tests/test_riven_weapon_normalize.py`
- `tests/test_baro.py`
- `tests/test_events.py`
- `tests/test_game_data.py`

### 投资、倒卖、监控、推送

- `tests/test_investment.py`
- `tests/test_mod_flipper.py`
- `tests/test_set_profit.py`
- `tests/test_monitor.py`
- `tests/test_enriched_monitor.py`
- `tests/test_scheduler.py`
- `tests/test_proactive_push.py`
- `tests/test_push.py`

### Web 和飞书

- `tests/test_web_api.py`
- `tests/test_web_ui_playwright.py`
- `tests/test_feishu.py`

### 记忆、知识、目标、自学习

- `tests/test_memory.py`
- `tests/test_memory_recall.py`
- `tests/test_trading_memory.py`
- `tests/test_trade_history.py`
- `tests/test_price_history.py`
- `tests/test_knowledge.py`
- `tests/test_patterns.py`
- `tests/test_rules.py`
- `tests/test_feedback.py`
- `tests/test_goals.py`
- `tests/test_goal_generation.py`
- `tests/test_goal_decompose.py`

### 端到端

- `tests/test_phase35_e2e.py`

## 5. 推荐测试命令

运行全部测试：

```bash
python -m pytest
```

运行某一类测试：

```bash
python -m pytest tests/test_web_api.py
python -m pytest tests/test_tool_context.py
python -m pytest tests/test_riven.py tests/test_baro.py
```

B 站攻略视频推荐变更建议先运行：

```bash
python -m pytest tests/test_bilibili_recommendations.py tests/test_chat.py -q
```

该集合覆盖本地推荐数据加载、`needs_review` 跳过、主武器/副武器/近战分类推荐、具体武器配卡问题命中对应视频，以及价格类问题不出现视频推荐。

紫卡解析、评分、价格位置、置信度和安全模型上下文变更建议运行：

```bash
python -m pytest tests/test_riven.py tests/test_tool_router.py -q
```

中文活动别名、数据源暂不支持边界、开放世界周期别名和路由候选变更建议运行：

```bash
python -m pytest tests/test_events.py tests/test_chat.py tests/test_tool_router.py -q
```

Prime 部件/遗物刷取路线推荐、路线评分、工具路由和 Web API 变更建议运行：

```bash
python -m pytest tests/test_farming_route.py tests/test_relic_value.py tests/test_tool_router.py tests/test_web_api.py::TestWebAPI::test_farming_route_api_returns_ranked_routes tests/test_chat.py::ChatTests::test_farming_route_tool_returns_route_and_safe_context -q
```

该集合覆盖按部件反查遗物、按遗物列出奖励路线、同纪元裂缝匹配、遗物来源、入库风险、期望白金/杜卡德、安全模型上下文和 `/api/farming-route` 响应。

该集合覆盖虚空裂缝/裂隙/开核桃、虚空商人/奸商、入侵、虚空风暴、Prime 重生/返厂、平原/希图斯/金星/火卫二周期，以及午夜电波、仲裁、突击、Darvo、扎里曼和赏金等数据源缺字段时的明确“不编造”提示。

飞书、Web API、调度和聊天意图相关变更建议先运行目标集合：

```bash
python -m pytest tests/test_chat.py tests/test_feishu.py tests/test_monitor.py tests/test_web_api.py -q
```

套装套利评分、Web API 和前端面板变更可先验证：

```bash
python -m pytest tests/test_set_profit.py tests/test_web_api.py::TestWebAPI::test_set_profit_api_returns_actionable_trade_plan tests/test_web_ui_playwright.py::test_trade_opportunity_panels_render_actionable_trade_plans -q
node --check warframe_agent/web/static/js/sidebar.js
```

交易机会推送、去重、原因说明、检测范围过滤、Mod/赋能/Prime 可执行交易计划相关变更建议运行：

```bash
python -m pytest tests/test_proactive_push.py tests/test_enriched_monitor.py tests/test_rules.py tests/test_monitor.py tests/test_trading_memory.py tests/test_memory_recall.py -q
python -m pytest tests/test_market_formatter.py tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py tests/test_chat.py tests/test_web_api.py -q
python -m pytest tests/test_push.py tests/test_feishu.py tests/test_web_ui_playwright.py -q
```

其中 `test_market_formatter` 覆盖批量买入聚合和 safe summary；`test_mod_flipper` 覆盖赋能 R0 quantity 聚合；`test_set_profit` 覆盖 Prime 只展示选中策略路径、ROI、流动性、风险等级、机会分数和模型上下文安全；`test_chat`/`test_web_api` 覆盖展示层含玩家链接而模型上下文保持安全；`test_proactive_push` 覆盖 push history 只保存安全摘要和按 profit bucket/quantity/signature 去重；`test_push`/`test_feishu`/Playwright 覆盖 WxPusher、飞书和 WebSocket 的可执行交易计划展示。

手工 smoke 可通过聊天发送 `暂停交易机会`、`开启交易机会`、`交易机会只检测MOD`、`交易机会只检测赋能`、`交易机会检测全部`，再检查 `/api/push/config` 和 `data/agent_memory.json` 中对应状态是否更新。

### 交易机会 ID 验证

当 WxPusher 收到带 `机会ID：OPxxxxxx` 的交易机会后，可在飞书或聊天框直接输入该 ID，也可输入 `/opp OPxxxxxx` 或 `/机会 OPxxxxxx`。预期回复包含买入/卖出步骤、warframe.market 链接、玩家主页、游戏内私聊命令、机会标题后的游戏内中文名和 48 小时有效期提示。赋能机会应重点检查数量阶梯，例如 7p 库存 5 个、9p 库存 22 个、需求 21 个时，回复应显示 `7p × 5` 和 `9p × 16`，总成本 179p。普通 MOD 不应显示“需要 R0 × 21”。Prime 武器 Set 应和战甲 Set 一样说明游戏内需交付完整部件组合。过期或不存在的 ID 应返回明确过期提示，不应落入普通物品搜索。

Web UI 相关变更应额外运行 Playwright 测试，并实际打开本地页面验证主要路径。交易机会卡片变更应确认 `trade_plan` 步骤、quantity、market/profile 链接和复制 whisper 都可见且 XSS payload 不执行。Playwright Python 包不等于浏览器已安装；如果缺少 Chromium，需要单独执行 `python -m playwright install chromium`。

运行态状态变更可先验证：

```bash
python -m pytest tests/test_feishu.py tests/test_monitor.py tests/test_web_api.py -q
```

服务启动后访问 `/api/runtime/status`，确认返回 `web`、`feishu`、`wxpusher`、`scheduler`、`daily_report`、`background_tasks` 和 `recent_tool_calls` 字段；前端侧栏状态点应能显示在线、检查中、部分异常或连接错误，点击状态点应打开只读运行态详情。

交易记忆召回相关变更可先验证：

```bash
python -m pytest tests/test_memory_recall.py tests/test_trading_memory.py tests/test_chat.py::ChatTests::test_chat_uses_memory_recall_safe_summary_only tests/test_web_api.py::TestWebAPI::test_memory_recall_api_returns_safe_trace -q
```

Web UI 运行态、工具观测和记忆 trace 相关变更可先验证：

```bash
python -m pytest tests/test_web_api.py tests/test_web_ui_playwright.py -q
```

工具调用观测面板变更可先单测验证：

```bash
python -m pytest tests/test_web_ui_playwright.py::test_tool_observability_panel_renders_history_stats_and_filters_safely -q
```

## 6. 维护建议

### 修改聊天或路由

- 先确认是否已有确定性规则覆盖。
- 新增工具时同步更新 `ToolRegistry`、路由 prompt、工具上下文压缩策略和测试。
- 不要让 LLM 编造实时价格、玩家信息或活动状态。

### 修改市场和活动数据

- 关注 API 响应变化。
- 给外部数据加缓存和失败回退。
- 进入模型前必须清洗。

### 修改 Web API

- 保持 Pydantic 请求模型明确。
- 修改会触发外部动作的接口时，补充测试。
- 前端变更要用浏览器验证。

### 修改推送和飞书

- 注意副作用：可能向真实用户发送消息。
- 测试环境应使用测试 token 或禁用真实推送。
- worker 启停、去重、旧消息过滤要保留。

### 修改记忆和历史库

- 避免保存完整敏感输入。
- 保持只读查询能力。
- 注意 SQLite schema 兼容和迁移。

## 7. 常见排障方向

| 现象 | 排查方向 |
|---|---|
| 价格查不到 | 名称解析、别名、warframe.market API、缓存过期。 |
| 紫卡结果为空 | 武器名 normalize、属性映射、价格上限、拍卖 API。 |
| Baro 推荐异常 | World State 缓存、Baro 库存解析、rank 参数。 |
| Web 页面无数据 | `/api/chat` 或对应 API 响应、浏览器控制台、静态 JS。 |
| 飞书不回复 | `feishu_config.json`、worker 日志、chat_id、`/api/chat` 是否可用。Windows venv 下可能看到带同一 worker marker 的父子两个物理进程；逻辑 worker 应按“父进程不含同 marker”的进程计数为 1。 |
| 推送失败 | `push_config.json`、UID/topic、网络、平台返回码。 |
| 状态不确定 | 优先查看 `/api/runtime/status`；其中包含 Web uptime、飞书 worker、scheduler 和日报摘要。调度细节仍可查看 `/api/scheduler/status`。 |
| 模型回答跑偏 | 工具上下文是否清洗、确定性规则是否命中、router prompt。 |
