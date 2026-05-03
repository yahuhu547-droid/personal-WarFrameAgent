from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config

DB_PATH = config.DATA_DIR / "price_history.db"


@dataclass(frozen=True)
class PriceSnapshot:
    item_id: str
    sell_price: int | None
    buy_price: int | None
    timestamp: str


class PriceHistoryDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS price_snapshots ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  item_id TEXT NOT NULL,"
                "  sell_price INTEGER,"
                "  buy_price INTEGER,"
                "  timestamp TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_item_timestamp "
                "ON price_snapshots (item_id, timestamp)"
            )
            conn.commit()
        finally:
            conn.close()

    def record(self, item_id: str, sell_price: int | None, buy_price: int | None) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO price_snapshots (item_id, sell_price, buy_price, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (item_id, sell_price, buy_price, datetime.now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def recent(self, item_id: str, limit: int = 10) -> list[PriceSnapshot]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT item_id, sell_price, buy_price, timestamp "
                "FROM price_snapshots WHERE item_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (item_id, limit),
            ).fetchall()
        finally:
            conn.close()
        return [PriceSnapshot(*row) for row in rows]

    def recent_since(self, item_id: str, hours: int = 24) -> list[PriceSnapshot]:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT item_id, sell_price, buy_price, timestamp "
                "FROM price_snapshots WHERE item_id = ? AND timestamp >= ? "
                "ORDER BY timestamp DESC",
                (item_id, cutoff),
            ).fetchall()
        finally:
            conn.close()
        return [PriceSnapshot(*row) for row in rows]

    def trend_summary(self, item_id: str) -> str | None:
        snapshots = self.recent(item_id, limit=5)
        if len(snapshots) < 2:
            return None
        prices = [s.sell_price for s in reversed(snapshots) if s.sell_price is not None]
        if len(prices) < 2:
            return None
        diff = prices[-1] - prices[0]
        if diff > 0:
            return f"近期趋势: 上涨 +{diff}p (从 {prices[0]}p 到 {prices[-1]}p)"
        elif diff < 0:
            return f"近期趋势: 下跌 {diff}p (从 {prices[0]}p 到 {prices[-1]}p)"
        return f"近期趋势: 持平 {prices[-1]}p"

    def rolling_average(self, item_id: str, window: int = 5) -> float | None:
        snapshots = self.recent(item_id, limit=window)
        prices = [s.sell_price for s in snapshots if s.sell_price is not None]
        if not prices:
            return None
        return sum(prices) / len(prices)

    def detect_anomaly(self, item_id: str, threshold_pct: float = 30.0) -> dict | None:
        """检测价格异常波动，返回 {direction, deviation_pct, current, average} 或 None"""
        snapshots = self.recent(item_id, limit=10)
        if len(snapshots) < 3:
            return None
        prices = [s.sell_price for s in reversed(snapshots) if s.sell_price is not None]
        if len(prices) < 3:
            return None
        avg = sum(prices[:-1]) / len(prices[:-1])
        current = prices[-1]
        if avg == 0:
            return None
        deviation_pct = ((current - avg) / avg) * 100
        if abs(deviation_pct) < threshold_pct:
            return None
        return {
            "direction": "spike" if deviation_pct > 0 else "drop",
            "deviation_pct": round(deviation_pct, 1),
            "current": current,
            "average": round(avg, 1),
        }
