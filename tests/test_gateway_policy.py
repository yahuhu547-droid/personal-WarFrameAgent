from warframe_agent.gateway_policy import build_gateway_policy, classify_gateway_request


def test_gateway_policy_allows_interactive_user_chat_entrypoints():
    for channel in ["web_chat", "websocket_chat", "local_cli"]:
        decision = classify_gateway_request(channel, action="message")

        assert decision["decision"] == "allow_interactive_chat"
        assert decision["blocked"] is False
        assert decision["requires_human_confirmation"] is False
        assert decision["trust_boundary"] == "local_user_interactive"


def test_gateway_policy_external_inbound_uses_existing_confirmation_and_redacts_payload():
    decision = classify_gateway_request(
        "feishu_bot",
        action="message",
        authenticated=True,
        payload_text=(
            "run /w SellerGateway hi token=secret-token "
            "https://warframe.market/profile/SellerGateway chat_id=oc_gateway"
        ),
    )

    assert decision["decision"] == "requires_existing_confirmation_flow"
    assert decision["blocked"] is False
    assert decision["requires_human_confirmation"] is True
    assert decision["trust_boundary"] == "configured_external_inbound"
    serialized = str(decision)
    for forbidden in ["SellerGateway", "secret-token", "profile/", "/w", "oc_gateway", "chat_id"]:
        assert forbidden not in serialized
    assert "[REDACTED]" in serialized


def test_gateway_policy_keeps_push_channels_outbound_only():
    outbound = classify_gateway_request("wxpusher", action="send_notification", authenticated=True)
    inbound = classify_gateway_request("wxpusher", action="message", authenticated=True)

    assert outbound["decision"] == "allow_outbound_notification"
    assert outbound["blocked"] is False
    assert outbound["trust_boundary"] == "configured_outbound_push"
    assert inbound["decision"] == "blocked_outbound_only_channel"
    assert inbound["blocked"] is True
    assert inbound["requires_human_confirmation"] is True


def test_gateway_policy_blocks_public_anonymous_and_high_risk_gateways():
    blocked_cases = [
        ("bilibili_comment", "message", False),
        ("anonymous_webhook", "message", False),
        ("github_issue", "message", False),
        ("seller_dm", "message", True),
        ("web_chat", "execute_tool", True),
        ("websocket_chat", "run_shell", True),
        ("feishu_bot", "browser_control", True),
        ("local_cli", "write_file", True),
    ]

    for channel, action, authenticated in blocked_cases:
        decision = classify_gateway_request(channel, action=action, authenticated=authenticated)

        assert decision["blocked"] is True
        assert decision["requires_human_confirmation"] is True
        assert decision["decision"].startswith("blocked")


def test_gateway_policy_snapshot_is_safe_and_aggregate_only():
    policy = build_gateway_policy()

    assert policy["default_mode"] == "explicit_gateway_only"
    assert policy["automatic_inbound_execution_enabled"] is False
    assert policy["anonymous_inbound_enabled"] is False
    assert policy["outbound_push_requires_configuration"] is True
    assert "web_chat" in policy["interactive_entrypoints"]
    assert "wxpusher" in policy["outbound_notification_channels"]
    assert policy["decision_counts"]["allow_interactive_chat"] >= 1
    assert policy["decision_counts"]["requires_existing_confirmation_flow"] >= 1
    assert policy["decision_counts"]["blocked_public_or_anonymous_inbound"] >= 1
    serialized = str(policy)
    for forbidden in [
        "SellerGateway",
        "secret-token",
        "profile/",
        "/w",
        "oc_gateway",
        "chat_id",
        "app_secret",
        "raw_payload",
        "handler",
    ]:
        assert forbidden not in serialized
