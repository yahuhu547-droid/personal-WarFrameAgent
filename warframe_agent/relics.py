"""遗物掉落数据库 — 从游戏导出数据构建遗物↔部件索引。"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)

# 内部名称 → 市场名称的已知映射
_NAME_FIXES = {
    "helmet": "neuroptics",
}

# 遗物等级中文映射
TIER_MAP = {
    "Lith": "古纪",
    "Meso": "前纪",
    "Neo": "中纪",
    "Axi": "后纪",
    "Requiem": "遗珍",
}

# 反向映射（中文 → 英文）
_TIER_REVERSE = {v: k for k, v in TIER_MAP.items()}

# 掉落率（Warframe Wiki 标准值）
RARITY_DROP_RATE = {
    "COMMON": 0.2533,
    "UNCOMMON": 0.11,
    "RARE": 0.02,
}


@dataclass(frozen=True)
class RelicDrop:
    """一条遗物掉落记录。"""
    relic_name: str        # 遗物显示名（英文）
    relic_tier: str        # Lith/Meso/Neo/Axi/Requiem
    part_name: str         # 部件显示名（英文）
    market_id: str         # market item_id（可能为空）
    rarity: str            # COMMON/UNCOMMON/RARE
    drop_rate: float       # 掉落率


@dataclass(frozen=True)
class RelicInfo:
    """遗物信息。"""
    name: str              # 遗物显示名
    tier: str              # Lith/Meso/Neo/Axi/Requiem
    is_vaulted: bool       # 是否已 Vault
    drops: list[RelicDrop]


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _build_upgrade_map(export_path: Path) -> dict[str, str]:
    """从 ExportUpgrades 构建 uniqueName → name 映射。"""
    if not export_path.exists():
        return {}
    try:
        data = json.loads(export_path.read_text(encoding="utf-8"))
        upgrades = data.get("ExportUpgrades", [])
        return {u["uniqueName"]: u["name"] for u in upgrades if "uniqueName" in u}
    except Exception as exc:
        logger.warning("加载 ExportUpgrades 失败: %s", exc)
        return {}


def _build_item_map(items: list[dict]) -> dict[str, str]:
    """从 items_full 构建 normalized_name → market_id 映射。"""
    item_map: dict[str, str] = {}
    for item in items:
        en = item.get("en_name", "")
        norm = _normalize(en)
        if norm:
            item_map[norm] = item.get("item_id", "")
    return item_map


def _find_market_id(reward_name: str, item_map: dict[str, str]) -> str:
    """将内部奖励名映射到 market_id。"""
    norm = _normalize(reward_name)
    # 直接匹配
    if norm in item_map:
        return item_map[norm]
    # 尝试加 blueprint
    if norm + "blueprint" in item_map:
        return item_map[norm + "blueprint"]
    # Helmet → Neuroptics 替换
    for old, new in _NAME_FIXES.items():
        if old in norm:
            fixed = norm.replace(old, new)
            if fixed in item_map:
                return item_map[fixed]
            if fixed + "blueprint" in item_map:
                return item_map[fixed + "blueprint"]
    return ""


def _detect_tier(relic_name: str) -> str:
    """从遗物名检测等级。"""
    for tier in ["Lith", "Meso", "Neo", "Axi", "Requiem"]:
        if tier in relic_name:
            return tier
    return ""


class RelicDB:
    """遗物掉落数据库。"""

    def __init__(self) -> None:
        self._relics: dict[str, RelicInfo] = {}        # relic_name → RelicInfo
        self._part_index: dict[str, list[RelicDrop]] = {}  # market_id → [RelicDrop]
        self._name_index: dict[str, list[RelicDrop]] = {}  # part_name_lower → [RelicDrop]
        self._loaded = False

    def load(self, items: list[dict] | None = None) -> None:
        """加载遗物数据并构建索引。"""
        if self._loaded:
            return

        # 加载 ExportUpgrades 映射
        upgrade_map = _build_upgrade_map(config.EXPORT_DIR / "ExportUpgrades_en.json")

        # 加载 items_full 构建 market_id 映射
        if items is None:
            items_path = config.ITEMS_FULL_PATH
            if items_path.exists():
                try:
                    items = json.loads(items_path.read_text(encoding="utf-8-sig"))
                except Exception:
                    items = []
            else:
                items = []
        item_map = _build_item_map(items)

        # 加载遗物数据
        relic_path = config.EXPORT_DIR / "ExportRelicArcane_en.json"
        if not relic_path.exists():
            logger.warning("遗物数据文件不存在: %s", relic_path)
            return

        try:
            data = json.loads(relic_path.read_text(encoding="utf-8"))
            raw_relics = data.get("ExportRelicArcane", [])
        except Exception as exc:
            logger.warning("加载遗物数据失败: %s", exc)
            return

        # 解析每个遗物（去重：同一遗物可能有多条记录代表不同精炼等级）
        seen_relics: set[str] = set()
        for raw in raw_relics:
            relic_name = raw.get("name", "")
            if relic_name in seen_relics:
                continue
            tier = _detect_tier(relic_name)
            if not tier:
                continue
            seen_relics.add(relic_name)

            drops: list[RelicDrop] = []
            for rw in raw.get("relicRewards", []):
                reward_unique = rw.get("rewardName", "")
                rarity = rw.get("rarity", "COMMON")

                # 从 upgrade_map 获取显示名
                part_name = upgrade_map.get(reward_unique, reward_unique.split("/")[-1])
                # 清理内部名
                part_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", part_name)
                part_name = part_name.replace("Prime", " Prime").replace("  ", " ").strip()

                market_id = _find_market_id(part_name, item_map)
                drop_rate = RARITY_DROP_RATE.get(rarity, 0.1)

                drop = RelicDrop(
                    relic_name=relic_name,
                    relic_tier=tier,
                    part_name=part_name,
                    market_id=market_id,
                    rarity=rarity,
                    drop_rate=drop_rate,
                )
                drops.append(drop)

                # 索引
                if market_id:
                    self._part_index.setdefault(market_id, []).append(drop)
                self._name_index.setdefault(part_name.lower(), []).append(drop)

            self._relics[relic_name] = RelicInfo(
                name=relic_name,
                tier=tier,
                is_vaulted=False,  # 默认未 Vault，后续由 events.py 更新
                drops=drops,
            )

        self._loaded = True
        logger.info("遗物数据库加载完成: %d 个遗物, %d 个部件索引", len(self._relics), len(self._part_index))

    def set_vaulted(self, relic_names: set[str]) -> None:
        """标记已 Vault 的遗物。"""
        for name, info in self._relics.items():
            if name in relic_names:
                self._relics[name] = RelicInfo(
                    name=info.name,
                    tier=info.tier,
                    is_vaulted=True,
                    drops=info.drops,
                )

    def find_by_part(self, query: str) -> list[RelicDrop]:
        """按部件名查找掉落遗物。支持 market_id 或模糊匹配。"""
        self.load()
        # 先按 market_id 查
        if query in self._part_index:
            return self._part_index[query]
        # 按部件名模糊匹配（同时尝试 helmet/neuroptics 互换）
        query_lower = query.lower()
        alt_lower = query_lower
        for old, new in _NAME_FIXES.items():
            if old in query_lower:
                alt_lower = query_lower.replace(old, new)
            elif new in query_lower:
                alt_lower = query_lower.replace(new, old)
        results: list[RelicDrop] = []
        seen: set[str] = set()
        for name, drops in self._name_index.items():
            if query_lower in name or alt_lower in name:
                for d in drops:
                    key = (d.relic_name, d.part_name)
                    if key not in seen:
                        seen.add(key)
                        results.append(d)
        return results

    def find_by_relic(self, query: str) -> RelicInfo | None:
        """按遗物名查找。支持中英文和模糊匹配。"""
        self.load()
        # 精确匹配
        if query in self._relics:
            return self._relics[query]
        # 中文等级名 → 英文
        normalized = query
        for cn, en in _TIER_REVERSE.items():
            if cn in normalized:
                normalized = normalized.replace(cn, en)
        if normalized != query and normalized in self._relics:
            return self._relics[normalized]
        # 模糊匹配（同时尝试原始和转换后的查询）
        query_lower = query.lower()
        norm_lower = normalized.lower()
        for name, info in self._relics.items():
            name_lower = name.lower()
            if query_lower in name_lower or norm_lower in name_lower:
                return info
        return None

    def get_all_relics(self, tier: str = "", unvaulted_only: bool = True) -> list[RelicInfo]:
        """获取所有遗物，可按等级过滤。"""
        self.load()
        results = list(self._relics.values())
        if tier:
            results = [r for r in results if r.tier == tier]
        if unvaulted_only:
            results = [r for r in results if not r.is_vaulted]
        return results


# 全局单例
_relic_db: RelicDB | None = None


def get_relic_db() -> RelicDB:
    global _relic_db
    if _relic_db is None:
        _relic_db = RelicDB()
    return _relic_db
