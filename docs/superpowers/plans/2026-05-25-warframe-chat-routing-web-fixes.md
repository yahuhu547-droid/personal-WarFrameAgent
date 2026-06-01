# Warframe Chat Routing And Web Error Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reviewed correctness gaps where natural Chinese questions are routed to the wrong subsystem, opportunity scans silently miss candidates, tool contracts misreport failures, and Web chat error states mislead or lock the user.

**Architecture:** Keep the existing `ChatAgent` and tool registry shape, but add deterministic intent guards before market-context fallback. Tighten shared market/order helpers so scan tools compute on the intended input set. Make frontend chat handle every backend response shape explicitly.

**Tech Stack:** Python 3, pytest, FastAPI/WebSocket, vanilla JavaScript frontend.

---

## File Structure

- Modify `warframe_agent/chat.py`: add guide/build intent handling, route relic value/farming queries before generic event handling, consume `target_part` in `relic_value`.
- Modify `warframe_agent/bilibili_recommendations.py`: expose a small guide-intent helper and optional entity/category detection helpers for clearer fallback messages.
- Modify `warframe_agent/tool_router.py`: remove unavailable `general_chat` candidates or make them intentionally fall through without creating successful tool results.
- Modify `warframe_agent/tool_registry.py`: treat handler `None` as a non-successful no-result state.
- Modify `warframe_agent/set_profit.py`: scan all Prime groups by default and normalize order type counting.
- Modify `warframe_agent/investment.py`: scan all Prime candidates unless an explicit limit is applied after scoring; normalize set-order counting.
- Modify `warframe_agent/mod_flipper.py`: scan all eligible mods for correctness, then apply display limit after scoring.
- Modify `warframe_agent/market.py`: make rank filtering exclude unknown-rank orders when a rank filter is requested.
- Modify `warframe_agent/web/static/js/app.js`: make `sendChat()` return a normalized error shape with a user-visible message.
- Modify `warframe_agent/web/static/js/chat.js`: handle REST errors, WebSocket `{status:"error"}`, and undefined reply safely.
- Test `tests/test_chat.py`: add regression coverage for "猴子该怎么配卡" and guide fallback.
- Test `tests/test_tool_router.py`: cover relic/guide candidate selection and no-result tool coercion.
- Test `tests/test_set_profit.py`, `tests/test_investment.py`, `tests/test_mod_flipper.py`: cover scan candidates beyond previous hard caps.
- Test `tests/test_market_client.py` or `tests/test_mod_flipper.py`: cover missing rank exclusion under rank filters.
- Test `tests/test_web_api.py` and `tests/test_web_ui_playwright.py`: cover WebSocket error and REST non-2xx chat behavior.

## Task 1: Add Deterministic Guide Intent Fallback

**Files:**
- Modify: `warframe_agent/bilibili_recommendations.py`
- Modify: `warframe_agent/chat.py`
- Modify: `warframe_agent/tool_router.py`
- Test: `tests/test_bilibili_recommendations.py`
- Test: `tests/test_chat.py`
- Test: `tests/test_tool_router.py`

- [ ] **Step 1: Add failing recommendation-intent tests**

Append these tests to `tests/test_bilibili_recommendations.py`:

```python
def test_wukong_alias_has_guide_intent_but_no_repository_match():
    service = BilibiliRecommendationService(BilibiliRecommendationStore(Path("data/bilibili_recommendations.json")))

    assert is_bilibili_recommendation_intent("猴子该怎么配卡") is True
    assert service.recommend("猴子该怎么配卡") == []
```

Append this test to `tests/test_chat.py`:

```python
def test_guide_question_with_known_market_alias_does_not_fall_into_price_context():
    prompts = []

    def model_call(prompt):
        prompts.append(prompt)
        return "不应该调用模型生成价格上下文"

    with tempfile.TemporaryDirectory() as tmp:
        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: SAMPLE_ORDERS,
            model_call=model_call,
            memory_path=Path(tmp) / "agent_memory.json",
        )
        answer = agent.answer("猴子该怎么配卡")

    assert "暂未收录" in answer
    assert "配卡" in answer
    assert "B 站视频" in answer
    assert "最低卖价" not in answer
    assert prompts == []
```

Append this test to `tests/test_tool_router.py`:

