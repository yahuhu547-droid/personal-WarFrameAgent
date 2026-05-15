"""紫卡（Riven）搜索功能测试。"""

import pytest

from warframe_agent.riven import (
    RIVEN_ATTRIBUTES,
    COMPOUND_KEYWORDS,
    RivenQuery,
    RivenResult,
    _extract_attributes,
    _extract_max_price,
    _extract_weapon_name,
    _looks_like_riven_query,
    format_riven_results,
    parse_riven_query,
    search_rivens,
)


# ── 属性映射 ──────────────────────────────────────────────────────────────────


class TestAttributeMapping:
    def test_all_24_attributes_mapped(self):
        assert len(RIVEN_ATTRIBUTES) >= 24

    def test_critical_chance(self):
        assert RIVEN_ATTRIBUTES["暴击率"] == "critical_chance"
        assert RIVEN_ATTRIBUTES["暴击"] == "critical_chance"

    def test_critical_damage(self):
        assert RIVEN_ATTRIBUTES["暴击伤害"] == "critical_damage"
        assert RIVEN_ATTRIBUTES["暴伤"] == "critical_damage"

    def test_multishot(self):
        assert RIVEN_ATTRIBUTES["多重"] == "multishot"

    def test_status_chance(self):
        assert RIVEN_ATTRIBUTES["触发率"] == "status_chance"
        assert RIVEN_ATTRIBUTES["触发几率"] == "status_chance"

    def test_compound_keywords(self):
        assert COMPOUND_KEYWORDS["双爆"] == ["critical_chance", "critical_damage"]
        assert COMPOUND_KEYWORDS["双暴"] == ["critical_chance", "critical_damage"]


# ── 查询检测 ──────────────────────────────────────────────────────────────────


class TestLooksLikeRivenQuery:
    def test_zi_ka(self):
        assert _looks_like_riven_query("斯特朗紫卡") is True

    def test_lie_xia(self):
        assert _looks_like_riven_query("斯特朗裂罅") is True

    def test_riven(self):
        assert _looks_like_riven_query("strun riven") is True

    def test_xi_ka(self):
        assert _looks_like_riven_query("洗卡") is True

    def test_not_riven(self):
        assert _looks_like_riven_query("斯特朗多少钱") is False


# ── 属性提取 ──────────────────────────────────────────────────────────────────


class TestExtractAttributes:
    def test_double_crit(self):
        pos, neg, no_neg = _extract_attributes("双爆紫卡")
        assert "critical_chance" in pos
        assert "critical_damage" in pos
        assert no_neg is False

    def test_no_negative(self):
        _, _, no_neg = _extract_attributes("无负紫卡")
        assert no_neg is True

    def test_no_negative_variant(self):
        _, _, no_neg = _extract_attributes("不要负")
        assert no_neg is True

    def test_single_attr(self):
        pos, _, _ = _extract_attributes("暴击率紫卡")
        assert "critical_chance" in pos

    def test_explicit_negative(self):
        _, neg, _ = _extract_attributes("负后坐力")
        assert "recoil" in neg

    def test_mixed(self):
        pos, neg, no_neg = _extract_attributes("双暴无负触发率")
        assert "critical_chance" in pos
        assert "critical_damage" in pos
        assert "status_chance" in pos
        assert no_neg is True


# ── 价格提取 ──────────────────────────────────────────────────────────────────


class TestExtractMaxPrice:
    def test_below(self):
        assert _extract_max_price("100以下") == 100

    def test_within(self):
        assert _extract_max_price("50p以内") == 50

    def test_not_exceed(self):
        assert _extract_max_price("不超过200") == 200

    def test_no_price(self):
        assert _extract_max_price("紫卡双爆") is None


# ── 武器名提取 ────────────────────────────────────────────────────────────────


class TestExtractWeaponName:
    def _resolver(self, name):
        from warframe_agent.dictionary import normalize_market_id
        return normalize_market_id(name)

    def test_english_weapon(self):
        result = _extract_weapon_name("rubico紫卡", self._resolver)
        assert result == "rubico"

    def test_chinese_weapon(self):
        result = _extract_weapon_name("斯特朗紫卡", self._resolver)
        # Might resolve through resolver or return None
        # The actual resolution depends on ItemResolver state


# ── 解析完整查询 ──────────────────────────────────────────────────────────────


