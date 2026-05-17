import unittest

from warframe_agent.chat import ChatAgent, build_item_context, is_chat_exit
from warframe_agent.dictionary import ResolveResult
from warframe_agent.events import EventTracker, GameEvent, PrimeResurgenceRotation, PrimeResurgenceItem, WorldCycle


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


def _prime_resurgence_tracker():
    tracker = EventTracker()
    tracker._last_fetch = 9999999999.0
    tracker._events = [
        GameEvent(
            event_type="prime_resurgence",
            description="Prime 重生: Rhino Prime + Nyx Prime",
            prime_resurgence=PrimeResurgenceRotation(
                featured_names=["Rhino Prime", "Nyx Prime"],
                start_time="2026-05-14 18:00 UTC",
                end_time="2026-06-11 18:00 UTC",
                next_featured_names=["Loki Prime", "Ember Prime"],
                next_start_time="2026-06-11 18:00 UTC",
                next_end_time="2026-07-09 18:00 UTC",
                items=[
                    PrimeResurgenceItem("/Lotus/StoreItems/Powersuits/Rhino/RhinoPrime", "Rhino Prime", "", 3, 0),
                    PrimeResurgenceItem("/Lotus/StoreItems/Powersuits/Jade/NyxPrime", "Nyx Prime", "", 3, 0),
                    PrimeResurgenceItem("/Lotus/StoreItems/Weapons/Tenno/Melee/AnkyrosPrime", "Ankyros Prime", "", 2, 0),
                    PrimeResurgenceItem("/Lotus/StoreItems/Weapons/Tenno/Rifle/BoltorPrime", "Boltor Prime", "", 2, 0),
                    PrimeResurgenceItem("/Lotus/StoreItems/Weapons/Tenno/Melee/ScindoPrime", "Scindo Prime", "", 3, 0),
                    PrimeResurgenceItem("/Lotus/StoreItems/Weapons/Tenno/ThrowingWeapons/HikouPrime", "Hikou Prime", "", 2, 0),
                    PrimeResurgenceItem("/Lotus/StoreItems/Types/Items/MiscItems/NoruPrimeScarf", "Noru Prime Scarf", "", 2, 0),
                    PrimeResurgenceItem("/Lotus/StoreItems/Types/Items/MiscItems/RhinoPrimeBobbleHead", "Rhino Prime Bobble Head", "", 1, 0),
                    PrimeResurgenceItem("/Lotus/Types/Game/Projections/T1VoidProjectionRhinoNyxVaultABronze", "T1 Void Projection Rhino Nyx Vault A Bronze", "", 0, 1),
                    PrimeResurgenceItem("/Lotus/Types/Game/Projections/T2VoidProjectionRhinoNyxVaultABronze", "T2 Void Projection Rhino Nyx Vault A Bronze", "", 0, 1),
                    PrimeResurgenceItem("/Lotus/Types/Game/Projections/T3VoidProjectionRhinoNyxVaultABronze", "T3 Void Projection Rhino Nyx Vault A Bronze", "", 0, 1),
                    PrimeResurgenceItem("/Lotus/Types/Game/Projections/T4VoidProjectionRhinoNyxVaultABronze", "T4 Void Projection Rhino Nyx Vault A Bronze", "", 0, 1),
                ],
            ),
        )
    ]
    return tracker



def test_cycle_status_and_alert_commands(tmp_path):
    tracker = EventTracker()
    tracker._world_state = {
        "earthCycle": {"isDay": False, "expiry": "2000"},
        "vallisCycle": {"isWarm": False, "expiry": "4000"},
    }
    tracker._last_fetch = 9999999999.0
    agent = ChatAgent(event_tracker=tracker, model_call=lambda prompt: "unused", memory_path=tmp_path / "memory.json")

    status = agent.answer("/cycle status 金星")
    assert "奥布山谷/金星当前为寒冷" in status

    added = agent.answer("/cycle add 地球 黑夜")
    assert "已订阅状态提醒：地球变为黑夜" in added
    assert "当前已经是目标状态" in added

    listing = agent.answer("/cycle list")
    assert "地球变为黑夜" in listing

    removed = agent.answer("/cycle remove 1")
    assert "已取消状态订阅" in removed


def test_cycle_natural_language_does_not_fall_through_to_item_lookup(tmp_path):
    tracker = EventTracker()
    tracker._world_state = {"vallisCycle": {"isWarm": False, "expiry": "4000"}}
    tracker._last_fetch = 9999999999.0
    agent = ChatAgent(event_tracker=tracker, model_call=lambda prompt: "unused", memory_path=tmp_path / "memory.json")

    query_answer = agent.answer("现在金星冷吗")
    assert "奥布山谷/金星当前为寒冷" in query_answer
    assert "没有找到匹配的物品" not in query_answer

    alert_answer = agent.answer("金星变寒冷提醒我")
    assert "奥布山谷/金星变为寒冷" in alert_answer
    assert agent.memory.cycle_alerts[0].cycle == "vallis"
    assert agent.memory.cycle_alerts[0].target_state == "cold"


