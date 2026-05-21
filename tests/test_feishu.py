"""飞书机器人模块测试。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from warframe_agent.feishu import FeishuBot, FeishuConfig, build_trade_plan_card_elements, _worker_marker


class TestFeishuConfig:
    def test_default_config(self):
        cfg = FeishuConfig()
        assert cfg.enabled is False
        assert cfg.app_id == ""
        assert cfg.app_secret == ""

    def test_save_and_load(self, tmp_path: Path):
        path = tmp_path / "feishu_config.json"
        cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret123")
        cfg.save(path)

        loaded = FeishuConfig.load(path)
        assert loaded.enabled is True
        assert loaded.app_id == "cli_test"
        assert loaded.app_secret == "secret123"

    def test_load_missing_file(self, tmp_path: Path):
        cfg = FeishuConfig.load(tmp_path / "nonexistent.json")
        assert cfg.enabled is False

    def test_load_corrupt_file(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        cfg = FeishuConfig.load(path)
        assert cfg.enabled is False


class TestFeishuBot:
    def test_available_when_configured(self):
        cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret")
        bot = FeishuBot(cfg)
        assert bot.available is True

    def test_not_available_when_disabled(self):
        cfg = FeishuConfig(enabled=False, app_id="cli_test", app_secret="secret")
        bot = FeishuBot(cfg)
        assert bot.available is False

    def test_not_available_when_no_credentials(self):
        cfg = FeishuConfig(enabled=True, app_id="", app_secret="")
        bot = FeishuBot(cfg)
        assert bot.available is False

    def test_on_message_callback(self):
        cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret")
        callback = MagicMock(return_value="回复")
        bot = FeishuBot(cfg, on_message=callback)
        assert bot.on_message is callback

    def test_stop_without_start(self):
        cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret")
        bot = FeishuBot(cfg)
        bot.stop()  # 不应报错

    @patch("warframe_agent.feishu.ReplyMessageRequest")
    @patch("warframe_agent.feishu.ReplyMessageRequestBody")
    def test_reply_uses_reply_request(self, mock_body_cls, mock_request_cls):
        cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret")
        bot = FeishuBot(cfg)
        client = MagicMock()
        response = MagicMock()
        response.success.return_value = True
        client.im.v1.message.reply.return_value = response
        bot._client = client

        body = MagicMock()
        mock_body_cls.builder.return_value.msg_type.return_value.content.return_value.build.return_value = body
        request = MagicMock()
        mock_request_cls.builder.return_value.message_id.return_value.request_body.return_value.build.return_value = request

        assert bot.reply("om_test", "回复") is True
        mock_request_cls.builder.return_value.message_id.assert_called_once_with("om_test")
        client.im.v1.message.reply.assert_called_once_with(request)

    def test_status_snapshot_is_safe_and_reports_runtime_files(self, tmp_path: Path):
        cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret-value")
        bot = FeishuBot(cfg)
        proc = MagicMock()
        proc.pid = 12345
        proc.poll.return_value = None
        bot._ws_proc = proc
        lock_path = tmp_path / "feishu_worker.lock"
        log_path = tmp_path / "feishu_worker.log"
        lock_path.write_text("12345", encoding="utf-8")
        log_path.write_text("log with secret-value should not be exposed", encoding="utf-8")

        snapshot = bot.status_snapshot(data_dir=tmp_path)

        assert snapshot["enabled"] is True
        assert snapshot["configured"] is True
        assert snapshot["available"] is True
        assert snapshot["managed_pid"] == 12345
        assert snapshot["managed_running"] is True
        assert snapshot["lock_file_exists"] is True
        assert snapshot["lock_pid"] == "12345"
        assert snapshot["log_file_exists"] is True
        assert snapshot["log_size_bytes"] > 0
        assert "secret-value" not in json.dumps(snapshot)
        assert "app_secret" not in snapshot


def test_build_trade_plan_card_elements_contains_actionable_steps():
    elements = build_trade_plan_card_elements({
        "display_strategy": "买部件 -> 卖整套",
        "total_cost": 70,
        "total_revenue": 95,
        "profit": 25,
        "roi_pct": 35.7,
        "risk_level": "medium",
        "buy_steps": [{
            "label": "买入部件：蓝图",
            "player": "PartSellerFS",
            "unit_price": 10,
            "quantity": 1,
            "subtotal": 10,
            "market_url": "https://warframe.market/items/rhino_prime_blueprint",
            "profile_url": "https://warframe.market/profile/PartSellerFS",
            "whisper": "/w PartSellerFS Hi! I want to buy.",
        }],
        "sell_steps": [{
            "label": "出售整套",
            "player": "SetBuyerFS",
            "unit_price": 95,
            "quantity": 1,
            "subtotal": 95,
            "market_url": "https://warframe.market/items/rhino_prime_set",
            "profile_url": "https://warframe.market/profile/SetBuyerFS",
            "whisper": "/w SetBuyerFS Hi! I want to sell.",
        }],
    })
    serialized = json.dumps(elements, ensure_ascii=False)

    assert "策略：买部件 -> 卖整套" in serialized
    assert "成本：70p" in serialized
    assert "利润：+25p" in serialized
    assert "买入部件：蓝图" in serialized
    assert "PartSellerFS：10p × 1 = 10p" in serialized
    assert "SetBuyerFS：95p × 1 = 95p" in serialized
    assert "https://warframe.market/profile/PartSellerFS" in serialized
    assert "/w SetBuyerFS Hi! I want to sell." in serialized


def test_trade_plan_card_includes_opportunity_id_hint():
    elements = build_trade_plan_card_elements({
        "display_name": "Akbolto Prime",
        "display_strategy": "拆件买入 -> 完整套装订单卖出",
        "total_cost": 39,
        "total_revenue": 80,
        "profit": 35,
        "roi_pct": 89.7,
        "risk_level": "medium",
        "buy_steps": [],
        "sell_steps": [],
    }, opportunity_id="OP8K3A2Q")

    text = "\n".join(str(element) for element in elements)
    assert "机会ID：OP8K3A2Q" in text
    assert "在飞书输入 `OP8K3A2Q`" in text


def test_worker_script_converts_data_dir_to_path():
    from warframe_agent.feishu import _FEISHU_WORKER_SCRIPT

    assert 'DATA_DIR = Path(r"{data_dir}")' in _FEISHU_WORKER_SCRIPT


def test_worker_script_has_project_marker():
    from warframe_agent.feishu import _FEISHU_WORKER_SCRIPT

    assert 'WORKER_MARKER = "{marker}"' in _FEISHU_WORKER_SCRIPT


def test_worker_script_uses_single_instance_lock():
    from warframe_agent.feishu import _FEISHU_WORKER_SCRIPT

    assert 'feishu_worker.lock' in _FEISHU_WORKER_SCRIPT
    assert 'LK_NBLCK' in _FEISHU_WORKER_SCRIPT
    assert 'sys.exit(0)' in _FEISHU_WORKER_SCRIPT


def test_worker_cleanup_matches_project_marker():
    cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret")
    bot = FeishuBot(cfg)
    marker = _worker_marker()
    output = (
        f"python -c lark_oapi P2ImMessageReceiveV1 WORKER_MARKER={marker} 12345\n"
        "python -c lark_oapi P2ImMessageReceiveV1 67890\n"
    )

    with patch("warframe_agent.feishu.subprocess.run") as run:
        run.return_value.stdout = output
        bot._kill_old_workers()

    kill_calls = [call for call in run.call_args_list if call.args[0][0] == "taskkill"]
    assert len(kill_calls) == 1
    assert kill_calls[0].args[0][-1] == "12345"


def test_worker_cleanup_ignores_marker_in_inspection_command():
    cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret")
    bot = FeishuBot(cfg)
    marker = _worker_marker()
    output = f"python -c \"marker = '{marker}'\" 12345\n"

    with patch("warframe_agent.feishu.subprocess.run") as run:
        run.return_value.stdout = output
        bot._kill_old_workers()

    kill_calls = [call for call in run.call_args_list if call.args[0][0] == "taskkill"]
    assert kill_calls == []


def test_worker_cleanup_keeps_current_worker_process():
    cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret")
    bot = FeishuBot(cfg)
    marker = _worker_marker()
    bot._ws_proc = MagicMock()
    bot._ws_proc.pid = 12345
    output = f"python -c lark_oapi P2ImMessageReceiveV1 WORKER_MARKER={marker} 12345\n"

    with patch("warframe_agent.feishu.subprocess.run") as run:
        run.return_value.stdout = output
        bot._kill_old_workers()

    kill_calls = [call for call in run.call_args_list if call.args[0][0] == "taskkill"]
    assert kill_calls == []
