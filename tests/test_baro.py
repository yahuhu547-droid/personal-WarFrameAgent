from warframe_agent.baro import (
    analyze_baro_inventory,
    format_baro_order_details,
    format_baro_order_details_for_model,
    format_baro_report,
    parse_baro_rank_request,
)
from warframe_agent.chat import ChatAgent
from warframe_agent.events import BaroItem, GameEvent


def _baro_event():
    return GameEvent(
        event_type="baro_visit",
        description="Baro active",
        baro_items=[
            BaroItem(
                item_type="/Lotus/Upgrades/Mods/PrimedFlow",
                item_name="Primed Flow",
                market_id="primed_flow",
                ducat_cost=350,
                credit_cost=110000,
            ),
            BaroItem(
                item_type="/Lotus/Types/Items/MiscItems/Decoration",
                item_name="Decoration",
                market_id="baro_decoration",
                ducat_cost=100,
                credit_cost=100000,
            ),
            BaroItem(
                item_type="/Lotus/Powersuits/Operator/ArcaneTest",
                item_name="Arcane Test",
                market_id="arcane_test",
                ducat_cost=500,
                credit_cost=200000,
            ),
            BaroItem(
                item_type="/Lotus/StoreItems/Upgrades/Mods/Shotgun/DualStat/FireEventShotgunMod",
                item_name="FireEventShotgunMod",
                market_id="",
                ducat_cost=300,
                credit_cost=150000,
            ),
        ],
    )


def _orders(item_id):
    return {
        "primed_flow": [
            {"type": "sell", "platinum": 11, "quantity": 2, "mod_rank": 0, "user": {"ingameName": "SellerR0", "status": "ingame", "reputation": 1}},
            {"type": "sell", "platinum": 95, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "SellerR10", "status": "ingame", "reputation": 4}},
            {"type": "sell", "platinum": 105, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "SellerR10", "status": "ingame", "reputation": 2}},
            {"type": "buy", "platinum": 9, "quantity": 3, "mod_rank": 0, "user": {"ingameName": "BuyerR0", "status": "ingame", "reputation": 2}},
            {"type": "buy", "platinum": 80, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "BuyerR10", "status": "ingame", "reputation": 3}},
            {"type": "buy", "platinum": 79, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "BuyerR10B", "status": "ingame", "reputation": 1}},
            {"type": "buy", "platinum": 78, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "BuyerR10C", "status": "ingame", "reputation": 1}},
            {"type": "buy", "platinum": 77, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "BuyerR10D", "status": "ingame", "reputation": 1}},
            {"type": "buy", "platinum": 76, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "BuyerR10E", "status": "ingame", "reputation": 1}},
            {"type": "buy", "platinum": 75, "quantity": 1, "mod_rank": 10, "user": {"ingameName": "BuyerR10", "status": "ingame", "reputation": 1}},
        ],
        "arcane_test": [
            {"type": "sell", "platinum": 7, "quantity": 21, "rank": 0, "user": {"ingameName": "ArcSeller", "status": "ingame", "reputation": 5}},
            {"type": "buy", "platinum": 5, "quantity": 5, "rank": 0, "user": {"ingameName": "ArcBuyer", "status": "ingame", "reputation": 6}},
        ],
    }.get(item_id, [])


ITEM_META = {
    "primed_flow": {"type": "mod", "max_rank": 10},
    "arcane_test": {"type": "arcane", "max_rank": 5},
}


