from pathlib import Path

from PIL import Image

from warframe_agent.video_analysis.icon_match import IconHashIndex


def test_icon_hash_index_matches_nearest_icon(tmp_path):
    icon_dir = tmp_path / "icons"
    icon_dir.mkdir()
    red = icon_dir / "serration.png"
    blue = icon_dir / "split_chamber.png"
    query = tmp_path / "query.png"

    Image.new("RGB", (16, 16), "red").save(red)
    Image.new("RGB", (16, 16), "blue").save(blue)
    Image.new("RGB", (16, 16), "red").save(query)

    index = IconHashIndex.from_directory(icon_dir, kind="mod")
    matches = index.match(query, limit=1)

    assert matches[0].label == "serration"
    assert matches[0].kind == "mod"
    assert matches[0].score == 1.0
    assert Path(matches[0].source_icon) == red
