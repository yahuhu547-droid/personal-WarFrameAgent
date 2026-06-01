from __future__ import annotations

from pathlib import Path

from warframe_agent.chat import ChatAgent
from warframe_agent.dictionary import ResolveResult
from warframe_agent.events import (
    BaroItem,
    EventTracker,
    GameEvent,
    PrimeResurgenceItem,
    PrimeResurgenceRotation,
)


def _orders(item_id: str) -> list[dict]:
    if item_id == "primed_flow":
        return [
            {
                "type": "sell",
                "platinum": 95,
                "quantity": 1,
                "mod_rank": 10,
                "user": {"ingameName": "SellerR10", "status": "ingame", "reputation": 4},
            },
            {
                "type": "buy",
                "platinum": 80,
                "quantity": 1,
                "mod_rank": 10,
                "user": {"ingameName": "BuyerR10", "status": "ingame", "reputation": 3},
            },
        ]
    if item_id == "arcane_test":
        return [
            {
                "type": "sell",
                "platinum": 7,
                "quantity": 21,
                "rank": 0,
                "user": {"ingameName": "ArcSeller", "status": "ingame", "reputation": 5},
            },
        ]
    if item_id == "arcane_energize":
        return [
            {
                "type": "sell",
                "platinum": 39,
                "quantity": 1,
                "user": {"ingameName": "EnergizeSeller", "status": "ingame", "reputation": 8},
            }
        ]
    return []


def _item_info(item_id: str) -> dict | None:
    return {
        "primed_flow": {"type": "mod", "max_rank": 10},
        "arcane_test": {"type": "arcane", "max_rank": 5},
    }.get(item_id)


class EventReplyTracker:
    def __init__(self):
        self._base = EventTracker()
        self._world_state = {
            "Goals": [
                {"Tag": "JadeShadowsEvent", "Node": "SolNode723"},
                {"Tag": "ThermiaFractures", "Node": "VenusHUB"},
            ],
            "ActiveMissions": [
                {
                    "Modifier": "VoidT1",
                    "MissionType": "MT_CAPTURE",
                    "Node": "SolNode1",
                    "Expiry": "1777921200000",
                },
                {
                    "Modifier": "VoidT4",
                    "MissionType": "MT_EXTERMINATION",
                    "Node": "SolNode742",
                    "Hard": True,
                    "Expiry": "1777924800000",
                },
            ],
            "VoidStorms": [{"Node": "CrewBattleNode1"}],
            "Invasions": [
                {
                    "Completed": False,
                    "LocTag": "/Lotus/Language/Menu/CorpusInvasionGeneric",
                }
            ],
        }
        self._events = self._base.parse_events(self._world_state)
        self._events.append(
            GameEvent(
                event_type="baro_visit",
                description="Baro Ki'Teer 来访 @ Strata Relay，库存 2 件物品",
                baro_items=[
                    BaroItem("/Lotus/Upgrades/Mods/PrimedFlow", "Primed Flow", "primed_flow", 350, 110000),
                    BaroItem("/Lotus/Powersuits/Operator/ArcaneTest", "Arcane Test", "arcane_test", 500, 200000),
                ],
            )
        )
        self._events.append(
            GameEvent(
                event_type="prime_resurgence",
                description="Prime 重生: Rhino Prime + Nyx Prime",
                prime_resurgence=PrimeResurgenceRotation(
                    featured_names=["Rhino Prime", "Nyx Prime"],
                    end_time="2026-06-11 18:00 UTC",
                    items=[
                        PrimeResurgenceItem(
                            "/Lotus/StoreItems/Powersuits/Rhino/RhinoPrime",
                            "Rhino Prime",
                            "rhino_prime_set",
                            3,
                            0,
                        ),
                        PrimeResurgenceItem(
                            "/Lotus/StoreItems/Powersuits/Nyx/NyxPrime",
                            "Nyx Prime",
                            "nyx_prime_set",
                            3,
                            0,
                        ),
                    ],
                ),
            )
        )

    def get_active_events(self):
        return list(self._events)

    def get_limited_events(self):
        return self._base.parse_limited_events(self._world_state)

    def get_active_fissures(self):
        return self._base.parse_fissures(self._world_state)


class EmptyEventTracker:
    def get_active_events(self):
        return []

    def get_limited_events(self):
        return []


class EnergizeResolver:
    def resolve(self, name: str) -> ResolveResult:
        lowered = name.lower()
        if "充沛" in name or "arcane_energize" in lowered:
            return ResolveResult("arcane_energize", "alias", name)
        raise LookupError(name)


def _agent(tmp_path: Path) -> ChatAgent:
    agent = ChatAgent(
        event_tracker=EventReplyTracker(),
        order_fetcher=_orders,
        resolver=EnergizeResolver(),
        model_call=lambda prompt: "unused",
        memory_path=tmp_path / "memory.json",
    )
    agent._baro_item_info_lookup = _item_info
    return agent


def test_generic_activity_reply_does_not_mix_specific_events(tmp_path):
    answer = _agent(tmp_path).answer("现在有什么活动")

    assert "当前限时活动" in answer
    assert "兽之腹" in answer
    assert "热美亚裂缝" in answer
    assert "当前虚空裂缝" not in answer
    assert "当前入侵" not in answer
    assert "当前虚空风暴" not in answer
    assert "当前虚空商人" not in answer


