from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_SOURCE = Path("Extra Resource/exports/bilibili_metadata/bili-space-api-title-candidates.json")
DEFAULT_RECOMMENDATIONS = Path("data/bilibili_recommendations.json")
DEFAULT_REPORT = Path("Extra Resource/exports/bilibili_metadata/fallback_inventory_report.json")
DEFAULT_CANDIDATES = Path("Extra Resource/exports/bilibili_metadata/bilibili_recommendation_candidates.json")
DEFAULT_REVIEW_SUMMARY = Path("Extra Resource/exports/bilibili_metadata/bilibili_recommendation_review_summary.json")
FORBIDDEN_SUGGESTION_KEYS = {"mods", "mod", "arcanes", "arcane", "incarnon", "build", "school", "warframe", "riven", "damage", "playstyle"}

BILIBILI_VIDEO_PREFIX = "https://www.bilibili.com/video/"
CATEGORY_TOPIC = {"primary": "主手", "secondary": "副手", "melee": "近战", "warframe": "战甲", "companion": "同伴"}

KNOWN_WEAPON_MAPPINGS = {
    "BV1Ad9iYSE4X": {"category": "primary", "weapons": ["塞多", "Cedo"]},
    "BV15rLXzFE2C": {"category": "primary", "weapons": ["特拉", "Tetra"]},
    "BV1izo4YnEEr": {"category": "secondary", "weapons": ["脓痘", "Pox"]},
    "BV1vZZuYMEoN": {"category": "secondary", "weapons": ["啐沫者", "Catabolyst"]},
}

KNOWN_COMPANION_ALIASES = {
    "笑面型库娃": ["笑面型库娃", "笑面猫", "笑猫", "好运猫", "柴郡狯犽", "扫猫", "Smeeta Kavat"],
    "铁甲狐": ["铁甲狐", "Panzer Vulpaphyla", "病毒狐"],
    "机械猎犬": ["机械猎犬", "猎犬", "机械狗", "C系猎犬", "帕尔沃斯猎犬", "Hound"],
    "恐鸟": ["恐鸟", "自制恐鸟", "MOA"],
    "死亡魔方": ["死亡魔方", "Dethcube", "Deathcube"],
    "鹦鹉螺": ["鹦鹉螺", "Nautilus"],
    "蛟龙": ["蛟龙", "Diriga"],
    "赫利俄斯": ["赫利俄斯", "太阳神", "Helios"],
    "搬运者": ["搬运者", "Carrier"],
    "塔克桑": ["塔克桑", "Taxon"],
    "阴影": ["阴影", "Shade"],
    "奥克": ["奥克", "Oxylus"],
    "引灵": ["引灵"],
    "电气浮囊": ["电气浮囊"],
    "冰凇": ["冰凇", "冰淞"],
    "库娃": ["库娃", "猫猫", "猫"],
    "库狛": ["库狛", "突击狗", "隐身狗", "电狗", "盾狗", "挖蓝狗", "挖宝狗", "狗"],
    "守护": ["守护", "机械守护"],
    "嗜血猫": ["嗜血猫"],
    "同伴": ["同伴", "宠物"],
}
COMPANION_SOURCE_TOKENS = ("宠物", "同伴", "守护", "猎犬", "恐鸟", "库娃", "库狛")

