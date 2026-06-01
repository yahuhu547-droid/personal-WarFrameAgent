# Step 22：自然语言价格提醒

## 本次借鉴点

- `/alert add 充沛 below 45` 这类命令适合保留为底层入口，但普通用户更自然的说法是“充沛低于45p提醒我”。
- 价格提醒属于写记忆、触发未来推送的轻量动作，可以自然语言直接创建；但解析必须保守，避免普通价格问题被误判成提醒。
- 最小可靠条件是同时出现：提醒词、方向词和价格数字。

## 已完成

- `warframe_agent/chat.py`
  - 新增 `PriceAlertIntent` 和 `_parse_natural_language_price_alert(...)`。
  - 支持“充沛低于45p提醒我”“充沛高于100p通知我”。
  - 支持“取消充沛低于45p提醒”移除对应提醒。
  - `answer(...)` 和 `answer_stream(...)` 都在通用物品路由前处理该意图。
  - 复用 `AgentMemory.with_price_alert(...)` 和 `without_price_alert(...)`，不新增存储结构。
- `tests/test_chat_memory_commands.py`
  - 覆盖低于提醒、高于提醒、取消提醒、流式回答一致性、普通价格问题不误创建和模糊取消不误删。

## 避免误触发的规则

- 仅有价格方向不触发，例如“充沛低于45p了吗”不会创建提醒。
- 没有价格数字不触发，例如“充沛便宜了提醒我”暂不处理。
- 没有方向词不触发，例如“提醒我看充沛”暂不处理。

## 后续可继续

- `/fav add/remove` 自然语言化，例如“帮我关注充沛”“取消关注充沛”。
- `/pref` 自然语言偏好更新，例如“我偏低风险，预算30到150p”。
- `/review done` 自然语言机会复盘，但需要确认实际利润和反馈。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_price_alert or natural_language_price_question" -q --basetemp .pytest-tmp -p no:cacheprovider
# 4 passed, 21 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_price_alert or natural_language_price_question or vague_cancel or add_alert" -q --basetemp .pytest-tmp -p no:cacheprovider
# 7 passed, 20 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
# 27 passed

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```
