from __future__ import annotations

from .market import MarketOrder


def display_name(item_id: str) -> str:
    return item_id.replace("_", " ").title()


def build_whisper(user_name: str, item_id: str, platinum: int, order_type: str) -> str:
    if order_type == "sell":
        action = "buy"
    elif order_type == "buy":
        action = "sell"
    else:
        raise ValueError(f"未知订单类型：{order_type}")
    return f'/w {user_name} Hi! I want to {action}: "{display_name(item_id)}" for {platinum} platinum. (warframe.market)'


def format_order_table(title: str, orders: list[MarketOrder], item_id: str) -> str:
    lines = [f"\n[{title}]", "排名 | 价格 | 数量 | 玩家 | 状态 | 声望 | 私聊命令", "--- | --- | --- | --- | --- | --- | ---"]
    if not orders:
        lines.append("无在线订单")
        return "\n".join(lines)
    for index, order in enumerate(orders, start=1):
        command = build_whisper(order.user_name, item_id, order.platinum, order.order_type)
        lines.append(
            f"{index} | {order.platinum}p | {order.quantity} | {order.user_name} | {order.status} | {order.reputation} | {command}"
        )
    return "\n".join(lines)


def format_lookup_result(item_id: str, source: str, sellers: list[MarketOrder], buyers: list[MarketOrder]) -> str:
    lines = [f"\n识别物品：{item_id}（来源：{source}）"]
    lines.append(format_order_table("推荐卖家 Sell 订单：最低价前 5，点击 Buy 的等价私聊", sellers, item_id))
    lines.append(format_order_table("推荐买家 Buy 订单：最高价前 5，点击 Sell 的等价私聊", buyers, item_id))
    return "\n".join(lines)
