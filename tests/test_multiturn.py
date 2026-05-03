import unittest

from warframe_agent.chat import ChatAgent, build_chat_messages, build_system_prompt
from warframe_agent.memory import AgentMemory
from warframe_agent.session import SessionContext


class FakeResolver:
    aliases = {"充沛": "arcane_energize"}
    generated_aliases = {}

    def resolve(self, name):
        if name == "充沛":
            from warframe_agent.dictionary import ResolveResult
            return ResolveResult("arcane_energize", "alias", name)
        raise LookupError(name)


ORDERS = [
    {"type": "sell", "platinum": 40, "quantity": 21, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10}},
    {"type": "buy", "platinum": 35, "quantity": 5, "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 5}},
]


class SessionToMessagesTests(unittest.TestCase):
    def test_empty_history(self):
        session = SessionContext()
        self.assertEqual(session.to_messages(), [])

    def test_single_exchange(self):
        session = SessionContext()
        session.add_exchange("你好", "你好！有什么可以帮你的？")
        msgs = session.to_messages()
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0], {"role": "user", "content": "你好"})
        self.assertEqual(msgs[1], {"role": "assistant", "content": "你好！有什么可以帮你的？"})

    def test_limit_respected(self):
        session = SessionContext()
        for i in range(10):
            session.add_exchange(f"q{i}", f"a{i}")
        msgs = session.to_messages(limit=2)
        self.assertEqual(len(msgs), 4)
        self.assertEqual(msgs[0]["content"], "q8")
        self.assertEqual(msgs[2]["content"], "q9")

    def test_default_limit_from_config(self):
        session = SessionContext()
        for i in range(10):
            session.add_exchange(f"q{i}", f"a{i}")
        msgs = session.to_messages()
        self.assertEqual(len(msgs), 12)  # 6 exchanges * 2 messages each


class BuildChatMessagesTests(unittest.TestCase):
    def test_system_message_present(self):
        memory = AgentMemory.default()
        msgs = build_chat_messages("你好", [], memory)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("星际战甲", msgs[0]["content"])

    def test_history_included(self):
        memory = AgentMemory.default()
        history = [
            {"role": "user", "content": "之前的问题"},
            {"role": "assistant", "content": "之前的回答"},
        ]
        msgs = build_chat_messages("新问题", [], memory, history=history)
        # system(1) + history(2) + user_question(1) = 4
        self.assertEqual(len(msgs), 4)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["content"], "之前的问题")
        self.assertEqual(msgs[2]["content"], "之前的回答")
        self.assertEqual(msgs[3]["role"], "user")

    def test_no_history(self):
        memory = AgentMemory.default()
        msgs = build_chat_messages("问题", [], memory, history=None)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["role"], "user")


class MultiTurnIntegrationTests(unittest.TestCase):
    def test_session_history_accumulates(self):
        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: ORDERS,
            model_call=lambda prompt: "mock回答",
        )
        agent.answer("充沛多少钱")
        self.assertEqual(len(agent.session.history), 1)
        agent.answer("那现在呢")
        self.assertEqual(len(agent.session.history), 2)

    def test_to_messages_after_exchanges(self):
        agent = ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: ORDERS,
            model_call=lambda prompt: "mock回答",
        )
        agent.answer("充沛多少钱")
        agent.answer("那现在呢")
        msgs = agent.session.to_messages(limit=2)
        self.assertEqual(len(msgs), 4)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["content"], "充沛多少钱")
        self.assertEqual(msgs[2]["role"], "user")
        self.assertEqual(msgs[2]["content"], "那现在呢")


if __name__ == "__main__":
    unittest.main()
