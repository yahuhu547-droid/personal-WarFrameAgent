from warframe_agent.video_analysis.draft import ParsedBuildDraftBuilder
from warframe_agent.video_analysis.models import (
    DetectedRegion,
    FrameSample,
    IconMatch,
    OcrCandidate,
    VideoSource,
)


def test_draft_builder_infers_weapon_from_weapon_name_ocr():
    source = VideoSource.from_url("https://www.bilibili.com/video/BV1dJ5LzREZk")
    frame = FrameSample(path="frame.png", timestamp_seconds=29)
    region = DetectedRegion(kind="weapon_name", box=[0, 0, 100, 20], confidence=0.9, frame_path="frame.png")
    ocr = OcrCandidate(text="伯斯顿 Prime", region_kind="weapon_name", confidence=0.95, frame_path="frame.png")
    icon = IconMatch(label="膛线", kind="mod", score=0.8, source_icon="icons/serration.png")

    draft = ParsedBuildDraftBuilder().build(
        source=source,
        title="伯斯顿-步枪救星",
        frames=[frame],
        regions=[region],
        ocr_candidates=[ocr],
        icon_matches=[icon],
    )

    assert draft.inferred_weapon == "伯斯顿 Prime"
    assert draft.inferred_category == "primary"
    assert draft.needs_review is True
    assert draft.trusted_for_agent_answers is False
    assert "自动解析草稿；MOD、赋能、灵化选择需用户过目确认后才能写入可信数据。" in draft.notes
