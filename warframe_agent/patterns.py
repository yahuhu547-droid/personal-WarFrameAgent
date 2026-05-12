"""模式学习 — 从交易历史和价格历史中提取规律，用 LLM 发现模式。"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .price_history import PriceHistoryDB
from .trade_history import TradeHistoryDB
from .goals import TradeOutcome


@dataclass(frozen=True)
class LearnedPattern:
    pattern_id: str
    category: str       # "time" / "item" / "strategy"
    description: str
    confidence: float   # 0.0-1.0
    data_points: int
    discovered_at: str
    last_validated: str


def extract_time_patterns(
    trade_db: TradeHistoryDB,
    price_db: PriceHistoryDB,
) -> dict:
    """按星期和小时聚合交易数据，返回原始统计。"""
    trades = trade_db.get_recent_trades(limit=200)
    if not trades:
        return {"trade_count": 0, "by_weekday": {}, "by_hour": {}}

    weekday_counter: Counter[int] = Counter()
    hour_counter: Counter[int] = Counter()
    weekday_profit: dict[int, list[int]] = {}
    hour_profit: dict[int, list[int]] = {}

    for t in trades:
        try:
            dt = datetime.fromisoformat(t.timestamp)
            wd = dt.weekday()  # 0=Mon, 6=Sun
            hr = dt.hour
            weekday_counter[wd] += 1
            hour_counter[hr] += 1
            weekday_profit.setdefault(wd, []).append(t.price)
            hour_profit.setdefault(hr, []).append(t.price)
        except Exception:
            continue

    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    by_weekday = {}
    for wd in sorted(weekday_counter):
        prices = weekday_profit.get(wd, [])
        by_weekday[weekday_names[wd]] = {
            "count": weekday_counter[wd],
            "avg_price": round(sum(prices) / len(prices)) if prices else 0,
        }

    by_hour = {}
    for hr in sorted(hour_counter):
        prices = hour_profit.get(hr, [])
        by_hour[f"{hr:02d}:00"] = {
            "count": hour_counter[hr],
            "avg_price": round(sum(prices) / len(prices)) if prices else 0,
        }

    return {
        "trade_count": len(trades),
        "by_weekday": by_weekday,
        "by_hour": by_hour,
    }


def extract_item_patterns(
    trade_db: TradeHistoryDB,
    price_db: PriceHistoryDB,
) -> dict:
    """提取单品交易频率和价格稳定性数据。"""
    trades = trade_db.get_recent_trades(limit=200)
    if not trades:
        return {"item_count": 0, "items": []}

    item_counter: Counter[str] = Counter()
    item_prices: dict[str, list[int]] = {}
    item_names: dict[str, str] = {}

    for t in trades:
        item_counter[t.item_id] += 1
        item_prices.setdefault(t.item_id, []).append(t.price)
        item_names[t.item_id] = t.item_name

    items = []
    for item_id, count in item_counter.most_common(10):
        prices = item_prices.get(item_id, [])
        avg = round(sum(prices) / len(prices)) if prices else 0
        items.append({
            "item_id": item_id,
            "item_name": item_names.get(item_id, item_id),
            "trade_count": count,
            "avg_price": avg,
        })

    return {"item_count": len(item_counter), "items": items}


def extract_strategy_patterns(
    trade_outcomes: list[TradeOutcome],
) -> dict:
    """从交易结果中提取策略级别的统计。"""
    if not trade_outcomes:
        return {"total": 0, "by_source": {}}

    source_stats: dict[str, dict] = {}
    for o in trade_outcomes:
        # 从 item_id 推断 source
        if "mod" in o.item_id.lower() or "primed" in o.item_id.lower():
            source = "mod_flip"
        elif "_set" in o.item_id or "_prime_" in o.item_id:
            source = "set_profit"
        else:
            source = "other"

        if source not in source_stats:
            source_stats[source] = {"total": 0, "good": 0, "bad": 0, "ignored": 0, "profits": []}
        stats = source_stats[source]
        stats["total"] += 1
        stats[o.user_feedback] = stats.get(o.user_feedback, 0) + 1
        if o.actual_profit != 0:
            stats["profits"].append(o.actual_profit)

    for source, stats in source_stats.items():
        profits = stats.pop("profits", [])
        stats["avg_profit"] = round(sum(profits) / len(profits)) if profits else 0
        stats["success_rate"] = round(stats["good"] / max(stats["total"], 1), 2)

    return {"total": len(trade_outcomes), "by_source": source_stats}


def build_pattern_discovery_prompt(
    time_data: dict,
    item_data: dict,
    strategy_data: dict,
) -> str:
    """构建模式发现的 LLM prompt。"""
    return (
        "你是 Warframe 交易数据分析师。从以下交易数据中发现有价值的规律。\n\n"
        f"## 交易时间分布\n```json\n{json.dumps(time_data, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 热门交易物品\n```json\n{json.dumps(item_data, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 策略表现\n```json\n{json.dumps(strategy_data, ensure_ascii=False, indent=2)}\n```\n\n"
        "请从中发现 1-5 条有价值的规律，返回 JSON 数组，每条格式:\n"
        '{"category": "time/item/strategy", "description": "规律描述", "confidence": 0.0-1.0, "evidence": "数据依据"}\n\n'
        "规则:\n"
        "- 只发现有数据支撑的规律，不要猜测\n"
        "- confidence 基于数据量和一致性：数据越多、越一致，confidence 越高\n"
        "- 用中文描述规律\n"
        "- 只返回 JSON 数组，不要解释"
    )


def parse_patterns(response: str) -> list[dict]:
    """解析 LLM 返回的模式 JSON。"""
    # 提取 JSON 数组
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if not match:
        return []
    try:
        patterns = json.loads(match.group())
        if not isinstance(patterns, list):
            return []
        result = []
        for p in patterns:
            if isinstance(p, dict) and "description" in p:
                result.append({
                    "category": p.get("category", "unknown"),
                    "description": p["description"],
                    "confidence": min(1.0, max(0.0, float(p.get("confidence", 0.5)))),
                    "evidence": p.get("evidence", ""),
                })
        return result
    except (json.JSONDecodeError, ValueError):
        return []


def discover_patterns(
    trade_db: TradeHistoryDB,
    price_db: PriceHistoryDB,
    trade_outcomes: list[TradeOutcome],
    llm_caller: Callable[[list[dict]], str],
) -> list[dict]:
    """主入口：提取数据 → LLM 分析 → 返回模式列表。"""
    time_data = extract_time_patterns(trade_db, price_db)
    item_data = extract_item_patterns(trade_db, price_db)
    strategy_data = extract_strategy_patterns(trade_outcomes)

    # 数据太少时不调用 LLM
    if time_data.get("trade_count", 0) < 3 and strategy_data.get("total", 0) < 3:
        return []

    prompt = build_pattern_discovery_prompt(time_data, item_data, strategy_data)
    try:
        response = llm_caller([
            {"role": "system", "content": "你是数据分析师，从交易数据中发现规律。只返回 JSON。"},
            {"role": "user", "content": prompt},
        ])
    except Exception:
        return []

    patterns = parse_patterns(response)
    # 添加元数据
    now = datetime.now(timezone.utc).isoformat()
    enriched = []
    for p in patterns:
        enriched.append({
            **p,
            "pattern_id": uuid.uuid4().hex[:12],
            "discovered_at": now,
            "last_validated": now,
        })
    return enriched
