import unittest

from warframe_agent.chat import ChatAgent


class EmptyResolver:
    aliases = {}
    generated_aliases = {}

    def resolve(self, name):
        raise LookupError(name)


ORDERS = [
    {"type": "sell", "platinum": 40, "quantity": 21, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10}},
]


class ChatRagFallbackTests(unittest.TestCase):
    def test_chat_uses_rag_result_when_alias_lookup_fails(self):
        prompts = []
        agent = ChatAgent(
            resolver=EmptyResolver(),
            order_fetcher=lambda item_id: ORDERS,
            model_call=lambda prompt: prompts.append(prompt) or "充沛赋能 / Arcane Energize / arcane_energize：已查到。",
            rag_search=lambda message: ["arcane_energize"],
        )

        answer = agent.answer("充沛现在价格怎么样")

        self.assertIn("arcane_energize", answer)
        self.assertIn("最低卖价: 40p", prompts[0])


if __name__ == "__main__":
    unittest.main()
