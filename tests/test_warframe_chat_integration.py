import unittest

from warframe_agent.chat import ChatAgent


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


class WarframeChatIntegrationTests(unittest.TestCase):
    def test_warframe_set_query_returns_deterministic_pricing_without_model_call(self):
        def model_call(prompt):
            raise AssertionError("generic model path should not be called")

        agent = ChatAgent(order_fetcher=orders_for, model_call=model_call, warframe_items=ITEMS)

        answer = agent.answer("伏特p一套现在多少钱")

        self.assertIn("伏特 Prime / Volt Prime / volt_prime_set", answer)
        self.assertIn("拆件买最低合计: 85p", answer)

    def test_warframe_part_query_returns_part_price(self):
        agent = ChatAgent(order_fetcher=orders_for, model_call=lambda prompt: "generic", warframe_items=ITEMS)

        answer = agent.answer("伏特p机体多少钱")

        self.assertIn("Volt Prime 机体", answer)
        self.assertIn("最低卖价: 20p", answer)


if __name__ == "__main__":
    unittest.main()