def test_specific_event_questions_do_not_fallback_to_limited_activity(tmp_path):
    agent = _agent(tmp_path)

    invasion = agent.answer("入侵有哪些")
    storm = agent.answer("虚空风暴现在有吗")
    baro = agent.answer("Baro 来了吗")

    assert "当前入侵" in invasion
    assert "Corpus 入侵" in invasion
    assert "当前限时活动" not in invasion
    assert "当前虚空风暴" in storm
    assert "当前限时活动" not in storm
    assert "当前虚空商人" in baro
    assert "当前限时活动" not in baro


def test_baro_mod_price_reply_contains_rank_prices_and_no_raw_names(tmp_path, monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(
        baro,
        "preferred_chinese_name",
        lambda item_id: {"primed_flow": "川流不息 Prime", "arcane_test": "测试赋能"}.get(item_id),
    )

    answer = _agent(tmp_path).answer("虚空商人满级mod价格")

    assert "## Baro Mod / 赋能价格" in answer
    assert "川流不息 Prime R10" in answer
    assert "杜卡德金币: 350" in answer
    assert "最高买价: 80p" in answer
    assert "最低卖价: 95p" in answer
    assert "Primed Flow" not in answer
    assert "BuyerR10" not in answer
    assert "/w " not in answer


def test_baro_inventory_wording_makes_scope_clear(tmp_path, monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(
        baro,
        "preferred_chinese_name",
        lambda item_id: {"primed_flow": "川流不息 Prime", "arcane_test": "测试赋能"}.get(item_id),
    )

    answer = _agent(tmp_path).answer("虚空商人带来了什么物品")

    assert "Baro" in answer
    assert "Mod / 赋能" in answer
    assert "仅展示可分析的 Mod / 赋能" in answer
    assert "川流不息 Prime" in answer
    assert "测试赋能" in answer


def test_baro_absent_replies_are_clear_and_do_not_fall_through(tmp_path):
    agent = ChatAgent(
        event_tracker=EmptyEventTracker(),
        model_call=lambda prompt: "unused",
        memory_path=tmp_path / "memory.json",
    )

    status = agent.answer("Baro 来了吗")
    price = agent.answer("虚空商人mod价格")

    assert "当前虚空商人" in status or "当前没有" in status
    assert "当前没有" in price or "暂无" in price
    assert "没有找到匹配的物品" not in status + price


def test_baro_followup_respects_buyer_seller_and_count(tmp_path, monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime"}.get(item_id))
    agent = _agent(tmp_path)
    agent.answer("虚空商人满级mod价格")

    buyer = agent.answer("给我第一个买家链接")
    seller = agent.answer("给我第一个卖家链接")

    assert "买家 1. BuyerR10 | 80p" in buyer
    assert "卖家 1." not in buyer
    assert "卖家 1. SellerR10 | 95p" in seller
    assert "买家 1." not in seller


def test_baro_followup_session_history_remains_safe(tmp_path, monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime"}.get(item_id))
    agent = _agent(tmp_path)
    agent.answer("虚空商人满级mod价格")

    reply = agent.answer("给我第一个玩家链接")
    stored_reply = agent.session.history[-1][1]

    assert "BuyerR10" in reply
    assert "tool=baro_order_followup" in stored_reply
    for forbidden in ["BuyerR10", "SellerR10", "https://warframe.market/profile", "/w "]:
        assert forbidden not in stored_reply


def test_baro_followup_does_not_hijack_later_market_link_query(tmp_path, monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime"}.get(item_id))
    agent = _agent(tmp_path)
    agent.answer("虚空商人满级mod价格")

    answer = agent.answer("充沛最便宜卖家链接")

    assert "EnergizeSeller" in answer
    assert "https://warframe.market/items/arcane_energize" in answer
    assert "BuyerR10" not in answer
    assert "川流不息 Prime" not in answer


def test_unsupported_events_are_explicit_and_do_not_use_item_lookup(tmp_path):
    agent = _agent(tmp_path)
    for query, label in [
        ("午夜电波现在是什么", "午夜电波"),
        ("仲裁现在是什么", "仲裁"),
        ("突击任务", "突击"),
        ("Darvo 每日特惠", "每日特惠"),
        ("扎里曼赏金", "扎里曼"),
    ]:
        answer = agent.answer(query)
        assert f"当前数据源暂不支持{label}" in answer
        assert "不会编造结果" in answer
        assert "没有找到匹配的物品" not in answer


def test_event_keywords_do_not_hijack_market_relic_or_video_intents(tmp_path):
    agent = _agent(tmp_path)
    agent._try_router_result = lambda message, candidate_tools=None: "ROUTED_RELIC" if candidate_tools else None

    relic = agent.answer("这个遗物收益怎么样，最近有什么活动影响吗")
    activity = agent.answer("热美亚裂缝现在有吗")
    jade = agent.answer("兽之腹现在有吗")
    steel_exterminate = agent.answer("钢铁歼灭现在有吗")

    assert relic == "ROUTED_RELIC" or "期望" in relic or "暂时无法计算" in relic
    assert "热美亚裂缝" in activity
    assert "兽之腹" not in activity
    assert "当前虚空裂缝" not in activity
    assert "兽之腹" in jade
    assert "热美亚裂缝" not in jade
    assert "当前虚空裂缝" not in jade
    assert "当前虚空裂缝/裂隙" in steel_exterminate
    assert "钢铁" in steel_exterminate
    assert "歼灭" in steel_exterminate
    assert "当前限时活动" not in steel_exterminate
