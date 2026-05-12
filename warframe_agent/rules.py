"""规则引擎 — 替代监控器中所有 LLM 决策，纯规则驱动。"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .feedback import FeedbackAnalyzer, StrategyFeedback
from .goals import AgentGoal, TradeOutcome, create_goal
from .knowledge import CategoryHealth, MarketKnowledge
from .memory import AgentMemory, ProactiveSuggestion
from .price_history import PriceHistoryDB
from .trade_history import TradeHistoryDB
from .names import display_item_name


@dataclass(frozen=True)
class ProactivePush:
    item_id: str
    item_display: str
    push_type: str       # "opportunity" / "warning" / "recommendation"
    priority: int        # 1=critical, 2=important
    message: str
    action_suggestion: str  # "buy now" / "sell now" / "watch"
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MarketState:
    volatility_index: float = 0.0
    trend_direction: str = "neutral"   # "bullish" / "bearish" / "neutral"
    activity_level: str = "low"        # "high" / "medium" / "low"
    category_performance: dict[str, CategoryHealth] = field(default_factory=dict)
    anomaly_count: int = 0
    opportunity_count: int = 0
    best_category: str = ""


@dataclass(frozen=True)
class AdaptiveThresholds:
    """根据市场数据动态计算的阈值，替代硬编码常量。"""
    roi_good: float        # 市场平均 ROI 的 1.2 倍（最低 20）
    roi_excellent: float   # 市场平均 ROI 的 2.0 倍（最低 50）
    volatility_high: float # 市场平均波动率的 1.5 倍（最低 30）
    min_profit: float      # 市场平均利润的 0.8 倍（最低 3）


def compute_thresholds(knowledge: MarketKnowledge | None = None) -> AdaptiveThresholds:
    """从知识库计算动态阈值。无知识库时返回保守默认值。"""
    if not knowledge:
        return AdaptiveThresholds(roi_good=30, roi_excellent=50, volatility_high=50, min_profit=5)
    summary = knowledge.get_market_summary()
    avg_roi = summary.get("avg_roi", 30)
    avg_vol = summary.get("avg_volatility", 30)
    avg_profit = summary.get("avg_profit", 10)
    return AdaptiveThresholds(
        roi_good=max(20, avg_roi * 1.2),
        roi_excellent=max(50, avg_roi * 2.0),
        volatility_high=max(30, avg_vol * 1.5),
        min_profit=max(3, avg_profit * 0.8),
    )


def evaluate_market_state(
    price_db: PriceHistoryDB,
    trade_db: TradeHistoryDB,
    memory: AgentMemory,
    knowledge: MarketKnowledge | None = None,
) -> MarketState:
    """纯计算评估市场状态，无网络、无 LLM。"""
    if knowledge:
        summary = knowledge.get_market_summary()
        cat_health = summary.get("category_health", {})
        return MarketState(
            volatility_index=summary.get("volatility_index", 0),
            trend_direction=summary.get("trend_direction", "neutral"),
            activity_level="high" if summary.get("total_items", 0) > 20 else "medium" if summary.get("total_items", 0) > 5 else "low",
            category_performance=cat_health,
            anomaly_count=sum(1 for s in memory.recent_suggestions if s.suggestion_type == "anomaly"),
            opportunity_count=sum(1 for s in memory.recent_suggestions if s.suggestion_type in ("opportunity", "goal_opportunity")),
            best_category=summary.get("best_category", ""),
        )

    # 无知识库时从 trade_db 推断
    trades = trade_db.get_recent_trades(limit=50)
    return MarketState(
        volatility_index=0,
        trend_direction="neutral",
        activity_level="high" if len(trades) > 20 else "medium" if len(trades) > 5 else "low",
        category_performance={},
        anomaly_count=sum(1 for s in memory.recent_suggestions if s.suggestion_type == "anomaly"),
        opportunity_count=sum(1 for s in memory.recent_suggestions if s.suggestion_type in ("opportunity", "goal_opportunity")),
        best_category="",
    )


def _is_strategy_blocked(strategy: str, outcomes: list[TradeOutcome]) -> bool:
    """检查策略是否被反馈系统屏蔽（历史表现太差）。"""
    if not outcomes:
        return False
    fb = FeedbackAnalyzer().get_feedback_for(outcomes, strategy)
    return fb is not None and fb.sample_size >= 5 and not fb.recommended


def generate_auto_goals(
    market_state: MarketState,
    memory: AgentMemory,
    knowledge: MarketKnowledge | None = None,
    trade_outcomes: list[TradeOutcome] | None = None,
) -> list[AgentGoal]:
    """规则驱动目标生成，替代 LLM generate_goals_from_market。"""
    existing_keys = {(g.goal_type, g.target) for g in memory.active_goals}
    auto_count = sum(1 for g in memory.active_goals if g.description.startswith("[自动]"))
    goals: list[AgentGoal] = []
    outcomes = trade_outcomes or []
    thresholds = compute_thresholds(knowledge)

    def _can_add(goal_type: str, target: str) -> bool:
        nonlocal auto_count
        if auto_count >= config.MAX_AUTO_GOALS:
            return False
        if (goal_type, target) in existing_keys:
            return False
        return True

    cat = market_state.category_performance

    # 规则 1: mod 平均 ROI > roi_good → flip_mod
    mod_health = cat.get("mod")
    if mod_health and mod_health.avg_roi > thresholds.roi_good and _can_add("flip_mod", "mod_flip"):
        if not _is_strategy_blocked("mod_flip", outcomes):
            goals.append(create_goal(
                goal_type="flip_mod",
                description="[自动] Mod 翻转 — 高 ROI 机会",
                target="mod_flip",
                criteria={"min_roi": int(thresholds.roi_good), "budget": 500},
            ))
            auto_count += 1
            existing_keys.add(("flip_mod", "mod_flip"))

    # 规则 2: prime_set 机会 > 5 → build_set
    set_health = cat.get("prime_set")
    if set_health and set_health.opportunity_count > 5 and _can_add("build_set", "prime_sets"):
        if not _is_strategy_blocked("set_build", outcomes):
            goals.append(create_goal(
                goal_type="build_set",
                description="[自动] Prime 套装 — 多个机会",
                target="prime_sets",
                criteria={"min_profit": int(thresholds.min_profit)},
            ))
            auto_count += 1
            existing_keys.add(("build_set", "prime_sets"))

    # 规则 3: prime_set 平均 ROI > roi_good → find_bargain
    if set_health and set_health.avg_roi > thresholds.roi_good and _can_add("find_bargain", "prime_sets"):
        if not _is_strategy_blocked("bargain_hunt", outcomes):
            goals.append(create_goal(
                goal_type="find_bargain",
                description="[自动] Prime 套利 — ROI 活跃",
                target="prime_sets",
                criteria={"min_roi": int(thresholds.roi_good), "budget": 500},
            ))
            auto_count += 1
            existing_keys.add(("find_bargain", "prime_sets"))

    # 规则 4: 有异常 + 市场下行 → 保守 maximize_profit
    if market_state.anomaly_count > 0 and market_state.trend_direction == "bearish":
        if _can_add("maximize_profit", "all"):
            goals.append(create_goal(
                goal_type="maximize_profit",
                description="[自动] 保守策略 — 市场波动",
                target="all",
                criteria={"budget": 200, "min_roi": int(thresholds.roi_good)},
            ))

    return goals[:config.MAX_AUTO_GOALS]


def generate_proactive_message(
    suggestion: ProactiveSuggestion,
    market_state: MarketState,
    knowledge: MarketKnowledge | None = None,
    price_db: PriceHistoryDB | None = None,
) -> ProactivePush:
    """模板化推送消息，替代 LLM _run_proactive_push。"""
    item_id = suggestion.item_id
    item_display = display_item_name(item_id)

    # 获取知识库上下文
    event_ctx = None
    if knowledge:
        stats = knowledge.get_item_stats(item_id)
        if stats:
            event_ctx = stats.event_context

    # 异常类型
    if suggestion.suggestion_type == "anomaly":
        direction = "暴涨" if "暴涨" in suggestion.message or "spike" in suggestion.message else "暴跌"
        # 从 suggestion.message 提取数据（格式: "XX 价格暴涨！当前 Xp，均值 Xp，偏差 X%"）
        thresholds = compute_thresholds(knowledge)
        recommendation = _anomaly_recommendation(direction, market_state.volatility_index, event_ctx, thresholds)
        message = f"{item_display} 价格{direction}！{recommendation}"
        if event_ctx:
            message += f"（{event_ctx}）"
        action = "watch" if market_state.volatility_index > thresholds.volatility_high else ("buy now" if direction == "暴跌" else "sell now")
        return ProactivePush(
            item_id=item_id,
            item_display=item_display,
            push_type="warning",
            priority=suggestion.priority,
            message=message,
            action_suggestion=action,
            data={"suggestion_type": "anomaly"},
        )

    # 机会/目标机会类型
    if suggestion.suggestion_type in ("opportunity", "goal_opportunity"):
        action = "buy now" if suggestion.priority == 1 else "watch"
        push_type = "opportunity"
        message = suggestion.message
        if event_ctx:
            message += f"（注意：{event_ctx}）"
        return ProactivePush(
            item_id=item_id,
            item_display=item_display,
            push_type=push_type,
            priority=suggestion.priority,
            message=message,
            action_suggestion=action,
            data={"suggestion_type": suggestion.suggestion_type},
        )

    # 其他类型（trend 等）
    return ProactivePush(
        item_id=item_id,
        item_display=item_display,
        push_type="recommendation",
        priority=suggestion.priority,
        message=suggestion.message,
        action_suggestion="watch",
        data={"suggestion_type": suggestion.suggestion_type},
    )


def _anomaly_recommendation(direction: str, volatility: float, event_ctx: str | None, thresholds: AdaptiveThresholds | None = None) -> str:
    """根据异常方向、波动率、事件上下文生成建议。"""
    if event_ctx:
        if direction == "暴跌":
            return "可能受游戏活动影响，建议观望"
        return "可能受游戏活动影响，注意风险"

    vol_threshold = thresholds.volatility_high if thresholds is not None else config.DEFAULT_VOLATILITY_HIGH
    if volatility > vol_threshold:
        if direction == "暴跌":
            return "价格波动大，可能是抄底机会但需谨慎"
        return "价格波动大，可能是短期泡沫，建议观望"

    if direction == "暴跌":
        return "可能是抄底机会，建议少量买入"
    return "建议趁高价出售"


def decide_next_step(
    goal: AgentGoal,
    current_results: list[dict],
    completed_steps: list[str],
    iteration: int,
    max_iter: int = 3,
    trade_outcomes: list[TradeOutcome] | None = None,
) -> tuple[str, dict]:
    """决策树替代 LLM 动态规划。返回 (action, params)。"""
    if iteration >= max_iter:
        return ("stop", {})

    # 反馈系统：当前策略历史胜率 < 20% 且样本 >= 3 → 换策略
    if trade_outcomes:
        strategy_map = {
            "scan_mod_flip": "mod_flip",
            "scan_set_profit": "set_build",
            "scan_investment": "bargain_hunt",
        }
        for step in completed_steps:
            strategy = strategy_map.get(step)
            if strategy:
                fb = FeedbackAnalyzer().get_feedback_for(trade_outcomes, strategy)
                if fb and fb.sample_size >= 3 and fb.win_rate < 0.2:
                    return ("switch_strategy", {"reason": "low_win_rate", "strategy": strategy})

    # 结果为空 → 换扫描器
    if not current_results:
        all_actions = {"scan_mod_flip", "scan_set_profit", "scan_investment"}
        tried = set(completed_steps)
        remaining = all_actions - tried
        if remaining:
            next_action = remaining.pop()
            params = {"min_roi_pct": 100} if next_action == "scan_mod_flip" else {"min_profit": 5} if next_action == "scan_set_profit" else {"budget": 500, "min_roi_pct": 10}
            return (next_action, params)
        return ("stop", {})

    # ROI 过高 → 可能是陈旧数据，停止
    best_roi = max((r.get("roi_pct", 0) for r in current_results), default=0)
    if best_roi > 500:
        return ("stop", {})

    # ROI > 100 且没试过 set_profit → 试试
    if best_roi > 100 and "scan_set_profit" not in completed_steps:
        return ("scan_set_profit", {"min_profit": 5})

    # ROI < 50 且没试过 mod_flip → 试试
    if best_roi < 50 and "scan_mod_flip" not in completed_steps:
        return ("scan_mod_flip", {"min_roi_pct": 100})

    return ("stop", {})
