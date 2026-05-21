import json

from warframe_agent.bilibili_recommendations import (
    BilibiliRecommendationService,
    BilibiliRecommendationStore,
    format_bilibili_recommendations,
    is_bilibili_recommendation_intent,
)


def _write_records(path, records):
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def test_store_loads_valid_records_and_skips_invalid(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [
        {
            "id": "torid",
            "title": "托里德-射线荣光的继承者",
            "url": "https://www.bilibili.com/video/BV1pZr5YREtY/",
            "weapons": ["托里德"],
            "aliases": ["托里德配卡"],
            "category": "主手",
        },
        {"id": "bad-url", "title": "bad", "url": "https://example.com/video"},
        {"id": "missing-title", "url": "https://www.bilibili.com/video/BVxxx/"},
        {
            "id": "review",
            "title": "待确认视频",
            "url": "https://www.bilibili.com/video/BVreview/",
            "needs_review": True,
        },
    ])

    records = BilibiliRecommendationStore(path).load()

    assert len(records) == 1
    assert records[0].id == "torid"
    assert records[0].url == "https://www.bilibili.com/video/BV1pZr5YREtY/"
    assert records[0].category == "primary"


def test_recommend_matches_torid_build_query(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [
        {
            "id": "torid",
            "title": "托里德-射线荣光的继承者",
            "url": "https://www.bilibili.com/video/BV1pZr5YREtY/",
            "weapons": ["托里德"],
            "aliases": ["托里德配卡"],
            "topics": ["配卡", "灵化"],
            "priority": 10,
        },
        {
            "id": "angstrum",
            "title": "棱晶安格斯特灵化配卡参考",
            "url": "https://www.bilibili.com/video/BV19WbBzHE8W/",
            "weapons": ["棱晶安格斯特"],
            "aliases": ["棱晶安格斯特配卡"],
            "topics": ["配卡"],
            "priority": 100,
        },
    ])

    matches = BilibiliRecommendationService(BilibiliRecommendationStore(path)).recommend("托里德怎么配卡")

    assert [match.video.id for match in matches] == ["torid"]


def test_recommend_matches_angstrum_video_query(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [{
        "id": "angstrum",
        "title": "棱晶安格斯特灵化配卡参考",
        "url": "https://www.bilibili.com/video/BV19WbBzHE8W/",
        "weapons": ["棱晶安格斯特", "安格斯特"],
        "aliases": ["棱晶安格斯特攻略"],
    }])

    matches = BilibiliRecommendationService(BilibiliRecommendationStore(path)).recommend("棱晶安格斯特攻略视频")

    assert len(matches) == 1
    assert matches[0].video.url.endswith("BV19WbBzHE8W/")


def test_non_guide_query_does_not_trigger_recommendations(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [{
        "id": "torid",
        "title": "托里德-射线荣光的继承者",
        "url": "https://www.bilibili.com/video/BV1pZr5YREtY/",
        "weapons": ["托里德"],
    }])

    matches = BilibiliRecommendationService(BilibiliRecommendationStore(path)).recommend("托里德多少钱")

    assert matches == []
    assert is_bilibili_recommendation_intent("托里德怎么配卡") is True
    assert is_bilibili_recommendation_intent("托里德多少钱") is False


def test_category_query_returns_matching_category_only(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [
        {
            "id": "burston",
            "title": "伯斯顿-步枪救星",
            "url": "https://www.bilibili.com/video/BV1dJ5LzREZk/",
            "weapons": ["伯斯顿"],
            "topics": ["配卡"],
            "category": "primary",
            "priority": 10,
        },
        {
            "id": "nikana",
            "title": "侍刃-近战老牌真神",
            "url": "https://www.bilibili.com/video/BV1eZPveRE39/",
            "weapons": ["侍刃"],
            "topics": ["配卡"],
            "category": "melee",
            "priority": 100,
        },
    ])

    matches = BilibiliRecommendationService(BilibiliRecommendationStore(path)).recommend("推荐几个主武器配卡视频")

    assert [match.video.id for match in matches] == ["burston"]


def test_format_bilibili_recommendations_outputs_markdown_links(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [{
        "id": "torid",
        "title": "托里德-射线荣光的继承者",
        "url": "https://www.bilibili.com/video/BV1pZr5YREtY/",
        "author": "206092469",
        "weapons": ["托里德"],
        "topics": ["配卡"],
        "category": "primary",
        "summary": "托里德参考视频。",
    }])
    matches = BilibiliRecommendationService(BilibiliRecommendationStore(path)).recommend("托里德配卡")

    text = format_bilibili_recommendations(matches)

    assert "参考视频" in text
    assert "[托里德-射线荣光的继承者](https://www.bilibili.com/video/BV1pZr5YREtY/)" in text
    assert "UP主：206092469" in text
    assert "类型：主武器" in text


def test_format_empty_recommendations_only_when_requested():
    assert format_bilibili_recommendations([]) == ""
    assert format_bilibili_recommendations([], empty_message=True) == "暂未收录相关 B 站视频。"
