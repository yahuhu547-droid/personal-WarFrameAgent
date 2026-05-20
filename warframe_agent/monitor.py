from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from . import config
from .events import EventTracker
from .goals import execute_plan, plan_for_goal
from .knowledge import MarketKnowledge
from .market import best_sellers, fetch_orders, get_max_rank_from_orders
from .memory import AgentMemory, PriceAlert, ProactiveSuggestion, MEMORY_PATH, normalize_opportunity_filter
from .mod_flipper import is_tradeable_arcane, is_tradeable_mod
from .names import display_item_name, load_item_data
from .rules import (
    ProactivePush,
    evaluate_market_state,
    generate_auto_goals,
    generate_proactive_message,
)
from .scheduler import Scheduler, serialize_scheduler_jobs

logger = logging.getLogger(__name__)

PRICE_MONITOR_SCAN_JOB_ID = "price_monitor.scan"
PRICE_MONITOR_SCAN_JOB_NAME = "Price monitor scan"
PRICE_MONITOR_EVENT_CHECKS_JOB_ID = "price_monitor.event_checks"
PRICE_MONITOR_EVENT_CHECKS_JOB_NAME = "Price monitor event checks"
PRICE_MONITOR_DAILY_REPORT_JOB_ID = "price_monitor.daily_report"
PRICE_MONITOR_DAILY_REPORT_JOB_NAME = "Price monitor daily report"
PRICE_MONITOR_KNOWLEDGE_UPDATE_JOB_ID = "price_monitor.knowledge_update"
PRICE_MONITOR_KNOWLEDGE_UPDATE_JOB_NAME = "Price monitor knowledge update"
PRICE_MONITOR_GOAL_GENERATION_JOB_ID = "price_monitor.goal_generation"
PRICE_MONITOR_GOAL_GENERATION_JOB_NAME = "Price monitor goal generation"
PRICE_MONITOR_SELF_LEARNING_JOB_ID = "price_monitor.self_learning"
PRICE_MONITOR_SELF_LEARNING_JOB_NAME = "Price monitor self learning"
MARKET_SNAPSHOT_MEMORY_SOURCE = "price_monitor.scan"
MARKET_SNAPSHOT_MEMORY_MIN_SECONDS = 3600


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


def _item_matches_opportunity_filter(item_id: str, opportunity_filter: str, item_data: dict[str, dict] | None = None) -> bool:
    opportunity_filter = normalize_opportunity_filter(opportunity_filter)
    if opportunity_filter == "all":
        return True
    items = item_data if item_data is not None else load_item_data()
    item = items.get(item_id) or items.get(item_id.lower()) or {"item_id": item_id, "url_name": item_id}
    if opportunity_filter == "arcane":
        return is_tradeable_arcane(item) or item_id.lower().startswith("arcane_")
    if opportunity_filter == "mod":
        return is_tradeable_mod(item) and not (is_tradeable_arcane(item) or item_id.lower().startswith("arcane_"))
    return True


def detect_opportunities(
    favorite_snapshots: list[FavoriteSnapshot],
    opportunity_filter: str = "all",
) -> list[ProactiveSuggestion]:
    """分析收藏夹快照，检测套利和买入机会。"""
    opportunities = []
    item_data = load_item_data() if normalize_opportunity_filter(opportunity_filter) != "all" else None
    threshold_pct = config.SPREAD_OPPORTUNITY_THRESHOLD_PCT
    for snap in favorite_snapshots:
        if not _item_matches_opportunity_filter(snap.item_id, opportunity_filter, item_data):
            continue
        if snap.sell_price and snap.buy_price and snap.buy_price > 0:
            spread = snap.sell_price - snap.buy_price
            spread_pct = (spread / snap.buy_price) * 100
            if spread_pct > threshold_pct:
                rationale = (
                    f"原因：最低卖价 {snap.sell_price}p 高于最高收价 {snap.buy_price}p，"
                    f"价差 {spread}p（{spread_pct:.0f}%），超过 {threshold_pct}% 阈值；"
                    "下单前请再确认在线订单、成交量和税费。"
                )
                opportunities.append(ProactiveSuggestion(
                    item_id=snap.item_id,
                    suggestion_type="opportunity",
                    priority=2,
                    message=f"{snap.item_display} 买卖盘价差 {spread}p ({spread_pct:.0f}%)。{rationale}",
                    data={
                        "source": "spread",
                        "sell_price": snap.sell_price,
                        "buy_price": snap.buy_price,
                        "spread": spread,
                        "spread_pct": round(spread_pct, 1),
                        "threshold_pct": threshold_pct,
                        "rationale": rationale,
                    },
                ))
    return opportunities


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze_value(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_freeze_value(v) for v in value)
    return value


def _unique_goals(goals: list) -> list:
    unique = []
    seen = set()
    for goal in goals:
        key = (goal.goal_type, goal.target, _freeze_value(goal.criteria))
        if key in seen:
            continue
        seen.add(key)
        unique.append(goal)
    return unique


