from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from . import config


# Ollama 原生工具格式（function calling）
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "query_price",
            "description": "查询单个物品的实时市场价格（卖价、收价、价差）",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "物品名称（中文、英文或 market_id）"},
                },
                "required": ["item_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_set",
            "description": "查询 Prime 套装价格，对比整套购买 vs 拆件购买",
            "parameters": {
                "type": "object",
                "properties": {
                    "warframe_name": {"type": "string", "description": "战甲或武器名称"},
                },
                "required": ["warframe_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_missing_parts",
            "description": "计算补齐 Prime 套装还需要多少钱",
            "parameters": {
                "type": "object",
                "properties": {
                    "warframe_name": {"type": "string", "description": "战甲或武器名称"},
                    "owned_parts": {"type": "string", "description": "已有部件列表"},
                },
                "required": ["warframe_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_favorites",
            "description": "扫描关注物品和价格提醒的当前状态",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_alert",
            "description": "设置价格提醒，当物品价格达到阈值时通知",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "物品名称"},
                    "direction": {"type": "string", "description": "below 或 above"},
                    "price": {"type": "integer", "description": "目标价格"},
                },
                "required": ["item_name", "direction", "price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "price_trend",
            "description": "查看物品的价格历史趋势",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "物品名称"},
                },
                "required": ["item_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mod_flipper",
            "description": "扫描可交易 Mod 的翻转利润，找出最值得低级买、满级卖的 Mod，按每千内融利润排序",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_profit": {"type": "integer", "description": "最低利润阈值（白金），默认 5"},
                    "limit": {"type": "integer", "description": "返回结果数量，默认 20"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_profit",
            "description": "分析 Prime 套装利润，对比整套买卖 vs 拆件买卖，按利润排序",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_profit": {"type": "integer", "description": "最低利润阈值（白金），默认 5"},
                    "limit": {"type": "integer", "description": "返回结果数量，默认 20"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "investment_advisor",
            "description": "投资顾问：根据预算扫描物品翻转机会，按 ROI 排序，过滤低成交量和超预算项",
            "parameters": {
                "type": "object",
                "properties": {
                    "budget": {"type": "integer", "description": "可用预算（白金），默认 1000"},
                    "min_roi": {"type": "number", "description": "最低 ROI 百分比，默认 10"},
                    "limit": {"type": "integer", "description": "返回结果数量，默认 15"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan",
            "description": "将复杂请求分解为多个子任务并按顺序执行。用于对比多个物品、投资分析、多步骤查询。",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "用户目标简述"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tool": {"type": "string", "description": "子任务工具名"},
                                "args": {"type": "object", "description": "工具参数"},
                                "purpose": {"type": "string", "description": "步骤目的"},
                            },
                            "required": ["tool", "args"],
                        },
                        "description": "子任务列表",
                    },
                },
                "required": ["goal", "steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_events",
            "description": "查询当前游戏活动和事件（Baro 来访、警报、入侵、虚空风暴等）",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deep_analysis",
            "description": "深度分析单个物品的多维度数据（价格趋势、风险评估、投资建议），使用云端大模型推理",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "物品名称（中文、英文或 market_id）"},
                },
                "required": ["item_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "riven_search",
            "description": "搜索紫卡(Riven)拍卖信息。当用户提到紫卡、裂罅、Riven，或查询武器的紫卡时使用。支持指定正属性、负属性、价格上限。",
            "parameters": {
                "type": "object",
                "properties": {
                    "weapon": {"type": "string", "description": "武器名称，如 斯特朗、soma、rubico"},
                    "positive": {"type": "string", "description": "期望的正属性，如 双爆、暴击率+暴击伤害"},
                    "negative": {"type": "string", "description": "期望的负属性，如 无负、后坐力"},
                    "max_price": {"type": "integer", "description": "最高价格(白金)"},
                },
                "required": ["weapon"],
            },
        },
    },
]


TOOLS = [
    {
        "name": "query_price",
        "description": "查询单个物品的实时市场价格（卖价、收价、价差）",
        "parameters": {"item_name": "物品名称（中文、英文或 market_id）"},
    },
    {
        "name": "query_set",
        "description": "查询 Prime 套装价格，对比整套购买 vs 拆件购买",
        "parameters": {"warframe_name": "战甲或武器名称"},
    },
    {
        "name": "query_missing_parts",
        "description": "计算补齐 Prime 套装还需要多少钱",
        "parameters": {"warframe_name": "战甲或武器名称", "owned_parts": "已有部件列表"},
    },
    {
        "name": "scan_favorites",
        "description": "扫描关注物品和价格提醒的当前状态",
        "parameters": {},
    },
    {
        "name": "set_alert",
        "description": "设置价格提醒，当物品价格达到阈值时通知",
        "parameters": {"item_name": "物品名称", "direction": "below 或 above", "price": "目标价格"},
    },
    {
        "name": "price_trend",
        "description": "查看物品的价格历史趋势",
        "parameters": {"item_name": "物品名称"},
    },
    {
        "name": "general_chat",
        "description": "一般性 Warframe 交易问题或闲聊，不需要调用特定工具",
        "parameters": {"message": "用户消息"},
    },
    {
        "name": "mod_flipper",
        "description": "扫描 Mod 翻转利润，按每千内融利润排序",
        "parameters": {"min_profit": "最低利润", "limit": "结果数量"},
    },
    {
        "name": "set_profit",
        "description": "分析 Prime 套装利润，按利润排序",
        "parameters": {"min_profit": "最低利润", "limit": "结果数量"},
    },
    {
        "name": "investment_advisor",
        "description": "投资顾问：按预算和 ROI 扫描翻转机会",
        "parameters": {"budget": "预算", "min_roi": "最低ROI%", "limit": "结果数量"},
    },
    {
        "name": "plan",
        "description": "将复杂请求分解为多个子任务并按顺序执行",
        "parameters": {"goal": "用户目标", "steps": "子任务列表"},
    },
    {
        "name": "query_events",
        "description": "查询当前游戏活动和事件（Baro 来访、虚空裂缝、入侵、虚空风暴等）。可选 type 参数过滤：void_fissure=虚空裂缝, baro_visit=虚空商人, invasion=入侵, void_storm=虚空风暴",
        "parameters": {"type": "事件类型过滤（可选）：void_fissure / baro_visit / invasion / void_storm，不传则返回全部"},
    },
    {
        "name": "deep_analysis",
        "description": "深度分析单个物品的多维度数据，使用云端大模型推理",
        "parameters": {"item_name": "物品名称"},
    },
    {
        "name": "riven_search",
        "description": "搜索紫卡(Riven)拍卖信息。当用户提到紫卡、裂罅、Riven时使用。支持指定正属性、负属性、价格上限。",
        "parameters": {"weapon": "武器名称", "positive": "期望正属性(如双爆)", "negative": "期望负属性(如无负)", "max_price": "最高价格"},
    },
]


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


def _format_plan_results(goal: str, results: list[tuple[PlanStep, str | None]]) -> str:
    """将所有步骤结果格式化为 LLM 可推理的聚合文本。"""
    parts = [f"## 执行计划: {goal}\n"]
    for i, (step, result) in enumerate(results, 1):
        parts.append(f"### 步骤 {i}: {step.purpose or step.tool}")
        parts.append(f"工具: {step.tool}({json.dumps(step.arguments, ensure_ascii=False)})")
        if result:
            parts.append(f"结果:\n{result}")
        else:
            parts.append("结果: 执行失败或无结果")
        parts.append("")
    parts.append("请根据以上所有步骤的结果，综合回答用户的问题。")
    return "\n".join(parts)


def execute_plan(
    plan: ExecutionPlan,
    tool_executor: Callable[[ToolCall], str | None],
) -> list[tuple[PlanStep, str | None]]:
    """顺序执行 plan 的每一步，收集 (step, result) 对。"""
    results = []
    for step in plan.steps:
        tc = ToolCall(name=step.tool, arguments=step.arguments)
        result = tool_executor(tc)
        results.append((step, result))
    return results


def build_router_prompt(message: str) -> str:
    tools_desc = "\n".join(
        f"- {t['name']}: {t['description']}"
        + (f" (参数: {', '.join(t['parameters'].keys())})" if t['parameters'] else "")
        for t in TOOLS
    )
    return (
        "你是一个工具路由器。根据用户消息，选择最合适的工具并提取参数。\n"
        "只返回一个 JSON 对象，格式: {\"tool\": \"工具名\", \"args\": {参数}}\n"
        "不要返回其他内容，不要解释。\n\n"
        f"可用工具:\n{tools_desc}\n\n"
        f"用户消息: {message}\n"
        "JSON:"
    )


def parse_tool_call(response: str) -> ToolCall | None:
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
    valid_names = {t["name"] for t in TOOLS}
    if tool_name not in valid_names:
        return None
    # 提取参数：优先 args 字段，否则取除 tool 外的所有顶层字段
    args = data.get("args", {})
    if not args:
        args = {k: v for k, v in data.items() if k != "tool"}
    return ToolCall(name=tool_name, arguments=args)


def react_loop(
    message: str,
    tool_executor: Callable[[ToolCall], str | None],
    model_call: Callable[[list[dict]], str] | None = None,
    max_iterations: int = config.MAX_TOOL_ITERATIONS,
    model: str = config.REACT_MODEL,
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
    if model_call is None:
        model_call = _default_model_call

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
                "7. 用户问游戏活动/Baro/警报 → query_events\n"
                "   - 用户问虚空裂缝/裂隙/开核桃 → query_events(type='void_fissure')\n"
                "   - 用户问Baro/虚空商人 → query_events(type='baro_visit')\n"
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
                "- 如果工具返回了数据列表，完整展示，不要只挑一条"
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
        tool_calls = _extract_tool_calls(response)
        if not tool_calls:
            # 没有工具调用，视为最终回答
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
                "content": result or f"工具 {tc.name} 执行失败或无结果",
            })

    return None


def _extract_tool_calls(response: str) -> list[ToolCall]:
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
                    tc = parse_tool_call(json.dumps(item))
                    if tc:
                        calls.append(tc)
            if calls:
                return calls
        except json.JSONDecodeError:
            pass

    # 尝试单个 {"tool": ..., "args": ...}
    tc = parse_tool_call(cleaned)
    if tc:
        calls.append(tc)
    return calls


def _default_model_call(messages: list[dict]) -> str:
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama Python package is not installed") from exc
    response = ollama.chat(model=config.REACT_MODEL, messages=messages, tools=TOOL_SCHEMAS)
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