```python
def test_select_candidate_tools_for_build_questions_does_not_offer_unregistered_general_chat():
    candidates = select_candidate_tools("猴子该怎么配卡")

    self.assertNotIn("general_chat", candidates)
    self.assertIn("query_events", candidates)
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_bilibili_recommendations.py::test_wukong_alias_has_guide_intent_but_no_repository_match tests/test_chat.py::ChatTests::test_guide_question_with_known_market_alias_does_not_fall_into_price_context tests/test_tool_router.py::ToolRouterTests::test_select_candidate_tools_for_build_questions_does_not_offer_unregistered_general_chat -q -p no:cacheprovider --basetemp output/pytest-tmp-guide-intent
```

Expected: the ChatAgent test fails because the current answer uses market/LLM fallback instead of a guide fallback; the tool-router test may fail if `general_chat` is still selected.

- [ ] **Step 3: Add a guide fallback helper**

In `warframe_agent/chat.py`, near `_try_direct_bilibili_recommendations()`, add:

```python
    def _guide_fallback_answer(self, message: str) -> str:
        entity = self._guide_entity_label(message)
        target = f"「{entity}」" if entity else "这个目标"
        return (
            f"暂未收录{target}的配卡/攻略 B 站视频。"
            "我现在不会把这个问题当成市场价格查询。"
            "可以先换成更具体的武器、战甲英文名，或把可信攻略链接加入 data/bilibili_recommendations.json。"
        )

    def _guide_entity_label(self, message: str) -> str | None:
        for token in _message_tokens(message):
            if token in {"配卡", "配装", "攻略", "教程", "视频", "怎么", "该", "如何"}:
                continue
            if token in getattr(self.resolver, "aliases", {}) or token in getattr(self.resolver, "generated_aliases", {}):
                return token
        for alias in ("猴子", "悟空", "电男", "伏特", "毒妈", "女枪", "犀牛"):
            if alias in message:
                return alias
        return None
```

- [ ] **Step 4: Stop guide questions from falling into price contexts**

In both `answer()` and `answer_stream()`, after the direct Bilibili recommendation block and before Baro/Riven/market handling, add:

```python
        if is_bilibili_recommendation_intent(message):
            result = self._guide_fallback_answer(message)
            self.session.add_exchange(message, result)
            self._log_answer(message, result)
            return result
```

For `answer_stream()`, use:

```python
        if is_bilibili_recommendation_intent(message):
            result = self._guide_fallback_answer(message)
            self.session.add_exchange(message, result)
            self._log_answer(message, result)
            yield result
            return
```

- [ ] **Step 5: Remove unavailable `general_chat` candidates**

In `warframe_agent/tool_router.py`, change the build/guide branches:

```python
    elif any(token in lowered for token in ("配卡", "配装", "build", "mod配置", "钢铁怎么配", "武器怎么配")):
        candidates = ["riven_search", "query_events", "farming_route"]
    elif any(token in lowered for token in ("攻略", "打法", "机制", "怎么玩", "怎么打", "流程")):
        candidates = ["query_events", "farming_route"]
```

- [ ] **Step 6: Verify guide behavior**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_bilibili_recommendations.py tests/test_chat.py::ChatTests::test_guide_question_with_known_market_alias_does_not_fall_into_price_context tests/test_chat.py::ChatTests::test_answer_appends_bilibili_recommendations_for_build_questions tests/test_tool_router.py::ToolRouterTests::test_select_candidate_tools_for_build_questions_does_not_offer_unregistered_general_chat -q -p no:cacheprovider --basetemp output/pytest-tmp-guide-intent
```

Expected: all selected tests pass.

## Task 2: Route Relic Value And Farming Queries Before Generic Events

**Files:**
- Modify: `warframe_agent/chat.py`
- Test: `tests/test_tool_router.py`
- Test: `tests/test_chat.py`

- [ ] **Step 1: Add failing route-precedence tests**

Append this test to `tests/test_tool_router.py`:

```python
def test_relic_value_and_farming_queries_have_specific_candidates_before_events():
    value_candidates = select_candidate_tools("这个遗物收益怎么样")
    route_candidates = select_candidate_tools("哪个裂缝适合开这个核桃")

    self.assertIn("relic_value", value_candidates)
    self.assertIn("farming_route", route_candidates)
