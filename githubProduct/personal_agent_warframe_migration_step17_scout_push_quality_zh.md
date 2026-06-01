# Step 17：Scout 推送质量评估

## 本次借鉴点

- 主动推送不只要“发出去”，还要能复盘“有没有被处理、有没有赚钱、有没有误报”。这类质量信号可以学习 Scout/个人 Agent 的闭环思路，但只保存聚合指标。
- 长期库不要保存 raw 订单、玩家名、profile 链接或 `/w` 私聊。`push_history` 记录安全的发送事实，`opportunity_outcomes` 记录安全复盘结果，质量层只在两者之上做统计。
- 质量评估要按 `item_name + source + strategy + category` 分桶，否则同一物品的不同机会来源会互相污染，例如赋能倒卖和套装套利不应混在一起。

## 已完成

- `warframe_agent/trading_memory.py`
  - 新增 `PushQualitySignal`。
  - 新增 `TradingMemoryDB.summarize_push_quality(...)`，聚合 `sent_count`、`reviewed_count`、`completed_count`、`accepted_count`、`rejected_count`、`pending_count`、`good_count`、`bad_count`、利润均值和质量率。
  - 从 `push_history.metadata.safe_summary`、`opportunity_source`、`source`、`strategy` 等安全字段推断来源、策略和品类。
  - 对 rejected/failed/expired/skipped、bad/ignored/rejected 反馈和负实际利润归为差结果，用于误报率。
- `warframe_agent/web/app.py`
  - 新增 `GET /api/trading-memory/push-quality`。
  - API 只返回安全聚合字段，不返回 metadata、profile、market URL、whisper、token 或玩家名。
- `tests/test_trading_memory.py`
  - 覆盖安全聚合、过滤 item/source、future since 过滤和敏感字段不泄漏。
- `tests/test_proactive_push.py`
  - 覆盖真实 proactive push 写入的安全元数据可以被质量聚合消费。
- `tests/test_web_api.py`
  - 覆盖 Web API 返回安全聚合字段。

## 准备学习的清单

- 观察 `good_rate` 和 `false_positive_rate` 是否能作为后续主动推送降噪权重。
- 观察 `avg_profit_delta` 是否能发现预期利润偏乐观的策略。
- 观察 `pending_count` 是否能区分“还没复盘”和“用户明确拒绝”。
- 后续可把该聚合注入个人画像，但仍应只注入 bucket 级指标，不注入 OP 明细。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trading_memory.py -k "push_quality" -q
# 2 passed

.\.venv\Scripts\python.exe -m pytest tests/test_proactive_push.py -k "records_to_injected_trading_memory_db or sanitizes_trade_plan_before_recording" -q --basetemp .pytest_tmp_step17_push
# 3 passed, 20 deselected

.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k push_quality -q
# 1 passed, 69 deselected
```

## 后续可继续

- 聊天模式分层：把视频攻略、交易执行、价格分析和长期计划做更明确的本地路由。
- 质量权重接入主动推送：用 Scout push quality 的聚合结果温和调整不同 source/strategy 的推送优先级。
