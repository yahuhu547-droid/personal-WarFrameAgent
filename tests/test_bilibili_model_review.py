import json

from tools.review_bilibili_recommendations_with_models import (
    ModelVote,
    build_consensus,
    merge_suggestions,
    parse_model_vote,
    review_candidates,
)
from warframe_agent.model_orchestrator import ModelOrchestrator


def test_parse_model_vote_accepts_json_only_response():
    vote = parse_model_vote(
        json.dumps({
            "bvid": "BV1",
            "category": "primary",
            "weapons": ["托里德"],
            "aliases": ["托里德配卡", "托里德攻略"],
            "confidence": 0.9,
            "reject_reason": "",
        }, ensure_ascii=False),
        reviewer="title",
        expected_bvid="BV1",
    )

    assert vote.error == ""
    assert vote.category == "primary"
    assert vote.weapons == ["托里德"]
    assert vote.confidence == 0.9


def test_parse_model_vote_rejects_non_json_and_forbidden_fields():
    non_json = parse_model_vote("```json\n{}\n```", reviewer="title", expected_bvid="BV1")
    forbidden = parse_model_vote(
        json.dumps({"bvid": "BV1", "category": "primary", "weapons": ["托里德"], "mods": ["膛线"]}, ensure_ascii=False),
        reviewer="title",
        expected_bvid="BV1",
    )

    assert non_json.error == "response_not_json_object"
    assert forbidden.error == "forbidden_fields:mods"


def test_consensus_requires_two_matching_votes_and_defaults_unapproved():
    candidate = {"bvid": "BV1", "title": "托里德-新版配卡", "title_subject": "托里德", "collection_category": "primary"}
    votes = [
        ModelVote(reviewer="a", category="primary", weapons=["托里德"], aliases=["托里德配卡"], confidence=0.9),
        ModelVote(reviewer="b", category="primary", weapons=["托里德"], aliases=["托里德攻略"], confidence=0.8),
        ModelVote(reviewer="c", category="primary", weapons=["舍杜"], confidence=0.9),
    ]

    result = build_consensus(candidate, votes)

    assert result["consensus_status"] == "suggested_approved"
    assert result["consensus_reason"] == "two_of_three_model_consensus"
    assert result["weapons"] == ["托里德"]
    assert result["approved"] is False


def test_consensus_trusts_collection_category_and_rejects_unclear_title_subject():
    trusted_category = build_consensus(
        {"bvid": "BV1", "title": "托里德-主手合集", "title_subject": "托里德", "collection_category": "melee"},
        [
            ModelVote(reviewer="a", category="primary", weapons=["托里德"], confidence=0.9),
            ModelVote(reviewer="b", category="primary", weapons=["托里德"], confidence=0.8),
        ],
    )
    unclear = build_consensus(
        {"bvid": "BV2", "title": "版本速览", "title_subject": "版本速览", "collection_category": "primary"},
        [
            ModelVote(reviewer="a", category="primary", weapons=["托里德"], confidence=0.9),
            ModelVote(reviewer="b", category="primary", weapons=["托里德"], confidence=0.8),
        ],
    )

    assert trusted_category["consensus_status"] == "suggested_approved"
    assert trusted_category["category"] == "melee"
    assert trusted_category["collection_category"] == "melee"
    assert unclear["consensus_status"] == "needs_human_review"
    assert unclear["consensus_reason"] == "weapon_not_derivable_from_title_subject"


def test_review_candidates_uses_orchestrator_and_generates_suggestions():
    responses = [
        json.dumps({"bvid": "BV1", "category": "primary", "weapons": ["托里德"], "aliases": ["托里德配卡"], "confidence": 0.9, "reject_reason": ""}, ensure_ascii=False),
        json.dumps({"bvid": "BV1", "category": "primary", "weapons": ["托里德"], "aliases": ["托里德攻略"], "confidence": 0.8, "reject_reason": ""}, ensure_ascii=False),
        json.dumps({"bvid": "BV1", "category": "primary", "weapons": ["舍杜"], "aliases": ["舍杜配卡"], "confidence": 0.7, "reject_reason": ""}, ensure_ascii=False),
    ]

    def factory():
        def cloud_call(messages, model):
            return responses.pop(0)

        return ModelOrchestrator(
            cloud_call=cloud_call,
            local_call=lambda messages: "{}",
            scout_models={"bilibili_title_review": "m1", "bilibili_category_review": "m2", "bilibili_alias_review": "m3"},
            routing="cloud",
            cloud_api_key="key",
        )

    result = review_candidates(
        {"groups": {"primary": [{"bvid": "BV1", "title": "托里德-新版配卡", "title_subject": "托里德", "collection_category": "primary"}]}},
        orchestrator_factory=factory,
    )

    assert result["suggestion_count"] == 1
    assert result["suggestions"][0]["consensus_status"] == "suggested_approved"
    assert result["suggestions"][0]["approved"] is False


def test_review_candidates_supports_offset_and_merge_preserves_approved_flag():
    def factory():
        response = json.dumps({"bvid": "BV2", "category": "primary", "weapons": ["舍杜"], "aliases": [], "confidence": 0.9, "reject_reason": ""}, ensure_ascii=False)
        return ModelOrchestrator(
            cloud_call=lambda messages, model: response,
            local_call=lambda messages: "{}",
            scout_models={"bilibili_title_review": "m1", "bilibili_category_review": "m2", "bilibili_alias_review": "m3"},
            routing="cloud",
            cloud_api_key="key",
        )

    batch = review_candidates(
        {"groups": {"primary": [
            {"bvid": "BV1", "title": "托里德-新版配卡", "title_subject": "托里德", "collection_category": "primary"},
            {"bvid": "BV2", "title": "舍杜，挂机必备！", "title_subject": "舍杜", "collection_category": "primary"},
        ]}},
        orchestrator_factory=factory,
        offset=1,
        limit=1,
    )
    merged = merge_suggestions(
        {"suggestions": [{"bvid": "BV2", "approved": True, "old": True}]},
        batch,
    )

    assert [item["bvid"] for item in batch["suggestions"]] == ["BV2"]
    assert merged["suggestion_count"] == 1
    assert merged["suggestions"][0]["approved"] is True
