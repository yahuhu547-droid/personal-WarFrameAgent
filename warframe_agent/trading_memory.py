from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import config

TRADING_MEMORY_DB_PATH = config.DATA_DIR / "trading_memory.db"
TRADING_MEMORY_RETENTION_DAYS = 180
USER_QUERY_SUMMARY_VERSION = 1
USER_QUERY_SUMMARY_INTENTS = {
    "price_check",
    "trade_buy",
    "trade_sell",
    "spread_check",
    "price_trend",
    "price_compare",
    "completed_trade_buy",
    "completed_trade_sell",
    "riven_search",
    "baro_recommendation",
    "event_query",
    "watchlist_scan",
    "alert_create",
    "set_profit_scan",
    "mod_flip_scan",
    "investment_advice",
    "trading_tool",
    "unknown",
}
USER_QUERY_SUMMARY_TOOL_NAMES = {
    "query_price",
    "price_trend",
    "query_set",
    "query_missing_parts",
    "scan_favorites",
    "set_alert",
    "mod_flipper",
    "set_profit",
    "investment_advisor",
    "query_events",
    "riven_search",
}
USER_QUERY_SUMMARY_ITEM_SOURCES = {"contexts", "tool_args_resolved", "none", "mixed"}
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,80}$")


@dataclass(frozen=True)
class UserQueryMemory:
    id: int
    timestamp: str
    query_text: str
    intent: str
    item_name: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MarketSnapshotMemory:
    id: int
    timestamp: str
    item_name: str
    source: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class RecommendationMemory:
    id: int
    timestamp: str
    item_name: str
    recommendation_type: str
    reason: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class PushHistoryMemory:
    id: int
    timestamp: str
    push_type: str
    item_name: str
    message: str
    metadata: dict[str, Any]


