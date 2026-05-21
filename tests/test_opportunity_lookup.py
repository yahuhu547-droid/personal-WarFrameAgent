from __future__ import annotations

from datetime import datetime, timedelta, timezone

from warframe_agent.opportunity_lookup import (
    OPPORTUNITY_ID_PATTERN,
    OpportunityLookupStore,
    format_opportunity_lookup_reply,
    is_opportunity_lookup_id,
)


def _plan() -> dict:
    return {
        "display_name": "Akbolto Prime",
        "display_strategy": "拆件买入 -> 完整套装订单卖出",
        "strategy": "buy_parts_sell_set",
        "item_id": "akbolto_prime_set",
        "total_cost": 39,
        "total_revenue": 80,
        "profit": 35,
        "roi_pct": 89.7,
        "risk_level": "medium",
        "plan_signature": "sig-akbolto",
        "buy_steps": [
            {
                "label": "Akbolto Prime Blueprint",
                "player": "SellerA",
                "unit_price": 10,
                "quantity": 1,
                "subtotal": 10,
                "market_url": "https://warframe.market/items/akbolto_prime_blueprint",
                "profile_url": "https://warframe.market/profile/SellerA",
                "whisper": "/w SellerA Hi! I want to buy.",
            }
        ],
        "sell_steps": [
            {
                "label": "Akbolto Prime Set",
                "player": "BuyerD",
                "unit_price": 80,
                "quantity": 1,
                "subtotal": 80,
                "market_url": "https://warframe.market/items/akbolto_prime_set",
                "profile_url": "https://warframe.market/profile/BuyerD",
                "whisper": "/w BuyerD Hi! I want to sell.",
            }
        ],
    }


def test_create_and_get_opportunity_detail(tmp_path):
    store = OpportunityLookupStore(tmp_path / "lookup.db")

    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", _plan())
    detail = store.get(lookup_id)

    assert OPPORTUNITY_ID_PATTERN.fullmatch(lookup_id)
    assert detail is not None
    assert detail.lookup_id == lookup_id
    assert detail.item_display == "Akbolto Prime"
    assert detail.content["buy_steps"][0]["player"] == "SellerA"
    assert detail.content["sell_steps"][0]["whisper"].startswith("/w BuyerD")


def test_get_requires_exact_lookup_id(tmp_path):
    store = OpportunityLookupStore(tmp_path / "lookup.db")
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", _plan())

    assert store.get(lookup_id.lower()) is not None
    assert store.get(lookup_id[:4]) is None


def test_expired_record_is_removed(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", _plan(), ttl_hours=1)

    later = datetime(2026, 5, 20, 14, 0, tzinfo=timezone.utc)
    expired_store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: later)

    assert expired_store.get(lookup_id) is None
    assert expired_store.count() == 0


def test_is_opportunity_lookup_id():
    assert is_opportunity_lookup_id("OP8K3A2Q") is True
    assert is_opportunity_lookup_id("op8k3a2q") is True
    assert is_opportunity_lookup_id("AKBOLTO") is False
    assert is_opportunity_lookup_id("OP123") is False


