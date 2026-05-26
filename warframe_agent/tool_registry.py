from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    required: tuple[str, ...] = ()
    handler: Callable[[dict[str, Any]], str | ToolResult | None] | None = None
    expose_schema: bool = True
    skill: str = "general"
    safety_level: str = "read_only"
    side_effect: bool = False
    tags: tuple[str, ...] = ()
    context_policy: str = "default"


@dataclass(frozen=True)
class ToolExecutionMetadata:
    tool_name: str
    args_summary: dict[str, Any]
    ok: bool
    error: str | None
    duration_ms: float
    timestamp: str
    message_context: str | None = None


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str | None = None
    error: str | None = None
    metadata: ToolExecutionMetadata | None = None
    display_content: str | None = None
    model_context: str | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"工具已注册: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def get_tool(self, name: str) -> ToolSpec | None:
        return self.get(name)

    def names(self) -> set[str]:
        return set(self._tools)

    @property
    def tool_map(self) -> Mapping[str, ToolSpec]:
        return MappingProxyType(self._tools)

    def with_handler(self, name: str, handler: Callable[[dict[str, Any]], str | ToolResult | None]) -> None:
        spec = self.get(name)
        if not spec:
            raise KeyError(f"未知工具: {name}")
        self._tools[name] = replace(spec, handler=handler)

    def list_tools(self, names: set[str] | None = None, skill: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": {key: _parameter_description(value) for key, value in spec.parameters.items()},
            }
            for spec in self._filtered_specs(names=names, skill=skill)
        ]

    def list_tool_schemas(self, names: set[str] | None = None, skill: str | None = None) -> list[dict[str, Any]]:
        schemas = []
        for spec in self._filtered_specs(names=names, skill=skill):
            if not spec.expose_schema:
                continue
            schema = {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": {
                        "type": "object",
                        "properties": spec.parameters,
                    },
                },
            }
            if spec.required:
                schema["function"]["parameters"]["required"] = list(spec.required)
            schemas.append(schema)
        return schemas

    def to_params(self, names: set[str] | None = None, skill: str | None = None) -> list[dict[str, Any]]:
        return self.list_tool_schemas(names=names, skill=skill)

    def candidate_names(self, skill: str | None = None, include_side_effects: bool = False) -> set[str]:
        return {
            spec.name
            for spec in self._filtered_specs(skill=skill)
            if spec.expose_schema and (include_side_effects or not spec.side_effect)
        }

    def _filtered_specs(self, names: set[str] | None = None, skill: str | None = None) -> list[ToolSpec]:
        specs = list(self._tools.values())
        if names is not None:
            specs = [spec for spec in specs if spec.name in names]
        if skill is not None:
            specs = [spec for spec in specs if spec.skill == skill]
        return specs

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        tool_input: dict[str, Any] | None = None,
    ) -> ToolResult:
        if arguments is not None and tool_input is not None:
            raise TypeError("Pass either arguments or tool_input, not both")
        arguments = dict(arguments if arguments is not None else (tool_input or {}))
        started = time.perf_counter()
        spec = self.get(name)
        if not spec:
            error = f"未知工具: {name}"
            return ToolResult(ok=False, error=error, metadata=_build_metadata(name, arguments, False, error, started))
        missing = [key for key in spec.required if key not in arguments or arguments.get(key) in (None, "")]
        if missing:
            error = f"缺少参数: {', '.join(missing)}"
            return ToolResult(ok=False, error=error, metadata=_build_metadata(name, arguments, False, error, started))
        if not spec.handler:
            error = f"工具未绑定处理器: {name}"
            return ToolResult(ok=False, error=error, metadata=_build_metadata(name, arguments, False, error, started))
        try:
            output = spec.handler(arguments)
            return _coerce_handler_output_to_tool_result(name, output, arguments, started)
        except Exception as exc:
            logger.debug("工具执行失败 %s: %s", name, exc)
            error = f"工具执行失败: {name}"
            return ToolResult(ok=False, error=error, metadata=_build_metadata(name, arguments, False, error, started))


