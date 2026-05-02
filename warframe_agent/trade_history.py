from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config

TRADE_DB_PATH = config.DATA_DIR / "trade_history.db"


@dataclass(frozen=True)
class TradeRecord:
    id: int
    item_id: str
    item_name: str
    trade_type: str  # "buy" or "sell"
    price: int
    player_name: str
    timestamp: str
    notes: str


class TradeHistoryDB:
    def __init__(self, db_path: Path = TRADE_DB_PATH):
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
                "CREATE TABLE IF NOT EXISTS trade_history ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  item_id TEXT NOT NULL,"
                "  item_name TEXT NOT NULL,"
                "  trade_type TEXT NOT NULL,"
                "  price INTEGER NOT NULL,"
                "  player_name TEXT,"
                "  timestamp TEXT NOT NULL,"
                "  notes TEXT"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_timestamp "
                "ON trade_history (timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_item "
                "ON trade_history (item_id)"
            )
            conn.commit()
        finally:
            conn.close()

    def add_trade(
        self,
        item_id: str,
        item_name: str,
        trade_type: str,
        price: int,
        player_name: str = "",
        notes: str = "",
    ) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                "INSERT INTO trade_history (item_id, item_name, trade_type, price, player_name, timestamp, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (item_id, item_name, trade_type, price, player_name, datetime.now().isoformat(), notes),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_recent_trades(self, limit: int = 20) -> list[TradeRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, item_id, item_name, trade_type, price, player_name, timestamp, notes "
                "FROM trade_history ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            conn.close()
        return [TradeRecord(*row) for row in rows]

    def get_trades_by_item(self, item_id: str, limit: int = 10) -> list[TradeRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, item_id, item_name, trade_type, price, player_name, timestamp, notes "
                "FROM trade_history WHERE item_id = ? ORDER BY timestamp DESC LIMIT ?",
                (item_id, limit),
            ).fetchall()
        finally:
            conn.close()
        return [TradeRecord(*row) for row in rows]

    def get_trade_stats(self) -> dict:
        conn = self._connect()
        try:
            # 总交易次数
            total = conn.execute("SELECT COUNT(*) FROM trade_history").fetchone()[0]

            # 总买入/卖出次数
            buy_count = conn.execute(
                "SELECT COUNT(*) FROM trade_history WHERE trade_type = 'buy'"
            ).fetchone()[0]
            sell_count = conn.execute(
                "SELECT COUNT(*) FROM trade_history WHERE trade_type = 'sell'"
            ).fetchone()[0]

            # 总花费/收入
            total_spent = conn.execute(
                "SELECT COALESCE(SUM(price), 0) FROM trade_history WHERE trade_type = 'buy'"
            ).fetchone()[0]
            total_earned = conn.execute(
                "SELECT COALESCE(SUM(price), 0) FROM trade_history WHERE trade_type = 'sell'"
            ).fetchone()[0]

            # 最常交易的物品
            most_traded = conn.execute(
                "SELECT item_name, COUNT(*) as cnt FROM trade_history "
                "GROUP BY item_id ORDER BY cnt DESC LIMIT 5"
            ).fetchall()

            return {
                "total_trades": total,
                "buy_count": buy_count,
                "sell_count": sell_count,
                "total_spent": total_spent,
                "total_earned": total_earned,
                "net_profit": total_earned - total_spent,
                "most_traded": [{"name": r[0], "count": r[1]} for r in most_traded],
            }
        finally:
            conn.close()

    def delete_trade(self, trade_id: int) -> bool:
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM trade_history WHERE id = ?", (trade_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
