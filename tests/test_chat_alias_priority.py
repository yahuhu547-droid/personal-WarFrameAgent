import unittest

from warframe_agent.chat import ChatAgent
from warframe_agent.dictionary import ResolveResult


class DuplicateAliasResolver:
    aliases = {"充沛": "arcane_energize"}
    generated_aliases = {"充沛": "energizing_shot", "充沛射击": "energizing_shot"}

    def resolve(self, name):
        if name == "充沛":
            return ResolveResult("arcane_energize", "alias", name)
        raise LookupError(name)


ORDERS = [
    {"type": "sell", "platinum": 40, "quantity": 21, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10}},
]


class ChatAliasPriorityTests(unittest.TestCase):
    def test_manual_alias_key_overrides_generated_duplicate_key(self):
        prompts = []
        agent = ChatAgent(
            resolver=DuplicateAliasResolver(),
            order_fetcher=lambda item_id: ORDERS,
            model_call=lambda prompt: prompts.append(prompt) or "充沛赋能 / Arcane Energize / arcane_energize：40p。",
        )

        agent.answer("充沛现在价格怎么样")

        self.assertIn("arcane_energize", prompts[0])
        self.assertNotIn("energizing_shot", prompts[0])
        self.assertIn("所有价格单位都是 Warframe 白金 platinum，绝不是美元", prompts[0])


if __name__ == "__main__":
    unittest.main()