```

Append this test to `tests/test_chat.py`:

```python
def test_relic_value_question_uses_router_before_limited_event_fallback():
    calls = []

    def router(prompt):
        calls.append(prompt)
        return '{"tool":"relic_value","args":{"relic_name":"Lith B1"}}'

    with tempfile.TemporaryDirectory() as tmp:
        agent = ChatAgent(
            router_call=router,
            model_call=router,
            rag_search=lambda message: [],
            memory_path=Path(tmp) / "agent_memory.json",
        )
        agent._try_react_loop = lambda message: None
        agent.tool_registry.with_handler(
            "relic_value",
            lambda args: ToolResult(ok=True, content="Lith B1 期望白金 3.2p", display_content="Lith B1 期望白金 3.2p"),
        )
        answer = agent.answer("这个遗物收益怎么样")

    assert "期望白金" in answer
    assert calls
    assert "当前限时活动" not in answer
```

Add these imports to `tests/test_chat.py` if missing:

```python
from warframe_agent.tool_registry import ToolResult
```

- [ ] **Step 2: Run the failing route tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py::ToolRouterTests::test_relic_value_and_farming_queries_have_specific_candidates_before_events tests/test_chat.py::ChatTests::test_relic_value_question_uses_router_before_limited_event_fallback -q -p no:cacheprovider --basetemp output/pytest-tmp-relic-routing
```

Expected: ChatAgent test fails because generic event handling returns limited event text before router execution.

- [ ] **Step 3: Add specific relic-intent helpers**

In `warframe_agent/chat.py`, near `_is_event_query()`, add:

```python
def _is_relic_value_intent(message: str) -> bool:
    lower = message.lower()
    has_relic = any(kw in lower for kw in ("遗物", "核桃", "relic", "lith", "meso", "neo", "axi", "古纪", "前纪", "中纪", "后纪"))
    has_value = any(kw in lower for kw in ("收益", "价值", "估值", "期望", "值不值得", "值得开", "效率", "杜卡特", "杜卡德", "ducat"))
    return has_relic and has_value


def _is_relic_farming_intent(message: str) -> bool:
    lower = message.lower()
    has_relic = any(kw in lower for kw in ("遗物", "核桃", "relic", "lith", "meso", "neo", "axi", "古纪", "前纪", "中纪", "后纪"))
    has_route = any(kw in lower for kw in ("去哪刷", "哪里刷", "怎么刷", "刷取", "掉落", "来源", "哪个裂缝", "适合开", "开这个核桃"))
    return has_relic and has_route
```

- [ ] **Step 4: Route specific relic intents before generic events**

In `answer()`, before:

```python
        if _is_event_query(message) or _is_trading_tool_query(message):
```

insert:

```python
        if _is_relic_value_intent(message) or _is_relic_farming_intent(message):
            routed = self._try_router_result(message)
            routed_display = self._tool_result_display_text(routed)
            if routed_display:
                self.session.add_exchange(message, self._tool_result_history_text(routed))
                self._log_answer(message, routed_display)
                return routed_display
```

Repeat the same structure in `answer_stream()`, yielding `routed_display`.

- [ ] **Step 5: Verify route precedence**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_router.py::ToolRouterTests::test_relic_value_and_farming_queries_have_specific_candidates_before_events tests/test_chat.py::ChatTests::test_relic_value_question_uses_router_before_limited_event_fallback -q -p no:cacheprovider --basetemp output/pytest-tmp-relic-routing
```

Expected: both tests pass.

## Task 3: Make Scans Correct Before Limiting Display

**Files:**
- Modify: `warframe_agent/set_profit.py`
- Modify: `warframe_agent/investment.py`
- Modify: `warframe_agent/mod_flipper.py`
- Test: `tests/test_set_profit.py`
- Test: `tests/test_investment.py`
- Test: `tests/test_mod_flipper.py`

- [ ] **Step 1: Add failing set-profit cap regression**

Append this test to `tests/test_set_profit.py`:

```python
def test_scan_all_set_profits_considers_candidates_after_first_15():
    items = []
    for i in range(16):
        base = f"dummy_{i}_prime"
        items.extend([
            {"item_id": f"{base}_set", "en_name": f"Dummy {i} Prime Set", "tags": ["prime", "set", "warframe"]},
            {"item_id": f"{base}_blueprint", "en_name": f"Dummy {i} Prime Blueprint", "tags": ["prime", "component", "warframe"]},
            {"item_id": f"{base}_chassis_blueprint", "en_name": f"Dummy {i} Prime Chassis Blueprint", "tags": ["prime", "component", "warframe"]},
        ])

    target_base = "dummy_15_prime"

    def order_fetcher(item_id):
        if item_id == f"{target_base}_set":
            return [{"type": "buy", "platinum": 100, "quantity": 1, "user": {"ingameName": "Buyer", "status": "ingame"}}]
        if item_id in {f"{target_base}_blueprint", f"{target_base}_chassis_blueprint"}:
            return [{"type": "sell", "platinum": 10, "quantity": 1, "user": {"ingameName": "Seller", "status": "ingame"}}]
        return []

    results = scan_all_set_profits(items, order_fetcher=order_fetcher, min_profit=1, limit=5)

    assert any(result.item_id == f"{target_base}_set" for result in results)