def test_baro_report_lists_only_mods_and_arcanes_without_defaulting_to_rank_zero(monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime", "arcane_test": "测试赋能"}.get(item_id))
    recommendations = analyze_baro_inventory(_baro_event(), _orders, item_info_lookup=lambda item_id: ITEM_META.get(item_id))

    assert [r.market_id for r in recommendations] == ["primed_flow", "arcane_test", "scattering_inferno"]
    assert recommendations[0].rank == 10
    assert recommendations[0].best_buy_price == 80
    assert recommendations[0].best_sell_price == 95

    report = format_baro_report(recommendations)

    assert "川流不息 Prime R10 | 杜卡德金币: 350 | 最高买价: 80p | 最低卖价: 95p" in report
    assert "测试赋能 R5 | 杜卡德金币: 500 | 最高买价: 暂无订单 | 最低卖价: 暂无订单" in report
    assert "FireEventShotgunMod" not in report
    assert "-  |" not in report
    assert "等级:" not in report
    assert "Decoration" not in report
    assert "primed_flow" not in report
    assert "arcane_test" not in report
    assert "≈" not in report
    assert "÷" not in report


def test_baro_rank_request_uses_item_max_rank_for_full_rank():
    request = parse_baro_rank_request("满级虚空商人推荐")
    recommendations = analyze_baro_inventory(
        _baro_event(),
        _orders,
        rank_request=request,
        item_info_lookup=lambda item_id: ITEM_META.get(item_id),
    )

    primed_flow = next(r for r in recommendations if r.market_id == "primed_flow")
    arcane = next(r for r in recommendations if r.market_id == "arcane_test")

    assert primed_flow.rank == 10
    assert primed_flow.best_buy_price == 80
    assert primed_flow.best_sell_price == 95
    assert arcane.rank == 5


def test_baro_order_details_include_profile_links_and_ranked_whispers():
    recommendations = analyze_baro_inventory(
        _baro_event(),
        _orders,
        rank_request=10,
        item_info_lookup=lambda item_id: ITEM_META.get(item_id),
    )
    primed_flow = next(r for r in recommendations if r.market_id == "primed_flow")

    details = format_baro_order_details(primed_flow, seller_limit=1, buyer_limit=1)

    assert "买家 1. BuyerR10 | 80p | 数量 1 | https://warframe.market/profile/BuyerR10" in details
    assert '/w BuyerR10 Hi! I want to sell: "' in details
    assert '(Rank 10)" for 80 platinum. (warframe.market)' in details
    assert "primed_flow" not in details
    assert "卖家 1. SellerR10 | 95p | 数量 1 | https://warframe.market/profile/SellerR10" in details
    assert '/w SellerR10 Hi! I want to buy: "' in details
    assert '(Rank 10)" for 95 platinum. (warframe.market)' in details


def test_baro_order_details_model_context_excludes_player_links_and_whispers():
    recommendations = analyze_baro_inventory(
        _baro_event(),
        _orders,
        rank_request=10,
        item_info_lookup=lambda item_id: ITEM_META.get(item_id),
    )
    primed_flow = next(r for r in recommendations if r.market_id == "primed_flow")

    context = format_baro_order_details_for_model(primed_flow, seller_limit=1, buyer_limit=2)

    assert "tool=baro_order_followup" in context
    assert "item=川流不息 Prime" in context
    assert "rank=10" in context
    assert "buyer_count=2" in context
    assert "best_buy=80p" in context
    assert "seller_count=1" in context
    assert "best_sell=95p" in context
    for forbidden in [
        "BuyerR10",
        "BuyerR10B",
        "SellerR10",
        "https://warframe.market/profile",
        "/w ",
        "raw buyers",
        "raw sellers",
    ]:
        assert forbidden not in context


def test_order_detail_limits_default_to_five_highest_buyers_for_link_followup():
    from warframe_agent.baro import parse_order_detail_limits

    assert parse_order_detail_limits("给我玩家链接") == (5, 0)
    assert parse_order_detail_limits("多个卖家") == (0, 5)
    assert parse_order_detail_limits("多个买家") == (5, 0)
    assert parse_order_detail_limits("3个买家") == (3, 0)
    assert parse_order_detail_limits("三个买家") == (3, 0)
    assert parse_order_detail_limits("3个卖家") == (0, 3)
    assert parse_order_detail_limits("三个卖家") == (0, 3)
    assert parse_order_detail_limits("2个买家和3个卖家") == (2, 3)
    assert parse_order_detail_limits("2个买家和三个卖家") == (2, 3)
    assert parse_order_detail_limits("3个") == (3, 0)
    assert parse_order_detail_limits("给我第一个满级卖家链接") == (0, 1)


def test_chat_baro_unspecified_rank_link_followup_asks_for_rank():
    agent = ChatAgent(
        order_fetcher=_orders,
        event_tracker=FakeBaroTracker(),
        model_call=lambda prompt: "unused",
    )
    agent._baro_item_info_lookup = lambda item_id: ITEM_META.get(item_id)

    agent.answer("虚空商人mod价格")
    followup = agent.answer("给我第一个玩家链接")

    assert "https://warframe.market/profile/BuyerR10" in followup
    assert "(Rank 10)" in followup


class FakeBaroTracker:
    def get_active_events(self):
        return [_baro_event()]


def test_chat_baro_query_then_order_link_followup():
    agent = ChatAgent(
        order_fetcher=_orders,
        event_tracker=FakeBaroTracker(),
        model_call=lambda prompt: "unused",
    )
    agent._baro_item_info_lookup = lambda item_id: ITEM_META.get(item_id)

    answer = agent.answer("虚空商人满级mod价格")

    assert "川流不息 Prime R10 | 杜卡德金币: 350 | 最高买价: 80p | 最低卖价: 95p" in answer
    assert "等级:" not in answer
    assert "≈" not in answer

    followup = agent.answer("给我第一个玩家链接")

    assert "https://warframe.market/profile/BuyerR10" in followup
    assert "https://warframe.market/profile/SellerR10" not in followup
    assert "(Rank 10)" in followup


def test_chat_baro_link_followup_defaults_to_five_highest_buy_price_players():
    agent = ChatAgent(
        order_fetcher=_orders,
        event_tracker=FakeBaroTracker(),
        model_call=lambda prompt: "unused",
    )
    agent._baro_item_info_lookup = lambda item_id: ITEM_META.get(item_id)

    agent.answer("虚空商人满级mod价格")
    followup = agent.answer("给我最高买价的玩家链接")

    assert "买家 1. BuyerR10 | 80p" in followup
    assert "买家 5. BuyerR10E | 76p" in followup
    assert "BuyerR10" in followup
    assert "卖家 1." not in followup


def test_chat_baro_link_followup_session_history_is_safe():
    agent = ChatAgent(
        order_fetcher=_orders,
        event_tracker=FakeBaroTracker(),
        model_call=lambda prompt: "unused",
    )
    agent._baro_item_info_lookup = lambda item_id: ITEM_META.get(item_id)

    agent.answer("虚空商人满级mod价格")
    followup = agent.answer("给我第一个玩家链接")

    assert "BuyerR10" in followup
    assert "https://warframe.market/profile/BuyerR10" in followup
    stored_reply = agent.session.history[-1][1]
    assert "tool=baro_order_followup" in stored_reply
    assert "best_buy=80p" in stored_reply
    for forbidden in ["BuyerR10", "SellerR10", "https://warframe.market/profile", "/w "]:
        assert forbidden not in stored_reply


def test_chat_baro_items_wording_uses_fast_path(monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime", "arcane_test": "测试赋能", "scattering_inferno": "炼狱轰击"}.get(item_id))
    agent = ChatAgent(
        order_fetcher=_orders,
        event_tracker=FakeBaroTracker(),
        model_call=lambda prompt: "MODEL",
    )
    agent._baro_item_info_lookup = lambda item_id: ITEM_META.get(item_id)

    answer = agent.answer("虚空商人带来了什么物品")

    assert "川流不息 Prime R10 | 杜卡德金币: 350 | 最高买价: 80p | 最低卖价: 95p" in answer
    assert "测试赋能 R5 | 杜卡德金币: 500 | 最高买价: 暂无订单 | 最低卖价: 暂无订单" in answer
    assert "炼狱轰击" in answer
    assert "FireEventShotgunMod" not in answer
    assert "-  |" not in answer
    assert "Decoration" not in answer
    assert "Primed Flow" not in answer
    assert "Arcane Test" not in answer
    assert "没有可分析" not in answer
    assert "MODEL" not in answer


def test_baro_report_prefers_chinese_names_only(monkeypatch):
    from warframe_agent import baro

    monkeypatch.setattr(baro, "preferred_chinese_name", lambda item_id: {"primed_flow": "川流不息 Prime", "arcane_test": "测试赋能"}.get(item_id))
    recommendations = analyze_baro_inventory(_baro_event(), _orders, item_info_lookup=lambda item_id: ITEM_META.get(item_id))

    report = format_baro_report(recommendations)

    assert "川流不息 Prime" in report
    assert "测试赋能" in report
    assert "primed_flow" not in report
    assert "arcane_test" not in report
