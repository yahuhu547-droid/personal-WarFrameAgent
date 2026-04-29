from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from . import config

MEMORY_PATH = config.DATA_DIR / "agent_memory.json"


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
class AgentMemory:
    preferences: TradingPreferences
    price_alerts: list[PriceAlert]
    favorite_items: list[str]
    common_questions: list[str]

    @classmethod
    def load(cls, path: Path = MEMORY_PATH) -> "AgentMemory":
        if not path.exists():
            return cls.default()
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
        preferences = TradingPreferences(**data.get("preferences", {}))
        alerts = [PriceAlert(**alert) for alert in data.get("price_alerts", [])]
        return cls(
            preferences=preferences,
            price_alerts=alerts,
            favorite_items=list(data.get("favorite_items", [])),
            common_questions=list(data.get("common_questions", [])),
        )

    @classmethod
    def default(cls) -> "AgentMemory":
        return cls(
            preferences=TradingPreferences(),
            price_alerts=[],
            favorite_items=[],
            common_questions=[],
        )

    def save(self, path: Path = MEMORY_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def to_dict(self) -> dict:
        return {
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
        }

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
