"""relics.py — 遗物掉落数据库测试。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from warframe_agent.relics import (
    RelicDB,
    RelicDrop,
    RelicInfo,
    _build_item_map,
    _build_upgrade_map,
    _detect_tier,
    _find_market_id,
    _normalize,
    get_relic_db,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_relic_data(name: str, rewards: list[dict]) -> dict:
    return {"name": name, "relicRewards": rewards}


def _make_reward(unique: str, rarity: str = "COMMON") -> dict:
    return {"rewardName": unique, "rarity": rarity}


SAMPLE_EXPORT = {
    "ExportRelicArcane": [
        _make_relic_data(
            "Lith T1 Relic",
            [
                _make_reward("/Lotus/Types/Parts/ValkyrPrimeChassis", "COMMON"),
                _make_reward("/Lotus/Types/Parts/NovaPrimeSystems", "UNCOMMON"),
                _make_reward("/Lotus/Types/Parts/WeaponReceiver", "RARE"),
            ],
        ),
        _make_relic_data(
            "Meso V2 Relic",
            [
                _make_reward("/Lotus/Types/Parts/ValkyrPrimeChassis", "COMMON"),
                _make_reward("/Lotus/Types/Parts/Forma", "COMMON"),
            ],
        ),
        # 重复条目（模拟精炼等级不同）
        _make_relic_data(
            "Lith T1 Relic",
            [
                _make_reward("/Lotus/Types/Parts/ValkyrPrimeChassis", "COMMON"),
                _make_reward("/Lotus/Types/Parts/NovaPrimeSystems", "UNCOMMON"),
                _make_reward("/Lotus/Types/Parts/WeaponReceiver", "RARE"),
            ],
        ),
    ]
}

SAMPLE_UPGRADES = {
    "ExportUpgrades": [
        {"uniqueName": "/Lotus/Types/Parts/ValkyrPrimeChassis", "name": "Valkyr Prime Chassis Blueprint"},
        {"uniqueName": "/Lotus/Types/Parts/NovaPrimeSystems", "name": "Nova Prime Systems Blueprint"},
        {"uniqueName": "/Lotus/Types/Parts/WeaponReceiver", "name": "Weapon Receiver"},
        {"uniqueName": "/Lotus/Types/Parts/Forma", "name": "Forma Blueprint"},
    ]
}

SAMPLE_ITEMS = [
    {"item_id": "valkyr_prime_chassis_blueprint", "en_name": "Valkyr Prime Chassis Blueprint"},
    {"item_id": "nova_prime_systems_blueprint", "en_name": "Nova Prime Systems Blueprint"},
    {"item_id": "weapon_receiver", "en_name": "Weapon Receiver"},
]


# ── 单元测试 ─────────────────────────────────────────────────────────────────


class TestNormalize:
    def test_basic(self):
        assert _normalize("Rhino Prime") == "rhinoprime"

    def test_special_chars(self):
        assert _normalize("Boar Prime Stock!") == "boarprimestock"

    def test_empty(self):
        assert _normalize("") == ""


class TestDetectTier:
    def test_lith(self):
        assert _detect_tier("Lith B1 Relic") == "Lith"

    def test_axi(self):
        assert _detect_tier("Axi R1 Relic") == "Axi"

    def test_requiem(self):
        assert _detect_tier("Requiem I Relic") == "Requiem"

    def test_unknown(self):
        assert _detect_tier("Unknown Relic") == ""


class TestBuildItemMap:
    def test_basic(self):
        items = [
            {"item_id": "valkyr_prime_chassis_blueprint", "en_name": "Valkyr Prime Chassis Blueprint"},
            {"item_id": "nova_prime_systems_blueprint", "en_name": "Nova Prime Systems Blueprint"},
        ]
        result = _build_item_map(items)
        assert "valkyrprimechassisblueprint" in result
        assert result["valkyrprimechassisblueprint"] == "valkyr_prime_chassis_blueprint"

    def test_empty(self):
        assert _build_item_map([]) == {}


class TestFindMarketId:
    def test_direct_match(self):
        item_map = {"valkyrprimechassisblueprint": "valkyr_prime_chassis_blueprint"}
        assert _find_market_id("Valkyr Prime Chassis Blueprint", item_map) == "valkyr_prime_chassis_blueprint"

    def test_helmet_to_neuroptics(self):
        item_map = {"rhinoprimeneuropticsblueprint": "rhino_prime_neuroptics_blueprint"}
        assert _find_market_id("Rhino Prime Helmet Blueprint", item_map) == "rhino_prime_neuroptics_blueprint"

    def test_no_match(self):
        assert _find_market_id("Unknown Part", {}) == ""

    def test_blueprint_suffix_fallback(self):
        item_map = {"valkyrprimechassisblueprint": "valkyr_prime_chassis_blueprint"}
        assert _find_market_id("Valkyr Prime Chassis", item_map) == "valkyr_prime_chassis_blueprint"


class TestBuildUpgradeMap:
    def test_basic(self, tmp_path):
        data = {"ExportUpgrades": [{"uniqueName": "/a/b", "name": "Test"}]}
        path = tmp_path / "upgrades.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = _build_upgrade_map(path)
        assert result == {"/a/b": "Test"}

    def test_missing_file(self, tmp_path):
        assert _build_upgrade_map(tmp_path / "missing.json") == {}


# ── 集成测试 ─────────────────────────────────────────────────────────────────


class TestRelicDB:
    @pytest.fixture()
    def db(self, tmp_path):
        """创建使用临时数据的 RelicDB。"""
        export_dir = tmp_path / "export"
        export_dir.mkdir()
        (export_dir / "ExportRelicArcane_en.json").write_text(
            json.dumps(SAMPLE_EXPORT), encoding="utf-8"
        )
        (export_dir / "ExportUpgrades_en.json").write_text(
            json.dumps(SAMPLE_UPGRADES), encoding="utf-8"
        )
        items_path = tmp_path / "items_full.json"
        items_path.write_text(json.dumps(SAMPLE_ITEMS), encoding="utf-8-sig")

        with (
            patch("warframe_agent.relics.config.EXPORT_DIR", export_dir),
            patch("warframe_agent.relics.config.ITEMS_FULL_PATH", items_path),
        ):
            db = RelicDB()
            db.load(items=SAMPLE_ITEMS)
            return db

    def test_deduplication(self, db):
        """同一遗物不应重复索引。"""
        # Lith T1 在原始数据中出现 2 次，但应只索引 1 次
        assert "Lith T1 Relic" in db._relics
        info = db._relics["Lith T1 Relic"]
        assert len(info.drops) == 3  # 3 个不同部件，不是 6 个

    def test_find_by_part_market_id(self, db):
        """通过 market_id 查找。"""
        drops = db.find_by_part("valkyr_prime_chassis_blueprint")
        assert len(drops) == 2  # Lith T1 + Meso V2
        relic_names = {d.relic_name for d in drops}
        assert "Lith T1 Relic" in relic_names
        assert "Meso V2 Relic" in relic_names

    def test_find_by_part_fuzzy(self, db):
        """模糊匹配部件名。"""
        drops = db.find_by_part("valkyr prime chassis")
        assert len(drops) >= 1

    def test_find_by_relic_exact(self, db):
        """精确匹配遗物名。"""
        info = db.find_by_relic("Lith T1 Relic")
        assert info is not None
        assert info.name == "Lith T1 Relic"
        assert info.tier == "Lith"
        assert len(info.drops) == 3

    def test_find_by_relic_fuzzy(self, db):
        """模糊匹配遗物名。"""
        info = db.find_by_relic("Lith T1")
        assert info is not None
        assert info.name == "Lith T1 Relic"

    def test_find_by_relic_not_found(self, db):
        assert db.find_by_relic("Nonexistent Relic") is None

    def test_set_vaulted(self, db):
        """标记 Vault 遗物。"""
        db.set_vaulted({"Lith T1 Relic"})
        info = db.find_by_relic("Lith T1 Relic")
        assert info.is_vaulted is True

    def test_get_all_relics(self, db):
        """获取所有遗物。"""
        all_relics = db.get_all_relics()
        assert len(all_relics) == 2  # Lith T1 + Meso V2 (去重后)

    def test_get_all_relics_filter_tier(self, db):
        """按等级过滤。"""
        lith_only = db.get_all_relics(tier="Lith")
        assert len(lith_only) == 1
        assert lith_only[0].name == "Lith T1 Relic"

    def test_get_all_relics_vaulted_filter(self, db):
        """过滤已 Vault 遗物。"""
        db.set_vaulted({"Lith T1 Relic"})
        unvaulted = db.get_all_relics(unvaulted_only=True)
        assert len(unvaulted) == 1
        assert unvaulted[0].name == "Meso V2 Relic"

    def test_drop_rates(self, db):
        """验证掉落率。"""
        info = db.find_by_relic("Lith T1 Relic")
        drops_by_rarity = {d.rarity: d.drop_rate for d in info.drops}
        assert drops_by_rarity["COMMON"] == pytest.approx(0.2533)
        assert drops_by_rarity["UNCOMMON"] == pytest.approx(0.11)
        assert drops_by_rarity["RARE"] == pytest.approx(0.02)

    def test_load_idempotent(self, db):
        """多次调用 load 不应重复加载。"""
        db.load()
        db.load()
        assert len(db._relics) == 2


class TestRelicDBSingleton:
    def test_get_relic_db(self):
        """get_relic_db 返回单例。"""
        # 清除全局单例
        import warframe_agent.relics as m
        old = m._relic_db
        m._relic_db = None
        try:
            db1 = get_relic_db()
            db2 = get_relic_db()
            assert db1 is db2
        finally:
            m._relic_db = old


class TestRelicDropDataclass:
    def test_frozen(self):
        drop = RelicDrop("Lith B1", "Lith", "Part", "part_id", "COMMON", 0.25)
        with pytest.raises(AttributeError):
            drop.relic_name = "changed"

    def test_equality(self):
        d1 = RelicDrop("Lith B1", "Lith", "Part", "pid", "COMMON", 0.25)
        d2 = RelicDrop("Lith B1", "Lith", "Part", "pid", "COMMON", 0.25)
        assert d1 == d2
