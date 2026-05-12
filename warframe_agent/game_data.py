"""游戏数据查询模块 — 从 Export 数据中查询 Mod 效果、战甲技能、遗物信息。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)


class GameDataStore:
    """懒加载的游戏数据查询器，用于注入 LLM 上下文。"""

    def __init__(self):
        self._mods: dict[str, dict] = {}       # key -> {name, description, levelStats, rarity}
        self._arcanes: dict[str, dict] = {}     # key -> {name, levelStats, rarity}
        self._warframes: dict[str, dict] = {}   # key -> {name, description, abilities}
        self._ducat_values: dict[str, int] = {}
        self._vault_status: dict[str, dict] = {}
        self._relic_sources: dict[str, list] = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._load_mods()
        self._load_arcanes()
        self._load_warframes()
        self._load_ducats()
        self._load_vault_status()
        self._load_relic_sources()
        self._loaded = True

    def _load_mods(self):
        path = config.EXPORT_DIR / "ExportUpgrades_zh.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            for item in data.get("ExportUpgrades", []):
                name = item.get("name", "")
                if not name:
                    continue
                key = name.lower().replace(" ", "")
                self._mods[key] = {
                    "name": name,
                    "description": item.get("description", []),
                    "levelStats": item.get("levelStats", []),
                    "rarity": item.get("rarity", ""),
                    "compatName": item.get("compatName", ""),
                    "type": item.get("type", ""),
                    "tags": item.get("tags", []),
                }
        except Exception as exc:
            logger.debug("加载 Mod 数据失败: %s", exc)

    def _load_arcanes(self):
        path = config.EXPORT_DIR / "ExportRelicArcane_zh.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            for item in data.get("ExportRelicArcane", []):
                name = item.get("name", "")
                if not name:
                    continue
                key = name.lower().replace(" ", "").replace("·", "")
                self._arcanes[key] = {
                    "name": name,
                    "levelStats": item.get("levelStats", []),
                    "rarity": item.get("rarity", ""),
                    "tags": item.get("tags", []),
                }
        except Exception as exc:
            logger.debug("加载 Arcane 数据失败: %s", exc)

    def _load_warframes(self):
        path = config.EXPORT_DIR / "ExportWarframes_zh.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            for item in data.get("ExportWarframes", []):
                name = item.get("name", "")
                if not name:
                    continue
                key = name.lower().replace(" ", "").replace("<archwing>", "")
                self._warframes[key] = {
                    "name": name,
                    "description": item.get("description", ""),
                    "abilities": item.get("abilities", []),
                    "health": item.get("health"),
                    "shield": item.get("shield"),
                    "armor": item.get("armor"),
                }
        except Exception as exc:
            logger.debug("加载战甲数据失败: %s", exc)

    def _load_ducats(self):
        path = config.DATA_DIR / "ducat_values.json"
        if path.exists():
            try:
                self._ducat_values = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                logger.debug("加载杜卡特数据失败: %s", exc)

    def _load_vault_status(self):
        path = config.DATA_DIR / "relic_vault_status.json"
        if path.exists():
            try:
                self._vault_status = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                logger.debug("加载封存数据失败: %s", exc)

    def _load_relic_sources(self):
        path = config.DATA_DIR / "relic_sources.json"
        if path.exists():
            try:
                self._relic_sources = json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                logger.debug("加载遗物来源失败: %s", exc)

    def get_mod_info(self, name: str) -> str | None:
        """返回 Mod/Arcane 的效果描述，用于注入 LLM 上下文。"""
        self._ensure_loaded()
        key = name.lower().replace(" ", "")

        # 先查 Mod
        mod = self._mods.get(key)
        if mod:
            return self._format_mod(mod)

        # 再查 Arcane
        key_no_dot = key.replace("·", "")
        arcane = self._arcanes.get(key_no_dot) or self._arcanes.get(key)
        if arcane:
            return self._format_arcane(arcane)

        return None

    def _format_mod(self, mod: dict) -> str:
        lines = [f"Mod: {mod['name']}"]
        desc = mod.get("description", [])
        if desc:
            lines.append(f"效果: {desc[0] if isinstance(desc, list) else desc}")
        level_stats = mod.get("levelStats", [])
        if level_stats:
            max_stats = level_stats[-1].get("stats", [])
            if max_stats:
                lines.append(f"满级: {', '.join(max_stats)}")
        if mod.get("rarity"):
            lines.append(f"稀有度: {mod['rarity']}")
        if mod.get("compatName"):
            lines.append(f"适用: {mod['compatName']}")
        return "\n".join(lines)

    def _format_arcane(self, arcane: dict) -> str:
        lines = [f"赋能: {arcane['name']}"]
        level_stats = arcane.get("levelStats", [])
        if level_stats:
            max_stats = level_stats[-1].get("stats", [])
            if max_stats:
                lines.append(f"满级效果: {max_stats[0]}")
        if arcane.get("rarity"):
            lines.append(f"稀有度: {arcane['rarity']}")
        return "\n".join(lines)

    def get_warframe_info(self, name: str) -> str | None:
        """返回战甲技能描述。"""
        self._ensure_loaded()
        key = name.lower().replace(" ", "")
        wf = self._warframes.get(key)
        if not wf:
            return None
        lines = [f"战甲: {wf['name']}"]
        if wf.get("description"):
            lines.append(f"简介: {wf['description']}")
        for ability in wf.get("abilities", [])[:4]:
            aname = ability.get("abilityName", "")
            adesc = ability.get("description", "")
            if aname:
                lines.append(f"技能「{aname}」: {adesc}")
        return "\n".join(lines)

    def get_ducat_value(self, item_id: str) -> int | None:
        self._ensure_loaded()
        return self._ducat_values.get(item_id)

    def is_vaulted(self, relic_name: str) -> bool | None:
        self._ensure_loaded()
        status = self._vault_status.get(relic_name)
        if status:
            return status.get("vaulted")
        return None

    def get_relic_sources(self, relic_name: str) -> list[dict]:
        self._ensure_loaded()
        return self._relic_sources.get(relic_name, [])
