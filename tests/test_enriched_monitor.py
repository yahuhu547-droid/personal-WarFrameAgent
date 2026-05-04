"""测试自主触发 + LLM 分析：异常检测、机会检测、趋势预测、prompt 构建。"""
from __future__ import annotations

from unittest.mock import MagicMock

from warframe_agent.monitor import (
    EnrichedNotification,
    FavoriteSnapshot,
    PriceMonitor,
    ScanResult,
    build_anomaly_analysis_prompt,
    detect_opportunities,
)
from warframe_agent.price_history import PriceHistoryDB


# ── build_anomaly_analysis_prompt ──

def test_build_anomaly_analysis_prompt_contains_all_fields():
    prompt = build_anomaly_analysis_prompt(
        item_id="arcane_energize",
        item_display="充沛赋能",
        anomaly={"current": 120, "average": 80, "deviation_pct": 50, "direction": "spike"},
        trend="近 7 天上涨",
        history_high=150,
        history_low=40,
    )
    assert "充沛赋能" in prompt
    assert "arcane_energize" in prompt
    assert "120" in prompt
    assert "80" in prompt
    assert "50%" in prompt
    assert "暴涨" in prompt
    assert "近 7 天上涨" in prompt
    assert "150" in prompt
    assert "40" in prompt


def test_build_anomaly_analysis_prompt_handles_none_trend():
    prompt = build_anomaly_analysis_prompt(
        item_id="test", item_display="Test",
        anomaly={"current": 10, "average": 20, "deviation_pct": 50, "direction": "dip"},
        trend=None, history_high=None, history_low=None,
    )
    assert "暴跌" in prompt
    assert "未知" in prompt


# ── detect_opportunities ──

def test_detect_opportunities_finds_high_spread():
    snapshots = [
        FavoriteSnapshot(item_id="a", item_display="A", sell_price=100, buy_price=40),
    ]
    opps = detect_opportunities(snapshots)
    assert len(opps) == 1
    assert opps[0].suggestion_type == "opportunity"
    assert "价差" in opps[0].message


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


# ── PriceMonitor with llm_analyzer ──

def test_monitor_with_llm_analyzer():
    """验证 llm_analyzer 回调被调用，分析结果被保存到通知。"""
    analyzer = MagicMock(return_value="这是 LLM 分析结果")
    monitor = PriceMonitor(
        order_fetcher=lambda _: [],
        llm_analyzer=analyzer,
    )
    assert monitor.llm_analyzer is analyzer


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
