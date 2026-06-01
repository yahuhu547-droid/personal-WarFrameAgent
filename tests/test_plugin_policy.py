from warframe_agent.plugin_policy import build_plugin_policy, classify_plugin_capability


def test_plugin_policy_allows_local_skills_as_guidance_only():
    decision = classify_plugin_capability(
        "local_skill",
        capability="prompt_guidance",
        manifest_text="path=C:/Users/secret-token/skill token=abc123",
    )

    assert decision["decision"] == "allow_guidance_only"
    assert decision["blocked"] is False
    assert decision["requires_explicit_enable"] is False
    assert decision["trust_boundary"] == "local_guidance"
    serialized = str(decision)
    assert "secret-token" not in serialized
    assert "abc123" not in serialized
    assert "C:/Users" not in serialized
    assert "[REDACTED]" in serialized


def test_plugin_policy_requires_review_for_personal_plugins():
    decision = classify_plugin_capability(
        "personal_plugin",
        capability="tool_provider",
        installed=True,
        manifest_text="handler=run params={api_key:secret-token}",
    )

    assert decision["decision"] == "requires_review"
    assert decision["blocked"] is False
    assert decision["requires_human_confirmation"] is True
    assert decision["trust_boundary"] == "installed_local_extension"
    serialized = str(decision)
    for forbidden in ["handler", "api_key", "secret-token", "params"]:
        assert forbidden not in serialized


def test_plugin_policy_connectors_require_explicit_enable_and_confirmation():
    decision = classify_plugin_capability(
        "connector",
        capability="account_access",
        installed=True,
        explicit_enable=True,
        manifest_text="account_id=user-123 token=secret-token",
    )

    assert decision["decision"] == "requires_explicit_enable"
    assert decision["blocked"] is False
    assert decision["requires_explicit_enable"] is True
    assert decision["requires_human_confirmation"] is True
    assert decision["trust_boundary"] == "external_account_connector"
    serialized = str(decision)
    for forbidden in ["user-123", "secret-token", "account_id", "token"]:
        assert forbidden not in serialized


def test_plugin_policy_blocks_high_risk_capabilities_even_when_installed():
    for capability in ["shell", "file_write", "browser_control", "scheduler_create", "credential_access"]:
        decision = classify_plugin_capability(
            "personal_plugin",
            capability=capability,
            installed=True,
            explicit_enable=True,
        )

        assert decision["decision"] == "blocked_high_risk_capability"
        assert decision["blocked"] is True
        assert decision["requires_human_confirmation"] is True


def test_plugin_policy_blocks_unknown_or_uninstalled_capabilities():
    unknown = classify_plugin_capability("mystery_plugin", capability="tool_provider")
    uninstalled = classify_plugin_capability("personal_plugin", capability="tool_provider", installed=False)

    assert unknown["decision"] == "blocked_unknown_capability"
    assert unknown["blocked"] is True
    assert uninstalled["decision"] == "blocked_uninstalled_extension"
    assert uninstalled["blocked"] is True


def test_plugin_policy_snapshot_is_safe_and_aggregate_only():
    policy = build_plugin_policy()

    assert policy["default_mode"] == "guidance_only"
    assert policy["plugin_runtime_enabled"] is False
    assert policy["connector_runtime_enabled"] is False
    assert policy["automatic_tool_install_enabled"] is False
    assert policy["decision_counts"]["allow_guidance_only"] >= 1
    assert policy["decision_counts"]["requires_review"] >= 1
    assert policy["decision_counts"]["blocked_high_risk_capability"] >= 1
    serialized = str(policy)
    for forbidden in [
        "secret-token",
        "api_key",
        "account_id",
        "handler",
        "params",
        "raw_manifest",
        "C:/Users",
        "user-123",
    ]:
        assert forbidden not in serialized
