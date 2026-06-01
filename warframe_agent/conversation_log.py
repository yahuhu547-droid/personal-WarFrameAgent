from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config

LOG_PATH = config.DATA_DIR / "conversation_logs.jsonl"
_SAFE_CONTEXT_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,80}$")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_SENSITIVE_KV_RE = re.compile(
    r"(?i)\b(password|token|secret|api[_-]?key|apikey|authorization|cookie|app_secret|chat_id)\b\s*[:=]\s*([^\s\r\n,;]+)"
)
_WHISPER_RE = re.compile(r"(?i)/w\s+\S+[^\r\n]*")
_MARKET_URL_RE = re.compile(r"https?://(?:www\.)?warframe\.market/\S+")
_PLAYER_LABEL_RE = re.compile(r"(最低卖家|当前最低卖家|最低买家|当前最高买家|卖家|买家|购买私聊|出售私聊)\s*[:：]\s*[^，,\r\n]+")
_INTERNAL_TOOL_KEYS = {
    "__message",
    "message_context",
    "prompt",
    "raw_chat",
    "raw_arguments",
    "arguments",
    "content",
    "display_content",
    "model_context",
    "result_summary",
    "final_answer",
    "assistant_reply",
    "user_message",
    "context",
}
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
)


@dataclass
class ConversationEntry:
    user_message: str
    assistant_reply: str
    tool_calls: list[dict] | None = None
    contexts: list[str] | None = None
    timestamp: str = ""
    rating: int | None = None  # 1-5, None = unrated
    session_id: str = ""


def log_conversation(entry: ConversationEntry) -> None:
    """追加一条对话记录到 JSONL 文件。"""
    timestamp = entry.timestamp or datetime.now().isoformat()
    safe_entry = _safe_conversation_entry(entry, timestamp=timestamp)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(safe_entry), ensure_ascii=False) + "\n")


def load_conversations(limit: int = 0) -> list[ConversationEntry]:
    """加载对话记录。limit=0 表示全部。"""
    if not LOG_PATH.exists():
        return []
    entries = []
    with LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entries.append(ConversationEntry(**data))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue
    if limit > 0:
        entries = entries[-limit:]
    return entries


def query_tool_call_history(
    limit: int = 50,
    tool_name: str | None = None,
    ok: bool | None = None,
    session_id: str | None = None,
) -> list[dict]:
    if limit <= 0:
        return []

    records = []
    for entry in reversed(load_conversations()):
        if session_id is not None and entry.session_id != session_id:
            continue
        if not isinstance(entry.tool_calls, list):
            continue
        for tool_call in reversed(entry.tool_calls):
            if not isinstance(tool_call, dict):
                continue
            if tool_name is not None and tool_call.get("tool_name") != tool_name:
                continue
            if ok is not None and tool_call.get("ok") is not ok:
                continue
            records.append({
                "tool_timestamp": tool_call.get("timestamp"),
                "tool_name": tool_call.get("tool_name"),
                "args_summary": tool_call.get("args_summary"),
                "ok": tool_call.get("ok"),
                "error": tool_call.get("error"),
                "duration_ms": tool_call.get("duration_ms"),
                "conversation_timestamp": entry.timestamp,
                "session_id": entry.session_id,
                "contexts": entry.contexts,
            })
            if len(records) >= limit:
                return records
    return records


def query_tool_call_stats(
    limit: int = 500,
    tool_name: str | None = None,
    session_id: str | None = None,
) -> dict:
    history = query_tool_call_history(limit=limit, tool_name=tool_name, session_id=session_id)
    stats = _empty_tool_call_stats()
    if not history:
        return stats

    durations = []
    buckets: dict[str, dict] = {}
    bucket_durations: dict[str, list[float]] = {}

    for record in history:
        name = record.get("tool_name") or "unknown"
        bucket = buckets.setdefault(name, _empty_tool_bucket())
        bucket_durations.setdefault(name, [])

        stats["total_calls"] += 1
        bucket["total_calls"] += 1

        ok = record.get("ok")
        if ok is True:
            stats["success_count"] += 1
            bucket["success_count"] += 1
        elif ok is False:
            stats["failure_count"] += 1
            bucket["failure_count"] += 1
        else:
            stats["unknown_count"] += 1
            bucket["unknown_count"] += 1

        duration = record.get("duration_ms")
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            durations.append(float(duration))
            bucket_durations[name].append(float(duration))

    stats["success_rate"] = _success_rate(stats)
    stats["duration_ms"] = _duration_stats(durations)
    stats["by_tool"] = {
        name: _finalize_tool_bucket(bucket, bucket_durations[name])
        for name, bucket in sorted(buckets.items())
    }
    stats["top_tools"] = [
        {"tool_name": name, "total_calls": bucket["total_calls"]}
        for name, bucket in sorted(buckets.items(), key=lambda item: (-item[1]["total_calls"], item[0]))
    ]
    return stats


