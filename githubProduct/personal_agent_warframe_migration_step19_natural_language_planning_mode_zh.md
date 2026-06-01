# Step 19：自然语言目标 / 计划模式

## 本次借鉴点

- 个人 Agent 需要把“计划/目标”与“立即交易执行”分开。用户说“制定计划”“一周赚 500p”“不要直接买”时，系统应先给安全计划草案，而不是抓订单、生成 `/w` 私聊或进入 B 站攻略。
- 自然语言计划默认不自动创建目标。显式追踪仍使用 `/goal set ...`，这样能避免误把一次咨询变成长期任务。
- Router 层可以把 `plan` 放进候选工具，为后续多步骤执行准备能力；ChatAgent 当前只做安全预览，不自动执行工具计划。

## 已完成

- `warframe_agent/chat.py`
  - `_classify_chat_mode(...)` 新增 `planning` 模式。
  - `_message_has_planning_intent(...)` 识别“计划/规划/目标/路线图/plan”和“时间范围 + 收益目标”。
  - `answer(...)` 与 `answer_stream(...)` 在直接市场意图之后、B 站推荐之前消费 planning 模式。
  - `_try_planning_intent(...)` 返回确定性“计划草案”，并提示 `/goal set ...`，不抓订单、不生成购买私聊、不自动创建目标。
- `warframe_agent/tool_router.py`
  - `select_candidate_tools(...)` 对自然语言计划请求加入 `plan`、`investment_advisor`、`mod_flipper`、`set_profit`、`query_price`、`price_trend` 候选。
- `tests/test_chat.py`
  - 覆盖 planning 分类、市场链接优先、目标计划压过攻略视频、普通回答和流式回答都不执行交易。
- `tests/test_tool_router.py`
  - 覆盖计划请求候选包含 `plan`。

## 准备学习的清单

- 后续可让 `/goal set ...` 解析目标金额、周期和风险，而不是继续硬编码预算和 ROI。
- 后续可让 planning 预览读取个人偏好和 Step 17 的推送质量聚合，但仍保持默认不执行交易。
- 后续可在用户明确确认后把自然语言计划转换成 `GoalTracker` 目标或 `tool_router.plan`。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_chat_mode_classifier_prioritizes_market_over_video_words -q
# 1 passed

.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_natural_language_planning_mode_does_not_execute_trade_or_bilibili tests/test_chat.py::ChatTests::test_answer_stream_natural_language_planning_mode_matches_answer_priority -q
# 2 passed

.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py::ToolRouterTests::test_candidate_tools_for_natural_language_planning_include_plan -q
# 1 passed
```

## 后续可继续

- `/goal set` 目标解析增强：从“一周赚 500p、预算 300p、低风险”中提取周期、目标利润、预算和风险。
- 主动推送质量权重：把 Step 17 聚合结果用于温和调整推送优先级。
