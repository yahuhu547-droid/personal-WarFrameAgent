import unittest

from warframe_agent.chat import ChatAgent
from warframe_agent.dictionary import ResolveResult


class FakeResolver:
    aliases = {"充沛": "arcane_energize"}
    dictionary = {}

    def resolve(self, name):
        if name == "充沛":
            return ResolveResult("arcane_energize", "alias", name)
        raise LookupError(name)


SAMPLE_ORDERS = [
    {"type": "sell", "platinum": 40, "quantity": 21, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10}},
    {"type": "buy", "platinum": 35, "quantity": 5, "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 5}},
]


class ShortNameRegressionTests(unittest.TestCase):
    def test_short_chinese_name_inside_sentence_is_resolved(self):
        prompts = []
        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: SAMPLE_ORDERS,
            model_call=lambda prompt: prompts.append(prompt) or "充沛赋能 / Arcane Energize / arcane_energize：最低卖价 40p。",
        )

        answer = agent.answer("充沛现在价格怎么样")

        self.assertIn("充沛赋能 / Arcane Energize / arcane_energize", answer)
        self.assertIn("最低卖价: 40p", prompts[0])


if __name__ == "__main__":
    unittest.main()