KNOWN_WARFRAME_ALIASES = {
    "Volt": ["Volt", "伏特", "电男"],
    "Dante": ["Dante", "但丁"],
    "Mesa": ["Mesa", "弥撒", "女枪"],
    "Saryn": ["Saryn", "毒妈"],
    "Wisp": ["Wisp", "花妹"],
    "Revenant": ["Revenant", "吸血鬼", "夜灵"],
    "Nekros": ["Nekros", "摸尸", "摸尸甲"],
    "Khora": ["Khora", "猫甲"],
    "Gauss": ["Gauss", "高斯"],
    "Nova": ["Nova", "诺娃"],
    "Rhino": ["Rhino", "牛", "牛甲"],
    "Octavia": ["Octavia", "DJ"],
    "Protea": ["Protea", "普洛忒娅"],
    "Xaku": ["Xaku"],
    "Citrine": ["Citrine"],
    "Kullervo": ["Kullervo"],
    "Jade": ["Jade"],
    "Qorvex": ["Qorvex"],
    "Lavos": ["Lavos"],
    "Titania": ["Titania", "蝶妹"],
    "Mirage": ["Mirage", "小丑"],
    "Hildryn": ["Hildryn", "盾娘"],
    "Baruuk": ["Baruuk"],
    "Mag": ["Mag", "磁妹"],
    "Excalibur": ["Excalibur", "咖喱"],
    "Limbo": ["Limbo"],
    "Wukong": ["Wukong", "悟空", "猴子"],
    "Chroma": ["Chroma", "龙甲"],
    "Inaros": ["Inaros", "沙甲"],
    "Trinity": ["Trinity", "奶妈"],
    "Harrow": ["Harrow", "主教"],
    "Ivara": ["Ivara", "弓妹"],
    "Ember": ["Ember", "火鸡"],
    "Frost": ["Frost", "冰男"],
    "Equinox": ["Equinox", "阴阳"],
    "Sevagoth": ["Sevagoth", "鬼甲"],
    "Cyte-09": ["Cyte-09", "老九"],
    "Nyx": ["Nyx", "脑溢血"],
    "Voruna": ["Voruna", "狼甲", "狼女", "狼妹", "沃鲁纳", "沃鲁娜"],
}
WARFRAME_SOURCE_TOKENS = ("战甲", "甲", "Warframe", "warframe")

OUT_OF_SCOPE_TITLE_TOKENS = (
    "BOSS攻略",
    "萌新必看",
    "今日杂谈",
    "速览",
    "速报",
    "赠礼图鉴",
    "配色配卡",
)


@dataclass(frozen=True)
class SourceSpec:
    path: Path
    category: str = ""
    label: str = ""


@dataclass(frozen=True)
class BuildResult:
    report: dict[str, Any]
    candidates: list[dict[str, Any]]
    review_summary: dict[str, Any]
    appended: list[dict[str, Any]]