```

- [ ] **Step 2: Add failing investment cap regression**

Append this test to `tests/test_investment.py`:

```python
def test_scan_prime_investments_considers_candidates_after_first_30():
    items = []
    for i in range(31):
        base = f"invest_{i}_prime"
        items.extend([
            {"item_id": f"{base}_set", "en_name": f"Invest {i} Prime Set", "tags": ["prime", "set", "weapon"]},
            {"item_id": f"{base}_blueprint", "en_name": f"Invest {i} Prime Blueprint", "tags": ["prime", "component", "weapon"]},
            {"item_id": f"{base}_barrel", "en_name": f"Invest {i} Prime Barrel", "tags": ["prime", "component", "weapon"]},
        ])

    target_base = "invest_30_prime"

    def order_fetcher(item_id):
        if item_id == f"{target_base}_set":
            return [{"type": "buy", "platinum": 120, "quantity": 1, "user": {"ingameName": "Buyer", "status": "ingame"}}]
        if item_id in {f"{target_base}_blueprint", f"{target_base}_barrel"}:
            return [{"type": "sell", "platinum": 20, "quantity": 1, "user": {"ingameName": "Seller", "status": "ingame"}}]
        return []

    results = scan_prime_investments(items, order_fetcher=order_fetcher, budget=100, min_roi_pct=1, limit=5)

    assert any(result.item_id == f"{target_base}_set" for result in results)
```

- [ ] **Step 3: Add failing mod-flipper cap regression**

Append this test to `tests/test_mod_flipper.py`:

```python
def test_scan_all_mod_flips_considers_mods_after_priority_slices():
    items = [
        {
            "url_name": f"ordinary_mod_{i}",
            "item_name": f"Ordinary Mod {i}",
            "tags": ["mod"],
            "tradable": True,
            "modMaxRank": 10,
            "rarity": "Rare",
        }
        for i in range(25)
    ]
    target = "ordinary_mod_24"

    def order_fetcher(item_id):
        if item_id == target:
            return [
                {"type": "sell", "platinum": 10, "quantity": 1, "rank": 0, "user": {"ingameName": "Seller", "status": "ingame"}},
                {"type": "buy", "platinum": 40, "quantity": 1, "rank": 10, "user": {"ingameName": "Buyer", "status": "ingame"}},
            ]
        return []

    results = scan_all_mod_flips(items, order_fetcher=order_fetcher, min_profit=1, limit=5)

    assert any(result.item_id == target for result in results)
```

- [ ] **Step 4: Run cap regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_set_profit.py::test_scan_all_set_profits_considers_candidates_after_first_15 tests/test_investment.py::test_scan_prime_investments_considers_candidates_after_first_30 tests/test_mod_flipper.py::test_scan_all_mod_flips_considers_mods_after_priority_slices -q -p no:cacheprovider --basetemp output/pytest-tmp-scan-caps
```

Expected: all three fail before implementation.

- [ ] **Step 5: Remove pre-scoring caps**

In `warframe_agent/set_profit.py`, change:

```python
    all_candidates = list(groups.values())[:15]
```

to:

```python
    all_candidates = list(groups.values())
```

In `warframe_agent/investment.py`, change the scout and candidate block to:

