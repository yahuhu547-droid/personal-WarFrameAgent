# Personal Agent 学习迁移 Step 9: 机会复盘反馈闭环

日期: 2026-05-26

## 借鉴点

个人 Agent 项目里最有价值的学习闭环不是保存更多原始记录，而是把用户已经确认过的结果变成可复用的偏好信号。本步借鉴“复盘 -> 聚合记忆 -> 下一次排序”的思路，让历史机会结果影响个人评分，但只使用安全统计字段。

## 已落地内容

- `warframe_agent/personal_profile.py` 新增 `OutcomeFeedbackSignal` 聚合结构。
- `build_personal_profile(...)` 会从 `AgentMemory.trade_outcomes` 提炼 `source`、`strategy`、`category`、样本数、胜负数、平均实际利润和好结果比例。
- `profile_safe_summary(...)` 新增 `outcome_feedback` 安全摘要，不包含 `outcome_id`、`goal_id` 或任何玩家级字段。
- `warframe_agent/personal_scoring.py` 在样本数达到 3 条后才使用复盘反馈做小幅调权：
  - 历史同类策略表现好时增加个人分，并给出 `历史策略表现好`。
  - 历史同类策略亏损或差评多时降低个人分，并给出 `历史策略需谨慎`。
  - 单条或两条稀疏样本不会影响评分。
- 未知 `TradeOutcome.action` 不再作为 `source` 或 `strategy` 输出；只能归为 `unknown`，避免把 token、玩家名、whisper 或 profile 语义通过清洗后的字符串带入安全摘要。

## 安全边界

- 评分不读取 SQLite、不读取 OP 短期详情库，也不读取 raw orders。
- 画像和评分只使用聚合统计，不保存玩家名、profile 链接、`/w` 私聊命令、token、API key、原始用户问题或助手回复。
- `outcome_id` 和 `goal_id` 不进入 `profile_safe_summary`、评分理由或模型上下文。
- 调权幅度有上限，不能覆盖预算、ROI、风险和利润这些主规则。

## 本轮验证

- 已红绿验证: `.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py -k "outcome_feedback" -q`
- 已红绿验证: `.venv\Scripts\python.exe -m pytest tests/test_personal_scoring.py -k "outcome_feedback or sparse" -q`
- 已通过: `.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py tests/test_personal_scoring.py -q`，结果 `12 passed`
- 已通过: `.venv\Scripts\python.exe -m pytest tests/test_mod_flipper.py -k "personal_score" -q`
- 已通过: `.venv\Scripts\python.exe -m pytest tests/test_set_profit.py -k "personal_score" -q`
- 已通过: `.venv\Scripts\python.exe -m pytest tests/test_investment.py -k "personal_score" -q`
- 注意: 普通 `python` 当前指向 `F:\anaPhy\python.exe` 和 pytest 3.8，在收集测试时会卡住；本项目测试应使用工作区 `.venv\Scripts\python.exe`。

## 下一步建议

1. 后续可把 SQLite `opportunity_outcomes` 作为显式参数注入 `build_personal_profile(...)`，但不要让扫描器直接查库。
2. Web 画像面板可在需要时展示“历史策略反馈”聚合，而不是展示单次复盘明细。
3. 当记录真实 OP outcome 的入口补齐后，再做 `opportunity_outcomes -> profile outcome_feedback` 的第二阶段接线。