def test_activity_query_returns_only_limited_events():
    tracker = EventTracker()
    tracker._last_fetch = 9999999999.0
    tracker._world_state = {
        "Goals": [
            {"Tag": "JadeShadowsEvent", "Node": "SolNode723"},
            {"Tag": "ThermiaFractures", "Node": "VenusHUB"},
        ],
        "ActiveMissions": [
            {"Modifier": "VoidT1", "MissionType": "MT_CAPTURE", "Node": "SolNode1"},
        ],
        "VoidStorms": [{"Node": "CrewBattleNode1"}],
        "Invasions": [{"Completed": False, "LocTag": "/Lotus/Language/Menu/CorpusInvasionGeneric"}],
    }
    tracker._events = tracker.parse_events(tracker._world_state)
    agent = ChatAgent(event_tracker=tracker, model_call=lambda prompt: "unused")

    answer = agent.answer("现在有什么活动")

    assert "兽之腹" in answer
    assert "热美亚裂缝" in answer
    assert "虚空裂缝" not in answer
    assert "虚空风暴" not in answer
    assert "入侵" not in answer


def test_specific_fissure_query_still_returns_fissures():
    tracker = EventTracker()
    tracker._last_fetch = 9999999999.0
    tracker._world_state = {
        "Goals": [{"Tag": "JadeShadowsEvent", "Node": "SolNode723"}],
        "ActiveMissions": [
            {"Modifier": "VoidT1", "MissionType": "MT_CAPTURE", "Node": "SolNode1"},
        ],
    }
    tracker._events = tracker.parse_events(tracker._world_state)
    agent = ChatAgent(event_tracker=tracker, model_call=lambda prompt: "unused")

    answer = agent.answer("裂隙任务有哪些")

    assert "当前虚空裂缝/裂隙" in answer
    assert "虚空裂缝" in answer
    assert "兽之腹" not in answer


def test_resurgence_command_formats_current_shop_items_only():
    agent = ChatAgent(event_tracker=_prime_resurgence_tracker(), model_call=lambda prompt: "unused")

    answer = agent.answer("/重生")

    assert "Prime 重生轮换:" not in answer
    assert "开始时间:" not in answer
    assert "下一期:" not in answer
    assert "可兑换返厂核桃:" not in answer
    assert "返厂战甲:" in answer
    assert "Rhino Prime" in answer
    assert "Nyx Prime" in answer
    assert "返厂武器:" in answer
    assert "甲龙双拳 Prime" in answer
    assert "螺钉步枪 Prime" in answer
    assert "分裂斩斧 Prime" in answer
    assert "飞扬 Prime" in answer
    assert "Scindo Prime" not in answer
    assert "可通过兑换当前 Prime 重生的古纪 B4、前纪 N6、中纪 R1、后纪 S3刷取" in answer
    assert "古纪 A" not in answer

def test_resurgence_natural_language_uses_direct_event_answer():
    agent = ChatAgent(event_tracker=_prime_resurgence_tracker(), model_call=lambda prompt: "unused")

    answer = agent.answer("当前 Prime 重生是谁，下一期是谁")

    assert "Rhino Prime" in answer
    assert "返厂战甲:" in answer
    assert "下一期:" not in answer
    assert "没有找到匹配的物品" not in answer


def test_resurgence_command_adds_set_price_when_orders_available():
    def order_fetcher(item_id):
        if item_id == "rhino_prime_set":
            return [
                {"type": "sell", "platinum": 90, "quantity": 1, "user": {"ingameName": "Seller", "status": "ingame", "reputation": 1}},
                {"type": "buy", "platinum": 100, "quantity": 1, "user": {"ingameName": "Buyer", "status": "ingame", "reputation": 1}},
            ]
        return []

    agent = ChatAgent(
        event_tracker=_prime_resurgence_tracker(),
        model_call=lambda prompt: "unused",
        order_fetcher=order_fetcher,
    )

    answer = agent.answer("当前 Prime 重生物品")

    assert "Rhino Prime" in answer
    assert "可通过兑换当前 Prime 重生的古纪 B4、前纪 N6" in answer
    assert "最高卖出价 100p" in answer
    assert "最低买入价 90p" in answer


def test_resurgence_filters_cosmetics_and_converts_internal_relic_names():
    agent = ChatAgent(event_tracker=_prime_resurgence_tracker(), model_call=lambda prompt: "unused")

    answer = agent.answer("Prime 重生物品")

    assert "Noru Prime Scarf" not in answer
    assert "Bobble Head" not in answer
    assert "T1 Void Projection" not in answer
    assert "古纪" in answer
    assert "前纪" in answer
    assert "中纪" in answer
    assert "后纪" in answer
    assert answer.count("Rhino Prime") == 1


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
