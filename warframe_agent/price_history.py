from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)

DB_PATH = config.DATA_DIR / "price_history.db"
PRICE_HISTORY_TTL_DAYS = 30


@dataclass(frozen=True)
class PriceSnapshot:
    item_id: str
    sell_price: int | None
    buy_price: int | None
    timestamp: str


class PriceHistoryDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _ensure_table(self) -> None:
        with self._lock:
            conn = self._get_conn()
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

    def record(self, item_id: str, sell_price: int | None, buy_price: int | None) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO price_snapshots (item_id, sell_price, buy_price, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (item_id, sell_price, buy_price, datetime.now().isoformat()),
            )
            conn.commit()

    def recent(self, item_id: str, limit: int = 10) -> list[PriceSnapshot]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT item_id, sell_price, buy_price, timestamp "
                "FROM price_snapshots WHERE item_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (item_id, limit),
            ).fetchall()
        return [PriceSnapshot(*row) for row in rows]

    def recent_since(self, item_id: str, hours: int = 24) -> list[PriceSnapshot]:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT item_id, sell_price, buy_price, timestamp "
                "FROM price_snapshots WHERE item_id = ? AND timestamp >= ? "
                "ORDER BY timestamp DESC",
                (item_id, cutoff),
            ).fetchall()
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

    def predict_trend(self, item_id: str, event_context: dict | None = None) -> dict | None:
        """线性回归预测价格趋势，支持事件修正。

        Args:
            item_id: 物品 market ID
            event_context: 可选事件上下文，如 {"baro_active": True, "vault_active": True}

        Returns:
            {direction, slope, confidence, predicted_next, price_range, data_points, current, event_factor}
        """
        snapshots = self.recent(item_id, limit=10)
        if len(snapshots) < 3:
            return None
        prices = [(i, s.sell_price) for i, s in enumerate(reversed(snapshots)) if s.sell_price is not None]
        if len(prices) < 3:
            return None
        n = len(prices)
        sum_x = sum(p[0] for p in prices)
        sum_y = sum(p[1] for p in prices)
        sum_xy = sum(p[0] * p[1] for p in prices)
        sum_x2 = sum(p[0] ** 2 for p in prices)
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return None
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        predicted_next = slope * n + intercept

        # R² 计算（拟合优度 → 置信度）
        y_mean = sum_y / n
        ss_tot = sum((p[1] - y_mean) ** 2 for p in prices)
        ss_res = sum((p[1] - (slope * p[0] + intercept)) ** 2 for p in prices)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        r_squared = max(0, min(1, r_squared))

        # 数据量置信度因子（数据越多越可靠）
        data_confidence = min(1.0, n / 8)
        confidence = round(r_squared * data_confidence * 100, 0)

        # 价格波动范围（基于残差标准差）
        if n > 2:
            residuals = [p[1] - (slope * p[0] + intercept) for p in prices]
            std_err = (sum(r ** 2 for r in residuals) / (n - 2)) ** 0.5
        else:
            std_err = 0
        price_low = round(predicted_next - 1.96 * std_err, 0)
        price_high = round(predicted_next + 1.96 * std_err, 0)

        # 事件修正因子
        event_factor = 0.0
        event_label = ""
        if event_context:
            # Baro 来访 → Primed Mod 预期下跌 ~15%
            if event_context.get("baro_active") and "primed" in item_id.lower():
                event_factor = -0.15
                event_label = "Baro 来访压价"
            # Vault → 供给减少，预期上涨 ~10%
            elif event_context.get("vault_active"):
                event_factor = 0.10
                event_label = "Vault 减少供给"
            # Prime Access → 新品上市，同类旧品短期下跌
            elif event_context.get("prime_access_active"):
                event_factor = -0.05
                event_label = "Prime Access 冲击"

        if event_factor != 0:
            predicted_next = predicted_next * (1 + event_factor)
            price_low = price_low * (1 + event_factor)
            price_high = price_high * (1 + event_factor)

        direction = "rising" if slope > 0.5 else "falling" if slope < -0.5 else "stable"
        return {
            "direction": direction,
            "slope": round(slope, 2),
            "confidence": confidence,
            "predicted_next": round(predicted_next, 0),
            "price_range": (round(price_low, 0), round(price_high, 0)),
            "data_points": n,
            "current": prices[-1][1],
            "event_factor": event_label,
        }

    def cleanup_old_data(self, days: int = PRICE_HISTORY_TTL_DAYS) -> int:
        """删除超过指定天数的历史数据，返回删除行数。"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM price_snapshots WHERE timestamp < ?", (cutoff,)
            )
            conn.commit()
            deleted = cursor.rowcount
        if deleted > 0:
            logger.info("价格历史清理: 删除 %d 条超过 %d 天的记录", deleted, days)
        return deleted

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
