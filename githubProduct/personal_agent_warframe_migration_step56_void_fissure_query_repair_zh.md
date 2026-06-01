# Step 56：虚空裂缝聊天查询修复

## 任务背景

用户反馈“虚空裂缝”的提问仍有问题，返回内容存在缺少和不符合筛选的问题。

本步属于 Step 54 / Step 55 之后的项目质量修复，不是旧个人 Agent 学习借鉴路线重启。

## 复现问题

使用同一个 `EventTracker` world state 构造两个裂缝：

- 古纪 / Lith，捕获，普通，地球 - E Prime。
- 后纪 / Axi，生存，钢铁，虚空 - Mot。

修复前：

- `古纪裂缝有哪些` 会同时返回古纪和后纪裂缝。
- `钢铁后纪裂缝有哪些` 会同时返回普通古纪和钢铁后纪裂缝。
- `现在有什么虚空裂缝` 只展示 `GameEvent.description`，缺少结构化 `结束:` 等字段。

## 根因

聊天层的“虚空裂缝 / 裂隙 / 裂缝”问法虽然已经能进入 `void_fissure` 事件分支，但 `_query_events_result(...)` 只使用 `EventTracker.get_active_events()` 产出的 `GameEvent.description`。

这条路径无法读取用户原始问题里的筛选词，也没有使用项目已有的结构化 `VoidFissure` 数据，因此不能按 `古纪 / 后纪 / 钢铁 / 普通 / 捕获 / 生存` 等条件过滤。

## 修复内容

- `ChatAgent._query_events_result(...)` 新增 `source_query` 参数。
- `ChatAgent._handle_specific_event_query(...)` 把用户原始消息传入事件查询。
- `query_events` 工具在存在 `__message` 时也把原始消息传入事件查询。
- 当事件类型为 `void_fissure` 时，优先使用 `EventTracker.get_active_fissures()` 的结构化数据。
- 新增裂缝筛选：
  - 纪元：古纪 / Lith、前纪 / Meso、中纪 / Neo、后纪 / Axi、遗珍 / Requiem、仲裁 / Arbitration。
  - 模式：普通 / Normal、钢铁 / Steel / Steel Path。
  - 任务类型：捕获、生存、歼灭、防御、移动防御、间谍、拦截、挖掘、炼金、中断等。
- 新增裂缝展示：
  - `纪元 任务类型 普通/钢铁 @ 节点 | 结束: UTC 时间`。
- 如果结构化裂缝为空，仍回退到原有 `get_active_events() + format_events_for_display(...)`，保护旧缓存行为。

## 用户可见结果

- `现在有什么虚空裂缝` 返回当前裂缝列表和结束时间，不混入运营限时活动。
- `古纪裂缝有哪些` 只返回古纪裂缝。
- `钢铁后纪裂缝有哪些` 只返回钢铁后纪裂缝。
- `现在有什么活动` 继续只返回热美亚裂缝、兽之腹等运营限时活动，不混入虚空裂缝。

## 验证摘要

红测：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "void_fissure_query_filters_by_tier_and_mode or void_fissure_query_returns_structured_details_without_limited_events" -q --basetemp .pytest-tmp-step56-red -p no:cacheprovider
```

结果：`2 failed`，失败分别证明筛选不生效和缺少 `结束:` 详情。

绿测与回归：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "activity_query_returns_only_limited_events or specific_fissure_query_still_returns_fissures or void_fissure_query" -q --basetemp .pytest-tmp-step56-chat -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_events.py -k "limited or void_fissure or query_event_type or format_events_for_display" -q --basetemp .pytest-tmp-step56-events -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_tool_router.py -k "event or farming_route" -q --basetemp .pytest-tmp-step56-router -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "fissure_alert_natural_language" -q --basetemp .pytest-tmp-step56-fissure-alerts -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -q --basetemp .pytest-tmp-step56-chat-all -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_router.py::ReactLoopTests::test_chat_agent_react_query_events_uses_safe_compact_model_context -q --basetemp .pytest-tmp-step56-router-context -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/events.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
```

结果：

- 裂缝目标聊天回归：`4 passed, 72 deselected`。
- 事件格式化回归：`4 passed, 21 deselected`。
- ToolRouter 事件 / farming route 回归：`3 passed, 34 deselected`。
- 裂缝提醒自然语言守卫：`6 passed, 50 deselected`。
- `tests/test_chat.py` 全量：`76 passed`。
- ReAct query_events 安全上下文测试：`1 passed`。
- AST：`AST OK`。

手动样本验证：

```txt
现在有什么虚空裂缝
当前虚空裂缝/裂隙:
- 古纪 (Lith) 捕获 普通 @ 地球 - E Prime | 结束: 2026-05-04 19:00 UTC
- 后纪 (Axi) 生存 钢铁 @ 虚空 - Mot | 结束: 2026-05-04 20:00 UTC

古纪裂缝有哪些
当前虚空裂缝/裂隙:
- 古纪 (Lith) 捕获 普通 @ 地球 - E Prime | 结束: 2026-05-04 19:00 UTC

钢铁后纪裂缝有哪些
当前虚空裂缝/裂隙:
- 后纪 (Axi) 生存 钢铁 @ 虚空 - Mot | 结束: 2026-05-04 20:00 UTC
```

## 安全边界

- 未安装依赖。
- 未下载文件。
- 未上传 GitHub。
- 未新增 Browser / GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。
- 修改只影响聊天事件查询中的 `void_fissure` 专用展示与筛选，其他事件类型沿用原有格式化路径。

## 后续建议

- 如果用户希望进一步对齐 Web 裂隙面板，可以另开任务评估 `warframestat.us /pc/fissures` 与官方 worldState 数据源的差异，但这会涉及网络数据源策略，不属于本次最小修复。