def test_format_reply_includes_links_whispers_and_set_order_note(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", _plan())
    detail = store.get(lookup_id)

    text = format_opportunity_lookup_reply(detail, now=now + timedelta(hours=1))

    assert f"机会 {lookup_id}：Akbolto Prime" in text
    assert "Set 订单不是单独物品" in text
    assert "完整套装订单买家" in text
    assert "https://warframe.market/items/akbolto_prime_blueprint" in text
    assert "https://warframe.market/profile/SellerA" in text
    assert "/w SellerA Hi! I want to buy." in text
    assert "有效期：剩余 47 小时" in text
    assert "请以 warframe.market 实时状态为准" in text


def test_format_reply_for_prime_weapon_set_order_mentions_component_delivery(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    plan = {
        "display_name": "Akbolto Prime",
        "display_strategy": "拆件买入 -> 完整套装订单卖出",
        "strategy": "buy_parts_sell_set",
        "item_id": "akbolto_prime_set",
        "total_cost": 39,
        "total_revenue": 80,
        "profit": 35,
        "roi_pct": 89.7,
        "risk_level": "medium",
        "buy_steps": [
            {"label": "Akbolto Prime Blueprint", "player": "BlueprintSeller", "unit_price": 10, "quantity": 1, "subtotal": 10, "market_url": "https://warframe.market/items/akbolto_prime_blueprint", "profile_url": "https://warframe.market/profile/BlueprintSeller", "whisper": "/w BlueprintSeller Hi! I want to buy."},
            {"label": "Akbolto Prime Link", "player": "LinkSeller", "unit_price": 17, "quantity": 1, "subtotal": 17, "market_url": "https://warframe.market/items/akbolto_prime_link", "profile_url": "https://warframe.market/profile/LinkSeller", "whisper": "/w LinkSeller Hi! I want to buy."},
        ],
        "sell_steps": [
            {"label": "Akbolto Prime Set", "player": "SetBuyer", "unit_price": 80, "quantity": 1, "subtotal": 80, "market_url": "https://warframe.market/items/akbolto_prime_set", "profile_url": "https://warframe.market/profile/SetBuyer", "whisper": "/w SetBuyer Hi! I want to sell."},
        ],
    }
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", plan)

    text = format_opportunity_lookup_reply(store.get(lookup_id), now=now)

    assert "说明：Set 订单不是单独物品，游戏内需交付全部对应部件。" in text
    assert "需要买入的部件：" in text
    assert "完整套装订单买家：" in text
    assert "Akbolto Prime Blueprint" in text
    assert "Akbolto Prime Link" in text


def test_format_reply_title_appends_in_game_chinese_name_for_remaining_opportunity_types(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    cases = [
        ("akbolto_prime_set", "Akbolto Prime", "安柏勒托 Prime", {"strategy": "buy_parts_sell_set"}),
        ("arcane_energize", "Arcane Energize", "充沛赋能", {"source": "arcane_flip", "strategy": "arcane_r0_to_r5"}),
        ("primed_flow", "Primed Flow", "川流不息 Prime", {"source": "mod_flip", "strategy": "mod_r0_to_r10"}),
    ]

    for item_id, english_name, chinese_name, extra in cases:
        store = OpportunityLookupStore(tmp_path / f"{item_id}.db", now=lambda: now)
        plan = {
            "display_name": english_name,
            "item_id": item_id,
            "zh_name": chinese_name,
            "display_strategy": "测试策略",
            "total_cost": 1,
            "total_revenue": 2,
            "profit": 1,
            "roi_pct": 100.0,
            "risk_level": "low",
            "buy_steps": [],
            "sell_steps": [],
            **extra,
        }
        lookup_id = store.create(item_id, english_name, plan)

        text = format_opportunity_lookup_reply(store.get(lookup_id), now=now)

        assert f"机会 {lookup_id}：{english_name}（游戏内：{chinese_name}）" in text


def test_format_reply_for_arcane_flip_shows_quantity_tiers(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    plan = {
        "source": "arcane_flip",
        "display_name": "Arcane Energize",
        "display_strategy": "买 21 个 R0 -> 合成 R5 -> 卖出",
        "strategy": "arcane_r0_to_r5",
        "item_id": "arcane_energize",
        "required_quantity": 21,
        "total_cost": 179,
        "total_revenue": 210,
        "profit": 31,
        "roi_pct": 17.3,
        "risk_level": "medium",
        "buy_steps": [
            {"label": "买入 R0", "player": "SevenPlat", "unit_price": 7, "quantity": 5, "subtotal": 35, "market_url": "https://warframe.market/items/arcane_energize", "profile_url": "https://warframe.market/profile/SevenPlat", "whisper": "/w SevenPlat Hi! I want to buy."},
            {"label": "买入 R0", "player": "NinePlat", "unit_price": 9, "quantity": 16, "subtotal": 144, "market_url": "https://warframe.market/items/arcane_energize", "profile_url": "https://warframe.market/profile/NinePlat", "whisper": "/w NinePlat Hi! I want to buy."},
        ],
        "sell_steps": [
            {"label": "出售 R5", "player": "Rank5Buyer", "unit_price": 210, "quantity": 1, "subtotal": 210, "market_url": "https://warframe.market/items/arcane_energize", "profile_url": "https://warframe.market/profile/Rank5Buyer", "whisper": "/w Rank5Buyer Hi! I want to sell."},
        ],
    }
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("arcane_energize", "Arcane Energize", plan)

    text = format_opportunity_lookup_reply(store.get(lookup_id), now=now)

    assert "赋能满级合成买入：需要 R0 × 21" in text
    assert "SevenPlat — 7p × 5 = 35p" in text
    assert "NinePlat — 9p × 16 = 144p" in text
    assert "满级赋能卖出买家：" in text
    assert "Rank5Buyer" in text
    assert "预计利润：+31p" in text


def test_format_reply_for_mod_flip_does_not_describe_arcane_quantity_synthesis(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    plan = {
        "source": "mod_flip",
        "display_name": "Primed Flow",
        "display_strategy": "买 R0 -> 升到 R10 -> 卖出",
        "strategy": "mod_r0_to_r10",
        "item_id": "primed_flow",
        "required_quantity": 1,
        "total_cost": 40,
        "total_revenue": 120,
        "profit": 80,
        "roi_pct": 200.0,
        "risk_level": "medium",
        "buy_steps": [
            {"label": "买入 R0", "player": "ModSeller", "unit_price": 40, "quantity": 1, "subtotal": 40, "market_url": "https://warframe.market/items/primed_flow", "profile_url": "https://warframe.market/profile/ModSeller", "whisper": "/w ModSeller Hi! I want to buy."},
        ],
        "sell_steps": [
            {"label": "出售 R10", "player": "ModBuyer", "unit_price": 120, "quantity": 1, "subtotal": 120, "market_url": "https://warframe.market/items/primed_flow", "profile_url": "https://warframe.market/profile/ModBuyer", "whisper": "/w ModBuyer Hi! I want to sell."},
        ],
    }
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("primed_flow", "Primed Flow", plan)

    text = format_opportunity_lookup_reply(store.get(lookup_id), now=now)

    assert "MOD 升级买入：" in text
    assert "满级 MOD 卖出买家：" in text
    assert "赋能满级合成买入" not in text
    assert "需要 R0 × 21" not in text
    assert "ModSeller" in text
    assert "ModBuyer" in text
