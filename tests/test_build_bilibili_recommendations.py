import json
from pathlib import Path

from tools.build_bilibili_recommendations import SourceSpec, build_outputs
from warframe_agent.bilibili_recommendations import BilibiliRecommendationService
from warframe_agent.bilibili_recommendations import BilibiliRecommendationStore


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_build_outputs_generates_report_and_review_candidates(tmp_path):
    source = tmp_path / "source.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    _write_json(source, [
        {
            "url": "https://www.bilibili.com/video/BV1pZr5YREtY/",
            "bvid": "BV1pZr5YREtY",
            "title": "托里德-射线荣光的继承者《Warframe/星际战甲》",
            "author": "206092469",
        },
        {
            "url": "https://www.bilibili.com/video/BV1Ad9iYSE4X/",
            "bvid": "BV1Ad9iYSE4X",
            "title": "塞多-触暴双修《Warframe/星际战甲》",
            "author": "206092469",
        },
        {
            "url": "https://www.bilibili.com/video/BV1TUkuYnE9w/",
            "bvid": "BV1TUkuYnE9w",
            "title": "《Warframe/星际战甲》任务分类，萌新必看！",
            "author": "206092469",
        },
    ])
    _write_json(recommendations, [{
        "id": "torid",
        "title": "托里德-射线荣光的继承者",
        "url": "https://www.bilibili.com/video/BV1pZr5YREtY/",
        "bvid": "BV1pZr5YREtY",
        "weapons": ["托里德"],
        "needs_review": False,
    }])

    result = build_outputs(
        source_path=source,
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        today="2026-05-21",
    )

    assert result.report["source_candidate_count"] == 3
    assert result.report["already_approved_count"] == 1
    assert result.report["auto_approved_new_bvids"] == ["BV1Ad9iYSE4X"]
    assert result.report["needs_review_new_bvids"] == ["BV1TUkuYnE9w"]
    generated = json.loads(candidates.read_text(encoding="utf-8"))
    assert generated[0]["weapons"] == ["塞多", "Cedo"]
    assert generated[0]["needs_review"] is False
    assert generated[1]["needs_review"] is True
    assert "MOD" not in json.dumps(generated, ensure_ascii=False)
    assert report.exists()


def test_append_approved_only_adds_non_review_video_metadata(tmp_path):
    source = tmp_path / "source.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    _write_json(source, [
        {
            "url": "https://www.bilibili.com/video/BV1Ad9iYSE4X/",
            "bvid": "BV1Ad9iYSE4X",
            "title": "塞多-触暴双修《Warframe/星际战甲》",
            "author": "206092469",
        },
        {
            "url": "https://www.bilibili.com/video/BV1TUkuYnE9w/",
            "bvid": "BV1TUkuYnE9w",
            "title": "《Warframe/星际战甲》任务分类，萌新必看！",
            "author": "206092469",
        },
    ])
    _write_json(recommendations, [])

    result = build_outputs(
        source_path=source,
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        append_approved=True,
        today="2026-05-21",
    )

    assert [item["bvid"] for item in result.appended] == ["BV1Ad9iYSE4X"]
    loaded = BilibiliRecommendationStore(recommendations).load()
    assert [record.bvid for record in loaded] == ["BV1Ad9iYSE4X"]
    assert loaded[0].category == "primary"
    assert loaded[0].needs_review is False


def test_source_specs_attach_collection_category_without_approving_unknown_weapons(tmp_path):
    primary_source = tmp_path / "primary.json"
    melee_source = tmp_path / "melee.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    review_summary = tmp_path / "review_summary.json"
    _write_json(primary_source, [{
        "url": "https://www.bilibili.com/video/BVPRIMARY01/",
        "bvid": "BVPRIMARY01",
        "title": "示例步枪-候选标题《Warframe/星际战甲》",
        "author": "206092469",
    }])
    _write_json(melee_source, [{
        "url": "https://www.bilibili.com/video/BVMELEE0001/",
        "bvid": "BVMELEE0001",
        "title": "示例近战-候选标题《Warframe/星际战甲》",
        "author": "206092469",
    }])
    _write_json(recommendations, [])

    result = build_outputs(
        source_specs=[SourceSpec(primary_source, category="primary", label="primary_collection"), SourceSpec(melee_source, category="melee", label="melee_collection")],
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        review_summary_path=review_summary,
        append_approved=True,
        today="2026-05-21",
    )

    assert result.appended == []
    generated = json.loads(candidates.read_text(encoding="utf-8"))
    assert [item["collection_category"] for item in generated] == ["primary", "melee"]
    assert [item["category"] for item in generated] == ["primary", "melee"]
    assert all(item["needs_review"] is True for item in generated)
    assert all(item["review_reason"] == "weapon_or_category_needs_user_review" for item in generated)
    assert result.report["source_files"] == [
        {"path": str(primary_source), "category": "primary", "label": "primary_collection"},
        {"path": str(melee_source), "category": "melee", "label": "melee_collection"},
    ]
    summary = json.loads(review_summary.read_text(encoding="utf-8"))
    assert summary["needs_review_count"] == 2
    assert [item["bvid"] for item in summary["groups"]["primary"]] == ["BVPRIMARY01"]
    assert [item["title_subject"] for item in summary["groups"]["melee"]] == ["示例近战"]
    assert summary["groups"]["primary"][0]["review_reason"] == "weapon_or_category_needs_user_review"
    assert result.review_summary == summary
    assert BilibiliRecommendationStore(recommendations).load() == []


