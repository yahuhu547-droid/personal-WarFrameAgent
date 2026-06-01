from datetime import datetime

import pytest

from warframe_agent.safety_policy import build_runtime_safety_policy, summarize_tool_registry_safety
from warframe_agent.tool_registry import ToolRegistry, ToolResult, ToolSpec, create_default_tool_registry


def test_register_and_get_tool():
    registry = ToolRegistry()
    spec = ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
    )

    registry.register(spec)

    assert registry.get("query_price") == spec
    assert registry.names() == {"query_price"}


def test_register_rejects_duplicate_names():
    registry = ToolRegistry()
    spec = ToolSpec(name="query_price", description="查询价格", parameters={})

    registry.register(spec)

    with pytest.raises(ValueError):
        registry.register(spec)


def test_list_tools_exports_legacy_router_format():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
    ))

    assert registry.list_tools() == [{
        "name": "query_price",
        "description": "查询价格",
        "parameters": {"item_name": "物品名称"},
    }]


def test_list_tool_schemas_exports_ollama_function_format():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
    ))

    assert registry.list_tool_schemas() == [{
        "type": "function",
        "function": {
            "name": "query_price",
            "description": "查询价格",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "物品名称"},
                },
                "required": ["item_name"],
            },
        },
    }]


def test_to_params_exports_openmanus_function_format():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
    ))

    assert registry.to_params() == registry.list_tool_schemas()


def test_get_tool_and_tool_map_expose_registered_specs_read_only():
    registry = ToolRegistry()
    spec = ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
    )

    registry.register(spec)

    assert registry.get_tool("query_price") is spec
    assert registry.tool_map["query_price"] is spec
    with pytest.raises(TypeError):
        registry.tool_map["other"] = spec


def test_execute_accepts_openmanus_style_tool_input_keyword():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
        handler=lambda args: f"{args['item_name']} 45p",
    ))

    result = registry.execute(name="query_price", tool_input={"item_name": "充沛"})

    assert result.ok is True
    assert result.content == "充沛 45p"


def test_execute_calls_handler_and_wraps_content():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
        handler=lambda args: f"{args['item_name']} 45p",
    ))

    result = registry.execute("query_price", {"item_name": "充沛"})

    assert result.ok is True
    assert result.content == "充沛 45p"
    assert result.error is None


def test_execute_success_populates_display_and_model_context():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        handler=lambda args: "充沛 45p",
    ))

    result = registry.execute("query_price", {"item_name": "充沛"})

    assert result.content == "充沛 45p"
    assert result.display_content == "充沛 45p"
    assert result.model_context == "充沛 45p"


def test_handler_none_is_not_reported_as_success():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="maybe_empty", description="empty", parameters={}))
    registry.with_handler("maybe_empty", lambda args: None)

    result = registry.execute("maybe_empty", {})

    assert result.ok is False
    assert result.error == "工具无结果: maybe_empty"
    assert result.display_content is None
    assert result.model_context is None


def test_execute_model_context_compresses_long_content_without_changing_display():
    long_content = "\n".join([f"raw-line-{i:03d}" for i in range(100)]) + "\nRAW_TAIL_SENTINEL"
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={},
        handler=lambda args: long_content,
    ))

    result = registry.execute("query_price", {})

    assert "RAW_TAIL_SENTINEL" in result.content
    assert "RAW_TAIL_SENTINEL" in result.display_content
    assert "RAW_TAIL_SENTINEL" not in result.model_context
    assert "[工具结果已压缩: tool=query_price" in result.model_context


def test_execute_model_context_redacts_sensitive_content():
    raw_content = "token=secret-token\nAuthorization: Bearer xyz-secret\n最低卖价 45p"
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={},
        handler=lambda args: raw_content,
    ))

    result = registry.execute("query_price", {})

    assert "secret-token" in result.content
    assert "xyz-secret" in result.display_content
    assert "最低卖价 45p" in result.model_context
    assert "[REDACTED]" in result.model_context
    assert "secret-token" not in result.model_context
    assert "xyz-secret" not in result.model_context


def test_execute_failure_does_not_set_display_or_model_context():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
        handler=lambda args: "unused",
    ))

    result = registry.execute("query_price", {})

    assert result.ok is False
    assert result.content is None
    assert result.display_content is None
    assert result.model_context is None


