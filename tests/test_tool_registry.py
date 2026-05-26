from datetime import datetime

import pytest

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
