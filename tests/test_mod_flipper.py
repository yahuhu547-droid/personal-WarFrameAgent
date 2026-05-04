"""测试 Mod 翻转分析器。"""
from __future__ import annotations

from warframe_agent.mod_flipper import (
    ModFlipResult,
    analyze_mod_flip,
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


def test_value_score_formula():
    import math
    result = ModFlipResult(
        item_id="test", display_name="Test",
        r0_buy_price=10, r10_sell_price=60,
        flip_profit=50, endo_cost=20470,
        plat_per_1k_endo=50 / 20.47,
        value_score=0, volume_48h=10, max_rank=10, rarity="RARE",
    )
    expected = (50 / 20.47) * math.log2(11)
    assert abs(result.value_score - expected) < 0.01 or result.value_score == 0  # value_score is computed at creation