def test_source_spec_extracts_bvid_from_url_only_records(tmp_path):
    source = tmp_path / "primary.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    _write_json(source, [{
        "url": "https://www.bilibili.com/video/BVURLONLY01/?spm_id_from=333.788",
        "title": "示例主武器-候选标题《Warframe/星际战甲》",
        "author": "206092469",
    }])
    _write_json(recommendations, [])

    result = build_outputs(
        source_specs=[SourceSpec(source, category="primary", label="primary_collection")],
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        append_approved=True,
        today="2026-05-21",
    )

    assert result.appended == []
    generated = json.loads(candidates.read_text(encoding="utf-8"))
    assert generated[0]["bvid"] == "BVURLONLY01"
    assert generated[0]["url"] == "https://www.bilibili.com/video/BVURLONLY01/"
    assert generated[0]["category"] == "primary"
    assert generated[0]["collection_category"] == "primary"
    assert generated[0]["needs_review"] is True
    assert result.report["source_unique_bvid_count"] == 1
    assert BilibiliRecommendationStore(recommendations).load() == []


def test_title_prefix_matching_uses_approved_library_without_manual_bvid_mapping(tmp_path):
    source = tmp_path / "source.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    _write_json(source, [{
        "url": "https://www.bilibili.com/video/BVNEWTORID01/",
        "bvid": "BVNEWTORID01",
        "title": "托里德-新版钢铁配卡《Warframe/星际战甲》",
        "author": "206092469",
    }])
    _write_json(recommendations, [{
        "id": "torid",
        "title": "托里德-射线荣光的继承者",
        "url": "https://www.bilibili.com/video/BV1pZr5YREtY/",
        "bvid": "BV1pZr5YREtY",
        "weapons": ["托里德", "Torid"],
        "aliases": ["托里德配卡"],
        "category": "primary",
        "needs_review": False,
    }])

    result = build_outputs(
        source_path=source,
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        append_approved=True,
        today="2026-05-21",
    )

    assert [item["bvid"] for item in result.appended] == ["BVNEWTORID01"]
    loaded = BilibiliRecommendationStore(recommendations).load()
    assert [record.bvid for record in loaded] == ["BV1pZr5YREtY", "BVNEWTORID01"]
    assert loaded[1].weapons == ["托里德", "Torid"]
    assert loaded[1].category == "primary"
    assert loaded[1].needs_review is False


def test_title_prefix_matching_rejects_collection_category_mismatch(tmp_path):
    source = tmp_path / "melee.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    _write_json(source, [{
        "url": "https://www.bilibili.com/video/BVMISMATCH01/",
        "title": "托里德-误放近战合集《Warframe/星际战甲》",
        "author": "206092469",
    }])
    _write_json(recommendations, [{
        "id": "torid",
        "title": "托里德-射线荣光的继承者",
        "url": "https://www.bilibili.com/video/BV1pZr5YREtY/",
        "bvid": "BV1pZr5YREtY",
        "weapons": ["托里德", "Torid"],
        "category": "primary",
        "needs_review": False,
    }])

    result = build_outputs(
        source_specs=[SourceSpec(source, category="melee", label="melee_collection")],
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        append_approved=True,
        today="2026-05-21",
    )

    assert result.appended == []
    generated = json.loads(candidates.read_text(encoding="utf-8"))
    assert generated[0]["bvid"] == "BVMISMATCH01"
    assert generated[0]["category"] == "melee"
    assert generated[0]["needs_review"] is True
    assert generated[0]["review_reason"] == "weapon_or_category_needs_user_review"
    assert [record.bvid for record in BilibiliRecommendationStore(recommendations).load()] == ["BV1pZr5YREtY"]