def build_outputs(
    *,
    source_path: Path = DEFAULT_SOURCE,
    source_specs: list[SourceSpec] | None = None,
    recommendations_path: Path = DEFAULT_RECOMMENDATIONS,
    report_path: Path = DEFAULT_REPORT,
    candidates_path: Path = DEFAULT_CANDIDATES,
    review_summary_path: Path | None = None,
    apply_approved_suggestions_path: Path | None = None,
    append_approved: bool = False,
    today: str | None = None,
) -> BuildResult:
    today = today or date.today().isoformat()
    review_summary_path = review_summary_path or candidates_path.with_name("bilibili_recommendation_review_summary.json")
    specs = source_specs or [SourceSpec(source_path)]
    source_items = _load_sources(specs)
    recommendations = _load_list(recommendations_path) if recommendations_path.exists() else []
    approved_bvids = {str(item.get("bvid") or "") for item in recommendations if item.get("bvid")}
    title_mappings = _build_title_mappings(recommendations)

    candidates = _build_candidates(source_items, approved_bvids, title_mappings=title_mappings, today=today)
    appended: list[dict[str, Any]] = []
    existing = {str(item.get("bvid") or "") for item in recommendations if item.get("bvid")}
    if append_approved:
        for candidate in candidates:
            if candidate.get("needs_review") or candidate.get("bvid") in existing:
                continue
            clean = {key: value for key, value in candidate.items() if key != "review_reason"}
            recommendations.append(clean)
            existing.add(str(clean.get("bvid") or ""))
            appended.append(clean)
    if apply_approved_suggestions_path:
        for suggestion in _load_approved_suggestions(apply_approved_suggestions_path):
            if suggestion.get("bvid") in existing:
                continue
            clean = _suggestion_to_record(suggestion, today=today)
            recommendations.append(clean)
            existing.add(str(clean.get("bvid") or ""))
            appended.append(clean)
    if append_approved or apply_approved_suggestions_path:
        _write_json(recommendations_path, recommendations)

    source_unique_bvids = _unique_bvids(source_items)
    report = {
        "source_file": str(source_path),
        "source_files": [_format_source_spec(spec) for spec in specs],
        "generated_at": today,
        "approved_library_count": len(recommendations) if append_approved else len(_load_list(recommendations_path)) if recommendations_path.exists() else 0,
        "source_candidate_count": len(source_items),
        "source_unique_bvid_count": len(source_unique_bvids),
        "already_approved_count": len([item for item in source_items if item.get("bvid") in approved_bvids]),
        "new_candidate_count": len(candidates),
        "auto_approved_new_count": len([item for item in candidates if not item.get("needs_review")]),
        "needs_review_new_count": len([item for item in candidates if item.get("needs_review")]),
        "already_approved_bvids": sorted(bvid for bvid in approved_bvids if bvid in source_unique_bvids),
        "auto_approved_new_bvids": [item["bvid"] for item in candidates if not item.get("needs_review")],
        "needs_review_new_bvids": [item["bvid"] for item in candidates if item.get("needs_review")],
        "appended_bvids": [item["bvid"] for item in appended],
        "notes": [
            "Only video metadata is generated; MOD/arcanes/incarnon choices are not written.",
            "Auto-approved candidates are limited to conservative title/weapon/category mappings.",
            "needs_review records must not be loaded by the recommendation service until reviewed.",
        ],
    }
    review_summary = _build_review_summary(candidates, generated_at=today)
    _write_json(candidates_path, candidates)
    _write_json(report_path, report)
    _write_json(review_summary_path, review_summary)
    return BuildResult(report=report, candidates=candidates, review_summary=review_summary, appended=appended)


def _build_candidates(source_items: list[dict[str, Any]], approved_bvids: set[str], *, title_mappings: dict[str, dict[str, Any]] | None = None, today: str) -> list[dict[str, Any]]:
    candidates = []
    seen = set()
    title_mappings = title_mappings or {}
    for item in source_items:
        bvid = str(item.get("bvid") or "")
        if not bvid or bvid in seen:
            continue
        seen.add(bvid)
        if bvid in approved_bvids:
            continue
        mapping = dict(KNOWN_WEAPON_MAPPINGS.get(bvid) or {})
        source_category = _clean_category(item.get("_source_category"))
        if source_category and not mapping.get("category"):
            mapping["category"] = source_category
        title = str(item.get("title") or "")
        companion_mapping = _extract_companion_mapping(item, source_category)
        if companion_mapping:
            candidates.append(_make_record(item, companion_mapping, needs_review=False, reason="companion_final_metadata_confirmed_from_local_search", today=today))
            continue
        warframe_mapping = _extract_warframe_mapping(item, source_category)
        if warframe_mapping:
            candidates.append(_make_record(item, warframe_mapping, needs_review=False, reason="warframe_final_metadata_confirmed_from_local_search", today=today))
            continue
        if not mapping.get("weapons"):
            mapping.update(_match_title_mapping(title, source_category, title_mappings))
        if mapping.get("weapons") and mapping.get("category"):
            candidates.append(_make_record(item, mapping, needs_review=False, reason="title_and_weapon_mapping_confirmed_from_local_metadata", today=today))
            continue
        if any(token in title for token in OUT_OF_SCOPE_TITLE_TOKENS) or not ("-" in title or "，" in title):
            reason = "out_of_scope_or_not_basic_weapon_build"
        else:
            reason = "weapon_or_category_needs_user_review"
        candidates.append(_make_record(item, mapping, needs_review=True, reason=reason, today=today))
    return candidates


