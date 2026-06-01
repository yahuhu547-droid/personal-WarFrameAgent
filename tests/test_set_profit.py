"""测试 Prime 套装利润分析器。"""
from __future__ import annotations

from warframe_agent.set_profit import (
    SetProfitResult,
    _count_orders,
    analyze_set_profit,
    format_set_profit_results_for_model,
    scan_all_set_profits,
)
from warframe_agent.memory import AgentMemory
from warframe_agent.personal_profile import build_personal_profile
from warframe_agent.warframes import PrimeGroup


def _mock_orders(item_id):
    """模拟订单数据。"""
    data = {
        "rhino_prime_set": [
            {"order_type": "sell", "platinum": 90, "quantity": 1, "user": {"ingame_name": "s1", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 95, "quantity": 1, "user": {"ingame_name": "b1", "status": "ingame", "reputation": 5}},
        ],
        "rhino_prime_blueprint": [
            {"order_type": "sell", "platinum": 10, "quantity": 1, "user": {"ingame_name": "s2", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 8, "quantity": 1, "user": {"ingame_name": "b2", "status": "ingame", "reputation": 5}},
        ],
        "rhino_prime_chassis": [
            {"order_type": "sell", "platinum": 15, "quantity": 1, "user": {"ingame_name": "s3", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 12, "quantity": 1, "user": {"ingame_name": "b3", "status": "ingame", "reputation": 5}},
        ],
        "rhino_prime_neuroptics": [
            {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "s4", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 15, "quantity": 1, "user": {"ingame_name": "b4", "status": "ingame", "reputation": 5}},
        ],
        "rhino_prime_systems": [
            {"order_type": "sell", "platinum": 25, "quantity": 1, "user": {"ingame_name": "s5", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 20, "quantity": 1, "user": {"ingame_name": "b5", "status": "ingame", "reputation": 5}},
        ],
    }
    return data.get(item_id, [])


def test_count_orders_accepts_type_field_orders():
    orders = [
        {"type": "sell", "platinum": 10, "quantity": 1},
        {"type": "buy", "platinum": 12, "quantity": 1},
        {"order_type": "sell", "platinum": 11, "quantity": 1},
    ]

    assert _count_orders(orders, "sell") == 2
    assert _count_orders(orders, "buy") == 1


def test_analyze_single_set():
    group = PrimeGroup(
        base_id="rhino_prime",
        items={
            "set": "rhino_prime_set",
            "blueprint": "rhino_prime_blueprint",
            "chassis": "rhino_prime_chassis",
            "neuroptics": "rhino_prime_neuroptics",
            "systems": "rhino_prime_systems",
        },
        en_title="Rhino Prime",
    )
    result = analyze_set_profit(group, _mock_orders)
    assert result is not None
    assert result.base_id == "rhino_prime"
    # parts_buy_total = 8 + 12 + 15 + 20 = 55（部件最高收价总收入）
    assert result.parts_buy_total == 55
    # parts_sell_total = 10 + 15 + 20 + 25 = 70（部件最低卖价总成本）
    assert result.parts_sell_total == 70
    # 买部件卖套装 = 套装最高收价 95 - 部件最低卖价总成本 70 = 25
    assert result.profit_buy_parts_sell_set == 25
    # 买套装卖部件 = 部件最高收价总收入 55 - 套装最低卖价 90 = -35
    assert result.profit_buy_set_sell_parts == -35
    assert result.best_strategy == "买部件→卖套装"
    assert result.best_profit == 25
    assert result.set_item_id == "rhino_prime_set"
    assert result.market_url == "https://warframe.market/items/rhino_prime_set"
    assert len(result.part_details) == 4
    blueprint = next(part for part in result.part_details if part["item_id"] == "rhino_prime_blueprint")
    assert blueprint["market_url"] == "https://warframe.market/items/rhino_prime_blueprint"
    assert blueprint["seller"]["player"] == "s2"
    assert blueprint["seller"]["price"] == 10
    assert blueprint["buyer"]["player"] == "b2"
    assert blueprint["buyer"]["price"] == 8
    assert result.set_seller["player"] == "s1"
    assert result.set_buyer["player"] == "b1"
    assert result.trade_plan["strategy"] == "buy_parts_sell_set"
    assert result.trade_plan["total_cost"] == 70
    assert result.trade_plan["total_revenue"] == 95
    assert result.trade_plan["profit"] == 25
    assert [step["player"] for step in result.trade_plan["buy_steps"]] == ["s2", "s3", "s4", "s5"]
    assert [step["label"] for step in result.trade_plan["buy_steps"]] == ["买入部件：蓝图", "买入部件：机体", "买入部件：头部神经光元", "买入部件：系统"]
    assert [step["player"] for step in result.trade_plan["sell_steps"]] == ["b1"]
    plan_text = str(result.trade_plan)
    assert "s1" not in plan_text
    for buyer in ["b2", "b3", "b4", "b5"]:
        assert buyer not in plan_text


def test_best_strategy_buy_set_sell_parts():
    """当套装便宜、部件贵时，策略应为买套装拆卖。"""
    def mock_orders(item_id):
        data = {
            "nova_prime_set": [
                {"order_type": "sell", "platinum": 30, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 25, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
            "nova_prime_blueprint": [
                {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 18, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
            "nova_prime_chassis": [
                {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 18, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
            "nova_prime_neuroptics": [
                {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 18, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
            "nova_prime_systems": [
                {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 18, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
        }
        return data.get(item_id, [])

    group = PrimeGroup(
        base_id="nova_prime",
        items={
            "set": "nova_prime_set",
            "blueprint": "nova_prime_blueprint",
            "chassis": "nova_prime_chassis",
            "neuroptics": "nova_prime_neuroptics",
            "systems": "nova_prime_systems",
        },
        en_title="Nova Prime",
    )
    result = analyze_set_profit(group, mock_orders)
    assert result is not None
    # parts_buy_total = 18+18+18+18 = 72（拆卖给最高收价买家）, set_buy = 30
    # profit_buy_set_sell_parts = 72 - 30 = 42
    assert result.best_strategy == "买套装→卖部件"
    assert result.best_profit == 42
    assert result.trade_plan["strategy"] == "buy_set_sell_parts"
    assert result.trade_plan["total_cost"] == 30
    assert result.trade_plan["total_revenue"] == 72
    assert result.trade_plan["profit"] == 42
    assert [step["player"] for step in result.trade_plan["buy_steps"]] == ["s"]
    assert [step["player"] for step in result.trade_plan["sell_steps"]] == ["b", "b", "b", "b"]


def test_no_profit_returns_none():
    """无利润时返回 None。"""
    def mock_orders(item_id):
        return [
            {"order_type": "sell", "platinum": 100, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 10, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
        ]

    group = PrimeGroup(
        base_id="test_prime",
        items={"set": "test_set", "blueprint": "test_bp"},
        en_title="Test Prime",
    )
    result = analyze_set_profit(group, mock_orders)
    assert result is None


def test_missing_set_price_does_not_create_fake_profit():
    """套装无价格时不能把缺失报价当 0 制造利润。"""
    def mock_orders(item_id):
        if item_id == "x_set":
            return []  # 套装无订单
        return [
            {"order_type": "sell", "platinum": 10, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 8, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
        ]

    group = PrimeGroup(
        base_id="x_prime",
        items={"set": "x_set", "blueprint": "x_bp", "chassis": "x_chassis"},
        en_title="X Prime",
    )
    result = analyze_set_profit(group, mock_orders)
    assert result is None


def _result(
    base_id: str,
    display_name: str,
    best_strategy: str,
    best_profit: int,
    *,
    profit_buy_parts_sell_set: int = 0,
    profit_buy_set_sell_parts: int = 0,
    set_buy_price: int | None = 40,
    set_sell_price: int | None = 55,
    parts_buy_total: int = 45,
    parts_sell_total: int = 60,
    part_count: int = 4,
    volume_48h: int | None = 12,
    best_cost: int = 0,
    best_revenue: int = 0,
    roi_pct: float = 0.0,
    liquidity_score: float = 0.0,
    risk_level: str = "medium",
    risk_score: float = 0.0,
    opportunity_score: float = 0.0,
    supply_count: int = 0,
    demand_count: int = 0,
    trade_plan: dict | None = None,
) -> SetProfitResult:
    return SetProfitResult(
        base_id=base_id,
        display_name=display_name,
        set_buy_price=set_buy_price,
        parts_sell_total=parts_sell_total,
        set_sell_price=set_sell_price,
        parts_buy_total=parts_buy_total,
        profit_buy_parts_sell_set=profit_buy_parts_sell_set,
        profit_buy_set_sell_parts=profit_buy_set_sell_parts,
        best_strategy=best_strategy,
        best_profit=best_profit,
        volume_48h=volume_48h,
        part_count=part_count,
        best_cost=best_cost,
        best_revenue=best_revenue,
        roi_pct=roi_pct,
        liquidity_score=liquidity_score,
        risk_level=risk_level,
        risk_score=risk_score,
        opportunity_score=opportunity_score,
        supply_count=supply_count,
        demand_count=demand_count,
        trade_plan=trade_plan,
    )


def test_format_set_profit_results_for_model_includes_strategy_and_profit_fields():
    results = [
        _result(
            "rhino_prime",
            "Rhino Prime",
            "买部件→卖套装",
            15,
            profit_buy_parts_sell_set=15,
            profit_buy_set_sell_parts=-10,
            set_buy_price=80,
            set_sell_price=70,
            parts_buy_total=55,
            parts_sell_total=70,
            part_count=4,
            volume_48h=23,
        )
    ]

    formatted = format_set_profit_results_for_model(results, min_profit=5, limit=20)

    assert formatted.splitlines()[0] == "metadata tool=set_profit min_profit=5 limit=20 result_count=1"
    assert "display_name=Rhino Prime" in formatted
    assert "best_strategy=买部件→卖套装" in formatted
    assert "best_profit=15" in formatted
    assert "profit_buy_parts_sell_set=15" in formatted
    assert "profit_buy_set_sell_parts=-10" in formatted
    assert "set_buy_price=80" in formatted
    assert "set_sell_price=70" in formatted
    assert "parts_buy_total=55" in formatted
    assert "parts_sell_total=70" in formatted
    assert "part_count=4" in formatted
    assert "volume_48h=23" in formatted
    assert not formatted.startswith("#")
    for forbidden in ["/w", "seller", "buyer", "market_url", "whisper"]:
        assert forbidden not in formatted.lower()


def test_format_set_profit_results_for_model_compacts_and_reports_omitted_count():
    results = [
        _result(f"item_{i}", f"Item {i}", "买套装→卖部件", 100 - i)
        for i in range(10)
    ]

    formatted = format_set_profit_results_for_model(results, min_profit=10, limit=20, max_items=3)
    lines = formatted.splitlines()

    assert lines[0] == "metadata tool=set_profit min_profit=10 limit=20 result_count=10"
    assert sum(1 for line in lines if line.startswith("row ")) == 3
    assert "base_id=item_0" in formatted
    assert "base_id=item_2" in formatted
    assert "base_id=item_3" not in formatted
    assert lines[-1] == "omitted_count=7"


def test_analyze_set_profit_populates_roi_risk_and_opportunity_metrics(monkeypatch):
    monkeypatch.setattr("warframe_agent.set_profit.fetch_item_statistics", lambda item_id: {"volume_48h": 18})
    group = PrimeGroup(
        base_id="rhino_prime",
        items={
            "set": "rhino_prime_set",
            "blueprint": "rhino_prime_blueprint",
            "chassis": "rhino_prime_chassis",
            "neuroptics": "rhino_prime_neuroptics",
            "systems": "rhino_prime_systems",
        },
        en_title="Rhino Prime",
    )

    result = analyze_set_profit(group, _mock_orders)

    assert result is not None
    assert result.best_cost == 70
    assert result.best_revenue == 95
    assert result.roi_pct == 35.7
    assert result.supply_count == 4
    assert result.demand_count == 1
    assert result.liquidity_score > 0
    assert result.risk_level in {"low", "medium", "high"}
    assert result.risk_score >= 0
    assert result.opportunity_score > result.best_profit
    assert result.trade_plan["roi_pct"] == result.roi_pct
    assert result.trade_plan["risk_level"] == result.risk_level


def test_buy_set_sell_parts_roi_uses_set_cost(monkeypatch):
    monkeypatch.setattr("warframe_agent.set_profit.fetch_item_statistics", lambda item_id: {"volume_48h": 8})

    def mock_orders(item_id):
        data = {
            "nova_prime_set": [
                {"order_type": "sell", "platinum": 30, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 25, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
            "nova_prime_blueprint": [
                {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 18, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
            "nova_prime_chassis": [
                {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 18, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
            "nova_prime_neuroptics": [
                {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 18, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
            "nova_prime_systems": [
                {"order_type": "sell", "platinum": 20, "quantity": 1, "user": {"ingame_name": "s", "status": "ingame", "reputation": 5}},
                {"order_type": "buy", "platinum": 18, "quantity": 1, "user": {"ingame_name": "b", "status": "ingame", "reputation": 5}},
            ],
        }
        return data.get(item_id, [])

    group = PrimeGroup(
        base_id="nova_prime",
        items={
            "set": "nova_prime_set",
            "blueprint": "nova_prime_blueprint",
            "chassis": "nova_prime_chassis",
            "neuroptics": "nova_prime_neuroptics",
            "systems": "nova_prime_systems",
        },
        en_title="Nova Prime",
    )

    result = analyze_set_profit(group, mock_orders)

    assert result is not None
    assert result.best_strategy == "买套装→卖部件"
    assert result.best_cost == 30
    assert result.best_revenue == 72
    assert result.roi_pct == 140.0


def test_scan_all_set_profits_sorts_by_opportunity_score(monkeypatch):
    low_profit_high_score = _result(
        "fast_prime", "Fast Prime", "买部件→卖套装", 12,
        opportunity_score=90, roi_pct=120,
    )
    high_profit_low_score = _result(
        "slow_prime", "Slow Prime", "买部件→卖套装", 30,
        opportunity_score=20, roi_pct=15,
    )

    groups = {
        "slow_prime": PrimeGroup(base_id="slow_prime", items={"set": "slow_prime_set", "blueprint": "slow_prime_blueprint"}, en_title="Slow Prime"),
        "fast_prime": PrimeGroup(base_id="fast_prime", items={"set": "fast_prime_set", "blueprint": "fast_prime_blueprint"}, en_title="Fast Prime"),
    }
    monkeypatch.setattr("warframe_agent.set_profit.build_prime_groups", lambda items: groups)

    def fake_analyze(group, order_fetcher):
        return high_profit_low_score if group.base_id == "slow_prime" else low_profit_high_score

    monkeypatch.setattr("warframe_agent.set_profit.analyze_set_profit", fake_analyze)

    results = scan_all_set_profits([{}], min_profit=1, limit=2)

    assert [result.base_id for result in results] == ["fast_prime", "slow_prime"]


def test_scan_all_set_profits_applies_personal_profile_sorting(monkeypatch):
    safe_fit = _result(
        "safe_prime", "Safe Prime", "buy_parts_sell_set", 20,
        best_cost=50,
        roi_pct=40,
        risk_level="low",
        opportunity_score=20,
    )
    risky_market = _result(
        "risky_prime", "Risky Prime", "buy_parts_sell_set", 45,
        best_cost=50,
        roi_pct=90,
        risk_level="high",
        opportunity_score=120,
    )
    groups = {
        "risky_prime": PrimeGroup(base_id="risky_prime", items={"set": "risky_prime_set", "blueprint": "risky_prime_blueprint"}, en_title="Risky Prime"),
        "safe_prime": PrimeGroup(base_id="safe_prime", items={"set": "safe_prime_set", "blueprint": "safe_prime_blueprint"}, en_title="Safe Prime"),
    }
    monkeypatch.setattr("warframe_agent.set_profit.build_prime_groups", lambda items: groups)

    def fake_analyze(group, order_fetcher):
        return risky_market if group.base_id == "risky_prime" else safe_fit

    monkeypatch.setattr("warframe_agent.set_profit.analyze_set_profit", fake_analyze)
    memory = AgentMemory.default().with_updated_preferences(
        risk_appetite="low",
        budget_min=1,
        budget_max=100,
        preferred_categories=["prime_set"],
        min_roi_pct=20,
    )
    profile = build_personal_profile(memory)

    results = scan_all_set_profits([{}], min_profit=1, limit=2, personal_profile=profile)

    assert [result.base_id for result in results] == ["safe_prime", "risky_prime"]
    assert results[0].personal_score > results[1].personal_score


def test_format_set_profit_results_for_model_includes_scores_without_trade_targets():
    result = _result(
        "rhino_prime", "Rhino Prime", "买部件→卖套装", 25,
        best_cost=70,
        best_revenue=95,
        roi_pct=35.7,
        liquidity_score=56.0,
        risk_level="medium",
        risk_score=25.0,
        opportunity_score=63.4,
        supply_count=4,
        demand_count=1,
        trade_plan={
            "buy_steps": [{"player": "SecretSeller", "profile_url": "https://warframe.market/profile/SecretSeller", "whisper": "/w SecretSeller hi"}],
            "safe_summary": {"profit": 25},
        },
    )

    formatted = format_set_profit_results_for_model([result], min_profit=5, limit=20)

    assert "best_cost=70" in formatted
    assert "best_revenue=95" in formatted
    assert "roi_pct=35.7" in formatted
    assert "liquidity_score=56.0" in formatted
    assert "risk_level=medium" in formatted
    assert "risk_score=25.0" in formatted
    assert "opportunity_score=63.4" in formatted
    assert "supply_count=4" in formatted
    assert "demand_count=1" in formatted
    for forbidden in ["SecretSeller", "profile", "/w", "whisper", "buy_steps"]:
        assert forbidden not in formatted


def test_set_profit_result_can_carry_personal_score():
    result = SetProfitResult(
        base_id="gauss_prime",
        display_name="Gauss Prime",
        set_buy_price=100,
        parts_sell_total=120,
        set_sell_price=130,
        parts_buy_total=90,
        profit_buy_parts_sell_set=30,
        profit_buy_set_sell_parts=20,
        best_strategy="买部件→卖套装",
        best_profit=30,
        volume_48h=20,
        part_count=4,
        best_cost=100,
        best_revenue=130,
        roi_pct=30.0,
        personal_score=88.5,
        personal_reasons=["预算匹配", "偏好品类匹配"],
    )

    assert result.personal_score == 88.5
    assert result.personal_reasons == ["预算匹配", "偏好品类匹配"]

def test_scan_all_set_profits_considers_candidates_after_first_15(monkeypatch):
    groups = {
        f"item_{index}_prime": PrimeGroup(
            base_id=f"item_{index}_prime",
            items={
                "set": f"item_{index}_prime_set",
                "blueprint": f"item_{index}_prime_blueprint",
            },
            en_title=f"Item {index} Prime",
        )
        for index in range(15)
    }
    groups["late_item_prime"] = PrimeGroup(
        base_id="late_item_prime",
        items={"set": "late_item_prime_set", "blueprint": "late_item_prime_blueprint"},
        en_title="Late Item Prime",
    )
    monkeypatch.setattr("warframe_agent.set_profit.build_prime_groups", lambda items: groups)

    def fake_analyze(group, order_fetcher):
        if group.base_id != "late_item_prime":
            return None
        return _result(
            "late_item_prime",
            "Late Item Prime",
            "buy_parts_sell_set",
            50,
            opportunity_score=50,
        )

    monkeypatch.setattr("warframe_agent.set_profit.analyze_set_profit", fake_analyze)

    results = scan_all_set_profits([{}], min_profit=1, limit=5)

    assert [result.base_id for result in results] == ["late_item_prime"]
