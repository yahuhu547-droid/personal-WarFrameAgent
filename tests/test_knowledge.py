"""Tests for MarketKnowledge (knowledge base)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from warframe_agent.knowledge import (
    ItemKnowledge,
    CategoryHealth,
    MarketKnowledge,
    _classify_category,
)


# ── _classify_category ──

def test_classify_arcane():
    assert _classify_category("arcane_energize") == ("arcane", "arcane")


def test_classify_mod_primed():
    assert _classify_category("primed_continuity") == ("mod", "primed")


def test_classify_mod_common():
    assert _classify_category("riven_mod_slash") == ("mod", "common")


def test_classify_prime_part():
    assert _classify_category("ember_prime_chassis") == ("prime_part", "prime")


def test_classify_other():
    assert _classify_category("morphics") == ("other", "other")


# ── ItemKnowledge ──

def test_item_knowledge_creation():
    ik = ItemKnowledge(item_id="test", category="mod", subcategory="primed")
    assert ik.item_id == "test"
    assert ik.volatility == 0.0
    assert ik.trend == "stable"
    assert ik.scan_count == 0
    assert ik.event_context is None


# ── CategoryHealth ──

def test_category_health_defaults():
    ch = CategoryHealth(category="mod")
    assert ch.opportunity_count == 0
    assert ch.trend == "neutral"
    assert ch.top_items == []


# ── MarketKnowledge ──

def test_get_item_stats_empty():
    mk = MarketKnowledge()
    assert mk.get_item_stats("nonexistent") is None


def test_get_item_stats_present():
    ik = ItemKnowledge(item_id="test", category="mod", subcategory="primed")
    mk = MarketKnowledge(items={"test": ik})
    assert mk.get_item_stats("test") is not None
    assert mk.get_item_stats("test").item_id == "test"


def test_get_category_health_empty():
    mk = MarketKnowledge()
    ch = mk.get_category_health("mod")
    assert ch.category == "mod"
    assert ch.opportunity_count == 0


def test_get_category_health_with_items():
    items = {
        "a": ItemKnowledge(item_id="a", category="mod", subcategory="primed", trend="rising", scan_count=10),
        "b": ItemKnowledge(item_id="b", category="mod", subcategory="common", trend="rising", scan_count=5),
        "c": ItemKnowledge(item_id="c", category="mod", subcategory="common", trend="falling", scan_count=3),
    }
    mk = MarketKnowledge(items=items)
    ch = mk.get_category_health("mod")
    assert ch.opportunity_count == 3
    assert ch.trend == "bullish"  # 2 rising vs 1 falling
    assert len(ch.top_items) == 3


def test_get_market_summary():
    items = {
        "a": ItemKnowledge(item_id="a", category="mod", subcategory="primed", trend="rising", volatility=20),
        "b": ItemKnowledge(item_id="b", category="prime_set", subcategory="prime", trend="stable", volatility=10),
    }
    mk = MarketKnowledge(items=items)
    summary = mk.get_market_summary()
    assert summary["total_items"] == 2
    assert summary["trend_direction"] == "bullish"  # 1 rising > 0 falling * 1.5
    assert summary["volatility_index"] == 15.0


def test_update_from_scan():
    price_db = MagicMock()
    price_db.recent.return_value = []
    price_db.predict_trend.return_value = None

    mk = MarketKnowledge()
    scan_results = [
        {"item_id": "arcane_energize", "profit": 50},
        {"item_id": "primed_continuity", "profit": 80},
    ]
    mk.update_from_scan(scan_results, price_db)
    assert mk.get_item_stats("arcane_energize") is not None
    assert mk.get_item_stats("arcane_energize").category == "arcane"
    assert mk.get_item_stats("arcane_energize").scan_count == 1
    assert mk.get_item_stats("primed_continuity").category == "mod"


def test_update_from_scan_incremental():
    price_db = MagicMock()
    price_db.recent.return_value = []
    price_db.predict_trend.return_value = None

    mk = MarketKnowledge()
    mk.update_from_scan([{"item_id": "test_item"}], price_db)
    assert mk.get_item_stats("test_item").scan_count == 1

    mk.update_from_scan([{"item_id": "test_item"}], price_db)
    assert mk.get_item_stats("test_item").scan_count == 2


def test_update_from_scan_with_price_data():
    snapshot = MagicMock()
    snapshot.sell_price = 100
    snapshot.buy_price = 80

    price_db = MagicMock()
    price_db.recent.return_value = [snapshot] * 5
    price_db.predict_trend.return_value = {"direction": "rising", "slope": 1.5, "predicted_next": 110, "data_points": 5, "current": 100}

    mk = MarketKnowledge()
    mk.update_from_scan([{"item_id": "test_item"}], price_db)
    stats = mk.get_item_stats("test_item")
    assert stats.rolling_avg_sell == 100.0
    assert stats.rolling_avg_buy == 80.0
    assert stats.trend == "rising"
    assert stats.volatility == 0.0  # all same price → 0 variance


def test_update_event_context():
    items = {
        "a": ItemKnowledge(item_id="a", category="mod", subcategory="primed"),
        "b": ItemKnowledge(item_id="b", category="mod", subcategory="common"),
    }
    mk = MarketKnowledge(items=items)
    events = [
        {"items_affected": ["a"], "description": "Baro 访问"},
    ]
    mk.update_event_context(events)
    assert mk.get_item_stats("a").event_context == "Baro 访问"
    assert mk.get_item_stats("b").event_context is None


def test_save_load_roundtrip():
    items = {
        "test": ItemKnowledge(
            item_id="test", category="mod", subcategory="primed",
            rolling_avg_sell=100.0, volatility=15.5, trend="rising",
            scan_count=5,
        ),
    }
    mk = MarketKnowledge(items=items)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    try:
        mk.save(path)
        loaded = MarketKnowledge.load(path)
        stats = loaded.get_item_stats("test")
        assert stats is not None
        assert stats.item_id == "test"
        assert stats.rolling_avg_sell == 100.0
        assert stats.volatility == 15.5
        assert stats.trend == "rising"
        assert stats.scan_count == 5
    finally:
        path.unlink()


def test_load_nonexistent():
    mk = MarketKnowledge.load(Path("/tmp/nonexistent_knowledge.json"))
    assert mk.get_item_stats("anything") is None


# ── predict_with_events ──

class FakeEvent:
    def __init__(self, items_affected, event_type="", impact="", description=""):
        self.items_affected = items_affected
        self.event_type = event_type
        self.impact = impact
        self.description = description


def test_predict_with_positive_event():
    """正面事件 + stable → rising。"""
    items = {
        "serration": ItemKnowledge(
            item_id="serration", category="mod", subcategory="common",
            trend="stable", scan_count=3,
        ),
    }
    mk = MarketKnowledge(items=items)
    events = [FakeEvent(items_affected=["serration"], impact="positive")]
    assert mk.predict_with_events("serration", events) == "rising"


def test_predict_with_negative_event():
    """负面事件 + stable → falling。"""
    items = {
        "serration": ItemKnowledge(
            item_id="serration", category="mod", subcategory="common",
            trend="stable", scan_count=3,
        ),
    }
    mk = MarketKnowledge(items=items)
    events = [FakeEvent(items_affected=["serration"], impact="negative")]
    assert mk.predict_with_events("serration", events) == "falling"


def test_predict_with_event_already_rising():
    """正面事件 + 已经 rising → 保持 rising。"""
    items = {
        "serration": ItemKnowledge(
            item_id="serration", category="mod", subcategory="common",
            trend="rising", scan_count=3,
        ),
    }
    mk = MarketKnowledge(items=items)
    events = [FakeEvent(items_affected=["serration"], impact="positive")]
    assert mk.predict_with_events("serration", events) == "rising"


def test_predict_no_events():
    """无事件时返回基础趋势。"""
    items = {
        "serration": ItemKnowledge(
            item_id="serration", category="mod", subcategory="common",
            trend="falling", scan_count=3,
        ),
    }
    mk = MarketKnowledge(items=items)
    assert mk.predict_with_events("serration", None) == "falling"


def test_predict_unknown_item():
    """未知物品返回 insufficient_data。"""
    mk = MarketKnowledge()
    assert mk.predict_with_events("unknown", []) == "insufficient_data"


def test_update_from_scan_with_events():
    """update_from_scan 注入事件上下文。"""
    snapshot = MagicMock()
    snapshot.sell_price = 100
    snapshot.buy_price = 80
    price_db = MagicMock()
    price_db.recent.return_value = [snapshot] * 3
    price_db.predict_trend.return_value = None

    events = [FakeEvent(items_affected=["test_item"], event_type="baro_visit", impact="positive", description="Baro 来了")]
    mk = MarketKnowledge()
    mk.update_from_scan([{"item_id": "test_item"}], price_db, events=events)
    stats = mk.get_item_stats("test_item")
    assert stats.event_context is not None
    assert "baro_visit" in stats.event_context
