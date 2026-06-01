# Step 57 Event And Baro Response Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 系统体检活动、虚空商人、Prime 重生、入侵、虚空风暴、开放世界周期和不支持活动等用户回复，发现并修复“答非所问、内容缺少、混入错误类型、误导性措辞”的问题。

**Architecture:** 保持当前 `ChatAgent + EventTracker + baro.py + query_events` 主链路。先用用户问法矩阵补足回归测试；只有测试暴露真实问题时，才在最小位置修复对应回复，不重构事件系统。

**Tech Stack:** Python, pytest, Markdown, UTF-8.

---

## Current Baseline From Initial Inspection

已完成轻量摸底，暂未修改生产代码：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_baro.py -q --basetemp .pytest-tmp-step57-baro-scout -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "activity_query_returns_only_limited_events or chinese_activity_aliases_use_direct_event_answers or unsupported_activity_aliases_do_not_fall_through_to_item_lookup or resurgence" -q --basetemp .pytest-tmp-step57-events-scout -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_tool_router.py -k "baro or activity or unsupported_event" -q --basetemp .pytest-tmp-step57-router-scout -p no:cacheprovider
```

结果：

- Baro 现有测试：`11 passed`。
- 活动 / Prime 重生 / 不支持活动现有聊天测试：`7 passed, 69 deselected`。
- ToolRouter Baro / activity 相关测试：`2 passed, 35 deselected`。

手动样本观察：

- `现在有什么活动` 返回 `当前限时活动:`，只列热美亚裂缝 / 兽之腹等运营限时活动。
- `入侵有哪些` 返回 `当前入侵:`。
- `虚空风暴现在有吗` 返回 `当前虚空风暴:`。
- `Baro 来了吗` 返回 `当前虚空商人:`。
- `虚空商人mod价格` 返回 `## Baro Mod / 赋能价格`。
- `虚空商人带来了什么物品` 当前也返回 Mod / 赋能价格报告，需确认是否应明确“只展示可分析的 Mod / 赋能”。
- `给我第一个玩家链接` 在 Baro 查询后返回玩家订单，并把 session 历史保存为安全模型上下文。
- `午夜电波现在是什么` 返回“当前数据源暂不支持午夜电波查询，不会编造结果。”

## Risk Areas To Audit

1. **泛活动问法边界**
   - `现在有什么活动` 应继续只返回运营限时活动，不混入虚空裂缝、入侵、虚空风暴。
   - `当前游戏事件有哪些` / `现在有什么事件` 是否应返回全部事件，需要用测试锁定期望；若继续只返回限时活动，回复应避免让用户误以为已经覆盖所有事件。

2. **具体事件问法**
   - `入侵有哪些`、`虚空风暴现在有吗`、`当前 Prime 重生是谁`、`Baro 来了吗` 不应 fallback 到 `当前限时活动`。
   - 无数据时要明确 `暂无` 或 `当前没有检测到...`，不能走物品匹配或编造。

3. **虚空商人库存 / MOD / 赋能**
   - `虚空商人mod价格`、`虚空商人满级mod价格` 应返回 rank、杜卡德、最高买价、最低卖价。
   - `虚空商人带来了什么物品` 目前实际只展示可分析的 Mod / 赋能，可能和“物品”语义不完全一致；需要测试并决定是改文案还是补全库存展示。
   - `Baro 来了吗` 与 `虚空商人mod价格` 在无库存 / 未到来时的回复应一致且可理解。

4. **Baro 后续追问**
   - `给我第一个玩家链接`、`给我卖家链接`、`给我最高买价的玩家链接`、`给我前5个买家` 必须尊重买家 / 卖家 / 数量。
   - 模型上下文和 session 历史不能保存玩家名、profile 链接或 `/w` 私聊命令。

5. **不支持数据源**
   - 午夜电波、仲裁、突击、Darvo、扎里曼赏金等必须明确“不支持，不编造”，不能 fallback 到物品查询。

6. **跨意图优先级**
   - 市场价格、遗物收益、B 站视频、计划模式不应被 `活动 / Baro / 裂缝` 关键词误抢。
   - `热美亚裂缝` 是运营活动，不应被误当成虚空裂缝或裂缝订阅。

