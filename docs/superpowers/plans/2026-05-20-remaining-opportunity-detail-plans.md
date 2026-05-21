# Remaining Opportunity Detail Plans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make opportunity ID lookup replies generate clear executable plans for remaining opportunity types: Prime weapons, arcanes, and mods, while keeping already-covered warframe/Prime Set behavior intact.

**Architecture:** Reuse the existing `trade_plan` schema and short-term `OpportunityLookupStore`; improve only the lookup reply formatter and regression tests so plans are rendered by strategy/source. Keep arcane cost calculation in `mod_flipper.py` using existing `build_buy_plan()` but add the exact requested quantity-tier regression. Prime weapons continue through the same Set-order path as warframes, with clearer repeated-part wording support in the formatter.

**Tech Stack:** Python, pytest, existing `warframe_agent` modules (`opportunity_lookup`, `mod_flipper`, `market`, `trade_plan`).

---

## File structure

- Modify `warframe_agent/opportunity_lookup.py`: classify lookup replies by `trade_plan.source`/`strategy`, add arcane/mod section titles and repeated-part line support.
- Modify `tests/test_opportunity_lookup.py`: add reply-format tests for Prime weapon, arcane quantity-tier, and normal mod plans.
- Modify `tests/test_mod_flipper.py`: add exact arcane aggregation regression for `7p × 5 + 9p × 16`.
- Modify `tests/test_market_formatter.py`: add exact generic `build_buy_plan()` regression for `7p × 5 + 9p × 16`.
- Update `md/rebuilt/05-data-memory.md` and `md/rebuilt/07-operations-testing.md` with the remaining plan behavior.

## Task 1: Exact arcane quantity-tier regression

**Files:**
- Modify: `tests/test_market_formatter.py`
- Modify: `tests/test_mod_flipper.py`

- [x] **Step 1: Add failing/golden test for generic buy aggregation**

In `tests/test_market_formatter.py`, inside `TestTradeFormatting`, add:

```python
    def test_build_buy_plan_uses_partial_quantity_from_next_price_tier(self):
        orders = [
            {"order_type": "sell", "platinum": 7, "quantity": 5, "user": {"ingame_name": "SevenPlat", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "sell", "platinum": 9, "quantity": 22, "user": {"ingame_name": "NinePlat", "status": "ingame", "reputation": 9}, "rank": 0},
        ]

        plan = build_buy_plan(orders, needed=21, rank_filter=0)

        self.assertTrue(plan.fulfilled)
        self.assertEqual(plan.total_quantity, 21)
        self.assertEqual(plan.total_cost, 179)
        self.assertEqual([(entry.user_name, entry.platinum, entry.quantity, entry.subtotal) for entry in plan.entries], [
            ("SevenPlat", 7, 5, 35),
            ("NinePlat", 9, 16, 144),
        ])
```

- [x] **Step 2: Add arcane analyzer regression**

In `tests/test_mod_flipper.py`, after `test_analyze_arcane_flip_aggregates_rank0_quantities_for_rank5`, add:

```python
def test_analyze_arcane_flip_uses_partial_quantity_from_next_price_tier():
    def mock_orders(item_id):
        return [
            {"order_type": "sell", "platinum": 7, "quantity": 5, "user": {"ingame_name": "SevenPlat", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "sell", "platinum": 9, "quantity": 22, "user": {"ingame_name": "NinePlat", "status": "ingame", "reputation": 9}, "rank": 0},
            {"order_type": "buy", "platinum": 210, "quantity": 1, "user": {"ingame_name": "Rank5Buyer", "status": "ingame", "reputation": 10}, "rank": 5},
        ]

    result = analyze_mod_flip("arcane_energize", 5, "LEGENDARY", mock_orders)

    assert result is not None
    assert result.required_quantity == 21
    assert result.r0_buy_price == 179
    assert result.r10_sell_price == 210
    assert result.flip_profit == 31
    assert round(result.roi_pct, 1) == 17.3
    assert [(step["player"], step["unit_price"], step["quantity"], step["subtotal"]) for step in result.trade_plan["buy_steps"]] == [
        ("SevenPlat", 7, 5, 35),
        ("NinePlat", 9, 16, 144),
    ]
    assert result.trade_plan["total_cost"] == 179
    assert result.trade_plan["total_revenue"] == 210
    assert result.trade_plan["profit"] == 31
```

