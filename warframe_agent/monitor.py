from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from . import config
from .events import EventTracker
from .goals import execute_plan, plan_for_goal
from .knowledge import MarketKnowledge
from .market import best_sellers, fetch_orders, get_max_rank_from_orders
from .memory import AgentMemory, PriceAlert, ProactiveSuggestion, MEMORY_PATH
from .names import display_item_name
from .rules import (
    ProactivePush,
    evaluate_market_state,
    generate_auto_goals,
    generate_proactive_message,
)

logger = logging.getLogger(__name__)


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
        on_goal_opportunity: Callable[[dict], None] | None = None,
        on_proactive_push: Callable[[ProactivePush], None] | None = None,
        on_daily_report: Callable[[str], None] | None = None,
        on_fissure: Callable | None = None,
        on_baro_recommendation: Callable[[str], None] | None = None,
        price_db=None,
        knowledge: MarketKnowledge | None = None,
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
        self.on_baro_recommendation = on_baro_recommendation
        self.price_db = price_db
        self.knowledge = knowledge or MarketKnowledge()
        self.event_tracker = EventTracker()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._notifications: list[AlertNotification] = []
        self._watch_notifications: list[WatchNotification] = []
        self._watch_last_notified: dict[str, str] = {}  # item_id -> "YYYY-MM-DD HH:MM"
        self._fissure_notified: dict[str, float] = {}  # dedup key -> timestamp
        self._baro_recommendation_sent: str | None = None  # Baro start_time
        self._spike_notified: dict[str, float] = {}  # item_id -> timestamp
        self._vault_event_pushed: set[str] = set()  # vault event descriptions already pushed
        self._prime_access_pushed: set[str] = set()  # PA event descriptions already pushed
        self._lock = threading.Lock()
        self._scan_cycle_count = 0
        self._last_report_date: str | None = None

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
        for goal in memory.active_goals_list():
            try:
                plan = plan_for_goal(goal)
                goal_results = execute_plan(plan, items, self.order_fetcher)
                for r in goal_results:
                    if r.get("profit", 0) > 0:
                        result.suggestions.append(ProactiveSuggestion(
                            item_id=r.get("item_id", ""),
                            suggestion_type="goal_opportunity",
                            priority=1 if r.get("roi_pct", 0) > 100 else 2,
                            message=(
                                f"目标「{goal.description}」发现机会: "
                                f"{r.get('item_name', '')} +{r.get('profit', 0)}p "
                                f"(ROI {r.get('roi_pct', 0)}%)"
                            ),
                        ))
            except Exception as exc:
                result.errors.append(f"goal {goal.goal_id}: {exc}")
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
        high_priority = [s for s in scan_result.suggestions if s.priority <= 2]
        if not high_priority:
            return

        for suggestion in high_priority[:3]:
            try:
                push = generate_proactive_message(
                    suggestion, market_state, self.knowledge, self.price_db,
                )
                self.on_proactive_push(push)
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
                        if suggestion.suggestion_type == "goal_opportunity" and self.on_goal_opportunity:
                            self.on_goal_opportunity({
                                "item_id": suggestion.item_id,
                                "message": suggestion.message,
                                "priority": suggestion.priority,
                            })
                    memory.save(self.memory_path)

                # 周期性知识库更新 + 目标生成
                self._scan_cycle_count += 1
                if self._scan_cycle_count % config.KNOWLEDGE_UPDATE_INTERVAL == 0:
                    self._run_knowledge_update(scan)
                if self._scan_cycle_count % config.GOAL_GENERATION_INTERVAL == 0:
                    self._run_goal_generation()

                # 周期性自学习闭环
                if self._scan_cycle_count % config.PATTERN_DISCOVERY_INTERVAL == 0:
                    self._run_self_learning(memory)

                # 裂缝订阅检查
                self._check_fissure_alerts()

                # Baro 购买推荐
                self._check_baro_recommendation()

                # 事件驱动推送（Vault 回归、Prime Access）
                self._check_event_driven_push()

                # 每日报告微信推送
                self._check_daily_report()

            except Exception as exc:
                logger.warning("监控主循环异常: %s", exc)
            self._stop_event.wait(self.interval_seconds)
