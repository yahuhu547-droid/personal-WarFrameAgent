from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, replace, field
from pathlib import Path

from . import config
from .goals import AgentGoal, TradeOutcome

MEMORY_PATH = config.DATA_DIR / "agent_memory.json"

_BUY_KEYWORDS = ["买", "收", "最低卖", "卖最低"]
_SELL_KEYWORDS = ["卖", "出", "最高收", "收多少", "有人收"]
_CATEGORY_KEYWORDS = {
    "arcane": ["赋能", "arcane"],
    "prime_set": ["一套", "p套", "prime set", "set"],
    "prime_part": ["机体", "系统", "蓝图", "头部", "chassis", "systems", "blueprint", "neuroptics"],
    "mod": ["mod", "卡片", "振幅晶体"],
}


@dataclass(frozen=True)
class ProactiveSuggestion:
    item_id: str
    suggestion_type: str  # anomaly, trend, opportunity
    priority: int  # 1=critical, 2=important, 3=info
    message: str
    timestamp: str = ""


@dataclass(frozen=True)
class UserProfile:
    preferred_trade_type: str = "neutral"  # buy, sell, neutral
    queried_items: dict[str, int] = field(default_factory=dict)
    favorite_categories: list[str] = field(default_factory=list)
    total_queries: int = 0

    @classmethod
    def from_questions(cls, questions: list[str]) -> "UserProfile":
        buy_count = 0
        sell_count = 0
        item_counter: Counter[str] = Counter()
        category_counter: Counter[str] = Counter()

        for q in questions:
            lower = q.lower()
            if any(kw in lower for kw in _BUY_KEYWORDS):
                buy_count += 1
            if any(kw in lower for kw in _SELL_KEYWORDS):
                sell_count += 1
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(kw in lower for kw in keywords):
                    category_counter[cat] += 1
            # 提取可能的物品名（简单启发式：跳过纯关键词）
            tokens = re.split(r"[\s,，。?？!！]+", q)
            for tok in tokens:
                if len(tok) >= 2 and tok not in (*_BUY_KEYWORDS, *_SELL_KEYWORDS):
                    item_counter[tok] += 1

        if buy_count > sell_count:
            preferred = "buy"
        elif sell_count > buy_count:
            preferred = "sell"
        else:
            preferred = "neutral"

        return cls(
            preferred_trade_type=preferred,
            queried_items=dict(item_counter.most_common(20)),
            favorite_categories=[cat for cat, _ in category_counter.most_common(5)],
            total_queries=len(questions),
        )


@dataclass(frozen=True)
class TradingPreferences:
    platform: str = "pc"
    crossplay: bool = True
    max_results: int = 5


@dataclass(frozen=True)
class PriceAlert:
    item_id: str
    direction: str
    price: int
    note: str = ""

    def matches(self, current_price: int) -> bool:
        if self.direction == "below":
            return current_price <= self.price
        if self.direction == "above":
            return current_price >= self.price
        return False


@dataclass(frozen=True)
class WatchItem:
    item_id: str
    item_name: str
    frequency: str = "daily"  # daily, hourly, weekly
    time: str = "09:00"
    content: str = "top3_buyers"  # top3_sellers, top3_buyers, price_change, all


@dataclass(frozen=True)
class FissureAlert:
    node_pattern: str = ""        # 子串匹配，如 "虚空" 或 "SolNode742"
    mission_type: str = ""        # 如 "MT_EXTERMINATION" 或中文 "歼灭"
    tier: str = ""                # 如 "VoidT4" 或中文 "后纪"
    hard: bool | None = None      # None=不过滤, True=仅钢铁, False=仅普通
    note: str = ""                # 用户可读描述

    def matches_fissure(self, node: str, node_display: str, mission_type: str,
                        mission_display: str, tier: str, tier_display: str, hard: bool) -> bool:
        if self.node_pattern and self.node_pattern not in node and self.node_pattern not in node_display:
            return False
        if self.mission_type and self.mission_type != mission_type and self.mission_type != mission_display:
            return False
        if self.tier and self.tier != tier and self.tier not in tier_display:
            return False
        if self.hard is not None and self.hard != hard:
            return False
        return True


