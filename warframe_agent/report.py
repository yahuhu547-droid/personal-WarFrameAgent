from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

from . import config
from .formatter import build_whisper
from .market import MarketOrder


def render_daily_report(items: list[dict], report_date: str | None = None) -> str:
    report_date = report_date or date.today().isoformat()
    lines = [f"# Warframe 每日价格表 - {report_date}", ""]
    if not items:
        lines.append("暂无价格数据。")
        lines.append("")
        return "\n".join(lines)

    for category in _category_order(items):
        lines.extend([f"## {category}", "", "物品 | 最低在线卖价 | 最高在线收价 | 差价 | 推荐", "--- | --- | --- | --- | ---"])
        for item in [row for row in items if row["category"] == category]:
            lines.append(_summary_row(item))
        lines.append("")
        for item in [row for row in items if row["category"] == category]:
            lines.extend(_detail_lines(item))
    return "\n".join(lines)


def write_daily_report(items: list[dict], output_dir: Path = config.REPORT_DIR, report_date: str | None = None) -> Path:
    report_date = report_date or date.today().isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"daily-{report_date}.md"
    path.write_text(render_daily_report(items, report_date=report_date), encoding="utf-8")
    return path


def _category_order(items: Iterable[dict]) -> list[str]:
    categories: list[str] = []
    for item in items:
        category = item["category"]
        if category not in categories:
            categories.append(category)
    return categories


def _summary_row(item: dict) -> str:
    if item.get("error"):
        return f"{item['item_id']} | 查询失败 | 查询失败 | - | {item['error']}"
    sellers: list[MarketOrder] = item.get("sellers", [])
    buyers: list[MarketOrder] = item.get("buyers", [])
    sell_price = f"{sellers[0].platinum}p" if sellers else "无"
    buy_price = f"{buyers[0].platinum}p" if buyers else "无"
    spread = f"{sellers[0].platinum - buyers[0].platinum}p" if sellers and buyers else "-"
    recommendation = "可买可卖" if sellers and buyers else "数据不足"
    return f"{item['item_id']} | {sell_price} | {buy_price} | {spread} | {recommendation}"


def _detail_lines(item: dict) -> list[str]:
    lines = [f"### {item['item_id']}", ""]
    if item.get("error"):
        lines.extend([f"查询失败：{item['error']}", ""])
        return lines
    lines.extend(_orders_to_lines("卖家 Sell 订单（你点击 Buy）", item.get("sellers", []), item["item_id"]))
    lines.extend(_orders_to_lines("买家 Buy 订单（你点击 Sell）", item.get("buyers", []), item["item_id"]))
    return lines


def _orders_to_lines(title: str, orders: list[MarketOrder], item_id: str) -> list[str]:
    lines = [f"#### {title}", "", "排名 | 价格 | 数量 | 玩家 | 声望 | 私聊命令", "--- | --- | --- | --- | --- | ---"]
    if not orders:
        lines.extend(["无在线订单", ""])
        return lines
    for index, order in enumerate(orders, start=1):
        command = build_whisper(order.user_name, item_id, order.platinum, order.order_type)
        lines.append(f"{index} | {order.platinum}p | {order.quantity} | {order.user_name} | {order.reputation} | `{command}`")
    lines.append("")
    return lines
