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
_SENSITIVE_METADATA_TEXT_RE = re.compile(
    r"(?i)(/w\b|warframe\.market/profile|profile_url|token|secret|api[_-]?key|authorization|cookie|bearer\s+\S+)"
)
_OPPORTUNITY_OUTCOME_STATUSES = {"completed", "skipped", "failed", "expired", "watching", "accepted", "rejected"}
_OPPORTUNITY_FEEDBACK_VALUES = {"good", "bad", "ignored", "neutral", "accepted", "rejected"}


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


@dataclass(frozen=True)
class PushQualitySignal:
    item_name: str
    source: str
    strategy: str
    category: str
    sent_count: int
    reviewed_count: int
    completed_count: int
    accepted_count: int
    rejected_count: int
    pending_count: int
    good_count: int
    bad_count: int
    avg_expected_profit: float
    avg_actual_profit: float
    avg_profit_delta: float
    good_rate: float
    completion_rate: float
    rejection_rate: float
    false_positive_rate: float


@dataclass(frozen=True)
class OpportunityOutcomeMemory:
    id: int
    timestamp: str
    opportunity_id: str
    item_name: str
    source: str
    strategy: str
    status: str
    expected_profit: int
    actual_profit: int
    user_feedback: str
    metadata: dict[str, Any]

    @property
    def opportunity_type(self) -> str:
        return self.source

    @property
    def outcome(self) -> str:
        return self.status


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
            conn.execute(
                "CREATE TABLE IF NOT EXISTS opportunity_outcomes ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  timestamp TEXT NOT NULL,"
                "  opportunity_id TEXT NOT NULL,"
                "  item_name TEXT NOT NULL,"
                "  source TEXT NOT NULL,"
                "  strategy TEXT NOT NULL,"
                "  status TEXT NOT NULL,"
                "  expected_profit INTEGER NOT NULL,"
                "  actual_profit INTEGER NOT NULL,"
                "  user_feedback TEXT NOT NULL,"
                "  metadata_json TEXT NOT NULL"
                ")"
            )
            self._ensure_opportunity_outcome_columns(conn)
            for table in [
                "user_queries",
                "market_snapshots",
                "recommendations",
                "push_history",
                "opportunity_outcomes",
            ]:
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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_opportunity_outcomes_item_timestamp "
                "ON opportunity_outcomes (item_name, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_opportunity_outcomes_source_timestamp "
                "ON opportunity_outcomes (source, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_opportunity_outcomes_status_timestamp "
                "ON opportunity_outcomes (status, timestamp)"
            )
            conn.commit()

    def _ensure_opportunity_outcome_columns(self, conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_outcomes)").fetchall()}
        migrations = {
            "opportunity_id": "ALTER TABLE opportunity_outcomes ADD COLUMN opportunity_id TEXT NOT NULL DEFAULT ''",
            "source": "ALTER TABLE opportunity_outcomes ADD COLUMN source TEXT NOT NULL DEFAULT ''",
            "strategy": "ALTER TABLE opportunity_outcomes ADD COLUMN strategy TEXT NOT NULL DEFAULT ''",
            "status": "ALTER TABLE opportunity_outcomes ADD COLUMN status TEXT NOT NULL DEFAULT 'watching'",
            "expected_profit": "ALTER TABLE opportunity_outcomes ADD COLUMN expected_profit INTEGER NOT NULL DEFAULT 0",
            "actual_profit": "ALTER TABLE opportunity_outcomes ADD COLUMN actual_profit INTEGER NOT NULL DEFAULT 0",
            "user_feedback": "ALTER TABLE opportunity_outcomes ADD COLUMN user_feedback TEXT NOT NULL DEFAULT 'neutral'",
        }
        for column, sql in migrations.items():
            if column not in existing:
                conn.execute(sql)
        if "opportunity_type" in existing:
            conn.execute("UPDATE opportunity_outcomes SET source = opportunity_type WHERE source = ''")
            conn.execute("UPDATE opportunity_outcomes SET strategy = opportunity_type WHERE strategy = ''")
        if "outcome" in existing:
            conn.execute("UPDATE opportunity_outcomes SET status = outcome WHERE status = 'watching'")
            conn.execute("UPDATE opportunity_outcomes SET user_feedback = outcome WHERE user_feedback = 'neutral'")

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

    def record_opportunity_outcome(
        self,
        opportunity_id: str,
        item_name: str,
        source: str,
        strategy: str | None = None,
        status: str | None = None,
        expected_profit: int = 0,
        actual_profit: int = 0,
        user_feedback: str = "neutral",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if metadata is None and isinstance(strategy, dict):
            metadata = strategy
            strategy = None
        if status is None and strategy is None:
            # Backward compatibility with the previous local helper:
            # (item_name, opportunity_type, outcome, metadata=None).
            legacy_item_name = opportunity_id
            legacy_source = item_name
            legacy_status = source
            opportunity_id = ""
            item_name = legacy_item_name
            source = legacy_source
            strategy = legacy_source
            status = legacy_status
            user_feedback = legacy_status
        strategy = strategy or source
        status = _normalize_outcome_status(status or "watching")
        user_feedback = _normalize_feedback(user_feedback)
        return self._insert(
            "INSERT INTO opportunity_outcomes "
            "(timestamp, opportunity_id, item_name, source, strategy, status, expected_profit, actual_profit, user_feedback, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(),
                str(opportunity_id or "")[:32],
                _safe_memory_identifier(item_name),
                _safe_memory_identifier(source),
                _safe_memory_identifier(strategy),
                status,
                int(expected_profit or 0),
                int(actual_profit or 0),
                user_feedback,
                _to_json(_sanitize_opportunity_outcome_metadata(metadata)),
            ),
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

    def summarize_push_quality(
        self,
        push_type: str = "opportunity",
        item_name: str | None = None,
        source: str | None = None,
        limit: int = 100,
        since: str | None = None,
    ) -> list[PushQualitySignal]:
        if limit <= 0:
            return []
        safe_item = _safe_memory_identifier(item_name) if item_name else None
        safe_source = _safe_memory_identifier(source) if source else None
        record_limit = max(limit * 10, limit)
        pushes = self.get_push_history(
            push_type=push_type,
            item_name=safe_item,
            limit=record_limit,
            since=since,
        )
        outcomes = self.get_opportunity_outcomes(
            item_name=safe_item,
            source=safe_source,
            limit=record_limit,
            since=since,
        )
        groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}

        for push in pushes:
            push_source = _push_quality_source_from_metadata(push.metadata)
            if safe_source and push_source != safe_source:
                continue
            strategy = _push_quality_strategy_from_metadata(push.metadata)
            category = _infer_push_quality_category(push.item_name, push_source, strategy)
            key = (push.item_name, push_source, strategy, category)
            group = _push_quality_group(groups, key)
            group["sent_count"] += 1

        for outcome in outcomes:
            outcome_source = _safe_memory_identifier(outcome.source) or "unknown"
            if safe_source and outcome_source != safe_source:
                continue
            strategy = _safe_memory_identifier(outcome.strategy) or outcome_source
            category = _infer_push_quality_category(outcome.item_name, outcome_source, strategy)
            key = (outcome.item_name, outcome_source, strategy, category)
            group = _push_quality_group(groups, key)
            group["reviewed_count"] += 1
            if outcome.status == "completed":
                group["completed_count"] += 1
            if outcome.status == "accepted":
                group["accepted_count"] += 1
            if outcome.status in {"rejected", "failed", "expired", "skipped"}:
                group["rejected_count"] += 1
            if _is_good_push_outcome(outcome):
                group["good_count"] += 1
            if _is_bad_push_outcome(outcome):
                group["bad_count"] += 1
            group["expected_profit_total"] += int(outcome.expected_profit or 0)
            group["actual_profit_total"] += int(outcome.actual_profit or 0)

        signals = [_push_quality_signal_from_group(key, group) for key, group in groups.items()]
        signals.sort(key=lambda signal: (-signal.sent_count, -signal.reviewed_count, signal.item_name, signal.source, signal.strategy))
        return signals[:limit]

    def get_opportunity_outcomes(
        self,
        status: str | None = None,
        item_name: str | None = None,
        source: str | None = None,
        opportunity_type: str | None = None,
        limit: int = 100,
        since: str | None = None,
    ) -> list[OpportunityOutcomeMemory]:
        rows = self._select(
            "SELECT id, timestamp, opportunity_id, item_name, source, strategy, status, expected_profit, actual_profit, user_feedback, metadata_json "
            "FROM opportunity_outcomes",
            filters=[
                ("timestamp >= ?", since),
                ("status = ?", _normalize_outcome_status(status) if status else None),
                ("item_name = ?", _safe_memory_identifier(item_name) if item_name else None),
                ("source = ?", _safe_memory_identifier(source or opportunity_type) if (source or opportunity_type) else None),
            ],
            order_by="timestamp DESC",
            limit=limit,
        )
        return [
            OpportunityOutcomeMemory(
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                int(row[7]),
                int(row[8]),
                row[9],
                _from_json(row[10]),
            )
            for row in rows
        ]

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
            for table in [
                "user_queries",
                "market_snapshots",
                "recommendations",
                "push_history",
                "opportunity_outcomes",
            ]:
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


