import unittest

from warframe_agent.warframes import price_warframe_query


ITEMS = [
    {"item_id": "volt_prime_set", "zh_name": "Volt Prime 一套", "en_name": "Volt Prime Set", "tags": ["set", "prime", "warframe"]},
    {"item_id": "volt_prime_blueprint", "zh_name": "Volt Prime 蓝图", "en_name": "Volt Prime Blueprint", "tags": ["blueprint", "prime", "warframe"]},
    {"item_id": "volt_prime_chassis_blueprint", "zh_name": "Volt Prime 机体 蓝图", "en_name": "Volt Prime Chassis Blueprint", "tags": ["component", "prime", "warframe", "blueprint"]},
    {"item_id": "volt_prime_neuroptics_blueprint", "zh_name": "Volt Prime 头部神经光元 蓝图", "en_name": "Volt Prime Neuroptics Blueprint", "tags": ["component", "prime", "warframe", "blueprint"]},
    {"item_id": "volt_prime_systems_blueprint", "zh_name": "Volt Prime 系统 蓝图", "en_name": "Volt Prime Systems Blueprint", "tags": ["component", "prime", "warframe", "blueprint"]},
]


def orders_for(item_id):
    prices = {
        "volt_prime_set": (80, 60),
        "volt_prime_blueprint": (10, 5),
        "volt_prime_chassis_blueprint": (20, 12),
        "volt_prime_neuroptics_blueprint": (30, 18),
        "volt_prime_systems_blueprint": (25, 15),
    }
    sell_price, buy_price = prices[item_id]
    return [
        {"type": "sell", "platinum": sell_price, "quantity": 1, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10}},
        {"type": "buy", "platinum": buy_price, "quantity": 1, "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 5}},
    ]


class MissingPartsTests(unittest.TestCase):
    def test_missing_parts_cost_for_prime_warframe(self):
        text = price_warframe_query("我有伏特p蓝图和系统，还差多少钱补齐", ITEMS, orders_for)

        self.assertIn("已拥有: 蓝图、系统", text)
        self.assertIn("缺少: 机体、头部神经光元", text)
        self.assertIn("补齐最低成本: 50p", text)
        self.assertIn("补齐后和整套对比", text)


if __name__ == "__main__":
    unittest.main()
