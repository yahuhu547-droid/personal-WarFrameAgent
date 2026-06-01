import json

from warframe_agent.video_analysis.models import ParsedBuildDraft, VideoSource
from warframe_agent.video_analysis.storage import JsonlDraftStore


def test_jsonl_draft_store_appends_serialized_draft(tmp_path):
    path = tmp_path / "drafts.jsonl"
    draft = ParsedBuildDraft(
        source=VideoSource.from_url("https://www.bilibili.com/video/BV1dJ5LzREZk"),
        title="伯斯顿-步枪救星",
        inferred_weapon="伯斯顿",
    )

    JsonlDraftStore(path).append(draft)

    saved = json.loads(path.read_text(encoding="utf-8").strip())
    assert saved["source"]["bvid"] == "BV1dJ5LzREZk"
    assert saved["inferred_weapon"] == "伯斯顿"
    assert saved["needs_review"] is True