def _safe_metadata_text(value: Any, max_chars: int = 120) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or _SENSITIVE_METADATA_TEXT_RE.search(text):
        return ""
    return text[:max_chars]


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


def _sanitize_opportunity_outcome_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    metadata = metadata if isinstance(metadata, dict) else {}
    safe_metadata: dict[str, Any] = {}
    if isinstance(metadata.get("safe_summary"), str):
        safe_summary_text = _safe_metadata_text(metadata["safe_summary"], max_chars=500)
        if safe_summary_text:
            safe_metadata["safe_summary"] = safe_summary_text
    elif isinstance(metadata.get("safe_summary"), dict):
        allowed_keys = {
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
        }
        safe_summary = {}
        for key, value in metadata["safe_summary"].items():
            if key not in allowed_keys:
                continue
            if isinstance(value, (bool, int, float)) or value is None:
                safe_summary[str(key)] = value
                continue
            safe_value = _safe_metadata_text(value)
            if safe_value:
                safe_summary[str(key)] = safe_value
        if safe_summary:
            safe_metadata["safe_summary"] = safe_summary
    if "personal_score" in metadata:
        safe_metadata["personal_score"] = _safe_int(metadata.get("personal_score"))
    if "market_score" in metadata:
        safe_metadata["market_score"] = _safe_int(metadata.get("market_score"))
    if "personal_reasons" in metadata:
        safe_metadata["personal_reasons"] = _safe_identifier_list(metadata.get("personal_reasons"), limit=10)
    return safe_metadata


