"""飞书机器人模块测试。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from warframe_agent.feishu import FeishuBot, FeishuConfig


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
