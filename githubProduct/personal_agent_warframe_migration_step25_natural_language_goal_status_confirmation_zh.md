# Step 25：自然语言目标完成/放弃确认

## 本次借鉴点

- `/goal done ID` 和 `/goal drop ID` 是稳定的显式命令，但用户更自然的说法是“完成第1个目标”“放弃第1个目标”。
- 目标状态变更比收藏和偏好更高风险：一旦写入 `achieved/abandoned`，会影响目标复盘和后续执行。因此自然语言入口必须先确认，不直接改状态。
- 自然语言只匹配活跃目标，并且必须能唯一定位：序号、目标 ID 前缀或描述片段。

## 已完成

- `warframe_agent/chat.py`
  - 新增 `GoalStatusIntent` 与 `PendingGoalStatusConfirmation`。
  - 新增 `_parse_natural_language_goal_status(...)`，支持完成/放弃目标动作。
  - 新增 `_try_goal_status_intent(...)`，生成待确认状态变更。
  - 新增 `_try_goal_status_confirmation_response(...)`，用户回复“确认完成/确认放弃/确认”后才写入。
  - `answer(...)` 与 `answer_stream(...)` 都在目标创建确认和 planning 之前处理目标状态确认，避免被 planning 抢走。
  - 确认完成后复用 `GoalTracker.update_goal_status(..., "achieved")` 和 `generate_review(...)`。
  - 确认放弃后复用 `GoalTracker.update_goal_status(..., "abandoned")`。
- `tests/test_chat_memory_commands.py`
  - 扩展 `FakeGoalTracker` 支持目标状态更新和复盘。
  - 覆盖自然语言完成先确认、不立即写状态。
  - 覆盖“确认完成”“确认放弃”“取消”。
  - 覆盖 `answer_stream(...)` 行为一致。
  - 覆盖疑问句不创建待确认状态。
  - 覆盖显式 `/goal done ID` 仍然立即执行。

## 避免误触发的规则

- “完成目标了吗”“目标怎么完成”这类问题不创建待确认状态。
- “完成后用 /review done ...”这类计划文本不创建待确认状态。
- “我完成了一笔交易”不进入目标状态更新，避免抢走交易记录路径。
- 自然语言目标状态更新只匹配活跃目标；未找到或多匹配时不写入。
- Slash 命令仍是显式入口，`/goal done ID` 和 `/goal drop ID` 不额外二次确认。

## 后续可继续

- `/review done` 自然语言交易复盘，需要确认机会 ID、实际利润和反馈。
- `/fissure add/remove` 自然语言订阅裂缝提醒，适合确认式写入。
- 目标状态自然语言可继续扩展描述片段、多匹配列表和中文序号十以上。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "goal_status" -q --basetemp .pytest-tmp -p no:cacheprovider
# 7 passed, 38 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "goal_status_confirmation or goal_confirmation or goal_set" -q --basetemp .pytest-tmp -p no:cacheprovider
# 12 passed, 33 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
# 45 passed

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```