class TradingMemoryDB:
    def __init__(self, db_path: Path = TRADING_MEMORY_DB_PATH, read_only: bool = False):
        self.db_path = db_path
        self.read_only = read_only
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        if not read_only:
            self._ensure_tables()

    @classmethod
    def open_readonly_if_exists(cls, db_path: Path = TRADING_MEMORY_DB_PATH) -> "TradingMemoryDB | None":
        if not db_path.exists():
            return None
        return cls(db_path=db_path, read_only=True)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            if self.read_only:
                uri = self.db_path.as_posix()
                self._conn = sqlite3.connect(f"file:{uri}?mode=ro", uri=True, check_same_thread=False)
            else:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
                self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _ensure_tables(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "CREATE TABLE IF NOT EXISTS user_queries ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  timestamp TEXT NOT NULL,"
                "  query_text TEXT NOT NULL,"
                "  intent TEXT NOT NULL,"
                "  item_name TEXT NOT NULL,"
                "  metadata_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS market_snapshots ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  timestamp TEXT NOT NULL,"
                "  item_name TEXT NOT NULL,"
                "  source TEXT NOT NULL,"
                "  payload_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS recommendations ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  timestamp TEXT NOT NULL,"
                "  item_name TEXT NOT NULL,"
                "  recommendation_type TEXT NOT NULL,"
                "  reason TEXT NOT NULL,"
                "  payload_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS push_history ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  timestamp TEXT NOT NULL,"
                "  push_type TEXT NOT NULL,"
                "  item_name TEXT NOT NULL,"
                "  message TEXT NOT NULL,"
                "  metadata_json TEXT NOT NULL"
                ")"
            )
            for table in ["user_queries", "market_snapshots", "recommendations", "push_history"]:
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_timestamp ON {table} (timestamp)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_queries_item_timestamp "
                "ON user_queries (item_name, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_market_snapshots_item_timestamp "
                "ON market_snapshots (item_name, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_market_snapshots_source_timestamp "
                "ON market_snapshots (source, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_recommendations_item_timestamp "
                "ON recommendations (item_name, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_recommendations_type_timestamp "
                "ON recommendations (recommendation_type, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_push_history_item_timestamp "
                "ON push_history (item_name, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_push_history_type_timestamp "
                "ON push_history (push_type, timestamp)"
            )
            conn.commit()

    def record_user_query(
        self,
        query_text: str,
        intent: str = "",
        item_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        return self._insert(
            "INSERT INTO user_queries (timestamp, query_text, intent, item_name, metadata_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), query_text, intent, item_name, _to_json(metadata)),
        )

    def record_user_query_summary(
        self,
        intent: str = "",
        item_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        safe_intent = _normalize_user_query_intent(intent)
        safe_item_name = _safe_memory_identifier(item_name)
        safe_metadata = _sanitize_user_query_summary_metadata(metadata)
        query_text = _build_user_query_summary_text(safe_intent, safe_item_name, safe_metadata)
        return self.record_user_query(
            query_text,
            intent=safe_intent,
            item_name=safe_item_name,
            metadata=safe_metadata,
        )

    def record_market_snapshot(self, item_name: str, source: str, payload: dict[str, Any]) -> int:
        return self._insert(
            "INSERT INTO market_snapshots (timestamp, item_name, source, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), item_name, source, _to_json(payload)),
        )

    def record_recommendation(
        self,
        item_name: str,
        recommendation_type: str,
        reason: str = "",
        payload: dict[str, Any] | None = None,
    ) -> int:
        return self._insert(
            "INSERT INTO recommendations (timestamp, item_name, recommendation_type, reason, payload_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), item_name, recommendation_type, reason, _to_json(payload)),
        )

    def record_push(
        self,
        push_type: str,
        message: str,
        item_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        return self._insert(
            "INSERT INTO push_history (timestamp, push_type, item_name, message, metadata_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), push_type, item_name, message, _to_json(metadata)),
        )

    def _insert(self, sql: str, params: tuple[Any, ...]) -> int:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(sql, params)
            conn.commit()
            return int(cursor.lastrowid)

    def get_recent_user_queries(
        self,
        limit: int = 50,
        since: str | None = None,
        item_name: str | None = None,
    ) -> list[UserQueryMemory]:
        rows = self._select(
            "SELECT id, timestamp, query_text, intent, item_name, metadata_json FROM user_queries",
            filters=[("timestamp >= ?", since), ("item_name = ?", item_name)],
            order_by="timestamp DESC",
            limit=limit,
        )
        return [UserQueryMemory(row[0], row[1], row[2], row[3], row[4], _from_json(row[5])) for row in rows]

    def get_market_snapshots(
        self,
        item_name: str | None = None,
        source: str | None = None,
        limit: int = 100,
        since: str | None = None,
    ) -> list[MarketSnapshotMemory]:
        rows = self._select(
            "SELECT id, timestamp, item_name, source, payload_json FROM market_snapshots",
            filters=[("timestamp >= ?", since), ("item_name = ?", item_name), ("source = ?", source)],
            order_by="timestamp DESC",
            limit=limit,
        )
        return [MarketSnapshotMemory(row[0], row[1], row[2], row[3], _from_json(row[4])) for row in rows]

    def get_recommendations(
        self,
        item_name: str | None = None,
        recommendation_type: str | None = None,
        limit: int = 100,
        since: str | None = None,
    ) -> list[RecommendationMemory]:
        rows = self._select(
            "SELECT id, timestamp, item_name, recommendation_type, reason, payload_json FROM recommendations",
            filters=[
                ("timestamp >= ?", since),
                ("item_name = ?", item_name),
                ("recommendation_type = ?", recommendation_type),
            ],
            order_by="timestamp DESC",
            limit=limit,
        )
        return [RecommendationMemory(row[0], row[1], row[2], row[3], row[4], _from_json(row[5])) for row in rows]

    def get_push_history(
        self,
        push_type: str | None = None,
        item_name: str | None = None,
        limit: int = 100,
        since: str | None = None,
    ) -> list[PushHistoryMemory]:
        rows = self._select(
            "SELECT id, timestamp, push_type, item_name, message, metadata_json FROM push_history",
            filters=[("timestamp >= ?", since), ("item_name = ?", item_name), ("push_type = ?", push_type)],
            order_by="timestamp DESC",
            limit=limit,
        )
        return [PushHistoryMemory(row[0], row[1], row[2], row[3], row[4], _from_json(row[5])) for row in rows]

    def _select(
        self,
        base_sql: str,
        filters: list[tuple[str, Any]],
        order_by: str,
        limit: int,
    ) -> list[tuple[Any, ...]]:
        where = [clause for clause, value in filters if value is not None]
        params = [value for _, value in filters if value is not None]
        sql = base_sql
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {order_by} LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._get_conn().execute(sql, tuple(params)).fetchall()
        return rows

    def cleanup_old_data(self, days: int = TRADING_MEMORY_RETENTION_DAYS) -> dict[str, int]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        deleted: dict[str, int] = {}
        with self._lock:
            conn = self._get_conn()
            for table in ["user_queries", "market_snapshots", "recommendations", "push_history"]:
                cursor = conn.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,))
                deleted[table] = cursor.rowcount
            conn.commit()
        return deleted

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


def _normalize_user_query_intent(intent: str) -> str:
    normalized = str(intent or "").strip().lower()
    return normalized if normalized in USER_QUERY_SUMMARY_INTENTS else "unknown"


def _safe_memory_identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    normalized = re.sub(r"_+", "_", normalized)
    if _SAFE_IDENTIFIER_RE.fullmatch(normalized):
        return normalized
    return ""


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_identifier_list(value: Any, allowed: set[str] | None = None, limit: int = 3) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        safe_item = _safe_memory_identifier(item)
        if not safe_item:
            continue
        if allowed is not None and safe_item not in allowed:
            continue
        if safe_item not in result:
            result.append(safe_item)
        if len(result) >= limit:
            break
    return result


def _sanitize_user_query_summary_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    metadata = metadata if isinstance(metadata, dict) else {}
    context_item_ids = _safe_identifier_list(metadata.get("context_item_ids"), limit=3)
    tool_names = _safe_identifier_list(metadata.get("tool_names"), allowed=USER_QUERY_SUMMARY_TOOL_NAMES, limit=5)
    item_source = str(metadata.get("item_source") or "none").strip().lower()
    if item_source not in USER_QUERY_SUMMARY_ITEM_SOURCES:
        item_source = "none"
    return {
        "schema_version": USER_QUERY_SUMMARY_VERSION,
        "storage_kind": "summary",
        "source": "chat_agent",
        "summary_strategy": "deterministic_v1",
        "raw_query_stored": False,
        "assistant_reply_stored": False,
        "context_item_ids": context_item_ids,
        "context_count": _safe_int(metadata.get("context_count")),
        "tool_names": tool_names,
        "tool_count": _safe_int(metadata.get("tool_count")),
        "tool_ok_count": _safe_int(metadata.get("tool_ok_count")),
        "item_source": item_source,
    }


def _build_user_query_summary_text(intent: str, item_name: str, metadata: dict[str, Any]) -> str:
    item_text = item_name or "none"
    context_count = _safe_int(metadata.get("context_count"))
    tool_names = metadata.get("tool_names") if isinstance(metadata.get("tool_names"), list) else []
    tools_text = ",".join(tool_names) if tool_names else "none"
    return f"summary:v1 intent={intent} item={item_text} contexts={context_count} tools={tools_text}"


def _to_json(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _from_json(value: str) -> dict[str, Any]:
    try:
        loaded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if isinstance(loaded, dict):
        return loaded
    return {}
