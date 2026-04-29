import unittest

from warframe_agent.chat import ChatAgent
from warframe_agent.session import SessionContext, is_followup


SAMPLE_ORDERS = [
    {"order_type": "sell", "platinum": 45, "quantity": 1, "user": {"ingame_name": "Seller1", "status": "ingame", "reputation": 5}},
    {"order_type": "buy", "platinum": 38, "quantity": 1, "user": {"ingame_name": "Buyer1", "status": "ingame", "reputation": 3}},
]


class FakeResolver:
    aliases = {"充沛": "arcane_energize"}
    generated_aliases = {}

    def resolve(self, name):
        if name in ("充沛", "arcane_energize"):
            class Result:
                item_id = "arcane_energize"
            return Result()
        raise LookupError(name)


class SessionContextTests(unittest.TestCase):
    def test_followup_detected(self):
        self.assertTrue(is_followup("那散件呢"))
        self.assertTrue(is_followup("现在呢"))
        self.assertTrue(is_followup("涨了吗"))

    def test_non_followup_not_detected(self):
        self.assertFalse(is_followup("充沛现在价格怎么样"))
        self.assertFalse(is_followup("伏特p一套多少钱"))

    def test_session_tracks_last_items(self):
        session = SessionContext()
        self.assertFalse(session.has_context())
        session.update(["arcane_energize"])
        self.assertTrue(session.has_context())
        self.assertEqual(session.last_item_ids, ["arcane_energize"])

    def test_session_tracks_history(self):
        session = SessionContext()
        session.add_exchange("充沛多少钱", "45p")
        session.add_exchange("那呢", "还是45p")
        self.assertEqual(len(session.history), 2)

    def test_followup_reuses_last_item(self):
        prompts = []
        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: SAMPLE_ORDERS,
            model_call=lambda prompt: (prompts.append(prompt), "测试回复")[1],
        )
        agent.answer("充沛现在价格怎么样")
        self.assertEqual(agent.session.last_item_ids, ["arcane_energize"])

        prompts.clear()
        agent.answer("现在呢")
        self.assertTrue(len(prompts) > 0)
        self.assertIn("arcane_energize", prompts[0])

    def test_no_context_falls_through_to_normal_resolution(self):
        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: SAMPLE_ORDERS,
            model_call=lambda prompt: "测试回复",
        )
        answer = agent.answer("现在呢")
        self.assertIn("没有找到", answer)


if __name__ == "__main__":
    unittest.main()