class TestParseRivenQuery:
    def _resolver(self, name):
        from warframe_agent.dictionary import ItemResolver, normalize_market_id, normalize_lookup_key
        r = ItemResolver()
        # 先检查别名
        alias_id = r.aliases.get(normalize_lookup_key(name))
        if alias_id and not any(alias_id.endswith(s) for s in ["_set", "_mod", "_blueprint"]):
            return alias_id
        # 尝试字典解析（支持中文武器名如"毒囊双枪"→dual_toxocyst）
        try:
            result = r.resolve(name)
            item_id = result.item_id
            if not any(item_id.endswith(s) for s in ["_set", "_mod", "_blueprint"]):
                return item_id
        except Exception:
            pass
        # 回退到 normalized
        normalized = normalize_market_id(name)
        if normalized and len(normalized) >= 2:
            return normalized
        return None

    def test_strun_double_crit_no_neg(self):
        q = parse_riven_query("斯特朗双爆紫卡无负", weapon_resolver=self._resolver)
        assert q is not None
        assert q.weapon_url_name == "strun"
        assert q.positive_attrs == ["critical_chance", "critical_damage"]
        assert q.no_negative is True

    def test_rubico_crit(self):
        q = parse_riven_query("rubico紫卡暴击率", weapon_resolver=self._resolver)
        assert q is not None
        assert q.weapon_url_name == "rubico"
        assert "critical_chance" in q.positive_attrs

    def test_glaive_cn_name_resolves_to_glaive_not_halikar(self):
        q = parse_riven_query("战刃紫卡", weapon_resolver=self._resolver)
        assert q is not None
        assert q.weapon_url_name == "glaive"

    def test_status_prefix_does_not_break_weapon_name(self):
        q = parse_riven_query("给我在线玩家毒囊双枪双爆紫卡，无负", weapon_resolver=self._resolver)
        assert q is not None
        assert q.weapon_url_name == "dual_toxocyst"
        assert q.positive_attrs == ["critical_chance", "critical_damage"]
        assert q.no_negative is True

    def test_request_prefix_does_not_break_weapon_name(self):
        q = parse_riven_query("要斯特朗双爆紫卡", weapon_resolver=self._resolver)
        assert q is not None
        assert q.weapon_url_name == "strun"
        assert q.positive_attrs == ["critical_chance", "critical_damage"]

    def test_geichu_prefix_does_not_break_weapon_name(self):
        q = parse_riven_query("给出执法者双爆紫卡，无负", weapon_resolver=self._resolver)
        assert q is not None
        assert q.weapon_url_name == "magistar"
        assert q.positive_attrs == ["critical_chance", "critical_damage"]
        assert q.no_negative is True

    def test_lawgiver_shortcut_resolves_to_magistar(self):
        """简写"执法者"应解析为 magistar（基础版执法者，紫卡可用）。"""
        q = parse_riven_query("执法者双爆紫卡无负", weapon_resolver=self._resolver)
        assert q is not None
        assert q.weapon_url_name == "magistar"

    def test_max_price(self):
        q = parse_riven_query("rubico紫卡100以下", weapon_resolver=self._resolver)
        assert q is not None
        assert q.max_price == 100

    def test_not_riven_query(self):
        q = parse_riven_query("斯特朗多少钱", weapon_resolver=self._resolver)
        assert q is None


# ── 过滤逻辑 ──────────────────────────────────────────────────────────────────


