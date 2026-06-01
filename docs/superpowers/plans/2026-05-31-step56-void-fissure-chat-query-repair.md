# Step 56 Void Fissure Chat Query Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复聊天中“虚空裂缝 / 裂隙 / 裂缝”提问返回内容缺少或不符的问题，尤其是带筛选词时不能返回全部裂缝。

**Architecture:** 保持现有 `ChatAgent + EventTracker` 主链路不变。只在 `void_fissure` 事件查询中使用已有结构化 `VoidFissure` 数据做过滤和格式化；其他事件类型继续走 `format_events_for_display(...)`。

**Tech Stack:** Python, pytest, Markdown, UTF-8.

---

## Root Cause

- 当前“虚空裂缝”聊天问法会进入 `_handle_specific_event_query(...)`，再调用 `_query_events_result(event_type="void_fissure")`。
- `_query_events_result(...)` 只从 `get_active_events()` 取得 `GameEvent.description` 并格式化，无法根据用户消息里的 `古纪 / 后纪 / 钢铁 / 普通 / 捕获 / 生存` 等筛选词过滤。
- 复现样例：`古纪裂缝有哪些` 和 `钢铁后纪裂缝有哪些` 当前会返回全部裂缝，包含不匹配的纪元和模式。
- 展示内容只来自一句 description，缺少结构化到期时间等详情。

## Completion Criteria

- `现在有什么虚空裂缝` 返回 `当前虚空裂缝/裂隙:`，包含裂缝详情，不返回 `当前限时活动`、`兽之腹`、`热美亚裂缝`。
- `古纪裂缝有哪些` 只返回古纪 / Lith 裂缝，不返回后纪 / Axi。
- `钢铁后纪裂缝有哪些` 只返回钢铁后纪裂缝，不返回普通古纪裂缝。
- `裂隙任务有哪些` 继续可用。
- `现在有什么活动` 继续只返回运营限时活动，不混入虚空裂缝。
- `query_events(type="void_fissure")` 仍可不带筛选返回全部当前裂缝。

## Files

- Modify: `tests/test_chat.py`
  - 增加聊天层回归测试，覆盖普通裂缝问法、筛选问法和不混限时活动。
- Modify: `warframe_agent/chat.py`
  - `_query_events_result(...)` 增加 `source_query` 可选参数。
  - `_handle_specific_event_query(...)` 把原始 message 传给裂缝专用查询。
  - 新增或局部实现裂缝筛选与格式化 helper。
- Create: `githubProduct/personal_agent_warframe_migration_step56_void_fissure_query_repair_zh.md`
  - 记录问题、修复、验证和后续注意事项。
- Modify: `AGENTS.md`
  - 追加 Step 56 进度、状态、影响范围和验证摘要。
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - 同步 Step 56 项目质量修复记录。
- Modify: `md/rebuilt/10-learning-route-audit.md`
  - 同步 Step 56 不属于旧学习路线重启的说明。

---

### Task 1: Add Failing Chat Regression Tests

**Files:**
- Modify: `tests/test_chat.py`

- [x] **Step 1: Add a fixture-style world state inside chat event tests**

Use the existing `EventTracker` pattern near `test_specific_fissure_query_still_returns_fissures`.

```python
def test_void_fissure_query_filters_by_tier_and_mode():
    tracker = EventTracker()
    tracker._last_fetch = 9999999999.0
    tracker._world_state = {
        "Goals": [{"Tag": "JadeShadowsEvent", "Node": "SolNode723"}],
        "ActiveMissions": [
            {
                "Modifier": "VoidT1",
                "MissionType": "MT_CAPTURE",
                "Node": "SolNode1",
                "Expiry": "1777921200000",
            },
            {
                "Modifier": "VoidT4",
                "MissionType": "MT_SURVIVAL",
                "Node": "SolNode742",
                "Hard": True,
                "Expiry": "1777924800000",
            },
        ],
    }
    tracker._events = tracker.parse_events(tracker._world_state)
    agent = ChatAgent(event_tracker=tracker, model_call=lambda prompt: "unused")

    lith = agent.answer("古纪裂缝有哪些")
    steel_axi = agent.answer("钢铁后纪裂缝有哪些")

    assert "当前虚空裂缝/裂隙" in lith
    assert "古纪 (Lith)" in lith
    assert "捕获" in lith
    assert "地球 - E Prime" in lith
    assert "后纪 (Axi)" not in lith
    assert "钢铁" not in lith

    assert "当前虚空裂缝/裂隙" in steel_axi
    assert "后纪 (Axi)" in steel_axi
    assert "生存" in steel_axi
    assert "钢铁" in steel_axi
    assert "虚空 - Mot" in steel_axi
    assert "古纪 (Lith)" not in steel_axi
```

- [x] **Step 2: Add a non-mixing and detail test**

```python
def test_void_fissure_query_returns_structured_details_without_limited_events():
    tracker = EventTracker()
    tracker._last_fetch = 9999999999.0
    tracker._world_state = {
        "Goals": [
            {"Tag": "JadeShadowsEvent", "Node": "SolNode723"},
            {"Tag": "ThermiaFractures", "Node": "VenusHUB"},
        ],
        "ActiveMissions": [
            {
                "Modifier": "VoidT4",
                "MissionType": "MT_SURVIVAL",
                "Node": "SolNode742",
                "Hard": True,
                "Expiry": "1777924800000",
            },
        ],
    }
    tracker._events = tracker.parse_events(tracker._world_state)
    agent = ChatAgent(event_tracker=tracker, model_call=lambda prompt: "unused")

    answer = agent.answer("现在有什么虚空裂缝")

    assert "当前虚空裂缝/裂隙" in answer
    assert "后纪 (Axi)" in answer
    assert "生存" in answer
    assert "钢铁" in answer
    assert "虚空 - Mot" in answer
    assert "结束:" in answer
    assert "当前限时活动" not in answer
    assert "兽之腹" not in answer
    assert "热美亚裂缝" not in answer
```

