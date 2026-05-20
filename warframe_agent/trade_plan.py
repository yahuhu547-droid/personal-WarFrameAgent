from __future__ import annotations

from hashlib import sha1
from math import floor
from typing import Any

from .formatter import build_whisper, display_name, market_item_url
from .market import MarketOrder

WARFRAME_MARKET_ITEM_URL_PREFIX = "https://warframe.market/items/"
WARFRAME_MARKET_PROFILE_URL_PREFIX = "https://warframe.market/profile/"


def safe_warframe_market_url(url: str) -> str:
    text = str(url or "").strip()
    if text.startswith(WARFRAME_MARKET_ITEM_URL_PREFIX) or text.startswith(WARFRAME_MARKET_PROFILE_URL_PREFIX):
        return text
    return ""


def trade_plan_step_lines(step: dict[str, Any]) -> list[str]:
    label = str(step.get("label") or step.get("display_name") or step.get("item_id") or "交易步骤")
    player = str(step.get("player") or "未知玩家")
    unit_price = step.get("unit_price", "-")
    quantity = step.get("quantity", 1)
    subtotal = step.get("subtotal", "-")
    lines = [f"{label} — {player}：{unit_price}p × {quantity} = {subtotal}p"]
    market_url = safe_warframe_market_url(step.get("market_url"))
    profile_url = safe_warframe_market_url(step.get("profile_url"))
    whisper = str(step.get("whisper") or "")
    if market_url:
        lines.append(f"市场：{market_url}")
    if profile_url:
        lines.append(f"Profile：{profile_url}")
    if whisper:
        lines.append(whisper)
    return lines

def profile_url(player: str) -> str:
    name = str(player or "").strip()
    return f"https://warframe.market/profile/{name}" if name else ""


def profit_bucket(profit: int | float, bucket_size: int = 10) -> str:
    try:
        value = int(floor(float(profit) / bucket_size) * bucket_size)
    except (TypeError, ValueError):
        value = 0
    return f"{value}_{value + bucket_size}"


def trade_step_from_order(
    *,
    side: str,
    label: str,
    item_id: str,
    order: MarketOrder,
    quantity: int | None = None,
    rank: int | None = None,
) -> dict[str, Any]:
    qty = int(quantity if quantity is not None else order.quantity)
    subtotal = int(order.platinum) * qty
    return {
        "side": side,
        "label": label,
        "item_id": item_id,
        "display_name": display_name(item_id),
        "rank": order.mod_rank if rank is None else rank,
        "quantity": qty,
        "unit_price": int(order.platinum),
        "subtotal": subtotal,
        "player": order.user_name,
        "reputation": order.reputation,
        "market_url": market_item_url(item_id),
        "profile_url": profile_url(order.user_name),
        "whisper": build_whisper(order.user_name, item_id, int(order.platinum), order.order_type),
    }


def build_trade_plan(
    *,
    source: str,
    strategy: str,
    display_strategy: str,
    item_id: str,
    display_name: str,
    required_quantity: int,
    buy_steps: list[dict[str, Any]],
    sell_steps: list[dict[str, Any]],
    total_cost: int,
    total_revenue: int,
    profit: int,
    roi_pct: float,
    volume_48h: int | None = None,
    risk_level: str = "",
) -> dict[str, Any]:
    summary_parts = [
        source,
        strategy,
        item_id,
        str(required_quantity),
        str(total_cost),
        str(total_revenue),
        str(profit_bucket(profit)),
        ",".join(f"{s.get('side')}:{s.get('item_id')}:{s.get('rank')}:{s.get('quantity')}:{s.get('unit_price')}" for s in buy_steps + sell_steps),
    ]
    signature = sha1("|".join(summary_parts).encode("utf-8")).hexdigest()[:16]
    plan = {
        "schema_version": 1,
        "source": source,
        "strategy": strategy,
        "display_strategy": display_strategy,
        "item_id": item_id,
        "display_name": display_name,
        "required_quantity": required_quantity,
        "buy_steps": buy_steps,
        "sell_steps": sell_steps,
        "total_cost": int(total_cost),
        "total_revenue": int(total_revenue),
        "profit": int(profit),
        "roi_pct": round(float(roi_pct), 1),
        "volume_48h": volume_48h,
        "risk_level": risk_level,
        "profit_bucket": profit_bucket(profit),
        "plan_signature": signature,
    }
    plan["safe_summary"] = trade_plan_safe_summary(plan)
    return plan


def trade_plan_safe_summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": plan.get("schema_version", 1),
        "source": plan.get("source", ""),
        "strategy": plan.get("strategy", ""),
        "item_id": plan.get("item_id", ""),
        "display_name": plan.get("display_name", ""),
        "required_quantity": plan.get("required_quantity", 0),
        "buy_step_count": len(plan.get("buy_steps") or []),
        "sell_step_count": len(plan.get("sell_steps") or []),
        "total_cost": plan.get("total_cost", 0),
        "total_revenue": plan.get("total_revenue", 0),
        "profit": plan.get("profit", 0),
        "roi_pct": plan.get("roi_pct", 0),
        "volume_48h": plan.get("volume_48h"),
        "risk_level": plan.get("risk_level", ""),
        "profit_bucket": plan.get("profit_bucket", ""),
        "plan_signature": plan.get("plan_signature", ""),
    }