```python
    if scout_fn is not None:
        try:
            scouted_ids = scout_fn(all_candidates)
            if scouted_ids:
                id_set = set(scouted_ids)
                candidates = [g for g in all_candidates if g.base_id in id_set]
                logger.info("Scout 预筛选: %d → %d 个投资候选", len(all_candidates), len(candidates))
            else:
                candidates = all_candidates
        except Exception as exc:
            logger.debug("Scout 预筛选失败，使用原始列表: %s", exc)
            candidates = all_candidates
    else:
        candidates = all_candidates

    results = []
    for group in candidates:
```

In `warframe_agent/mod_flipper.py`, change:

```python
    all_candidates = [*high_liquidity[:12], *priority_mods[:16], *other_arcanes[:6], *other_mods[:20]]
```

to:

```python
    all_candidates = [*high_liquidity, *priority_mods, *other_arcanes, *other_mods]
```

- [ ] **Step 6: Verify scan correctness**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_set_profit.py tests/test_investment.py tests/test_mod_flipper.py -q -p no:cacheprovider --basetemp output/pytest-tmp-scan-caps
```

Expected: all selected tests pass.

## Task 4: Normalize Order Type Counting And Rank Filtering

**Files:**
- Modify: `warframe_agent/set_profit.py`
- Modify: `warframe_agent/investment.py`
- Modify: `warframe_agent/market.py`
- Test: `tests/test_set_profit.py`
- Test: `tests/test_investment.py`
- Test: `tests/test_market_client.py`

- [ ] **Step 1: Add order counting tests**

Append this test to `tests/test_set_profit.py`:

```python
def test_set_profit_counts_type_field_orders_for_liquidity():
    orders = [
        {"type": "sell", "platinum": 10, "quantity": 1, "user": {"ingameName": "Seller", "status": "ingame"}},
        {"type": "buy", "platinum": 20, "quantity": 1, "user": {"ingameName": "Buyer", "status": "ingame"}},
    ]

    assert _count_orders(orders, "sell") == 1
    assert _count_orders(orders, "buy") == 1
```

Append this test to `tests/test_market_client.py`:

```python
def test_best_sellers_rank_filter_excludes_unknown_rank_orders():
    orders = [
        {"type": "sell", "platinum": 1, "quantity": 1, "user": {"ingameName": "UnknownRank", "status": "ingame"}},
        {"type": "sell", "platinum": 5, "quantity": 1, "rank": 0, "user": {"ingameName": "RankZero", "status": "ingame"}},
    ]

    sellers = best_sellers(orders, limit=2, rank_filter=0)

    assert [seller.user_name for seller in sellers] == ["RankZero"]
```

- [ ] **Step 2: Run order tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_set_profit.py::test_set_profit_counts_type_field_orders_for_liquidity tests/test_market_client.py::test_best_sellers_rank_filter_excludes_unknown_rank_orders -q -p no:cacheprovider --basetemp output/pytest-tmp-order-normalization
```

Expected: both tests fail before implementation.

- [ ] **Step 3: Normalize order type helper**

In `warframe_agent/set_profit.py`, change `_count_orders()` to:

```python
def _count_orders(orders: list[dict], order_type: str) -> int:
    return sum(1 for order in orders if (order.get("order_type") or order.get("type")) == order_type)
```

In `warframe_agent/investment.py`, change:

```python
    all_supply += sum(1 for o in set_orders if o.get("order_type") == "sell")
    all_demand += sum(1 for o in set_orders if o.get("order_type") == "buy")
```

to:

```python
    all_supply += sum(1 for o in set_orders if (o.get("order_type") or o.get("type")) == "sell")
    all_demand += sum(1 for o in set_orders if (o.get("order_type") or o.get("type")) == "buy")
```

- [ ] **Step 4: Exclude unknown ranks when rank filtering**

In `warframe_agent/market.py`, change:

```python
        if rank_filter is not None and mod_rank is not None and mod_rank != rank_filter:
            continue
```

to:

```python
        if rank_filter is not None:
            if mod_rank is None or mod_rank != rank_filter:
                continue
```