- [x] **Step 3: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "void_fissure_query_filters_by_tier_and_mode or void_fissure_query_returns_structured_details_without_limited_events" -q --basetemp .pytest-tmp-step56-red -p no:cacheprovider
```

Expected before implementation:

```txt
2 failed
```

At least one failure must prove filtered questions still include non-matching fissures or lack structured detail.

---

### Task 2: Implement Structured Void Fissure Chat Formatting

**Files:**
- Modify: `warframe_agent/chat.py`

- [x] **Step 1: Pass source query into event result**

Change `_tool_query_events` and `_handle_specific_event_query` to use an optional `source_query`:

```python
display, model_context = self._query_events_result(event_type=event_type, source_query=args.get("__message"))
```

```python
display, _ = self._query_events_result(
    event_type=_event_type_from_message(message) or message,
    source_query=message,
)
```

- [x] **Step 2: Add void fissure specialized branch**

Inside `_query_events_result(...)`, after normalizing event type and support checking:

```python
if normalized_type == "void_fissure":
    try:
        tracker = self.event_tracker or EventTracker()
        if not self.event_tracker:
            tracker.load_cache()
        fissures = tracker.get_active_fissures()
    except Exception as exc:
        logger.debug("虚空裂缝查询失败: %s", exc)
        fissures = []
    if fissures:
        display = _format_void_fissures_for_chat(fissures, source_query)
        model_context = _format_void_fissures_for_model(fissures, source_query)
        return display, model_context
```

If there are no structured fissures, fall back to current `get_active_events() + format_events_for_display(...)`.

- [x] **Step 3: Add filter and formatter helpers**

Helpers should be module-level in `chat.py` near other event helper functions:

```python
def _filter_void_fissures_for_query(fissures, query: str | None):
    ...

def _format_void_fissures_for_chat(fissures, query: str | None = None) -> str:
    selected = _filter_void_fissures_for_query(fissures, query)
    lines = ["当前虚空裂缝/裂隙:"]
    if not selected:
        return "\n".join([lines[0], "暂无匹配裂缝。"])
    for fissure in selected[:20]:
        mode = "钢铁" if fissure.hard else "普通"
        line = f"- {fissure.tier_display} {fissure.mission_display} {mode} @ {fissure.node_display}"
        if fissure.expiry:
            line += f" | 结束: {_format_worldstate_time(fissure.expiry)}"
        lines.append(line)
    return "\n".join(lines)
```

Filtering rules:

- tier aliases:
  - `古纪` / `lith` -> `VoidT1`
  - `前纪` / `meso` -> `VoidT2`
  - `中纪` / `neo` -> `VoidT3`
  - `后纪` / `axi` -> `VoidT4`
  - `遗珍` / `requiem` -> `VoidT5`
  - `仲裁` / `arbitration` -> `VoidT6`
- mode:
  - `钢铁` / `steel` / `steel path` -> `hard=True`
  - `普通` / `normal` -> `hard=False`
- mission display or raw mission type text should filter when present, for example `捕获` or `MT_CAPTURE`。
- no filters means return all.

- [x] **Step 4: Run green tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "activity_query_returns_only_limited_events or specific_fissure_query_still_returns_fissures or void_fissure_query" -q --basetemp .pytest-tmp-step56-chat -p no:cacheprovider
```

Expected:

```txt
4 passed
```

---

### Task 3: Broaden Verification

**Files:**
- No code change expected.

- [x] **Step 1: Run event formatting tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_events.py -k "limited or void_fissure or query_event_type or format_events_for_display" -q --basetemp .pytest-tmp-step56-events -p no:cacheprovider
```

Expected: all selected tests pass.

- [x] **Step 2: Run router event candidate tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_tool_router.py -k "event or farming_route" -q --basetemp .pytest-tmp-step56-router -p no:cacheprovider
```

Expected: all selected tests pass.

- [x] **Step 3: Run syntax and diff checks**

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/events.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\chat.py tests\test_chat.py docs\superpowers\plans\2026-05-31-step56-void-fissure-chat-query-repair.md githubProduct\personal_agent_warframe_migration_step56_void_fissure_query_repair_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

Expected: `AST OK`; `git diff --check` exit code 0, allowing only LF/CRLF conversion warnings.

---

### Task 4: Document Step 56

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step56_void_fissure_query_repair_zh.md`
- Modify: `AGENTS.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`

- [x] **Step 1: Write report**

Report must include:

- 复现问题。
- 根因。
- 修复范围。
- 用户可见结果。
- 验证命令与结果。
- 安全边界：不上传 GitHub、不安装依赖、不下载文件、不启用高权限 runtime。

- [x] **Step 2: Update AGENTS and rebuilt docs**

Append Step 56 with:

```markdown
## 2026-05-31 Step 56：虚空裂缝聊天查询修复

| 日期 | 任务 | 进度 | 状态 | 说明 |
| --- | --- | ---: | --- | --- |
| 2026-05-31 | Step 56 虚空裂缝聊天查询修复 | 100% | 已完成 | 已修复裂缝聊天问法的筛选和详情展示，普通活动查询仍不混裂缝。 |
```

- [x] **Step 3: Final verification after docs**

Re-run the targeted chat command and `git diff --check` from Task 3.
