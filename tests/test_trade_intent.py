import unittest

from warframe_agent.chat import ChatAgent
from warframe_agent.dictionary import ResolveResult
from warframe_agent.trade_intent import detect_trade_intent


class FakeResolver:
    aliases = {"充沛": "arcane_energize", "充沛赋能": "arcane_energize"}

    def resolve(self, name):
        if name in self.aliases:
            return ResolveResult(self.aliases[name], "alias", name)
        if "arcane_energize" in name:
            return ResolveResult("arcane_energize", "normalized", name)
        raise LookupError(name)


SAMPLE_ORDERS = [
    {
        "type": "sell",
        "platinum": 5,
        "quantity": 21,
        "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10},
    },
    {
        "type": "buy",
        "platinum": 3,
        "quantity": 10,
        "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 5},
    },
]

PRIME_ITEMS = [
    {"item_id": "lex_prime_set", "zh_name": "Lex Prime 一套", "en_name": "Lex Prime Set", "tags": ["set", "prime", "weapon", "secondary"]},
    {"item_id": "lex_prime_blueprint", "zh_name": "Lex Prime 蓝图", "en_name": "Lex Prime Blueprint", "tags": ["blueprint", "prime", "weapon", "secondary"]},
    {"item_id": "lex_prime_barrel", "zh_name": "Lex Prime 枪管", "en_name": "Lex Prime Barrel", "tags": ["component", "prime", "weapon"]},
    {"item_id": "lex_prime_receiver", "zh_name": "Lex Prime 枪机", "en_name": "Lex Prime Receiver", "tags": ["component", "prime", "weapon"]},
]


def prime_orders_for(item_id):
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


class TradeIntentTests(unittest.TestCase):
    def test_detect_buy_intent_from_lowest_sell_words(self):
        self.assertEqual(detect_trade_intent("充沛最低卖多少"), "buy")

    def test_detect_sell_intent_from_highest_buy_words(self):
        self.assertEqual(detect_trade_intent("充沛最高收多少"), "sell")

    def test_generic_chat_buy_intent_returns_deterministic_quote(self):
        def model_call(prompt):
            raise AssertionError("generic model path should not be called")

        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: SAMPLE_ORDERS,
            model_call=model_call,
        )

        answer = agent.answer("我要买充沛")

        self.assertIn("按你要买来看", answer)
        self.assertIn("最低卖价: 5p", answer)
        self.assertIn("/w Seller", answer)

    def test_generic_chat_sell_intent_returns_deterministic_quote(self):
        def model_call(prompt):
            raise AssertionError("generic model path should not be called")

        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: SAMPLE_ORDERS,
            model_call=model_call,
        )

        answer = agent.answer("我想卖充沛")

        self.assertIn("按你要卖来看", answer)
        self.assertIn("最高收价: 3p", answer)
        self.assertIn("/w Buyer", answer)

    def test_prime_set_buy_intent_emphasizes_lowest_sell(self):
        agent = ChatAgent(order_fetcher=prime_orders_for, model_call=lambda prompt: "generic", warframe_items=PRIME_ITEMS)

        answer = agent.answer("Lex Prime 一套最低卖多少")

        self.assertIn("按你要买整套来看", answer)
        self.assertIn("整套直接买最低: 70p", answer)

    def test_prime_part_sell_intent_emphasizes_highest_buy(self):
        agent = ChatAgent(order_fetcher=prime_orders_for, model_call=lambda prompt: "generic", warframe_items=PRIME_ITEMS)

        answer = agent.answer("Lex Prime 枪管最高收多少")

        self.assertIn("按你要卖这个部件来看", answer)
        self.assertIn("最高收价: 10p", answer)

    def test_generic_chat_buy_intent_uses_temporary_unavailable_text(self):
        no_seller_orders = [
            {"type": "buy", "platinum": 3, "quantity": 10, "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 5}},
        ]
        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: no_seller_orders,
            model_call=lambda prompt: "generic",
        )

        answer = agent.answer("我要买充沛")

        self.assertIn("当前最低卖价: 暂无", answer)


if __name__ == "__main__":
    unittest.main()
