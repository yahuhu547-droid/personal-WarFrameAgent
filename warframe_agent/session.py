from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import config


FOLLOWUP_TERMS = [
    "那", "呢", "散件", "部件", "比昨天", "比上次",
    "还有", "其他的", "怎么样了", "现在呢", "多少了",
    "涨了吗", "跌了吗", "变了吗",
    "返回", "帮我看", "有没有", "只要",
    "哪个好", "哪些好", "推荐", "值不值", "划算吗",
    "能买吗", "要买吗", "入手吗", "出吗", "卖吗",
]


@dataclass
class SessionContext:
    last_item_ids: list[str] = field(default_factory=list)
    last_query_type: str | None = None
    last_intent: str | None = None
    last_riven_query: object | None = None
    last_riven_page: int = 1
    last_riven_page_size: int = 10
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

    def to_messages(self, limit: int | None = None, current_query: str | None = None) -> list[dict[str, str]]:
        """将历史对话转为 Ollama messages 格式（最近 N 轮）。

        当提供 current_query 时，按相关性（关键词重叠 + 时间衰减）排序历史，
        优先保留与当前查询相关的对话轮次。
        """
        if limit is None:
            limit = config.CONTEXT_WINDOW
        if not current_query or len(self.history) <= limit:
            recent = self.history[-limit:]
        else:
            scored = []
            query_tokens = set(current_query.lower().split())
            for i, (user_msg, assistant_reply) in enumerate(self.history):
                relevance = _relevance_score(query_tokens, user_msg + " " + assistant_reply)
                time_decay = math.exp(-0.1 * (len(self.history) - 1 - i))
                scored.append((relevance + time_decay, i, user_msg, assistant_reply))
            scored.sort(key=lambda x: -x[0])
            selected = sorted(scored[:limit], key=lambda x: x[1])
            recent = [(item[2], item[3]) for item in selected]
        messages = []
        for user_msg, assistant_reply in recent:
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": assistant_reply})
        return messages

    def has_context(self) -> bool:
        return bool(self.last_item_ids)


def _relevance_score(query_tokens: set[str], text: str) -> float:
    """简单子串匹配评分，不依赖 embedding，零开销。"""
    text_lower = text.lower()
    return sum(1 for token in query_tokens if token in text_lower)


def is_followup(message: str) -> bool:
    normalized = message.strip().lower()
    if len(normalized) > 40:
        return False
    return any(term in normalized for term in FOLLOWUP_TERMS)