def _safe_conversation_entry(entry: ConversationEntry, *, timestamp: str) -> ConversationEntry:
    return replace(
        entry,
        user_message=_safe_text_summary("user", entry.user_message),
        assistant_reply=_safe_text_summary("assistant", entry.assistant_reply),
        tool_calls=_safe_tool_calls(entry.tool_calls),
        contexts=_safe_contexts(entry.contexts),
        timestamp=timestamp,
    )


def _safe_text_summary(role: str, text: str, *, max_chars: int = 500, max_lines: int = 8) -> str:
    sanitized = _sanitize_text(text)
    lines = sanitized.splitlines()[:max_lines]
    compact = "\n".join(line.strip() for line in lines if line.strip())
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + " [TRUNCATED]"
    return f"summary:v1 role={role} {compact}" if compact else f"summary:v1 role={role} empty"


def _sanitize_text(value: Any) -> str:
    text = _CONTROL_CHAR_RE.sub(" ", str(value or ""))
    text = _WHISPER_RE.sub("[REDACTED_WHISPER]", text)
    text = _MARKET_URL_RE.sub("[REDACTED_MARKET_URL]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _SENSITIVE_KV_RE.sub("[REDACTED_SECRET]", text)
    text = _PLAYER_LABEL_RE.sub(lambda match: f"{match.group(1)}: [REDACTED_PLAYER]", text)
    return text


def _safe_contexts(contexts: list[str] | None) -> list[str] | None:
    if not isinstance(contexts, list):
        return None
    safe = []
    for context in contexts:
        value = str(context or "").strip().lower()
        if not _SAFE_CONTEXT_RE.match(value):
            continue
        if _contains_sensitive_text(value):
            continue
        safe.append(value)
    return safe or None


def _safe_tool_calls(tool_calls: list[dict] | None) -> list[dict] | None:
    if not isinstance(tool_calls, list):
        return None
    safe_calls = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        safe_call = _safe_mapping(call)
        if safe_call:
            safe_calls.append(safe_call)
    return safe_calls or None


def _safe_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for key, value in mapping.items():
        key_text = str(key)
        if key_text in _INTERNAL_TOOL_KEYS:
            continue
        if _is_sensitive_key(key_text):
            safe[key_text] = "[REDACTED]"
            continue
        safe[key_text] = _safe_value(value)
    return safe


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _safe_mapping(value)
    if isinstance(value, list):
        return [_safe_value(item) for item in value if not _should_drop_value(item)]
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _sanitize_text(value)


def _should_drop_value(value: Any) -> bool:
    return isinstance(value, str) and _contains_sensitive_text(value)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _SENSITIVE_KEY_TOKENS)


def _contains_sensitive_text(text: str) -> bool:
    return bool(_WHISPER_RE.search(text) or _MARKET_URL_RE.search(text) or _SENSITIVE_KV_RE.search(text) or _BEARER_RE.search(text))


def _empty_tool_call_stats() -> dict:
    return {
        "total_calls": 0,
        "success_count": 0,
        "failure_count": 0,
        "unknown_count": 0,
        "success_rate": 0.0,
        "duration_ms": _duration_stats([]),
        "by_tool": {},
        "top_tools": [],
    }


def _empty_tool_bucket() -> dict:
    return {
        "total_calls": 0,
        "success_count": 0,
        "failure_count": 0,
        "unknown_count": 0,
    }


def _finalize_tool_bucket(bucket: dict, durations: list[float]) -> dict:
    return {
        "total_calls": bucket["total_calls"],
        "success_count": bucket["success_count"],
        "failure_count": bucket["failure_count"],
        "unknown_count": bucket["unknown_count"],
        "success_rate": _success_rate(bucket),
        "duration_ms": _duration_stats(durations),
    }


def _success_rate(bucket: dict) -> float:
    total = bucket["total_calls"]
    if total <= 0:
        return 0.0
    return round(bucket["success_count"] / total, 4)


def _duration_stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "avg": None, "min": None, "max": None}
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 2),
        "min": min(values),
        "max": max(values),
    }