def test_execute_preserves_explicit_tool_result_contexts():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="mod_flipper",
        description="扫描 Mod 翻转利润",
        parameters={},
        handler=lambda args: ToolResult(
            ok=True,
            content="raw markdown",
            display_content="visible markdown",
            model_context="compact domain context",
        ),
    ))

    result = registry.execute("mod_flipper", {})

    assert result.ok is True
    assert result.content == "raw markdown"
    assert result.display_content == "visible markdown"
    assert result.model_context == "compact domain context"
    assert result.metadata.tool_name == "mod_flipper"
    assert result.metadata.ok is True


def test_execute_preserves_explicit_tool_result_failure_metadata():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="mod_flipper",
        description="扫描 Mod 翻转利润",
        parameters={},
        handler=lambda args: ToolResult(ok=False, error="domain failed"),
    ))

    result = registry.execute("mod_flipper", {})

    assert result.ok is False
    assert result.error == "domain failed"
    assert result.metadata.tool_name == "mod_flipper"
    assert result.metadata.ok is False
    assert result.metadata.error == "domain failed"


def test_execute_unknown_tool_returns_failure():
    registry = ToolRegistry()

    result = registry.execute("missing", {})

    assert result.ok is False
    assert result.content is None
    assert "未知工具" in result.error


def test_execute_missing_required_arg_returns_failure():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
        handler=lambda args: "unused",
    ))

    result = registry.execute("query_price", {})

    assert result.ok is False
    assert result.content is None
    assert "缺少参数" in result.error


def test_execute_success_includes_internal_metadata():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
        handler=lambda args: f"{args['item_name']} 45p",
    ))

    result = registry.execute("query_price", {"item_name": "充沛"})

    assert result.ok is True
    assert result.metadata.tool_name == "query_price"
    assert result.metadata.ok is True
    assert result.metadata.error is None
    assert result.metadata.args_summary["item_name"] == "充沛"
    assert result.metadata.duration_ms >= 0
    datetime.fromisoformat(result.metadata.timestamp)


def test_default_registry_excludes_removed_subjective_experts():
    registry = create_default_tool_registry()

    for name in ("build_expert", "guide_expert", "activity_expert"):
        assert registry.get(name) is None


def test_execute_failure_includes_internal_metadata():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
        handler=lambda args: "unused",
    ))

    result = registry.execute("query_price", {})

    assert result.ok is False
    assert result.metadata.tool_name == "query_price"
    assert result.metadata.ok is False
    assert "缺少参数" in result.metadata.error
    assert result.metadata.duration_ms >= 0


def test_execute_unknown_tool_includes_internal_metadata():
    registry = ToolRegistry()

    result = registry.execute("missing", {"item_name": "充沛"})

    assert result.ok is False
    assert result.metadata.tool_name == "missing"
    assert result.metadata.ok is False
    assert "未知工具" in result.metadata.error


def test_execute_handler_exception_includes_internal_metadata():
    def boom(args):
        raise RuntimeError("secret internal detail")

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        required=("item_name",),
        handler=boom,
    ))

    result = registry.execute("query_price", {"item_name": "充沛"})

    assert result.ok is False
    assert result.metadata.tool_name == "query_price"
    assert result.metadata.ok is False
    assert result.metadata.error == result.error
    assert "secret internal detail" not in result.error


def test_execute_metadata_redacts_sensitive_arguments():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        handler=lambda args: "ok",
    ))

    result = registry.execute("query_price", {
        "item_name": "充沛",
        "api_key": "sk-secret",
        "apikey": "sk-secret-2",
        "password": "hunter2",
        "token": "abc",
        "authorization": "Bearer xyz",
        "cookie": "sid=123",
        "client_secret": "hidden",
    })

    summary_text = repr(result.metadata.args_summary)
    assert result.metadata.args_summary["item_name"] == "充沛"
    assert result.metadata.args_summary["api_key"] == "[REDACTED]"
    assert result.metadata.args_summary["apikey"] == "[REDACTED]"
    assert result.metadata.args_summary["password"] == "[REDACTED]"
    assert result.metadata.args_summary["token"] == "[REDACTED]"
    assert result.metadata.args_summary["authorization"] == "[REDACTED]"
    assert result.metadata.args_summary["cookie"] == "[REDACTED]"
    assert result.metadata.args_summary["client_secret"] == "[REDACTED]"
    assert "sk-secret" not in summary_text
    assert "hunter2" not in summary_text
    assert "Bearer xyz" not in summary_text


