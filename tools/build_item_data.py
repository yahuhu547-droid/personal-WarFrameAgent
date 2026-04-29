from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import requests

MARKET_ITEMS_URL = "https://api.warframe.market/v2/items"
MARKET_HEADERS = {
    "Accept": "application/json",
    "Language": "zh-hans",
    "Platform": "pc",
    "Crossplay": "true",
    "User-Agent": "warframe-local-trading-agent/1.0",
}
WEAPON_PART_LABELS = {
    "blueprint": "蓝图",
    "barrel": "枪管",
    "receiver": "枪机",
    "stock": "枪托",
    "blade": "刀刃",
    "handle": "刀柄",
    "link": "连接器",
    "disc": "圆盘",
    "grip": "弓身",
    "string": "弓弦",
    "upper_limb": "上弓臂",
    "lower_limb": "下弓臂",
}
WEAPON_SET_ALIAS_TERMS = ["一套", "整套", "全套"]
WEAPON_PART_ALIAS_TERMS = {
    "blueprint": ["蓝图", "总图", "bp"],
    "barrel": ["枪管"],
    "receiver": ["枪机", "机匣"],
    "stock": ["枪托"],
    "blade": ["刀刃"],
    "handle": ["刀柄"],
    "link": ["连接器", "连结器"],
    "disc": ["圆盘"],
    "grip": ["弓身", "弓把"],
    "string": ["弓弦"],
    "upper_limb": ["上弓臂"],
    "lower_limb": ["下弓臂"],
}
WEAPON_SUFFIXES = ["_set"] + [f"_{key}" for key in WEAPON_PART_LABELS]
WEAPON_SUFFIXES.sort(key=len, reverse=True)


def fetch_market_items() -> list[dict]:
    response = requests.get(MARKET_ITEMS_URL, headers=MARKET_HEADERS, timeout=30)
    response.raise_for_status()
    return response.json().get("data", [])


def build_item_records(payload: Iterable[dict]) -> list[dict]:
    records = []
    for item in payload:
        item_id = item.get("slug")
        if not item_id:
            continue
        i18n = item.get("i18n", {})
        zh_name = _localized_name(i18n, "zh-hans") or _localized_name(i18n, "zh") or ""
        en_name = _localized_name(i18n, "en") or _title_item_id(item_id)
        tags = item.get("tags", []) or []
        search_terms = sorted(set(_search_terms(item_id, zh_name, en_name)))
        records.append({
            "item_id": item_id,
            "zh_name": zh_name,
            "en_name": en_name,
            "tags": tags,
            "search_terms": search_terms,
        })
    return sorted(records, key=lambda record: record["item_id"])


def build_lookup_entries(records: Iterable[dict]) -> dict[str, str]:
    entries = {}
    for record in records:
        item_id = record["item_id"]
        for term in record.get("search_terms", []):
            if term:
                entries.setdefault(term, item_id)
    shorthand_aliases, conflicts = _build_safe_prime_weapon_aliases(list(records))
    for alias, item_id in shorthand_aliases.items():
        entries.setdefault(alias, item_id)
    for alias in conflicts:
        if alias in entries and entries[alias] not in conflicts[alias]:
            continue
        entries.pop(alias, None)
    return dict(sorted(entries.items()))


