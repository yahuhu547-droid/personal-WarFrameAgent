from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


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
