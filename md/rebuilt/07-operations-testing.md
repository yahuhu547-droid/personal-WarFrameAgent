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
| `data/bilibili_recommendations.json` | 基础配卡攻略查询的本地 B 站视频兜底库，包含具体武器、主武器/副武器/近战分类、具体战甲、宠物/同伴/守护/猎犬/恐鸟分类、别名、优先级和待确认标记。视频链接元数据可先入库。 |
| `data/video_parse_drafts.jsonl` | B 站视频离线解析草稿，包含帧、区域、OCR 和图标候选；MOD、赋能、灵化选择默认不可信，必须经用户过目确认后才能写入可信数据。 |
| `Extra Resource/exports/bilibili_metadata/fallback_inventory_report.json` | B 站候选元数据覆盖报告，记录当前候选、已入库和需复核数量。 |
| `Extra Resource/exports/bilibili_metadata/bilibili_recommendation_candidates.json` | 推荐记录候选草稿；只有明确分类和武器名的视频链接元数据才可并入正式库。 |
| `Extra Resource/exports/bilibili_metadata/bilibili_recommendation_review_summary.json` | 待复核候选摘要，按主武器/副武器/近战/未分类分组，便于人工确认标题前缀、分类和是否可入库。 |
| `Extra Resource/exports/bilibili_metadata/companion_build_links_final.json` | 已筛选的 companion 视频链接最终清单；用于导入宠物/同伴/守护/猎犬/恐鸟推荐记录。 |
| `Extra Resource/exports/bilibili_metadata/companion_build_import_report.json` | companion 视频导入报告，记录自动入库、待复核和追加 BVID。 |
| `Extra Resource/exports/bilibili_metadata/warframe_search_results.json` | 战甲视频搜索/合集元数据；当前首批由本地 B 站“战甲合集”导出生成。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_links_curated.json` | 已筛选的 warframe 视频链接清单；用于人工确认首批战甲覆盖。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_links_final.json` | 战甲视频链接最终清单；用于导入 `category: warframe` 推荐记录。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_import_report.json` | warframe 视频导入报告，记录自动入库、待复核和追加 BVID。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_candidates.json` | 战甲导入生成的推荐记录候选。 |
| `Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_review_summary.json` | 战甲导入复核摘要；首批正式导入要求 `needs_review_new_count == 0`。 |

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

个人 Agent 画像、机会复盘和个人化评分相关变更建议运行：

```bash
python -m pytest tests/test_personal_profile.py tests/test_personal_scoring.py tests/test_trading_memory.py tests/test_chat_memory_commands.py tests/test_web_api.py -q
python -m pytest tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py tests/test_monitor.py -q
```

