import json
import subprocess
import sys


def test_analyze_bilibili_video_writes_review_draft(tmp_path):
    output = tmp_path / "drafts.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            "tools/analyze_bilibili_video.py",
            "https://www.bilibili.com/video/BV1dJ5LzREZk?spm_id_from=333",
            "--title",
            "伯斯顿-步枪救星",
            "--timestamp",
            "8",
            "--timestamp",
            "29",
            "--frame",
            "data/video_frames/BV1dJ5LzREZk-8.png",
            "--frame",
            "data/video_frames/BV1dJ5LzREZk-29.png",
            "--fake-ocr-weapon",
            "伯斯顿 Prime",
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "BV1dJ5LzREZk" in result.stdout
    saved = json.loads(output.read_text(encoding="utf-8").strip())
    assert saved["source"]["bvid"] == "BV1dJ5LzREZk"
    assert saved["title"] == "伯斯顿-步枪救星"
    assert saved["inferred_weapon"] == "伯斯顿 Prime"
    assert saved["inferred_category"] == "primary"
    assert saved["needs_review"] is True
    assert saved["trusted_for_agent_answers"] is False
    assert len(saved["frames"]) == 2
