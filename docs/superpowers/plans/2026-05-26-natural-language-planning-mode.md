# Natural Language Planning Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative natural-language planning mode so requests like "制定一周赚 500p 的计划" do not trigger direct trade execution, Bilibili guide answers, or ordinary price fallback.

**Architecture:** Extend the lightweight chat mode classifier in `warframe_agent/chat.py` with a `planning` mode. Keep it deterministic and side-effect free: natural-language planning returns a safe plan preview and points users to `/goal set ...` if they want tracking. Explicit direct-market requests such as "市场链接/最低卖家/砍价" still win over planning words.

**Tech Stack:** Python dataclasses, existing `ChatAgent`, pytest, project `.venv`.

---

## File Map

- Modify: `warframe_agent/chat.py`
  - Add `_message_has_planning_intent(...)`.
  - Update `_classify_chat_mode(...)` with `planning`.
  - Add `ChatAgent._try_planning_intent(...)` and `ChatAgent._planning_goal_hint(...)`.
  - Call planning mode from both `answer(...)` and `answer_stream(...)` after direct market intent and before Bilibili/event/tool/price fallback.
- Modify: `warframe_agent/tool_router.py`
  - Include `plan` in candidate tools for natural-language planning requests.
- Modify: `tests/test_chat.py`
  - Add classifier and `answer(...)` regression tests for natural planning.
  - Add `answer_stream(...)` parity test.
- Modify: `tests/test_tool_router.py`
  - Add candidate-tool regression for planning requests.
- Create: `githubProduct/personal_agent_warframe_migration_step19_natural_language_planning_mode_zh.md`
  - Record borrowed idea, implementation scope, and learning checklist.
- Modify: `md/rebuilt/02-feature-scope.md`
  - Document natural-language planning mode.
- Modify: `md/rebuilt/07-operations-testing.md`
  - Add targeted verification commands.
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - Record Step 19 completion and next candidate tasks.

## Task 1: Planning Classifier

**Files:**
- Test: `tests/test_chat.py`
- Modify: `warframe_agent/chat.py`

- [x] **Step 1: Write failing classifier assertions**

Extend `test_chat_mode_classifier_prioritizes_market_over_video_words`:

```python
        self.assertEqual(_classify_chat_mode("帮我制定一周倒卖充沛赚500p的计划，不要直接买").mode, "planning")
        self.assertEqual(_classify_chat_mode("给我 充沛 的市场链接，顺便做个计划").mode, "trade_execution")
        self.assertEqual(_classify_chat_mode("帮我做一个充沛赚500p目标计划，顺便找攻略视频").mode, "planning")
```

- [x] **Step 2: Run red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_chat_mode_classifier_prioritizes_market_over_video_words -q
```

Expected: FAIL because planning text is currently classified as `trading_tool` or `guide_video`.

- [x] **Step 3: Implement classifier**

Add:

```python
def _message_has_planning_intent(message: str) -> bool:
    lowered = message.lower()
    normalized = normalize_lookup_key(message)
    planning_terms = ("计划", "规划", "目标", "步骤", "安排", "路线图", "roadmap", "plan")
    horizon_terms = ("一周", "本周", "今天开始", "长期", "短期", "每天", "阶段")
    profit_goal_terms = ("赚", "盈利", "利润目标", "目标利润", "500p", "1000p")
    has_plan = any(term in lowered or normalize_lookup_key(term) in normalized for term in planning_terms)
    has_horizon_goal = any(term in lowered or term in message for term in horizon_terms) and any(term in lowered or term in message for term in profit_goal_terms)
    return has_plan or has_horizon_goal
```

Update `_classify_chat_mode(...)` order:

```python
    if _message_has_direct_market_intent(message):
        return ChatModeDecision("trade_execution", "direct_market")
    if _message_has_planning_intent(message):
        return ChatModeDecision("planning", "planning_keywords")
```

- [x] **Step 4: Run green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_chat_mode_classifier_prioritizes_market_over_video_words -q
```

Expected: PASS.

## Task 2: Safe Planning Reply

**Files:**
- Test: `tests/test_chat.py`
- Modify: `warframe_agent/chat.py`

- [x] **Step 1: Write natural-language planning regression test**

Add:

```python
    def test_natural_language_planning_mode_does_not_execute_trade_or_bilibili(self):
        fetched = []
        model_prompts = []
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
                model_call=lambda prompt: model_prompts.append(prompt) or "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "agent_memory.json",
            )
            agent.bilibili_recommendations_path = rec_path

            answer = agent.answer("帮我制定一周倒卖充沛赚500p的计划，不要直接买，顺便给攻略视频")

        self.assertIn("计划草案", answer)
        self.assertIn("/goal set", answer)
        self.assertIn("不会直接下单", answer)
        self.assertNotIn("/w Seller", answer)
        self.assertNotIn("BVENERGIZE", answer)
        self.assertEqual(fetched, [])
        self.assertEqual(model_prompts, [])
```

- [x] **Step 2: Write answer_stream parity test**

Add:

```python
    def test_answer_stream_natural_language_planning_mode_matches_answer_priority(self):
        async def consume(agent):
            chunks = []
            async for chunk in agent.answer_stream("帮我制定一周倒卖充沛赚500p的计划，不要直接买"):
                chunks.append(chunk)
            return "".join(chunks)

        fetched = []
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                resolver=FakeResolver(),
                order_fetcher=lambda item_id: fetched.append(item_id) or SAMPLE_ORDERS,
                model_call=lambda prompt: "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "agent_memory.json",
            )

            answer = asyncio.run(consume(agent))

        self.assertIn("计划草案", answer)
        self.assertIn("/goal set", answer)
        self.assertNotIn("/w Seller", answer)
        self.assertEqual(fetched, [])
```

- [x] **Step 3: Run red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_natural_language_planning_mode_does_not_execute_trade_or_bilibili tests/test_chat.py::ChatTests::test_answer_stream_natural_language_planning_mode_matches_answer_priority -q
```

Expected: FAIL because no planning-mode reply exists.

- [x] **Step 4: Implement safe planning reply**

Add methods inside `ChatAgent`:

```python
    def _try_planning_intent(self, message: str) -> str | None:
        if _classify_chat_mode(message).mode != "planning":
            return None
        hint = self._planning_goal_hint(message)
        return "\n".join([
            "我把这条识别为计划/目标请求，不会直接下单、不会生成购买私聊。",
            "",
            "计划草案:",
            "1. 先确认预算、风险和最低 ROI；可用 /profile 查看当前偏好。",
            "2. 用投资/倒卖扫描找候选，只看利润、ROI、流动性和历史复盘表现。",
            "3. 每天复查价格和在线订单，达到目标价再手动执行交易。",
            "4. 完成后用 /review done OPID 实际利润 good|bad 记录结果。",
            "",
            f"需要跟踪目标时可以使用: /goal set {hint}",
        ])

    @staticmethod
    def _planning_goal_hint(message: str) -> str:
        compact = re.sub(r"\s+", " ", message.strip())
        compact = re.sub(r"(不要直接买|不要下单|顺便给攻略视频|顺便找攻略视频|攻略视频)", "", compact)
        return compact[:80] or "一周内赚500p"
```

Call `_try_planning_intent(...)` in both `answer(...)` and `answer_stream(...)` right after `_try_direct_market_intent(...)`.

- [x] **Step 5: Run green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py::ChatTests::test_natural_language_planning_mode_does_not_execute_trade_or_bilibili tests/test_chat.py::ChatTests::test_answer_stream_natural_language_planning_mode_matches_answer_priority -q
```

Expected: PASS.

## Task 2b: Router Candidate Support

**Files:**
- Test: `tests/test_tool_router.py`
- Modify: `warframe_agent/tool_router.py`

- [x] **Step 1: Write router candidate red test**

Add:

```python
    def test_candidate_tools_for_natural_language_planning_include_plan(self):
        candidates = select_candidate_tools("帮我制定一周赚500p的计划")

        self.assertIn("plan", candidates)
        self.assertIn("investment_advisor", candidates)
        self.assertLessEqual(len(candidates), 6)
```

- [x] **Step 2: Run red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py::ToolRouterTests::test_candidate_tools_for_natural_language_planning_include_plan -q
```

Expected: FAIL because `plan` is missing.

- [x] **Step 3: Implement candidate branch**

Add a `计划/规划/目标/路线图/roadmap/plan` branch in `select_candidate_tools(...)` returning:

```python
["plan", "investment_advisor", "mod_flipper", "set_profit", "query_price", "price_trend"]
```

- [x] **Step 4: Run green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py::ToolRouterTests::test_candidate_tools_for_natural_language_planning_include_plan -q
```

Expected: PASS.

## Task 3: Docs And Verification

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step19_natural_language_planning_mode_zh.md`
- Modify: `md/rebuilt/02-feature-scope.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: Update docs**

Document that natural-language planning is a safe preview mode. It does not create goals automatically and does not execute trades; `/goal set ...` remains the explicit tracking command.

- [x] **Step 2: Run verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "chat_mode or planning_mode or bilibili_video_words or direct_market_intent" -q
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py -k "planning_include_plan or investment_query_include_investment_tools or react_loop_records_agent_plan_snapshot" -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','tests/test_chat.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/tool_router.py','tests/test_tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\chat.py warframe_agent\tool_router.py tests\test_chat.py tests\test_tool_router.py docs\superpowers\plans\2026-05-26-natural-language-planning-mode.md githubProduct\personal_agent_warframe_migration_step19_natural_language_planning_mode_zh.md md\rebuilt\02-feature-scope.md md\rebuilt\07-operations-testing.md md\rebuilt\09-personal-agent-foundation.md
```

Expected: tests pass, AST OK, and `git diff --check` has no whitespace errors apart from possible CRLF warnings.

## Result

Completed on 2026-05-26. Final focused verification:

- `tests/test_chat.py -k "chat_mode or planning_mode or bilibili_video_words or direct_market_intent"`: 6 passed.
- `tests/test_tool_router.py -k "planning_include_plan or investment_query_include_investment_tools or react_loop_records_agent_plan_snapshot"`: 3 passed.
- Python AST parse for chat/router files and tests: OK.
- `git diff --check`: no whitespace errors; only CRLF conversion warnings.