机会复盘反馈进入个人评分时，可先跑更窄的红绿集合：

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py -k "outcome_feedback" -q
.\.venv\Scripts\python.exe -m pytest tests/test_personal_scoring.py -k "outcome_feedback or sparse" -q
.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py tests/test_personal_scoring.py -q
```

该集合覆盖 `AgentMemory.trade_outcomes` 到聚合 `outcome_feedback` 的安全画像、同策略好结果加分、同策略差结果扣分，以及样本数不足 3 条时不调权。当前普通 `python` 指向 `F:\anaPhy\python.exe` 和 pytest 3.8，收集本项目测试时可能卡住；建议使用工作区 `.venv\Scripts\python.exe`。

SQLite 机会复盘显式注入个人画像时，可额外运行：

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py -k "sqlite_opportunity_outcomes" -q
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "sqlite_outcomes" -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/personal_profile.py','warframe_agent/chat.py','warframe_agent/web/app.py','tests/test_personal_profile.py','tests/test_chat_memory_commands.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

该集合确认 `OpportunityOutcomeMemory` 可显式注入画像、Chat 扫描工具会把注入 DB 的复盘聚合进 profile、扫描器本身不读 SQLite。Web `/api/profile` 走只读 `TradingMemoryDB.open_readonly_if_exists()`；HTTP 级 Web API 测试仍需可写数据目录环境。

真实 OP 机会复盘记录入口变更时，可额外运行：

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "review_done_command or review_command_lists_safe_opportunity_outcomes or sqlite_outcomes" -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','tests/test_chat_memory_commands.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

该集合确认 `/review done OPID 实际利润 [反馈]` 和 `/复盘 完成 OPID 实际利润` 会从真实未过期 OP 机会写入 `opportunity_outcomes`，同时不破坏 `/review completed` 状态筛选，也不会把玩家名、profile 链接、`/w` 或 raw order steps 写进长期复盘 metadata。

Scout 推送质量聚合变更时，可额外运行：

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_trading_memory.py -k "push_quality or push_history or opportunity_outcomes" -q
.\.venv\Scripts\python.exe -m pytest tests/test_proactive_push.py -k "records_to_injected_trading_memory_db or sanitizes_trade_plan_before_recording" -q --basetemp .pytest_tmp_step17_push_final
.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k push_quality -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/trading_memory.py','warframe_agent/web/app.py','tests/test_trading_memory.py','tests/test_proactive_push.py','tests/test_web_api.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

该集合确认 `push_history` 和 `opportunity_outcomes` 可以被安全聚合为 Scout 风格推送质量信号，Web `GET /api/trading-memory/push-quality` 只返回计数、比例和利润聚合，不返回 raw metadata、玩家名、profile、market URL、`/w` 或 token。普通沙箱如果在导入 Web app 时因 SQLite WAL 报 `sqlite3.OperationalError: unable to open database file`，需要在可写数据目录环境中补跑 Web API 目标。

投资顾问默认参数接入个人偏好时可先跑窄测试：

```bash
python -m pytest tests/test_investment.py -k "resolve_investment_preference_defaults" -q
python -m pytest tests/test_chat_memory_commands.py -k "investment_tool_uses_preference_defaults or investment_tool_treats_blank_args or scan_tools_pass_personal_profile" -q
python -m pytest tests/test_web_api.py -k "investment_api_uses_preference_defaults or investment_api_http_query_omitted_and_empty_use_preference_defaults or investment_api_http_query_preserves_explicit_zero" -q
node --check warframe_agent/web/static/js/sidebar.js
```

Web `/api/investment` 的缺省参数回归覆盖直接 endpoint 调用、真实 HTTP omitted query、真实 HTTP empty query 和显式 `0`。普通沙箱如果在导入 Web app 时因 SQLite WAL 报 `sqlite3.OperationalError: unable to open database file`，需要在可写本项目数据目录的环境中补跑；Step 6 相关 Web API 目标曾在沙箱外通过，后续运行态相关变更仍需按各自步骤单独重跑。

B 站攻略视频推荐变更建议先运行：

```bash
python -m pytest tests/test_bilibili_recommendations.py tests/test_build_bilibili_recommendations.py tests/test_chat.py -q
```

该集合覆盖本地推荐数据加载、`needs_review` 跳过、主武器/副武器/近战分类推荐、具体武器配卡问题命中对应视频、具体战甲问题命中具体战甲名或别名、泛问战甲攻略按 warframe 类别返回、具体宠物问题命中具体同伴名或别名、泛问宠物攻略按 companion 类别返回、泛泛“怎么玩”不触发基础配卡推荐、价格类问题不出现视频推荐，以及候选元数据生成覆盖报告/推荐草稿/多模型复核建议时不会把待复核候选写进正式推荐库。

聊天模式分层或 B 站/市场意图优先级变更时，可先跑更窄集合：

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "chat_mode or bilibili_video_words or direct_market_intent or answer_returns_bilibili_recommendations or does_not_append_bilibili" -q
.\.venv\Scripts\python.exe -m pytest tests/test_bilibili_recommendations.py -q --basetemp .pytest_tmp_step18_bilibili
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','tests/test_chat.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

该集合确认 `_classify_chat_mode(...)` 会让直接交易、市场分析、交易工具和事件优先于 B 站攻略；`answer(...)` 和 `answer_stream(...)` 对“价格 + 攻略视频”混合问法返回实时订单摘要，不返回 B 站视频或“暂未收录”。

自然语言目标/计划模式变更时，可额外运行：

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "chat_mode or planning_mode or bilibili_video_words or direct_market_intent" -q
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "planning_include_plan or investment_query_include_investment_tools or react_loop_records_agent_plan_snapshot" -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/tool_router.py','tests/test_chat.py','tests/test_tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

该集合确认自然语言 planning 请求会返回安全计划草案和 `/goal set ...` 入口，不抓订单、不生成 `/w` 私聊、不进入 B 站攻略；同时 `tool_router.select_candidate_tools(...)` 会把 `plan` 放进计划请求候选，供未来显式执行计划使用。

B 站 fallback 视频库维护命令：

```bash
python tools/build_bilibili_recommendations.py
```

默认读取 `Extra Resource/exports/bilibili_metadata/bili-space-api-title-candidates.json`，输出 `fallback_inventory_report.json`、`bilibili_recommendation_candidates.json` 和 `bilibili_recommendation_review_summary.json`。该命令只生成报告、候选和复核摘要，不修改正式推荐库。

确认要把工具保守识别出的新视频链接元数据追加到正式推荐库时，显式运行：

```bash
python tools/build_bilibili_recommendations.py --append-approved
```

`--append-approved` 也只追加标题、BVID、URL、分类、武器名、别名等视频元数据；不会写入 MOD、赋能、特殊槽或灵化选择。待复核候选保持 `needs_review: true`，不会被 `BilibiliRecommendationStore` 加载。

拿到完整主手/副手/近战合集导出后，可用多个 `--source-spec` 输入并附带合集分类：

```bash
python tools/build_bilibili_recommendations.py \
  --source-spec "Extra Resource/exports/bilibili_metadata/primary_collection.json=primary" \
  --source-spec "Extra Resource/exports/bilibili_metadata/secondary_collection.json=secondary" \
  --source-spec "Extra Resource/exports/bilibili_metadata/melee_collection.json=melee"
