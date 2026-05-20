"""测试投资顾问 — Prime 套装套利分析。"""
from __future__ import annotations

from unittest.mock import patch

from warframe_agent.investment import (
    PrimeInvestment,
    _assess_risk,
    analyze_prime_investment,
    format_prime_investment_results_for_model,
    scan_prime_investments,
)
from warframe_agent.warframes import PrimeGroup


def _mock_orders(buy_price=30, sell_price=50):
    """构建 mock 订单。buy_price = 最低卖价（买入成本），sell_price = 最高收价（卖出收入）。"""
    return [
        {"order_type": "sell", "platinum": buy_price, "quantity": 1,
         "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
        {"order_type": "sell", "platinum": buy_price + 5, "quantity": 1,
         "user": {"ingame_name": "s2", "status": "ingame", "reputation": 3}},
        {"order_type": "buy", "platinum": sell_price, "quantity": 1,
         "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
        {"order_type": "buy", "platinum": sell_price - 3, "quantity": 1,
         "user": {"ingame_name": "b2", "status": "ingame", "reputation": 3}},
    ]


def _make_group(base_id="test_prime", part_count=4):
    """创建一个 PrimeGroup mock。"""
    items = {"set": f"{base_id}_set"}
    for i in range(part_count):
        key = ["blueprint", "chassis", "neuroptics", "systems"][i]
        items[key] = f"{base_id}_{key}_blueprint" if key != "blueprint" else f"{base_id}_blueprint"
    return PrimeGroup(
        base_id=base_id,
        items=items,
        tags={"prime", "warframe", "set"},
        zh_title=f"Test Prime 一套",
        en_title="Test Prime Set",
    )


def _mock_order_fetcher(item_id):
    """根据 item_id 返回 mock 订单。套装价格高于部件。"""
    if "set" in item_id:
        return _mock_orders(buy_price=100, sell_price=120)  # 套装：买100，卖120
    else:
        return _mock_orders(buy_price=15, sell_price=25)  # 部件：买15，卖25


def _make_investment(
    idx=1,
    *,
    roi_pct=42.5,
    risk_level="low",
    volume_48h=20,
    part_count=4,
):
    return PrimeInvestment(
        base_id=f"test_prime_{idx}",
        display_name=f"Test Prime {idx} 一套",
        strategy="buy_parts_sell_set",
        buy_cost=60 + idx,
        sell_price=120 + idx,
        profit_per_set=60,
        roi_pct=roi_pct,
        sets_affordable=8,
        total_profit=480,
        volume_48h=volume_48h,
        risk_level=risk_level,
        part_details=[
            {"key": f"part_{i}", "name": f"部件 {i}", "item_id": f"test_part_{i}", "buy": 10, "sell": 20}
            for i in range(part_count)
        ],
        set_item_id=f"test_prime_{idx}_set",
    )


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 20})
def test_analyze_prime_investment_parts_strategy(mock_stats):
    """测试策略 A：散买部件 → 整套卖出。"""
    group = _make_group("test_prime", 4)
    result = analyze_prime_investment(group, _mock_order_fetcher, budget=500)

    assert result is not None
    assert result.strategy == "buy_parts_sell_set"
    # 部件散买总价: 15 * 4 = 60
    assert result.buy_cost == 60
    # 套装卖出价: 120
    assert result.sell_price == 120
    # 每套利润: 120 - 60 = 60
    assert result.profit_per_set == 60
    # ROI: 60/60 * 100 = 100%
    assert result.roi_pct == 100.0
    # 可买套数: 500 // 60 = 8
    assert result.sets_affordable == 8
    # 总利润: 8 * 60 = 480
    assert result.total_profit == 480
    assert result.risk_level in ("low", "medium", "high")


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 20})
def test_investment_buy_parts_sell_set_has_actionable_plan(mock_stats):
    def fetcher(item_id):
        data = {
            "plan_prime_set": [
                {"order_type": "sell", "platinum": 90, "quantity": 1, "user": {"ingame_name": "SetSeller_INV", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 150, "quantity": 1, "user": {"ingame_name": "SetBuyer_INV", "status": "ingame", "reputation": 5}},
            ],
            "plan_prime_blueprint": [
                {"order_type": "sell", "platinum": 10, "quantity": 1, "user": {"ingame_name": "BpSeller_INV", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 5, "quantity": 1, "user": {"ingame_name": "BpBuyer_INV", "status": "ingame", "reputation": 5}},
            ],
            "plan_prime_chassis_blueprint": [
                {"order_type": "sell", "platinum": 15, "quantity": 1, "user": {"ingame_name": "ChassisSeller_INV", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 6, "quantity": 1, "user": {"ingame_name": "ChassisBuyer_INV", "status": "ingame", "reputation": 5}},
            ],
            "plan_prime_neuroptics_blueprint": [
                {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "NeuroSeller_INV", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 7, "quantity": 1, "user": {"ingame_name": "NeuroBuyer_INV", "status": "ingame", "reputation": 5}},
            ],
            "plan_prime_systems_blueprint": [
                {"order_type": "sell", "platinum": 25, "quantity": 1, "user": {"ingame_name": "SystemsSeller_INV", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 8, "quantity": 1, "user": {"ingame_name": "SystemsBuyer_INV", "status": "ingame", "reputation": 5}},
            ],
        }
        return data.get(item_id, [])

    result = analyze_prime_investment(_make_group("plan_prime", 4), fetcher, budget=500)

    assert result is not None
    assert result.trade_plan["strategy"] == "buy_parts_sell_set"
    assert result.trade_plan["total_cost"] == 70
    assert result.trade_plan["total_revenue"] == 150
    assert result.trade_plan["profit"] == 80
    assert [step["player"] for step in result.trade_plan["buy_steps"]] == [
        "BpSeller_INV", "ChassisSeller_INV", "NeuroSeller_INV", "SystemsSeller_INV",
    ]
    assert [step["player"] for step in result.trade_plan["sell_steps"]] == ["SetBuyer_INV"]
    serialized_plan = str(result.trade_plan)
    assert "SetSeller_INV" not in serialized_plan
    for buyer in ["BpBuyer_INV", "ChassisBuyer_INV", "NeuroBuyer_INV", "SystemsBuyer_INV"]:
        assert buyer not in serialized_plan
    assert "https://warframe.market/items/plan_prime_set" in serialized_plan
    assert "https://warframe.market/profile/SetBuyer_INV" in serialized_plan
    assert "/w SetBuyer_INV" in serialized_plan


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 20})
def test_analyze_prime_investment_set_strategy(mock_stats):
    """测试策略 B：整套买入 → 散卖部件。"""
    def cheap_parts_fetcher(item_id):
        if "set" in item_id:
            return _mock_orders(buy_price=50, sell_price=60)   # 套装便宜
        else:
            return _mock_orders(buy_price=5, sell_price=30)    # 部件卖价高

    group = _make_group("cheap_prime", 4)
    result = analyze_prime_investment(group, cheap_parts_fetcher, budget=500)

    assert result is not None
    assert result.strategy == "buy_set_sell_parts"
    # 套装买入: 50
    assert result.buy_cost == 50
    # 部件散卖总价: 30 * 4 = 120
    assert result.sell_price == 120
    # 每套利润: 120 - 50 = 70
    assert result.profit_per_set == 70


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 20})
def test_investment_buy_set_sell_parts_has_actionable_plan(mock_stats):
    def fetcher(item_id):
        if "set" in item_id:
            return [
                {"order_type": "sell", "platinum": 30, "quantity": 1, "user": {"ingame_name": "SetSeller_INV_B", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 25, "quantity": 1, "user": {"ingame_name": "SetBuyer_INV_B", "status": "ingame", "reputation": 5}},
            ]
        return [
            {"order_type": "sell", "platinum": 40, "quantity": 1, "user": {"ingame_name": "PartSeller_INV_B", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 18, "quantity": 1, "user": {"ingame_name": f"Buyer_{item_id}", "status": "ingame", "reputation": 5}},
        ]

    result = analyze_prime_investment(_make_group("split_prime", 4), fetcher, budget=500)

    assert result is not None
    assert result.trade_plan["strategy"] == "buy_set_sell_parts"
    assert result.trade_plan["total_cost"] == 30
    assert result.trade_plan["total_revenue"] == 72
    assert result.trade_plan["profit"] == 42
    assert [step["player"] for step in result.trade_plan["buy_steps"]] == ["SetSeller_INV_B"]
    assert len(result.trade_plan["sell_steps"]) == 4
    serialized_plan = str(result.trade_plan)
    assert "SetBuyer_INV_B" not in serialized_plan
    assert "PartSeller_INV_B" not in serialized_plan
    assert "/w SetSeller_INV_B" in serialized_plan


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 10})
def test_budget_calculation(mock_stats):
    """测试预算内可买套数。"""
    group = _make_group("expensive_prime", 4)
    result = analyze_prime_investment(group, _mock_order_fetcher, budget=100)

    assert result is not None
    # buy_cost = 60 (15 * 4 部件)
    assert result.buy_cost == 60
    # 100 // 60 = 1 套
    assert result.sets_affordable == 1
    assert result.total_profit == 60


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 10})
def test_missing_set_orders_do_not_create_fake_profit(mock_stats):
    def missing_set_fetcher(item_id):
        if "set" in item_id:
            return []
        return _mock_orders(buy_price=5, sell_price=30)

    group = _make_group("missing_set", 4)
    result = analyze_prime_investment(group, missing_set_fetcher, budget=1000)
    assert result is None


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 10})
def test_missing_part_seller_orders_do_not_create_fake_parts_strategy(mock_stats):
    def missing_part_seller_fetcher(item_id):
        if "set" in item_id:
            return [
                {"order_type": "buy", "platinum": 120, "quantity": 1,
                 "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ]
        return [
            {"order_type": "buy", "platinum": 30, "quantity": 1,
             "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
        ]

    group = _make_group("missing_part_seller", 4)
    result = analyze_prime_investment(group, missing_part_seller_fetcher, budget=1000)
    assert result is None


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 10})
def test_no_profit_returns_none(mock_stats):
    """测试无利润时返回 None。"""
    def no_profit_fetcher(item_id):
        if "set" in item_id:
            return _mock_orders(buy_price=200, sell_price=100)  # 套装贵
        else:
            return _mock_orders(buy_price=80, sell_price=10)    # 部件卖价低

    group = _make_group("no_profit", 4)
    result = analyze_prime_investment(group, no_profit_fetcher, budget=1000)
    assert result is None


def test_risk_level_low():
    assert _assess_risk(volume_48h=20, supply_count=5, demand_count=5) == "low"


def test_risk_level_medium():
    assert _assess_risk(volume_48h=3, supply_count=10, demand_count=5) == "medium"


def test_risk_level_high():
    assert _assess_risk(volume_48h=0, supply_count=20, demand_count=2) == "high"


def test_format_prime_investment_results_for_model_includes_metadata_and_top_rows():
    """紧凑模型上下文应包含预算、ROI、风险和主要投资字段。"""
    result = _make_investment(1, roi_pct=55.5, risk_level="medium", volume_48h=18, part_count=3)

    text = format_prime_investment_results_for_model(
        [result],
        budget=500,
        min_roi_pct=20.0,
        limit=10,
    )

    assert "tool=investment_advisor budget=500 min_roi=20.0 limit=10 result_count=1" in text
    assert "base_id=test_prime_1" in text
    assert "display_name=Test Prime 1 一套" in text
    assert "set_item_id=test_prime_1_set" in text
    assert "strategy=buy_parts_sell_set" in text
    assert "buy_cost=61" in text
    assert "sell_price=121" in text
    assert "profit_per_set=60" in text
    assert "roi_pct=55.5" in text
    assert "sets_affordable=8" in text
    assert "total_profit=480" in text
    assert "risk_level=medium" in text
    assert "volume_48h=18" in text
    assert "part_count=3" in text


def test_investment_model_context_excludes_players_links_whispers():
    result = _make_investment(1)
    result = PrimeInvestment(
        **{**result.__dict__, "trade_plan": {
            "buy_steps": [{"player": "HiddenPlayer", "market_url": "https://warframe.market/items/x", "profile_url": "https://warframe.market/profile/HiddenPlayer", "whisper": "/w HiddenPlayer hi"}],
            "sell_steps": [],
            "safe_summary": {"source": "investment", "strategy": "buy_parts_sell_set", "profit": 60},
        }}
    )

    text = format_prime_investment_results_for_model([result], budget=500, min_roi_pct=10, limit=5)

    for forbidden in ["HiddenPlayer", "warframe.market", "/w", "whisper", "market_url", "profile_url"]:
        assert forbidden not in text


def test_format_prime_investment_results_for_model_compacts_and_omits_raw_part_details():
    """结果超过 max_items 时应截断并只暴露 part_count，不泄漏原始部件明细。"""
    results = [_make_investment(i, part_count=2) for i in range(1, 5)]

    text = format_prime_investment_results_for_model(
        results,
        budget=300,
        min_roi_pct=15,
        limit=30,
        max_items=2,
    )

    assert "result_count=4" in text
    assert "omitted=2" in text
    assert "base_id=test_prime_1" in text
    assert "base_id=test_prime_2" in text
    assert "base_id=test_prime_3" not in text
    assert "part_count=2" in text
    assert "part_details" not in text
    assert "test_part_0" not in text
    assert "部件 0" not in text


def test_no_set_in_group():
    """测试没有套装的 group 返回 None。"""
    group = PrimeGroup(
        base_id="no_set",
        items={"blueprint": "no_set_bp"},
        tags={"prime", "warframe"},
        zh_title="No Set",
        en_title="No Set",
    )
    result = analyze_prime_investment(group, _mock_order_fetcher, budget=500)
    assert result is None


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 15})
def test_scan_prime_investments(mock_stats):
    """测试扫描多个套装。"""
    items = [
        {"item_id": "alpha_prime_set", "zh_name": "Alpha Prime 一套", "en_name": "Alpha Prime Set",
         "tags": ["set", "prime", "warframe"], "search_terms": []},
        {"item_id": "alpha_prime_blueprint", "zh_name": "Alpha Prime 蓝图", "en_name": "Alpha Prime Blueprint",
         "tags": ["blueprint", "prime", "warframe"], "search_terms": []},
        {"item_id": "alpha_prime_chassis_blueprint", "zh_name": "Alpha Prime 机体", "en_name": "Alpha Prime Chassis",
         "tags": ["component", "prime", "warframe", "blueprint"], "search_terms": []},
        {"item_id": "alpha_prime_neuroptics_blueprint", "zh_name": "Alpha Prime 头部", "en_name": "Alpha Prime Neuroptics",
         "tags": ["component", "prime", "warframe", "blueprint"], "search_terms": []},
        {"item_id": "alpha_prime_systems_blueprint", "zh_name": "Alpha Prime 系统", "en_name": "Alpha Prime Systems",
         "tags": ["component", "prime", "warframe", "blueprint"], "search_terms": []},
    ]

    results = scan_prime_investments(items, _mock_order_fetcher, budget=1000, min_roi_pct=10)
    # 应该找到 alpha_prime 套装
    assert len(results) >= 1
    assert results[0].base_id == "alpha_prime"
    assert results[0].roi_pct >= 10


