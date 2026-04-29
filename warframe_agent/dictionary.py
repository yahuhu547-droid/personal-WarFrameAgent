from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from . import config


@dataclass(frozen=True)
class ResolveResult:
    item_id: str
    source: str
    matched_name: str | None = None


class ItemResolver:
    def __init__(
        self,
        alias_path: Path = config.ALIAS_PATH,
        export_dir: Path = config.EXPORT_DIR,
        fallback: Callable[[str], str | None] | None = None,
        cache_path: Path = config.DICTIONARY_CACHE_PATH,
        generated_alias_path: Path = config.GENERATED_ALIAS_PATH,
    ):
        self.alias_path = Path(alias_path)
        self.generated_alias_path = Path(generated_alias_path)
        self.export_dir = Path(export_dir)
        self.fallback = fallback
        self.cache_path = Path(cache_path)
        self.aliases = self._load_aliases(self.alias_path)
        self.generated_aliases = self._load_aliases(self.generated_alias_path)
        self.dictionary = self._load_or_build_dictionary()

    def resolve(self, name: str) -> ResolveResult:
        raw_name = name.strip()
        if not raw_name:
            raise ValueError("物品名不能为空")

        alias_id = self._lookup_mapping(self.aliases, raw_name)
        if alias_id:
            return ResolveResult(alias_id, "alias", raw_name)

        dictionary_id = self._lookup_mapping(self.dictionary, raw_name)
        if dictionary_id:
            return ResolveResult(dictionary_id, "dictionary", raw_name)

        generated_alias_id = self._lookup_mapping(self.generated_aliases, raw_name)
        if generated_alias_id and _has_cjk(raw_name):
            return ResolveResult(generated_alias_id, "generated_alias", raw_name)

        normalized = normalize_market_id(raw_name)
        if normalized:
            return ResolveResult(normalized, "normalized", raw_name)

        if generated_alias_id:
            return ResolveResult(generated_alias_id, "generated_alias", raw_name)

        if self.fallback:
            fallback_id = self.fallback(raw_name)
            if fallback_id:
                return ResolveResult(normalize_market_id(fallback_id), "llm", raw_name)

        raise LookupError(f"无法识别物品：{raw_name}")

    def rebuild_cache(self) -> int:
        self.dictionary = self._build_dictionary()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.dictionary, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(self.dictionary)

    def _load_aliases(self, path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
        return {normalize_lookup_key(k): normalize_market_id(v) for k, v in data.items() if k and v}

    def _load_or_build_dictionary(self) -> dict[str, str]:
        if self.cache_path.exists():
            try:
                with self.cache_path.open("r", encoding="utf-8-sig") as file:
                    data = json.load(file)
                return {normalize_lookup_key(k): normalize_market_id(v) for k, v in data.items() if k and v}
            except (OSError, json.JSONDecodeError):
                pass
        return self._build_dictionary()

    def _build_dictionary(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for zh_file, en_file in config.EXPORT_FILE_PAIRS:
            zh_items = _extract_items(self.export_dir / zh_file)
            en_items = _extract_items(self.export_dir / en_file)
            en_by_unique = {
                item.get("uniqueName"): item
                for item in en_items
                if isinstance(item, dict) and item.get("uniqueName")
            }
            for zh_item in zh_items:
                if not isinstance(zh_item, dict):
                    continue
                en_item = en_by_unique.get(zh_item.get("uniqueName"), {})
                market_id = _item_market_id(zh_item, en_item)
                if not market_id:
                    continue
                names = set(_candidate_names(zh_item)) | set(_candidate_names(en_item))
                for candidate in names:
                    key = normalize_lookup_key(candidate)
                    if key:
                        mapping.setdefault(key, market_id)
        return mapping

    @staticmethod
    def _lookup_mapping(mapping: dict[str, str], name: str) -> str | None:
        return mapping.get(normalize_lookup_key(name))


def normalize_lookup_key(value: str) -> str:
    return re.sub(r"\s+", "", str(value).strip().lower())


def normalize_market_id(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _extract_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    return list(_walk_items(data))


def _walk_items(value) -> Iterable[dict]:
    if isinstance(value, list):
        for item in value:
            yield from _walk_items(item)
    elif isinstance(value, dict):
        if "uniqueName" in value and "name" in value:
            yield value
        for child in value.values():
            if isinstance(child, (list, dict)):
                yield from _walk_items(child)


def _candidate_names(item: dict) -> Iterable[str]:
    if not isinstance(item, dict):
        return []
    candidates = []
    for key in ("name", "compatName"):
        value = item.get(key)
        if isinstance(value, str):
            candidates.append(value)
    return candidates


def _item_market_id(zh_item: dict, en_item: dict) -> str:
    for item in (en_item, zh_item):
        for key in ("wikiaUrl", "name"):
            value = item.get(key)
            if isinstance(value, str) and value:
                if key == "wikiaUrl" and "/" in value:
                    value = value.rstrip("/").split("/")[-1]
                market_id = normalize_market_id(value)
                if market_id:
                    return market_id
    return ""



def _has_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)