```

`--source-spec` 的输入 JSON 应为数组，每项至少包含 `bvid` 或可解析 BVID 的 `url`，推荐包含 `title`、`url`、`author`。合集分类只作为元数据和候选分类提示；未知武器名仍会保持 `needs_review: true`，不会自动写入正式推荐库。人工复核时优先查看 `bilibili_recommendation_review_summary.json`，它只列出待复核候选，并按分类附带标题前缀、BVID、URL、来源和复核原因。

宠物/同伴/守护/猎犬/恐鸟最终清单导入命令：

```bash
python tools/build_bilibili_recommendations.py \
  --source "Extra Resource/exports/bilibili_metadata/companion_build_links_final.json" \
  --report "Extra Resource/exports/bilibili_metadata/companion_build_import_report.json" \
  --candidates "Extra Resource/exports/bilibili_metadata/companion_build_recommendation_candidates.json" \
  --review-summary "Extra Resource/exports/bilibili_metadata/companion_build_recommendation_review_summary.json" \
  --append-approved
```

该命令从标题和搜索词抽取常见宠物/同伴别名，写入 `companions`、`aliases`、`category: companion`、`priority` 和 `updated_at`。排序规则会提高“最新”“2025”“现版本”“T0”“详细”等更适合当前版本或更具体的视频优先级；合集仍可作为补充结果。具体宠物记录不应带 `同伴配卡`、`宠物攻略` 这类泛用别名，避免“死亡魔方同伴配卡”被铁甲狐视频抢结果。

战甲最终清单导入命令：

```bash
python tools/build_bilibili_recommendations.py \
  --source "Extra Resource/exports/bilibili_metadata/warframe_build_links_final.json" \
  --report "Extra Resource/exports/bilibili_metadata/warframe_build_import_report.json" \
  --candidates "Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_candidates.json" \
  --review-summary "Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_review_summary.json" \
  --append-approved