@dataclass(frozen=True)
class AgentMemory:
    preferences: TradingPreferences
    price_alerts: list[PriceAlert]
    favorite_items: list[str]
    common_questions: list[str]
    watchlist: list[WatchItem]
    user_profile: UserProfile | None = None
    recent_suggestions: list[ProactiveSuggestion] = field(default_factory=list)
    active_goals: list[AgentGoal] = field(default_factory=list)
    trade_outcomes: list[TradeOutcome] = field(default_factory=list)
    learned_patterns: list[dict] = field(default_factory=list)
    fissure_alerts: list[FissureAlert] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = MEMORY_PATH) -> "AgentMemory":
        if not path.exists():
            return cls.default()
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
        preferences = TradingPreferences(**data.get("preferences", {}))
        alerts = [PriceAlert(**alert) for alert in data.get("price_alerts", [])]
        watchlist = [WatchItem(**item) for item in data.get("watchlist", [])]
        profile_data = data.get("user_profile")
        profile = UserProfile(**profile_data) if profile_data else None
        suggestions = [ProactiveSuggestion(**s) for s in data.get("recent_suggestions", [])]
        goals = [AgentGoal(**g) for g in data.get("active_goals", [])]
        outcomes = [TradeOutcome(**o) for o in data.get("trade_outcomes", [])]
        fissure_alerts = [FissureAlert(**a) for a in data.get("fissure_alerts", [])]
        return cls(
            preferences=preferences,
            price_alerts=alerts,
            favorite_items=list(data.get("favorite_items", [])),
            common_questions=list(data.get("common_questions", [])),
            watchlist=watchlist,
            user_profile=profile,
            recent_suggestions=suggestions,
            active_goals=goals,
            trade_outcomes=outcomes,
            learned_patterns=list(data.get("learned_patterns", [])),
            fissure_alerts=fissure_alerts,
        )

    @classmethod
    def default(cls) -> "AgentMemory":
        return cls(
            preferences=TradingPreferences(),
            price_alerts=[],
            favorite_items=[],
            common_questions=[],
            watchlist=[],
            user_profile=None,
        )

    def save(self, path: Path = MEMORY_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def to_dict(self) -> dict:
        result = {
            "preferences": {
                "platform": self.preferences.platform,
                "crossplay": self.preferences.crossplay,
                "max_results": self.preferences.max_results,
            },
            "price_alerts": [
                {
                    "item_id": alert.item_id,
                    "direction": alert.direction,
                    "price": alert.price,
                    "note": alert.note,
                }
                for alert in self.price_alerts
            ],
            "favorite_items": list(self.favorite_items),
            "common_questions": list(self.common_questions),
            "watchlist": [
                {
                    "item_id": item.item_id,
                    "item_name": item.item_name,
                    "frequency": item.frequency,
                    "time": item.time,
                    "content": item.content,
                }
                for item in self.watchlist
            ],
        }
        if self.user_profile is not None:
            result["user_profile"] = {
                "preferred_trade_type": self.user_profile.preferred_trade_type,
                "queried_items": self.user_profile.queried_items,
                "favorite_categories": self.user_profile.favorite_categories,
                "total_queries": self.user_profile.total_queries,
            }
        if self.recent_suggestions:
            result["recent_suggestions"] = [
                {
                    "item_id": s.item_id,
                    "suggestion_type": s.suggestion_type,
                    "priority": s.priority,
                    "message": s.message,
                    "timestamp": s.timestamp,
                }
                for s in self.recent_suggestions
            ]
        if self.active_goals:
            result["active_goals"] = [
                {
                    "goal_id": g.goal_id,
                    "goal_type": g.goal_type,
                    "description": g.description,
                    "target": g.target,
                    "criteria": g.criteria,
                    "status": g.status,
                    "created_at": g.created_at,
                    "results": g.results,
                }
                for g in self.active_goals
            ]
        if self.trade_outcomes:
            result["trade_outcomes"] = [
                {
                    "outcome_id": o.outcome_id,
                    "goal_id": o.goal_id,
                    "action": o.action,
                    "item_id": o.item_id,
                    "price": o.price,
                    "expected_profit": o.expected_profit,
                    "actual_profit": o.actual_profit,
                    "user_feedback": o.user_feedback,
                    "timestamp": o.timestamp,
                }
                for o in self.trade_outcomes
            ]
        if self.learned_patterns:
            result["learned_patterns"] = self.learned_patterns
        if self.fissure_alerts:
            result["fissure_alerts"] = [
                {
                    "node_pattern": a.node_pattern,
                    "mission_type": a.mission_type,
                    "tier": a.tier,
                    "hard": a.hard,
                    "note": a.note,
                }
                for a in self.fissure_alerts
            ]
        return result

    def analyze_and_update_profile(self) -> "AgentMemory":
        """根据 common_questions 重新分析用户画像"""
        if not self.common_questions:
            return self
        profile = UserProfile.from_questions(self.common_questions)
        return replace(self, user_profile=profile)

    def with_suggestion(self, suggestion: ProactiveSuggestion, limit: int = 20) -> "AgentMemory":
        suggestions = [*self.recent_suggestions, suggestion]
        return replace(self, recent_suggestions=suggestions[-limit:])

    def with_updated_preferences(
        self,
        *,
        platform: str | None = None,
        crossplay: bool | None = None,
        max_results: int | None = None,
    ) -> "AgentMemory":
        return replace(
            self,
            preferences=TradingPreferences(
                platform=self.preferences.platform if platform is None else platform,
                crossplay=self.preferences.crossplay if crossplay is None else crossplay,
                max_results=self.preferences.max_results if max_results is None else max_results,
            ),
        )

    def set_preference(self, key: str, value: str) -> "AgentMemory":
        if key == "platform":
            return self.with_updated_preferences(platform=value)
        if key == "crossplay":
            return self.with_updated_preferences(crossplay=value.lower() in ("true", "1", "yes"))
        if key == "max_results":
            try:
                return self.with_updated_preferences(max_results=int(value))
            except ValueError:
                return self
        return self

    def with_favorite_item(self, item_id: str) -> "AgentMemory":
        if item_id in self.favorite_items:
            return self
        return replace(self, favorite_items=[*self.favorite_items, item_id])

    def without_favorite_item(self, item_id: str) -> "AgentMemory":
        return replace(self, favorite_items=[value for value in self.favorite_items if value != item_id])

    def with_price_alert(self, item_id: str, direction: str, price: int, note: str = "") -> "AgentMemory":
        alerts = [
            alert for alert in self.price_alerts
            if not (alert.item_id == item_id and alert.direction == direction and alert.price == price)
        ]
        alerts.append(PriceAlert(item_id=item_id, direction=direction, price=price, note=note))
        return replace(self, price_alerts=alerts)

    def without_price_alert(self, item_id: str, direction: str, price: int) -> "AgentMemory":
        return replace(
            self,
            price_alerts=[
                alert for alert in self.price_alerts
                if not (alert.item_id == item_id and alert.direction == direction and alert.price == price)
            ],
        )

    def with_common_question(self, question: str, limit: int = 20) -> "AgentMemory":
        question = question.strip()
        if not question:
            return self
        questions = [value for value in self.common_questions if value != question]
        questions.append(question)
        return replace(self, common_questions=questions[-limit:])

    def alerts_for(self, item_id: str, current_price: int) -> list[PriceAlert]:
        return [alert for alert in self.price_alerts if alert.item_id == item_id and alert.matches(current_price)]

    def with_watch_item(self, item_id: str, item_name: str, frequency: str = "daily", time: str = "09:00", content: str = "top3_buyers") -> "AgentMemory":
        # 检查是否已存在相同的关注项
        for item in self.watchlist:
            if item.item_id == item_id:
                return self
        watch_item = WatchItem(item_id=item_id, item_name=item_name, frequency=frequency, time=time, content=content)
        return replace(self, watchlist=[*self.watchlist, watch_item])

    def without_watch_item(self, item_id: str) -> "AgentMemory":
        return replace(self, watchlist=[item for item in self.watchlist if item.item_id != item_id])

    def with_updated_watch_item(self, item_id: str, **kwargs) -> "AgentMemory":
        watchlist = []
        for item in self.watchlist:
            if item.item_id == item_id:
                watchlist.append(replace(item, **kwargs))
            else:
                watchlist.append(item)
        return replace(self, watchlist=watchlist)

    # ── 目标管理 ──────────────────────────────────────────

    def with_goal(self, goal: AgentGoal) -> "AgentMemory":
        return replace(self, active_goals=[*self.active_goals, goal])

    def without_goal(self, goal_id: str) -> "AgentMemory":
        return replace(self, active_goals=[g for g in self.active_goals if g.goal_id != goal_id])

    def with_goal_result(self, goal_id: str, result: dict) -> "AgentMemory":
        goals = []
        for g in self.active_goals:
            if g.goal_id == goal_id:
                goals.append(replace(g, results=[*g.results, result]))
            else:
                goals.append(g)
        return replace(self, active_goals=goals)

    def active_goals_list(self) -> list[AgentGoal]:
        return [g for g in self.active_goals if g.status == "active"]

    def with_trade_outcome(self, outcome: TradeOutcome) -> "AgentMemory":
        return replace(self, trade_outcomes=[*self.trade_outcomes, outcome])

    def with_patterns(self, patterns: list[dict], limit: int = 20) -> "AgentMemory":
        existing_descs = {p["description"] for p in self.learned_patterns}
        new_patterns = [p for p in patterns if p.get("description") not in existing_descs]
        all_patterns = [*self.learned_patterns, *new_patterns]
        all_patterns.sort(key=lambda p: p.get("confidence", 0), reverse=True)
        return replace(self, learned_patterns=all_patterns[:limit])

    # ── 裂缝订阅 ──────────────────────────────────────────

    def with_fissure_alert(self, alert: FissureAlert) -> "AgentMemory":
        key = (alert.node_pattern, alert.mission_type, alert.tier, alert.hard)
        for existing in self.fissure_alerts:
            if (existing.node_pattern, existing.mission_type, existing.tier, existing.hard) == key:
                return self
        return replace(self, fissure_alerts=[*self.fissure_alerts, alert])

    def without_fissure_alert(self, index: int) -> "AgentMemory":
        if 0 <= index < len(self.fissure_alerts):
            alerts = [a for i, a in enumerate(self.fissure_alerts) if i != index]
            return replace(self, fissure_alerts=alerts)
        return self
