# Step 15：普通物品交易辅助意图优先级

## 本次借鉴点

- 个人 Agent 的意图路由要优先处理用户最可执行的请求。用户同时说“市场链接”和“攻略视频”时，交易请求比视频推荐更具体，应直接返回 warframe.market 链接。
- 同一条能力必须覆盖普通回答和流式回答。`answer_stream` 不是单独的功能分支，而是同一套确定性交易路径的流式输出入口。
- 在交易意图内部，“最低卖家/砍价”比“市场链接”更具体。用户同时要求卖家和链接时，应返回卖家、价格、复制用私聊和链接，而不是只返回裸链接。

## 已完成

- `warframe_agent/chat.py`
  - 直接市场意图现在在 B 站直出推荐之前运行，避免“攻略视频/B站”等词抢走明确的市场请求。
  - `_try_direct_market_intent` 中只有纯链接请求才直接返回链接；如果同时包含“最便宜卖家/最低卖家/砍价”等词，会继续查询订单并返回更完整的交易辅助。
- `tests/test_chat.py`
  - 新增普通物品市场请求优先于 B 站视频词的回归测试。
  - 新增“最便宜卖家 + 市场链接”由卖家意图优先的回归测试。
  - 新增 `answer_stream` 对普通物品市场链接和最低卖家的专项测试。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "direct_market_intent_takes_precedence_over_bilibili_video_words_when_market_requested or generic_cheapest_seller_intent_wins_when_link_is_also_requested or answer_stream_generic_market_link_intent_returns_url_without_fetching_orders or answer_stream_generic_cheapest_seller_intent_returns_whisper_and_link" -q
# 4 passed

.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "market_link_intent or cheapest_seller_intent or bargain_intent or bilibili or answer_stream_generic" -q
# 16 passed
```

## 后续可继续

- 长期记忆 vault 化：把敏感交易展示与可学习摘要分层存储。
- Scout 推送质量评估：为主动机会增加命中率、误报率和收益复盘指标。
- 聊天模式分层：把“视频攻略”“交易执行”“价格分析”“长期计划”做成更明确的本地模式选择。
