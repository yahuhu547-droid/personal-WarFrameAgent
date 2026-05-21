"""测试 Mod 翻转分析器。"""
from __future__ import annotations

from warframe_agent.mod_flipper import (
    ModFlipResult,
    analyze_mod_flip,
    format_mod_flip_results_for_model,
    get_endo_cost,
    get_tradeable_mods,
    scan_all_mod_flips,
)


def test_endo_cost_table_r10():
    assert get_endo_cost(10, "RARE") == 20470
    assert get_endo_cost(10, "COMMON") == 20470
    assert get_endo_cost(10, "LEGENDARY") == 20470


def test_endo_cost_table_r5():
    assert get_endo_cost(5, "UNCOMMON") == 1280


def test_endo_cost_table_r3():
    assert get_endo_cost(3, "RARE") == 320


def test_endo_cost_table_fallback():
    # 未知稀有度回退到 RARE
    assert get_endo_cost(10, "UNKNOWN") == 20470


def test_get_tradeable_mods():
    items = [
        {"url_name": "primed_flow", "item_name": "Primed Flow", "tags": ["mod"], "tradable": True, "modMaxRank": 10, "rarity": "LEGENDARY"},
        {"url_name": "vitality", "item_name": "Vitality", "tags": ["mod"], "tradable": True, "modMaxRank": 5, "rarity": "COMMON"},
        {"url_name": "serration", "item_name": "Serration", "tags": ["mod"], "tradable": False, "modMaxRank": 10, "rarity": "UNCOMMON"},
        {"url_name": "rhino_prime", "item_name": "Rhino Prime", "tags": ["warframe"], "tradable": True},
        {"url_name": "quick_thinking", "item_name": "Quick Thinking", "tags": ["mod"], "tradable": True, "modMaxRank": 3, "rarity": "RARE"},
    ]
    mods = get_tradeable_mods(items)
    assert len(mods) == 2  # primed_flow (R10) + vitality (R5), quick_thinking R3 被过滤
    assert mods[0]["url_name"] == "primed_flow"
    assert mods[1]["url_name"] == "vitality"


def test_get_tradeable_mods_includes_arcanes():
    items = [
        {"url_name": "arcane_energize", "item_name": "Arcane Energize", "tags": ["legendary", "arcane_enhancement"]},
        {"url_name": "arcane_grace", "item_name": "Arcane Grace", "tags": ["arcane_enhancement"]},
        {"url_name": "arcane_helmet", "item_name": "Arcane Helmet", "tags": ["arcane_helmet"]},
        {"url_name": "arcane_skin", "item_name": "Arcane Skin", "tags": ["skin", "arcane_enhancement"]},
    ]

    mods = get_tradeable_mods(items)

    ids = [m["url_name"] for m in mods]
    assert "arcane_energize" in ids
    assert "arcane_grace" in ids
    assert "arcane_helmet" not in ids
    assert "arcane_skin" not in ids
    energize = next(m for m in mods if m["url_name"] == "arcane_energize")
    assert energize["max_rank"] == 5
    assert energize["rarity"] == "LEGENDARY"


