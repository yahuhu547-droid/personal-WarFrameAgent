from __future__ import annotations

import json

from warframe_agent.companion_experience import (
    build_companion_experience_policy,
    classify_companion_experience_request,
)


def test_text_companion_request_is_allowed_without_voice_runtime():
    decision = classify_companion_experience_request("陪我聊聊今天刷图怎么不累")

    assert decision["category"] == "text_companion"
    assert decision["decision"] == "allow_text_only"
    assert decision["blocked"] is False
    assert decision["requires_human_confirmation"] is False
    assert decision["voice_runtime_required"] is False
    assert "text_companion" in decision["safe_tags"]


def test_voice_live2d_recording_requests_are_blocked_until_designed():
    messages = [
        "开麦克风听我说话",
        "给我语音回复",
        "启动 Live2D 桌宠",
        "后台监听我打钢铁中断时说的话",
    ]

    for message in messages:
        decision = classify_companion_experience_request(message)
        assert decision["decision"] == "blocked_unavailable_runtime"
        assert decision["blocked"] is True
        assert decision["requires_human_confirmation"] is True
        assert decision["voice_runtime_required"] is True


def test_background_companion_tasks_require_existing_confirmation_flow():
    decision = classify_companion_experience_request("一边陪我刷图一边后台盯价提醒")

    assert decision["category"] == "background_task_companion"
    assert decision["decision"] == "requires_existing_confirmation_flow"
    assert decision["blocked"] is False
    assert decision["requires_human_confirmation"] is True
    assert decision["reason"] == "background_tasks_use_existing_confirmation"


def test_trade_or_private_message_companion_requests_are_blocked_and_sanitized():
    decision = classify_companion_experience_request(
        "陪我直接私聊卖家并下单 /w SecretSeller hi token=LEAK"
    )

    assert decision["category"] == "trade_action"
    assert decision["decision"] == "blocked_sensitive_action"
    assert decision["blocked"] is True
    serialized = json.dumps(decision, ensure_ascii=False)
    for forbidden in ["SecretSeller", "/w", "token=", "LEAK", "profile/"]:
        assert forbidden not in serialized


def test_warframe_gameplay_companion_is_not_treated_as_voice_companion_ux():
    decision = classify_companion_experience_request("帮我推荐库娃同伴配卡和宠物获取路线")

    assert decision["category"] == "gameplay_companion"
    assert decision["decision"] == "route_general_chat"
    assert decision["blocked"] is False
    assert decision["voice_runtime_required"] is False


def test_companion_policy_snapshot_is_aggregate_only():
    policy = build_companion_experience_policy()

    assert policy["default_mode"] == "text_only"
    assert policy["voice_enabled"] is False
    assert policy["live2d_enabled"] is False
    assert policy["microphone_enabled"] is False
    assert policy["recording_enabled"] is False
    assert policy["background_listening_enabled"] is False
    assert policy["platform_tokens_required"] is False
    assert "allow_text_only" in policy["decision_counts"]
    assert "blocked_unavailable_runtime" in policy["decision_counts"]
    assert "requires_existing_confirmation_flow" in policy["decision_counts"]
    assert "blocked_sensitive_action" in policy["decision_counts"]
    serialized = json.dumps(policy, ensure_ascii=False)
    for forbidden in ["SecretSeller", "/w", "token=", "raw_message", "profile/"]:
        assert forbidden not in serialized