def test_execute_metadata_summarizes_large_arguments():
    long_value = "x" * 300
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        handler=lambda args: "ok",
    ))

    result = registry.execute("query_price", {"item_name": long_value, "items": list(range(50))})

    assert len(result.metadata.args_summary["item_name"]) < 160
    assert "300" in result.metadata.args_summary["item_name"]
    assert len(repr(result.metadata.args_summary["items"])) < 200


def test_execute_metadata_extracts_message_context_and_hides_internal_arg():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
        handler=lambda args: "ok",
    ))

    result = registry.execute("query_price", {"item_name": "充沛", "__message": "用户问：充沛多少钱"})

    assert result.metadata.message_context == "用户问：充沛多少钱"
    assert "__message" not in result.metadata.args_summary


def test_list_tools_can_filter_by_candidate_names():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
    ))
    registry.register(ToolSpec(
        name="query_events",
        description="查询活动",
        parameters={},
    ))

    tools = registry.list_tools(names={"query_events"})

    assert [tool["name"] for tool in tools] == ["query_events"]


def test_list_tool_schemas_can_filter_by_candidate_names():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={"item_name": {"type": "string", "description": "物品名称"}},
    ))
    registry.register(ToolSpec(
        name="query_events",
        description="查询活动",
        parameters={},
    ))

    schemas = registry.list_tool_schemas(names={"query_price"})

    assert [schema["function"]["name"] for schema in schemas] == ["query_price"]


def test_default_registry_contains_core_tools():
    registry = create_default_tool_registry()

    for name in ("query_price", "mod_flipper", "query_events", "riven_search"):
        assert registry.get(name) is not None


def test_default_registry_contains_expert_tools():
    registry = create_default_tool_registry()

    for name in ("market_expert", "riven_expert", "event_expert"):
        spec = registry.get(name)
        assert spec is not None
        assert "question" in spec.parameters
        assert "context" in spec.parameters


def test_default_tools_have_skill_and_safety_level():
    registry = create_default_tool_registry()

    expected_skills = {
        "query_price": "market_price",
        "query_set": "prime_set",
        "query_missing_parts": "prime_set",
        "scan_favorites": "monitoring",
        "set_alert": "monitoring",
        "price_trend": "market_price",
        "general_chat": "general",
        "mod_flipper": "trading_analysis",
        "set_profit": "prime_set",
        "investment_advisor": "trading_analysis",
        "plan": "planning",
        "query_events": "events",
        "deep_analysis": "trading_analysis",
        "market_expert": "market_price",
        "riven_expert": "riven",
        "event_expert": "events",
        "riven_search": "riven",
    }
    for tool_name, skill in expected_skills.items():
        spec = registry.get(tool_name)
        assert spec is not None
        assert spec.skill == skill
        assert spec.safety_level


def test_default_registry_keeps_general_chat_out_of_function_schemas():
    registry = create_default_tool_registry()

    assert registry.get("general_chat") is not None
    schema_names = {schema["function"]["name"] for schema in registry.list_tool_schemas()}
    assert "general_chat" not in schema_names


def test_external_side_effect_tools_are_not_candidates_by_default():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询价格",
        parameters={},
        safety_level="read_only",
    ))
    registry.register(ToolSpec(
        name="send_push",
        description="发送推送",
        parameters={},
        safety_level="external_side_effect",
        side_effect=True,
    ))

    candidate_names = registry.candidate_names()

    assert "query_price" in candidate_names
    assert "send_push" not in candidate_names


def test_tool_registry_safety_summary_counts_metadata_without_exposing_handlers_or_parameters():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="safe_price",
        description="safe",
        parameters={"secret_param": {"type": "string"}},
        skill="market_price",
        safety_level="read_only",
        context_policy="safe_aggregate_only",
        handler=lambda args: "should not leak",
    ))
    registry.register(ToolSpec(
        name="push_message",
        description="push",
        parameters={},
        skill="monitoring",
        safety_level="external_side_effect",
        side_effect=True,
        expose_schema=False,
    ))

    summary = summarize_tool_registry_safety(registry)

    assert summary["tool_count"] == 2
    assert summary["exposed_schema_count"] == 1
    assert summary["private_schema_count"] == 1
    assert summary["side_effect_count"] == 1
    assert summary["read_only_candidate_count"] == 1
    assert summary["safety_levels"] == {"external_side_effect": 1, "read_only": 1}
    assert summary["skills"] == {"market_price": 1, "monitoring": 1}
    assert summary["context_policies"] == {"default": 1, "safe_aggregate_only": 1}
    serialized = str(summary)
    for forbidden in [
        "handler",
        "should not leak",
        "secret_param",
        "parameters",
        "safe_price",
        "push_message",
        "description",
        "ToolResult",
        "model_context",
        "message_context",
        "hidden",
    ]:
        assert forbidden not in serialized