- [ ] **Step 5: Verify order normalization**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_set_profit.py tests/test_investment.py tests/test_market_client.py tests/test_mod_flipper.py -q -p no:cacheprovider --basetemp output/pytest-tmp-order-normalization
```

Expected: all selected tests pass.

## Task 5: Fix Tool No-Result Semantics And Relic Target Part Contract

**Files:**
- Modify: `warframe_agent/tool_registry.py`
- Modify: `warframe_agent/chat.py`
- Modify: `warframe_agent/relic_value.py`
- Test: `tests/test_tool_registry.py`
- Test: `tests/test_chat.py`
- Test: `tests/test_relic_value.py`

- [ ] **Step 1: Add no-result tool test**

Append this test to `tests/test_tool_registry.py`:

```python
def test_handler_none_is_not_reported_as_success():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="maybe_empty", description="empty", parameters={}))
    registry.with_handler("maybe_empty", lambda args: None)

    result = registry.execute("maybe_empty", {})

    assert result.ok is False
    assert result.error == "工具无结果: maybe_empty"
    assert result.display_content is None
    assert result.model_context is None
```

- [ ] **Step 2: Add target-part relic value test**

Append this test to `tests/test_relic_value.py`:

```python
def test_format_relic_value_marks_target_part_when_requested():
    report = RelicValueReport(
        relic_name="Lith B1",
        tier="Lith",
        is_vaulted=False,
        expected_platinum=2.5,
        expected_ducats=4.0,
        top_efficiency=None,
        rewards=[
            RelicRewardValue(
                part_name="Braton Prime Blueprint",
                item_id="braton_prime_blueprint",
                rarity="COMMON",
                chance=0.2533,
                sell_price=8,
                buy_price=5,
                valuation_price=5,
                ducats=15,
                ducats_per_plat=3.0,
                expected_platinum=1.27,
                expected_ducats=3.8,
                recommendation="均衡",
                warnings=[],
            )
        ],
        warnings=[],
    )

    text = format_relic_value_for_display(report, target_part="Braton Prime Blueprint")

    assert "目标部件" in text
    assert "Braton Prime Blueprint" in text
```

- [ ] **Step 3: Run contract tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_registry.py::test_handler_none_is_not_reported_as_success tests/test_relic_value.py::test_format_relic_value_marks_target_part_when_requested -q -p no:cacheprovider --basetemp output/pytest-tmp-tool-contracts
```

Expected: both fail before implementation.

- [ ] **Step 4: Treat `None` as no result**

In `warframe_agent/tool_registry.py`, inside `_coerce_handler_output_to_tool_result()`, before building successful metadata for non-`ToolResult` output, add:

```python
    if output is None:
        error = f"工具无结果: {tool_name}"
        return ToolResult(
            ok=False,
            error=error,
            metadata=_build_metadata(tool_name, arguments, False, error, started),
        )
```

- [ ] **Step 5: Add target-part display support**

In `warframe_agent/relic_value.py`, change the display function signature:

```python
def format_relic_value_for_display(report: RelicValueReport, target_part: str | None = None) -> str:
```

Inside it, after the header lines and before reward lines, add:

```python
    normalized_target = (target_part or "").strip().lower()
    if normalized_target:
        matched = [
            reward for reward in report.rewards
            if normalized_target in reward.part_name.lower() or normalized_target in reward.item_id.lower()
        ]
        if matched:
            lines.append(f"目标部件: {matched[0].part_name}，掉率 {matched[0].chance:.2%}，估值 {matched[0].valuation_price or '未知'}p")
        else:
            lines.append(f"目标部件: 未在该遗物奖励中找到 {target_part}")
```

Keep the existing reward list output unchanged after this block.

- [ ] **Step 6: Consume `target_part` in ChatAgent**

In `warframe_agent/chat.py`, inside `_tool_relic_value()`, add:

```python
        target_part = (args.get("target_part") or "").strip()
```

Change:

```python
        display = format_relic_value_for_display(report)
```

to:

```python
        display = format_relic_value_for_display(report, target_part=target_part or None)
```

