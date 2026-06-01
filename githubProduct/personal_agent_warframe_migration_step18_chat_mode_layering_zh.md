# Step 18：聊天模式分层

## 本次借鉴点

- 个人 Agent 的聊天入口需要先做轻量模式判断，再决定是否进入攻略视频、市场交易、价格分析、事件或工具路由。
- 模式分层应优先解决冲突词，而不是重写整条 ChatAgent 链路。第一步只让“价格/交易词”压过“攻略/视频词”，避免用户问价格时被 B 站推荐抢答。
- `answer(...)` 和 `answer_stream(...)` 必须共用同一套优先级，否则普通回答和流式回答会产生不一致体验。

## 已完成

- `warframe_agent/chat.py`
  - 新增 `ChatModeDecision`。
  - 新增 `_classify_chat_mode(...)`，当前输出 `trade_execution`、`event`、`trading_tool`、`market_analysis`、`guide_video`、`general`。
  - B 站直出和追加推荐现在只在 `guide_video` 模式触发。
  - 当问法同时包含价格和攻略视频词时，`market_analysis` 会返回实时订单摘要，不依赖 LLM 输出。
- `tests/test_chat.py`
  - 覆盖分类器优先级。
  - 覆盖 `answer(...)` 和 `answer_stream(...)` 中“充沛多少钱，顺便给攻略视频”走价格摘要，不返回 B 站视频。

## 准备学习的清单

- 继续观察自然语言“目标/计划”是否需要从 Router 前移到显式 `planning` 模式。
- 继续观察哪些价格问法应该走确定性实时订单摘要，哪些仍适合 LLM 做解释性分析。
- 后续如接入更多模式，优先保持分类器纯函数可测，不把工具执行副作用放进分类器。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_chat_mode_classifier_prioritizes_market_over_video_words -q
# 1 passed

.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_price_mode_wins_over_explicit_bilibili_video_words tests/test_chat.py::ChatTests::test_answer_stream_price_mode_wins_over_explicit_bilibili_video_words -q
# 2 passed
```

## 后续可继续

- 自然语言目标/计划模式：把“制定一周赚 500p 计划”从普通市场问答中分离出来。
- 主动推送质量权重：把 Step 17 的聚合结果用于温和调整 source/strategy 优先级。