```

该命令从标题和搜索词抽取常见战甲名/别名，写入 `warframes`、`aliases`、`category: warframe`、`priority` 和 `updated_at`。当前首批数据来自本地 B 站“战甲合集”导出；若实时 Playwright/B 站搜索可用，可先扩展 `warframe_search_results.json` 和 `warframe_build_links_curated.json`，再生成 `warframe_build_links_final.json`。具体战甲记录不应带 `战甲配卡`、`战甲攻略` 这类泛用别名，避免“夜灵配卡”被不相关战甲视频抢结果。

多模型复核待确认候选时运行：

```bash
CLOUD_API_BASE="http://localhost:8080" CLOUD_API_KEY="<local-relay-key>" python tools/review_bilibili_recommendations_with_models.py --limit 10
```

如果本地中转站不接受无 `/v1` 地址，再用 `CLOUD_API_BASE="http://localhost:8080/v1"` 重试。该命令只生成 `bilibili_recommendation_model_suggestions.json`，已确认合集的主手/副手/近战分类直接沿用合集来源，模型只辅助武器名和别名；所有建议默认 `approved: false`；人工确认后把对应项改为 `approved: true`，再运行：

```bash
python tools/build_bilibili_recommendations.py --apply-approved-suggestions "Extra Resource/exports/bilibili_metadata/bilibili_recommendation_model_suggestions.json"
```

应用建议时只写入视频元数据，禁止写入 MOD、赋能、特殊槽、灵化选择、流派或枪架子。

B 站视频画面解析维护工具变更建议运行：

```bash
python -m pytest tests/test_video_analysis_models.py tests/test_video_analysis_regions.py tests/test_video_analysis_icon_match.py tests/test_video_analysis_draft.py tests/test_video_analysis_storage.py tests/test_video_analysis_ocr.py tests/test_video_analysis_frame_capture.py tests/test_analyze_bilibili_video.py -q
```

首个伯斯顿公开视频解析草稿可用以下命令重新生成，结果只作为人工确认材料，不进入 Agent 回答：

```bash
python tools/analyze_bilibili_video.py "https://www.bilibili.com/video/BV1dJ5LzREZk" --title "伯斯顿-步枪救星" --timestamp 8 --timestamp 13 --timestamp 18 --timestamp 29 --timestamp 35 --timestamp 45 --frame data/video_frames/BV1dJ5LzREZk-8.png --frame data/video_frames/BV1dJ5LzREZk-13.png --frame data/video_frames/BV1dJ5LzREZk-18.png --frame data/video_frames/BV1dJ5LzREZk-29.png --frame data/video_frames/BV1dJ5LzREZk-35.png --frame data/video_frames/BV1dJ5LzREZk-45.png --fake-ocr-weapon "伯斯顿 Prime" --output data/video_parse_drafts.jsonl
```

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

服务启动后访问 `/api/runtime/status`，确认返回 `web`、`feishu`、`wxpusher`、`scheduler`、`daily_report`、`background_tasks`、`recent_tool_calls`、`agent_trace` 和 `safety_policy` 字段；前端侧栏状态点应能显示在线、检查中、部分异常或连接错误，点击状态点应打开只读运行态详情。

运行态安全策略快照变更可先验证：

```bash
python -m pytest tests/test_tool_registry.py -k "tool_registry_safety_summary or runtime_safety_policy_embeds_tool_registry_summary" -q
python -m pytest tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q
node --check warframe_agent/web/static/js/app.js
```

该测试覆盖 shell、通用文件写入、浏览器私网和任意调度器默认禁用，市场网络读取为只读，项目数据写入受限，scheduler jobs 和外部推送只返回布尔状态；ToolRegistry 只返回聚合统计，不返回 handler、参数名、参数 schema、raw args、ToolResult 或 model_context；同时确认 runtime/status 不泄漏 Push token、UID、Feishu app_secret 或 chat_id。普通沙箱如果在导入 Web app 时因 SQLite WAL 报 `sqlite3.OperationalError: unable to open database file`，需要在可写本项目数据目录环境中重跑 Web API 目标。

Agent Trace 运行态变更可先验证：

```bash
python -m pytest tests/test_tool_router.py -k "lifecycle" -q
python -m pytest tests/test_web_api.py -k "runtime_status or agent_trace_snapshot" -q
python -m pytest tests/test_web_ui_playwright.py -k "runtime_status or agent_trace" -q
node --check warframe_agent/web/static/js/app.js
```

`agent_trace` 只允许展示安全快照。生命周期字段只包含 `status`、`started_at`、`ended_at`、`max_iterations` 和 `duration_ms` 这类标量；检查页面文本时应确认没有 `secret-token`、`Bearer`、`raw_arguments`、`result_summary`、`secret final answer`、warframe.market profile URL、玩家名或 `/w` 私聊片段。普通沙箱如果在导入 Web app 时因 SQLite WAL 报 `sqlite3.OperationalError: unable to open database file`，需要在可写本项目数据目录的环境中重跑 pytest。

AgentPlan 运行态只读快照变更可先验证：

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "agent_plan or lifecycle" -q
.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k "runtime_status_includes_safe_agent_trace_snapshot" -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/tool_router.py','warframe_agent/web/app.py','tests/test_tool_router.py','tests/test_web_api.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

该集合确认 `plan` 工具执行时会生成只读 `AgentPlanSnapshot`，步骤状态会从 pending/running 进入 completed 或 failed；runtime status 只返回 goal 是否存在、最多 10 个步骤、工具名、purpose、安全参数摘要、状态、耗时和是否有结果，不返回 raw arguments、完整 result summary、final answer、profile、`/w` 或 token。普通沙箱如遇 SQLite WAL 导入错误，需要在可写数据目录环境中补跑 Web API 目标。

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

## 2026-05-26 追加：AgentPlan Web 运行态面板验证

AgentPlan 运行态面板变更建议使用项目内虚拟环境验证，不需要安装新包：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "agent_plan or lifecycle" -q
node --check warframe_agent/web/static/js/app.js
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['tests/test_web_ui_playwright.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

该 Playwright 用例会在 fixture 中故意放入 `raw_arguments`、`result_summary`、token、玩家名、`/w` 和 `final_answer` 相关字段，确认 Web Runtime 面板只显示安全摘要：`Agent Plan`、`plan_status`、`goal_present`、`plan_steps`、步骤 purpose、工具名、`result_present` 和 `error_present`。

## 2026-05-26 追加：运行态验证闭环

Step 14 用于集中补齐 Step 4-13 的 Web/API/UI/记忆验证闭环。推荐命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k "runtime_status" -q
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py -k "runtime_panel" -q
.\.venv\Scripts\python.exe -m pytest tests/test_tool_registry.py -k "tool_registry_safety_summary or runtime_safety_policy_embeds_tool_registry_summary" -q
.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py -k "sqlite_opportunity_outcomes or outcome_feedback" -q
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "sqlite_outcomes or review" -q
node --check warframe_agent/web/static/js/app.js
```

