from __future__ import annotations

from dataclasses import dataclass, field


FOLLOWUP_TERMS = [
    "那", "呢", "散件", "部件", "比昨天", "比上次",
    "还有", "其他的", "怎么样了", "现在呢", "多少了",
    "涨了吗", "跌了吗", "变了吗",
]


@dataclass
class SessionContext:
    last_item_ids: list[str] = field(default_factory=list)
    last_query_type: str | None = None
    last_intent: str | None = None
    history: list[tuple[str, str]] = field(default_factory=list)

    def update(
        self,
        item_ids: list[str],
        query_type: str | None = None,
        intent: str | None = None,
    ) -> None:
        if item_ids:
            self.last_item_ids = list(item_ids)
        if query_type:
            self.last_query_type = query_type
        if intent:
            self.last_intent = intent

    def add_exchange(self, user_msg: str, reply: str, max_history: int = 10) -> None:
        self.history.append((user_msg, reply))
        if len(self.history) > max_history:
            self.history = self.history[-max_history:]

    def has_context(self) -> bool:
        return bool(self.last_item_ids)


def is_followup(message: str) -> bool:
    normalized = message.strip().lower()
    if len(normalized) > 40:
        return False
    return any(term in normalized for term in FOLLOWUP_TERMS)
