"""Tests for game event tracking (events.py)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from warframe_agent.events import EventTracker, GameEvent, PrimeResurgenceItem, PrimeResurgenceRotation, _classify_event


# ── GameEvent ──

def test_game_event_defaults():
    e = GameEvent(event_type="alert")
    assert e.impact == "neutral"
    assert e.items_affected == []
    assert e.description == ""


# ── _classify_event ──

def test_classify_baro():
    raw = {"type": "baro_visit", "description": "Baro 来了", "activation": "2026-01-01", "expiry": "2026-01-03"}
    e = _classify_event(raw)
    assert e is not None
    assert e.event_type == "baro_visit"
    assert e.impact == "positive"
    assert "Baro" in e.description


def test_classify_alert():
    raw = {"type": "alert", "description": "特殊警报", "activation": "2026-01-01", "expiry": "2026-01-02"}
    e = _classify_event(raw)
    assert e is not None
    assert e.event_type == "alert"


def test_classify_unknown_returns_none():
    raw = {"type": "something_weird", "description": "???"}
    e = _classify_event(raw)
    assert e is None


# ── parse_events ──

def test_parse_baro_active():
    world_state = {
        "voidTrader": {
            "active": True,
            "inventory": [
                {"item": "Primed Continuity"},
                {"item": "Primed Flow"},
            ],
            "activation": "2026-05-01T00:00:00Z",
            "expiry": "2026-05-03T00:00:00Z",
        },
        "alerts": [],
        "invasions": [],
        "voidStorms": [],
    }
    tracker = EventTracker()
    events = tracker.parse_events(world_state)
    assert len(events) == 1
    assert events[0].event_type == "baro_visit"
    assert len(events[0].items_affected) == 2
    assert "primed_continuity" in events[0].items_affected


def test_parse_no_events():
    world_state = {"voidTrader": {}, "alerts": [], "invasions": [], "voidStorms": []}
    tracker = EventTracker()
    events = tracker.parse_events(world_state)
    assert len(events) == 0


def test_parse_alerts():
    world_state = {
        "voidTrader": {},
        "alerts": [
            {"active": True, "mission": {"description": "救援任务"}, "activation": "", "expiry": ""},
            {"active": False, "mission": {"description": "过期"}, "activation": "", "expiry": ""},
        ],
        "invasions": [],
        "voidStorms": [],
    }
    tracker = EventTracker()
    events = tracker.parse_events(world_state)
    assert len(events) == 1  # only active


def test_parse_prime_resurgence(monkeypatch):
    import warframe_agent.events as events_module

    monkeypatch.setattr(events_module.time, "time", lambda: 1779000000)
    world_state = {
        "PrimeVaultTraders": [
            {
                "Activation": {"$date": {"$numberLong": "1778781600000"}},
                "Expiry": {"$date": {"$numberLong": "1781200800000"}},
                "Manifest": [
                    {"ItemType": "/Lotus/StoreItems/Powersuits/Rhino/RhinoPrime", "PrimePrice": 3},
                    {"ItemType": "/Lotus/StoreItems/Powersuits/Jade/NyxPrime", "PrimePrice": 3},
                    {"ItemType": "/Lotus/StoreItems/Types/Game/Projections/T1VoidProjectionRhinoNyxVaultABronze", "RegularPrice": 1},
                ],
                "ScheduleInfo": [
                    {
                        "Expiry": {"$date": {"$numberLong": "1781200800000"}},
                        "FeaturedItem": "/Lotus/Types/StoreItems/Packages/MegaPrimeVault/MPVRhinoNyxPrimeDualPack",
                    },
                    {
                        "Expiry": {"$date": {"$numberLong": "1783620000000"}},
                        "FeaturedItem": "/Lotus/Types/StoreItems/Packages/MegaPrimeVault/MPVLokiEmberPrimeDualPack",
                    },
                ],
            }
        ],
    }

    tracker = EventTracker()
    events = tracker.parse_events(world_state)
    event = next(e for e in events if e.event_type == "prime_resurgence")

    assert event.description == "Prime 重生: Rhino Prime + Nyx Prime"
    assert event.prime_resurgence is not None
    assert event.prime_resurgence.featured_names == ["Rhino Prime", "Nyx Prime"]
    assert event.prime_resurgence.end_time == "2026-06-11 18:00 UTC"
    assert event.prime_resurgence.next_featured_names == ["Loki Prime", "Ember Prime"]
    assert event.prime_resurgence.next_start_time == "2026-06-11 18:00 UTC"
    assert event.prime_resurgence.next_end_time == "2026-07-09 18:00 UTC"
    assert [item.item_name for item in event.prime_resurgence.items[:2]] == ["Rhino Prime", "Nyx Prime"]


def test_get_event_impact_baro_item():
    tracker = EventTracker()
    tracker._events = [
        GameEvent(
            event_type="baro_visit",
            items_affected=["primed_continuity", "primed_flow"],
            description="Baro 来访",
        ),
    ]
    impact = tracker.get_event_impact("primed_continuity")
    assert impact is not None
    assert "Baro" in impact


def test_get_event_impact_unrelated():
    tracker = EventTracker()
    tracker._events = [
        GameEvent(event_type="alert", description="普通警报"),
    ]
    impact = tracker.get_event_impact("serration")
    assert impact is None


# ── cache ──

def test_save_load_cache(tmp_path):
    from warframe_agent.events import EVENT_CACHE_PATH
    import warframe_agent.events as events_module

    # Patch cache path
    original_path = events_module.EVENT_CACHE_PATH
    events_module.EVENT_CACHE_PATH = tmp_path / "cache.json"

    try:
        tracker = EventTracker()
        tracker._events = [
            GameEvent(event_type="baro_visit", description="Test Baro", items_affected=["primed_flow"]),
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
                    items=[PrimeResurgenceItem("/Lotus/StoreItems/Powersuits/Rhino/RhinoPrime", "Rhino Prime", "", 3, 0)],
                ),
            ),
        ]
        tracker._last_fetch = 12345.0
        tracker._save_cache()

        tracker2 = EventTracker()
        tracker2.load_cache()
        assert len(tracker2._events) == 2
        assert tracker2._events[0].event_type == "baro_visit"
        assert tracker2._events[1].prime_resurgence is not None
        assert tracker2._events[1].prime_resurgence.featured_names == ["Rhino Prime", "Nyx Prime"]
        assert tracker2._events[1].prime_resurgence.next_featured_names == ["Loki Prime", "Ember Prime"]
        assert tracker2._events[1].prime_resurgence.next_end_time == "2026-07-09 18:00 UTC"
        assert tracker2._last_fetch == 12345.0
    finally:
        events_module.EVENT_CACHE_PATH = original_path


def test_fetch_world_state_failure():
    tracker = EventTracker()
    tracker.set_fetcher(lambda: (_ for _ in ()).throw(ConnectionError("down")))
    result = tracker.fetch_world_state()
    assert result is None


def test_refresh_uses_cache_on_failure():
    tracker = EventTracker()
    tracker._events = [GameEvent(event_type="alert", description="cached")]
    tracker._last_fetch = 9999999999.0  # far future → cache valid
    events = tracker.get_active_events()
    assert len(events) == 1
    assert events[0].description == "cached"