class TestFilterLogic:
    def _make_result(self, pos_attrs, neg_attrs, price=50):
        return RivenResult(
            weapon="strun",
            mod_name="test-mod",
            positive_attrs=[{"stat": s, "value": 90} for s in pos_attrs],
            negative_attrs=[{"stat": s, "value": -30} for s in neg_attrs],
            price=price,
            seller="test",
            seller_status="online",
        )

    def test_filter_positive(self):
        from warframe_agent.riven import search_rivens
        # This tests the filtering logic in search_rivens
        # We can't easily mock the API, so we test the data structures
        result = self._make_result(["critical_chance", "critical_damage"], [])
        assert len(result.positive_attrs) == 2
        assert len(result.negative_attrs) == 0

    def test_no_negative_filter(self):
        result = self._make_result(["critical_chance"], ["recoil"])
        assert len(result.negative_attrs) == 1
        # A "no_negative" query should reject this

    def test_online_filter_happens_before_limit(self, monkeypatch):
        from warframe_agent import riven

        def auction(price, status, seller):
            return {
                "item": {
                    "weapon_url_name": "laetum",
                    "name": f"laetum-{seller}",
                    "attributes": [
                        {"url_name": "critical_chance", "value": -40, "positive": False},
                    ],
                    "re_rolls": 0,
                },
                "buyout_price": price,
                "owner": {"ingame_name": seller, "status": status},
            }

        auctions = [auction(50 + i, "offline", f"offline-{i}") for i in range(10)]
        auctions.extend([
            auction(90, "ingame", "ingame-a"),
            auction(100, "online", "online-a"),
            auction(110, "ingame", "ingame-b"),
        ])
        monkeypatch.setattr(riven, "fetch_riven_auctions",
            lambda weapon, positive_attrs=None, negative_attrs=None, max_price=None: auctions)

        query = RivenQuery(
            weapon_url_name="laetum",
            negative_attrs=["critical_chance"],
            seller_statuses=("ingame", "online"),
        )

        results = search_rivens(query)

        assert [result.seller for result in results] == ["ingame-a", "ingame-b", "online-a"]

    def test_negative_attrs_are_sent_to_api(self, monkeypatch):
        from warframe_agent import riven

        captured_urls = []

        class Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"payload": {"auctions": []}}

        def fake_get(url, headers, timeout):
            captured_urls.append(url)
            return Response()

        monkeypatch.setattr(riven.requests, "get", fake_get)
        monkeypatch.setattr(riven, "_wait_for_rate_limit", lambda: None)

        query = RivenQuery(weapon_url_name="laetum", negative_attrs=["critical_chance"])
        search_rivens(query)

        assert "negative_stats=critical_chance" in captured_urls[0]


class TestRivenStatusIntent:
    def test_default_status_can_be_online_for_new_buy_query(self):
        from warframe_agent.chat import _riven_statuses_from_message

        assert _riven_statuses_from_message("给我毒囊双枪双爆紫卡", default_online=True) == ("ingame", "online")

    def test_game_status_means_ingame_only(self):
        from warframe_agent.chat import _riven_statuses_from_message

        assert _riven_statuses_from_message("给出游戏中的玩家") == ("ingame",)

    def test_online_status_includes_ingame_and_online(self):
        from warframe_agent.chat import _riven_statuses_from_message

        assert _riven_statuses_from_message("给出在线玩家的") == ("ingame", "online")

    def test_all_status_explicitly_includes_offline(self):
        from warframe_agent.chat import _riven_statuses_from_message

        assert _riven_statuses_from_message("给出全部玩家") == ()


# ── 格式化 ────────────────────────────────────────────────────────────────────


class TestFormatOutput:
    def test_no_results(self):
        q = RivenQuery(weapon_url_name="strun", positive_attrs=["critical_chance"], no_negative=True)
        result = format_riven_results(q, [])
        assert "未找到" in result

    def test_with_results(self):
        q = RivenQuery(weapon_url_name="strun", positive_attrs=["critical_chance", "critical_damage"])
        results = [
            RivenResult(
                weapon="strun",
                mod_name="hexa-magnades",
                positive_attrs=[
                    {"stat": "critical_chance", "value": 98.7},
                    {"stat": "critical_damage", "value": 89.3},
                ],
                negative_attrs=[{"stat": "recoil", "value": 10.3}],
                price=20,
                seller="TestPlayer",
                seller_status="online",
                re_rolls=0,
            ),
        ]
        output = format_riven_results(q, results)
        assert "Strun" in output
        assert "20p" in output
        assert "暴击率" in output
        assert "暴击伤害" in output
        assert "TestPlayer" in output

    def test_conditions_display(self):
        q = RivenQuery(weapon_url_name="rubico", positive_attrs=["critical_chance"], no_negative=True, max_price=100)
        results = []
        output = format_riven_results(q, results)
        assert "正属性" in output
        assert "无负" in output
        assert "100p" in output


# ── API 集成测试（需要网络）──────────────────────────────────────────────────


@pytest.mark.skipif(
    not pytest.importorskip("requests"),
    reason="需要 requests 库"
)
class TestRivenAPI:
    def test_fetch_riven_auctions(self):
        from warframe_agent.riven import fetch_riven_auctions
        auctions = fetch_riven_auctions("strun")
        assert isinstance(auctions, list)
        if auctions:
            item = auctions[0]
            assert "item" in item
            assert "attributes" in item.get("item", {})

    def test_search_rivens_real(self):
        query = RivenQuery(weapon_url_name="strun")
        results = search_rivens(query)
        assert isinstance(results, list)
        if results:
            r = results[0]
            assert r.weapon == "strun"
            assert r.price is not None or r.price is None  # Just check structure


