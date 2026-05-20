from __future__ import annotations

from warframe_agent.events import VoidFissure
from warframe_agent.farming_route import (
    FarmingRouteReport,
    analyze_farming_route,
    format_farming_route_for_display,
    format_farming_route_for_model,
)
from warframe_agent.relics import RelicDrop, RelicInfo


class FakeRelicDB:
    def __init__(self):
        self.relics = {
            "Lith B1": RelicInfo(
                name="Lith B1",
                tier="Lith",
                is_vaulted=False,
                drops=[RelicDrop("Lith B1", "Lith", "Braton Prime Blueprint", "braton_prime_blueprint", "COMMON", 0.2533)],
            ),
            "Axi R1": RelicInfo(
                name="Axi R1",
                tier="Axi",
                is_vaulted=True,
                drops=[RelicDrop("Axi R1", "Axi", "Braton Prime Blueprint", "braton_prime_blueprint", "RARE", 0.02)],
            ),
        }

    def load(self, items=None):
        return None

    def find_by_part(self, query):
        if query in {"braton_prime_blueprint", "Braton Prime Blueprint", "布莱顿 Prime 蓝图"}:
            return [relic.drops[0] for relic in self.relics.values()]
        return []

    def find_by_relic(self, query):
        return self.relics.get(query)


class FakeGameData:
    def get_relic_sources(self, relic_name: str):
        return {
            "Lith B1": ["Hepit, Void 捕获", "Olympus, Mars 中断"],
            "Axi R1": [],
        }.get(relic_name, [])

    def is_vaulted(self, name: str) -> bool:
        return name == "Axi R1"

    def get_ducat_value(self, item_id: str):
        return {"braton_prime_blueprint": 15}.get(item_id)


FISSURES = [
    VoidFissure(
        node="SolNode22",
        node_display="虚空 - Hepit",
        mission_type="MT_CAPTURE",
        mission_display="捕获",
        tier="VoidT1",
        tier_display="古纪 (Lith)",
        hard=False,
        activation="2026-05-20T10:00:00Z",
        expiry="2026-05-20T11:00:00Z",
    ),
    VoidFissure(
        node="SolNode742",
        node_display="虚空 - Mot",
        mission_type="MT_SURVIVAL",
        mission_display="生存",
        tier="VoidT4",
        tier_display="后纪 (Axi)",
        hard=True,
        activation="2026-05-20T10:00:00Z",
        expiry="2026-05-20T11:00:00Z",
    ),
]


def test_analyze_farming_route_ranks_unvaulted_relic_with_active_fissure_higher():
    report = analyze_farming_route(
        target="braton_prime_blueprint",
        relic_db=FakeRelicDB(),
        game_data=FakeGameData(),
        fissures=FISSURES,
        order_fetcher=lambda item_id: [{"type": "buy", "platinum": 5}],
    )

    assert isinstance(report, FarmingRouteReport)
    assert report.target == "braton_prime_blueprint"
    assert report.routes[0].relic_name == "Lith B1"
    assert report.routes[0].drop_rate == 0.2533
    assert report.routes[0].is_vaulted is False
    assert report.routes[0].active_fissures[0].tier == "Lith"
    assert report.routes[0].score > report.routes[1].score
    assert "Hepit" in report.routes[0].sources[0]


def test_analyze_farming_route_accepts_relic_name_and_uses_all_rewards():
    report = analyze_farming_route(
        target="Lith B1",
        relic_db=FakeRelicDB(),
        game_data=FakeGameData(),
        fissures=FISSURES,
        order_fetcher=lambda item_id: [{"type": "buy", "platinum": 5}],
    )

    assert report.query_type == "relic"
    assert report.routes[0].relic_name == "Lith B1"
    assert report.routes[0].target_part == "Braton Prime Blueprint"
    assert report.routes[0].expected_platinum is not None
    assert report.routes[0].expected_ducats is not None


def test_format_farming_route_display_and_model_context_are_safe():
    report = analyze_farming_route(
        target="braton_prime_blueprint",
        relic_db=FakeRelicDB(),
        game_data=FakeGameData(),
        fissures=FISSURES,
        order_fetcher=lambda item_id: [
            {"type": "sell", "platinum": 8, "user": {"ingameName": "Seller_RAW_SENTINEL"}},
            {"type": "buy", "platinum": 5, "user": {"ingameName": "Buyer_RAW_SENTINEL"}},
        ],
    )

    display = format_farming_route_for_display(report)
    context = format_farming_route_for_model(report)

    assert "刷取路线" in display
    assert "Lith B1" in display
    assert "当前裂缝" in display
    assert "tool=farming_route" in context
    assert "score=" in context
    assert "drop_rate=" in context
    for forbidden in ["Seller_RAW_SENTINEL", "Buyer_RAW_SENTINEL", "https://warframe.market", "/w", "whisper", "RAW_SENTINEL"]:
        assert forbidden not in context