def _normalize_outcome_status(status: str) -> str:
    normalized = (status or "watching").strip().lower()
    return normalized if normalized in _OPPORTUNITY_OUTCOME_STATUSES else "watching"


def _normalize_feedback(value: str) -> str:
    normalized = (value or "neutral").strip().lower()
    return normalized if normalized in _OPPORTUNITY_FEEDBACK_VALUES else "neutral"


def _push_quality_group(
    groups: dict[tuple[str, str, str, str], dict[str, Any]],
    key: tuple[str, str, str, str],
) -> dict[str, Any]:
    return groups.setdefault(
        key,
        {
            "sent_count": 0,
            "reviewed_count": 0,
            "completed_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "good_count": 0,
            "bad_count": 0,
            "expected_profit_total": 0,
            "actual_profit_total": 0,
        },
    )


def _push_quality_source_from_metadata(metadata: dict[str, Any]) -> str:
    if not isinstance(metadata, dict):
        return "unknown"
    for key in ("opportunity_source", "source"):
        value = _safe_memory_identifier(metadata.get(key))
        if value and value != "rule_proactive_push":
            return value
    safe_summary = metadata.get("safe_summary")
    if isinstance(safe_summary, dict):
        value = _safe_memory_identifier(safe_summary.get("source"))
        if value:
            return value
    return "unknown"


