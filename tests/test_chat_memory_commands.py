import tempfile
import unittest
from pathlib import Path

from warframe_agent.chat import ChatAgent
from warframe_agent.memory import AgentMemory


class MemoryCommandResolver:
    aliases = {"充沛": "arcane_energize"}
    generated_aliases = {}

    def resolve(self, name):
        if name == "充沛":
            class Result:
                item_id = "arcane_energize"
            return Result()
        raise LookupError(name)


class ChatMemoryCommandTests(unittest.TestCase):
    def test_memory_command_can_add_favorite_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("/fav add 充沛")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已添加收藏", answer)
        self.assertIn("arcane_energize", saved.favorite_items)

    def test_memory_command_can_add_alert_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("/alert add 充沛 below 45")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已添加提醒", answer)
        self.assertEqual(saved.price_alerts[0].item_id, "arcane_energize")
        self.assertEqual(saved.price_alerts[0].price, 45)

    def test_regular_question_is_saved_into_common_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "测试回复",
                memory_path=memory_path,
            )

            agent.answer("充沛现在价格怎么样")
            saved = AgentMemory.load(memory_path)

        self.assertIn("充沛现在价格怎么样", saved.common_questions)


if __name__ == "__main__":
    unittest.main()