- [ ] **Step 7: Verify tool contracts**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_registry.py tests/test_relic_value.py tests/test_chat.py::ChatTests::test_relic_value_command_returns_ev_and_safe_tool_context -q -p no:cacheprovider --basetemp output/pytest-tmp-tool-contracts
```

Expected: all selected tests pass.

## Task 6: Fix Web Chat Error Handling

**Files:**
- Modify: `warframe_agent/web/static/js/app.js`
- Modify: `warframe_agent/web/static/js/chat.js`
- Test: `tests/test_web_ui_playwright.py`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Add REST error UI regression**

In `tests/test_web_ui_playwright.py`, add a route in the existing page setup for `/api/chat` to return status `500` with JSON:

```python
await route.fulfill(
    status=500,
    content_type="application/json",
    body=json.dumps({"detail": "后端测试错误"}, ensure_ascii=False),
)
```

Add a test:

```python
def test_chat_rest_error_shows_backend_error_without_locking_input(page):
    page.route("**/ws/chat", lambda route: route.abort())
    page.route("**/api/chat", lambda route: route.fulfill(
        status=500,
        content_type="application/json",
        body=json.dumps({"detail": "后端测试错误"}, ensure_ascii=False),
    ))

    page.locator("#chat-input").fill("测试错误")
    page.locator("#send-btn").click()

    expect(page.locator(".message.agent").last()).to_contain_text("后端测试错误")
    expect(page.locator("#chat-input")).to_be_enabled()
```

- [ ] **Step 2: Add WebSocket error UI regression**

Add a mock WebSocket branch that sends:

```javascript
this.onmessage({ data: JSON.stringify({ status: 'error', message: 'message 无效' }) });
```

Add a test:

```python
def test_chat_websocket_error_replaces_loading_and_unlocks_input(page):
    page.evaluate("""
        window.MockChatWebSocketMode = 'error';
    """)

    page.locator("#chat-input").fill("x" * 5001)
    page.locator("#send-btn").click()

    expect(page.locator(".message.agent").last()).to_contain_text("message 无效")
    expect(page.locator("#chat-input")).to_be_enabled()
```

- [ ] **Step 3: Run failing Web UI tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py::test_chat_rest_error_shows_backend_error_without_locking_input tests/test_web_ui_playwright.py::test_chat_websocket_error_replaces_loading_and_unlocks_input -q -p no:cacheprovider --basetemp output/pytest-tmp-web-chat
```

Expected: tests fail because errors are not rendered correctly.

- [ ] **Step 4: Normalize REST chat errors**

In `warframe_agent/web/static/js/app.js`, change `sendChat()` to:

```javascript
async function sendChat(message) {
    const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        return {
            status: 'error',
            error: `HTTP ${res.status}`,
            message: data.detail || data.message || data.error || `请求失败: HTTP ${res.status}`
        };
    }
    return data;
}
```

- [ ] **Step 5: Add frontend error renderer**

In `warframe_agent/web/static/js/chat.js`, add near the chat helpers:

```javascript
function finishCurrentChatWithText(text) {
    if (currentStreamMsg) {
        const content = currentStreamMsg.querySelector('.message-content');
        if (content) {
            content.textContent = text;
        }
    }
    isTyping = false;
    currentStreamMsg = null;
    saveChatHistory();
}

function normalizeChatReply(data) {
    if (!data) return { ok: false, text: '错误: 服务器没有返回内容' };
    if (data.status === 'error' || data.error) {
        return { ok: false, text: data.message || data.error || '错误: 请求失败' };
    }
    return { ok: true, text: data.reply || '' };
}
```

- [ ] **Step 6: Handle WebSocket error messages**

In `chatWs.onmessage`, after JSON parse and before `processing`, add:

```javascript
        if (data.status === 'error') {
            finishCurrentChatWithText(data.message || '错误: 请求失败');
            return;
        }
```

Change every `isItemNotFoundResponse(data.reply)` call to guard with normalized text:

```javascript
                const reply = data.reply || '';
                if (isItemNotFoundResponse(reply) && query) {
                    currentStreamMsg.remove();
                    showItemNotFound(query);
                } else {
                    content.innerHTML = renderMarkdown(reply);
                    detectWhisperCommands(content);
                }
```

- [ ] **Step 7: Handle REST error result**

In the REST fallback block, replace direct `data.reply` handling with:

```javascript
                    const normalized = normalizeChatReply(data);
                    if (!normalized.ok) {
                        finishCurrentChatWithText(normalized.text);
                        return;
                    }
                    if (currentStreamMsg) {
                        const c = currentStreamMsg.querySelector('.message-content');
                        const q = currentStreamMsg.getAttribute('data-query') || '';
                        if (c) {
                            if (isItemNotFoundResponse(normalized.text) && q) {
                                currentStreamMsg.remove();
                                showItemNotFound(q);
                            } else {
                                c.innerHTML = renderMarkdown(normalized.text);
                                detectWhisperCommands(c);
                            }
                        }
                    }
```