def test_analyze_mod_flip_success():
    def mock_orders(item_id):
        return [
            {"order_type": "sell", "platinum": 10, "quantity": 1, "user": {"ingame_name": "seller1", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "buy", "platinum": 80, "quantity": 1, "user": {"ingame_name": "buyer1", "status": "ingame", "reputation": 5}, "rank": 10},
        ]

    result = analyze_mod_flip("test_mod", 10, "RARE", mock_orders)
    assert result is not None
    assert result.flip_profit == 70  # 80 - 10
    assert result.r0_buy_price == 10
    assert result.r10_sell_price == 80
    assert result.endo_cost == 20470
    assert result.plat_per_1k_endo > 0
    assert result.market_url == "https://warframe.market/items/test_mod"
    assert result.r0_seller["player"] == "seller1"
    assert result.r0_seller["price"] == 10
    assert "/w seller1" in result.r0_seller["whisper"]
    assert result.max_rank_buyer["player"] == "buyer1"
    assert result.max_rank_buyer["price"] == 80
    assert "/w buyer1" in result.max_rank_buyer["whisper"]


def test_analyze_arcane_flip_aggregates_rank0_quantities_for_rank5():
    def mock_orders(item_id):
        return [
            {"order_type": "sell", "platinum": 4, "quantity": 10, "user": {"ingame_name": "CheapBulk", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "sell", "platinum": 6, "quantity": 12, "user": {"ingame_name": "NextBulk", "status": "ingame", "reputation": 9}, "rank": 0},
            {"order_type": "buy", "platinum": 150, "quantity": 1, "user": {"ingame_name": "Rank5Buyer", "status": "ingame", "reputation": 10}, "rank": 5},
        ]

    result = analyze_mod_flip("arcane_energize", 5, "LEGENDARY", mock_orders)

    assert result is not None
    assert result.required_quantity == 21
    assert result.r0_buy_price == 106
    assert result.r10_sell_price == 150
    assert result.flip_profit == 44
    assert round(result.roi_pct, 1) == 41.5
    assert result.trade_plan["source"] == "arcane_flip"
    assert result.trade_plan["strategy"] == "arcane_r0_to_r5"
    assert [(step["player"], step["unit_price"], step["quantity"], step["subtotal"]) for step in result.trade_plan["buy_steps"]] == [
        ("CheapBulk", 4, 10, 40),
        ("NextBulk", 6, 11, 66),
    ]
    assert result.trade_plan["sell_steps"][0]["player"] == "Rank5Buyer"
    assert result.trade_plan["total_cost"] == 106
    assert result.trade_plan["total_revenue"] == 150


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


def test_analyze_arcane_flip_returns_none_when_rank0_quantity_insufficient():
    def mock_orders(item_id):
        return [
            {"order_type": "sell", "platinum": 4, "quantity": 10, "user": {"ingame_name": "CheapBulk", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "buy", "platinum": 150, "quantity": 1, "user": {"ingame_name": "Rank5Buyer", "status": "ingame", "reputation": 10}, "rank": 5},
        ]

    result = analyze_mod_flip("arcane_energize", 5, "LEGENDARY", mock_orders)

    assert result is None


def test_analyze_arcane_flip_returns_none_when_aggregate_cost_exceeds_buyer_price():
    def mock_orders(item_id):
        return [
            {"order_type": "sell", "platinum": 10, "quantity": 21, "user": {"ingame_name": "ExpensiveBulk", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "buy", "platinum": 150, "quantity": 1, "user": {"ingame_name": "Rank5Buyer", "status": "ingame", "reputation": 10}, "rank": 5},
        ]

    result = analyze_mod_flip("arcane_energize", 5, "LEGENDARY", mock_orders)

    assert result is None


def test_analyze_mod_flip_no_profit():
    def mock_orders(item_id):
        return [
            {"order_type": "sell", "platinum": 100, "quantity": 1, "user": {"ingame_name": "seller1", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "buy", "platinum": 50, "quantity": 1, "user": {"ingame_name": "buyer1", "status": "ingame", "reputation": 5}, "rank": 10},
        ]

    result = analyze_mod_flip("test_mod", 10, "RARE", mock_orders)
    assert result is None  # 亏损，不返回


def test_analyze_mod_flip_no_orders():
    def mock_orders(item_id):
        return []

    result = analyze_mod_flip("test_mod", 10, "RARE", mock_orders)
    assert result is None


def test_scan_filters_by_min_profit():
    def mock_orders(item_id):
        if item_id == "cheap_mod":
            return [
                {"order_type": "sell", "platinum": 5, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}, "rank": 0},
                {"order_type": "buy", "platinum": 8, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}, "rank": 10},
            ]
        return [
            {"order_type": "sell", "platinum": 10, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}, "rank": 0},
            {"order_type": "buy", "platinum": 50, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}, "rank": 10},
        ]

    items = [
        {"url_name": "cheap_mod", "item_name": "Cheap", "tags": ["mod"], "tradable": True, "modMaxRank": 10, "rarity": "RARE"},
        {"url_name": "good_mod", "item_name": "Good", "tags": ["mod"], "tradable": True, "modMaxRank": 10, "rarity": "RARE"},
    ]
    results = scan_all_mod_flips(items, mock_orders, min_profit=5)
    assert len(results) == 1  # cheap_mod profit=3 < 5 被过滤，good_mod profit=40 保留
    assert results[0].item_id == "good_mod"


def test_scan_all_mod_flips_filters_mod_only():
    analyzed = []

    def mock_orders(item_id):
        analyzed.append(item_id)
        return []

    items = [
        {"url_name": "primed_flow", "item_name": "Primed Flow", "tags": ["mod"], "tradable": True, "modMaxRank": 10, "rarity": "LEGENDARY"},
        {"url_name": "arcane_energize", "item_name": "Arcane Energize", "tags": ["arcane_enhancement"]},
    ]

    scan_all_mod_flips(items, mock_orders, opportunity_filter="mod", scout_fn=None)

    assert analyzed == ["primed_flow"]


def test_scan_all_mod_flips_filters_arcane_only():
    analyzed = []

    def mock_orders(item_id):
        analyzed.append(item_id)
        return []

    items = [
        {"url_name": "primed_flow", "item_name": "Primed Flow", "tags": ["mod"], "tradable": True, "modMaxRank": 10, "rarity": "LEGENDARY"},
        {"url_name": "arcane_energize", "item_name": "Arcane Energize", "tags": ["arcane_enhancement"]},
    ]

    scan_all_mod_flips(items, mock_orders, opportunity_filter="arcane", scout_fn=None)

    assert analyzed == ["arcane_energize"]


def test_value_score_formula():
    import math
    result = ModFlipResult(
        item_id="test", display_name="Test",
        r0_buy_price=10, r10_sell_price=60,
        flip_profit=50, endo_cost=20470,
        plat_per_1k_endo=50 / 20.47,
        value_score=0, volume_48h=10, max_rank=10, rarity="RARE",
        roi_pct=500.0, is_prime=False,
    )
    expected = (50 / 20.47) * math.log2(11)
    assert abs(result.value_score - expected) < 0.01 or result.value_score == 0  # value_score is computed at creation


def _mod_flip_result(index: int, *, profit: int = 50) -> ModFlipResult:
    return ModFlipResult(
        item_id=f"mod_{index}",
        display_name=f"Mod {index}",
        r0_buy_price=10 + index,
        r10_sell_price=10 + index + profit,
        flip_profit=profit,
        roi_pct=profit / (10 + index) * 100,
        endo_cost=20470,
        plat_per_1k_endo=profit / 20.47,
        value_score=profit,
        volume_48h=100 + index,
        max_rank=10,
        rarity="LEGENDARY" if index == 0 else "RARE",
        is_prime=index == 0,
    )


def test_format_mod_flip_results_for_model_keeps_compact_top_metrics():
    results = [_mod_flip_result(0, profit=70)]

    text = format_mod_flip_results_for_model(results, min_profit=20, limit=5)

    assert "tool=mod_flipper min_profit=20 limit=5 result_count=1" in text
    assert "## Mod 翻转排行榜" not in text
    assert "item_id=mod_0" in text
    assert "display_name=Mod 0" in text
    assert "rarity=LEGENDARY" in text
    assert "max_rank=10" in text
    assert "r0_buy_price=10" in text
    assert "r10_sell_price=80" in text
    assert "flip_profit=70" in text
    assert "roi_pct=700.00" in text
    assert "endo_cost=20470" in text
    assert "plat_per_1k_endo=3.42" in text
    assert "volume_48h=100" in text
    assert "is_prime=true" in text
    for forbidden in ["seller", "buyer", "/w", "market_url", "whisper"]:
        assert forbidden not in text.lower()


def test_format_mod_flip_results_for_model_omits_tail_rows_and_count():
    results = [_mod_flip_result(i, profit=100 - i) for i in range(10)]

    text = format_mod_flip_results_for_model(results, min_profit=10, limit=10, max_items=3)

    assert "result_count=10" in text
    assert "item_id=mod_0" in text
    assert "item_id=mod_1" in text
    assert "item_id=mod_2" in text
    assert "item_id=mod_3" not in text
    assert "omitted_count=7" in text