本轮补验证发现并修复了两个运行态安全摘要问题：最近工具调用的 `args_summary` 会额外跳过 `message_context`、`prompt`、`model_context`、`final_answer`、`profile`、`whisper` 等敏感键；ToolRegistry 聚合字段从 `hidden_schema_count` 改为 `private_schema_count`，避免运行态序列化中出现与敏感测试值 `hidden` 撞名的字段。普通沙箱仍可能在导入 Web app 时因 SQLite WAL 报 `sqlite3.OperationalError: unable to open database file`，此时需要在可写数据目录环境中重跑 Web API 目标。

## 2026-05-26 追加：普通物品交易辅助意图优先级

Step 15 补齐普通物品直接交易辅助的优先级和流式覆盖。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "direct_market_intent_takes_precedence_over_bilibili_video_words_when_market_requested or generic_cheapest_seller_intent_wins_when_link_is_also_requested or answer_stream_generic_market_link_intent_returns_url_without_fetching_orders or answer_stream_generic_cheapest_seller_intent_returns_whisper_and_link" -q
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "market_link_intent or cheapest_seller_intent or bargain_intent or bilibili or answer_stream_generic" -q
```

该集合确认“市场链接/最低卖家/砍价”等直接市场意图不会被“B站/视频/攻略”混合词抢走；“最低卖家 + 市场链接”会返回卖家、价格、复制用私聊和链接，而不是只返回裸链接；`answer_stream` 与普通 `answer` 保持相同的普通物品交易路径。当前验证结果为聚焦用例 `4 passed`，市场/B站周边守护用例 `16 passed`。

## 2026-05-26 追加：Conversation Log 默认安全写入

Step 16 把 `conversation_logs.jsonl` 的安全边界前移到写入点。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_conversation_log.py -q --basetemp .pytest_tmp_step16_conv
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "direct_market_answer_conversation_log_uses_safe_summary or records_sanitized_user_query_summary or answer_stream_records_one_sanitized_user_query_summary or router_tool_path_records_safe_tool_names_only or chat_uses_memory_recall_safe_summary_only" -q
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "conversation_log or tool_calls_do_not_leak" -q
```

该集合确认普通长期对话日志会写入 `summary:v1 role=...` 安全摘要；用户可见回答仍可包含复制用 `/w`，但持久化日志不保存玩家名、profile、market URL、token、`message_context`、`raw_arguments`、`model_context`、`result_summary` 或 `final_answer`。当前验证结果为 `tests/test_conversation_log.py` 12 个通过、聊天安全记忆窄测 5 个通过、ToolRouter 日志窄测 2 个通过。

## 2026-05-26 追加：`/goal set` 自然语言目标解析

