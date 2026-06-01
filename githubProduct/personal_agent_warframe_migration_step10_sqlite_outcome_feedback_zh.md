# Personal Agent 学习迁移 Step 10: SQLite 机会复盘注入个人画像

日期: 2026-05-26

## 借鉴点

Step 9 已经完成“JSON 交易结果 -> 聚合画像 -> 个人评分”的闭环。本步继续借鉴个人 Agent 的复盘记忆设计，把长期 SQLite `opportunity_outcomes` 显式注入画像构建，但不让扫描器直接读库，保持工具层纯净。

## 已落地内容

- `build_personal_profile(...)` 新增 keyword-only 参数 `opportunity_outcomes`。
- `personal_profile.py` 可以同时聚合 `AgentMemory.trade_outcomes` 和 SQLite `OpportunityOutcomeMemory`。
- 聚合字段仍只包含 `source`、`strategy`、`category`、样本数、胜负数、平均实际利润和好结果比例。
- `ChatAgent` 新增统一画像构建路径：从注入的 `trading_memory_db` 读取最近机会复盘，再传入 profile。
- `/profile`、Mod/赋能翻转、套装套利、投资顾问这几条 Chat 路径都会使用带 SQLite 复盘的画像。
- Web `/api/profile`、`/api/profile/preferences` 和三个 Web 扫描端点使用只读 `TradingMemoryDB.open_readonly_if_exists()` 注入复盘记录。

## 安全边界

- `personal_profile.py` 不 import、不打开 `TradingMemoryDB`，只接收调用方传入的记录。
- 扫描器不读 SQLite，也不接触 OP ID 或原始 metadata。
- `profile_safe_summary` 不返回 `opportunity_id`、玩家名、profile URL、`/w`、token、secret、raw orders 或完整 metadata。
- 未知或敏感的 source/strategy 会回落到 `unknown`，不会把清洗后的敏感字符串带入画像摘要。
- Web 侧读取 SQLite 使用只读连接；数据库不存在时返回空复盘，不创建新库。

## 本轮验证

- 已红绿验证: `.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py -k "sqlite_opportunity_outcomes" -q`
- 已红绿验证: `.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "sqlite_outcomes" -q`
- 已通过: `.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py tests/test_personal_scoring.py -q`
- 已通过: `.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "profile_command or scan_tools_pass_personal_profile or sqlite_outcomes" -q`
- 已通过: `.venv\Scripts\python.exe -B -c "... ast ..."` 解析 profile/chat/web/app 和相关测试。
- Web API pytest 仍需在可写数据目录环境中补跑；普通导入 Web app 的路径可能触发 SQLite WAL 限制。

## 下一步建议

1. 增加真实 OP outcome 记录入口，例如聊天命令 `/review done OPxxxx good 45p` 或 Web 表单。
2. Web 画像面板可展示聚合历史策略反馈，但不要展示单条 OP 明细。
3. 当 Web API 测试环境可写后，补跑 `/api/profile` 的 HTTP 级回归。
