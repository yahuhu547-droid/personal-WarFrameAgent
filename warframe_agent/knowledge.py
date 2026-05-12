"""结构化知识库 — 随时间积累市场智能，替代 LLM 的市场分析角色。"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)

KNOWLEDGE_TTL_DAYS = 30
from .price_history import PriceHistoryDB

KNOWLEDGE_PATH = config.DATA_DIR / "knowledge_base.json"


def _classify_category(item_id: str) -> tuple[str, str]:
    """根据 item_id 推断 (category, subcategory)。"""
    lower = item_id.lower()
    if "arcane" in lower:
        return "arcane", "arcane"
    if "_set" in lower or ("_prime_" in lower and any(
        p in lower for p in ["blueprint", "chassis", "neuroptics", "systems"]
    )):
        return "prime_part", "prime"
    if "_prime_" in lower and "_set" not in lower:
        return "prime_set", "prime"
    if "primed" in lower:
        return "mod", "primed"
    if "mod" in lower or "riven" in lower:
        return "mod", "common"
    return "other", "other"


@dataclass(frozen=True)
class ItemKnowledge:
    item_id: str
    category: str
    subcategory: str
    rolling_avg_sell: float | None = None
    rolling_avg_buy: float | None = None
    volatility: float = 0.0
    trend: str = "stable"          # "rising" / "falling" / "stable"
    volume_trend: str = "unknown"  # "increasing" / "decreasing" / "stable" / "unknown"
    last_updated: str = ""
    scan_count: int = 0
    event_context: str | None = None


@dataclass(frozen=True)
class CategoryHealth:
    category: str
    opportunity_count: int = 0
    avg_roi: float = 0.0
    avg_profit: float = 0.0
    trend: str = "neutral"  # "bullish" / "bearish" / "neutral"
    top_items: list[str] = field(default_factory=list)


class MarketKnowledge:
    def __init__(self, items: dict[str, ItemKnowledge] | None = None):
        self._items: dict[str, ItemKnowledge] = items or {}

    def get_item_stats(self, item_id: str) -> ItemKnowledge | None:
        return self._items.get(item_id)

    def get_category_health(self, category: str) -> CategoryHealth:
        items = [ik for ik in self._items.values() if ik.category == category]
        if not items:
            return CategoryHealth(category=category)
        rising = sum(1 for i in items if i.trend == "rising")
        falling = sum(1 for i in items if i.trend == "falling")
        if rising > falling * 1.5:
            trend = "bullish"
        elif falling > rising * 1.5:
            trend = "bearish"
        else:
            trend = "neutral"
        avg_vol = sum(i.volatility for i in items) / len(items) if items else 0
        # 从 spread 计算平均利润
        spreads = [
            i.rolling_avg_sell - i.rolling_avg_buy
            for i in items
            if i.rolling_avg_sell is not None and i.rolling_avg_buy is not None
        ]
        avg_profit = round(sum(spreads) / len(spreads), 1) if spreads else 0
        top = sorted(items, key=lambda i: i.scan_count, reverse=True)[:5]
        return CategoryHealth(
            category=category,
            opportunity_count=len(items),
            avg_roi=avg_vol,
            avg_profit=avg_profit,
            trend=trend,
            top_items=[i.item_id for i in top],
        )

    def get_market_summary(self) -> dict:
        categories = set(ik.category for ik in self._items.values())
        cat_health = {c: self.get_category_health(c) for c in categories}
        total = len(self._items)
        rising = sum(1 for i in self._items.values() if i.trend == "rising")
        falling = sum(1 for i in self._items.values() if i.trend == "falling")
        avg_vol = (
            sum(i.volatility for i in self._items.values()) / total
            if total > 0 else 0
        )
        if rising > falling * 1.5:
            direction = "bullish"
        elif falling > rising * 1.5:
            direction = "bearish"
        else:
            direction = "neutral"
        best = max(cat_health.values(), key=lambda c: c.avg_roi, default=None)
        # 聚合品类指标
        all_rois = [ch.avg_roi for ch in cat_health.values() if ch.avg_roi > 0]
        all_profits = [ch.avg_profit for ch in cat_health.values() if ch.avg_profit > 0]
        return {
            "total_items": total,
            "trend_direction": direction,
            "volatility_index": round(avg_vol, 1),
            "category_health": {c: ch for c, ch in cat_health.items()},
            "best_category": best.category if best else "",
            "avg_roi": round(sum(all_rois) / len(all_rois), 1) if all_rois else 0,
            "avg_profit": round(sum(all_profits) / len(all_profits), 1) if all_profits else 0,
            "avg_volatility": round(avg_vol, 1),
        }

    def update_from_scan(
        self,
        scan_results: list[dict],
        price_db: PriceHistoryDB,
        events: list | None = None,
    ) -> None:
        """增量更新：从扫描结果中更新物品知识。可选注入游戏事件上下文。"""
        now = datetime.now(timezone.utc).isoformat()
        seen_ids: set[str] = set()

        # 构建 item_id → event 映射
        item_event_map: dict[str, str] = {}
        if events:
            for e in events:
                for iid in getattr(e, "items_affected", []) or []:
                    desc = getattr(e, "description", "")
                    etype = getattr(e, "event_type", "")
                    impact = getattr(e, "impact", "")
                    entry = f"{etype}:{impact}" if etype else desc
                    if iid in item_event_map:
                        item_event_map[iid] += f"; {entry}"
                    else:
                        item_event_map[iid] = entry

        for r in scan_results:
            item_id = r.get("item_id", "")
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            existing = self._items.get(item_id)
            cat, subcat = _classify_category(item_id)

            # 从 price_db 计算统计量
            snapshots = price_db.recent(item_id, limit=10)
            sell_prices = [s.sell_price for s in snapshots if s.sell_price is not None]
            buy_prices = [s.buy_price for s in snapshots if s.buy_price is not None]

            avg_sell = round(sum(sell_prices) / len(sell_prices), 1) if sell_prices else None
            avg_buy = round(sum(buy_prices) / len(buy_prices), 1) if buy_prices else None

            # 变异系数 (coefficient of variation)
            volatility = 0.0
            if sell_prices and len(sell_prices) >= 2 and avg_sell and avg_sell > 0:
                variance = sum((p - avg_sell) ** 2 for p in sell_prices) / len(sell_prices)
                volatility = round((math.sqrt(variance) / avg_sell) * 100, 1)

            # 趋势
            trend_data = price_db.predict_trend(item_id)
            trend = trend_data["direction"] if trend_data else "stable"

            # 交易活跃度：从快照数推断
            snapshot_count = len(snapshots)
            if snapshot_count >= 8:
                volume_trend = "increasing"
            elif snapshot_count >= 3:
                volume_trend = "stable"
            else:
                volume_trend = "decreasing"

            scan_count = (existing.scan_count + 1) if existing else 1

            # 事件上下文：优先用新事件，否则保留旧的
            event_ctx = item_event_map.get(item_id) or (existing.event_context if existing else None)

            self._items[item_id] = ItemKnowledge(
                item_id=item_id,
                category=cat,
                subcategory=subcat,
                rolling_avg_sell=avg_sell,
                rolling_avg_buy=avg_buy,
                volatility=volatility,
                trend=trend,
                volume_trend=volume_trend,
                last_updated=now,
                scan_count=scan_count,
                event_context=event_ctx,
            )

    def predict_with_events(self, item_id: str, events: list | None = None) -> str:
        """结合事件上下文预测趋势。正面事件 + stable → rising，负面 + stable → falling。"""
        stats = self.get_item_stats(item_id)
        if not stats:
            return "insufficient_data"
        # 扫描次数不足时趋势不可靠
        if stats.scan_count < 3:
            return "insufficient_data"
        base_trend = stats.trend
        if not events:
            return base_trend
        for event in events:
            affected = getattr(event, "items_affected", []) or []
            if item_id in affected:
                impact = getattr(event, "impact", "")
                if impact == "positive" and base_trend == "stable":
                    return "rising"
                if impact == "negative" and base_trend == "stable":
                    return "falling"
        return base_trend

    def update_event_context(self, events: list[dict]) -> None:
        """从游戏事件列表更新物品的事件上下文。"""
        item_events: dict[str, str] = {}
        for e in events:
            for item_id in e.get("items_affected", []):
                desc = e.get("description", "")
                if item_id in item_events:
                    item_events[item_id] += f"; {desc}"
                else:
                    item_events[item_id] = desc

        updated = {}
        for item_id, ik in self._items.items():
            ctx = item_events.get(item_id)
            if ctx:
                updated[item_id] = replace(ik, event_context=ctx)
            elif ik.event_context:
                updated[item_id] = replace(ik, event_context=None)
        self._items.update(updated)

    def _cleanup_expired(self) -> int:
        """移除超过 TTL 未更新的条目，返回移除数量。"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=KNOWLEDGE_TTL_DAYS)
        expired = [
            iid for iid, ik in self._items.items()
            if ik.last_updated and datetime.fromisoformat(ik.last_updated) < cutoff
        ]
        for iid in expired:
            del self._items[iid]
        if expired:
            logger.info("知识库过期清理: 移除 %d 条（超过 %d 天未更新）", len(expired), KNOWLEDGE_TTL_DAYS)
        return len(expired)

    def save(self, path: Path = KNOWLEDGE_PATH) -> None:
        self._cleanup_expired()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "items": {
                iid: {
                    "item_id": ik.item_id,
                    "category": ik.category,
                    "subcategory": ik.subcategory,
                    "rolling_avg_sell": ik.rolling_avg_sell,
                    "rolling_avg_buy": ik.rolling_avg_buy,
                    "volatility": ik.volatility,
                    "trend": ik.trend,
                    "volume_trend": ik.volume_trend,
                    "last_updated": ik.last_updated,
                    "scan_count": ik.scan_count,
                    "event_context": ik.event_context,
                }
                for iid, ik in self._items.items()
            }
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = KNOWLEDGE_PATH) -> "MarketKnowledge":
        if not path.exists():
            return cls()
        try:
            with path.open("r", encoding="utf-8-sig") as f:
                data = json.load(f)
            items = {}
            for iid, d in data.get("items", {}).items():
                items[iid] = ItemKnowledge(
                    item_id=d["item_id"],
                    category=d["category"],
                    subcategory=d["subcategory"],
                    rolling_avg_sell=d.get("rolling_avg_sell"),
                    rolling_avg_buy=d.get("rolling_avg_buy"),
                    volatility=d.get("volatility", 0),
                    trend=d.get("trend", "stable"),
                    volume_trend=d.get("volume_trend", "unknown"),
                    last_updated=d.get("last_updated", ""),
                    scan_count=d.get("scan_count", 0),
                    event_context=d.get("event_context"),
                )
            knowledge = cls(items=items)
            knowledge._cleanup_expired()
            return knowledge
        except (json.JSONDecodeError, KeyError):
            return cls()