def _coerce_handler_output_to_tool_result(
    tool_name: str,
    output: str | ToolResult | None,
    arguments: dict[str, Any],
    started: float,
) -> ToolResult:
    from .tool_context import compress_tool_result_for_model

    if isinstance(output, ToolResult):
        content = output.content
        display_content = output.display_content if output.display_content is not None else content
        model_source = display_content if content is None else content
        model_context = output.model_context
        if model_context is None and output.ok:
            model_context = compress_tool_result_for_model(tool_name, model_source or "")
        metadata = output.metadata or _build_metadata(tool_name, arguments, output.ok, output.error, started)
        return ToolResult(
            ok=output.ok,
            content=content,
            error=output.error,
            metadata=metadata,
            display_content=display_content if output.ok else None,
            model_context=model_context if output.ok else None,
        )
    if output is None:
        error = f"工具无结果: {tool_name}"
        return ToolResult(
            ok=False,
            error=error,
            metadata=_build_metadata(tool_name, arguments, False, error, started),
        )
    metadata = _build_metadata(tool_name, arguments, True, None, started)
    return ToolResult(
        ok=True,
        content=output,
        metadata=metadata,
        display_content=output,
        model_context=compress_tool_result_for_model(tool_name, output or ""),
    )



def _build_metadata(
    tool_name: str,
    arguments: dict[str, Any],
    ok: bool,
    error: str | None,
    started: float,
) -> ToolExecutionMetadata:
    return ToolExecutionMetadata(
        tool_name=tool_name,
        args_summary=_summarize_arguments(arguments),
        ok=ok,
        error=error,
        duration_ms=max(0.0, (time.perf_counter() - started) * 1000),
        timestamp=datetime.now(timezone.utc).isoformat(),
        message_context=arguments.get("__message"),
    )


def _summarize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    summary = {}
    for key, value in arguments.items():
        if key == "__message":
            continue
        if _is_sensitive_key(key):
            summary[key] = "[REDACTED]"
        else:
            summary[key] = _summarize_value(value)
    return summary


def _summarize_value(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) > 120:
            return f"{value[:80]}... [len={len(value)}]"
        return value
    if isinstance(value, list):
        if len(value) > 10:
            return {"type": "list", "length": len(value), "preview": value[:5]}
        return [_summarize_value(item) for item in value]
    if isinstance(value, tuple):
        return _summarize_value(list(value))
    if isinstance(value, dict):
        items = list(value.items())
        limited = items[:10]
        result = {key: ("[REDACTED]" if _is_sensitive_key(str(key)) else _summarize_value(val)) for key, val in limited}
        if len(items) > 10:
            result["__truncated__"] = len(items) - 10
        return result
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ("password", "token", "secret", "api_key", "apikey", "authorization", "cookie"))


def _parameter_description(value: Any) -> str:
    if isinstance(value, dict):
        description = value.get("description")
        if description:
            return str(description)
    return str(value)


def _param(param_type: str, description: str) -> dict[str, str]:
    return {"type": param_type, "description": description}


