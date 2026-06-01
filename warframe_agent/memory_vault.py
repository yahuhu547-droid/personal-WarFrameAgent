from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from .conversation_log import ConversationEntry
from .trading_memory import TradingMemoryDB

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_MARKET_PROFILE_RE = re.compile(r"https?://(?:www\.)?warframe\.market/profile/\S+")
_WHISPER_RE = re.compile(r"(?i)/w\s+\S+[^\r\n]*")
_SENSITIVE_KV_RE = re.compile(
    r"(?i)\b(password|token|secret|api[_-]?key|apikey|authorization|cookie|app_secret|chat_id|profile_url)\b\s*[:=]\s*([^\s\r\n,;]+)"
)
_SECRET_LIKE_RE = re.compile(r"(?i)\b(?:secret|token|password|api[_-]?key)[-_:=][^\s,;]+")
_PLAYER_HANDLE_RE = re.compile(r"(?i)\b(?:Seller|Buyer|Player)[A-Za-z0-9_\-]*\b")
_PROMPT_INJECTION_RE = re.compile(r"(?i)\b(ignore|forget|override)\s+(previous|prior|all)\s+instructions\b")
_ROLE_PREFIX_RE = re.compile(r"(?im)\b(system|developer|assistant|user|tool)\s*:")
_XML_ROLE_TAG_RE = re.compile(r"(?i)</?\s*(system|developer|assistant|user|tool)\s*>")
_CODE_FENCE_RE = re.compile(r"```")
_SAFE_IDENTIFIER_RE = re.compile(r"[^a-z0-9_]+")
_SENSITIVE_KEY_TOKENS = (
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "app_secret",
    "chat_id",
    "profile",
    "whisper",
    "seller",
    "buyer",
    "player",
    "raw",
    "message",
    "reply",
    "prompt",
    "arguments",
    "result",
    "content",
)
_ALLOWED_MARKET_KEYS = {
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
_ALLOWED_RECOMMENDATION_KEYS = _ALLOWED_MARKET_KEYS | {
    "event_type",
    "market_id",
    "best_buy_price",
    "best_sell_price",
    "rank",
    "max_rank",
    "item_kind",
}
_ALLOWED_PUSH_KEYS = {
    "source",
    "item_id",
    "priority",
    "action_suggestion",
    "suggestion_type",
    "event_type",
}
_ALLOWED_OUTCOME_KEYS = {
    "source",
    "strategy",
    "item_id",
    "required_quantity",
    "total_cost",
    "total_revenue",
    "profit",
    "roi_pct",
    "risk_level",
    "profit_bucket",
    "plan_signature",
    "turnaround_days",
    "budget_spent",
    "quantity",
    "confidence",
    "personal_score",
    "market_score",
}


@dataclass(frozen=True)
class MemoryVaultEntry:
    source: str
    record_id: str
    timestamp: str
    item_name: str
    title: str
    summary: dict[str, Any]
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MemoryVaultSnapshot:
    generated_at: str
    entries: tuple[MemoryVaultEntry, ...]
    source_counts: dict[str, int]
    markdown_preview: str

    @property
    def total(self) -> int:
        return len(self.entries)


def build_memory_vault_snapshot(
    *,
    db: TradingMemoryDB | None,
    conversations: Iterable[ConversationEntry] | None = None,
    limit: int = 50,
) -> MemoryVaultSnapshot:
    safe_limit = max(0, min(int(limit or 0), 200))
    entries: list[MemoryVaultEntry] = []
    if db is not None:
        entries.extend(_entries_from_db(db, per_source_limit=max(safe_limit, 1)))
    entries.extend(_entries_from_conversations(conversations or []))
    entries.sort(key=lambda entry: (entry.timestamp, entry.source, entry.record_id), reverse=True)
    entries = entries[:safe_limit]
    source_counts = _source_counts(entries)
    markdown_preview = format_memory_vault_markdown(entries, source_counts)
    return MemoryVaultSnapshot(
        generated_at=datetime.now(timezone.utc).isoformat(),
        entries=tuple(entries),
        source_counts=source_counts,
        markdown_preview=markdown_preview,
    )


def memory_vault_snapshot_to_api(snapshot: MemoryVaultSnapshot) -> dict[str, Any]:
    return {
        "generated_at": snapshot.generated_at,
        "total": snapshot.total,
        "source_counts": dict(snapshot.source_counts),
        "entries": [_entry_to_api(entry) for entry in snapshot.entries],
        "markdown_preview": snapshot.markdown_preview,
    }


def format_memory_vault_markdown(
    entries: Iterable[MemoryVaultEntry],
    source_counts: dict[str, int] | None = None,
    *,
    max_chars: int = 4000,
) -> str:
    safe_entries = list(entries)
    counts = source_counts if source_counts is not None else _source_counts(safe_entries)
    lines = ["# Memory Vault Snapshot", "", f"- total={len(safe_entries)}"]
    for source, count in sorted(counts.items()):
        lines.append(f"- {source}={count}")
    if safe_entries:
        lines.extend(["", "## Entries"])
    for entry in safe_entries:
        facts = _format_facts(entry.summary)
        title = _safe_text(entry.title, max_chars=120)
        item = entry.item_name or "none"
        line = f"- [{entry.source}] {item} {title}"
        if facts:
            line += f" facts: {facts}"
        lines.append(line)
    return _safe_text("\n".join(lines), max_chars=max_chars)


def _entries_from_db(db: TradingMemoryDB, *, per_source_limit: int) -> list[MemoryVaultEntry]:
    entries: list[MemoryVaultEntry] = []
    for record in db.get_recent_user_queries(limit=per_source_limit):
        metadata = _safe_mapping(
            record.metadata,
            allowed_keys={
                "storage_kind",
                "source",
                "schema_version",
                "context_item_ids",
                "context_count",
                "tool_names",
                "tool_count",
                "tool_ok_count",
                "item_source",
            },
        )
        entries.append(
            _entry(
                source="user_query",
                record_id=record.id,
                timestamp=record.timestamp,
                item_name=record.item_name,
                title="prior query summary",
                summary={
                    "intent": _safe_identifier(record.intent),
                    "item_name": _safe_identifier(record.item_name),
                    "context_count": metadata.get("context_count"),
                    "tool_names": metadata.get("tool_names"),
                    "tool_ok_count": metadata.get("tool_ok_count"),
                },
                tags=["query", record.intent, record.item_name],
            )
        )
    for record in db.get_market_snapshots(limit=per_source_limit):
        payload = _safe_mapping(record.payload, allowed_keys=_ALLOWED_MARKET_KEYS)
        entries.append(
            _entry(
                source="market_snapshot",
                record_id=record.id,
                timestamp=record.timestamp,
                item_name=record.item_name,
                title=f"market snapshot from {_safe_text(record.source, max_chars=80)}",
                summary={"source": _safe_text(record.source, max_chars=80), **payload},
                tags=["market", record.source, record.item_name],
            )
        )
    for record in db.get_recommendations(limit=per_source_limit):
        payload = _safe_mapping(record.payload, allowed_keys=_ALLOWED_RECOMMENDATION_KEYS)
        entries.append(
            _entry(
                source="recommendation",
                record_id=record.id,
                timestamp=record.timestamp,
                item_name=record.item_name,
                title=f"{_safe_identifier(record.recommendation_type) or 'recommendation'} recommendation",
                summary={
                    "recommendation_type": _safe_identifier(record.recommendation_type),
                    "reason": _safe_text(record.reason, max_chars=160),
                    **payload,
                },
                tags=["recommendation", record.recommendation_type, record.item_name],
            )
        )
    for record in db.get_push_history(limit=per_source_limit):
        metadata = _safe_mapping(record.metadata, allowed_keys=_ALLOWED_PUSH_KEYS)
        entries.append(
            _entry(
                source="push_history",
                record_id=record.id,
                timestamp=record.timestamp,
                item_name=record.item_name,
                title=f"{_safe_identifier(record.push_type) or 'push'} push",
                summary={
                    "push_type": _safe_identifier(record.push_type),
                    **metadata,
                },
                tags=["push", record.push_type, record.item_name],
            )
        )
    for record in db.get_opportunity_outcomes(limit=per_source_limit):
        metadata = record.metadata if isinstance(record.metadata, dict) else {}
        safe_summary = metadata.get("safe_summary") if isinstance(metadata.get("safe_summary"), dict) else {}
        summary = {
            "source": _safe_identifier(record.source),
            "strategy": _safe_identifier(record.strategy),
            "status": _safe_identifier(record.status),
            "expected_profit": record.expected_profit,
            "actual_profit": record.actual_profit,
            "feedback": _safe_identifier(record.user_feedback),
            **_safe_mapping(safe_summary, allowed_keys=_ALLOWED_OUTCOME_KEYS),
            **_safe_mapping(metadata, allowed_keys=_ALLOWED_OUTCOME_KEYS),
        }
        entries.append(
            _entry(
                source="opportunity_outcome",
                record_id=record.id,
                timestamp=record.timestamp,
                item_name=record.item_name,
                title=f"{_safe_identifier(record.status) or 'outcome'} opportunity outcome",
                summary=summary,
                tags=["outcome", record.source, record.strategy, record.status, record.item_name],
            )
        )
    return entries


def _entries_from_conversations(conversations: Iterable[ConversationEntry]) -> list[MemoryVaultEntry]:
    entries: list[MemoryVaultEntry] = []
    for index, entry in enumerate(conversations):
        tool_names = _safe_tool_names(entry.tool_calls)
        contexts = _safe_identifier_list(entry.contexts, limit=5)
        item_name = contexts[0] if contexts else ""
        summary = {
            "context_count": len(contexts),
            "tool_count": len(tool_names),
            "tool_names": tool_names,
        }
        if _safe_identifier(entry.session_id):
            summary["session_id"] = _safe_identifier(entry.session_id)
        entries.append(
            _entry(
                source="conversation_log",
                record_id=index,
                timestamp=entry.timestamp,
                item_name=item_name,
                title="conversation summary",
                summary=summary,
                tags=["conversation", *contexts, *tool_names],
            )
        )
    return entries


def _entry(
    *,
    source: str,
    record_id: Any,
    timestamp: Any,
    item_name: Any,
    title: Any,
    summary: dict[str, Any],
    tags: Iterable[Any] = (),
) -> MemoryVaultEntry:
    safe_source = _safe_identifier(source) or "unknown"
    safe_item = _safe_identifier(item_name)
    return MemoryVaultEntry(
        source=safe_source,
        record_id=f"{safe_source}:{_safe_text(record_id, max_chars=64)}",
        timestamp=_safe_text(timestamp, max_chars=80),
        item_name=safe_item,
        title=_safe_text(title, max_chars=120),
        summary=_compact_summary(summary),
        tags=tuple(_safe_identifier_list(tags, limit=12)),
    )


def _entry_to_api(entry: MemoryVaultEntry) -> dict[str, Any]:
    return {
        "source": entry.source,
        "record_id": entry.record_id,
        "timestamp": entry.timestamp,
        "item_name": entry.item_name,
        "title": entry.title,
        "summary": dict(entry.summary),
        "tags": list(entry.tags),
    }


def _compact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in summary.items():
        key_text = str(key or "")
        if _is_sensitive_key(key_text):
            continue
        safe_key = _safe_identifier(key_text)
        if not safe_key:
            continue
        safe_value = _safe_value(value)
        if safe_value in ("", [], {}, None):
            continue
        compact[safe_key] = safe_value
    return compact


def _safe_mapping(mapping: Any, *, allowed_keys: set[str]) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in mapping.items():
        key_text = str(key or "")
        if key_text not in allowed_keys or _is_sensitive_key(key_text):
            continue
        safe_value = _safe_value(value)
        if safe_value in ("", [], {}, None):
            continue
        safe[key_text] = safe_value
    return safe


def _safe_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, str):
        return _safe_text(value, max_chars=240)
    if isinstance(value, list):
        safe_list = [_safe_value(item) for item in value[:10]]
        return [item for item in safe_list if item not in ("", [], {}, None)]
    if isinstance(value, tuple):
        safe_list = [_safe_value(item) for item in list(value)[:10]]
        return [item for item in safe_list if item not in ("", [], {}, None)]
    if isinstance(value, dict):
        return {}
    return _safe_text(value, max_chars=120)