def test_apply_approved_suggestions_only_appends_human_approved_safe_metadata(tmp_path):
    source = tmp_path / "source.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    suggestions = tmp_path / "suggestions.json"
    _write_json(source, [])
    _write_json(recommendations, [])
    _write_json(suggestions, {"suggestions": [
        {
            "bvid": "BVAPPROVED01",
            "title": "舍杜，挂机必备！",
            "url": "https://www.bilibili.com/video/BVAPPROVED01/",
            "category": "primary",
            "collection_category": "primary",
            "weapons": ["舍杜"],
            "aliases": ["舍杜配卡", "舍杜攻略"],
            "source": "primary_collection",
            "approved": True,
        },
        {
            "bvid": "BVUNAPPROVED",
            "title": "典客-炸比之殇",
            "category": "primary",
            "weapons": ["典客"],
            "approved": False,
        },
    ]})

    result = build_outputs(
        source_path=source,
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        apply_approved_suggestions_path=suggestions,
        today="2026-05-22",
    )

    assert [item["bvid"] for item in result.appended] == ["BVAPPROVED01"]
    loaded = BilibiliRecommendationStore(recommendations).load()
    assert [record.bvid for record in loaded] == ["BVAPPROVED01"]
    written = json.loads(recommendations.read_text(encoding="utf-8"))
    assert written[0]["weapons"] == ["舍杜"]
    assert written[0]["category"] == "primary"
    assert written[0]["needs_review"] is False
    assert "mods" not in json.dumps(written, ensure_ascii=False).lower()
    assert "incarnon" not in json.dumps(written, ensure_ascii=False).lower()


def test_apply_approved_suggestions_rejects_forbidden_fields(tmp_path):
    source = tmp_path / "source.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    suggestions = tmp_path / "suggestions.json"
    _write_json(source, [])
    _write_json(recommendations, [])
    _write_json(suggestions, {"suggestions": [{
        "bvid": "BVBAD",
        "title": "托里德-配卡",
        "category": "primary",
        "weapons": ["托里德"],
        "mods": ["膛线"],
        "approved": True,
    }]})

    try:
        build_outputs(
            source_path=source,
            recommendations_path=recommendations,
            report_path=report,
            candidates_path=candidates,
            apply_approved_suggestions_path=suggestions,
            today="2026-05-22",
        )
    except ValueError as exc:
        assert "forbidden fields" in str(exc)
    else:
        raise AssertionError("Expected forbidden suggestion field to fail")


def test_append_approved_imports_companion_final_links(tmp_path):
    source = tmp_path / "companion_build_links_final.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    _write_json(source, [
        {
            "query": "Warframe 同伴 配卡",
            "bvid": "BV1j42oYyEW9",
            "url": "https://www.bilibili.com/video/BV1j42oYyEW9/",
            "title": "新版本同伴配卡推荐，笑面型库娃，铁甲狐，warframe（星际战甲国际服）萌新入门视频_游戏热门视频",
        },
        {
            "query": "Warframe 猎犬 配卡",
            "bvid": "BV1Y5d4YCEfp",
            "url": "https://www.bilibili.com/video/BV1Y5d4YCEfp/",
            "title": "T0异况机械猎犬详细配卡攻略 warframe星际战甲_星际战甲_攻略",
        },
        {
            "query": "Warframe 恐鸟 配卡",
            "bvid": "BV1aYP6zoEwv",
            "url": "https://www.bilibili.com/video/BV1aYP6zoEwv/",
            "title": "星际战甲/Warframe自制恐鸟怎么选恐鸟配件怎么选恐鸟有什么作用#Warframe #warframe星际战甲",
        },
    ])
    _write_json(recommendations, [])

    result = build_outputs(
        source_path=source,
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        append_approved=True,
        today="2026-05-24",
    )

    assert [item["bvid"] for item in result.appended] == ["BV1j42oYyEW9", "BV1Y5d4YCEfp", "BV1aYP6zoEwv"]
    loaded = BilibiliRecommendationStore(recommendations).load()
    assert all(record.category == "companion" for record in loaded)
    assert all(record.needs_review is False for record in loaded)
    assert all(record.companions for record in loaded)
    service = BilibiliRecommendationService(BilibiliRecommendationStore(recommendations))
    assert service.recommend("铁甲狐配卡")[0].video.bvid == "BV1j42oYyEW9"
    assert service.recommend("机械猎犬攻略")[0].video.bvid == "BV1Y5d4YCEfp"
    assert service.recommend("恐鸟配卡视频")[0].video.bvid == "BV1aYP6zoEwv"


