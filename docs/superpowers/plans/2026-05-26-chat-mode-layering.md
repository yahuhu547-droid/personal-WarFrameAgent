# Chat Mode Layering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight chat mode layer so guide-video wording does not steal market, trade, event, or planning questions, while preserving existing direct Bilibili recommendation flows.

**Architecture:** Keep routing inside `ChatAgent` and avoid new dependencies. Add a deterministic `ChatModeDecision` helper in `warframe_agent/chat.py`, then use it only as a guard around direct/append Bilibili recommendation paths. The first implementation is intentionally conservative: it changes conflict handling, not the tool registry or LLM prompt contract.

**Tech Stack:** Python dataclasses, existing `ChatAgent`, pytest, project `.venv`.

---

## File Map

- Modify: `warframe_agent/chat.py`
  - Add `ChatModeDecision`.
  - Add `_classify_chat_mode(...)`, `_message_has_direct_market_intent(...)`, `_message_has_market_analysis_intent(...)`, and `_message_has_guide_video_intent(...)`.
  - Update `_try_direct_bilibili_recommendations(...)` and `_append_bilibili_recommendations(...)` to only use Bilibili when the classifier picks `guide_video`.
  - Return deterministic order summaries for `market_analysis` conflicts instead of relying on LLM output.
- Modify: `tests/test_chat.py`
  - Add classifier unit tests.
  - Add answer and answer_stream regression tests for mixed price/video wording.
- Create: `githubProduct/personal_agent_warframe_migration_step18_chat_mode_layering_zh.md`
  - Record borrowed idea, implementation scope, and learning checklist.
- Modify: `md/rebuilt/02-feature-scope.md`
  - Document chat mode layering scope.
- Modify: `md/rebuilt/07-operations-testing.md`
  - Add targeted verification commands.
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - Record Step 18 completion and next candidate tasks.

## Task 1: Chat Mode Classifier

**Files:**
- Test: `tests/test_chat.py`
- Modify: `warframe_agent/chat.py`

- [x] **Step 1: Write the failing classifier test**

Add to `tests/test_chat.py` imports:

```python
from warframe_agent.chat import ChatAgent, build_chat_messages, build_item_context, is_chat_exit, _classify_chat_mode, _self_check
```

Add:

```python
    def test_chat_mode_classifier_prioritizes_market_over_video_words(self):
        self.assertEqual(_classify_chat_mode("充沛多少钱，顺便给攻略视频").mode, "market_analysis")
        self.assertEqual(_classify_chat_mode("给我 充沛 的市场链接 攻略视频").mode, "trade_execution")
        self.assertEqual(_classify_chat_mode("推荐几个近战配卡视频").mode, "guide_video")
        self.assertEqual(_classify_chat_mode("有什么 mod 可以翻转赚钱").mode, "trading_tool")
        self.assertEqual(_classify_chat_mode("现在有什么活动").mode, "event")
```

- [x] **Step 2: Run red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_chat_mode_classifier_prioritizes_market_over_video_words -q
```

Expected: FAIL with import error or missing `_classify_chat_mode`.

- [x] **Step 3: Implement classifier**

Add near `ItemContext`:

```python
@dataclass(frozen=True)
class ChatModeDecision:
    mode: str
    reason: str = ""
```

Add helper functions near other module-level intent helpers:

```python
def _classify_chat_mode(message: str) -> ChatModeDecision:
    if _message_has_direct_market_intent(message):
        return ChatModeDecision("trade_execution", "direct_market")
    if _is_event_query(message):
        return ChatModeDecision("event", "event_keywords")
    if _is_trading_tool_query(message):
        return ChatModeDecision("trading_tool", "trading_tool_keywords")
    if _message_has_market_analysis_intent(message):
        return ChatModeDecision("market_analysis", "market_keywords")
    if _message_has_guide_video_intent(message):
        return ChatModeDecision("guide_video", "guide_keywords")
    return ChatModeDecision("general", "fallback")
```

The market-analysis detector must include `多少钱`、`价格`、`买价`、`卖价`、`白金`、`价差`、`会涨`、`会跌`、`趋势`、`走势`、`行情`、`能不能买`、`能不能卖`、`我要买`、`我要卖`、`我想买`、`我想卖`、`最高收`、`最低卖`。 The guide detector must include `配卡`、`攻略`、`视频`、`教程`、`b站`、`bilibili`、`build`。

- [x] **Step 4: Run green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_chat_mode_classifier_prioritizes_market_over_video_words -q
```

Expected: PASS.

## Task 2: Bilibili Guardrails For Mixed Intent

**Files:**
- Test: `tests/test_chat.py`
- Modify: `warframe_agent/chat.py`

- [x] **Step 1: Write answer regression test**

Add:

