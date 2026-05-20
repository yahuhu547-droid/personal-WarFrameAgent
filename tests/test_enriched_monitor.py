"""测试规则驱动监控：机会检测、知识库集成、市场状态评估。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from warframe_agent.monitor import (
    EnrichedNotification,
    FavoriteSnapshot,
    PriceMonitor,
    ScanResult,
    detect_opportunities,
)
from warframe_agent.knowledge import MarketKnowledge
from warframe_agent.price_history import PriceHistoryDB


# ── detect_opportunities ──

def test_detect_opportunities_finds_high_spread():
    snapshots = [
        FavoriteSnapshot(item_id="a", item_display="A", sell_price=100, buy_price=40),
    ]
    opps = detect_opportunities(snapshots)
    assert len(opps) == 1
    assert opps[0].suggestion_type == "opportunity"
    assert "买卖盘价差" in opps[0].message
    assert "原因" in opps[0].message
    assert "100p" in opps[0].message
    assert "40p" in opps[0].message
    assert "40%" in opps[0].message
    assert opps[0].data["source"] == "spread"
    assert opps[0].data["sell_price"] == 100
    assert opps[0].data["buy_price"] == 40
    assert opps[0].data["spread"] == 60
    assert opps[0].data["spread_pct"] == 150.0
    assert opps[0].data["threshold_pct"] == 40
    assert "原因" in opps[0].data["rationale"]
    assert "低买高卖" not in opps[0].message


def test_detect_opportunities_ignores_low_spread():
    snapshots = [
        FavoriteSnapshot(item_id="b", item_display="B", sell_price=50, buy_price=45),
    ]
    opps = detect_opportunities(snapshots)
    assert len(opps) == 0


def test_detect_opportunities_ignores_missing_prices():
    snapshots = [
        FavoriteSnapshot(item_id="c", item_display="C", sell_price=None, buy_price=None),
    ]
    assert detect_opportunities(snapshots) == []


@patch("warframe_agent.monitor.load_item_data")
def test_detect_opportunities_filters_mod_only(load_item_data_mock):
    load_item_data_mock.return_value = {
        "primed_flow": {"item_id": "primed_flow", "tags": ["mod"], "tradable": True, "modMaxRank": 10},
        "arcane_energize": {"item_id": "arcane_energize", "tags": ["arcane_enhancement"]},
        "mesa_prime_set": {"item_id": "mesa_prime_set", "tags": ["prime", "set"]},
    }
    snapshots = [
        FavoriteSnapshot(item_id="primed_flow", item_display="Primed Flow", sell_price=100, buy_price=40),
        FavoriteSnapshot(item_id="arcane_energize", item_display="Arcane Energize", sell_price=100, buy_price=40),
        FavoriteSnapshot(item_id="mesa_prime_set", item_display="Mesa Prime Set", sell_price=100, buy_price=40),
    ]

    opps = detect_opportunities(snapshots, opportunity_filter="mod")

    assert [opp.item_id for opp in opps] == ["primed_flow"]


@patch("warframe_agent.monitor.load_item_data")
def test_detect_opportunities_filters_arcane_only(load_item_data_mock):
    load_item_data_mock.return_value = {
        "primed_flow": {"item_id": "primed_flow", "tags": ["mod"], "tradable": True, "modMaxRank": 10},
        "arcane_energize": {"item_id": "arcane_energize", "tags": ["arcane_enhancement"]},
    }
    snapshots = [
        FavoriteSnapshot(item_id="primed_flow", item_display="Primed Flow", sell_price=100, buy_price=40),
        FavoriteSnapshot(item_id="arcane_energize", item_display="Arcane Energize", sell_price=100, buy_price=40),
    ]

    opps = detect_opportunities(snapshots, opportunity_filter="arcane")

    assert [opp.item_id for opp in opps] == ["arcane_energize"]


# ── PriceMonitor with knowledge ──

def test_monitor_with_knowledge():
    """验证 knowledge 参数被正确传递。"""
    knowledge = MarketKnowledge()
    monitor = PriceMonitor(
        order_fetcher=lambda _: [],
        knowledge=knowledge,
    )
    assert monitor.knowledge is knowledge


def test_monitor_default_knowledge():
    """验证未传 knowledge 时自动创建空知识库。"""
    monitor = PriceMonitor(order_fetcher=lambda _: [])
    assert isinstance(monitor.knowledge, MarketKnowledge)
    assert monitor.knowledge.get_item_stats("anything") is None


def test_enriched_notification_fields():
    n = EnrichedNotification(
        item_id="test",
        item_display="Test",
        notification_type="anomaly",
        raw_data={"current": 100},
        analysis="分析文本",
        priority=1,
    )
    assert n.item_id == "test"
    assert n.notification_type == "anomaly"
    assert n.analysis == "分析文本"
    assert n.priority == 1


# ── predict_trend ──

def test_predict_trend_linear_regression(tmp_path):
    """用已知数据序列验证线性回归预测。"""
    db_path = tmp_path / "test_prices.db"
    db = PriceHistoryDB(db_path)

    # 录入线性递增数据：10, 20, 30, ..., 100
    for i in range(1, 11):
        db.record("test_item", sell_price=i * 10, buy_price=i * 10 - 5)

    result = db.predict_trend("test_item")
    assert result is not None
    assert result["direction"] in ("rising", "falling", "stable")
    assert result["data_points"] == 10
    assert result["current"] == 100
    # 斜率应为正（线性递增）
    assert result["slope"] > 0


def test_predict_trend_returns_none_for_no_data(tmp_path):
    db = PriceHistoryDB(tmp_path / "empty.db")
    assert db.predict_trend("nonexistent") is None
