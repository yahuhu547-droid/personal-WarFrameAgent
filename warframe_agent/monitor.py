from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

from . import config
from .market import best_sellers, fetch_orders
from .memory import AgentMemory, PriceAlert, MEMORY_PATH
from .names import display_item_name


@dataclass(frozen=True)
class AlertNotification:
    alert: PriceAlert
    current_price: int
    item_display: str


@dataclass(frozen=True)
class FavoriteSnapshot:
    item_id: str
    item_display: str
    sell_price: int | None
    buy_price: int | None


@dataclass
class ScanResult:
    triggered_alerts: list[AlertNotification] = field(default_factory=list)
    favorite_snapshots: list[FavoriteSnapshot] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class PriceMonitor:
    def __init__(
        self,
        order_fetcher: Callable[[str], list[dict]] = fetch_orders,
        interval_seconds: int = 300,
        memory_path=None,
        on_alert: Callable[[AlertNotification], None] | None = None,
    ):
        self.order_fetcher = order_fetcher
        self.interval_seconds = interval_seconds
        self.memory_path = memory_path or MEMORY_PATH
        self.on_alert = on_alert
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._notifications: list[AlertNotification] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def drain_notifications(self) -> list[AlertNotification]:
        with self._lock:
            result = list(self._notifications)
            self._notifications.clear()
            return result

    def scan_once(self) -> ScanResult:
        from .market import best_buyers
        memory = AgentMemory.load(self.memory_path)
        result = ScanResult()
        scanned_items: set[str] = set()
        for alert in memory.price_alerts:
            scanned_items.add(alert.item_id)
            try:
                orders = self.order_fetcher(alert.item_id)
                sellers = best_sellers(orders, limit=1)
                if sellers and alert.matches(sellers[0].platinum):
                    notification = AlertNotification(
                        alert=alert,
                        current_price=sellers[0].platinum,
                        item_display=display_item_name(alert.item_id),
                    )
                    result.triggered_alerts.append(notification)
            except Exception as exc:
                result.errors.append(f"{alert.item_id}: {exc}")
        for item_id in memory.favorite_items:
            try:
                orders = self.order_fetcher(item_id)
                sellers = best_sellers(orders, limit=1)
                buyers = best_buyers(orders, limit=1)
                result.favorite_snapshots.append(FavoriteSnapshot(
                    item_id=item_id,
                    item_display=display_item_name(item_id),
                    sell_price=sellers[0].platinum if sellers else None,
                    buy_price=buyers[0].platinum if buyers else None,
                ))
            except Exception as exc:
                result.errors.append(f"{item_id}: {exc}")
        return result

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                scan = self.scan_once()
                if scan.triggered_alerts:
                    with self._lock:
                        self._notifications.extend(scan.triggered_alerts)
                    if self.on_alert:
                        for n in scan.triggered_alerts:
                            self.on_alert(n)
            except Exception:
                pass
            self._stop_event.wait(self.interval_seconds)
