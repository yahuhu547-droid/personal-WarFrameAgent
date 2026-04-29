from __future__ import annotations

import json
from pathlib import Path

from . import config

_alias_cache: dict[str, dict[str, str]] = {}
_item_data_cache: dict[str, dict[str, dict]] = {}


def clear_name_cache() -> None:
    _alias_cache.clear()
    _item_data_cache.clear()


def load_aliases(alias_path: Path = config.ALIAS_PATH) -> dict[str, str]:
    key = str(alias_path)
    if key not in _alias_cache:
        path = Path(alias_path)
        if not path.exists():
            _alias_cache[key] = {}
        else:
            with path.open("r", encoding="utf-8-sig") as file:
                _alias_cache[key] = json.load(file)
    return _alias_cache[key]


def load_item_data(item_data_path: Path = config.ITEMS_FULL_PATH) -> dict[str, dict]:
    key = str(item_data_path)
    if key not in _item_data_cache:
        path = Path(item_data_path)
        if not path.exists():
            _item_data_cache[key] = {}
        else:
            with path.open("r", encoding="utf-8-sig") as file:
                data = json.load(file)
            _item_data_cache[key] = {item.get("item_id"): item for item in data if item.get("item_id")}
    return _item_data_cache[key]


def preferred_chinese_name(
    item_id: str,
    alias_path: Path = config.ALIAS_PATH,
    item_data_path: Path = config.ITEMS_FULL_PATH,
) -> str | None:
    aliases = load_aliases(alias_path)
    candidates = [alias for alias, mapped_id in aliases.items() if mapped_id == item_id and _has_chinese(alias)]
    if candidates:
        return sorted(candidates, key=lambda alias: (-len(alias), alias))[0]
    item = load_item_data(item_data_path).get(item_id)
    if item and item.get("zh_name"):
        return item["zh_name"]
    return None


def english_name(item_id: str, item_data_path: Path = config.ITEMS_FULL_PATH) -> str:
    item = load_item_data(item_data_path).get(item_id)
    if item and item.get("en_name"):
        return item["en_name"]
    words = str(item_id).replace("_", " ").split()
    return " ".join(_title_word(word) for word in words)


def display_item_name(
    item_id: str,
    alias_path: Path = config.ALIAS_PATH,
    item_data_path: Path = config.ITEMS_FULL_PATH,
) -> str:
    chinese_name = preferred_chinese_name(item_id, alias_path=alias_path, item_data_path=item_data_path)
    english = english_name(item_id, item_data_path=item_data_path)
    if chinese_name:
        return f"{chinese_name} / {english} / {item_id}"
    return f"{english} / {item_id}"


def _has_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _title_word(word: str) -> str:
    if word.lower() == "prime":
        return "Prime"
    return word[:1].upper() + word[1:]

