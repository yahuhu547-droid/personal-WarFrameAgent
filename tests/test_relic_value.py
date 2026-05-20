from __future__ import annotations

from warframe_agent.relics import RelicDrop, RelicInfo
from warframe_agent.relic_value import (
    analyze_relic_value,
    format_relic_value_for_display,
    format_relic_value_for_model,
)


class FakeGameData:
    def __init__(self, ducats: dict[str, int | None] | None = None):
        self.ducats = ducats or {}

    def get_ducat_value(self, item_id: str) -> int | None:
        return self.ducats.get(item_id)


def make_relic() -> RelicInfo:
    return RelicInfo(
        name="Lith B1",
        tier="Lith",
        is_vaulted=False,
        drops=[
            RelicDrop("Lith B1", "Lith", "Braton Prime Blueprint", "braton_prime_blueprint", "COMMON", 0.2533),
            RelicDrop("Lith B1", "Lith", "Paris Prime String", "paris_prime_string", "UNCOMMON", 0.11),
            RelicDrop("Lith B1", "Lith", "Forma Blueprint", "forma_blueprint", "RARE", 0.02),
        ],
    )


def test_relic_value_prefers_highest_buy_price_for_conservative_ev():
    orders_by_item = {
        "braton_prime_blueprint": [
            {"type": "sell", "platinum": 8, "quantity": 1, "user": {"ingameName": "Seller_RAW_ORDER_SENTINEL", "status": "ingame"}},
            {"type": "buy", "platinum": 5, "quantity": 1, "user": {"ingameName": "Buyer_RAW_ORDER_SENTINEL", "status": "ingame"}},
        ],
        "paris_prime_string": [
            {"type": "sell", "platinum": 10, "quantity": 1, "user": {"ingameName": "Seller2", "status": "ingame"}},
            {"type": "buy", "platinum": 7, "quantity": 1, "user": {"ingameName": "Buyer2", "status": "ingame"}},
        ],
        "forma_blueprint": [
            {"type": "sell", "platinum": 3, "quantity": 1, "user": {"ingameName": "Seller3", "status": "ingame"}},
        ],
    }

    report = analyze_relic_value(
        make_relic(),
        order_fetcher=lambda item_id: orders_by_item.get(item_id, []),
        game_data=FakeGameData({
            "braton_prime_blueprint": 15,
            "paris_prime_string": 45,
            "forma_blueprint": None,
        }),
    )

    rewards = {reward.market_id: reward for reward in report.reward_values}
    assert rewards["braton_prime_blueprint"].valuation_price == 5
    assert rewards["braton_prime_blueprint"].valuation_source == "highest_buy"
    assert rewards["paris_prime_string"].valuation_price == 7
    assert rewards["forma_blueprint"].valuation_price == 3
    assert rewards["forma_blueprint"].valuation_source == "lowest_sell_fallback"
    assert report.expected_platinum == round(0.2533 * 5 + 0.11 * 7 + 0.02 * 3, 2)
    assert report.expected_ducats == round(0.2533 * 15 + 0.11 * 45, 2)


def test_unknown_ducat_value_is_not_guessed_or_used_for_efficiency():
    report = analyze_relic_value(
        make_relic(),
        order_fetcher=lambda item_id: [
            {"type": "buy", "platinum": 4, "quantity": 1, "user": {"ingameName": "Buyer", "status": "ingame"}}
        ],
        game_data=FakeGameData({"braton_prime_blueprint": 15}),
    )

    forma = next(reward for reward in report.reward_values if reward.market_id == "forma_blueprint")
    assert forma.ducat_value is None
    assert forma.ducats_per_plat is None
    assert "未知杜卡德值" in forma.data_warnings
    assert report.expected_ducats == round(0.2533 * 15, 2)


def test_display_and_model_format_include_ev_but_model_context_is_safe():
    report = analyze_relic_value(
        make_relic(),
        order_fetcher=lambda item_id: [
            {
                "type": "sell",
                "platinum": 8,
                "quantity": 1,
                "profile_url": "https://warframe.market/profile/Seller_RAW_ORDER_SENTINEL",
                "user": {"ingameName": "Seller_RAW_ORDER_SENTINEL", "status": "ingame"},
            },
            {
                "type": "buy",
                "platinum": 5,
                "quantity": 1,
                "user": {"ingameName": "Buyer_RAW_ORDER_SENTINEL", "status": "ingame"},
            },
        ],
        game_data=FakeGameData({
            "braton_prime_blueprint": 15,
            "paris_prime_string": 45,
            "forma_blueprint": None,
        }),
    )

    display = format_relic_value_for_display(report)
    model_context = format_relic_value_for_model(report)

    assert "Lith B1" in display
    assert "期望白金" in display
    assert "期望杜卡德" in display
    assert "tool=relic_value" in model_context
    assert "expected_platinum" in model_context
    assert "highest_buy" in model_context
    for forbidden in [
        "Seller_RAW_ORDER_SENTINEL",
        "Buyer_RAW_ORDER_SENTINEL",
        "https://warframe.market/profile",
        "/w",
        "whisper",
        "RAW_ORDER_SENTINEL",
    ]:
        assert forbidden not in model_context
