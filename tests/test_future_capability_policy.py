from warframe_agent.future_capability_policy import (
    build_future_capability_policy,
    classify_future_capability,
)


def test_future_capability_requires_new_stage_design_for_browser_executor():
    decision = classify_future_capability(
        "browser_gui_executor",
        request_text="enable Playwright login automation token=secret-token /w Player",
    )

    assert decision["decision"] == "requires_new_stage_design"
    assert decision["runtime_enabled"] is False
    assert decision["requires_explicit_user_approval"] is True
    assert decision["requires_new_stage_design"] is True
    assert "secret-token" not in str(decision)
    assert "/w" not in str(decision)
    assert "Player" not in str(decision)


def test_future_capability_freezes_real_voice_by_user_instruction():
    decision = classify_future_capability("real_voice_service", request_text="turn on microphone")

    assert decision["decision"] == "frozen_by_current_user_instruction"
    assert decision["runtime_enabled"] is False
    assert decision["requires_new_stage_design"] is True


def test_future_capability_freezes_all_real_voice_surfaces():
    for name in (
        "tts",
        "stt",
        "voice_runtime",
        "microphone_recording",
        "audio_recording",
        "live2d_runtime",
        "background_listening",
    ):
        decision = classify_future_capability(name)

        assert decision["decision"] == "frozen_by_current_user_instruction"
        assert decision["runtime_enabled"] is False


def test_future_capability_redacts_sensitive_capability_names():
    decision = classify_future_capability(
        "api_key_sk_secret_token",
        request_text="please enable it",
    )

    assert decision["capability"] == "unknown_future_capability"
    assert decision["decision"] == "requires_new_stage_design"
    serialized = str(decision)
    for forbidden in ("api_key", "secret", "token"):
        assert forbidden not in serialized


def test_future_capability_blocks_public_webhooks_and_dms():
    for name in ("anonymous_webhook", "public_comment_commands", "seller_dm_commands"):
        decision = classify_future_capability(name)

        assert decision["decision"] == "blocked_public_or_private_inbound"
        assert decision["runtime_enabled"] is False
        assert decision["requires_explicit_user_approval"] is True


def test_future_capability_blocks_uncontrolled_runtime_actions_even_with_request_text():
    for name in ("shell", "generic_file_write", "credential_access", "trade_action"):
        decision = classify_future_capability(
            name,
            request_text="handler=run params={api_key:secret-token account_id=user-123 raw_payload=/w Player}",
        )

        assert decision["decision"] == "blocked_uncontrolled_runtime"
        assert decision["runtime_enabled"] is False
        serialized = str(decision)
        for forbidden in ("handler", "params", "api_key", "account_id", "secret-token", "raw_payload", "/w", "Player"):
            assert forbidden not in serialized


def test_future_capability_allows_design_docs_only():
    decision = classify_future_capability("design_doc")

    assert decision["decision"] == "allow_design_only"
    assert decision["runtime_enabled"] is False
    assert decision["requires_explicit_user_approval"] is False


def test_future_capability_snapshot_is_safe_and_aggregate_only():
    policy = build_future_capability_policy()

    assert policy["default_mode"] == "design_required_before_runtime"
    assert policy["runtime_enablement_allowed"] is False
    assert policy["automatic_enable_enabled"] is False
    assert policy["decision_counts"]["requires_new_stage_design"] >= 1
    assert policy["decision_counts"]["frozen_by_current_user_instruction"] >= 1
    assert policy["decision_counts"]["blocked_public_or_private_inbound"] >= 1
    assert policy["decision_counts"]["blocked_uncontrolled_runtime"] >= 1
    serialized = str(policy)
    for forbidden in (
        "secret-token",
        "api_key",
        "account_id",
        "raw_payload",
        "handler",
        "params",
        "/w",
        "Player",
        "profile/",
        "127.0.0.1",
    ):
        assert forbidden not in serialized