```python
    def test_price_mode_wins_over_explicit_bilibili_video_words(self):
        fetched = []
        with tempfile.TemporaryDirectory() as tmp:
            rec_path = Path(tmp) / "bilibili_recommendations.json"
            rec_path.write_text(json.dumps([{
                "id": "energize-guide",
                "title": "充沛赋能攻略视频",
                "url": "https://www.bilibili.com/video/BVENERGIZE/",
                "aliases": ["充沛攻略", "充沛赋能攻略"],
                "topics": ["攻略"],
            }], ensure_ascii=False), encoding="utf-8")
            agent = ChatAgent(
                resolver=FakeResolver(),
                order_fetcher=lambda item_id: fetched.append(item_id) or SAMPLE_ORDERS,
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "agent_memory.json",
            )
            agent.bilibili_recommendations_path = rec_path

            answer = agent.answer("充沛多少钱，顺便给攻略视频")

        self.assertIn("最低卖价", answer)
        self.assertIn("5p", answer)
        self.assertNotIn("参考视频", answer)
        self.assertNotIn("BVENERGIZE", answer)
        self.assertEqual(fetched, ["arcane_energize"])
```

- [x] **Step 2: Write answer_stream regression test**

Add:

```python
    def test_answer_stream_price_mode_wins_over_explicit_bilibili_video_words(self):
        async def consume(agent):
            chunks = []
            async for chunk in agent.answer_stream("充沛多少钱，顺便给攻略视频"):
                chunks.append(chunk)
            return "".join(chunks)

        fetched = []
        with tempfile.TemporaryDirectory() as tmp:
            rec_path = Path(tmp) / "bilibili_recommendations.json"
            rec_path.write_text(json.dumps([{
                "id": "energize-guide",
                "title": "充沛赋能攻略视频",
                "url": "https://www.bilibili.com/video/BVENERGIZE/",
                "aliases": ["充沛攻略", "充沛赋能攻略"],
                "topics": ["攻略"],
            }], ensure_ascii=False), encoding="utf-8")
            agent = ChatAgent(
                resolver=FakeResolver(),
                order_fetcher=lambda item_id: fetched.append(item_id) or SAMPLE_ORDERS,
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "agent_memory.json",
            )
            agent.bilibili_recommendations_path = rec_path

            answer = asyncio.run(consume(agent))

        self.assertIn("最低卖价", answer)
        self.assertIn("5p", answer)
        self.assertNotIn("参考视频", answer)
        self.assertNotIn("BVENERGIZE", answer)
        self.assertEqual(fetched, ["arcane_energize"])
```

- [x] **Step 3: Run red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_price_mode_wins_over_explicit_bilibili_video_words tests/test_chat.py::ChatTests::test_answer_stream_price_mode_wins_over_explicit_bilibili_video_words -q
```

Expected: FAIL because explicit video words currently trigger Bilibili before market context.

- [x] **Step 4: Implement Bilibili guards**

Change `_try_direct_bilibili_recommendations(...)`:

```python
        decision = _classify_chat_mode(message)
        if decision.mode != "guide_video":
            return None
```

Change `_append_bilibili_recommendations(...)`:

```python
        if _classify_chat_mode(message).mode != "guide_video":
            return answer
```

- [x] **Step 4b: Return deterministic summaries for market-analysis conflicts**

After `_deterministic_trade_intent_answer(...)`, if `_classify_chat_mode(message).mode == "market_analysis"`, return `fallback_answer(message, contexts)` in both `answer(...)` and `answer_stream(...)`. This prevents injected or failing LLM calls from replacing an explicit price question with generic text.

- [x] **Step 5: Run green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_price_mode_wins_over_explicit_bilibili_video_words tests/test_chat.py::ChatTests::test_answer_stream_price_mode_wins_over_explicit_bilibili_video_words -q
```

Expected: PASS.

## Task 3: Docs And Verification

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step18_chat_mode_layering_zh.md`
- Modify: `md/rebuilt/02-feature-scope.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: Update docs**

Document that chat mode layering is a deterministic routing guard, not an LLM prompt rewrite. Mention the first conflict solved: price/trade wording wins over guide-video terms.

- [x] **Step 2: Run verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "chat_mode or bilibili_video_words or direct_market_intent or answer_returns_bilibili_recommendations or does_not_append_bilibili" -q
.\.venv\Scripts\python.exe -m pytest tests/test_bilibili_recommendations.py -q --basetemp .pytest_tmp_step18_bilibili
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','tests/test_chat.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\chat.py tests\test_chat.py docs\superpowers\plans\2026-05-26-chat-mode-layering.md githubProduct\personal_agent_warframe_migration_step18_chat_mode_layering_zh.md md\rebuilt\02-feature-scope.md md\rebuilt\07-operations-testing.md md\rebuilt\09-personal-agent-foundation.md
```

Expected: tests pass, AST OK, and `git diff --check` has no whitespace errors apart from possible CRLF warnings.

## Result

Completed on 2026-05-26. Final focused verification:

- `tests/test_chat.py -k "chat_mode or bilibili_video_words or direct_market_intent or answer_returns_bilibili_recommendations or does_not_append_bilibili"`: 7 passed.
- `tests/test_bilibili_recommendations.py --basetemp .pytest_tmp_step18_bilibili`: 14 passed.
- Python AST parse for `warframe_agent/chat.py` and `tests/test_chat.py`: OK.
- `git diff --check`: no whitespace errors; only CRLF conversion warnings.
