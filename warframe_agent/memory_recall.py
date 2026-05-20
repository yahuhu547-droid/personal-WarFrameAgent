from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .trading_memory import (
    MarketSnapshotMemory,
    PushHistoryMemory,
    RecommendationMemory,
    TradingMemoryDB,
    UserQueryMemory,
)

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,80}$")
_SENSITIVE_TEXT_RE = re.compile(
    r"(?im)\b(password|token|secret|api_key|apikey|authorization|cookie|app_secret|chat_id|whisper|player|seller|buyer)\b\s*[:=]\s*([^\s\r\n,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_FORBIDDEN_TEXT_RE = re.compile(r"(?i)(/w\s+\S+|Seller_RAW|Buyer_RAW|ignore\s+previous\s+instructions)")
_ROLE_PREFIX_RE = re.compile(r"(?im)\b(system|developer|assistant|user|tool)\s*:")
_XML_ROLE_TAG_RE = re.compile(r"(?i)</?\s*(system|developer|assistant|user|tool)\s*>")
_JSON_TOOL_KEY_RE = re.compile(r'(?i)"tool"\s*:\s*"([^"]+)"')
_CODE_FENCE_RE = re.compile(r"```")
_INTERNAL_KEYS = {
    "raw_message",
    "raw_query",
    "query_text",
    "assistant_reply",
    "prompt",
    "context",
    "orders",
    "whisper",
    "player",
    "seller",
    "buyer",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "app_secret",
    "chat_id",
}
_ALLOWED_PAYLOAD_KEYS = {
    "item_id",
    "sell_price",
    "buy_price",
    "spread",
    "spread_pct",
    "roi_pct",
    "profit",
    "priority",
    "source",
    "strategy",
    "ducats_per_plat",
    "volume_48h",
}


@dataclass(frozen=True)
class MemoryRecallItem:
    source: str
    record_id: int
    timestamp: str
    item_name: str
    score: float
    relevance: float
    recency: float
    salience: float
    summary: dict[str, Any]
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRecallResult:
    query_summary: dict[str, Any]
    items: list[MemoryRecallItem]
    score_breakdown: dict[str, Any]


class MemoryRecallService:
    def __init__(self, db: TradingMemoryDB):
        self.db = db

    def recall(
        self,
        query: str,
        *,
        item_name: str = "",
        intent: str = "",
        tool_names: list[str] | None = None,
        limit: int = 5,
    ) -> MemoryRecallResult:
        safe_item = _safe_identifier(item_name)
        safe_intent = _safe_identifier(intent)
        safe_tools = [_safe_identifier(name) for name in (tool_names or [])]
        safe_tools = [name for name in safe_tools if name]
        query_tokens = _query_tokens(query)
        candidates: list[MemoryRecallItem] = []

        for record in self.db.get_recent_user_queries(limit=100):
            candidates.append(self._score_user_query(record, query_tokens, safe_item, safe_intent, safe_tools))
        for record in self.db.get_market_snapshots(limit=100):
            candidates.append(self._score_market_snapshot(record, query_tokens, safe_item, safe_intent, safe_tools))
        for record in self.db.get_recommendations(limit=100):
            candidates.append(self._score_recommendation(record, query_tokens, safe_item, safe_intent, safe_tools))
        for record in self.db.get_push_history(limit=100):
            candidates.append(self._score_push(record, query_tokens, safe_item, safe_intent, safe_tools))

        candidates.sort(key=lambda item: (-item.score, item.source, item.record_id))
        items = candidates[: max(0, limit)]
        return MemoryRecallResult(
            query_summary={
                "item_name": safe_item,
                "intent": safe_intent,
                "tool_names": safe_tools,
            },
            items=items,
            score_breakdown={
                "count": len(items),
                "max_score": max((item.score for item in items), default=0.0),
                "weights": {"relevance": 0.6, "recency": 0.2, "salience": 0.2},
            },
        )

    def format_for_model(self, result: MemoryRecallResult, max_items: int = 5) -> str:
        if not result.items:
            return ""
        lines = ["[记忆召回摘要]"]
        for index, item in enumerate(result.items[:max_items], start=1):
            facts = ", ".join(f"{key}={value}" for key, value in item.summary.items() if value not in (None, "", []))
            trace = ", ".join(f"{key}={value}" for key, value in item.trace.items() if value not in (None, "", []))
            lines.append(
                f"{index}. source={item.source} item={item.item_name or 'none'} "
                f"score={item.score:.3f} facts=({facts}) trace=({trace})"
            )
        return _sanitize_text("\n".join(lines), max_chars=3000)

    def _score_user_query(
        self,
        record: UserQueryMemory,
        query_tokens: set[str],
        item_name: str,
        intent: str,
        tool_names: list[str],
    ) -> MemoryRecallItem:
        metadata = _safe_mapping(record.metadata, allowed_keys={
            "storage_kind",
            "source",
            "schema_version",
            "context_item_ids",
            "context_count",
            "tool_names",
            "tool_count",
            "tool_ok_count",
            "item_source",
        })
        summary = {
            "intent": _safe_identifier(record.intent),
            "item_name": _safe_identifier(record.item_name),
            "context_count": metadata.get("context_count", 0),
            "tool_names": metadata.get("tool_names", []),
        }
        return self._build_item(
            source="user_query",
            record_id=record.id,
            timestamp=record.timestamp,
            record_item=_safe_identifier(record.item_name),
            record_intent=_safe_identifier(record.intent),
            record_tools=metadata.get("tool_names") if isinstance(metadata.get("tool_names"), list) else [],
            query_tokens=query_tokens,
            requested_item=item_name,
            requested_intent=intent,
            requested_tools=tool_names,
            salience=0.45 if metadata.get("tool_ok_count", 0) else 0.25,
            salience_reason="prior_tool_success" if metadata.get("tool_ok_count", 0) else "prior_query_summary",
            summary=summary,
        )

    def _score_market_snapshot(
        self,
        record: MarketSnapshotMemory,
        query_tokens: set[str],
        item_name: str,
        intent: str,
        tool_names: list[str],
    ) -> MemoryRecallItem:
        payload = _safe_mapping(record.payload, allowed_keys=_ALLOWED_PAYLOAD_KEYS)
        payload_source = payload.pop("source", None)
        summary = {"source": _sanitize_text(record.source, 80), **payload}
        if payload_source:
            summary["payload_source"] = payload_source
        return self._build_item(
            source="market_snapshot",
            record_id=record.id,
            timestamp=record.timestamp,
            record_item=_safe_identifier(record.item_name),
            record_intent="price_check",
            record_tools=["query_price", "price_trend"],
            query_tokens=query_tokens,
            requested_item=item_name,
            requested_intent=intent,
            requested_tools=tool_names,
            salience=0.5,
            salience_reason="market_snapshot",
            summary=summary,
        )

    def _score_recommendation(
        self,
        record: RecommendationMemory,
        query_tokens: set[str],
        item_name: str,
        intent: str,
        tool_names: list[str],
    ) -> MemoryRecallItem:
        payload = _safe_mapping(record.payload, allowed_keys=_ALLOWED_PAYLOAD_KEYS)
        priority = payload.get("priority") if isinstance(payload.get("priority"), int) else None
        salience = 1.0 if priority == 1 else 0.75
        summary = {
            "recommendation_type": _safe_identifier(record.recommendation_type),
            "reason": _sanitize_text(record.reason, 160),
            **payload,
        }
        return self._build_item(
            source="recommendation",
            record_id=record.id,
            timestamp=record.timestamp,
            record_item=_safe_identifier(record.item_name),
            record_intent=_recommendation_intent(record.recommendation_type),
            record_tools=["investment_advisor", "market_expert"],
            query_tokens=query_tokens,
            requested_item=item_name,
            requested_intent=intent,
            requested_tools=tool_names,
            salience=salience,
            salience_reason="high_priority_recommendation" if priority == 1 else "recommendation",
            summary=summary,
        )

    def _score_push(
        self,
        record: PushHistoryMemory,
        query_tokens: set[str],
        item_name: str,
        intent: str,
        tool_names: list[str],
    ) -> MemoryRecallItem:
        metadata = _safe_mapping(record.metadata, allowed_keys=_ALLOWED_PAYLOAD_KEYS)
        priority = metadata.get("priority") if isinstance(metadata.get("priority"), int) else None
        summary = {
            "push_type": _safe_identifier(record.push_type),
            "metadata": metadata,
        }
        return self._build_item(
            source="push_history",
            record_id=record.id,
            timestamp=record.timestamp,
            record_item=_safe_identifier(record.item_name),
            record_intent=_recommendation_intent(record.push_type),
            record_tools=["scan_favorites", "set_alert"],
            query_tokens=query_tokens,
            requested_item=item_name,
            requested_intent=intent,
            requested_tools=tool_names,
            salience=0.9 if priority == 1 else 0.65,
            salience_reason="important_push" if priority == 1 else "push_history",
            summary=summary,
        )

    def _build_item(
        self,
        *,
        source: str,
        record_id: int,
        timestamp: str,
        record_item: str,
        record_intent: str,
        record_tools: list[str],
        query_tokens: set[str],
        requested_item: str,
        requested_intent: str,
        requested_tools: list[str],
        salience: float,
        salience_reason: str,
        summary: dict[str, Any],
    ) -> MemoryRecallItem:
        relevance, trace = _relevance_trace(
            record_item=record_item,
            record_intent=record_intent,
            record_tools=record_tools,
            query_tokens=query_tokens,
            requested_item=requested_item,
            requested_intent=requested_intent,
            requested_tools=requested_tools,
        )
        recency = _recency_score(timestamp)
        score = round((relevance * 0.6) + (recency * 0.2) + (min(max(salience, 0.0), 1.0) * 0.2), 4)
        trace.update({
            "recency": round(recency, 4),
            "salience": round(salience, 4),
            "salience_reason": salience_reason,
        })
        return MemoryRecallItem(
            source=source,
            record_id=record_id,
            timestamp=timestamp,
            item_name=record_item,
            score=score,
            relevance=round(relevance, 4),
            recency=round(recency, 4),
            salience=round(salience, 4),
            summary=_safe_mapping(summary),
            trace=_safe_mapping(trace),
        )


def _relevance_trace(
    *,
    record_item: str,
    record_intent: str,
    record_tools: list[str],
    query_tokens: set[str],
    requested_item: str,
    requested_intent: str,
    requested_tools: list[str],
) -> tuple[float, dict[str, Any]]:
    item_match = bool(requested_item and record_item == requested_item)
    token_match = bool(record_item and record_item in query_tokens)
    intent_match = bool(requested_intent and record_intent == requested_intent)
    tool_overlap = sorted(set(record_tools) & set(requested_tools))
    relevance = 0.15
    if item_match:
        relevance += 0.55
    elif token_match:
        relevance += 0.35
    if intent_match:
        relevance += 0.2
    if tool_overlap:
        relevance += 0.1
    return min(relevance, 1.0), {
        "item_match": item_match,
        "token_match": token_match,
        "intent_match": intent_match,
        "tool_match": tool_overlap,
    }


def _recency_score(timestamp: str, decay_lambda: float = 0.02) -> float:
    try:
        parsed = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return 0.0
    if parsed.tzinfo is None:
        now = datetime.now()
    else:
        now = datetime.now(timezone.utc)
    hours_ago = max(0.0, (now - parsed).total_seconds() / 3600)
    return math.exp(-decay_lambda * hours_ago)


def _query_tokens(query: str) -> set[str]:
    text = str(query or "").lower().replace(" ", "_").replace("-", "_")
    tokens = {_safe_identifier(token) for token in re.split(r"[^a-z0-9_]+", text) if token}
    compact = _safe_identifier(text)
    if compact:
        tokens.add(compact)
    return {token for token in tokens if token}


def _recommendation_intent(value: str) -> str:
    normalized = _safe_identifier(value)
    if normalized in {"opportunity", "investment", "goal"}:
        return "investment_advice"
    if normalized in {"baro", "baro_recommendation"}:
        return "baro_recommendation"
    return normalized or "trading_tool"


def _safe_identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized if _SAFE_IDENTIFIER_RE.fullmatch(normalized) else ""


def _safe_mapping(value: Any, allowed_keys: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        key_text = _safe_identifier(str(key))
        if not key_text or key_text in _INTERNAL_KEYS:
            continue
        if allowed_keys is not None and key_text not in allowed_keys:
            continue
        result[key_text] = _safe_value(item)
    return result


def _safe_value(value: Any) -> Any:
    if isinstance(value, str):
        identifier = _safe_identifier(value)
        if identifier and identifier == value.strip().lower().replace("-", "_").replace(" ", "_"):
            return identifier
        return _sanitize_text(value, 180)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        return [_safe_value(item) for item in value[:5] if _safe_value(item) not in ("", None)]
    if isinstance(value, dict):
        return _safe_mapping(value)
    return _sanitize_text(str(value), 120)


def _sanitize_text(value: Any, max_chars: int = 300) -> str:
    text = str(value or "")
    text = _BEARER_RE.sub("[REDACTED]", text)
    text = _SENSITIVE_TEXT_RE.sub("[REDACTED]", text)
    text = _FORBIDDEN_TEXT_RE.sub("[REDACTED]", text)
    text = _ROLE_PREFIX_RE.sub(lambda match: f"data_role_{match.group(1).lower()} =", text)
    text = _XML_ROLE_TAG_RE.sub(lambda match: f"[data-{match.group(1).lower()}-tag]", text)
    text = _JSON_TOOL_KEY_RE.sub(lambda match: f'"data_tool"="{match.group(1)}"', text)
    text = _CODE_FENCE_RE.sub("'''", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    if len(text) > max_chars:
        return f"{text[:max_chars]}... [len={len(text)}]"
    return text
