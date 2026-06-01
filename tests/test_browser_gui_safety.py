from __future__ import annotations

import json


def test_browser_gui_policy_classifies_read_only_public_actions():
    from warframe_agent.browser_gui_safety import classify_browser_gui_action

    decision = classify_browser_gui_action(
        "read_page",
        target_url="https://warframe.market/items/arcane_energize",
    )

    assert decision["decision"] == "allow_read_only"
    assert decision["requires_human_confirmation"] is False
    assert decision["blocked"] is False
    assert decision["target_scope"] == "public_warframe_market"


def test_browser_gui_policy_requires_confirmation_for_mutating_ui_actions():
    from warframe_agent.browser_gui_safety import classify_browser_gui_action

    decision = classify_browser_gui_action(
        "type_text",
        target_url="https://wiki.warframe.com",
        text="hello",
    )

    assert decision["decision"] == "requires_human_confirmation"
    assert decision["requires_human_confirmation"] is True
    assert decision["blocked"] is False


def test_browser_gui_policy_blocks_trade_private_and_credential_actions():
    from warframe_agent.browser_gui_safety import classify_browser_gui_action

    for action in ["login", "send_whisper", "place_order", "payment", "delete", "credential_entry"]:
        decision = classify_browser_gui_action(action, target_url="https://warframe.market/profile/SecretSeller")
        assert decision["decision"] == "blocked"
        assert decision["blocked"] is True
        assert decision["requires_human_confirmation"] is True


def test_browser_gui_policy_blocks_private_network_targets_and_redacts_sensitive_text():
    from warframe_agent.browser_gui_safety import classify_browser_gui_action

    decision = classify_browser_gui_action(
        "read_page",
        target_url="http://127.0.0.1:3000/admin?token=secret-token",
        text="/w SecretSeller hi Authorization: Bearer abc",
    )

    serialized = json.dumps(decision, ensure_ascii=False)
    assert decision["decision"] == "blocked"
    assert decision["target_scope"] == "private_network"
    for forbidden in ["127.0.0.1", "secret-token", "SecretSeller", "/w", "Bearer abc", "token="]:
        assert forbidden not in serialized


def test_browser_gui_policy_snapshot_is_aggregate_only():
    from warframe_agent.browser_gui_safety import build_browser_gui_safety_policy

    policy = build_browser_gui_safety_policy()

    assert policy["default_mode"] == "read_only"
    assert policy["automation_enabled"] is False
    assert policy["human_takeover_required"] is True
    assert "allow_read_only" in policy["decision_counts"]
    assert "requires_human_confirmation" in policy["decision_counts"]
    assert "blocked" in policy["decision_counts"]
    serialized = json.dumps(policy, ensure_ascii=False)
    for forbidden in ["SecretSeller", "token=", "raw_arguments", "profile/"]:
        assert forbidden not in serialized