def _load_approved_suggestions(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    suggestions = raw.get("suggestions") if isinstance(raw, dict) else raw
    if not isinstance(suggestions, list):
        raise ValueError(f"{path} must contain a suggestions list")
    approved = []
    for suggestion in suggestions:
        if not isinstance(suggestion, dict) or not suggestion.get("approved"):
            continue
        forbidden = sorted(key for key in suggestion if str(key).lower() in FORBIDDEN_SUGGESTION_KEYS)
        if forbidden:
            raise ValueError(f"Approved suggestion {suggestion.get('bvid', '')} contains forbidden fields: {', '.join(forbidden)}")
        bvid = str(suggestion.get("bvid") or "")
        category = _clean_category(suggestion.get("category"))
        weapons = [str(weapon).strip() for weapon in suggestion.get("weapons") or [] if str(weapon).strip()]
        if not bvid or not category or not weapons:
            continue
        approved.append(dict(suggestion, bvid=bvid, category=category, weapons=weapons))
    return approved


def _suggestion_to_record(suggestion: dict[str, Any], *, today: str) -> dict[str, Any]:
    category = _clean_category(suggestion.get("category"))
    weapons = [str(weapon).strip() for weapon in suggestion.get("weapons") or [] if str(weapon).strip()]
    aliases = [str(alias).strip() for alias in suggestion.get("aliases") or [] if str(alias).strip()]
    if not aliases:
        aliases = _aliases_for_weapons(weapons)
    title = _clean_title(str(suggestion.get("title") or weapons[0]))
    bvid = str(suggestion.get("bvid") or "")
    primary_name = weapons[0]
    topics = ["配卡", "攻略"]
    if category in CATEGORY_TOPIC:
        topics.append(CATEGORY_TOPIC[category])
    return {
        "id": f"{_slug(primary_name)}-build",
        "title": title,
        "url": f"{BILIBILI_VIDEO_PREFIX}{bvid}/",
        "bvid": bvid,
        "author": str(suggestion.get("author") or "206092469"),
        "topics": topics,
        "weapons": weapons,
        "warframes": [],
        "activities": ["钢铁之路"] if category in CATEGORY_TOPIC else [],
        "aliases": aliases[:20],
        "category": category,
        "needs_review": False,
        "summary": f"{primary_name}{CATEGORY_TOPIC.get(category, '')}配卡参考视频。",
        "priority": 50,
        "updated_at": today,
        "source": str(suggestion.get("source") or "bilibili_model_suggestion"),
        "collection_category": str(suggestion.get("collection_category") or category),
        "last_seen_at": today,
    }


def _build_review_summary(candidates: list[dict[str, Any]], *, generated_at: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {"primary": [], "secondary": [], "melee": [], "warframe": [], "companion": [], "uncategorized": []}
    for candidate in candidates:
        if not candidate.get("needs_review"):
            continue
        category = _clean_category(candidate.get("category")) or "uncategorized"
        groups.setdefault(category, []).append({
            "bvid": candidate.get("bvid", ""),
            "title": candidate.get("title", ""),
            "url": candidate.get("url", ""),
            "title_subject": _title_subject(str(candidate.get("title") or "")),
            "weapons": candidate.get("weapons", []),
            "warframes": candidate.get("warframes", []),
            "companions": candidate.get("companions", []),
            "category": category if category != "uncategorized" else "",
            "collection_category": candidate.get("collection_category", ""),
            "review_reason": candidate.get("review_reason", ""),
            "source": candidate.get("source", ""),
        })
    groups = {category: entries for category, entries in groups.items() if entries}
    return {
        "generated_at": generated_at,
        "needs_review_count": sum(len(entries) for entries in groups.values()),
        "groups": groups,
        "notes": [
            "This file is for human review only.",
            "Only confirmed video metadata should be appended to data/bilibili_recommendations.json.",
            "MOD/arcanes/incarnon choices remain outside trusted recommendation data until user review.",
        ],
    }


def _build_title_mappings(recommendations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mappings: dict[str, dict[str, Any]] = {}
    for metadata in list(KNOWN_WEAPON_MAPPINGS.values()) + recommendations:
        category = _clean_category(metadata.get("category"))
        weapons = [str(weapon).strip() for weapon in metadata.get("weapons") or [] if str(weapon).strip()]
        if not category or not weapons:
            continue
        aliases = [str(alias).strip() for alias in metadata.get("aliases") or [] if str(alias).strip()]
        for name in weapons + aliases:
            normalized = _normalize_title_token(name)
            if normalized:
                mappings.setdefault(normalized, {"category": category, "weapons": weapons})
    return mappings


def _match_title_mapping(title: str, source_category: str, title_mappings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    prefix = _title_subject(title)
    normalized_prefix = _normalize_title_token(prefix)
    if not normalized_prefix:
        return {}
    for key in sorted(title_mappings, key=len, reverse=True):
        if normalized_prefix != key:
            continue
        mapping = dict(title_mappings[key])
        if source_category and mapping.get("category") != source_category:
            return {}
        return mapping
    return {}


def _extract_companion_mapping(item: dict[str, Any], source_category: str) -> dict[str, Any]:
    title = str(item.get("title") or "")
    query = str(item.get("query") or "")
    label = str(item.get("_source_label") or "")
    combined = f"{title} {query} {label}"
    if source_category != "companion" and not any(token in combined for token in COMPANION_SOURCE_TOKENS):
        return {}

    matched = []
    normalized_combined = _normalize_title_token(combined)
    for companion, aliases in KNOWN_COMPANION_ALIASES.items():
        for alias in aliases:
            if _normalize_title_token(alias) in normalized_combined:
                matched.append(companion)
                break
    if len(matched) > 1:
        matched = [companion for companion in matched if companion != "同伴"]
    if not matched:
        matched = ["同伴"]
    return {"category": "companion", "companions": _dedupe(matched)}


def _extract_warframe_mapping(item: dict[str, Any], source_category: str) -> dict[str, Any]:
    title = str(item.get("title") or "")
    query = str(item.get("query") or "")
    label = str(item.get("_source_label") or "")
    combined = f"{title} {query} {label}"
    is_final_source = "warframe_build_links_final" in label or "warframe" in label
    if source_category != "warframe" and not is_final_source and not any(token in combined for token in WARFRAME_SOURCE_TOKENS):
        return {}

    matched = []
    normalized_combined = _normalize_title_token(combined)
    for warframe, aliases in KNOWN_WARFRAME_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalize_title_token(alias)
            if normalized_alias and normalized_alias in normalized_combined:
                matched.append(warframe)
                break
    if not matched and is_final_source and any(token in combined for token in ("战甲", "Warframe", "warframe")):
        matched = ["战甲"]
    if not matched:
        return {}
    if len(matched) > 1:
        matched = [warframe for warframe in matched if warframe != "战甲"]
    return {"category": "warframe", "warframes": _dedupe(matched)}


def _title_subject(title: str) -> str:
    cleaned = _clean_title(title)
    return cleaned.split("-", 1)[0].split("，", 1)[0].strip()


def _normalize_title_token(value: str) -> str:
    value = _clean_title(value).lower()
    value = re.sub(r"配卡|攻略|教程|视频|build", "", value, flags=re.IGNORECASE)
    return re.sub(r"[^0-9a-z一-鿿]+", "", value)


def _make_record(item: dict[str, Any], metadata: dict[str, Any], *, needs_review: bool, reason: str, today: str) -> dict[str, Any]:
    title = _clean_title(str(item.get("title") or ""))
    category = str(metadata.get("category") or "")
    weapons = list(metadata.get("weapons") or [])
    warframes = list(metadata.get("warframes") or [])
    companions = list(metadata.get("companions") or [])
    if not weapons and not warframes and not companions and title:
        weapons = [title.split("-", 1)[0].split("，", 1)[0].strip()]
    topics = ["配卡", "攻略"]
    if category in CATEGORY_TOPIC:
        topics.append(CATEGORY_TOPIC[category])
    if category == "companion":
        aliases = _aliases_for_companions(companions)
    elif category == "warframe":
        aliases = _aliases_for_warframes(warframes)
    else:
        aliases = _aliases_for_weapons(weapons)
    primary_name = weapons[0] if weapons else warframes[0] if warframes else companions[0] if companions else title
    if category == "companion":
        summary_subject = "、".join(companions[:3])
    elif category == "warframe":
        summary_subject = "、".join(warframes[:3])
    else:
        summary_subject = primary_name
    return {
        "id": f"{_slug(primary_name)}-build",
        "title": title,
        "url": f"{BILIBILI_VIDEO_PREFIX}{item.get('bvid')}/",
        "bvid": str(item.get("bvid") or ""),
        "author": str(item.get("author") or "206092469"),
        "topics": topics,
        "weapons": weapons,
        "warframes": warframes,
        "companions": companions,
        "activities": ["钢铁之路"] if category in {"primary", "secondary", "melee"} else [],
        "aliases": aliases,
        "category": category,
        "needs_review": bool(needs_review),
        "summary": f"{summary_subject}{CATEGORY_TOPIC.get(category, '')}配卡/攻略参考视频。" if summary_subject and category else f"{title} 配卡候选视频，需复核。",
        "priority": _priority_for_record(title, category=category, warframes=warframes, companions=companions),
        "updated_at": today,
        "source": str(item.get("_source_label") or "bilibili_space_api_title_candidates"),
        "collection_category": str(item.get("_source_category") or ""),
        "last_seen_at": today,
        "review_reason": reason,
    }


def _priority_for_record(title: str, *, category: str, warframes: list[str], companions: list[str]) -> int:
    priority = 50
    if category not in {"warframe", "companion"}:
        return priority
    specific_names = [name for name in (warframes if category == "warframe" else companions) if name not in {"战甲", "同伴"}]
    if len(specific_names) <= 2:
        priority += 10
    if any(token in title for token in ("2025", "最新", "现版本", "新版本", "当前版本", "T0")):
        priority += 20
    elif any(token in title for token in ("详细", "教程详解")):
        priority += 10
    if any(token in title for token in ("大合集", "合集", "排行", "梯度", "推荐更新")):
        priority -= 10
    return priority


def _aliases_for_weapons(weapons: list[str]) -> list[str]:
    aliases = []
    for weapon in weapons[:3]:
        aliases.extend([f"{weapon}配卡", f"{weapon}攻略"])
        if re.fullmatch(r"[A-Za-z0-9 ]+", weapon):
            aliases.append(f"{weapon} build".lower())
    deduped = []
    for alias in aliases:
        if alias and alias not in deduped:
            deduped.append(alias)
    return deduped[:20]


def _aliases_for_companions(companions: list[str]) -> list[str]:
    aliases = []
    for companion in companions[:8]:
        known_aliases = KNOWN_COMPANION_ALIASES.get(companion, [companion])
        for alias in known_aliases:
            aliases.extend([alias, f"{alias}配卡", f"{alias}攻略", f"{alias}教程"])
            if re.fullmatch(r"[A-Za-z0-9 ]+", alias):
                aliases.append(f"{alias} build".lower())
    if companions == ["同伴"]:
        aliases.extend(["宠物配卡", "宠物攻略", "同伴配卡", "同伴攻略"])
    return _dedupe(aliases)[:20]


def _aliases_for_warframes(warframes: list[str]) -> list[str]:
    aliases = []
    for warframe in warframes[:8]:
        known_aliases = KNOWN_WARFRAME_ALIASES.get(warframe, [warframe])
        for alias in known_aliases:
            aliases.extend([alias, f"{alias}配卡", f"{alias}攻略", f"{alias}教程"])
            if re.fullmatch(r"[A-Za-z0-9 ]+", alias):
                aliases.append(f"{alias} build")
    if warframes == ["战甲"]:
        aliases.extend(["战甲配卡", "战甲攻略", "战甲教程"])
    return _dedupe(aliases)[:24]


def _dedupe(values: list[str]) -> list[str]:
    deduped = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def _clean_title(title: str) -> str:
    title = title.strip()
    title = re.sub(r"《Warframe/星际战甲》", "", title).strip()
    title = re.sub(r"^《Warframe/星际战甲》", "", title).strip()
    return title.strip(" -_，,")


def _slug(text: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z一-鿿]+", "-", _clean_title(text)).strip("-").lower()
    return slug or "bilibili-video"


def _unique_bvids(items: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("bvid") or "") for item in items if item.get("bvid")}


def _load_sources(specs: list[SourceSpec]) -> list[dict[str, Any]]:
    items = []
    for spec in specs:
        for item in _load_list(spec.path):
            enriched = dict(item)
            if not enriched.get("bvid"):
                enriched["bvid"] = _extract_bvid(str(enriched.get("url") or ""))
            if spec.category:
                enriched["_source_category"] = spec.category
            enriched["_source_label"] = spec.label or spec.path.stem
            items.append(enriched)
    return items


def _extract_bvid(value: str) -> str:
    match = re.search(r"BV[0-9A-Za-z]+", value)
    return match.group(0) if match else ""


def _parse_source_spec(value: str) -> SourceSpec:
    if "=" not in value:
        return SourceSpec(Path(value))
    path_text, category_text = value.rsplit("=", 1)
    category = _clean_category(category_text)
    if not category:
        raise ValueError(f"Unsupported source category: {category_text}")
    return SourceSpec(Path(path_text), category=category, label=Path(path_text).stem)


def _format_source_spec(spec: SourceSpec) -> dict[str, str]:
    return {"path": str(spec.path), "category": spec.category, "label": spec.label or spec.path.stem}


def _clean_category(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    aliases = {
        "primary": "primary", "主手": "primary", "主武器": "primary",
        "secondary": "secondary", "副手": "secondary", "副武器": "secondary",
        "melee": "melee", "近战": "melee",
        "warframe": "warframe", "战甲": "warframe", "甲": "warframe",
        "companion": "companion", "宠物": "companion", "同伴": "companion", "守护": "companion", "猎犬": "companion", "恐鸟": "companion",
    }
    return aliases.get(normalized, "")


def _load_list(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [item for item in raw if isinstance(item, dict)]


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Bilibili fallback recommendation candidates from local metadata exports.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--source-spec",
        action="append",
        default=[],
        help="Metadata source with optional category override, e.g. primary.json=primary or melee.json=近战. Can be repeated.",
    )
    parser.add_argument("--recommendations", type=Path, default=DEFAULT_RECOMMENDATIONS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--review-summary", type=Path, default=DEFAULT_REVIEW_SUMMARY)
    parser.add_argument("--apply-approved-suggestions", type=Path, default=None, help="Append only human-approved model suggestions as safe video metadata.")
    parser.add_argument("--append-approved", action="store_true", help="Append auto-approved video metadata to the recommendation library.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_specs = [_parse_source_spec(value) for value in args.source_spec]
    result = build_outputs(
        source_path=args.source,
        source_specs=source_specs or None,
        recommendations_path=args.recommendations,
        report_path=args.report,
        candidates_path=args.candidates,
        review_summary_path=args.review_summary,
        apply_approved_suggestions_path=args.apply_approved_suggestions,
        append_approved=args.append_approved,
    )
    print(json.dumps({
        "report": str(args.report),
        "candidates": str(args.candidates),
        "review_summary": str(args.review_summary),
        "source_candidate_count": result.report["source_candidate_count"],
        "auto_approved_new_count": result.report["auto_approved_new_count"],
        "needs_review_new_count": result.report["needs_review_new_count"],
        "appended_count": len(result.appended),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