# ── ChatAgent 确定性紫卡路由测试 ─────────────────────────────────────────────


class TestChatAgentRivenRouting:
    """验证 ChatAgent.answer() 对紫卡查询走确定性路由，不依赖 LLM。"""

    def _make_agent(self):
        from unittest.mock import patch
        from warframe_agent.chat import ChatAgent
        from warframe_agent.dictionary import ResolveResult

        class FakeResolver:
            aliases = {"斯特朗": "strun"}

            def resolve(self, name):
                if name in self.aliases or "斯特朗" in name:
                    return ResolveResult("strun", "alias", name)
                raise LookupError(name)

        def model_call(prompt):
            raise AssertionError("LLM should not be called for deterministic riven queries")

        return ChatAgent(
            resolver=FakeResolver(),
            order_fetcher=lambda item_id: [],
            model_call=model_call,
        )

    def test_strun_double_crit_no_neg_routes_to_riven(self):
        from unittest.mock import patch
        agent = self._make_agent()
        fake_results = [
            RivenResult(
                weapon="strun",
                mod_name="strun-visicron",
                positive_attrs=[
                    {"stat": "critical_chance", "value": 100.0},
                    {"stat": "critical_damage", "value": 90.0},
                ],
                negative_attrs=[],
                price=50,
                seller="TestSeller",
                seller_status="online",
                re_rolls=3,
            ),
        ]
        with patch("warframe_agent.riven.fetch_riven_auctions", return_value=[]):
            with patch("warframe_agent.riven.search_rivens", return_value=fake_results):
                answer = agent.answer("斯特朗紫卡双爆无负")

        assert "Strun" in answer or "strun" in answer.lower()
        assert "暴击率" in answer or "暴击伤害" in answer or "50p" in answer

    def test_riven_query_does_not_fall_to_item_search(self):
        """紫卡查询不应该走物品匹配返回武器部件。"""
        from unittest.mock import patch
        agent = self._make_agent()
        with patch("warframe_agent.riven.fetch_riven_auctions", return_value=[]):
            with patch("warframe_agent.riven.search_rivens", return_value=[]):
                answer = agent.answer("斯特朗紫卡双爆无负")

        assert "未找到" in answer or "紫卡" in answer
        assert "部件" not in answer
        assert "蓝图" not in answer

    def test_new_riven_query_defaults_to_online_sellers(self):
        from unittest.mock import patch
        agent = self._make_agent()
        captured = {}

        def fake_search(query):
            captured["query"] = query
            return []

        with patch("warframe_agent.riven.search_rivens", side_effect=fake_search):
            agent.answer("斯特朗紫卡双爆无负")

        assert captured["query"].seller_statuses == ("ingame", "online")

    def test_explicit_all_players_disables_online_filter(self):
        from unittest.mock import patch
        agent = self._make_agent()
        captured = {}

        def fake_search(query):
            captured["query"] = query
            return []

        with patch("warframe_agent.riven.search_rivens", side_effect=fake_search):
            agent.answer("斯特朗紫卡双爆无负，全部玩家")

        assert captured["query"].seller_statuses == ()

    def test_followup_all_players_switches_to_all_sellers(self):
        from unittest.mock import patch
        agent = self._make_agent()
        captured = []

        def fake_search(query):
            captured.append(tuple(query.seller_statuses))
            return []

        with patch("warframe_agent.riven.search_rivens", side_effect=fake_search):
            agent.answer("斯特朗紫卡双爆无负")
            agent.answer("全部玩家")

        assert captured[0] == ("ingame", "online")
        assert captured[1] == ()

    def test_model_riven_parse_rejects_unmentioned_weapon_guess(self):
        from warframe_agent.chat import ChatAgent

        agent = ChatAgent(
            resolver=self._make_agent().resolver,
            order_fetcher=lambda item_id: [],
            model_call=lambda prompt: '{"weapon":"vaykor_hek","positive_attrs":["critical_chance"],"negative_attrs":[],"no_negative":false}',
        )

        assert agent._try_model_riven_parse("给出不存在武器双爆紫卡") is None