def create_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="query_price",
        description="查询单个物品的实时市场价格（卖价、收价、价差）",
        parameters={"item_name": _param("string", "物品名称（中文、英文或 market_id）")},
        required=("item_name",),
        skill="market_price",
    ))
    registry.register(ToolSpec(
        name="query_set",
        description="查询 Prime 套装价格，对比整套购买 vs 拆件购买",
        parameters={"warframe_name": _param("string", "战甲或武器名称")},
        required=("warframe_name",),
        skill="prime_set",
    ))
    registry.register(ToolSpec(
        name="query_missing_parts",
        description="计算补齐 Prime 套装还需要多少钱",
        parameters={
            "warframe_name": _param("string", "战甲或武器名称"),
            "owned_parts": _param("string", "已有部件列表"),
        },
        required=("warframe_name",),
        skill="prime_set",
    ))
    registry.register(ToolSpec(
        name="scan_favorites",
        description="扫描关注物品和价格提醒的当前状态",
        parameters={},
        skill="monitoring",
    ))
    registry.register(ToolSpec(
        name="set_alert",
        description="设置价格提醒，当物品价格达到阈值时通知",
        parameters={
            "item_name": _param("string", "物品名称"),
            "direction": _param("string", "below 或 above"),
            "price": _param("integer", "目标价格"),
        },
        required=("item_name", "direction", "price"),
        skill="monitoring",
        safety_level="local_state_write",
    ))
    registry.register(ToolSpec(
        name="price_trend",
        description="查看物品的价格历史趋势",
        parameters={"item_name": _param("string", "物品名称")},
        required=("item_name",),
        skill="market_price",
    ))
    registry.register(ToolSpec(
        name="general_chat",
        description="一般性 Warframe 交易问题或闲聊，不需要调用特定工具",
        parameters={"message": _param("string", "用户消息")},
        expose_schema=False,
        skill="general",
        safety_level="model_only",
    ))
    registry.register(ToolSpec(
        name="mod_flipper",
        description="扫描 Mod 翻转利润，按每千内融利润排序",
        parameters={
            "min_profit": _param("integer", "最低利润"),
            "limit": _param("integer", "结果数量"),
        },
        skill="trading_analysis",
    ))
    registry.register(ToolSpec(
        name="set_profit",
        description="分析 Prime 套装利润，按利润排序",
        parameters={
            "min_profit": _param("integer", "最低利润"),
            "limit": _param("integer", "结果数量"),
        },
        skill="prime_set",
    ))
    registry.register(ToolSpec(
        name="investment_advisor",
        description="投资顾问：按预算和 ROI 扫描翻转机会",
        parameters={
            "budget": _param("integer", "预算"),
            "min_roi": _param("number", "最低ROI%"),
            "limit": _param("integer", "结果数量"),
        },
        skill="trading_analysis",
    ))
    registry.register(ToolSpec(
        name="plan",
        description="将复杂请求分解为多个子任务并按顺序执行",
        parameters={
            "goal": _param("string", "用户目标"),
            "steps": {
                "type": "array",
                "description": "子任务列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": _param("string", "子任务工具名"),
                        "args": {"type": "object", "description": "工具参数"},
                        "purpose": _param("string", "步骤目的"),
                    },
                    "required": ["tool", "args"],
                },
            },
        },
        required=("goal", "steps"),
        skill="planning",
    ))
    registry.register(ToolSpec(
        name="query_events",
        description="查询当前游戏活动和事件（Baro 来访、虚空裂缝、入侵、虚空风暴、Prime 重生等）。可选 type 参数过滤：void_fissure=虚空裂缝, baro_visit=虚空商人, invasion=入侵, void_storm=虚空风暴, prime_resurgence=Prime 重生",
        parameters={"type": _param("string", "事件类型过滤（可选）：void_fissure / baro_visit / invasion / void_storm / prime_resurgence，不传则返回全部")},
        skill="events",
    ))
    registry.register(ToolSpec(
        name="relic_value",
        description="分析指定遗物的奖励价值、期望白金、期望杜卡德和杜卡德效率。当用户问遗物/核桃是否值得开、收益、价值或杜卡德时使用。",
        parameters={
            "relic_name": _param("string", "遗物名称，如 Lith B1 / 古纪 B1"),
            "target_part": _param("string", "目标部件，可选"),
        },
        required=("relic_name",),
        skill="relics",
        context_policy="safe_aggregate_only",
    ))
    registry.register(ToolSpec(
        name="farming_route",
        description="推荐 Prime 部件或遗物的刷取路线。当用户问某部件去哪刷、遗物怎么刷、哪个裂缝适合开某个核桃时使用。",
        parameters={
            "target": _param("string", "Prime 部件、遗物或用户问题中的目标名称"),
        },
        required=("target",),
        skill="relics",
        context_policy="safe_aggregate_only",
    ))
    registry.register(ToolSpec(
        name="deep_analysis",
        description="深度分析单个物品的多维度数据，使用云端大模型推理",
        parameters={"item_name": _param("string", "物品名称")},
        required=("item_name",),
        skill="trading_analysis",
    ))
    for name, description, skill in (
        ("market_expert", "市场专家：基于安全价格/趋势上下文做买卖建议，只做分析不执行交易", "market_price"),
        ("riven_expert", "紫卡专家：基于安全紫卡上下文解释属性、价格和风险", "riven"),
        ("event_expert", "事件专家：基于安全活动上下文给出限时活动优先级建议", "events"),
    ):
        registry.register(ToolSpec(
            name=name,
            description=description,
            parameters={
                "question": _param("string", "用户问题"),
                "context": _param("string", "已净化或可作为外部数据包裹的上下文"),
            },
            required=("question", "context"),
            skill=skill,
            safety_level="model_only",
        ))
    registry.register(ToolSpec(
        name="riven_search",
        description="搜索紫卡(Riven)拍卖信息。当用户提到紫卡、裂罅、Riven时使用。支持指定正属性、负属性、价格上限。",
        parameters={
            "weapon": _param("string", "武器名称"),
            "positive": _param("string", "期望正属性(如双爆)"),
            "negative": _param("string", "期望负属性(如无负)"),
            "max_price": _param("integer", "最高价格"),
        },
        required=("weapon",),
        skill="riven",
    ))
    return registry