def _push_quality_strategy_from_metadata(metadata: dict[str, Any]) -> str:
    if not isinstance(metadata, dict):
        return "unknown"
    value = _safe_memory_identifier(metadata.get("strategy"))
    if value:
        return value
    safe_summary = metadata.get("safe_summary")
    if isinstance(safe_summary, dict):
        value = _safe_memory_identifier(safe_summary.get("strategy"))
        if value:
            return value
    value = _safe_memory_identifier(metadata.get("suggestion_type"))
    return value or "unknown"


def _infer_push_quality_category(item_name: str, source: str, strategy: str) -> str:
    text = " ".join([item_name or "", source or "", strategy or ""]).lower()
    if "arcane" in text:
        return "arcane"
    if "prime_set" in text or "_set" in text or "set_profit" in text or "buy_parts_sell_set" in text:
        return "prime_set"
    if "mod" in text or "flipper" in text:
        return "mod"
    return "unknown"


def _is_good_push_outcome(outcome: OpportunityOutcomeMemory) -> bool:
    if outcome.user_feedback in {"bad", "ignored", "rejected"}:
        return False
    if outcome.status in {"rejected", "failed", "expired", "skipped"}:
        return False
    return int(outcome.actual_profit or 0) > 0 or outcome.user_feedback in {"good", "accepted"} or outcome.status in {"completed", "accepted"}


def _is_bad_push_outcome(outcome: OpportunityOutcomeMemory) -> bool:
    if outcome.user_feedback in {"bad", "ignored", "rejected"}:
        return True
    if outcome.status in {"rejected", "failed", "expired", "skipped"}:
        return True
    return int(outcome.actual_profit or 0) < 0


def _push_quality_signal_from_group(
    key: tuple[str, str, str, str],
    group: dict[str, Any],
) -> PushQualitySignal:
    item_name, source, strategy, category = key
    reviewed_count = int(group["reviewed_count"])
    expected_total = int(group["expected_profit_total"])
    actual_total = int(group["actual_profit_total"])
    good_count = int(group["good_count"])
    bad_count = int(group["bad_count"])
    avg_expected = round(expected_total / reviewed_count, 2) if reviewed_count else 0.0
    avg_actual = round(actual_total / reviewed_count, 2) if reviewed_count else 0.0
    sent_count = int(group["sent_count"])
    completed_count = int(group["completed_count"])
    accepted_count = int(group["accepted_count"])
    rejected_count = int(group["rejected_count"])
    return PushQualitySignal(
        item_name=item_name,
        source=source,
        strategy=strategy,
        category=category,
        sent_count=sent_count,
        reviewed_count=reviewed_count,
        completed_count=completed_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        pending_count=max(0, sent_count - reviewed_count),
        good_count=good_count,
        bad_count=bad_count,
        avg_expected_profit=avg_expected,
        avg_actual_profit=avg_actual,
        avg_profit_delta=round(avg_actual - avg_expected, 2),
        good_rate=round(good_count / reviewed_count, 4) if reviewed_count else 0.0,
        completion_rate=round((completed_count + accepted_count) / reviewed_count, 4) if reviewed_count else 0.0,
        rejection_rate=round(rejected_count / reviewed_count, 4) if reviewed_count else 0.0,
        false_positive_rate=round(bad_count / reviewed_count, 4) if reviewed_count else 0.0,
    )


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
