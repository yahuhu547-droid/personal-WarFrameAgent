import json
from pathlib import Path

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

    service = BilibiliRecommendationService(BilibiliRecommendationStore(path))

    assert service.recommend("托里德多少钱") == []
    assert service.recommend("托里德怎么玩") == []
    assert is_bilibili_recommendation_intent("托里德怎么配卡") is True
    assert is_bilibili_recommendation_intent("托里德攻略") is True
    assert is_bilibili_recommendation_intent("托里德怎么玩") is False
    assert is_bilibili_recommendation_intent("托里德多少钱") is False


def test_wukong_alias_has_guide_intent_but_no_repository_match():
    service = BilibiliRecommendationService(BilibiliRecommendationStore(Path("data/bilibili_recommendations.json")))

    assert is_bilibili_recommendation_intent("猴子该怎么配卡") is True
    assert service.recommend("猴子该怎么配卡") == []


def test_recommend_matches_warframe_and_companion_guides(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [
        {
            "id": "volt",
            "title": "Volt-战甲攻略",
            "url": "https://www.bilibili.com/video/BVvolt/",
            "warframes": ["Volt", "伏特", "电男"],
            "aliases": ["伏特攻略", "电男教程"],
            "topics": ["攻略", "战甲"],
            "category": "warframe",
        },
        {
            "id": "smeeta",
            "title": "笑面型库娃-宠物攻略",
            "url": "https://www.bilibili.com/video/BVsmeeta/",
            "companions": ["笑面型库娃", "猫猫"],
            "aliases": ["笑面型库娃攻略", "猫猫攻略"],
            "topics": ["攻略", "宠物"],
            "category": "companion",
        },
    ])
    service = BilibiliRecommendationService(BilibiliRecommendationStore(path))

    assert [match.video.id for match in service.recommend("伏特攻略视频")] == ["volt"]
    assert [match.video.id for match in service.recommend("笑面型库娃攻略")] == ["smeeta"]


def test_companion_category_query_returns_companion_only(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [
        {
            "id": "volt",
            "title": "Volt-战甲攻略",
            "url": "https://www.bilibili.com/video/BVvolt/",
            "warframes": ["Volt"],
            "topics": ["攻略"],
            "category": "warframe",
            "priority": 100,
        },
        {
            "id": "smeeta",
            "title": "笑面型库娃-宠物攻略",
            "url": "https://www.bilibili.com/video/BVsmeeta/",
            "companions": ["笑面型库娃"],
            "topics": ["攻略"],
            "category": "companion",
            "priority": 10,
        },
    ])

    matches = BilibiliRecommendationService(BilibiliRecommendationStore(path)).recommend("推荐宠物攻略视频")

    assert [match.video.id for match in matches] == ["smeeta"]


def test_warframe_category_query_returns_warframes_only(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [
        {
            "id": "volt",
            "title": "Volt-战甲攻略",
            "url": "https://www.bilibili.com/video/BVvolt/",
            "warframes": ["Volt"],
            "topics": ["攻略"],
            "category": "warframe",
            "priority": 10,
        },
        {
            "id": "smeeta",
            "title": "笑面型库娃-宠物攻略",
            "url": "https://www.bilibili.com/video/BVsmeeta/",
            "companions": ["笑面型库娃"],
            "topics": ["攻略"],
            "category": "companion",
            "priority": 100,
        },
    ])

    matches = BilibiliRecommendationService(BilibiliRecommendationStore(path)).recommend("推荐战甲攻略视频")

    assert [match.video.id for match in matches] == ["volt"]


def test_specific_warframe_query_requires_specific_warframe_match(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [
        {
            "id": "volt",
            "title": "伏特Volt最新配卡攻略",
            "url": "https://www.bilibili.com/video/BVvolt/",
            "warframes": ["Volt"],
            "aliases": ["伏特配卡", "电男攻略", "Volt build"],
            "topics": ["攻略", "配卡"],
            "category": "warframe",
            "priority": 80,
        },
        {
            "id": "mesa",
            "title": "Mesa弥撒女枪详细配卡攻略",
            "url": "https://www.bilibili.com/video/BVmesa/",
            "warframes": ["Mesa"],
            "aliases": ["Mesa配卡", "弥撒攻略", "女枪攻略"],
            "topics": ["攻略", "配卡"],
            "category": "warframe",
            "priority": 90,
        },
        {
            "id": "generic",
            "title": "战甲配卡合集",
            "url": "https://www.bilibili.com/video/BVgeneric/",
            "warframes": ["战甲"],
            "aliases": ["战甲配卡", "战甲攻略"],
            "topics": ["攻略", "配卡"],
            "category": "warframe",
            "priority": 100,
        },
        {
            "id": "voruna",
            "title": "狼甲Voruna配卡攻略",
            "url": "https://www.bilibili.com/video/BVvoruna/",
            "warframes": ["Voruna"],
            "aliases": ["狼甲配卡", "Voruna build", "沃鲁纳攻略"],
            "topics": ["攻略", "配卡"],
            "category": "warframe",
            "priority": 80,
        },
    ])
    service = BilibiliRecommendationService(BilibiliRecommendationStore(path))

    assert [match.video.id for match in service.recommend("伏特配卡")] == ["volt"]
    assert [match.video.id for match in service.recommend("电男攻略视频")] == ["volt"]
    assert [match.video.id for match in service.recommend("Mesa配卡")] == ["mesa"]
    assert [match.video.id for match in service.recommend("狼甲配卡")] == ["voruna"]


def test_companion_recommendations_prefer_newer_updates_when_same_pet_matches(tmp_path):
    path = tmp_path / "bilibili_recommendations.json"
    _write_records(path, [
        {
            "id": "old-smeeta",
            "title": "笑面型库娃-旧版宠物攻略",
            "url": "https://www.bilibili.com/video/BVoldsmeeta/",
            "companions": ["笑面型库娃"],
            "aliases": ["笑面型库娃攻略"],
            "topics": ["攻略", "宠物"],
            "category": "companion",
            "priority": 50,
            "updated_at": "2024-01-01",
        },
        {
            "id": "new-smeeta",
            "title": "笑面型库娃-2025新版宠物配置",
            "url": "https://www.bilibili.com/video/BVnewsmeeta/",
            "companions": ["笑面型库娃"],
            "aliases": ["笑面型库娃攻略"],
            "topics": ["攻略", "宠物"],
            "category": "companion",
            "priority": 50,
            "updated_at": "2025-05-01",
        },
    ])

    matches = BilibiliRecommendationService(BilibiliRecommendationStore(path)).recommend("笑面型库娃攻略")

    assert [match.video.id for match in matches][:2] == ["new-smeeta", "old-smeeta"]


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


def test_repository_recommendation_data_loads_expanded_fallback_library():
    records = BilibiliRecommendationStore(Path("data/bilibili_recommendations.json")).load()
    bvids = {record.bvid for record in records}

    categories = {record.category for record in records}

    assert len(records) >= 252
    assert "BV1Ad9iYSE4X" in bvids
    assert "BV1izo4YnEEr" in bvids
    assert "BV1vZZuYMEoN" in bvids
    assert "BV1DccBeSEZM" in bvids
    assert "BV1UT4ce3E4K" in bvids
    assert "warframe" in categories
    assert "companion" in categories
    assert all(record.needs_review is False for record in records)
