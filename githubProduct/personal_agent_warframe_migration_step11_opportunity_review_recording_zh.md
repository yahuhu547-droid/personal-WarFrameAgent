# Step 11: 真实 OP 机会复盘记录入口

本步把“机会推送”与“长期复盘学习”接起来：聊天侧新增 `/review done OPxxxxxx 实际利润 [good|bad|neutral|ignored]`，也支持中文 `/复盘 完成 OPxxxxxx 实际利润`。

## 学习借鉴点

- 记录入口必须先命中 `OpportunityLookupStore` 中未过期的真实 OP 机会，避免用户随便构造一条复盘污染画像。
- 写入 `TradingMemoryDB.opportunity_outcomes` 时只保存 `trade_plan.safe_summary` 白名单字段，不保存玩家名、profile 链接、`/w` 私聊命令、buy/sell steps 或 raw orders。
- `actual_profit` 来自用户复盘输入，可以为负数；不输入反馈时按利润自动推断 `good`、`bad` 或 `neutral`。
- `/review completed` 仍保持原有按状态筛选列表语义，记录入口只占用 `done`、`complete`、`完成`、`记录`。
- 这一步让 Step 10 的 SQLite 复盘画像注入有真实长期数据来源，后续个人评分可以从真实执行结果中逐步学习。

## 使用示例

```text
/review done OP8K3A2Q 45 good
/复盘 完成 OP8K3A2Q -12 bad
```

预期结果：系统返回“已记录机会复盘”，并在 `/review completed` 中可看到该 OP 的状态、预期利润、实际利润和反馈。

## 安全边界

长期记忆只保留 OP ID、item_id、source、strategy、status、expected_profit、actual_profit、user_feedback 和安全 metadata。完整市场执行细节仍只存在于短期 `opportunity_lookup.db`，并随 TTL 过期清理。
