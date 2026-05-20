from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from . import config
from .tool_context import format_plan_results_for_model, tool_result_model_context
from .tool_registry import create_default_tool_registry


_DEFAULT_REGISTRY = create_default_tool_registry()
TOOL_SCHEMAS = _DEFAULT_REGISTRY.list_tool_schemas()
TOOLS = _DEFAULT_REGISTRY.list_tools()
CORE_READ_ONLY_TOOLS = {"query_price", "price_trend", "query_set", "query_events", "riven_search", "relic_value", "farming_route"}
MAX_CANDIDATE_TOOLS = 6


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class PlanStep:
    tool: str
    arguments: dict[str, Any]
    purpose: str = ""


@dataclass(frozen=True)
class ExecutionPlan:
    goal: str
    steps: list[PlanStep]


def _parse_plan(tc: ToolCall) -> ExecutionPlan | None:
    """从 ToolCall 参数中解析 ExecutionPlan。"""
    args = tc.arguments
    goal = args.get("goal", "")
    raw_steps = args.get("steps", [])
    if not goal or not raw_steps:
        return None
    steps = []
    for s in raw_steps:
        if not isinstance(s, dict) or "tool" not in s:
            continue
        steps.append(PlanStep(
            tool=s["tool"],
            arguments=s.get("args", {}),
            purpose=s.get("purpose", ""),
        ))
    return ExecutionPlan(goal=goal, steps=steps) if steps else None


def _format_plan_results(goal: str, results: list[tuple[PlanStep, Any]]) -> str:
    """将所有步骤结果格式化为 LLM 可推理的聚合文本。"""
    return format_plan_results_for_model(goal, results)


def execute_plan(
    plan: ExecutionPlan,
    tool_executor: Callable[[ToolCall], Any],
) -> list[tuple[PlanStep, Any]]:
    """顺序执行 plan 的每一步，收集 (step, result) 对。"""
    results = []
    for step in plan.steps:
        tc = ToolCall(name=step.tool, arguments=step.arguments)
        result = tool_executor(tc)
        results.append((step, result))
    return results


def select_candidate_tools(message: str, max_tools: int = MAX_CANDIDATE_TOOLS) -> set[str]:
    lowered = message.lower()
    candidates: list[str]
    looks_like_relic_name = bool(re.search(r"\b(lith|meso|neo|axi|requiem)\s+[a-z0-9]+\b", lowered)) or any(token in lowered for token in ("古纪", "前纪", "中纪", "后纪", "遗珍"))
    relic_value_intent = any(token in lowered for token in ("价值", "估值", "收益", "期望", "值不值得", "值得开", "效率", "杜卡特", "杜卡德", "ducat"))
    if any(token in lowered for token in ("紫卡", "裂罅", "riven")):
        candidates = ["riven_search", "riven_expert"]
    elif (looks_like_relic_name or any(token in lowered for token in ("遗物", "核桃", "开核桃"))) and relic_value_intent:
        candidates = ["relic_value", "query_events", "event_expert"]
    elif any(token in lowered for token in ("去哪刷", "哪里刷", "怎么刷", "刷取", "掉落", "来源", "哪个裂缝", "适合开", "开这个核桃")):
        candidates = ["farming_route", "query_events", "relic_value", "event_expert"]
    elif any(token in lowered for token in ("baro", "虚空商人", "奸商", "裂缝", "裂隙", "开核桃", "活动", "入侵", "虚空风暴", "重生", "返厂", "resurgence", "vault", "午夜电波", "电波", "nightwave", "仲裁", "arbitration", "突击", "sortie", "darvo", "每日特惠", "每日优惠", "扎里曼", "zariman", "赏金", "bounty", "平原", "希图斯", "金星", "火卫二", "周期")):
        candidates = ["query_events", "event_expert"]
    elif any(token in lowered for token in ("专家", "分析")):
        candidates = ["market_expert", "query_price", "price_trend", "plan", "query_set", "set_profit"]
    elif any(token in lowered for token in ("对比", "比较", "分别", "多个")):
        candidates = ["plan", "query_price", "price_trend", "market_expert", "query_set", "set_profit"]
    elif any(token in lowered for token in ("投资", "预算", "roi", "倒卖", "翻转", "利润", "赚", "套利")):
        candidates = ["investment_advisor", "mod_flipper", "set_profit", "market_expert", "query_price", "price_trend"]
    elif any(token in lowered for token in ("prime", "套装", "缺", "补齐", "拆件", "整套")):
        candidates = ["query_set", "query_missing_parts", "set_profit", "query_price", "price_trend"]
    elif any(token in lowered for token in ("趋势", "涨", "跌", "历史")):
        candidates = ["price_trend", "query_price", "market_expert"]
    elif any(token in lowered for token in ("扫", "扫描", "收藏", "关注", "提醒")):
        candidates = ["scan_favorites", "set_alert", "query_price", "price_trend"]
    else:
        candidates = ["query_price", "price_trend", "query_set", "query_events", "riven_search"]
    valid = _DEFAULT_REGISTRY.candidate_names()
    return {name for name in candidates[:max_tools] if name in valid}


