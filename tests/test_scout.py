"""多模型预筛选模块测试。"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from warframe_agent import config
from warframe_agent.scout import (
    _build_mod_summary,
    _build_set_summary,
    _parse_json_list,
    _get_cached,
    _set_cache,
    _scout_cache,
    scout_mod_candidates,
    scout_set_candidates,
    scout_investment_candidates,
    clear_scout_cache,
)


# ── _parse_json_list ──────────────────────────────────────────────────────


class TestParseJsonList:
    def test_pure_json_array(self):
        assert _parse_json_list('["a", "b", "c"]') == ["a", "b", "c"]

    def test_json_with_surrounding_text(self):
        text = 'Here are the results: ["arcane_energize", "primed_flow"] end.'
        assert _parse_json_list(text) == ["arcane_energize", "primed_flow"]

    def test_empty_string(self):
        assert _parse_json_list("") == []

    def test_no_array_found(self):
        assert _parse_json_list("no json here") == []

    def test_invalid_json(self):
        assert _parse_json_list("[invalid json]") == []

    def test_non_list_json(self):
        assert _parse_json_list('{"key": "value"}') == []

    def test_mixed_types_in_array(self):
        # None/空值被过滤，非字符串转为 str
        result = _parse_json_list('["a", 1, null, "b"]')
        assert result == ["a", "1", "b"]

    def test_nested_arrays(self):
        # 嵌套数组会被 str() 转换（LLM 不会返回嵌套结构）
        result = _parse_json_list('[["nested"], "flat"]')
        assert result == ["['nested']", "flat"]


# ── _build_mod_summary ────────────────────────────────────────────────────


class TestBuildModSummary:
    def test_basic_mods(self):
        mods = [
            {"url_name": "arcane_energize", "max_rank": 5, "rarity": "rare", "is_prime": False},
            {"url_name": "primed_flow", "max_rank": 10, "rarity": "legendary", "is_prime": True},
        ]
        summary = _build_mod_summary(mods)
        assert "arcane_energize" in summary
        assert "primed_flow" in summary
        assert "[Prime]" in summary
        assert "R5" in summary
        assert "R10" in summary

    def test_with_cached_stats(self):
        mods = [{"url_name": "test_mod", "max_rank": 5, "rarity": "common", "is_prime": False}]
        cached = {"test_mod": {"volume_48h": 42}}
        summary = _build_mod_summary(mods, cached)
        assert "48h成交量=42" in summary


# ── _build_set_summary ────────────────────────────────────────────────────


class TestBuildSetSummary:
    def test_basic_groups(self):
        g1 = MagicMock()
        g1.base_id = "rhino_prime"
        g1.en_title = "Rhino Prime"
        g1.items = {"set": "s1", "blueprint": "b1", "chassis": "c1"}
        g1.tags = ["warframe"]

        summary = _build_set_summary([g1])
        assert "rhino_prime" in summary
        assert "Rhino Prime" in summary
        assert "2部件" in summary
        assert "warframe" in summary


# ── 缓存 ──────────────────────────────────────────────────────────────────


class TestScoutCache:
    def setup_method(self):
        clear_scout_cache()

    def test_cache_miss(self):
        assert _get_cached("nonexistent") is None

    def test_cache_hit(self):
        _set_cache("test_key", ["a", "b"])
        assert _get_cached("test_key") == ["a", "b"]

    def test_cache_expiry(self):
        _scout_cache["expired"] = (time.time() - 9999, ["old"])
        assert _get_cached("expired") is None
        assert "expired" not in _scout_cache

    def test_clear_cache(self):
        _set_cache("k1", ["v1"])
        _set_cache("k2", ["v2"])
        clear_scout_cache()
        assert _get_cached("k1") is None
        assert _get_cache_size() == 0


def _get_cache_size() -> int:
    return len(_scout_cache)


# ── scout_mod_candidates ──────────────────────────────────────────────────


class TestScoutModCandidates:
    def setup_method(self):
        clear_scout_cache()

    @patch("warframe_agent.scout._call_cloud")
    def test_returns_filtered_ids(self, mock_cloud):
        mock_cloud.return_value = '["arcane_energize", "primed_flow"]'
        mods = [
            {"url_name": "arcane_energize", "max_rank": 5, "rarity": "rare", "is_prime": False},
            {"url_name": "primed_flow", "max_rank": 10, "rarity": "legendary", "is_prime": True},
            {"url_name": "other_mod", "max_rank": 5, "rarity": "common", "is_prime": False},
        ]
        result = scout_mod_candidates(mods)
        assert result == ["arcane_energize", "primed_flow"]
        mock_cloud.assert_called_once()

    @patch("warframe_agent.scout._call_cloud")
    def test_filters_invalid_ids(self, mock_cloud):
        mock_cloud.return_value = '["arcane_energize", "nonexistent_mod"]'
        mods = [
            {"url_name": "arcane_energize", "max_rank": 5, "rarity": "rare", "is_prime": False},
        ]
        result = scout_mod_candidates(mods)
        assert result == ["arcane_energize"]

    @patch("warframe_agent.scout._call_cloud")
    def test_returns_empty_on_cloud_failure(self, mock_cloud):
        mock_cloud.return_value = None
        mods = [{"url_name": "test", "max_rank": 5, "rarity": "rare", "is_prime": False}]
        result = scout_mod_candidates(mods)
        assert result == []

    @patch("warframe_agent.scout._call_cloud")
    def test_caches_result(self, mock_cloud):
        mock_cloud.return_value = '["arcane_energize"]'
        mods = [{"url_name": "arcane_energize", "max_rank": 5, "rarity": "rare", "is_prime": False}]

        result1 = scout_mod_candidates(mods)
        result2 = scout_mod_candidates(mods)

        assert result1 == result2
        mock_cloud.assert_called_once()  # 第二次命中缓存


# ── scout_set_candidates ──────────────────────────────────────────────────


class TestScoutSetCandidates:
    def setup_method(self):
        clear_scout_cache()

    @patch("warframe_agent.scout._call_cloud")
    def test_returns_filtered_ids(self, mock_cloud):
        mock_cloud.return_value = '["rhino_prime"]'
        g1 = MagicMock()
        g1.base_id = "rhino_prime"
        g1.en_title = "Rhino Prime"
        g1.items = {"set": "s1", "bp": "b1"}
        g1.tags = ["warframe"]

        result = scout_set_candidates([g1])
        assert result == ["rhino_prime"]

    @patch("warframe_agent.scout._call_cloud")
    def test_empty_on_failure(self, mock_cloud):
        mock_cloud.return_value = "no json here"
        result = scout_set_candidates([MagicMock(base_id="x")])
        assert result == []


# ── scout_investment_candidates ────────────────────────────────────────────


class TestScoutInvestmentCandidates:
    def setup_method(self):
        clear_scout_cache()

    @patch("warframe_agent.scout._call_cloud")
    def test_returns_filtered_ids_with_budget(self, mock_cloud):
        mock_cloud.return_value = '["nova_prime"]'
        g1 = MagicMock()
        g1.base_id = "nova_prime"

        result = scout_investment_candidates([g1], budget=200, event_info="Baro 来访中")
        assert result == ["nova_prime"]
        # 验证 prompt 中包含预算和事件信息
        call_args = mock_cloud.call_args[0][0]
        assert "200" in call_args
        assert "Baro" in call_args

    @patch("warframe_agent.scout._call_cloud")
    def test_uses_correct_model(self, mock_cloud):
        mock_cloud.return_value = '["x"]'
        g1 = MagicMock(base_id="x")

        scout_investment_candidates([g1])
        # 投资顾问应该用 gpt-5.5
        assert mock_cloud.call_args[0][1] == config.SCOUT_MODELS["investment"]
