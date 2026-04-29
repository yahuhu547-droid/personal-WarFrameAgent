import unittest

from warframe_agent.chat import ChatAgent


ITEMS = [
    {"item_id": "lex_prime_set", "zh_name": "Lex Prime 一套", "en_name": "Lex Prime Set", "tags": ["set", "prime", "weapon", "secondary"]},
    {"item_id": "lex_prime_blueprint", "zh_name": "Lex Prime 蓝图", "en_name": "Lex Prime Blueprint", "tags": ["blueprint", "prime", "weapon", "secondary"]},
    {"item_id": "lex_prime_barrel", "zh_name": "Lex Prime 枪管", "en_name": "Lex Prime Barrel", "tags": ["component", "prime", "weapon"]},
    {"item_id": "lex_prime_receiver", "zh_name": "Lex Prime 枪机", "en_name": "Lex Prime Receiver", "tags": ["component", "prime", "weapon"]},
]


def orders_for(item_id):
    prices = {
        "lex_prime_set": (70, 50),
        "lex_prime_blueprint": (15, 7),
        "lex_prime_barrel": (20, 10),
        "lex_prime_receiver": (18, 9),
    }
    sell_price, buy_price = prices[item_id]
    return [
        {"type": "sell", "platinum": sell_price, "quantity": 1, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10}},
        {"type": "buy", "platinum": buy_price, "quantity": 1, "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 5}},
    ]


class PrimeSetChatIntegrationTests(unittest.TestCase):
    def test_chat_handles_prime_weapon_set_without_generic_model(self):
        def model_call(prompt):
            raise AssertionError("generic model path should not be called")

        agent = ChatAgent(order_fetcher=orders_for, model_call=model_call, warframe_items=ITEMS)

        answer = agent.answer("Lex Prime 一套多少钱")

        self.assertIn("Lex Prime / lex_prime_set", answer)
        self.assertIn("拆件买最低合计: 53p", answer)

    def test_chat_handles_missing_parts_question(self):
        agent = ChatAgent(order_fetcher=orders_for, model_call=lambda prompt: "generic", warframe_items=ITEMS)

        answer = agent.answer("我有 Lex Prime 蓝图和枪管，还差多少钱做一套")

        self.assertIn("已拥有: 蓝图、枪管", answer)
        self.assertIn("缺少: 枪机", answer)
        self.assertIn("补齐最低成本: 18p", answer)


if __name__ == "__main__":
    unittest.main()