def write_item_data(payload: Iterable[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = build_item_records(payload)
    aliases = build_lookup_entries(records)
    shorthand_aliases, conflicts = _build_safe_prime_weapon_aliases(records)
    (output_dir / "items_full.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "generated_aliases.json").write_text(json.dumps(aliases, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "generated_alias_conflicts.json").write_text(json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8")
    rag_lines = []
    for record in records:
        rag_lines.append(json.dumps({
            "id": record["item_id"],
            "text": f"{record.get('zh_name') or ''} / {record.get('en_name') or ''} / {record['item_id']} tags: {', '.join(record.get('tags', []))}",
            "metadata": record,
        }, ensure_ascii=False))
    (output_dir / "rag_items.jsonl").write_text("\n".join(rag_lines) + ("\n" if rag_lines else ""), encoding="utf-8")


def main() -> None:
    payload = fetch_market_items()
    write_item_data(payload, Path("data"))
    print(f"已生成全量物品数据：{len(payload)} 条原始物品")
    print("输出：data/items_full.json, data/generated_aliases.json, data/generated_alias_conflicts.json, data/rag_items.jsonl")


def _build_safe_prime_weapon_aliases(records: list[dict]) -> tuple[dict[str, str], dict[str, list[str]]]:
    candidates = {}
    for record in records:
        tags = set(record.get("tags", []))
        if "prime" not in tags or "weapon" not in tags:
            continue
        item_id = record["item_id"]
        split = _split_weapon_item(item_id)
        if not split:
            continue
        _, part_key = split
        zh_base = _extract_weapon_zh_base(record.get("zh_name", ""), part_key)
        if not zh_base or len(zh_base) < 2:
            continue
        for alias in _weapon_alias_candidates(zh_base, part_key):
            candidates.setdefault(alias, set()).add(item_id)
    aliases = {}
    conflicts = {}
    for alias, item_ids in candidates.items():
        if len(item_ids) == 1:
            aliases[alias] = list(item_ids)[0]
        else:
            conflicts[alias] = sorted(item_ids)
    return aliases, conflicts


def _split_weapon_item(item_id: str) -> tuple[str, str] | None:
    for suffix in WEAPON_SUFFIXES:
        if item_id.endswith(suffix):
            base_id = item_id[: -len(suffix)]
            part_key = "set" if suffix == "_set" else suffix[1:]
            return base_id, part_key
    return None


def _extract_weapon_zh_base(zh_name: str, part_key: str) -> str | None:
    if not zh_name:
        return None
    tail = " Prime 一套" if part_key == "set" else f" Prime {WEAPON_PART_LABELS.get(part_key, '')}"
    if tail and zh_name.endswith(tail):
        return zh_name[: -len(tail)].strip()
    return None


def _weapon_alias_candidates(zh_base: str, part_key: str) -> list[str]:
    aliases = []
    terms = WEAPON_SET_ALIAS_TERMS if part_key == "set" else WEAPON_PART_ALIAS_TERMS.get(part_key, [])
    for base_variant in _weapon_zh_base_variants(zh_base):
        for term in terms:
            alias = f"{base_variant}p{term}"
            if alias not in aliases:
                aliases.append(alias)
    return aliases


def _weapon_zh_base_variants(zh_base: str) -> list[str]:
    variants = []
    for candidate in (
        zh_base.strip(),
        zh_base.replace("·", "").replace("・", "").strip(),
        zh_base.replace(" & ", "和").replace("&", "和").replace("＆", "和").strip(),
        zh_base.replace(" & ", "").replace("&", "").replace("＆", "").strip(),
    ):
        normalized = " ".join(candidate.split())
        if normalized and normalized not in variants:
            variants.append(normalized)
    return variants


def _localized_name(i18n: dict, locale: str) -> str:
    value = i18n.get(locale, {})
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return ""


def _search_terms(item_id: str, zh_name: str, en_name: str) -> Iterable[str]:
    yield item_id
    yield item_id.replace("_", " ")
    if zh_name:
        yield zh_name
        yield zh_name.replace("·", "")
        for suffix in ("赋能", "Prime", "蓝图"):
            if zh_name.endswith(suffix) and len(zh_name) > len(suffix):
                yield zh_name[: -len(suffix)]
    if en_name:
        yield en_name
        yield en_name.lower()
    if item_id.startswith("arcane_"):
        yield _title_item_id(item_id)


def _title_item_id(item_id: str) -> str:
    return " ".join(word.capitalize() if word != "prime" else "Prime" for word in item_id.split("_"))


if __name__ == "__main__":
    main()
