# Step 28：Scout 推送质量接入主动推送优先级

## 本次借鉴点

- 个人 Agent 的主动推送不能只看“当前这条机会利润高不高”，还要参考历史复盘里“类似来源/策略是否经常被接受、完成、赚钱或误报”。这次学习的是反馈闭环进入执行前最后一公里，而不是重写底层扫描器。
- 质量反馈只适合做二级排序信号，不适合一上来做硬过滤。否则少量坏样本可能误杀新机会，也可能覆盖用户当前偏好、ROI 排序和冷却去重。
- 质量信号必须是聚合字段：`good_rate`、`false_positive_rate`、`reviewed_count`、`sent_count` 等。不能把 raw 订单、玩家名、profile URL、market URL、`/w` 私聊或 token 注入主动推送和长期记忆。

## 已完成

- `warframe_agent/monitor.py`
  - 新增主动推送质量排序阈值：`PUSH_QUALITY_HISTORY_LIMIT`、`PUSH_QUALITY_MIN_SENT_COUNT`、`PUSH_QUALITY_MIN_REVIEWED_COUNT`。
  - 新增 `_apply_push_quality_to_suggestions(...)`，在 `_run_proactive_push(...)` 的 `high_priority` 生成后读取 `TradingMemoryDB.summarize_push_quality(...)`。
  - 新增质量 lookup 和 hint helpers，把 `PushQualitySignal` 转成 `push_quality_score=-1/0/1`。
  - 只在相同 `priority` 的建议之间稳定重排；不跨 priority 移动，不过滤机会，不改 Scout、mod flip、set profit、goal plan 的核心排序。
  - 新增安全 metadata 白名单字段：`push_quality_score`、`push_quality_reason`、`push_quality_reviewed_count`、`push_quality_good_rate`、`push_quality_false_positive_rate`。

- `tests/test_proactive_push.py`
  - 新增 `_seed_push_quality(...)` 测试 helper，用真实 `push_history` 和 `opportunity_outcomes` 构造好/坏质量样本。
  - 覆盖“足够样本时同优先级高质量机会排前面，低质量机会仍会发送”。
  - 覆盖“低样本历史保持原始顺序，不写入质量分”。
  - 覆盖质量 metadata 不泄露历史中的玩家名、warframe.market 链接、profile、whisper 和 `/w`。

## 行为边界

- 无历史或低样本：保持中性，不加权。
- 高质量历史：同优先级内轻微前移。
- 低质量历史：同优先级内轻微后移，但仍允许发送。
- 用户偏好过滤、`push_proactive` 开关、机会冷却去重、物品类别过滤仍是硬约束。
- 推送质量只使用聚合统计，不回读 raw metadata 给用户或模型。

## 准备继续学习的清单

- 观察 `push_quality_score` 是否需要进一步拆成 `source` 级和 `strategy` 级两层，避免某个物品样本太少时完全没有参考。
- 观察 `pending_count` 是否能提示“还没有足够复盘”，避免用户把未复盘误解为低质量。
- 后续如果要接入 Web UI，应展示聚合质量 badge，而不是展示 raw 历史记录。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_proactive_push.py -k "push_quality" --basetemp .pytest-tmp -p no:cacheprovider
# RED: 1 failed, 1 passed, 23 deselected
# GREEN: 2 passed, 23 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_proactive_push.py -k "not scan_cycle" --basetemp .pytest-tmp -p no:cacheprovider
# 24 passed, 1 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_trading_memory.py -k "push_quality or opportunity_outcome" --basetemp .pytest-tmp -p no:cacheprovider
# 6 passed, 14 deselected

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```

`git diff --check` 对本步相关文件退出码为 0，仅提示 `monitor.py` 和 `test_proactive_push.py` 下次 Git 触碰时 LF 会替换为 CRLF。
