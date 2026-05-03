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
]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


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
    return ToolCall(name=tool_name, arguments=data.get("args", {}))


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
                "你是 Warframe 交易助手的工具路由器。根据用户消息选择合适的工具调用。"
                "如果不需要工具，直接回答用户问题。"
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

        # 执行工具调用并回传结果
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
    return response.get("message", {}).get("content", "")
