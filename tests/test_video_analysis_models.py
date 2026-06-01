from warframe_agent.video_analysis.models import (
    DetectedRegion,
    FrameSample,
    IconMatch,
    OcrCandidate,
    ParsedBuildDraft,
    VideoSource,
)


def test_video_source_normalizes_bilibili_url_to_bvid():
    source = VideoSource.from_url("https://www.bilibili.com/video/BV1dJ5LzREZk?spm_id_from=333")

    assert source.bvid == "BV1dJ5LzREZk"
    assert source.url == "https://www.bilibili.com/video/BV1dJ5LzREZk"


def test_video_source_rejects_url_without_bvid():
    try:
        VideoSource.from_url("https://www.bilibili.com/video/not-a-bvid")
    except ValueError as exc:
        assert "BVID" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_parsed_build_draft_marks_untrusted_by_default():
    draft = ParsedBuildDraft(
        source=VideoSource.from_url("https://www.bilibili.com/video/BV1dJ5LzREZk"),
        title="伯斯顿-步枪救星",
        frames=[FrameSample(path="frames/burston-29.png", timestamp_seconds=29.0)],
        regions=[DetectedRegion(kind="mod_grid", box=[0, 0, 100, 100], confidence=0.8)],
        ocr_candidates=[OcrCandidate(text="伯斯顿", region_kind="weapon_name", confidence=0.9)],
        icon_matches=[IconMatch(label="膛线", kind="mod", score=0.82, source_icon="icons/serration.png")],
    )

    assert draft.needs_review is True
    assert draft.trusted_for_agent_answers is False
    assert draft.source.bvid == "BV1dJ5LzREZk"