def _unique_suggestions(suggestions: list[ProactiveSuggestion]) -> list[ProactiveSuggestion]:
    unique = []
    seen = set()
    for suggestion in suggestions:
        data = suggestion.data or {}
        dedupe_key = data.get("dedupe_key")
        key = (
            "dedupe",
            dedupe_key,
        ) if dedupe_key else (
            suggestion.item_id,
            suggestion.suggestion_type,
            data.get("source", ""),
            data.get("strategy", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(suggestion)
    return unique


_PROACTIVE_SAFE_DATA_KEYS = {
    "suggestion_type",
    "dedupe_key",
    "strategy",
    "item_id",
    "display_name",
    "required_quantity",
    "buy_step_count",
    "sell_step_count",
    "total_cost",
    "total_revenue",
    "profit",
    "roi_pct",
    "volume_48h",
    "risk_level",
    "profit_bucket",
    "plan_signature",
    "sell_price",
    "buy_price",
    "spread",
    "spread_pct",
    "threshold_pct",
    "rationale",
}


def _trade_plan_safe_summary_from_data(data: dict | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    plan = data.get("trade_plan")
    if not isinstance(plan, dict):
        return {}
    summary = plan.get("safe_summary")
    if isinstance(summary, dict):
        return dict(summary)
    return {
        "schema_version": plan.get("schema_version", 1),
        "source": plan.get("source", ""),
        "strategy": plan.get("strategy", ""),
        "item_id": plan.get("item_id", ""),
        "display_name": plan.get("display_name", ""),
        "required_quantity": plan.get("required_quantity", 0),
        "buy_step_count": len(plan.get("buy_steps") or []),
        "sell_step_count": len(plan.get("sell_steps") or []),
        "total_cost": plan.get("total_cost", 0),
        "total_revenue": plan.get("total_revenue", 0),
        "profit": plan.get("profit", 0),
        "roi_pct": plan.get("roi_pct", 0),
        "volume_48h": plan.get("volume_48h"),
        "risk_level": plan.get("risk_level", ""),
        "profit_bucket": plan.get("profit_bucket", ""),
        "plan_signature": plan.get("plan_signature", ""),
    }


def _safe_proactive_metadata_from_data(data: dict | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    safe = _trade_plan_safe_summary_from_data(data)
    for key in _PROACTIVE_SAFE_DATA_KEYS:
        if key in data:
            safe[key] = data[key]
    safe.pop("source", None)
    return safe


def _opportunity_source_from_data(data: dict | None) -> str:
    if not isinstance(data, dict):
        return ""
    if data.get("source"):
        return str(data["source"])
    summary = _trade_plan_safe_summary_from_data(data)
    return str(summary.get("source") or "")


def _opportunity_dedupe_data(data: dict | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    dedupe_data = dict(data)
    summary = _trade_plan_safe_summary_from_data(data)
    if summary:
        dedupe_data.update(summary)
        if data.get("source"):
            dedupe_data["source"] = data["source"]
    return dedupe_data


def _opportunity_dedupe_key_from_data(
    *,
    push_type: str,
    suggestion_type: str,
    item_id: str,
    data: dict | None,
) -> str:
    dedupe_data = _opportunity_dedupe_data(data)
    has_plan_identity = any(
        dedupe_data.get(key) is not None and dedupe_data.get(key) != ""
        for key in ("profit_bucket", "required_quantity", "plan_signature")
    )
    if dedupe_data.get("dedupe_key") and not has_plan_identity:
        return str(dedupe_data["dedupe_key"])
    source = dedupe_data.get("source", "")
    strategy = dedupe_data.get("strategy", "")
    profit_bucket = dedupe_data.get("profit_bucket", "")
    required_quantity = dedupe_data.get("required_quantity", "")
    plan_signature = dedupe_data.get("plan_signature", "")
    parts = [push_type, suggestion_type, item_id]
    for value in (source, strategy, profit_bucket):
        if value:
            parts.append(str(value))
    if required_quantity not in (None, ""):
        parts.append(f"qty={required_quantity}")
    if plan_signature:
        parts.append(f"sig={plan_signature}")
    return ":".join(parts)


def _safe_proactive_record_message(push: ProactivePush) -> str:
    summary = _trade_plan_safe_summary_from_data(push.data)
    if not summary:
        return push.message
    return (
        f"交易机会 {push.item_id}: strategy={summary.get('strategy', '')} "
        f"profit={summary.get('profit', 0)}p roi={summary.get('roi_pct', 0)}% "
        f"bucket={summary.get('profit_bucket', '')}"
    )


class PriceMonitor:
    def __init__(
        self,
        order_fetcher: Callable[[str], list[dict]] = fetch_orders,
        interval_seconds: int = 300,
        memory_path=None,
        on_alert: Callable[[AlertNotification], None] | None = None,
        on_watch: Callable[[WatchNotification], None] | None = None,
        on_goal_opportunity: Callable[[dict], None] | None = None,
        on_proactive_push: Callable[[ProactivePush], None] | None = None,
        on_daily_report: Callable[[str], None] | None = None,
        on_fissure: Callable | None = None,
        on_cycle: Callable | None = None,
        on_baro_recommendation: Callable[[str], None] | None = None,
        price_db=None,
        knowledge: MarketKnowledge | None = None,
        trading_memory_db=None,
    ):
        self.order_fetcher = order_fetcher
        self.interval_seconds = interval_seconds
        self.memory_path = memory_path or MEMORY_PATH
        self.on_alert = on_alert
        self.on_watch = on_watch
        self.on_goal_opportunity = on_goal_opportunity
        self.on_proactive_push = on_proactive_push
        self.on_daily_report = on_daily_report
        self.on_fissure = on_fissure
        self.on_cycle = on_cycle
        self.on_baro_recommendation = on_baro_recommendation
        self.price_db = price_db
        self.trading_memory_db = trading_memory_db
        self.knowledge = knowledge or MarketKnowledge()
        self.event_tracker = EventTracker()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._notifications: list[AlertNotification] = []
        self._watch_notifications: list[WatchNotification] = []
        self._watch_last_notified: dict[str, str] = {}  # item_id -> "YYYY-MM-DD HH:MM"
        self._fissure_notified: dict[str, float] = {}  # dedup key -> timestamp
        self._cycle_last_state: dict[str, str] = {}
        self._cycle_notified: dict[str, float] = {}
        self._baro_recommendation_sent: str | None = None  # Baro start_time
        self._spike_notified: dict[str, float] = {}  # item_id -> timestamp
        self._vault_event_pushed: set[str] = set()  # vault event descriptions already pushed
        self._prime_access_pushed: set[str] = set()  # PA event descriptions already pushed
        self._lock = threading.Lock()
        self._scan_cycle_count = 0
        self._last_report_date: str | None = None
        self._scheduler: Scheduler | None = None
        self._last_scan_result: ScanResult | None = None
        self._event_checks_last_scan_cycle_count = 0
        self._market_snapshot_memory_last_written: dict[str, tuple[float, tuple[int | None, int | None]]] = {}
        self._opportunity_push_notified: dict[str, tuple[float, dict]] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._scheduler = self._build_scheduler()
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

    def drain_watch_notifications(self) -> list:
        with self._lock:
            result = list(self._watch_notifications)
            self._watch_notifications.clear()
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
        for snapshot in result.favorite_snapshots:
            self._record_market_snapshot_memory(snapshot)
        result.suggestions.extend(detect_opportunities(
            result.favorite_snapshots,
            opportunity_filter=memory.preferences.opportunity_filter,
        ))
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
        # Phase 4: 目标驱动扫描（规则引擎规划）
        items = self._load_items()
        goal_suggestions: list[ProactiveSuggestion] = []
        for goal in _unique_goals(memory.active_goals_list()):
            try:
                plan = plan_for_goal(goal)
                goal_results = execute_plan(
                    plan,
                    items,
                    self.order_fetcher,
                    opportunity_filter=memory.preferences.opportunity_filter,
                )
                for r in goal_results:
                    if r.get("profit", 0) > 0 and self._goal_result_matches_filter(r, memory.preferences.opportunity_filter):
                        data = self._goal_opportunity_data(goal, r)
                        goal_suggestions.append(ProactiveSuggestion(
                            item_id=r.get("item_id", ""),
                            suggestion_type="goal_opportunity",
                            priority=1 if r.get("roi_pct", 0) > 100 else 2,
                            message=(
                                f"目标「{goal.description}」发现机会: "
                                f"{r.get('item_name', '')} +{r.get('profit', 0)}p "
                                f"(ROI {r.get('roi_pct', 0)}%)。"
                                f"{data['rationale']}"
                            ),
                            data=data,
                        ))
            except Exception as exc:
                result.errors.append(f"goal {goal.goal_id}: {exc}")
        result.suggestions.extend(_unique_suggestions(goal_suggestions))
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
            if now.weekday() == 0 and in_window and week_key != last_notified:
                return True
        return False

    def _goal_result_matches_filter(self, result: dict, opportunity_filter: str) -> bool:
        opportunity_filter = normalize_opportunity_filter(opportunity_filter)
        if opportunity_filter == "all":
            return True
        if result.get("source") != "mod_flip":
            return False
        return _item_matches_opportunity_filter(result.get("item_id", ""), opportunity_filter)

    def _goal_opportunity_data(self, goal, result: dict) -> dict:
        data = {
            "source": result.get("source", ""),
            "strategy": result.get("strategy", ""),
            "profit": result.get("profit", 0),
            "roi_pct": result.get("roi_pct", 0),
            "buy_cost": result.get("buy_cost", 0),
            "sell_price": result.get("sell_price", 0),
            "risk": result.get("risk", ""),
            "goal_description": goal.description,
        }
        if "sets_affordable" in result:
            data["sets_affordable"] = result.get("sets_affordable")
        data["rationale"] = self._goal_opportunity_rationale(data)
        return data

    def _goal_opportunity_rationale(self, data: dict) -> str:
        source = data.get("source") or "unknown"
        source_label = {
            "mod_flip": "Mod/赋能翻转",
            "set_profit": "Prime 套装套利",
            "investment": "投资翻转",
        }.get(source, source)
        details = [f"原因：来源 {source_label}"]
        strategy = data.get("strategy")
        if strategy:
            details.append(f"策略 {strategy}")
        buy_cost = data.get("buy_cost")
        sell_price = data.get("sell_price")
        if buy_cost:
            details.append(f"预估成本 {buy_cost}p")
        if sell_price:
            details.append(f"目标卖价 {sell_price}p")
        details.append(f"预估利润 +{data.get('profit', 0)}p")
        details.append(f"ROI {data.get('roi_pct', 0)}%")
        risk = data.get("risk")
        if risk:
            details.append(f"风险 {risk}")
        return "，".join(details) + "。"

    def _load_items(self) -> list[dict]:
        """加载物品数据。"""
        import json
        items_path = config.DATA_DIR / "items_full.json"
        if items_path.exists():
            with items_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _run_knowledge_update(self, scan_result: ScanResult) -> None:
        """周期性知识库更新：从扫描结果中积累市场智能 + 刷新游戏事件。"""
        try:
            if not self.price_db:
                return
            # 从扫描结果提取 item_id 列表
            scanned_items = []
            for snap in scan_result.favorite_snapshots:
                scanned_items.append({"item_id": snap.item_id})

            # 刷新游戏事件，注入到知识库
            events = self.event_tracker.refresh()
            if scanned_items:
                self.knowledge.update_from_scan(scanned_items, self.price_db, events=events)

            self.knowledge.save()
        except Exception as exc:
            logger.warning("知识库更新失败: %s", exc)

    def _run_goal_generation(self) -> None:
        """规则驱动目标生成：从知识库评估市场状态，自动创建目标。"""
        try:
            from .price_history import PriceHistoryDB
            from .trade_history import TradeHistoryDB
            memory = AgentMemory.load(self.memory_path)
            price_db = self.price_db or PriceHistoryDB()
            trade_db = TradeHistoryDB()

            market_state = evaluate_market_state(price_db, trade_db, memory, self.knowledge)
            new_goals = generate_auto_goals(market_state, memory, self.knowledge, memory.trade_outcomes)
            if new_goals:
                for goal in new_goals:
                    memory = memory.with_goal(goal)
                memory.save(self.memory_path)
        except Exception as exc:
            logger.warning("自动目标生成失败: %s", exc)

    def _run_self_learning(self, memory: AgentMemory) -> None:
        """自学习闭环：用云端模型从交易数据中提炼规律，更新置信度。"""
        try:
            from .feedback import run_self_learning_cycle
            from .llm import _cloud_chat_sync

            outcomes = memory.trade_outcomes
            if len(outcomes) < 5:
                return

            existing = list(memory.learned_patterns or [])
            updated, new_patterns = run_self_learning_cycle(
                outcomes, existing, _cloud_chat_sync,
            )

            if new_patterns:
                memory = memory.with_patterns(new_patterns)
                logger.info("自学习发现 %d 条新规律", len(new_patterns))

            # 更新已有规律置信度
            if updated != existing:
                from dataclasses import replace
                memory = replace(memory, learned_patterns=updated)
                logger.info("自学习更新 %d 条规律置信度", len(updated))

            memory.save(self.memory_path)
        except Exception as exc:
            logger.debug("自学习闭环失败: %s", exc)

    def _record_market_snapshot_memory(self, snapshot: FavoriteSnapshot) -> None:
        db = self.trading_memory_db
        if db is None:
            return
        if snapshot.sell_price is None and snapshot.buy_price is None:
            return
        now = time.time()
        price_signature = (snapshot.sell_price, snapshot.buy_price)
        last_written = self._market_snapshot_memory_last_written.get(snapshot.item_id)
        if last_written:
            last_ts, last_signature = last_written
            if last_signature == price_signature and now - last_ts < MARKET_SNAPSHOT_MEMORY_MIN_SECONDS:
                return
        payload = {
            "source": MARKET_SNAPSHOT_MEMORY_SOURCE,
            "item_id": snapshot.item_id,
            "sell_price": snapshot.sell_price,
            "buy_price": snapshot.buy_price,
            "spread": (
                snapshot.sell_price - snapshot.buy_price
                if snapshot.sell_price is not None and snapshot.buy_price is not None
                else None
            ),
        }
        try:
            db.record_market_snapshot(
                item_name=snapshot.item_id,
                source=MARKET_SNAPSHOT_MEMORY_SOURCE,
                payload=payload,
            )
            self._market_snapshot_memory_last_written[snapshot.item_id] = (now, price_signature)
        except Exception as exc:
            logger.debug("市场快照长期记忆写入失败 %s: %s", snapshot.item_id, exc)

    def _record_proactive_push_memory(
        self,
        push: ProactivePush,
        source: str,
        extra: dict | None = None,
    ) -> None:
        db = self.trading_memory_db
        if db is None:
            return
        push_data = dict(push.data or {})
        metadata = {
            "source": source,
            "item_id": push.item_id,
            "item_display": push.item_display,
            "priority": push.priority,
            "action_suggestion": push.action_suggestion,
        }
        metadata.update(_safe_proactive_metadata_from_data(push_data))
        opportunity_source = _opportunity_source_from_data(push_data)
        if opportunity_source:
            metadata["opportunity_source"] = opportunity_source
        if push.push_type == "opportunity":
            metadata["dedupe_key"] = _opportunity_dedupe_key_from_data(
                push_type=push.push_type,
                suggestion_type=str(metadata.get("suggestion_type") or push_data.get("suggestion_type") or "opportunity"),
                item_id=push.item_id,
                data=push_data,
            )
        if extra:
            metadata.update(extra)
        try:
            db.record_push(
                push_type=push.push_type,
                message=_safe_proactive_record_message(push),
                item_name=push.item_id,
                metadata=metadata,
            )
        except Exception as exc:
            logger.debug("长期推送记忆写入失败 %s: %s", push.item_id, exc)

    def _is_trading_opportunity_push(self, push: ProactivePush, suggestion: ProactiveSuggestion) -> bool:
        suggestion_type = (push.data or {}).get("suggestion_type") or suggestion.suggestion_type
        return push.push_type == "opportunity" or suggestion_type in {"opportunity", "goal_opportunity"}

    def _opportunity_dedupe_key(self, push: ProactivePush, suggestion: ProactiveSuggestion) -> str:
        return _opportunity_dedupe_key_from_data(
            push_type=push.push_type,
            suggestion_type=suggestion.suggestion_type,
            item_id=push.item_id,
            data=push.data or suggestion.data or {},
        )

    def _has_material_opportunity_change(self, new_data: dict, old_metadata: dict) -> bool:
        threshold = config.PROACTIVE_OPPORTUNITY_MATERIAL_CHANGE_PCT
        safe_new_data = _opportunity_dedupe_data(new_data)
        for key in ("profit", "roi_pct"):
            try:
                new_value = float(safe_new_data.get(key, 0) or 0)
                old_value = float(old_metadata.get(key, 0) or 0)
            except (TypeError, ValueError):
                continue
            if old_value <= 0:
                continue
            if ((new_value - old_value) / old_value) * 100 >= threshold:
                return True
        return False

    def _should_suppress_opportunity_push(self, push: ProactivePush, suggestion: ProactiveSuggestion, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        key = self._opportunity_dedupe_key(push, suggestion)
        new_data = _opportunity_dedupe_data(push.data or suggestion.data or {})
        cutoff = datetime.now() - timedelta(hours=config.PROACTIVE_OPPORTUNITY_COOLDOWN_HOURS)
        db = self.trading_memory_db
        if db is not None:
            try:
                records = db.get_push_history(
                    push_type="opportunity",
                    item_name=push.item_id,
                    since=cutoff.isoformat(),
                )
                for record in records:
                    metadata = record.metadata or {}
                    if metadata.get("dedupe_key") == key:
                        return not self._has_material_opportunity_change(new_data, metadata)
                return False
            except Exception as exc:
                logger.debug("长期推送记忆读取失败 %s: %s", push.item_id, exc)
        existing = self._opportunity_push_notified.get(key)
        if not existing:
            return False
        last_ts, old_metadata = existing
        if now - last_ts >= config.PROACTIVE_OPPORTUNITY_COOLDOWN_HOURS * 3600:
            return False
        return not self._has_material_opportunity_change(new_data, old_metadata)

    def _mark_opportunity_push_sent(self, push: ProactivePush, suggestion: ProactiveSuggestion, now: float | None = None) -> None:
        now = time.time() if now is None else now
        key = self._opportunity_dedupe_key(push, suggestion)
        self._opportunity_push_notified[key] = (now, _opportunity_dedupe_data(push.data or suggestion.data or {}))

    def _run_proactive_push(self, scan_result: ScanResult, market_state=None) -> None:
        """规则驱动主动推送：模板化消息生成，无需 LLM。"""
        if not self.on_proactive_push:
            return

        from .price_history import PriceHistoryDB
        from .trade_history import TradeHistoryDB
        memory = AgentMemory.load(self.memory_path)

        # 计算市场状态（如果未传入）
        if market_state is None:
            price_db = self.price_db or PriceHistoryDB()
            trade_db = TradeHistoryDB()
            market_state = evaluate_market_state(price_db, trade_db, memory, self.knowledge)

        # 筛选 priority ≤ 2 的高价值建议
        high_priority = _unique_suggestions([s for s in scan_result.suggestions if s.priority <= 2])
        if not high_priority:
            return

        sent_count = 0
        for suggestion in high_priority:
            if sent_count >= config.PROACTIVE_OPPORTUNITY_MAX_PER_SCAN:
                break
            try:
                push = generate_proactive_message(
                    suggestion, market_state, self.knowledge, self.price_db,
                )
                if self._is_trading_opportunity_push(push, suggestion):
                    from .push import PushConfig
                    if not PushConfig.load().push_proactive:
                        continue
                    if not _item_matches_opportunity_filter(push.item_id, memory.preferences.opportunity_filter):
                        continue
                    if self._should_suppress_opportunity_push(push, suggestion):
                        continue
                self.on_proactive_push(push)
                sent_count += 1
                if self._is_trading_opportunity_push(push, suggestion):
                    self._mark_opportunity_push_sent(push, suggestion)
                self._record_proactive_push_memory(
                    push,
                    "rule_proactive_push",
                    {"suggestion_type": suggestion.suggestion_type},
                )
            except Exception as exc:
                logger.debug("主动推送失败 %s: %s", suggestion.item_id, exc)

    def _check_fissure_alerts(self) -> None:
        """检查裂缝订阅，匹配时触发通知。"""
        from .memory import AgentMemory, FissureAlert
        memory = AgentMemory.load(self.memory_path)
        if not memory.fissure_alerts:
            return

        fissures = self.event_tracker.get_active_fissures()
        if not fissures:
            return

        now = time.time()
        # 清理过期的去重记录
        expired_keys = [k for k, ts in self._fissure_notified.items() if now - ts > 3600]
        for k in expired_keys:
            del self._fissure_notified[k]

        for fissure in fissures:
            for alert in memory.fissure_alerts:
                if not alert.matches_fissure(
                    node=fissure.node,
                    node_display=fissure.node_display,
                    mission_type=fissure.mission_type,
                    mission_display=fissure.mission_display,
                    tier=fissure.tier,
                    tier_display=fissure.tier_display,
                    hard=fissure.hard,
                ):
                    continue
                # 去重：同一裂缝窗口只通知一次
                dedup_key = f"{fissure.node}|{fissure.mission_type}|{fissure.tier}|{fissure.expiry}"
                if dedup_key in self._fissure_notified:
                    continue
                self._fissure_notified[dedup_key] = now
                # 触发通知
                mode = "钢铁" if fissure.hard else "普通"
                msg = f"虚空裂缝匹配: {fissure.tier_display} {fissure.mission_display} {mode} @ {fissure.node_display}"
                logger.info("裂缝订阅匹配: %s", msg)
                if self.on_fissure:
                    try:
                        self.on_fissure(msg, fissure, alert)
                    except Exception as exc:
                        logger.debug("裂缝通知失败: %s", exc)

    def _check_cycle_alerts(self) -> None:
        from .events import cycle_timestamp
        memory = AgentMemory.load(self.memory_path)
        if not memory.cycle_alerts:
            return
        cycles = self.event_tracker.get_cycles()
        if not cycles:
            return
        now = time.time()
        expired_keys = [key for key, ts in self._cycle_notified.items() if now - ts > 86400]
        for key in expired_keys:
            del self._cycle_notified[key]
        for cycle in cycles:
            previous_state = self._cycle_last_state.get(cycle.cycle)
            for alert in memory.cycle_alerts:
                if not alert.matches_cycle(cycle.cycle, cycle.state):
                    continue
                if previous_state is None or previous_state == cycle.state:
                    continue
                activation_ts = cycle_timestamp(cycle.activation)
                if activation_ts and alert.created_at and alert.created_at > activation_ts:
                    continue
                dedup_key = f"{cycle.cycle}|{cycle.state}|{cycle.activation}|{cycle.expiry}"
                if dedup_key in self._cycle_notified:
                    continue
                self._cycle_notified[dedup_key] = now
                suffix = f"预计结束: {cycle.expiry}" if cycle.expiry else ""
                msg = f"{cycle.cycle_display}状态提醒：已变为{cycle.state_display}。{suffix}".rstrip()
                logger.info("状态订阅匹配: %s", msg)
                if self.on_cycle:
                    try:
                        self.on_cycle(msg, cycle, alert)
                    except Exception as exc:
                        logger.debug("状态通知失败: %s", exc)
            self._cycle_last_state[cycle.cycle] = cycle.state

    def _record_baro_recommendation_memory(self, recommendation, baro_event) -> None:
        db = self.trading_memory_db
        if db is None:
            return
        payload = {
            "source": "baro_recommendation",
            "event_type": baro_event.event_type,
            "event_description": baro_event.description,
            "baro_start_time": baro_event.start_time,
            "baro_end_time": baro_event.end_time,
            "item_name": recommendation.item_name,
            "market_id": recommendation.market_id,
            "ducat_cost": recommendation.ducat_cost,
            "credit_cost": recommendation.credit_cost,
            "rank": recommendation.rank,
            "max_rank": recommendation.max_rank,
            "item_kind": recommendation.item_kind,
            "best_buy_price": recommendation.best_buy_price,
            "best_sell_price": recommendation.best_sell_price,
        }
        try:
            db.record_recommendation(
                item_name=recommendation.market_id,
                recommendation_type="baro",
                reason=recommendation.reason,
                payload=payload,
            )
        except Exception as exc:
            logger.debug("Baro 推荐长期记忆写入失败 %s: %s", recommendation.market_id, exc)

    def _check_baro_recommendation(self) -> None:
        """检测 Baro 活跃时自动分析库存并推送推荐。"""
        events = self.event_tracker.get_active_events()
        baro_event = None
        for e in events:
            if e.event_type == "baro_visit" and e.baro_items:
                baro_event = e
                break
        if not baro_event:
            return
        # 每轮 Baro 只分析一次
        if self._baro_recommendation_sent == baro_event.start_time:
            return
        self._baro_recommendation_sent = baro_event.start_time
        logger.info("检测到 Baro 活跃，开始分析库存...")
        try:
            from .baro import analyze_baro_inventory, format_baro_report
            recommendations = analyze_baro_inventory(baro_event, self.order_fetcher)
            for recommendation in recommendations:
                self._record_baro_recommendation_memory(recommendation, baro_event)
            report = format_baro_report(recommendations)
            logger.info("Baro 推荐分析完成")
            if self.on_baro_recommendation:
                self.on_baro_recommendation(report)
        except Exception as exc:
            logger.warning("Baro 推荐分析失败: %s", exc)

    def _check_event_driven_push(self) -> None:
        """事件驱动推送：Vault 回归、Prime Access 上线等。"""
        if not self.on_proactive_push:
            return
        events = self.event_tracker.get_active_events()
        for event in events:
            # Prime Vault 回归
            if event.event_type == "prime_vault" and event.description not in self._vault_event_pushed:
                self._vault_event_pushed.add(event.description)
                item_text = ", ".join(
                    display_item_name(item_id) for item_id in event.items_affected[:3]
                ) if event.items_affected else "未知物品"
                push = ProactivePush(
                    item_id=event.items_affected[0] if event.items_affected else "unknown",
                    item_display=item_text,
                    push_type="opportunity",
                    priority=2,
                    message=f"{item_text} 已回归！建议关注相关遗物和部件价格变化，回归初期价格通常会有波动。",
                    action_suggestion="watch",
                )
                try:
                    self.on_proactive_push(push)
                    self._record_proactive_push_memory(
                        push,
                        "event_driven_push",
                        {
                            "event_type": event.event_type,
                            "event_description": event.description,
                            "items_affected": event.items_affected,
                        },
                    )
                    logger.info("Vault 回归推送: %s", event.description)
                except Exception as exc:
                    logger.debug("Vault 推送失败: %s", exc)

            # Prime Access
            if event.event_type == "prime_access" and event.description not in self._prime_access_pushed:
                self._prime_access_pushed.add(event.description)
                push = ProactivePush(
                    item_id="prime_access",
                    item_display="Prime Access",
                    push_type="recommendation",
                    priority=2,
                    message="新 Prime Access 已上线！新 Prime 物品价格波动期，建议观望 1-2 周再入手。同类旧 Prime 套装可能短期下跌。",
                    action_suggestion="watch",
                )
                try:
                    self.on_proactive_push(push)
                    self._record_proactive_push_memory(
                        push,
                        "event_driven_push",
                        {
                            "event_type": event.event_type,
                            "event_description": event.description,
                            "items_affected": event.items_affected,
                        },
                    )
                    logger.info("Prime Access 推送: %s", event.description)
                except Exception as exc:
                    logger.debug("Prime Access 推送失败: %s", exc)

    def _check_price_spikes(self, scanned_items: set[str]) -> list[ProactiveSuggestion]:
        """检测 3 小时内价格突变 >20%，每个物品每 6 小时最多推送一次。"""
        if not self.price_db:
            return []
        now = time.time()
        spike_window_hours = 3
        spike_threshold_pct = 20.0
        dedup_window = 6 * 3600  # 6 小时

        # 清理过期的去重记录
        expired = [k for k, ts in self._spike_notified.items() if now - ts > dedup_window]
        for k in expired:
            del self._spike_notified[k]

        results: list[ProactiveSuggestion] = []
        for item_id in scanned_items:
            if item_id in self._spike_notified:
                continue
            try:
                snapshots = self.price_db.recent_since(item_id, hours=spike_window_hours)
                if len(snapshots) < 2:
                    continue
                prices = [s.sell_price for s in snapshots if s.sell_price is not None]
                if len(prices) < 2:
                    continue
                oldest = prices[-1]  # DESC order, last = oldest
                newest = prices[0]   # first = newest
                if oldest == 0:
                    continue
                change_pct = ((newest - oldest) / oldest) * 100
                if abs(change_pct) < spike_threshold_pct:
                    continue
                direction = "暴涨" if change_pct > 0 else "暴跌"
                display = display_item_name(item_id)
                msg = (
                    f"{display} 3小时内{direction} {abs(change_pct):.0f}%！"
                    f"从 {oldest}p → {newest}p"
                )
                results.append(ProactiveSuggestion(
                    item_id=item_id,
                    suggestion_type="spike",
                    priority=1,
                    message=msg,
                ))
                self._spike_notified[item_id] = now
                logger.info("价格突变检测: %s", msg)
            except Exception as exc:
                logger.debug("价格突变检测失败 %s: %s", item_id, exc)
        return results

    def _check_daily_report(self) -> None:
        """检查是否需要发送每日报告到微信。"""
        from .push import (
            PushConfig, WxPusher, should_send_daily_report,
            format_buyers_with_whisper, format_sellers_with_whisper,
        )
        from .market import best_sellers, best_buyers
        from .names import display_item_name

        cfg = PushConfig.load()
        if not should_send_daily_report(cfg):
            return
        today = datetime.now().strftime("%Y-%m-%d")
        if self._last_report_date == today:
            return
        self._last_report_date = today

        try:
            memory = AgentMemory.load(self.memory_path)
            report_lines = [f"Warframe 每日价格表 ({today})", ""]
            has_data = False
            for item_id in memory.favorite_items:
                try:
                    orders = self.order_fetcher(item_id)
                    sellers = best_sellers(orders, limit=3)
                    buyers = best_buyers(orders, limit=3)
                    item_name = display_item_name(item_id)
                    if buyers:
                        report_lines.append(format_buyers_with_whisper(item_name, item_id, buyers))
                        report_lines.append("")
                    if sellers:
                        report_lines.append(format_sellers_with_whisper(item_name, item_id, sellers))
                        report_lines.append("")
                    has_data = True
                except Exception:
                    report_lines.append(f"{item_id} 查询失败")
                    report_lines.append("")
            if has_data:
                report_text = "\n".join(report_lines)
                client = WxPusher(cfg)
                client.send_text("Warframe 每日价格表", report_text)
                logger.info("每日报告已推送到微信")
                if self.on_daily_report:
                    try:
                        self.on_daily_report(report_text)
                    except Exception as exc:
                        logger.warning("每日报告回调异常: %s", exc)
        except Exception as exc:
            logger.warning("每日报告推送失败: %s", exc)

    def _maintenance_interval_seconds(self, scan_count_interval: int) -> int:
        return self.interval_seconds * scan_count_interval

    def _maintenance_initial_delay_seconds(self, scan_count_interval: int) -> int:
        return self.interval_seconds * max(scan_count_interval - 1, 0)

    def _run_knowledge_update_job(self) -> None:
        scan = self._last_scan_result
        if scan is None:
            return
        self._run_knowledge_update(scan)

    def _run_goal_generation_job(self) -> None:
        self._run_goal_generation()

    def _run_self_learning_job(self) -> None:
        memory = AgentMemory.load(self.memory_path)
        self._run_self_learning(memory)

    def _run_event_checks_job(self) -> None:
        if self._scan_cycle_count <= self._event_checks_last_scan_cycle_count:
            return
        self._event_checks_last_scan_cycle_count = self._scan_cycle_count
        try:
            self._check_fissure_alerts()
            self._check_cycle_alerts()
            self._check_baro_recommendation()
            self._check_event_driven_push()
            self._check_daily_report()
        except Exception as exc:
            logger.warning("事件检查任务异常: %s", exc)
            raise

    def scheduler_status_snapshot(self) -> dict[str, Any]:
        scheduler = self._scheduler
        jobs = [] if scheduler is None else serialize_scheduler_jobs(scheduler)
        thread = self._thread
        return {
            "running": thread is not None and thread.is_alive(),
            "has_scheduler": scheduler is not None,
            "total": len(jobs),
            "jobs": jobs,
        }

    def daily_report_status_snapshot(self) -> dict[str, Any]:
        from .push import PushConfig, should_send_daily_report

        cfg = PushConfig.load()
        return {
            "enabled": bool(cfg.enabled and cfg.push_daily_report),
            "report_time": cfg.report_time,
            "should_send_now": should_send_daily_report(cfg),
            "last_report_date": self._last_report_date,
        }

    def _build_scheduler(self) -> Scheduler:
        scheduler = Scheduler()
        scheduler.add_interval_job(
            PRICE_MONITOR_SCAN_JOB_ID,
            PRICE_MONITOR_SCAN_JOB_NAME,
            self._run_scan_cycle,
            self.interval_seconds,
            run_immediately=True,
        )
        scheduler.add_interval_job(
            PRICE_MONITOR_EVENT_CHECKS_JOB_ID,
            PRICE_MONITOR_EVENT_CHECKS_JOB_NAME,
            self._run_event_checks_job,
            self.interval_seconds,
            run_immediately=True,
        )
        scheduler.add_interval_job(
            PRICE_MONITOR_DAILY_REPORT_JOB_ID,
            PRICE_MONITOR_DAILY_REPORT_JOB_NAME,
            self._check_daily_report,
            self.interval_seconds,
        )
        scheduler.add_interval_job(
            PRICE_MONITOR_KNOWLEDGE_UPDATE_JOB_ID,
            PRICE_MONITOR_KNOWLEDGE_UPDATE_JOB_NAME,
            self._run_knowledge_update_job,
            self._maintenance_interval_seconds(config.KNOWLEDGE_UPDATE_INTERVAL),
            initial_delay_seconds=self._maintenance_initial_delay_seconds(config.KNOWLEDGE_UPDATE_INTERVAL),
        )
        scheduler.add_interval_job(
            PRICE_MONITOR_GOAL_GENERATION_JOB_ID,
            PRICE_MONITOR_GOAL_GENERATION_JOB_NAME,
            self._run_goal_generation_job,
            self._maintenance_interval_seconds(config.GOAL_GENERATION_INTERVAL),
            initial_delay_seconds=self._maintenance_initial_delay_seconds(config.GOAL_GENERATION_INTERVAL),
        )
        scheduler.add_interval_job(
            PRICE_MONITOR_SELF_LEARNING_JOB_ID,
            PRICE_MONITOR_SELF_LEARNING_JOB_NAME,
            self._run_self_learning_job,
            self._maintenance_interval_seconds(config.PATTERN_DISCOVERY_INTERVAL),
            initial_delay_seconds=self._maintenance_initial_delay_seconds(config.PATTERN_DISCOVERY_INTERVAL),
        )
        return scheduler

    def _run_scan_cycle(self) -> None:
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
            all_suggestions = list(scan.suggestions)

            # 价格突变检测（3小时内涨跌>20%）
            spike_items = {s.item_id for s in scan.favorite_snapshots}
            spike_suggestions = self._check_price_spikes(spike_items)
            all_suggestions.extend(spike_suggestions)

            # 规则驱动推送（无需 LLM）
            from .price_history import PriceHistoryDB
            from .trade_history import TradeHistoryDB
            price_db = self.price_db or PriceHistoryDB()
            trade_db = TradeHistoryDB()
            memory = AgentMemory.load(self.memory_path)
            market_state = evaluate_market_state(price_db, trade_db, memory, self.knowledge)

            enriched_scan = ScanResult(
                triggered_alerts=scan.triggered_alerts,
                watch_notifications=scan.watch_notifications,
                favorite_snapshots=scan.favorite_snapshots,
                suggestions=all_suggestions,
                errors=scan.errors,
            )
            self._run_proactive_push(enriched_scan, market_state)

            if all_suggestions:
                for suggestion in all_suggestions:
                    memory = memory.with_suggestion(suggestion)
                    if (
                        suggestion.suggestion_type == "goal_opportunity"
                        and self.on_goal_opportunity
                        and not (self.on_proactive_push and suggestion.priority <= 2)
                    ):
                        self.on_goal_opportunity({
                            "item_id": suggestion.item_id,
                            "message": suggestion.message,
                            "priority": suggestion.priority,
                        })
                memory.save(self.memory_path)

            self._scan_cycle_count += 1
            self._last_scan_result = scan

        except Exception as exc:
            logger.warning("监控主循环异常: %s", exc)

    def _run(self) -> None:
        scheduler = self._scheduler
        if scheduler is None:
            scheduler = self._build_scheduler()
            self._scheduler = scheduler
        while not self._stop_event.is_set():
            scheduler.tick()
            self._stop_event.wait(self.interval_seconds)
