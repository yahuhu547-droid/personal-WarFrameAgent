"""WxPusher 推送模块测试。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from warframe_agent.push import (
    WxPusher,
    PushConfig,
    format_buyers_with_whisper,
    format_sellers_with_whisper,
    format_trade_plan_push,
    should_send_daily_report,
)


class TestPushConfig:
    def test_default_config(self):
        cfg = PushConfig()
        assert cfg.enabled is False
        assert cfg.app_token == ""
        assert cfg.uids == []
        assert cfg.push_alerts is True
        assert cfg.push_daily_report is True
        assert cfg.report_time == "09:00"

    def test_save_and_load(self, tmp_path: Path):
        path = tmp_path / "push_config.json"
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=["UID_123"], report_time="10:00")
        cfg.save(path)

        loaded = PushConfig.load(path)
        assert loaded.enabled is True
        assert loaded.app_token == "AT_test"
        assert loaded.uids == ["UID_123"]
        assert loaded.report_time == "10:00"

    def test_load_missing_file(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        cfg = PushConfig.load(path)
        assert cfg.enabled is False
        assert cfg.uids == []

    def test_load_corrupt_file(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        cfg = PushConfig.load(path)
        assert cfg.enabled is False


class TestWxPusher:
    def test_available_when_configured(self):
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=["UID_123"])
        client = WxPusher(cfg)
        assert client.available is True

    def test_not_available_when_disabled(self):
        cfg = PushConfig(enabled=False, app_token="AT_test", uids=["UID_123"])
        client = WxPusher(cfg)
        assert client.available is False

    def test_not_available_when_no_uids(self):
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=[])
        client = WxPusher(cfg)
        assert client.available is False

    def test_not_available_when_no_token(self):
        cfg = PushConfig(enabled=True, app_token="", uids=["UID_123"])
        client = WxPusher(cfg)
        assert client.available is False

    @patch("warframe_agent.push.requests.post")
    def test_send_success(self, mock_post: MagicMock):
        mock_post.return_value.json.return_value = {"code": 1000, "msg": "ok"}
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=["UID_123"])
        client = WxPusher(cfg)

        result = client.send("测试标题", "测试内容", content_type=1)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["appToken"] == "AT_test"
        assert payload["content"] == "测试内容"
        assert payload["summary"] == "测试标题"
        assert payload["contentType"] == 1
        assert payload["uids"] == ["UID_123"]

    @patch("warframe_agent.push.requests.post")
    def test_send_api_error(self, mock_post: MagicMock):
        mock_post.return_value.json.return_value = {"code": 1001, "msg": "error"}
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=["UID_123"])
        client = WxPusher(cfg)

        result = client.send("标题", "内容")
        assert result is False

    @patch("warframe_agent.push.requests.post")
    def test_send_network_error(self, mock_post: MagicMock):
        mock_post.side_effect = Exception("timeout")
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=["UID_123"])
        client = WxPusher(cfg)

        result = client.send("标题", "内容")
        assert result is False

    def test_send_no_uids_returns_false(self):
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=[])
        client = WxPusher(cfg)
        assert client.send("标题", "内容") is False

    @patch("warframe_agent.push.requests.post")
    def test_send_text_uses_content_type_1(self, mock_post: MagicMock):
        mock_post.return_value.json.return_value = {"code": 1000}
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=["UID_123"])
        client = WxPusher(cfg)
        client.send_text("标题", "文本")
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["contentType"] == 1

    @patch("warframe_agent.push.requests.post")
    def test_send_markdown_uses_content_type_3(self, mock_post: MagicMock):
        mock_post.return_value.json.return_value = {"code": 1000}
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=["UID_123"])
        client = WxPusher(cfg)
        client.send_markdown("标题", "# Markdown")
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["contentType"] == 3

    @patch("warframe_agent.push.requests.post")
    def test_summary_truncated_to_100_chars(self, mock_post: MagicMock):
        mock_post.return_value.json.return_value = {"code": 1000}
        cfg = PushConfig(enabled=True, app_token="AT_test", uids=["UID_123"])
        client = WxPusher(cfg)
        long_title = "A" * 200
        client.send_text(long_title, "内容")
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert len(payload["summary"]) <= 100


class TestDailyReportFormatting:
    def test_buyers_whisper_uses_market_name_not_display_label(self):
        text = format_buyers_with_whisper(
            "充沛赋能 / Arcane Energize / arcane_energize",
            "arcane_energize",
            [{"user_name": "Buyer1", "platinum": 30, "mod_rank": None, "status": "ingame"}],
        )

        assert "最高收价" in text
        assert "最高买家价格" not in text
        assert "Rank" not in text
        assert "/w Buyer1 Hi! I want to sell: \"Arcane Energize\" for 30 platinum." in text
        assert "/w Buyer1 Hi! I want to buy:" not in text
        assert "/w Buyer1 Hi! I want to sell: 充沛赋能" not in text
        assert "https://warframe.market/items/arcane_energize" in text
        assert "warframe.market/items/充沛赋能" not in text

    def test_sellers_whisper_uses_market_name_not_display_label(self):
        text = format_sellers_with_whisper(
            "充沛赋能 / Arcane Energize / arcane_energize",
            "arcane_energize",
            [{"user_name": "Seller1", "platinum": 40, "mod_rank": None, "status": "ingame"}],
        )

        assert "最低卖价" in text
        assert "最低卖家价格" not in text
        assert "Rank" not in text
        assert "/w Seller1 Hi! I want to buy: \"Arcane Energize\" for 40 platinum." in text
        assert "/w Seller1 Hi! I want to sell:" not in text
        assert "/w Seller1 Hi! I want to buy: 充沛赋能" not in text
        assert "https://warframe.market/items/arcane_energize" in text
        assert "warframe.market/items/充沛赋能" not in text

    def test_rank_is_shown_only_when_order_has_rank(self):
        text = format_sellers_with_whisper(
            "满级 Mod / primed_flow",
            "primed_flow",
            [{"user_name": "Seller1", "platinum": 100, "mod_rank": 10, "status": "ingame"}],
        )

        assert "Rank 10" in text


class TestTradePlanPushFormatting:
    def test_format_trade_plan_push_contains_actionable_steps(self):
        text = format_trade_plan_push({
            "display_name": "Arcane Energize",
            "display_strategy": "买 21 个 R0 -> 合成 R5 -> 卖出",
            "total_cost": 105,
            "total_revenue": 150,
            "profit": 45,
            "roi_pct": 42.9,
            "risk_level": "medium",
            "buy_steps": [
                {
                    "label": "买入 R0",
                    "player": "SellerPush",
                    "unit_price": 5,
                    "quantity": 21,
                    "subtotal": 105,
                    "market_url": "https://warframe.market/items/arcane_energize",
                    "profile_url": "https://warframe.market/profile/SellerPush",
                    "whisper": "/w SellerPush Hi! I want to buy.",
                }
            ],
            "sell_steps": [
                {
                    "label": "出售 R5",
                    "player": "BuyerPush",
                    "unit_price": 150,
                    "quantity": 1,
                    "subtotal": 150,
                    "market_url": "https://warframe.market/items/arcane_energize",
                    "profile_url": "https://warframe.market/profile/BuyerPush",
                    "whisper": "/w BuyerPush Hi! I want to sell.",
                }
            ],
        })

        assert "## 交易机会：Arcane Energize" in text
        assert "策略：买 21 个 R0 -> 合成 R5 -> 卖出" in text
        assert "成本：105p" in text
        assert "收入：150p" in text
        assert "利润：+45p" in text
        assert "ROI：42.9%" in text
        assert "SellerPush：5p × 21 = 105p" in text
        assert "BuyerPush：150p × 1 = 150p" in text
        assert "https://warframe.market/items/arcane_energize" in text
        assert "https://warframe.market/profile/SellerPush" in text
        assert "`/w SellerPush Hi! I want to buy.`" in text


class TestShouldSendDailyReport:
    def test_returns_false_when_disabled(self):
        cfg = PushConfig(enabled=False)
        assert should_send_daily_report(cfg) is False

    def test_returns_false_when_report_disabled(self):
        cfg = PushConfig(enabled=True, push_daily_report=False)
        assert should_send_daily_report(cfg) is False

    @patch("warframe_agent.push.datetime")
    def test_returns_true_within_window(self, mock_dt: MagicMock):
        mock_dt.now.return_value.time.return_value = datetime.strptime("09:03", "%H:%M").time()
        cfg = PushConfig(enabled=True, push_daily_report=True, report_time="09:00")
        assert should_send_daily_report(cfg) is True

    @patch("warframe_agent.push.datetime")
    def test_returns_false_outside_window(self, mock_dt: MagicMock):
        mock_dt.now.return_value.time.return_value = datetime.strptime("12:00", "%H:%M").time()
        cfg = PushConfig(enabled=True, push_daily_report=True, report_time="09:00")
        assert should_send_daily_report(cfg) is False

    @patch("warframe_agent.push.datetime")
    def test_returns_true_at_window_edge(self, mock_dt: MagicMock):
        mock_dt.now.return_value.time.return_value = datetime.strptime("09:06", "%H:%M").time()
        cfg = PushConfig(enabled=True, push_daily_report=True, report_time="09:00")
        assert should_send_daily_report(cfg) is True

    @patch("warframe_agent.push.datetime")
    def test_returns_false_beyond_window(self, mock_dt: MagicMock):
        mock_dt.now.return_value.time.return_value = datetime.strptime("09:07", "%H:%M").time()
        cfg = PushConfig(enabled=True, push_daily_report=True, report_time="09:00")
        assert should_send_daily_report(cfg) is False