Step 20 让 `/goal set` 从中文目标句解析结构化 criteria。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_goals.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "planning_mode or chat_mode or direct_market_intent or bilibili_video_words" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```

该集合确认 `/goal set 一周赚500p，预算300p，低风险，最低ROI 20%` 会保存 `target_profit/target_amount/timeframe_days/budget/risk/min_roi`，并创建 `earn_platinum` 目标；普通 `/goal set 找高利润倒卖机会` 仍保持旧的 `maximize_profit` 和默认 `budget=500/min_roi=10`。测试使用 fake `GoalTracker`，避免污染真实 `data/goals.json`。

## 2026-05-26 追加：确认式目标创建

Step 21 给自然语言 planning 增加确认式目标创建。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "goal_confirmation or goal_set" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "planning_mode" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```

该集合确认自然语言 planning 首轮只展示“是否创建”确认，不写入目标；用户回复“确认创建”后才保存解析后的目标；回复“取消”会清除待确认状态。`/goal set` 仍保留为底层显式入口。

## 2026-05-26 追加：自然语言价格提醒

Step 22 让 `/alert add/remove` 的常见用法支持自然语言。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_price_alert or natural_language_price_question or vague_cancel or add_alert" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```

该集合确认“充沛低于45p提醒我”“充沛高于100p通知我”会写入价格提醒；“取消充沛低于45p提醒”会精确移除；`answer_stream` 与普通 `answer` 一致；“充沛低于45p了吗”和“取消提醒”不会误创建或误删除提醒。

## 2026-05-26 追加：自然语言收藏关注

Step 23 让 `/fav add/remove` 的常见用法支持自然语言。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_favorite or favorite" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```

该集合确认“帮我关注充沛”“帮我收藏充沛”会写入收藏；“取消关注充沛”“取消收藏充沛”会移除收藏；`answer_stream` 与普通 `answer` 一致；“关注列表”“充沛值得关注吗”和“充沛低于45p提醒我”不会误加收藏；重复关注不会产生重复收藏项。

## 2026-05-26 追加：自然语言偏好更新

Step 24 让 `/pref` 的常见长期偏好设置支持自然语言。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_preference or profile_pref" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```

该集合确认“我的预算300p，偏低风险，最低利润15%”“我偏好mod和赋能，最长周转3天”“平台设为xbox，关闭跨平台，最多显示10个结果”会写入长期偏好；`answer_stream` 与普通 `answer` 一致；“300p预算买什么好”“充沛低于45p提醒我”“帮我收藏充沛”和“交易机会只检测MOD”不会被偏好入口抢走。

## 2026-05-26 追加：自然语言目标完成/放弃确认

Step 25 让 `/goal done/drop` 的常见用法支持自然语言确认式入口。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "goal_status_confirmation or goal_confirmation or goal_set" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```

该集合确认“完成第1个目标”“放弃第1个目标”只创建待确认状态；“确认完成/确认放弃”才写入 `achieved/abandoned`；“取消”会清除待确认；`answer_stream` 与普通 `answer` 一致；“完成目标了吗”不会误创建状态更新；显式 `/goal done ID` 仍直接执行。

## 2026-05-26 追加：自然语言交易复盘确认

Step 26 让 `/review done` 的常见用法支持自然语言确认式入口。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "review_done_natural_language or review_done_command" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```

该集合确认“OPID 实际赚45p，结果不错，帮我复盘”只创建待确认状态；“确认复盘”才写入 completed opportunity outcome；“取消”不会写库；`answer_stream` 与普通 `answer` 一致；缺 OPID、缺有效利润和普通市场聊天不会误触发；显式 `/review done OPID 45 good` 仍直接执行。

## 2026-05-26 追加：自然语言裂缝提醒确认

Step 27 让 `/fissure add/remove` 的常见用法支持自然语言确认式入口。推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "fissure_alert_natural_language or fissure_command" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
```

该集合确认“提醒我钢铁后纪歼灭裂缝”只创建待确认订阅；“确认订阅”才写入 `FissureAlert`；“取消”不会写入；“取消第1个裂缝提醒/确认取消”才移除订阅；`answer_stream` 与普通 `answer` 一致；“现在有什么裂缝”不会误订阅；显式 `/fissure add ...` 与 `/fissure remove 1` 仍直接执行。

本步当前验证结果：裂缝提醒窄测 `6 passed, 50 deselected`；聊天命令全量 `56 passed`；`warframe_agent` AST 检查通过；`git diff --check` 对本步相关文件退出码为 0，仅有 CRLF 转换提示。
