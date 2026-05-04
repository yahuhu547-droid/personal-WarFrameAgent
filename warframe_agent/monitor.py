from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from . import config
from .market import best_sellers, fetch_orders, get_max_rank_from_orders
from .memory import AgentMemory, PriceAlert, ProactiveSuggestion, MEMORY_PATH
from .names import display_item_name


@dataclass(frozen=True)
class AlertNotification:
    alert: PriceAlert
    current_price: int
    item_display: str


@dataclass(frozen=True)
class WatchNotification:
    item_id: str
    item_name: str
    sell_price: int | None
    buy_price: int | None
    content: str
    frequency: str


@dataclass(frozen=True)
class FavoriteSnapshot:
    item_id: str
    item_display: str
    sell_price: int | None
    buy_price: int | None


@dataclass(frozen=True)
class EnrichedNotification:
    item_id: str
    item_display: str
    notification_type: str  # "anomaly", "opportunity", "trend"
    raw_data: dict
    analysis: str
    priority: int


@dataclass
class ScanResult:
    triggered_alerts: list[AlertNotification] = field(default_factory=list)
    watch_notifications: list[WatchNotification] = field(default_factory=list)
    favorite_snapshots: list[FavoriteSnapshot] = field(default_factory=list)
    suggestions: list[ProactiveSuggestion] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build_anomaly_analysis_prompt(
    item_id: str,
    item_display: str,
    anomaly: dict,
    trend: str | None,
    history_high: int | None,
    history_low: int | None,
) -> str:
    """构建 LLM 异常分析 prompt。"""
    direction = "暴涨" if anomaly["direction"] == "spike" else "暴跌"
    return (
        f"你是资深 Warframe 交易分析师。以下物品出现价格异常：\n"
        f"物品: {item_display} ({item_id})\n"
        f"当前价格: {anomaly['current']}p\n"
        f"历史均值: {anomaly['average']}p\n"
        f"偏离幅度: {anomaly['deviation_pct']}%\n"
        f"方向: {direction}\n"
        f"近期趋势: {trend or '未知'}\n"
        f"历史最高: {history_high}p / 历史最低: {history_low}p\n\n"
        f"请用 2-3 句话分析：\n"
        f"1. 造成这个波动的可能原因（结合 Warframe 游戏周期）\n"
        f"2. 是否是买入/卖出机会\n"
        f"3. 具体操作建议\n"
        f"用中文回答，简洁实用。"
    )


def detect_opportunities(favorite_snapshots: list[FavoriteSnapshot]) -> list[ProactiveSuggestion]:
    """分析收藏夹快照，检测套利和买入机会。"""
    opportunities = []
    for snap in favorite_snapshots:
        if snap.sell_price and snap.buy_price and snap.buy_price > 0:
            spread = snap.sell_price - snap.buy_price
            spread_pct = (spread / snap.buy_price) * 100
            if spread_pct > 40:
                opportunities.append(ProactiveSuggestion(
                    item_id=snap.item_id,
                    suggestion_type="opportunity",
                    priority=2,
                    message=f"{snap.item_display} 价差高达 {spread}p ({spread_pct:.0f}%)，低买高卖空间大",
                ))
    return opportunities


