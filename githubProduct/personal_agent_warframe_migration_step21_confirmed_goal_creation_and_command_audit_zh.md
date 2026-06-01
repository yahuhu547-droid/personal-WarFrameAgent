# Step 21：确认式目标创建与命令式入口审计

## 本次借鉴点

- Slash Command 适合做安全底层入口，但不应该成为普通用户和个人 Agent 对话的主要方式。
- 会持久化、会触发推送、会记录交易的动作，适合采用“自然语言解析 -> 结构化预览 -> 用户确认 -> 内部执行”的模式。
- 只读查询可以更大胆地自然语言化；写状态的动作要保留确认或明确命令兜底。

## 已完成

- `warframe_agent/chat.py`
  - 新增内存态 `PendingGoalConfirmation`。
  - 自然语言 planning 在识别到可追踪目标后，会展示解析摘要并询问是否创建。
  - 用户回复 `确认创建/确认/可以/好的` 后，才会创建 `GoalTracker` 目标。
  - 用户回复 `取消/不创建/算了` 会清除待确认目标。
  - `/goal set ...` 仍保留，并和确认创建共用同一套 `_create_goal_from_description(...)`。
- `tests/test_chat_memory_commands.py`
  - 覆盖 planning 不直接创建目标。
  - 覆盖确认后创建解析后的 `earn_platinum` 目标。
  - 覆盖取消后不会误创建目标。

## 项目中仍偏命令式的入口

### 已有自然语言桥，风险较低

- `/push opportunity off|on|filter ...`
  - 已有 `_try_opportunity_control(...)` 支持“暂停交易机会推送”“只检测赋能”等自然语言。
- `/cycle status/add ...`
  - 已有 `_try_cycle_intent(...)` 支持“地球现在黑夜吗”“金星变冷提醒我”。
- `/trade add ...`
  - 已有 `_auto_record_trade(...)` 从“我买了/卖了某物 xxp”自动记录一部分已完成交易。
- `/opp OPID`
  - 已支持直接输入机会 ID，不一定要带 `/opp`。

### 适合下一批自然语言化

- `/fav add/remove 物品名`
  - 用户自然说“帮我关注充沛”“取消关注充沛”即可。
  - 写记忆，但风险较低，可直接执行并返回撤销提示。
- `/alert add/remove 物品名 below/above 价格`
  - 用户自然说“充沛低于45p提醒我”。
  - 写提醒，建议解析后直接创建，必要时展示“已添加提醒”。
- `/pref risk/budget/categories/min_roi ...`
  - 用户自然说“我偏低风险，预算 30 到 150p，最低 ROI 25%”。
  - 会影响推荐策略，建议先摘要确认，或至少返回变更明细。
- `/goal done/drop/rm/review ID`
  - 用户自然说“完成 abc123 这个目标”“放弃这个目标”。
  - 会改变目标状态，建议确认。

### 高风险或更适合保留命令兜底

- `/review done OPID 实际利润 feedback`
  - 写入长期交易复盘，会影响个人画像和推荐评分。建议做自然语言解析，但必须展示 OP、实际利润和反馈确认。
- `/fissure add/remove ...`
  - 会创建/删除推送订阅。建议支持“虚空歼灭裂缝提醒我”，但删除仍优先走列表编号或确认。
- `/strategy run 策略名`
  - 会触发扫描，通常只读但可能耗时。可自然语言化为“跑一下低风险策略”。
- `/trade undo`
  - 删除最近交易记录。建议保留命令或增加明确确认。

### 只读命令，优先级较低

- `/memory`、`/profile`、`/scan`、`/trade list/stats`、`/goal`、`/relic`、`/strategy list`、`/vault`
  - 这些可以继续保留命令，同时支持自然语言问法即可，不需要确认。

## 后续建议顺序

1. `/alert` 自然语言创建价格提醒。
2. `/fav` 自然语言关注/取消关注。
3. `/pref` 自然语言偏好更新，带变更摘要。
4. `/review done` 自然语言机会复盘，带确认。
5. `/goal done/drop` 自然语言目标状态变更，带确认。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "goal_confirmation" -q --basetemp .pytest-tmp -p no:cacheprovider
# 3 passed, 18 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "goal_confirmation or goal_set" -q --basetemp .pytest-tmp -p no:cacheprovider
# 7 passed, 14 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
# 21 passed

.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "planning_mode" -q --basetemp .pytest-tmp -p no:cacheprovider
# 2 passed, 67 deselected

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```
