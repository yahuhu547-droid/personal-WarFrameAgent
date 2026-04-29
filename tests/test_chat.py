import unittest

from warframe_agent.chat import ChatAgent, build_item_context, is_chat_exit
from warframe_agent.dictionary import ResolveResult


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


class ChatTests(unittest.TestCase):
    def test_chat_exit_commands(self):
        self.assertTrue(is_chat_exit("q"))
        self.assertTrue(is_chat_exit("quit"))
        self.assertTrue(is_chat_exit("退出"))
        self.assertFalse(is_chat_exit("充沛现在能买吗"))

    def test_item_context_includes_veteran_market_details(self):
        context = build_item_context("arcane_energize", SAMPLE_ORDERS)

        self.assertIn("充沛赋能 / Arcane Energize / arcane_energize", context)
        self.assertIn("最低卖价: 5p", context)
        self.assertIn("最高收价: 3p", context)
        self.assertIn("价差: 2p", context)
        self.assertIn("满级估算: 21 个约 105p", context)
        self.assertIn("/w Seller", context)

    def test_answer_uses_model_with_market_context(self):
        prompts = []

        def model_call(prompt):
            prompts.append(prompt)
            return "充沛赋能 / Arcane Energize / arcane_energize：现在可以蹲低价。"

        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: SAMPLE_ORDERS,
            model_call=model_call,
        )

        answer = agent.answer("充沛现在能买吗")

        self.assertIn("充沛赋能 / Arcane Energize / arcane_energize", answer)
        self.assertIn("最低卖价: 5p", prompts[0])

    def test_alias_substring_is_detected_before_llm_fallback(self):
        called = []
        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: SAMPLE_ORDERS,
            model_call=lambda prompt: called.append(prompt) or "已识别充沛赋能 / Arcane Energize / arcane_energize",
        )

        answer = agent.answer("老哥，充沛现在能买吗")

        self.assertIn("充沛赋能", answer)
        self.assertIn("最低卖价: 5p", called[0])

    def test_watchlist_command_scans_configured_items(self):
        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: SAMPLE_ORDERS,
            model_call=lambda prompt: "watchlist summary",
            watchlist={"arcanes": ["arcane_energize"]},
        )

        answer = agent.answer("关注列表")

        self.assertIn("充沛赋能 / Arcane Energize / arcane_energize", answer)
        self.assertIn("价差: 2p", answer)


if __name__ == "__main__":
    unittest.main()
