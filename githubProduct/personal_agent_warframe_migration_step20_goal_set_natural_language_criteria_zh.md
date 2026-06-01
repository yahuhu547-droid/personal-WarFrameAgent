# Step 20：`/goal set` 自然语言目标解析

## 本次借鉴点

- 个人 Agent 的“目标创建”不能只存一句原文。显式命令 `/goal set 一周赚500p，预算300p，低风险，最低ROI 20%` 应落成可执行的结构化条件，供后续计划、进度和复盘使用。
- 目标解析适合做成确定性纯函数，先覆盖常见中文交易目标表达；不要把一次目标创建交给 LLM 自由解释，也不要让自然语言 planning 自动创建目标。
- Slash 命令的测试要 fake `GoalTracker`，避免默认 `data/goals.json` 被测试污染。

## 已完成

- `warframe_agent/goals.py`
  - 新增 `parse_goal_description_criteria(...)`，解析目标利润、周期、预算、风险和最低 ROI。
  - 新增 `format_goal_criteria_summary(...)`，把保存前的结构化条件转成用户可读摘要。
  - 支持中文数字和常见周期表达，例如 `一周`、`三天`、`一个月`。
- `warframe_agent/chat.py`
  - `/goal set|add|新建` 改为使用目标解析结果。
  - 明确收益目标时创建 `earn_platinum`；普通描述继续创建 `maximize_profit`，保留旧默认 `budget=500/min_roi=10`。
  - 回执中追加“已解析”摘要，帮助用户确认 Agent 理解是否正确。
- `tests/test_chat_memory_commands.py`
  - 覆盖 `/goal set 一周赚500p，预算300p，低风险，最低ROI 20%` 的命令集成。
  - 覆盖普通描述仍走旧类型和旧默认。
- `tests/test_goals.py`
  - 覆盖中文数字、周期、风险别名、ROI 顺序和摘要格式。

## 准备学习的清单

- 可以继续学习“确认式目标创建”：自然语言 planning 给草案，用户确认后再调用 `/goal set` 或目标创建 API。
- 可以把解析 helper 复用到 Web/API 目标创建入口，减少聊天端和网页端能力不一致。
- 可以把 Step 17 的推送质量聚合、个人偏好预算和风险偏好接入目标默认值，但仍保持显式覆盖优先。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
# 18 passed

.\.venv\Scripts\python.exe -m pytest tests\test_goals.py -q --basetemp .pytest-tmp -p no:cacheprovider
# 20 passed

.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "planning_mode or chat_mode or direct_market_intent or bilibili_video_words" -q --basetemp .pytest-tmp -p no:cacheprovider
# 6 passed, 63 deselected

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```

## 后续可继续

- Web/API 目标创建入口复用 `parse_goal_description_criteria(...)`。
- `/goal` 状态展示增加 criteria 摘要，而不只展示 description。
- 用目标 criteria 反向生成更细的执行步骤，例如预算分配、每天收益节奏和风险上限。
