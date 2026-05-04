"""测试 Prime 套装利润分析器。"""
from __future__ import annotations

from warframe_agent.set_profit import SetProfitResult, analyze_set_profit, scan_all_set_profits
from warframe_agent.warframes import PrimeGroup


def _mock_orders(item_id):
    """模拟订单数据。"""
    data = {
        "rhino_prime_set": [
            {"order_type": "sell", "platinum": 80, "quantity": 1, "user": {"ingame_name": "s1", "status": "ingame", "reputation": 5}},
            {"order_type": "buy", "platinum": 70, "quantity": 1, "user": {"ingame_name": "b1", "status": "ingame", "reputation": 5}},
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
    # parts_buy_total = 8 + 12 + 15 + 20 = 55
    assert result.parts_buy_total == 55
    # parts_sell_total = 10 + 15 + 20 + 25 = 70
    assert result.parts_sell_total == 70
    # profit_buy_parts_sell_set = 70 - 55 = 15
    assert result.profit_buy_parts_sell_set == 15
    # profit_buy_set_sell_parts = 70 - 80 = -10
    assert result.profit_buy_set_sell_parts == -10
    assert result.best_strategy == "买部件→卖套装"
    assert result.best_profit == 15


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
    # parts_sell_total = 20+20+20+20 = 80, set_buy = 30
    # profit_buy_set_sell_parts = 80 - 30 = 50
    assert result.best_strategy == "买套装→卖部件"
    assert result.best_profit == 50


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


def test_missing_set_price():
    """套装无价格时仍能计算拆件利润。"""
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
    # set_sell_price = None (0), parts_buy_total = 16
    # profit_buy_parts_sell_set = 0 - 16 = -16 (no profit)
    # profit_buy_set_sell_parts = 20 - 0 = 20
    assert result is not None
    assert result.best_profit == 20