class PriceMonitor:
    def __init__(
        self,
        order_fetcher: Callable[[str], list[dict]] = fetch_orders,
        interval_seconds: int = 300,
        memory_path=None,
        on_alert: Callable[[AlertNotification], None] | None = None,
        on_watch: Callable[[WatchNotification], None] | None = None,
        price_db=None,
        llm_analyzer: Callable[[str], str] | None = None,
    ):
        self.order_fetcher = order_fetcher
        self.interval_seconds = interval_seconds
        self.memory_path = memory_path or MEMORY_PATH
        self.on_alert = on_alert
        self.on_watch = on_watch
        self.price_db = price_db
        self.llm_analyzer = llm_analyzer
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._notifications: list[AlertNotification] = []
        self._watch_notifications: list[WatchNotification] = []
        self._watch_last_notified: dict[str, str] = {}  # item_id -> "YYYY-MM-DD HH:MM"
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
                rank_filter = get_max_rank_from_orders(orders)
                sellers = best_sellers(orders, limit=1, rank_filter=rank_filter)
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
                rank_filter = get_max_rank_from_orders(orders)
                sellers = best_sellers(orders, limit=1, rank_filter=rank_filter)
                buyers = best_buyers(orders, limit=1, rank_filter=rank_filter)
                result.favorite_snapshots.append(FavoriteSnapshot(
                    item_id=item_id,
                    item_display=display_item_name(item_id),
                    sell_price=sellers[0].platinum if sellers else None,
                    buy_price=buyers[0].platinum if buyers else None,
                ))
                scanned_items.add(item_id)
                if self.price_db and sellers:
                    self.price_db.record(item_id, sellers[0].platinum, buyers[0].platinum if buyers else None)
            except Exception as exc:
                result.errors.append(f"{item_id}: {exc}")
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_hour_min = now.hour * 60 + now.minute

        for watch_item in memory.watchlist:
            if watch_item.item_id in scanned_items:
                continue
            try:
                orders = self.order_fetcher(watch_item.item_id)
                rank_filter = get_max_rank_from_orders(orders)
                sellers = best_sellers(orders, limit=1, rank_filter=rank_filter)
                buyers = best_buyers(orders, limit=1, rank_filter=rank_filter)
                result.favorite_snapshots.append(FavoriteSnapshot(
                    item_id=watch_item.item_id,
                    item_display=watch_item.item_name,
                    sell_price=sellers[0].platinum if sellers else None,
                    buy_price=buyers[0].platinum if buyers else None,
                ))
                if self.price_db and sellers:
                    self.price_db.record(watch_item.item_id, sellers[0].platinum, buyers[0].platinum if buyers else None)

                # 检查是否到推送时间
                if self._should_notify_watch(watch_item, current_time, current_hour_min):
                    notification = WatchNotification(
                        item_id=watch_item.item_id,
                        item_name=watch_item.item_name,
                        sell_price=sellers[0].platinum if sellers else None,
                        buy_price=buyers[0].platinum if buyers else None,
                        content=watch_item.content,
                        frequency=watch_item.frequency,
                    )
                    result.watch_notifications.append(notification)
                    # daily/weekly 在 _should_notify_watch 中未设置 last_notified，在此设置
                    now = datetime.now()
                    today = now.strftime("%Y-%m-%d")
                    if watch_item.frequency == "daily":
                        self._watch_last_notified[watch_item.item_id] = today
                    elif watch_item.frequency == "weekly":
                        iso_week = now.isocalendar()[1]
                        self._watch_last_notified[watch_item.item_id] = f"W{iso_week}"

            except Exception as exc:
                result.errors.append(f"{watch_item.item_id}: {exc}")
        if self.price_db:
            all_items = scanned_items | {w.item_id for w in memory.watchlist}
            for item_id in all_items:
                try:
                    anomaly = self.price_db.detect_anomaly(item_id, config.ANOMALY_THRESHOLD_PERCENT)
                    if anomaly:
                        direction_text = "暴涨" if anomaly["direction"] == "spike" else "暴跌"
                        msg = (
                            f"{display_item_name(item_id)} 价格{direction_text}！"
                            f"当前 {anomaly['current']}p，均值 {anomaly['average']}p，"
                            f"偏差 {anomaly['deviation_pct']}%"
                        )
                        priority = 1 if abs(anomaly["deviation_pct"]) >= config.ANOMALY_THRESHOLD_PERCENT else 2
                        suggestion = ProactiveSuggestion(
                            item_id=item_id,
                            suggestion_type="anomaly",
                            priority=priority,
                            message=msg,
                        )
                        result.suggestions.append(suggestion)
                except Exception as exc:
                    result.errors.append(f"anomaly check {item_id}: {exc}")
        return result

    def _should_notify_watch(self, watch_item, current_time: str, current_hour_min: int) -> bool:
        """检查定时关注项是否应该推送通知"""
        item_key = watch_item.item_id
        last_notified = self._watch_last_notified.get(item_key, "")
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_hour = now.hour

        # 解析计划时间
        try:
            plan_parts = watch_item.time.split(":")
            plan_hour = int(plan_parts[0])
            plan_min = int(plan_parts[1])
            plan_hour_min = plan_hour * 60 + plan_min
        except (ValueError, IndexError):
            return False

        # 扫描间隔 5 分钟，允许 6 分钟容差
        tolerance = 6
        in_window = abs(current_hour_min - plan_hour_min) <= tolerance

        if watch_item.frequency == "hourly":
            # 每小时推送：在计划分钟附近 + 当前小时还没推送过
            hour_key = f"{today} {current_hour:02d}"
            if in_window and last_notified != hour_key:
                self._watch_last_notified[item_key] = hour_key
                return True
        elif watch_item.frequency == "daily":
            # 每天推送：在计划时间附近 + 今天还没推送过
            if in_window and not last_notified.startswith(today):
                return True
        elif watch_item.frequency == "weekly":
            # 每周推送：周一 + 在计划时间附近 + 本周还没推送
            iso_week = now.isocalendar()[1]
            week_key = f"W{iso_week}"
            if now.weekday() == 0 and in_window and week_key not in last_notified:
                return True
        return False

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
                if scan.watch_notifications:
                    with self._lock:
                        self._watch_notifications.extend(scan.watch_notifications)
                    if self.on_watch:
                        for n in scan.watch_notifications:
                            self.on_watch(n)

                # 机会检测
                opportunities = detect_opportunities(scan.favorite_snapshots)
                all_suggestions = list(scan.suggestions) + opportunities

                # LLM 分析增强
                if self.llm_analyzer:
                    enriched = []
                    for suggestion in all_suggestions:
                        if suggestion.suggestion_type == "anomaly" and self.price_db:
                            try:
                                trend = self.price_db.trend_summary(suggestion.item_id)
                                history = self.price_db.recent(suggestion.item_id, limit=20)
                                prices = [s.sell_price for s in history if s.sell_price is not None]
                                anomaly_data = self.price_db.detect_anomaly(suggestion.item_id, config.ANOMALY_THRESHOLD_PERCENT)
                                if anomaly_data:
                                    prompt = build_anomaly_analysis_prompt(
                                        suggestion.item_id,
                                        display_item_name(suggestion.item_id),
                                        anomaly_data,
                                        trend,
                                        max(prices) if prices else None,
                                        min(prices) if prices else None,
                                    )
                                    analysis = self.llm_analyzer(prompt)
                                    enriched.append(ProactiveSuggestion(
                                        item_id=suggestion.item_id,
                                        suggestion_type=suggestion.suggestion_type,
                                        priority=suggestion.priority,
                                        message=analysis,
                                        timestamp=suggestion.timestamp,
                                    ))
                                    continue
                            except Exception:
                                pass
                        enriched.append(suggestion)
                    all_suggestions = enriched

                if all_suggestions:
                    memory = AgentMemory.load(self.memory_path)
                    for suggestion in all_suggestions:
                        memory = memory.with_suggestion(suggestion)
                    memory.save(self.memory_path)
            except Exception:
                pass
            self._stop_event.wait(self.interval_seconds)