def build_router_prompt(
    message: str,
    candidate_tools: set[str] | None = None,
    budget_chars: int | None = None,
) -> str:
    tools = _DEFAULT_REGISTRY.list_tools(names=candidate_tools) if candidate_tools is not None else TOOLS
    tools_desc = "\n".join(
        f"- {t['name']}: {t['description']}"
        + (f" (参数: {', '.join(t['parameters'].keys())})" if t['parameters'] else "")
        for t in tools
    )
    prompt = (
        "你是一个工具路由器。根据用户消息，选择最合适的工具并提取参数。\n"
        "只返回一个 JSON 对象，格式: {\"tool\": \"工具名\", \"args\": {参数}}\n"
        "不要返回其他内容，不要解释。\n\n"
        f"可用工具:\n{tools_desc}\n\n"
        f"用户消息: {message}\n"
        "JSON:"
    )
    if budget_chars is not None and len(prompt) > budget_chars:
        suffix = "\nJSON:"
        available = max(0, budget_chars - len(suffix) - 20)
        prompt = f"{prompt[:available]}\n[已裁剪]" + suffix
    return prompt


def parse_tool_call(response: str, valid_names: set[str] | None = None) -> ToolCall | None:
    cleaned = response.strip()
    cleaned = re.sub(r"```json\s*", "", cleaned)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    end = start
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    else:
        return None
    try:
        data = json.loads(cleaned[start:end])
    except json.JSONDecodeError:
        return None
    tool_name = data.get("tool", "")
    allowed_names = valid_names or {t["name"] for t in TOOLS}
    if tool_name not in allowed_names:
        return None
    # 提取参数：优先 args 字段，否则取除 tool 外的所有顶层字段
    args = data.get("args", {})
    if not args:
        args = {k: v for k, v in data.items() if k != "tool"}
    return ToolCall(name=tool_name, arguments=args)


