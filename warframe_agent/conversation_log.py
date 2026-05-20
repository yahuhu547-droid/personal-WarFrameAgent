from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from . import config

LOG_PATH = config.DATA_DIR / "conversation_logs.jsonl"


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
    if not entry.timestamp:
        entry.timestamp = datetime.now().isoformat()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


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
