import unittest

from warframe_agent.market import MarketOrder
from warframe_agent.warframes import parse_warframe_query, price_warframe_query


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


class WarframeSetTests(unittest.TestCase):
    def test_parse_chinese_prime_part_query(self):
        query = parse_warframe_query("伏特p机体多少钱", ITEMS)

        self.assertIsNotNone(query)
        self.assertEqual(query.base_id, "volt_prime")
        self.assertEqual(query.query_type, "part")
        self.assertEqual(query.part_key, "chassis")
        self.assertEqual(query.item_ids(), ["volt_prime_chassis_blueprint"])

    def test_parse_chinese_prime_set_query(self):
        query = parse_warframe_query("伏特p一套现在多少钱", ITEMS)

        self.assertIsNotNone(query)
        self.assertEqual(query.query_type, "set")
        self.assertEqual(query.item_ids()[0], "volt_prime_set")
        self.assertIn("volt_prime_systems_blueprint", query.item_ids())

    def test_price_set_compares_direct_set_and_parts_totals(self):
        text = price_warframe_query("伏特p一套现在多少钱", ITEMS, orders_for)

        self.assertIn("伏特 Prime / Volt Prime / volt_prime_set", text)
        self.assertIn("整套直接买最低: 80p", text)
        self.assertIn("拆件买最低合计: 85p", text)
        self.assertIn("整套最高收: 60p", text)
        self.assertIn("拆件最高收合计: 50p", text)
        self.assertIn("机体", text)

    def test_price_part_query_shows_lowest_and_highest(self):
        text = price_warframe_query("伏特p机体多少钱", ITEMS, orders_for)

        self.assertIn("Volt Prime 机体", text)
        self.assertIn("最低卖价: 20p", text)
        self.assertIn("最高收价: 12p", text)
        self.assertIn("/w Seller", text)


if __name__ == "__main__":
    unittest.main()