def test_runtime_safety_policy_embeds_tool_registry_summary_without_tool_details():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="safe_price",
        description="safe",
        parameters={"api_key": {"type": "string"}},
        skill="market_price",
        safety_level="read_only",
        handler=lambda args: "secret result",
    ))

    policy = build_runtime_safety_policy(tool_registry=registry)

    summary = policy["tool_registry"]
    assert summary["tool_count"] == 1
    assert summary["exposed_schema_count"] == 1
    assert summary["private_schema_count"] == 0
    assert summary["safety_levels"] == {"read_only": 1}
    browser_policy = policy["browser_gui_policy"]
    assert browser_policy["default_mode"] == "read_only"
    assert browser_policy["automation_enabled"] is False
    assert browser_policy["human_takeover_required"] is True
    assert browser_policy["decision_counts"]["blocked"] >= 1
    assert "browser_gui_automation" in policy["capabilities"]
    assert policy["capabilities"]["browser_gui_automation"]["default"] == "disabled"
    companion_policy = policy["companion_experience_policy"]
    assert companion_policy["default_mode"] == "text_only"
    assert companion_policy["voice_enabled"] is False
    assert companion_policy["live2d_enabled"] is False
    assert companion_policy["microphone_enabled"] is False
    assert companion_policy["recording_enabled"] is False
    assert companion_policy["background_listening_enabled"] is False
    assert companion_policy["decision_counts"]["blocked_unavailable_runtime"] >= 1
    assert "voice_companion_experience" in policy["capabilities"]
    assert policy["capabilities"]["voice_companion_experience"]["default"] == "disabled"
    gateway_policy = policy["gateway_policy"]
    assert gateway_policy["default_mode"] == "explicit_gateway_only"
    assert gateway_policy["automatic_inbound_execution_enabled"] is False
    assert gateway_policy["anonymous_inbound_enabled"] is False
    assert gateway_policy["decision_counts"]["allow_interactive_chat"] >= 1
    assert gateway_policy["decision_counts"]["blocked_public_or_anonymous_inbound"] >= 1
    assert "multi_channel_gateway" in policy["capabilities"]
    assert policy["capabilities"]["multi_channel_gateway"]["default"] == "restricted"
    plugin_policy = policy["plugin_policy"]
    assert plugin_policy["default_mode"] == "guidance_only"
    assert plugin_policy["plugin_runtime_enabled"] is False
    assert plugin_policy["connector_runtime_enabled"] is False
    assert plugin_policy["automatic_tool_install_enabled"] is False
    assert plugin_policy["decision_counts"]["allow_guidance_only"] >= 1
    assert plugin_policy["decision_counts"]["blocked_high_risk_capability"] >= 1
    assert "skills_plugin_ecosystem" in policy["capabilities"]
    assert policy["capabilities"]["skills_plugin_ecosystem"]["default"] == "guidance_only"
    future_policy = policy["future_capability_policy"]
    assert future_policy["default_mode"] == "design_required_before_runtime"
    assert future_policy["runtime_enablement_allowed"] is False
    assert future_policy["decision_counts"]["requires_new_stage_design"] >= 1
    assert future_policy["decision_counts"]["blocked_uncontrolled_runtime"] >= 1
    assert "future_capability_admission" in policy["capabilities"]
    assert policy["capabilities"]["future_capability_admission"]["default"] == "design_required"
    assert policy["capabilities"]["future_capability_admission"]["enabled"] is False
    assert policy["capabilities"]["future_capability_admission"]["scope"] == "future_high_risk_features_policy_only"
    serialized = str(policy)
    for forbidden in [
        "api_key",
        "safe_price",
        "handler",
        "secret result",
        "parameters",
        "ToolResult",
        "model_context",
        "message_context",
        "127.0.0.1",
        "secret-token",
        "SecretSeller",
        "/w",
        "profile/",
        "raw_message",
        "microphone_path",
        "audio_url",
        "SellerGateway",
        "oc_gateway",
        "raw_payload",
        "account_id",
        "raw_manifest",
        "user-123",
        "raw_payload",
        "handler",
        "params",
        "Player",
    ]:
        assert forbidden not in serialized