---

### Task 1: Build Event Reply Matrix Tests

**Files:**
- Create: `tests/test_chat_event_replies.py`

- [x] **Step 1: Create shared fixtures**

Create a small fake tracker with limited events, Baro, invasion, void storm, Prime resurgence and cycles. Keep it self-contained; do not import private fixtures from other test files.

```python
from __future__ import annotations

from pathlib import Path

from warframe_agent.chat import ChatAgent
from warframe_agent.events import BaroItem, EventTracker, GameEvent, PrimeResurgenceItem, PrimeResurgenceRotation


def _orders(item_id: str) -> list[dict]:
    if item_id == "primed_flow":
        return [
            {"type": "sell", "platinum": 95, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "SellerR10", "status": "ingame", "reputation": 4}},
            {"type": "buy", "platinum": 80, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "BuyerR10", "status": "ingame", "reputation": 3}},
        ]
    if item_id == "arcane_test":
        return [
            {"type": "sell", "platinum": 7, "quantity": 21, "rank": 0, "user": {"ingameName": "ArcSeller", "status": "ingame", "reputation": 5}},
        ]
    return []


def _item_info(item_id: str) -> dict | None:
    return {
        "primed_flow": {"type": "mod", "max_rank": 10},
        "arcane_test": {"type": "arcane", "max_rank": 5},
    }.get(item_id)


class EventReplyTracker:
    def __init__(self):
        self._base = EventTracker()
        self._world_state = {
            "Goals": [
                {"Tag": "JadeShadowsEvent", "Node": "SolNode723"},
                {"Tag": "ThermiaFractures", "Node": "VenusHUB"},
            ],
            "ActiveMissions": [
                {"Modifier": "VoidT1", "MissionType": "MT_CAPTURE", "Node": "SolNode1", "Expiry": "1777921200000"},
            ],
            "VoidStorms": [{"Node": "CrewBattleNode1"}],
            "Invasions": [{"Completed": False, "LocTag": "/Lotus/Language/Menu/CorpusInvasionGeneric"}],
        }
        self._events = self._base.parse_events(self._world_state)
        self._events.append(
            GameEvent(
                event_type="baro_visit",
                description="Baro Ki'Teer 来访 @ Strata Relay，库存 2 件物品",
                baro_items=[
                    BaroItem("/Lotus/Upgrades/Mods/PrimedFlow", "Primed Flow", "primed_flow", 350, 110000),
                    BaroItem("/Lotus/Powersuits/Operator/ArcaneTest", "Arcane Test", "arcane_test", 500, 200000),
                ],
            )
        )
        self._events.append(
            GameEvent(
                event_type="prime_resurgence",
                description="Prime 重生: Rhino Prime + Nyx Prime",
                prime_resurgence=PrimeResurgenceRotation(
                    featured_names=["Rhino Prime", "Nyx Prime"],
                    end_time="2026-06-11 18:00 UTC",
                    items=[
                        PrimeResurgenceItem("/Lotus/StoreItems/Powersuits/Rhino/RhinoPrime", "Rhino Prime", "rhino_prime_set", 3, 0),
                        PrimeResurgenceItem("/Lotus/StoreItems/Powersuits/Nyx/NyxPrime", "Nyx Prime", "nyx_prime_set", 3, 0),
                    ],
                ),
            )
        )

    def get_active_events(self):
        return list(self._events)

    def get_limited_events(self):
        return self._base.parse_limited_events(self._world_state)

    def get_active_fissures(self):
        return self._base.parse_fissures(self._world_state)


def _agent(tmp_path: Path) -> ChatAgent:
    agent = ChatAgent(
        event_tracker=EventReplyTracker(),
        order_fetcher=_orders,
        model_call=lambda prompt: "unused",
        memory_path=tmp_path / "memory.json",
    )
    agent._baro_item_info_lookup = _item_info
    return agent
```

- [x] **Step 2: Add generic activity and specific event tests**

