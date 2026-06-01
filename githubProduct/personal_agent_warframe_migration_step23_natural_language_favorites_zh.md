# Step 23：自然语言收藏关注

## 本次借鉴点

- `/fav add/remove` 适合作为底层稳定命令，但用户和个人 Agent 聊天时更自然的表达是“帮我关注充沛”“帮我收藏充沛”“取消关注充沛”。
- 收藏属于轻量记忆写入，不需要二次确认；但“关注列表”“扫描关注”“充沛值得关注吗”这类句子不能被误判成写收藏。
- 最小可靠规则是只识别强命令式收藏动作，并把解析入口放在价格提醒之后、普通问答之前。

## 已完成

- `warframe_agent/chat.py`
  - 新增 `FavoriteIntent` 和 `_parse_natural_language_favorite(...)`。
  - 支持“帮我关注/收藏 物品”和“取消关注/收藏 物品”。
  - `answer(...)` 与 `answer_stream(...)` 均接入同一逻辑。
  - 复用 `_handle_favorite_command([action, item_name])`，继续沿用 `AgentMemory.with_favorite_item(...)` 去重与 `without_favorite_item(...)` 移除。
- `tests/test_chat_memory_commands.py`
  - 覆盖自然语言添加、移除、流式回答、取消收藏同义句。
  - 覆盖“关注列表”“值得关注吗”“低于45p提醒我”不误加收藏。
  - 覆盖重复关注不会产生重复 `favorite_items`。

## 避免误触发的规则

- 精确关注列表命令仍走 `scan_watchlist()`，不进入收藏解析。
- 问句类表达不写记忆，例如“充沛值得关注吗”。
- 价格提醒表达优先进入价格提醒解析，例如“充沛低于45p提醒我”只创建价格提醒，不添加收藏。
- 交易机会推送、只看赋能/只检测 mod 等控制句不进入收藏解析。

## 后续可继续

- `/pref` 自然语言偏好更新，例如“我预算 300p，偏低风险，最低利润 15%”。
- `/goal done/drop` 自然语言完成或放弃目标，需要保留确认步骤。
- `/review done` 自然语言交易复盘，适合做“先解析、再确认”的写入流程。

## 验证记录

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_favorite" -q --basetemp .pytest-tmp -p no:cacheprovider
# 6 passed, 27 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "natural_language_favorite or favorite" -q --basetemp .pytest-tmp -p no:cacheprovider
# 7 passed, 26 deselected

.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -q --basetemp .pytest-tmp -p no:cacheprovider
# 33 passed

.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('warframe_agent').rglob('*.py')]"
# passed
```
