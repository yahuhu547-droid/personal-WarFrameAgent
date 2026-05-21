from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import config

_BILIBILI_VIDEO_PREFIX = "https://www.bilibili.com/video/"
_GUIDE_INTENT_TOKENS = (
    "攻略", "指南", "打法", "怎么玩", "怎么打", "流程", "配卡", "配装",
    "武器怎么配", "钢铁怎么配", "视频", "b站", "bilibili", "教程",
    "主武器", "主手", "副武器", "副手", "近战",
    "build", "guide", "mod配置", "mod 配置",
)
_CATEGORY_ALIASES = {
    "primary": ("主武器", "主手", "主武器配卡", "主手配卡", "primary"),
    "secondary": ("副武器", "副手", "副武器配卡", "副手配卡", "secondary"),
    "melee": ("近战", "近战配卡", "melee"),
}
_CATEGORY_LABELS = {"primary": "主武器", "secondary": "副武器", "melee": "近战"}


@dataclass(frozen=True)
class BilibiliVideoRecommendation:
    id: str
    title: str
    url: str
    bvid: str = ""
    author: str = ""
    topics: list[str] = field(default_factory=list)
    weapons: list[str] = field(default_factory=list)
    warframes: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    category: str = ""
    needs_review: bool = False
    summary: str = ""
    priority: int = 0
    updated_at: str = ""


@dataclass(frozen=True)
class BilibiliRecommendationMatch:
    video: BilibiliVideoRecommendation
    score: int
    reasons: list[str]


class BilibiliRecommendationStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config.BILIBILI_RECOMMENDATIONS_PATH

    def load(self) -> list[BilibiliVideoRecommendation]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        records = []
        for item in raw:
            record = _record_from_raw(item)
            if record is not None:
                records.append(record)
        return records


class BilibiliRecommendationService:
    def __init__(self, store: BilibiliRecommendationStore | None = None) -> None:
        self.store = store or BilibiliRecommendationStore()

    def recommend(self, query: str, *, limit: int = 3) -> list[BilibiliRecommendationMatch]:
        if limit <= 0 or not is_bilibili_recommendation_intent(query):
            return []
        normalized_query = _normalize(query)
        matches = []
        for video in self.store.load():
            score, reasons = _score_video(normalized_query, video)
            if score > 0:
                matches.append(BilibiliRecommendationMatch(video=video, score=score, reasons=reasons))
        matches.sort(key=lambda item: (item.score, item.video.priority), reverse=True)
        return matches[:limit]


def is_bilibili_recommendation_intent(query: str) -> bool:
    normalized = _normalize(query)
    return any(_normalize(token) in normalized for token in _GUIDE_INTENT_TOKENS)


def format_bilibili_recommendations(matches: list[BilibiliRecommendationMatch], *, empty_message: bool = False) -> str:
    if not matches:
        return "暂未收录相关 B 站视频。" if empty_message else ""
    lines = ["参考视频："]
    for index, match in enumerate(matches, 1):
        video = match.video
        tags = _display_tags(video)
        reason = f"适合：{', '.join(tags)}" if tags else video.summary
        author = f"UP主：{video.author}。" if video.author else ""
        summary = f"{video.summary}" if video.summary else ""
        category = f"类型：{_CATEGORY_LABELS.get(video.category, video.category)}。" if video.category else ""
        detail = " ".join(part for part in (author, category, reason, summary) if part)
        lines.append(f"{index}. [{video.title}]({video.url})" + (f" — {detail}" if detail else ""))
    return "\n".join(lines)


def _record_from_raw(raw: Any) -> BilibiliVideoRecommendation | None:
    if not isinstance(raw, dict):
        return None
    record_id = _clean_text(raw.get("id"))
    title = _clean_text(raw.get("title"))
    url = _clean_text(raw.get("url"))
    if not record_id or not title or not url.startswith(_BILIBILI_VIDEO_PREFIX) or bool(raw.get("needs_review")):
        return None
    return BilibiliVideoRecommendation(
        id=record_id,
        title=title,
        url=url,
        bvid=_clean_text(raw.get("bvid")),
        author=_clean_text(raw.get("author")),
        topics=_clean_list(raw.get("topics")),
        weapons=_clean_list(raw.get("weapons")),
        warframes=_clean_list(raw.get("warframes")),
        activities=_clean_list(raw.get("activities")),
        aliases=_clean_list(raw.get("aliases")),
        category=_clean_category(raw.get("category")),
        needs_review=bool(raw.get("needs_review")),
        summary=_clean_text(raw.get("summary")),
        priority=_clean_int(raw.get("priority")),
        updated_at=_clean_text(raw.get("updated_at")),
    )


def _score_video(query: str, video: BilibiliVideoRecommendation) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    category_matches = _query_category_matches(query)
    field_weights = (
        ("别名", video.aliases, 80),
        ("武器", video.weapons, 60),
        ("战甲", video.warframes, 60),
        ("活动", video.activities, 50),
        ("类别", [_CATEGORY_LABELS.get(video.category, video.category)] if video.category in category_matches else [], 45),
        ("主题", video.topics, 25),
    )
    has_specific_match = False
    for label, values, weight in field_weights:
        for value in values:
            normalized_value = _normalize(value)
            if not normalized_value:
                continue
            if normalized_value == query:
                score += weight + 25
                reasons.append(f"{label}:{value}")
                if label != "主题":
                    has_specific_match = True
                break
            if normalized_value in query or query in normalized_value:
                score += weight
                reasons.append(f"{label}:{value}")
                if label != "主题":
                    has_specific_match = True
                break
    if not has_specific_match:
        return 0, []
    return score, reasons


def _display_tags(video: BilibiliVideoRecommendation) -> list[str]:
    tags = []
    for values in (video.weapons, video.warframes, video.activities, video.topics):
        for value in values:
            if value not in tags:
                tags.append(value)
            if len(tags) >= 4:
                return tags
    return tags


def _normalize(value: str) -> str:
    text = str(value or "").lower()
    return re.sub(r"[\s\-_·:：/|,，。.!！?？()（）\[\]【】]+", "", text)


def _clean_text(value: Any) -> str:
    return str(value or "").strip().replace("\r", " ").replace("\n", " ")[:300]


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value:
        text = _clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned[:20]


def _clean_category(value: Any) -> str:
    category = _normalize(str(value or ""))
    if category in _CATEGORY_ALIASES:
        return category
    for key, aliases in _CATEGORY_ALIASES.items():
        if category in {_normalize(alias) for alias in aliases}:
            return key
    return ""


def _query_category_matches(query: str) -> set[str]:
    matches = set()
    for category, aliases in _CATEGORY_ALIASES.items():
        if any(_normalize(alias) in query for alias in aliases):
            matches.add(category)
    return matches


def _clean_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
