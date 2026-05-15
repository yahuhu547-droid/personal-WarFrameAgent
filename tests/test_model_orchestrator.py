from __future__ import annotations

from warframe_agent.model_orchestrator import ModelOrchestrator, ModelRequest


def test_task_route_uses_configured_scout_model():
    orchestrator = ModelOrchestrator(
        cloud_call=lambda messages, model: f"cloud:{model}",
        local_call=lambda messages: "local",
        scout_models={"mod_flipper": "kimi-k2.6"},
        routing="auto",
        cloud_api_key="key",
    )

    result = orchestrator.chat(ModelRequest(messages=[{"role": "user", "content": "筛选候选"}], task="mod_flipper"))

    assert result.content == "cloud:kimi-k2.6"
    assert result.provider == "cloud"
    assert result.model == "kimi-k2.6"


def test_simple_auto_route_uses_local_model():
    orchestrator = ModelOrchestrator(
        cloud_call=lambda messages, model: "cloud",
        local_call=lambda messages: "local",
        routing="auto",
        cloud_api_key="key",
    )

    result = orchestrator.chat(ModelRequest(messages=[{"role": "user", "content": "你好"}]))

    assert result.content == "local"
    assert result.provider == "local"


def test_complex_auto_route_uses_default_cloud_model():
    orchestrator = ModelOrchestrator(
        cloud_call=lambda messages, model: f"cloud:{model}",
        local_call=lambda messages: "local",
        routing="auto",
        cloud_api_key="key",
        cloud_model="gpt-5.5",
        complexity_threshold=3,
    )

    result = orchestrator.chat(ModelRequest(messages=[{"role": "user", "content": "ROI profit strategy budget analysis"}]))

    assert result.content == "cloud:gpt-5.5"
    assert result.provider == "cloud"


def test_cloud_failure_falls_back_to_local():
    def fail_cloud(messages, model):
        raise TimeoutError("timeout")

    orchestrator = ModelOrchestrator(
        cloud_call=fail_cloud,
        local_call=lambda messages: "local fallback",
        routing="cloud",
        cloud_api_key="key",
    )

    result = orchestrator.chat(ModelRequest(messages=[{"role": "user", "content": "复杂分析"}]))

    assert result.content == "local fallback"
    assert result.provider == "local"
    assert "timeout" in result.fallback_reason


def test_cache_reuses_same_response_for_same_task_and_messages():
    calls = []

    def cloud_call(messages, model):
        calls.append(model)
        return "cached response"

    orchestrator = ModelOrchestrator(
        cloud_call=cloud_call,
        local_call=lambda messages: "local",
        routing="cloud",
        cloud_api_key="key",
        cache_ttl=600,
    )
    request = ModelRequest(messages=[{"role": "user", "content": "分析"}], task="analysis")

    first = orchestrator.chat(request)
    second = orchestrator.chat(request)

    assert first.content == second.content == "cached response"
    assert calls == ["gpt-5.5"]
