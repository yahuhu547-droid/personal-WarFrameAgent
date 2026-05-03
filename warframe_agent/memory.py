from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, replace, field
from pathlib import Path

from . import config

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
class AgentMemory:
    preferences: TradingPreferences
    price_alerts: list[PriceAlert]
    favorite_items: list[str]
    common_questions: list[str]
    watchlist: list[WatchItem]
    user_profile: UserProfile | None = None
    recent_suggestions: list[ProactiveSuggestion] = field(default_factory=list)

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
        return cls(
            preferences=preferences,
            price_alerts=alerts,
            favorite_items=list(data.get("favorite_items", [])),
            common_questions=list(data.get("common_questions", [])),
            watchlist=watchlist,
            user_profile=profile,
            recent_suggestions=suggestions,
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