Change `isItemNotFoundResponse()` to be safe for non-strings:

```javascript
function isItemNotFoundResponse(text) {
    const value = String(text || '');
    const patterns = ['没有找到', '未找到', '找不到', '无法找到', '未识别', '不认识'];
    return patterns.some(p => value.includes(p)) && value.includes('物品');
}
```

- [ ] **Step 8: Verify Web error behavior**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py::test_chat_rest_error_shows_backend_error_without_locking_input tests/test_web_ui_playwright.py::test_chat_websocket_error_replaces_loading_and_unlocks_input tests/test_web_api.py -q -p no:cacheprovider --basetemp output/pytest-tmp-web-chat
```

Expected: all selected tests pass.

## Task 7: Final Regression Suite And Documentation Note

**Files:**
- Modify: `md/rebuilt/02-feature-scope.md` only if behavior documentation is intentionally kept current.

- [ ] **Step 1: Run focused backend suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_bilibili_recommendations.py tests/test_chat.py tests/test_tool_router.py tests/test_set_profit.py tests/test_investment.py tests/test_mod_flipper.py tests/test_market_client.py tests/test_relic_value.py tests/test_web_api.py -q -p no:cacheprovider --basetemp output/pytest-tmp-final-backend
```

Expected: all selected tests pass.

- [ ] **Step 2: Run focused frontend suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py -q -p no:cacheprovider --basetemp output/pytest-tmp-final-ui
```

Expected: all selected tests pass or skip only for explicitly missing browser runtime.

- [ ] **Step 3: Manually verify the reviewed example questions**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from warframe_agent.chat import ChatAgent; a=ChatAgent(order_fetcher=lambda item_id: [], model_call=lambda prompt: 'BAD_MODEL_CALL', memory_path=Path('output/manual-review-memory.json')); print(a.answer('猴子该怎么配卡'))"
```

Expected output contains:

```text
暂未收录
配卡/攻略
B 站视频
```

Expected output does not contain:

```text
最低卖价
最高收价
BAD_MODEL_CALL
```

- [ ] **Step 4: Manually verify relic route predicates**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from warframe_agent.tool_router import select_candidate_tools; from warframe_agent.chat import _is_relic_value_intent, _is_relic_farming_intent; print(sorted(select_candidate_tools('这个遗物收益怎么样')), _is_relic_value_intent('这个遗物收益怎么样')); print(sorted(select_candidate_tools('哪个裂缝适合开这个核桃')), _is_relic_farming_intent('哪个裂缝适合开这个核桃'))"
```

Expected output shows `relic_value` in the first candidate list and `True`; `farming_route` in the second candidate list and `True`.

- [ ] **Step 5: Commit**

Run:

```powershell
git status --short
git add warframe_agent/chat.py warframe_agent/bilibili_recommendations.py warframe_agent/tool_router.py warframe_agent/tool_registry.py warframe_agent/set_profit.py warframe_agent/investment.py warframe_agent/mod_flipper.py warframe_agent/market.py warframe_agent/web/static/js/app.js warframe_agent/web/static/js/chat.js tests/test_bilibili_recommendations.py tests/test_chat.py tests/test_tool_router.py tests/test_set_profit.py tests/test_investment.py tests/test_mod_flipper.py tests/test_market_client.py tests/test_relic_value.py tests/test_web_api.py tests/test_web_ui_playwright.py
git commit -m "fix: correct chat routing and scan accuracy"
```

Expected: commit succeeds after tests pass.

## Self-Review

- Spec coverage: The plan covers the reviewed failures for guide/build chat, relic routing, scan truncation, order/rank consistency, tool no-result semantics, relic `target_part`, and Web chat errors.
- Placeholder scan: No task uses deferred implementation language; every code-changing task includes concrete snippets and verification commands.
- Type consistency: New helpers are plain functions or `ChatAgent` methods. Existing names used here are present in the codebase: `ChatAgent`, `ToolResult`, `ToolRegistry`, `ToolSpec`, `select_candidate_tools`, `best_sellers`, `scan_all_set_profits`, `scan_prime_investments`, and `scan_all_mod_flips`.
