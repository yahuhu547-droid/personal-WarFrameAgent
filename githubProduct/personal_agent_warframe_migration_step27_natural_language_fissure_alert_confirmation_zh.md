# Step 27：自然语言裂缝提醒确认

## 本次借鉴点

- `/fissure add/remove` 是稳定的底层命令，但用户更自然的说法是“提醒我钢铁后纪歼灭裂缝”或“取消第1个裂缝提醒”。
- 裂缝提醒会写入长期记忆，并影响后续监控推送，所以自然语言入口必须先确认，不能因为一句查询或闲聊直接订阅。
- 已有 `_add_fissure_alert(...)` 和 `_remove_fissure_alert(...)` 已经包含字段解析、去重、序号校验和持久化，新的自然语言层只负责生成草案，不绕过原路径。

## 已完成

- `warframe_agent/chat.py`
  - 新增 `FissureAlertIntent` 与 `PendingFissureAlertConfirmation`。
  - 新增 `_parse_natural_language_fissure_alert(...)`，要求同时出现裂缝词和明确的订阅/取消动词。
  - 支持纪元、任务、地点、钢铁/普通过滤词，例如“后纪”“歼灭”“虚空”“钢铁”。
  - 支持按序号取消，例如“取消第1个裂缝提醒”。
  - 新增 `_try_fissure_alert_intent(...)`，自然语言请求只生成待确认提示。
  - 新增 `_try_fissure_alert_confirmation_response(...)`，用户回复“确认订阅”后调用 `_add_fissure_alert(tokens)`，回复“确认取消”后调用 `_remove_fissure_alert([index])`。
  - `answer(...)` 与 `answer_stream(...)` 走同一套确认逻辑。
- `tests/test_chat_memory_commands.py`
  - 覆盖确认前不写入。
  - 覆盖确认后写入 `FissureAlert`。
  - 覆盖取消 pending 后不写入。
  - 覆盖按序号取消订阅。
  - 覆盖 `answer_stream(...)` 一致性。
  - 覆盖“现在有什么裂缝”不会误订阅。
  - 覆盖显式 `/fissure add/remove` 仍立即执行。

## 避免误触发的规则

- 查询类不写入，例如“现在有什么裂缝”“当前虚空裂缝”“哪个裂缝适合开这个核桃”。
- 模糊取消不删除，例如“取消提醒”没有序号时不会删除任何裂缝订阅。
- `热美亚裂缝`、收益问题、刷取问题不进入虚空裂缝提醒订阅。
- 自然语言订阅至少要包含一个可解析过滤条件，避免“提醒我裂缝”这种太宽泛的写入。
- 显式 `/fissure add ...` 和 `/fissure remove 1` 仍保留为脚本、调试和精确操作入口。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "fissure_alert_natural_language" -q --basetemp .pytest-tmp -p no:cacheprovider
# RED: 5 failed, 1 passed, 50 deselected
# GREEN: 6 passed, 50 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "fissure_alert_natural_language or fissure_command" -q --basetemp .pytest-tmp -p no:cacheprovider
# 6 passed, 50 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
# 56 passed

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```

`git diff --check` 对本步相关文件退出码为 0，仅提示部分文件下次 Git 触碰时 LF 会替换为 CRLF。
