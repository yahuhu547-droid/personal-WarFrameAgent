"""飞书机器人模块测试。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from warframe_agent.feishu import FeishuBot, FeishuConfig, _worker_marker


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


def test_worker_script_converts_data_dir_to_path():
    from warframe_agent.feishu import _FEISHU_WORKER_SCRIPT

    assert 'DATA_DIR = Path(r"{data_dir}")' in _FEISHU_WORKER_SCRIPT


def test_worker_script_has_project_marker():
    from warframe_agent.feishu import _FEISHU_WORKER_SCRIPT

    assert 'WORKER_MARKER = "{marker}"' in _FEISHU_WORKER_SCRIPT


def test_worker_cleanup_matches_project_marker():
    cfg = FeishuConfig(enabled=True, app_id="cli_test", app_secret="secret")
    bot = FeishuBot(cfg)
    current = str(bot._ws_proc.pid) if bot._ws_proc else ""
    marker = _worker_marker()
    output = f"python -c worker {marker} 12345\npython -c lark_oapi P2ImMessageReceiveV1 67890\n"

    with patch("warframe_agent.feishu.subprocess.run") as run:
        run.return_value.stdout = output
        bot._kill_old_workers()

    kill_calls = [call for call in run.call_args_list if call.args[0][0] == "taskkill"]
    assert len(kill_calls) == 1
    assert kill_calls[0].args[0][-1] == "12345"