def test_companion_import_prefers_specific_recent_guides_over_collections(tmp_path):
    source = tmp_path / "companion_build_links_final.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    _write_json(source, [
        {
            "query": "Warframe 宠物 配卡",
            "bvid": "BVCOLLECTION",
            "url": "https://www.bilibili.com/video/BVCOLLECTION/",
            "title": "【Warframe/星际战甲】同伴超级大合集！！死亡魔方/鹦鹉螺/蛟龙/机械狗/恐鸟/铁甲狐/5狗2猫！",
        },
        {
            "query": "Warframe 同伴 配卡",
            "bvid": "BVSPECIFIC",
            "url": "https://www.bilibili.com/video/BVSPECIFIC/",
            "title": "铁甲狐最新配卡，伤害拾取辅助，我全都要",
        },
    ])
    _write_json(recommendations, [])

    build_outputs(
        source_path=source,
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        append_approved=True,
        today="2026-05-24",
    )

    matches = BilibiliRecommendationService(BilibiliRecommendationStore(recommendations)).recommend("铁甲狐配卡")

    assert [match.video.bvid for match in matches[:2]] == ["BVSPECIFIC", "BVCOLLECTION"]


def test_companion_import_does_not_give_specific_records_generic_aliases(tmp_path):
    source = tmp_path / "companion_build_links_final.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    _write_json(source, [
        {
            "query": "Warframe 同伴 配卡",
            "bvid": "BVFOX",
            "url": "https://www.bilibili.com/video/BVFOX/",
            "title": "铁甲狐最新配卡，伤害拾取辅助，我全都要",
        },
        {
            "query": "星际战甲 同伴 配卡",
            "bvid": "BVCUBE",
            "url": "https://www.bilibili.com/video/BVCUBE/",
            "title": "死亡魔方冰淞prime详细配卡攻略 星际战甲",
        },
    ])
    _write_json(recommendations, [])

    build_outputs(
        source_path=source,
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        append_approved=True,
        today="2026-05-24",
    )

    records = {record.bvid: record for record in BilibiliRecommendationStore(recommendations).load()}
    assert "同伴配卡" not in records["BVFOX"].aliases
    assert "宠物攻略" not in records["BVFOX"].aliases
    matches = BilibiliRecommendationService(BilibiliRecommendationStore(recommendations)).recommend("死亡魔方同伴配卡")
    assert [match.video.bvid for match in matches[:2]] == ["BVCUBE"]


def test_append_approved_imports_warframe_final_links(tmp_path):
    source = tmp_path / "warframe_build_links_final.json"
    recommendations = tmp_path / "recommendations.json"
    report = tmp_path / "report.json"
    candidates = tmp_path / "candidates.json"
    _write_json(source, [
        {
            "query": "Warframe 伏特 配卡",
            "bvid": "BVVOLT2025",
            "url": "https://www.bilibili.com/video/BVVOLT2025/",
            "title": "【星际战甲】2025伏特Volt最新配卡攻略，日常/速刷/圣殿",
        },
        {
            "query": "星际战甲 Mesa 配卡",
            "bvid": "BVMESA0001",
            "url": "https://www.bilibili.com/video/BVMESA0001/",
            "title": "Mesa弥撒女枪详细配卡攻略 星际战甲",
        },
        {
            "query": "星际战甲 狼甲 配卡",
            "bvid": "BVVORUNA01",
            "url": "https://www.bilibili.com/video/BVVORUNA01/",
            "title": "狼甲Voruna日常钢铁配卡攻略 星际战甲",
        },
    ])
    _write_json(recommendations, [])

    result = build_outputs(
        source_path=source,
        recommendations_path=recommendations,
        report_path=report,
        candidates_path=candidates,
        append_approved=True,
        today="2026-05-24",
    )

    assert [item["bvid"] for item in result.appended] == ["BVVOLT2025", "BVMESA0001", "BVVORUNA01"]
    loaded = BilibiliRecommendationStore(recommendations).load()
    assert all(record.category == "warframe" for record in loaded)
    assert all(record.needs_review is False for record in loaded)
    records = {record.bvid: record for record in loaded}
    assert records["BVVOLT2025"].warframes == ["Volt"]
    assert "伏特配卡" in records["BVVOLT2025"].aliases
    assert "电男攻略" in records["BVVOLT2025"].aliases
    assert "Volt build" in records["BVVOLT2025"].aliases
    assert records["BVVOLT2025"].priority > records["BVMESA0001"].priority
    assert records["BVVORUNA01"].warframes == ["Voruna"]
    assert "狼甲配卡" in records["BVVORUNA01"].aliases
    assert "Voruna build" in records["BVVORUNA01"].aliases
    service = BilibiliRecommendationService(BilibiliRecommendationStore(recommendations))
    assert service.recommend("伏特配卡")[0].video.bvid == "BVVOLT2025"
    assert service.recommend("电男攻略视频")[0].video.bvid == "BVVOLT2025"
    assert service.recommend("狼甲配卡")[0].video.bvid == "BVVORUNA01"