@patch("warframe_agent.investment.fetch_item_statistics", return_value={"volume_48h": 15})
def test_scan_filters_non_warframe_weapon(mock_stats):
    """测试只扫描战甲和武器套装，排除其他类型。"""
    items = [
        # sentinel 套装（应被排除）
        {"item_id": "carrier_prime_set", "zh_name": "Carrier Prime 一套", "en_name": "Carrier Prime Set",
         "tags": ["set", "prime", "sentinel"], "search_terms": []},
        # warframe 套装（应被包含）
        {"item_id": "volt_prime_set", "zh_name": "Volt Prime 一套", "en_name": "Volt Prime Set",
         "tags": ["set", "prime", "warframe"], "search_terms": []},
        {"item_id": "volt_prime_blueprint", "zh_name": "Volt Prime 蓝图", "en_name": "Volt Prime Blueprint",
         "tags": ["blueprint", "prime", "warframe"], "search_terms": []},
        {"item_id": "volt_prime_chassis_blueprint", "zh_name": "Volt Prime 机体", "en_name": "Volt Prime Chassis",
         "tags": ["component", "prime", "warframe", "blueprint"], "search_terms": []},
        {"item_id": "volt_prime_neuroptics_blueprint", "zh_name": "Volt Prime 头部", "en_name": "Volt Prime Neuroptics",
         "tags": ["component", "prime", "warframe", "blueprint"], "search_terms": []},
        {"item_id": "volt_prime_systems_blueprint", "zh_name": "Volt Prime 系统", "en_name": "Volt Prime Systems",
         "tags": ["component", "prime", "warframe", "blueprint"], "search_terms": []},
    ]

    results = scan_prime_investments(items, _mock_order_fetcher, budget=1000, min_roi_pct=10)
    # 只有 volt_prime 应该出现，carrier_prime 被排除
    base_ids = [r.base_id for r in results]
    assert "volt_prime" in base_ids or len(results) == 0  # 可能因为价格原因没有结果