- [x] **Step 3: Run regression tests**

Run:

```bash
python -m pytest tests/test_market_formatter.py::TestTradeFormatting::test_build_buy_plan_uses_partial_quantity_from_next_price_tier tests/test_mod_flipper.py::test_analyze_arcane_flip_uses_partial_quantity_from_next_price_tier -v
```

Expected: PASS if existing aggregation is correct. If it fails, fix `warframe_agent/market.py:238-265` so `build_buy_plan()` takes only the remaining quantity from a larger seller stack, then rerun.

## Task 2: Opportunity lookup formatter for Prime weapons, arcanes, and mods

**Files:**
- Modify: `tests/test_opportunity_lookup.py`
- Modify: `warframe_agent/opportunity_lookup.py`

- [x] **Step 1: Add Prime weapon lookup reply test**

Add to `tests/test_opportunity_lookup.py`:

```python
def test_format_reply_for_prime_weapon_set_order_mentions_component_delivery(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    plan = {
        "display_name": "Akbolto Prime",
        "display_strategy": "拆件买入 -> 完整套装订单卖出",
        "strategy": "buy_parts_sell_set",
        "item_id": "akbolto_prime_set",
        "total_cost": 39,
        "total_revenue": 80,
        "profit": 35,
        "roi_pct": 89.7,
        "risk_level": "medium",
        "buy_steps": [
            {"label": "Akbolto Prime Blueprint", "player": "BlueprintSeller", "unit_price": 10, "quantity": 1, "subtotal": 10, "market_url": "https://warframe.market/items/akbolto_prime_blueprint", "profile_url": "https://warframe.market/profile/BlueprintSeller", "whisper": "/w BlueprintSeller Hi! I want to buy."},
            {"label": "Akbolto Prime Link", "player": "LinkSeller", "unit_price": 17, "quantity": 1, "subtotal": 17, "market_url": "https://warframe.market/items/akbolto_prime_link", "profile_url": "https://warframe.market/profile/LinkSeller", "whisper": "/w LinkSeller Hi! I want to buy."},
        ],
        "sell_steps": [
            {"label": "Akbolto Prime Set", "player": "SetBuyer", "unit_price": 80, "quantity": 1, "subtotal": 80, "market_url": "https://warframe.market/items/akbolto_prime_set", "profile_url": "https://warframe.market/profile/SetBuyer", "whisper": "/w SetBuyer Hi! I want to sell."},
        ],
    }
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", plan)

    text = format_opportunity_lookup_reply(store.get(lookup_id), now=now)

    assert "说明：Set 订单不是单独物品，游戏内需交付全部对应部件。" in text
    assert "需要买入的部件：" in text
    assert "完整套装订单买家：" in text
    assert "Akbolto Prime Blueprint" in text
    assert "Akbolto Prime Link" in text
```

- [x] **Step 2: Add arcane lookup reply test**

Add to `tests/test_opportunity_lookup.py`:

```python
def test_format_reply_for_arcane_flip_shows_quantity_tiers(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    plan = {
        "source": "arcane_flip",
        "display_name": "Arcane Energize",
        "display_strategy": "买 21 个 R0 -> 合成 R5 -> 卖出",
        "strategy": "arcane_r0_to_r5",
        "item_id": "arcane_energize",
        "required_quantity": 21,
        "total_cost": 179,
        "total_revenue": 210,
        "profit": 31,
        "roi_pct": 17.3,
        "risk_level": "medium",
        "buy_steps": [
            {"label": "买入 R0", "player": "SevenPlat", "unit_price": 7, "quantity": 5, "subtotal": 35, "market_url": "https://warframe.market/items/arcane_energize", "profile_url": "https://warframe.market/profile/SevenPlat", "whisper": "/w SevenPlat Hi! I want to buy."},
            {"label": "买入 R0", "player": "NinePlat", "unit_price": 9, "quantity": 16, "subtotal": 144, "market_url": "https://warframe.market/items/arcane_energize", "profile_url": "https://warframe.market/profile/NinePlat", "whisper": "/w NinePlat Hi! I want to buy."},
        ],
        "sell_steps": [
            {"label": "出售 R5", "player": "Rank5Buyer", "unit_price": 210, "quantity": 1, "subtotal": 210, "market_url": "https://warframe.market/items/arcane_energize", "profile_url": "https://warframe.market/profile/Rank5Buyer", "whisper": "/w Rank5Buyer Hi! I want to sell."},
        ],
    }
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("arcane_energize", "Arcane Energize", plan)

    text = format_opportunity_lookup_reply(store.get(lookup_id), now=now)

    assert "赋能满级合成买入：需要 R0 × 21" in text
    assert "SevenPlat — 7p × 5 = 35p" in text
    assert "NinePlat — 9p × 16 = 144p" in text
    assert "满级赋能卖出买家：" in text
    assert "Rank5Buyer" in text
    assert "预计利润：+31p" in text
```

- [x] **Step 3: Add normal mod lookup reply test**

Add to `tests/test_opportunity_lookup.py`:

```python
def test_format_reply_for_mod_flip_does_not_describe_arcane_quantity_synthesis(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    plan = {
        "source": "mod_flip",
        "display_name": "Primed Flow",
        "display_strategy": "买 R0 -> 升到 R10 -> 卖出",
        "strategy": "mod_r0_to_r10",
        "item_id": "primed_flow",
        "required_quantity": 1,
        "total_cost": 40,
        "total_revenue": 120,
        "profit": 80,
        "roi_pct": 200.0,
        "risk_level": "medium",
        "buy_steps": [
            {"label": "买入 R0", "player": "ModSeller", "unit_price": 40, "quantity": 1, "subtotal": 40, "market_url": "https://warframe.market/items/primed_flow", "profile_url": "https://warframe.market/profile/ModSeller", "whisper": "/w ModSeller Hi! I want to buy."},
        ],
        "sell_steps": [
            {"label": "出售 R10", "player": "ModBuyer", "unit_price": 120, "quantity": 1, "subtotal": 120, "market_url": "https://warframe.market/items/primed_flow", "profile_url": "https://warframe.market/profile/ModBuyer", "whisper": "/w ModBuyer Hi! I want to sell."},
        ],
    }
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("primed_flow", "Primed Flow", plan)

    text = format_opportunity_lookup_reply(store.get(lookup_id), now=now)

    assert "MOD 升级买入：" in text
    assert "满级 MOD 卖出买家：" in text
    assert "赋能满级合成买入" not in text
    assert "需要 R0 × 21" not in text
    assert "ModSeller" in text
    assert "ModBuyer" in text
```

- [x] **Step 4: Run formatter tests to verify current gaps**

Run:

```bash
python -m pytest tests/test_opportunity_lookup.py -v
```

Expected: at least the arcane/mod title tests fail because the formatter currently uses generic `买入：`/`卖出：` for non-set plans.

- [x] **Step 5: Implement source-aware section titles**

In `warframe_agent/opportunity_lookup.py`, replace `_buy_section_title()` and `_sell_section_title()` with:

```python
def _buy_section_title(plan: dict[str, Any]) -> str:
    source = str(plan.get("source") or "")
    strategy = str(plan.get("strategy") or "")
    if source == "arcane_flip" or strategy.startswith("arcane_r0_to_r"):
        required = plan.get("required_quantity") or sum(int(step.get("quantity") or 0) for step in plan.get("buy_steps") or [])
        return f"赋能满级合成买入：需要 R0 × {required}"
    if source == "mod_flip" or strategy.startswith("mod_r0_to_r"):
        return "MOD 升级买入："
    if strategy == "buy_set_sell_parts":
        return "买入完整套装订单：需确认卖家能一次性交付全部部件"
    return "需要买入的部件：" if _looks_like_set_plan(plan) else "买入："


def _sell_section_title(plan: dict[str, Any]) -> str:
    source = str(plan.get("source") or "")
    strategy = str(plan.get("strategy") or "")
    if source == "arcane_flip" or strategy.startswith("arcane_r0_to_r"):
        return "满级赋能卖出买家："
    if source == "mod_flip" or strategy.startswith("mod_r0_to_r"):
        return "满级 MOD 卖出买家："
    if strategy == "buy_set_sell_parts":
        return "拆分卖出部件：逐个匹配部件买家"
    return "完整套装订单买家：" if _looks_like_set_plan(plan) else "卖出："
```

