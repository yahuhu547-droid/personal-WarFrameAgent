from __future__ import annotations

from .models import DetectedRegion, FrameSample, IconMatch, OcrCandidate, ParsedBuildDraft, VideoSource

_PRIMARY_HINTS = ("伯斯顿", "托里德", "冷冻光束", "龙骑兵", "沙皇", "步枪", "霰弹枪")
_SECONDARY_HINTS = ("安格斯特", "葬铭", "努寇", "史特克", "副武器", "手枪")
_MELEE_HINTS = ("侍刃", "马谢特", "佐伦", "凯旋之爪", "执法者", "近战")


class ParsedBuildDraftBuilder:
    def build(
        self,
        *,
        source: VideoSource,
        title: str,
        frames: list[FrameSample] | None = None,
        regions: list[DetectedRegion] | None = None,
        ocr_candidates: list[OcrCandidate] | None = None,
        icon_matches: list[IconMatch] | None = None,
    ) -> ParsedBuildDraft:
        frames = frames or []
        regions = regions or []
        ocr_candidates = ocr_candidates or []
        icon_matches = icon_matches or []
        inferred_weapon = self._infer_weapon(title, ocr_candidates)
        return ParsedBuildDraft(
            source=source,
            title=title,
            frames=frames,
            regions=regions,
            ocr_candidates=ocr_candidates,
            icon_matches=icon_matches,
            inferred_weapon=inferred_weapon,
            inferred_category=self._infer_category(title, inferred_weapon),
            notes=["自动解析草稿；MOD、赋能、灵化选择需用户过目确认后才能写入可信数据。"],
            needs_review=True,
            trusted_for_agent_answers=False,
        )

    def _infer_weapon(self, title: str, ocr_candidates: list[OcrCandidate]) -> str:
        for candidate in ocr_candidates:
            if candidate.region_kind == "weapon_name" and candidate.text.strip():
                return candidate.text.strip()
        return title.split("-", 1)[0].strip()

    def _infer_category(self, title: str, weapon: str) -> str:
        haystack = f"{title} {weapon}"
        if any(token in haystack for token in _MELEE_HINTS):
            return "melee"
        if any(token in haystack for token in _SECONDARY_HINTS):
            return "secondary"
        if any(token in haystack for token in _PRIMARY_HINTS):
            return "primary"
        return ""
