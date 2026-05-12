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
        "mod_rank": 5,
        "user": {"ingameName": "Seller", "status": "ingame", "reputation": 10},
    },
    {
        "type": "buy",
        "platinum": 3,
        "quantity": 10,
        "mod_rank": 5,
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
        self.assertIn("满级价格（rank 5）: 5p", context)
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


# ── build_system_context tests ──

from warframe_agent.chat import build_system_context
from warframe_agent.knowledge import MarketKnowledge, ItemKnowledge, CategoryHealth
from warframe_agent.memory import AgentMemory, TradingPreferences


def test_build_system_context_empty():
    """所有数据为空时不崩溃。"""
    ctx = build_system_context()
    assert ctx == ""


def test_build_system_context_includes_knowledge():
    """知识库摘要出现。"""
    items = {
        "serration": ItemKnowledge(
            item_id="serration", category="mod", subcategory="common",
            rolling_avg_sell=10, rolling_avg_buy=5, volatility=20,
            trend="rising", volume_trend="stable", last_updated="", scan_count=5,
        ),
    }
    knowledge = MarketKnowledge(items=items)
    ctx = build_system_context(knowledge=knowledge)
    assert "市场概况" in ctx
    assert "跟踪物品=1" in ctx


def test_build_system_context_includes_trade_history():
    """交易统计出现。"""
    memory = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
    )
    ctx = build_system_context(memory=memory)
    # 无交易结果时不应出现交易统计
    assert "交易统计" not in ctx


def test_build_system_context_includes_trade_outcomes():
    """交易胜率出现。"""
    from warframe_agent.goals import TradeOutcome
    memory = AgentMemory(
        preferences=TradingPreferences(),
        price_alerts=[], favorite_items=[], common_questions=[], watchlist=[],
        trade_outcomes=[
            TradeOutcome(
                outcome_id="o1", goal_id="g1", action="bought", item_id="x",
                price=100, expected_profit=20, actual_profit=10,
                user_feedback="good", timestamp="2025-01-01T00:00:00",
            ),
        ],
    )
    ctx = build_system_context(memory=memory)
    assert "交易统计" in ctx
    assert "1/1" in ctx