- [x] **Step 6: Improve repeated-part display in `_format_steps()`**

In `warframe_agent/opportunity_lookup.py`, keep the existing line format because it already renders quantity:

```python
lines.append(f"{index}. {label} — {player} — {unit_price}p × {quantity} = {subtotal}p")
```

Add no new code unless tests show repeated quantities are hidden. This line displays `× 2` for repeated Prime weapon components.

- [x] **Step 7: Run formatter tests**

Run:

```bash
python -m pytest tests/test_opportunity_lookup.py -v
```

Expected: PASS.

## Task 3: Documentation update for remaining types

**Files:**
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/07-operations-testing.md`

- [x] **Step 1: Update data/memory doc**

In `md/rebuilt/05-data-memory.md`, extend the `机会 ID 短期详情` paragraph to mention:

```markdown
ID 回复会按 `trade_plan.source`/`strategy` 展示不同计划：Prime 武器/战甲按完整套装订单说明部件交付；赋能按 R0 数量阶梯聚合买入并显示满级卖出买家；普通 MOD 显示 R0/低级买入与满级卖出，不按赋能的 21 个 R0 合成规则计算。
```

- [x] **Step 2: Update operations/testing doc**

In `md/rebuilt/07-operations-testing.md`, extend `交易机会 ID 验证` with:

```markdown
赋能机会应重点检查数量阶梯，例如 7p 库存 5 个、9p 库存 22 个、需求 21 个时，回复应显示 `7p × 5` 和 `9p × 16`，总成本 179p。普通 MOD 不应显示“需要 R0 × 21”。Prime 武器 Set 应和战甲 Set 一样说明游戏内需交付完整部件组合。
```

## Task 4: Validation

**Files:** all modified files.

- [x] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_market_formatter.py::TestTradeFormatting::test_build_buy_plan_uses_partial_quantity_from_next_price_tier tests/test_mod_flipper.py::test_analyze_arcane_flip_uses_partial_quantity_from_next_price_tier tests/test_opportunity_lookup.py -v
```

Expected: PASS.

- [x] **Step 2: Run broader relevant tests**

Run:

```bash
python -m pytest tests/test_market_formatter.py tests/test_mod_flipper.py tests/test_opportunity_lookup.py tests/test_chat.py tests/test_push.py tests/test_feishu.py -v
```

Expected: PASS.

- [x] **Step 3: Inspect diff**

Run:

```bash
git diff -- warframe_agent/opportunity_lookup.py tests/test_opportunity_lookup.py tests/test_mod_flipper.py tests/test_market_formatter.py md/rebuilt/05-data-memory.md md/rebuilt/07-operations-testing.md docs/superpowers/plans/2026-05-20-remaining-opportunity-detail-plans.md
```

Expected: Diff only includes remaining opportunity detail plan formatter/tests/docs and this plan file.

---

## Self-review

Spec coverage:
- Prime weapon Set wording: Task 2 tests existing Set path for a weapon item.
- Arcane tiered R0 aggregation: Task 1 exact calculation and Task 2 lookup reply.
- MOD non-arcane behavior: Task 2 normal mod reply test.
- Documentation updates: Task 3.
- No commits: this plan intentionally omits commit steps because the user asked not to submit/commit previous work.

Placeholder scan: no TBD/TODO placeholders remain.

Type consistency: `source`, `strategy`, `required_quantity`, `buy_steps`, `sell_steps`, and section title helpers match the existing `trade_plan` schema.