def react_loop(
    message: str,
    tool_executor: Callable[[ToolCall], Any],
    model_call: Callable[[list[dict]], str] | None = None,
    max_iterations: int = config.MAX_TOOL_ITERATIONS,
    model: str = config.REACT_MODEL,
    candidate_tools: set[str] | None = None,
) -> str | None:
    """ReAct 循环：使用 Ollama 原生 tool calling 进行多步推理。

    Args:
        message: 用户消息
        tool_executor: 执行工具调用的函数，接收 ToolCall，返回结果字符串
        model_call: LLM 调用函数，接收 messages 列表，返回响应字符串
        max_iterations: 最大循环轮数
        model: 使用的模型名称

    Returns:
        最终回答字符串，或 None 表示回退到旧路由
    """
    selected_tools = candidate_tools or select_candidate_tools(message)
    if model_call is None:
        tool_schemas = _DEFAULT_REGISTRY.list_tool_schemas(names=selected_tools)
        model_call = lambda messages: _default_model_call(messages, tool_schemas=tool_schemas)

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "你是 Warframe 交易助手的工具路由器。根据用户消息选择最合适的工具。\n\n"
                "## 决策规则\n"
                "1. 用户问单个物品价格 → query_price\n"
                "2. 用户问 Prime 套装、整套vs拆件 → query_set\n"
                "3. 用户说\"还差/缺/补齐\"某套装 → query_missing_parts\n"
                "4. 用户问 Mod 翻转/升级赚钱/内融 → mod_flipper\n"
                "5. 用户问套装利润/拆件赚差价 → set_profit\n"
                "6. 用户问投资/预算/ROI → investment_advisor\n"
                "7. 用户问游戏活动/Baro/警报/Prime 重生 → query_events\n"
                "   - 用户问虚空裂缝/裂隙/开核桃 → query_events(type='void_fissure')\n"
                "   - 用户问遗物/核桃价值、收益、期望、杜卡德效率或值不值得开 → relic_value\n"
                "   - 用户问某 Prime 部件去哪刷、某遗物怎么刷、哪个裂缝适合开某核桃 → farming_route\n"
                "   - 用户问Baro/虚空商人/奸商 → query_events(type='baro_visit')\n"
                "   - 用户问Prime 重生/返厂/resurgence/下一期是谁 → query_events(type='prime_resurgence')\n"
                "   - 用户问午夜电波/仲裁/突击/Darvo/每日特惠/赏金/扎里曼但数据源缺字段 → query_events 并说明暂不支持，不要编造\n"
                "   - 用户问平原/希图斯/金星/火卫二周期 → query_events 或确定性周期状态\n"
                "8. 用户要对比多个物品或复杂分析 → plan（分解子任务）\n"
                "9. 用户问价格趋势/涨跌 → price_trend\n"
                "10. 用户问紫卡/裂罅/Riven → riven_search\n"
                "    - 如\"斯特朗双爆紫卡无负\" → riven_search(weapon='斯特朗', positive='双爆', negative='无负')\n"
                "    - 如\"rubico紫卡暴击率\" → riven_search(weapon='rubico', positive='暴击率')\n"
                "11. 一般闲聊或无法确定 → 直接回答，不调用工具\n\n"
                "## 注意事项\n"
                "- 中文别名需映射到英文（如\"电男\"=\"volt\"）再调用工具\n"
                "- 用户同时提到多个物品时，使用 plan 工具分别查询\n"
                "- 不确定用哪个工具时，直接回答让主模型处理\n"
                "- query_events 的结果只展示事件信息，不要混入交易数据、私聊命令或价格信息\n"
                "- 只用用户明确要求交易相关内容时才使用 query_price 等工具\n\n"
                "## 工具结果处理\n"
                "- 收到工具返回结果后，直接基于结果生成最终回答，不要再次调用工具\n"
                "- 用中文组织回答，简洁明了\n"
                "- 基于工具结果保留关键事实回答；工具上下文可能已压缩，不要编造被省略的细节"
            ),
        },
        {"role": "user", "content": message},
    ]

    for _ in range(max_iterations):
        try:
            response = model_call(messages)
        except Exception:
            return None

        # 检查是否有 tool_calls
        tool_calls = _extract_tool_calls(response, valid_names=selected_tools)
        if not tool_calls:
            if _looks_like_tool_call_response(response):
                return None
            return response.strip() if response.strip() else None

        # 检查是否有 plan 调用 — 优先处理
        plan_calls = [tc for tc in tool_calls if tc.name == "plan"]
        if plan_calls:
            plan = _parse_plan(plan_calls[0])
            if plan:
                step_results = execute_plan(plan, tool_executor)
                aggregated = _format_plan_results(plan.goal, step_results)
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "tool", "content": aggregated})
                continue  # 让 LLM 从聚合结果中生成最终回答

        # 执行普通工具调用并回传结果
        messages.append({"role": "assistant", "content": response})
        for tc in tool_calls:
            result = tool_executor(tc)
            messages.append({
                "role": "tool",
                "content": tool_result_model_context(tc.name, result, fallback=f"工具 {tc.name} 执行失败或无结果"),
            })

    return None


def _looks_like_tool_call_response(response: str) -> bool:
    cleaned = response.strip()
    cleaned = re.sub(r"```json\s*", "", cleaned)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
    if not cleaned or not cleaned.startswith(("{", "[")):
        return False
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return False
    if isinstance(data, dict):
        return "tool" in data
    if isinstance(data, list):
        return any(isinstance(item, dict) and "tool" in item for item in data)
    return False


def _extract_tool_calls(response: str, valid_names: set[str] | None = None) -> list[ToolCall]:
    """从 LLM 响应中提取工具调用（支持 JSON 和 function_call 格式）"""
    calls = []
    # 尝试解析 JSON 数组格式
    cleaned = response.strip()
    cleaned = re.sub(r"```json\s*", "", cleaned)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    # 尝试解析 [{"tool": ..., "args": ...}] 格式
    if cleaned.startswith("["):
        try:
            arr = json.loads(cleaned)
            for item in arr:
                if isinstance(item, dict) and "tool" in item:
                    tc = parse_tool_call(json.dumps(item), valid_names=valid_names)
                    if tc:
                        calls.append(tc)
            if calls:
                return calls
        except json.JSONDecodeError:
            pass

    # 尝试单个 {"tool": ..., "args": ...}
    tc = parse_tool_call(cleaned, valid_names=valid_names)
    if tc:
        calls.append(tc)
    return calls


def _default_model_call(messages: list[dict], tool_schemas: list[dict] | None = None) -> str:
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama Python package is not installed") from exc
    response = ollama.chat(model=config.REACT_MODEL, messages=messages, tools=tool_schemas or TOOL_SCHEMAS)
    msg = response.get("message", {})
    content = msg.get("content", "")
    # Ollama 原生 tool calls — 序列化为 JSON 格式供 _extract_tool_calls 解析
    tool_calls = msg.get("tool_calls", [])
    if tool_calls:
        calls_json = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            calls_json.append({
                "tool": fn.get("name", ""),
                "args": fn.get("arguments", {}),
            })
        content += "\n" + json.dumps(calls_json, ensure_ascii=False)
    return content
