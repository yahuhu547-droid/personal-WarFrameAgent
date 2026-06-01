# Step 24：自然语言偏好更新

## 本次借鉴点

- `/pref risk low`、`/pref budget 30-150` 适合作为底层稳定命令，但个人 Agent 更自然的长期记忆入口是“我的预算300p，偏低风险，最低利润15%”。
- 偏好写入会影响后续投资建议、主动机会筛选和个人画像，所以必须比收藏/价格提醒更保守：只识别带有“我的、偏好、设置、以后、平台、跨平台、最多显示”等写入锚点的句子。
- 一次性问题不能写成长久偏好，例如“300p预算买什么好”“我预算300p够吗”“低风险倒卖推荐”应继续走普通问答或交易工具。

## 已完成

- `warframe_agent/chat.py`
  - 新增 `PreferenceIntent` 和 `_parse_natural_language_preference(...)`。
  - 支持预算：`预算300p`、`预算30到150p`。
  - 支持风险：低风险/保守/稳健、中风险/均衡、高风险/激进。
  - 支持最低 ROI/利润、最长周转、偏好品类、平台、跨平台和最大结果数。
  - `answer(...)` 与 `answer_stream(...)` 都在价格提醒和收藏之后处理偏好写入。
  - 复用 `AgentMemory.with_updated_preferences(...)` 和原有持久化路径。
- `tests/test_chat_memory_commands.py`
  - 覆盖预算+风险+最低 ROI。
  - 覆盖品类+最长周转。
  - 覆盖平台+跨平台+最大结果数。
  - 覆盖流式回答。
  - 覆盖普通问题、价格提醒、收藏和交易机会过滤不被偏好入口抢走。

## 避免误触发的规则

- 价格提醒优先，例如“充沛低于45p提醒我”只创建价格提醒，不改预算。
- 收藏优先，例如“帮我收藏充沛”只写收藏，不改偏好品类。
- 交易机会控制优先，例如“交易机会只检测MOD”只改 `opportunity_filter`。
- 疑问句和一次性投资问题不写偏好，例如“300p预算买什么好”。
- 规划类句子暂不写偏好，例如“帮我制定一周赚500p计划，预算300p，低风险”，避免目标规划和长期偏好混在一起。

## 后续可继续

- `/goal done/drop` 自然语言完成或放弃目标，需要确认目标对象。
- `/review done` 自然语言交易复盘，需要确认实际利润、结果好坏和机会 ID。
- `/fissure add/remove` 自然语言订阅裂缝提醒，适合复用确认式写入。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_preference" -q --basetemp .pytest-tmp -p no:cacheprovider
# 5 passed, 33 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_preference or profile_pref" -q --basetemp .pytest-tmp -p no:cacheprovider
# 7 passed, 31 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
# 38 passed

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```
