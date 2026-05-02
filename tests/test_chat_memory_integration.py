import unittest

from warframe_agent.chat import ChatAgent
from warframe_agent.dictionary import ResolveResult
from warframe_agent.memory import AgentMemory, PriceAlert, TradingPreferences


class GeneratedResolver:
    aliases = {}
    generated_aliases = {"赤毒布拉玛": "kuva_bramma"}

    def resolve(self, name):
        if name == "赤毒布拉玛":
            return ResolveResult("kuva_bramma", "generated_alias", name)
        raise LookupError(name)


class AlertResolver:
    aliases = {"充沛": "arcane_energize"}
    generated_aliases = {}

    def resolve(self, name):
        if name == "充沛":
            return ResolveResult("arcane_energize", "alias", name)
        raise LookupError(name)


ORDERS = [
    {"type": "sell", "platinum": 40, "quantity": 21, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10}},
    {"type": "buy", "platinum": 35, "quantity": 5, "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 5}},
]


class ChatMemoryIntegrationTests(unittest.TestCase):
    def test_generated_alias_substring_is_detected(self):
        prompts = []
        agent = ChatAgent(
            resolver=GeneratedResolver(),
            order_fetcher=lambda item_id: ORDERS,
            model_call=lambda prompt: prompts.append(prompt) or "赤毒布拉玛 / Kuva Bramma / kuva_bramma：已识别。",
        )

        answer = agent.answer("赤毒布拉玛现在价格怎么样")

        self.assertIn("kuva_bramma", answer)
        self.assertIn("Kuva Bramma", prompts[0])

    def test_memory_alert_is_added_to_prompt(self):
        memory = AgentMemory(
            preferences=TradingPreferences(platform="pc", crossplay=True, max_results=5),
            price_alerts=[PriceAlert("arcane_energize", "below", 45, "充沛低于45提醒")],
            favorite_items=["arcane_energize"],
            common_questions=[],
            watchlist=[],
        )
        prompts = []
        agent = ChatAgent(
            resolver=AlertResolver(),
            order_fetcher=lambda item_id: ORDERS,
            model_call=lambda prompt: prompts.append(prompt) or "触发提醒：充沛低于45。",
            memory=memory,
        )

        answer = agent.answer("充沛现在价格怎么样")

        self.assertIn("触发提醒", answer)
        self.assertIn("记忆提醒: 充沛低于45提醒", prompts[0])
        self.assertIn("偏好: platform=pc, crossplay=True", prompts[0])


if __name__ == "__main__":
    unittest.main()