```python
def test_generic_activity_reply_does_not_mix_specific_events(tmp_path):
    answer = _agent(tmp_path).answer("现在有什么活动")

    assert "当前限时活动" in answer
    assert "兽之腹" in answer
    assert "热美亚裂缝" in answer
    assert "当前虚空裂缝" not in answer
    assert "当前入侵" not in answer
    assert "当前虚空风暴" not in answer
    assert "当前虚空商人" not in answer


def test_specific_event_questions_do_not_fallback_to_limited_activity(tmp_path):
    agent = _agent(tmp_path)

    assert "当前入侵" in agent.answer("入侵有哪些")
    assert "Corpus 入侵" in agent.answer("入侵有哪些")
    assert "当前虚空风暴" in agent.answer("虚空风暴现在有吗")
    assert "当前虚空商人" in agent.answer("Baro 来了吗")
    assert "当前限时活动" not in agent.answer("Baro 来了吗")
```

- [x] **Step 3: Run baseline tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py -k "generic_activity or specific_event_questions" -q --basetemp .pytest-tmp-step57-event-matrix -p no:cacheprovider
```

Expected:

- If all pass, keep as guardrail.
- If any fail, stop and classify root cause before implementing.

---

### Task 2: Audit Baro User Replies And Ambiguous Inventory Wording

**Files:**
- Modify: `tests/test_chat_event_replies.py`
- Potentially modify: `warframe_agent/chat.py`
- Potentially modify: `warframe_agent/baro.py`

- [x] **Step 1: Add Baro price, inventory and no-inventory tests**

```python
def test_baro_mod_price_reply_contains_rank_prices_and_no_raw_names(tmp_path, monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime", "arcane_test": "测试赋能"}.get(item_id))
    answer = _agent(tmp_path).answer("虚空商人满级mod价格")

    assert "## Baro Mod / 赋能价格" in answer
    assert "川流不息 Prime R10" in answer
    assert "杜卡德金币: 350" in answer
    assert "最高买价: 80p" in answer
    assert "最低卖价: 95p" in answer
    assert "Primed Flow" not in answer
    assert "BuyerR10" not in answer
    assert "/w " not in answer


def test_baro_inventory_wording_makes_scope_clear(tmp_path, monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime", "arcane_test": "测试赋能"}.get(item_id))
    answer = _agent(tmp_path).answer("虚空商人带来了什么物品")

    assert "Baro" in answer
    assert "Mod / 赋能" in answer
    assert "川流不息 Prime" in answer
    assert "测试赋能" in answer
    assert "仅" in answer or "可分析" in answer or "价格" in answer
```

This test intentionally checks whether the reply makes scope clear. If it passes only because the title says `Mod / 赋能价格`, keep it. If user-facing wording still feels misleading after review, implement the minimal copy change:

```python
lines = ["## Baro Mod / 赋能价格", "仅展示可分析的 Mod / 赋能；装饰、外观等非交易项暂不做价格分析。"]
```

- [x] **Step 2: Add no active Baro cases**

```python
class EmptyEventTracker:
    def get_active_events(self):
        return []

    def get_limited_events(self):
        return []


def test_baro_absent_replies_are_clear_and_do_not_fall_through(tmp_path):
    agent = ChatAgent(event_tracker=EmptyEventTracker(), model_call=lambda prompt: "unused", memory_path=tmp_path / "memory.json")

    status = agent.answer("Baro 来了吗")
    price = agent.answer("虚空商人mod价格")

    assert "当前虚空商人" in status or "当前没有" in status
    assert "当前没有" in price or "暂无" in price
    assert "没有找到匹配的物品" not in status + price
```

- [x] **Step 3: Run Baro reply tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py -k "baro" -q --basetemp .pytest-tmp-step57-baro-replies -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_baro.py -q --basetemp .pytest-tmp-step57-baro-existing -p no:cacheprovider
```

Expected: all pass after any minimal copy fix.

---

### Task 3: Audit Baro Follow-up Replies And Safe Context

**Files:**
- Modify: `tests/test_chat_event_replies.py`
- Potentially modify: `warframe_agent/baro.py`

- [x] **Step 1: Add buyer/seller follow-up tests**

```python
def test_baro_followup_respects_buyer_seller_and_count(tmp_path, monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime"}.get(item_id))
    agent = _agent(tmp_path)
    agent.answer("虚空商人满级mod价格")

    buyer = agent.answer("给我第一个买家链接")
    seller = agent.answer("给我第一个卖家链接")

    assert "买家 1. BuyerR10 | 80p" in buyer
    assert "卖家 1." not in buyer
    assert "卖家 1. SellerR10 | 95p" in seller
    assert "买家 1." not in seller


def test_baro_followup_session_history_remains_safe(tmp_path, monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime"}.get(item_id))
    agent = _agent(tmp_path)
    agent.answer("虚空商人满级mod价格")
    reply = agent.answer("给我第一个玩家链接")
    stored_reply = agent.session.history[-1][1]

    assert "BuyerR10" in reply
    assert "tool=baro_order_followup" in stored_reply
    for forbidden in ["BuyerR10", "SellerR10", "https://warframe.market/profile", "/w "]:
        assert forbidden not in stored_reply
```

- [x] **Step 2: Run follow-up tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py -k "baro_followup" -q --basetemp .pytest-tmp-step57-baro-followups -p no:cacheprovider
```

Expected: all pass. If seller/buyer ambiguity fails, adjust only `parse_order_detail_limits(...)` or `format_baro_order_details(...)` in `warframe_agent/baro.py`.

---

### Task 4: Audit Unsupported Event And Cross-Intent Routing

**Files:**
- Modify: `tests/test_chat_event_replies.py`
- Potentially modify: `warframe_agent/chat.py`
- Potentially modify: `warframe_agent/events.py`

- [x] **Step 1: Add unsupported event tests**

```python
def test_unsupported_events_are_explicit_and_do_not_use_item_lookup(tmp_path):
    agent = _agent(tmp_path)
    for query, label in [
        ("午夜电波现在是什么", "午夜电波"),
        ("仲裁现在是什么", "仲裁"),
        ("突击任务", "突击"),
        ("Darvo 每日特惠", "每日特惠"),
        ("扎里曼赏金", "扎里曼"),
    ]:
        answer = agent.answer(query)
        assert f"当前数据源暂不支持{label}" in answer
        assert "不会编造结果" in answer
        assert "没有找到匹配的物品" not in answer
```

- [x] **Step 2: Add cross-intent guardrail tests**

```python
def test_event_keywords_do_not_hijack_market_relic_or_video_intents(tmp_path):
    agent = _agent(tmp_path)
    agent._try_router_result = lambda message, candidate_tools=None: "ROUTED_RELIC" if candidate_tools else None

    relic = agent.answer("这个遗物收益怎么样，最近有什么活动影响吗")
    activity = agent.answer("热美亚裂缝现在有吗")

    assert relic == "ROUTED_RELIC" or "期望" in relic or "暂时无法计算" in relic
    assert "当前限时活动" in activity or "热美亚裂缝" in activity
    assert "当前虚空裂缝" not in activity
```

- [x] **Step 3: Run unsupported and cross-intent tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py -k "unsupported or cross_intent" -q --basetemp .pytest-tmp-step57-unsupported-cross -p no:cacheprovider
```

Expected: all pass or expose a precise route priority bug.

---

### Task 5: Implement Minimal Fixes Only For Red Cases

**Files:**
- Modify only files tied to failing tests:
  - `warframe_agent/chat.py`
  - `warframe_agent/baro.py`
  - `warframe_agent/events.py`
  - `tests/test_chat_event_replies.py`

- [x] **Step 1: Classify failures**

For every failing test, write a one-line root cause in the execution notes:

```markdown
- `test_name`: failed because [specific branch / formatter / routing condition].
```

- [x] **Step 2: Apply the smallest matching fix**

Allowed minimal fixes:

- Baro inventory wording: add one explanatory line to `format_baro_report(...)` or pass a display mode from `ChatAgent._try_baro_recommendation(...)`.
- Baro no-data consistency: adjust the no-Baro reply in `_try_baro_recommendation(...)` or event display copy.
- Specific event fallback: adjust `_is_specific_event_list_query(...)` or event type alias only for the failing alias.
- Unsupported event: add alias to `_UNSUPPORTED_QUERY_EVENT_ALIASES` only when tests prove missing coverage.
- Cross-intent: adjust ordering in `ChatAgent.answer(...)` only for the failing intent, and add a focused regression.

Forbidden in this task:

- Do not change ToolRouter safety policy.
- Do not add network fetches.
- Do not enable Browser/GUI executor, shell executor, connector, webhook or scheduler.
- Do not rewrite `ChatAgent`.

- [x] **Step 3: Run targeted green tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_event_replies.py -q --basetemp .pytest-tmp-step57-event-replies -p no:cacheprovider
```

Expected: all Step 57 reply matrix tests pass.

---

### Task 6: Regression Verification And Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Create: `githubProduct/personal_agent_warframe_migration_step57_event_baro_response_audit_zh.md`

- [x] **Step 1: Run focused existing suites**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_baro.py tests\test_events.py tests\test_tool_router.py tests\test_chat_event_replies.py -q --basetemp .pytest-tmp-step57-focused -p no:cacheprovider
```

Expected: all selected suites pass.

- [x] **Step 2: Run chat broad regression**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py tests\test_chat_memory_commands.py -k "activity or event or baro or resurgence or fissure" -q --basetemp .pytest-tmp-step57-chat-broad -p no:cacheprovider
```

Expected: all selected tests pass.

- [x] **Step 3: Run syntax and diff checks**

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/baro.py','warframe_agent/events.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\chat.py warframe_agent\baro.py warframe_agent\events.py tests\test_chat_event_replies.py docs\superpowers\plans\2026-05-31-step57-event-baro-response-audit.md githubProduct\personal_agent_warframe_migration_step57_event_baro_response_audit_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

Expected: `AST OK`; `git diff --check` exits 0, allowing only LF/CRLF warnings.

- [x] **Step 4: Document outcomes**

Report must include:

- Replies audited.
- Failures found, if any.
- Fixes made, if any.
- Tests run and exact pass/fail counts.
- Remaining risks.
- Safety boundary: no GitHub upload, no dependency install, no download, no high-privilege runtime.

## Execution Notes

- Red cases found during execution:
  - `test_baro_inventory_wording_makes_scope_clear`: failed because `format_baro_report(...)` did not explicitly say inventory-style Baro questions only show analyzable Mod / Arcane items.
  - `test_event_keywords_do_not_hijack_market_relic_or_video_intents`: failed because `热美亚裂缝现在有吗` was initially classified as a void fissure query.
  - `test_baro_followup_does_not_hijack_later_market_link_query`: failed because stale Baro follow-up context hijacked `充沛最便宜卖家链接`.
  - The specific limited-activity variant also exposed that `热美亚裂缝` and `兽之腹` were returned together instead of filtering by the requested activity.
- Minimal fixes applied:
  - `warframe_agent/baro.py`: Baro report now states that only analyzable Mod / Arcane items are shown.
  - `warframe_agent/chat.py`: limited activity aliases are separated from generic void fissure routing; specific limited-activity questions are filtered by requested label.
  - `warframe_agent/chat.py`: mission + mode/tier/fissure detail questions such as `钢铁歼灭现在有吗` route to structured void fissures.
  - `warframe_agent/chat.py`: Baro order follow-up yields to direct market item link/seller queries when the new message resolves to a non-Baro item.
- Verification completed:
  - Red extra: `2 failed` before fixes, then `2 passed`.
  - Step57 matrix: `10 passed`.
  - Focused suites: `83 passed`.
  - Chat broad regression: `18 passed, 114 deselected`.
  - AST check: `AST OK`.
- Subagent note: one read-only review subagent was attempted after implementation, but it hit a usage-limit error and produced no usable findings; final evidence is based on local tests and main-thread review.
- Safety boundary: no dependency install, no download, no GitHub upload, no Browser/GUI executor, no shell executor, no service recovery, no trigger platform, no plugin install, no connector enable, no webhook / DM command entry, and no real voice capability.
