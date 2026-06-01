# Step 26：自然语言交易复盘确认

## 本次借鉴点

- `/review done OPID 实际利润 feedback` 是稳定显式命令，但用户更自然的说法是“OP8K3A2Q 实际赚45p，结果不错，帮我复盘”。
- 交易复盘会写入长期交易记忆，影响后续个人画像和机会质量评估，所以自然语言入口必须先确认，不直接写库。
- `OpportunityLookupStore` 是短期机会详情库，可能包含操作细节；长期 `TradingMemoryDB` 只应保存 safe summary。自然语言确认后复用原来的 `/review done` 写入路径，避免绕开安全清洗。

## 已完成

- `warframe_agent/chat.py`
  - 新增 `ReviewDoneIntent` 与 `PendingReviewDoneConfirmation`。
  - 新增 `_parse_natural_language_review_done(...)`，要求同时出现有效 OPID 和实际利润。
  - 支持“实际赚45p”“实际亏5p”“实际利润 0p”等利润表达。
  - 支持中文反馈归一：不错/顺利/成功 -> `good`；亏/失败/不好 -> `bad`；没做/跳过/忽略 -> `ignored`；一般/持平 -> `neutral`。
  - 新增 `_try_review_done_intent(...)` 生成确认提示。
  - 新增 `_try_review_done_confirmation_response(...)`，用户回复“确认复盘/确认记录/确认”后才写入。
  - 确认写入复用 `_handle_review_record_command([lookup_id, profit, feedback])`。
- `tests/test_chat_memory_commands.py`
  - 覆盖自然语言复盘确认前不写库。
  - 覆盖确认后写入 completed opportunity outcome。
  - 覆盖取消后不写库。
  - 覆盖 `answer_stream(...)` 一致。
  - 覆盖缺 OPID、缺有效利润、普通市场聊天不创建 pending。
  - 保留显式 `/review done OPID 45 good` 即时写入回归。

## 避免误触发的规则

- 必须有有效 `OP[A-Z0-9]{6}` 机会 ID。
- 必须有实际利润整数；“实际赚很多”不触发。
- 问句、教程、计划文本不触发，例如“/review done 怎么用？”。
- 只有 `确认复盘/确认记录/确认` 等确认词才会写入；普通聊天不会误确认。
- 写入长期记忆时仍由原 `/review done` 路径抽取 safe summary，不保存 `/w`、profile、玩家名等敏感细节。

## 后续可继续

- `/fissure add/remove` 自然语言裂缝订阅确认。
- `review done` 可以进一步支持“没成交/跳过”映射为 skipped 状态，但需要先确定产品语义。
- 可为自然语言复盘增加“备注原因”字段，不过需要新的安全化存储策略。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "review_done_natural_language" -q --basetemp .pytest-tmp -p no:cacheprovider
# 5 passed, 45 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "review_done_natural_language or review_done_command" -q --basetemp .pytest-tmp -p no:cacheprovider
# 8 passed, 42 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
# 50 passed

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```