def _safe_text(value: Any, *, max_chars: int = 240) -> str:
    text = _CONTROL_CHAR_RE.sub(" ", str(value or ""))
    text = _WHISPER_RE.sub("[REDACTED]", text)
    text = _MARKET_PROFILE_RE.sub("[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _SENSITIVE_KV_RE.sub("[REDACTED]", text)
    text = _SECRET_LIKE_RE.sub("[REDACTED]", text)
    text = _PLAYER_HANDLE_RE.sub("[REDACTED]", text)
    text = _PROMPT_INJECTION_RE.sub("[REDACTED]", text)
    text = _ROLE_PREFIX_RE.sub(lambda match: f"data_role_{match.group(1).lower()}_", text)
    text = _XML_ROLE_TAG_RE.sub(lambda match: f"data_role_{match.group(1).lower()}_", text)
    text = _CODE_FENCE_RE.sub("'''", text)
    compact = " ".join(part.strip() for part in text.split() if part.strip())
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + " [TRUNCATED]"
    return compact


def _safe_identifier(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    text = _SAFE_IDENTIFIER_RE.sub("_", text).strip("_")
    if not text or _contains_sensitive_text(text):
        return ""
    return text[:80]


def _safe_identifier_list(values: Iterable[Any] | None, *, limit: int) -> list[str]:
    if values is None:
        return []
    safe: list[str] = []
    for value in values:
        item = _safe_identifier(value)
        if item and item not in safe:
            safe.append(item)
        if len(safe) >= limit:
            break
    return safe


def _safe_tool_names(tool_calls: list[dict] | None) -> list[str]:
    if not isinstance(tool_calls, list):
        return []
    names = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        name = _safe_identifier(call.get("tool_name"))
        if name and name not in names:
            names.append(name)
    return names[:8]


def _format_facts(summary: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in summary.items():
        if value in ("", [], {}, None):
            continue
        if isinstance(value, list):
            value_text = "[" + ",".join(_safe_text(item, max_chars=60) for item in value[:5]) + "]"
        else:
            value_text = _safe_text(value, max_chars=80)
        parts.append(f"{key}={value_text}")
    return ", ".join(parts[:8])


def _source_counts(entries: Iterable[MemoryVaultEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.source] = counts.get(entry.source, 0) + 1
    return counts


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _SENSITIVE_KEY_TOKENS)


def _contains_sensitive_text(text: str) -> bool:
    return (
        bool(_WHISPER_RE.search(text))
        or bool(_MARKET_PROFILE_RE.search(text))
        or bool(_SENSITIVE_KV_RE.search(text))
        or bool(_SECRET_LIKE_RE.search(text))
        or bool(_BEARER_RE.search(text))
    )
