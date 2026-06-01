from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

_BVID_RE = re.compile(r"BV[0-9A-Za-z]{10}")


@dataclass(frozen=True)
class VideoSource:
    url: str
    bvid: str
    platform: str = "bilibili"

    @classmethod
    def from_url(cls, url: str) -> "VideoSource":
        match = _BVID_RE.search(str(url or ""))
        if not match:
            raise ValueError("Bilibili URL must contain a BVID")
        bvid = match.group(0)
        return cls(url=f"https://www.bilibili.com/video/{bvid}", bvid=bvid)


@dataclass(frozen=True)
class FrameSample:
    path: str
    timestamp_seconds: float
    width: int = 0
    height: int = 0


@dataclass(frozen=True)
class DetectedRegion:
    kind: str
    box: list[int]
    confidence: float
    frame_path: str = ""


@dataclass(frozen=True)
class OcrCandidate:
    text: str
    region_kind: str
    confidence: float
    frame_path: str = ""


@dataclass(frozen=True)
class IconMatch:
    label: str
    kind: str
    score: float
    source_icon: str
    frame_path: str = ""
    region_kind: str = ""


@dataclass(frozen=True)
class HumanReviewRecord:
    reviewer: str
    reviewed_at: str
    accepted: bool
    notes: str = ""


@dataclass(frozen=True)
class ParsedBuildDraft:
    source: VideoSource
    title: str
    frames: list[FrameSample] = field(default_factory=list)
    regions: list[DetectedRegion] = field(default_factory=list)
    ocr_candidates: list[OcrCandidate] = field(default_factory=list)
    icon_matches: list[IconMatch] = field(default_factory=list)
    inferred_weapon: str = ""
    inferred_category: str = ""
    inferred_archetype: str = ""
    notes: list[str] = field(default_factory=list)
    needs_review: bool = True
    trusted_for_agent_answers: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
