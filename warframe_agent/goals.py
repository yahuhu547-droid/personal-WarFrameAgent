"""目标引擎 — Agent 自主目标、执行计划、反馈学习。"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from . import config
from .market import fetch_orders
from .mod_flipper import scan_all_mod_flips
from .set_profit import scan_all_set_profits
from .investment import scan_prime_investments
from .scout import scout_mod_candidates, scout_set_candidates, scout_investment_candidates

logger = logging.getLogger(__name__)

GOALS_PATH = config.DATA_DIR / "goals.json"
_GOAL_NUMBER_PATTERN = r"(?:\d+|[一二两三四五六七八九十百千万]+)"
_GOAL_PLATINUM_UNIT_PATTERN = r"(?:p|pt|白金|铂金|platinum)?"
_GOAL_DEFAULT_CRITERIA = {"budget": 500, "min_roi": 10}
_GOAL_RISK_LABELS = {"low": "低风险", "medium": "中风险", "high": "高风险"}


# ── 数据结构 ──────────────────────────────────────────────

@dataclass(frozen=True)
class AgentGoal:
    goal_id: str
    goal_type: str        # maximize_profit / find_bargain / build_set / flip_mod
    description: str
    target: str           # prime_sets / mod_flip / arcane / 具体 item_id
    criteria: dict        # {"min_roi": 50, "budget": 500}
    status: str           # active / achieved / abandoned / paused
    created_at: str
    results: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionStep:
    step_id: str
    goal_id: str
    action: str           # scan_mod_flip / scan_set_profit / scan_investment / check_price
    params: dict
    status: str = "pending"   # pending / running / done / failed
    result: dict | None = None


@dataclass(frozen=True)
class GoalExecutionPlan:
    goal_id: str
    steps: list[ExecutionStep]
    created_at: str


@dataclass(frozen=True)
class TradeOutcome:
    outcome_id: str
    goal_id: str
    action: str           # bought / sold / skipped
    item_id: str
    price: int
    expected_profit: int
    actual_profit: int
    user_feedback: str    # good / bad / ignored
    timestamp: str


# ── 目标创建 ──────────────────────────────────────────────

def create_goal(
    goal_type: str,
    description: str,
    target: str = "all",
    criteria: dict | None = None,
) -> AgentGoal:
    """创建一个新目标。"""
    return AgentGoal(
        goal_id=uuid.uuid4().hex[:12],
        goal_type=goal_type,
        description=description,
        target=target,
        criteria=criteria or {},
        status="active",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _parse_chinese_positive_int(text: str) -> int | None:
    digits = {
        "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    current = 0
    matched = False
    for char in text:
        if char in digits:
            current = digits[char]
            matched = True
        elif char in units:
            unit = units[char]
            matched = True
            if current == 0 and unit == 10:
                current = 1
            total += current * unit
            current = 0
        else:
            return None
    if not matched:
        return None
    return total + current


def _parse_goal_number(text: str | None) -> int | None:
    if not text:
        return None
    normalized = re.sub(r"[,，_\s]", "", text).lower()
    if normalized.isdigit():
        return int(normalized)
    return _parse_chinese_positive_int(normalized)


def _extract_goal_amount(description: str, patterns: Iterable[str]) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, description, flags=re.IGNORECASE)
        if match:
            amount = _parse_goal_number(match.group(1))
            if amount is not None:
                return amount
    return None


def _extract_goal_timeframe_days(description: str) -> int | None:
    if re.search(r"(今天|今日|当天)", description):
        return 1
    for match in re.finditer(rf"({_GOAL_NUMBER_PATTERN})\s*(?:个)?(天|日|周|星期|月)", description):
        amount = _parse_goal_number(match.group(1))
        if amount is None:
            continue
        unit = match.group(2)
        if unit in ("周", "星期"):
            return amount * 7
        if unit == "月":
            return amount * 30
        return amount
    return None


def _extract_goal_risk(description: str) -> str | None:
    if re.search(r"(低风险|风险低|稳健|保守)", description):
        return "low"
    if re.search(r"(高风险|风险高|激进|冲刺)", description):
        return "high"
    if re.search(r"(中风险|风险适中|均衡|平衡)", description):
        return "medium"
    return None


def parse_goal_description_criteria(description: str) -> dict:
    """Parse common Chinese goal wording into deterministic goal criteria."""
    criteria = dict(_GOAL_DEFAULT_CRITERIA)
    text = (description or "").strip()
    if not text:
        return criteria

    target_profit = _extract_goal_amount(text, [
        rf"(?:赚到|赚取|赚|盈利|利润|收益|攒|存)\s*({_GOAL_NUMBER_PATTERN})\s*{_GOAL_PLATINUM_UNIT_PATTERN}",
        rf"({_GOAL_NUMBER_PATTERN})\s*(?:p|pt|白金|铂金|platinum)\s*(?:利润|收益|盈利|目标)",
    ])
    if target_profit is not None:
        criteria["target_profit"] = target_profit
        criteria["target_amount"] = target_profit

    timeframe_days = _extract_goal_timeframe_days(text)
    if timeframe_days is not None:
        criteria["timeframe_days"] = timeframe_days

    budget = _extract_goal_amount(text, [
        rf"(?:预算|本金|投入|本钱|资金)\s*(?:控制在|不超过|上限|为|是|:|：)?\s*({_GOAL_NUMBER_PATTERN})\s*{_GOAL_PLATINUM_UNIT_PATTERN}",
    ])
    if budget is not None:
        criteria["budget"] = budget

    min_roi = _extract_goal_amount(text, [
        rf"(?:最低\s*)?(?:roi|回报率|收益率)\s*(?:不低于|至少|>=|大于|超过|为|是|:|：)?\s*({_GOAL_NUMBER_PATTERN})\s*%?",
        rf"(?:最低|至少|不低于|超过|大于)\s*({_GOAL_NUMBER_PATTERN})\s*%?\s*(?:roi|回报率|收益率)",
    ])
    if min_roi is not None:
        criteria["min_roi"] = min_roi

    risk = _extract_goal_risk(text)
    if risk:
        criteria["risk"] = risk

    return criteria


def format_goal_criteria_summary(criteria: dict) -> str:
    parts = []
    if criteria.get("target_profit") is not None:
        parts.append(f"目标利润 {criteria['target_profit']}p")
    if criteria.get("timeframe_days") is not None:
        parts.append(f"周期 {criteria['timeframe_days']} 天")
    if criteria.get("budget") is not None:
        parts.append(f"预算 {criteria['budget']}p")
    if criteria.get("risk") is not None:
        parts.append(_GOAL_RISK_LABELS.get(criteria["risk"], str(criteria["risk"])))
    if criteria.get("min_roi") is not None:
        parts.append(f"最低 ROI {criteria['min_roi']}%")
    return "；".join(parts)


# ── 计划生成 ──────────────────────────────────────────────

def plan_for_goal(goal: AgentGoal) -> GoalExecutionPlan:
    """根据目标类型生成执行计划。"""
    steps = []
    budget = goal.criteria.get("budget", 500)
    min_roi = goal.criteria.get("min_roi", 10)
    limit = goal.criteria.get("limit", 20)

    if goal.goal_type == "maximize_profit":
        steps = [
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_mod_flip",
                params={"min_roi_pct": max(min_roi, 100), "limit": limit},
            ),
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_set_profit",
                params={"min_profit": 5, "limit": limit},
            ),
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_investment",
                params={"budget": budget, "min_roi_pct": min_roi, "limit": limit},
            ),
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="rank_results",
                params={"budget": budget},
            ),
        ]
    elif goal.goal_type == "flip_mod":
        steps = [
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_mod_flip",
                params={"min_roi_pct": min_roi, "limit": limit},
            ),
        ]
    elif goal.goal_type == "build_set":
        steps = [
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_investment",
                params={"budget": budget, "min_roi_pct": min_roi, "limit": limit},
            ),
        ]
    elif goal.goal_type == "find_bargain":
        steps = [
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_investment",
                params={"budget": budget, "min_roi_pct": min_roi, "limit": limit},
            ),
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_mod_flip",
                params={"min_roi_pct": min_roi, "limit": limit},
            ),
        ]
    elif goal.goal_type == "earn_platinum":
        steps = [
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_mod_flip",
                params={"min_roi_pct": 50, "limit": 30},
            ),
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_set_profit",
                params={"min_profit": 3, "limit": 30},
            ),
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_investment",
                params={"budget": budget, "min_roi_pct": 5, "limit": 30},
            ),
        ]
    else:
        steps = [
            ExecutionStep(
                step_id=uuid.uuid4().hex[:8],
                goal_id=goal.goal_id,
                action="scan_investment",
                params={"budget": budget, "min_roi_pct": min_roi, "limit": limit},
            ),
        ]

    return GoalExecutionPlan(
        goal_id=goal.goal_id,
        steps=steps,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# ── 计划执行 ──────────────────────────────────────────────

def execute_plan(
    plan: GoalExecutionPlan,
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    opportunity_filter: str = "all",
) -> list[dict]:
    """执行计划中的所有步骤，收集结果。"""
    all_results = []
    budget = 500

    for step in plan.steps:
        try:
            if step.action == "scan_mod_flip":
                raw = scan_all_mod_flips(
                    items, order_fetcher,
                    min_roi_pct=step.params.get("min_roi_pct", 100),
                    limit=step.params.get("limit", 20),
                    scout_fn=scout_mod_candidates,
                    opportunity_filter=opportunity_filter,
                )
                for r in raw:
                    all_results.append({
                        "source": "mod_flip",
                        "item_id": r.item_id,
                        "item_name": r.display_name.split(" / ")[0],
                        "profit": r.flip_profit,
                        "roi_pct": r.roi_pct,
                        "buy_cost": r.r0_buy_price,
                        "sell_price": r.r10_sell_price,
                        "risk": "medium",
                    })

            elif step.action == "scan_set_profit" and opportunity_filter == "all":
                raw = scan_all_set_profits(
                    items, order_fetcher,
                    min_profit=step.params.get("min_profit", 5),
                    limit=step.params.get("limit", 20),
                    scout_fn=scout_set_candidates,
                )
                for r in raw:
                    all_results.append({
                        "source": "set_profit",
                        "item_id": r.base_id,
                        "item_name": r.display_name.split(" / ")[0],
                        "profit": r.best_profit,
                        "roi_pct": round(r.best_profit / max(r.parts_buy_total, 1) * 100, 1),
                        "buy_cost": r.parts_buy_total,
                        "sell_price": r.set_sell_price or 0,
                        "risk": "medium",
                    })

            elif step.action == "scan_investment" and opportunity_filter == "all":
                budget = step.params.get("budget", 500)
                raw = scan_prime_investments(
                    items, order_fetcher,
                    budget=budget,
                    min_roi_pct=step.params.get("min_roi_pct", 10),
                    limit=step.params.get("limit", 20),
                    scout_fn=lambda groups: scout_investment_candidates(groups, budget=budget),
                )
                for r in raw:
                    all_results.append({
                        "source": "investment",
                        "item_id": r.set_item_id,
                        "item_name": r.display_name,
                        "profit": r.total_profit,
                        "roi_pct": r.roi_pct,
                        "buy_cost": r.buy_cost,
                        "sell_price": r.sell_price,
                        "risk": r.risk_level,
                        "sets_affordable": r.sets_affordable,
                        "strategy": r.strategy,
                    })

            elif step.action == "rank_results":
                budget = step.params.get("budget", 500)

        except Exception as exc:
            logger.debug("计划步骤执行失败 %s: %s", step.action, exc)
            continue

    # 按 ROI 排序，去重
    seen = set()
    unique = []
    for r in sorted(all_results, key=lambda x: x.get("roi_pct", 0), reverse=True):
        key = r.get("item_id", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


# ── 反馈学习 ──────────────────────────────────────────────

def calculate_opportunity_score(
    opportunity: dict,
    trade_outcomes: list[TradeOutcome],
) -> float:
    """基于反馈历史调整机会评分。"""
    base_score = opportunity.get("roi_pct", 0)

    # 统计同类 source 的反馈
    source = opportunity.get("source", "")
    good = sum(1 for t in trade_outcomes if t.user_feedback == "good" and _matches_source(t, source))
    bad = sum(1 for t in trade_outcomes if t.user_feedback == "bad" and _matches_source(t, source))
    total = good + bad

    if total == 0:
        return base_score

    # 正反馈加权，负反馈减权
    good_rate = good / total
    if good_rate > 0.7:
        return base_score * 1.2  # +20%
    elif good_rate < 0.3:
        return base_score * 0.7  # -30%
    return base_score


def _matches_source(outcome: TradeOutcome, source: str) -> bool:
    """判断交易结果是否匹配某个来源。"""
    if source == "mod_flip":
        return "mod" in outcome.item_id.lower() or "primed" in outcome.item_id.lower()
    if source in ("set_profit", "investment"):
        return "_set" in outcome.item_id or "_prime_" in outcome.item_id
    return True


def record_trade_outcome(
    goal_id: str,
    action: str,
    item_id: str,
    price: int,
    expected_profit: int = 0,
    actual_profit: int = 0,
    user_feedback: str = "ignored",
) -> TradeOutcome:
    """记录一次交易结果。"""
    return TradeOutcome(
        outcome_id=uuid.uuid4().hex[:12],
        goal_id=goal_id,
        action=action,
        item_id=item_id,
        price=price,
        expected_profit=expected_profit,
        actual_profit=actual_profit,
        user_feedback=user_feedback,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ── 用户目标分解 ──────────────────────────────────────────

@dataclass(frozen=True)
class GoalProgress:
    goal_id: str
    target_amount: int
    current_amount: int
    remaining: int
    steps_completed: int
    steps_total: int
    estimated_completion: str


def decompose_platinum_goal(
    target_amount: int,
    budget: int,
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
) -> list[dict]:
    """将"赚 N 白金"目标分解为具体步骤。

    运行 3 个扫描器 → 按 total_profit 降序 → 贪心选取直到累计利润 ≥ 目标。
    返回步骤列表: [{"step": 1, "item_name": ..., "strategy": ..., "estimated_profit": ..., "source": ...}]
    """
    all_results: list[dict] = []

    # mod_flipper
    try:
        flips = scan_all_mod_flips(items, order_fetcher, min_roi_pct=50, limit=30, scout_fn=scout_mod_candidates)
        for r in flips:
            all_results.append({
                "item_id": r.item_id,
                "item_name": r.display_name.split(" / ")[0],
                "strategy": f"买 R0 {r.r0_buy_price}p → 卖 R{r.max_rank} {r.r10_sell_price}p",
                "estimated_profit": r.flip_profit,
                "source": "mod_flip",
                "cost": r.r0_buy_price,
            })
    except Exception as exc:
        logger.debug("Mod 翻转扫描失败: %s", exc)

    # set_profit
    try:
        sets = scan_all_set_profits(items, order_fetcher, min_profit=3, limit=30, scout_fn=scout_set_candidates)
        for r in sets:
            cost = r.parts_buy_total
            all_results.append({
                "item_id": r.base_id,
                "item_name": r.display_name.split(" / ")[0],
                "strategy": f"{r.best_strategy}，利润 +{r.best_profit}p",
                "estimated_profit": r.best_profit,
                "source": "set_profit",
                "cost": cost,
            })
    except Exception as exc:
        logger.debug("套装利润扫描失败: %s", exc)

    # investment
    try:
        invests = scan_prime_investments(items, order_fetcher, budget=budget, min_roi_pct=5, limit=30, scout_fn=lambda groups: scout_investment_candidates(groups, budget=budget))
        for r in invests:
            all_results.append({
                "item_id": r.set_item_id,
                "item_name": r.display_name,
                "strategy": f"{r.strategy}，ROI {r.roi_pct:.1f}%",
                "estimated_profit": r.total_profit,
                "source": "investment",
                "cost": r.buy_cost,
            })
    except Exception as exc:
        logger.debug("投资扫描失败: %s", exc)

    # 按利润降序排序，贪心选取
    all_results.sort(key=lambda x: x["estimated_profit"], reverse=True)
    selected: list[dict] = []
    cumulative = 0
    for r in all_results:
        if r["estimated_profit"] <= 0:
            continue
        # 预算检查
        if r["cost"] > budget:
            continue
        selected.append(r)
        cumulative += r["estimated_profit"]
        if cumulative >= target_amount:
            break

    # 添加步骤编号
    for i, s in enumerate(selected, 1):
        s["step"] = i

    return selected


def track_goal_progress(
    goal_id: str,
    target_amount: int,
    trade_outcomes: list[TradeOutcome],
) -> GoalProgress:
    """追踪目标进度。"""
    related = [t for t in trade_outcomes if t.goal_id == goal_id]
    current = sum(t.actual_profit for t in related)
    completed = sum(1 for t in related if t.user_feedback == "good")
    remaining = max(target_amount - current, 0)
    return GoalProgress(
        goal_id=goal_id,
        target_amount=target_amount,
        current_amount=current,
        remaining=remaining,
        steps_completed=completed,
        steps_total=len(related),
        estimated_completion=f"还需 {remaining}p" if remaining > 0 else "目标已达成",
    )


# ── LLM 驱动目标生成 ──────────────────────────────────────

@dataclass(frozen=True)
class MarketContext:
    """聚合市场数据，供 LLM 分析。"""
    top_mod_flips: list[dict]
    top_set_profits: list[dict]
    top_investments: list[dict]
    anomalies: list[dict]
    active_goals: list[AgentGoal]
    trade_outcomes: list[TradeOutcome]
    user_profile: object | None  # UserProfile
    learned_patterns: list[dict]


def _build_goal_generation_prompt(context: MarketContext) -> str:
    """构建目标生成的 LLM prompt。"""
    active_desc = [
        f"- {g.goal_type}: {g.description} (状态: {g.status})"
        for g in context.active_goals
    ]
    patterns_desc = [
        f"- [{p.get('category', '?')}] {p['description']} (置信度: {p.get('confidence', 0.5)})"
        for p in context.learned_patterns
    ]
    profile_desc = ""
    if context.user_profile:
        p = context.user_profile
        profile_desc = (
            f"- 交易倾向: {p.preferred_trade_type}\n"
            f"- 偏好类别: {', '.join(p.favorite_categories[:3]) if p.favorite_categories else '无'}"
        )

    return (
        "你是 Warframe 交易策略师。根据当前市场数据，决定应该关注哪些交易目标。\n\n"
        f"## 当前市场数据\n\n"
        f"### Mod翻转 Top5\n```json\n{json.dumps(context.top_mod_flips[:5], ensure_ascii=False)}\n```\n\n"
        f"### 套装利润 Top5\n```json\n{json.dumps(context.top_set_profits[:5], ensure_ascii=False)}\n```\n\n"
        f"### 投资机会 Top5\n```json\n{json.dumps(context.top_investments[:5], ensure_ascii=False)}\n```\n\n"
        f"### 价格异常\n```json\n{json.dumps(context.anomalies[:3], ensure_ascii=False)}\n```\n\n"
        f"### 当前活跃目标\n{chr(10).join(active_desc) if active_desc else '无'}\n\n"
        f"### 用户偏好\n{profile_desc or '无'}\n\n"
        f"### 已发现的市场规律\n{chr(10).join(patterns_desc) if patterns_desc else '暂无'}\n\n"
        "请生成 1-3 个目标，返回 JSON 数组，每个目标格式:\n"
        '{"goal_type": "...", "description": "...", "target": "...", "criteria": {...}, "reasoning": "..."}\n\n'
        "goal_type 可选: maximize_profit, flip_mod, build_set, find_bargain\n"
        "description 用中文，简洁描述目标。\n"
        "target: prime_sets / mod / all / 具体 item_id\n"
        "criteria: {budget: 白金数, min_roi: 最低ROI%}\n"
        "不要创建与现有活跃目标重复的目标。\n"
        "只返回 JSON 数组，不要解释。"
    )


def _parse_generated_goals(response: str, existing_goals: list[AgentGoal]) -> list[AgentGoal]:
    """解析 LLM 返回的目标 JSON，去重。"""
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if not match:
        return []
    try:
        raw_goals = json.loads(match.group())
    except (json.JSONDecodeError, ValueError):
        return []

    # 去重 key: goal_type + target
    existing_keys = {(g.goal_type, g.target) for g in existing_goals}
    goals = []
    for g in raw_goals:
        if not isinstance(g, dict):
            continue
        goal_type = g.get("goal_type", "")
        if goal_type not in ("maximize_profit", "flip_mod", "build_set", "find_bargain"):
            continue
        target = g.get("target", "all")
        key = (goal_type, target)
        if key in existing_keys:
            continue
        existing_keys.add(key)

        desc = g.get("description", "")
        if not desc:
            continue
        # 自动目标加前缀
        if not desc.startswith("[自动]"):
            desc = f"[自动] {desc}"

        criteria = g.get("criteria", {})
        goals.append(create_goal(
            goal_type=goal_type,
            description=desc,
            target=target,
            criteria=criteria,
        ))
    return goals[:3]


def generate_goals_from_market(
    context: MarketContext,
    llm_caller: Callable[[list[dict]], str],
) -> list[AgentGoal]:
    """用 LLM 分析市场数据，生成目标。"""
    prompt = _build_goal_generation_prompt(context)
    try:
        response = llm_caller([
            {"role": "system", "content": "你是 Warframe 交易策略师。只返回 JSON。"},
            {"role": "user", "content": prompt},
        ])
    except Exception as exc:
        logger.debug("LLM 目标生成失败: %s", exc)
        return []
    return _parse_generated_goals(response, context.active_goals)


# ── 动态执行规划（ReAct 风格）──────────────────────────────

def _build_next_step_prompt(
    goal: AgentGoal,
    completed_steps: list[dict],
    all_results: list[dict],
    budget: int,
    elapsed_seconds: float,
) -> str:
    """构建"下一步做什么"的 LLM prompt。"""
    best_roi = max((r.get("roi_pct", 0) for r in all_results), default=0)
    best_profit = max((r.get("profit", 0) for r in all_results), default=0)
    step_summary = "\n".join(
        f"- {s['action']}: 发现 {s['count']} 个结果, 最佳 ROI {s['best_roi']}%"
        for s in completed_steps
    )

    return (
        f"目标: {goal.description}\n"
        f"目标类型: {goal.goal_type}\n"
        f"预算: {budget}p\n"
        f"已用时间: {elapsed_seconds:.0f}s\n\n"
        f"已完成步骤:\n{step_summary or '无'}\n\n"
        f"当前发现: {len(all_results)} 个机会, 最佳 ROI {best_roi}%, 最佳利润 {best_profit}p\n\n"
        "下一步应该做什么？选项:\n"
        "- scan_mod_flip: 扫描 Mod 翻转 (参数: min_roi_pct, limit)\n"
        "- scan_set_profit: 扫描套装利润 (参数: min_profit, limit)\n"
        "- scan_investment: 扫描投资机会 (参数: budget, min_roi_pct, limit)\n"
        "- stop: 结果已足够好，停止\n\n"
        '返回 JSON: {"action": "...", "params": {...}, "reason": "..."}\n'
        "如果结果已经很好或时间不够，返回 stop。只返回 JSON。"
    )


def _parse_next_step(response: str) -> tuple[str, dict, str]:
    """解析 LLM 返回的下一步决策。"""
    match = re.search(r"\{.*\}", response, re.DOTALL)
    if not match:
        return "stop", {}, "无法解析"
    try:
        data = json.loads(match.group())
        action = data.get("action", "stop")
        params = data.get("params", {})
        reason = data.get("reason", "")
        if action not in ("scan_mod_flip", "scan_set_profit", "scan_investment", "stop"):
            action = "stop"
        return action, params, reason
    except (json.JSONDecodeError, ValueError):
        return "stop", {}, "JSON 解析失败"


def _execute_single_step(
    action: str,
    params: dict,
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]],
) -> list[dict]:
    """执行单个扫描步骤，返回标准化结果。"""
    results = []
    try:
        if action == "scan_mod_flip":
            raw = scan_all_mod_flips(
                items, order_fetcher,
                min_roi_pct=params.get("min_roi_pct", 100),
                limit=params.get("limit", 20),
                scout_fn=scout_mod_candidates,
            )
            for r in raw:
                results.append({
                    "source": "mod_flip", "item_id": r.item_id,
                    "item_name": r.display_name.split(" / ")[0],
                    "profit": r.flip_profit, "roi_pct": r.roi_pct,
                    "buy_cost": r.r0_buy_price, "sell_price": r.r10_sell_price,
                    "risk": "medium",
                })
        elif action == "scan_set_profit":
            raw = scan_all_set_profits(
                items, order_fetcher,
                min_profit=params.get("min_profit", 5),
                limit=params.get("limit", 20),
                scout_fn=scout_set_candidates,
            )
            for r in raw:
                results.append({
                    "source": "set_profit", "item_id": r.base_id,
                    "item_name": r.display_name.split(" / ")[0],
                    "profit": r.best_profit,
                    "roi_pct": round(r.best_profit / max(r.parts_buy_total, 1) * 100, 1),
                    "buy_cost": r.parts_buy_total,
                    "sell_price": r.set_sell_price or 0,
                    "risk": "medium",
                })
        elif action == "scan_investment":
            budget_val = params.get("budget", 500)
            raw = scan_prime_investments(
                items, order_fetcher,
                budget=budget_val,
                min_roi_pct=params.get("min_roi_pct", 10),
                limit=params.get("limit", 20),
                scout_fn=lambda groups: scout_investment_candidates(groups, budget=budget_val),
            )
            for r in raw:
                results.append({
                    "source": "investment", "item_id": r.set_item_id,
                    "item_name": r.display_name,
                    "profit": r.total_profit, "roi_pct": r.roi_pct,
                    "buy_cost": r.buy_cost, "sell_price": r.sell_price,
                    "risk": r.risk_level,
                    "sets_affordable": r.sets_affordable,
                    "strategy": r.strategy,
                })
    except Exception as exc:
        logger.debug("投资顾问扫描失败: %s", exc)
    return results


def execute_goal_dynamic(
    goal: AgentGoal,
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]],
    llm_caller: Callable[[list[dict]], str] | None = None,
    max_iterations: int = 3,
    timeout_seconds: int = 120,
) -> list[dict]:
    """动态执行目标：根据中间结果用 LLM 决定下一步。"""
    import time
    start_time = time.monotonic()
    budget = goal.criteria.get("budget", 500)
    min_roi = goal.criteria.get("min_roi", 10)

    # 无 LLM 时降级到静态执行
    if llm_caller is None:
        plan = plan_for_goal(goal)
        return execute_plan(plan, items, order_fetcher)

    all_results: list[dict] = []
    completed_steps: list[dict] = []
    seen_ids: set[str] = set()

    # 第一步：根据 goal_type 选初始扫描器
    first_action = {
        "flip_mod": "scan_mod_flip",
        "build_set": "scan_investment",
        "find_bargain": "scan_investment",
    }.get(goal.goal_type, "scan_mod_flip")

    first_params = {"min_roi_pct": max(min_roi, 100), "limit": 20, "budget": budget}
    if first_action == "scan_investment":
        first_params = {"budget": budget, "min_roi_pct": min_roi, "limit": 20}

    current_action = first_action
    current_params = first_params

    for iteration in range(max_iterations):
        elapsed = time.monotonic() - start_time
        if elapsed > timeout_seconds - 10:  # 留 10s 缓冲
            break

        # 执行当前步骤
        step_results = _execute_single_step(current_action, current_params, items, order_fetcher)
        new_count = 0
        for r in step_results:
            key = r.get("item_id", "")
            if key and key not in seen_ids:
                seen_ids.add(key)
                all_results.append(r)
                new_count += 1

        step_best_roi = max((r.get("roi_pct", 0) for r in step_results), default=0)
        completed_steps.append({
            "action": current_action,
            "count": new_count,
            "best_roi": step_best_roi,
        })

        # 让 LLM 决定下一步
        elapsed = time.monotonic() - start_time
        prompt = _build_next_step_prompt(goal, completed_steps, all_results, budget, elapsed)
        try:
            response = llm_caller([
                {"role": "system", "content": "你是交易策略师。根据当前结果决定下一步。只返回 JSON。"},
                {"role": "user", "content": prompt},
            ])
        except Exception as exc:
            logger.debug("动态规划 LLM 调用失败: %s", exc)
            break

        next_action, next_params, reason = _parse_next_step(response)
        if next_action == "stop":
            break

        current_action = next_action
        current_params = {**next_params, "budget": next_params.get("budget", budget)}

    # 去重排序
    all_results.sort(key=lambda x: x.get("roi_pct", 0), reverse=True)
    return all_results


# ── 目标持久化管理 ──────────────────────────────────────────

class GoalTracker:
    """管理用户目标的创建、持久化、进度追踪和复盘。"""

    def __init__(self, path: Path | None = None):
        self.path = path or GOALS_PATH
        self.goals: list[AgentGoal] = []
        self.outcomes: list[TradeOutcome] = []
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
            for g in data.get("goals", []):
                self.goals.append(AgentGoal(**g))
            for o in data.get("outcomes", []):
                self.outcomes.append(TradeOutcome(**o))
        except Exception as exc:
            logger.debug("加载目标数据失败: %s", exc)

    def _save(self):
        data = {
            "goals": [asdict(g) for g in self.goals],
            "outcomes": [asdict(o) for o in self.outcomes],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_goal(self, goal: AgentGoal) -> AgentGoal:
        self.goals.append(goal)
        self._save()
        return goal

    def remove_goal(self, goal_id: str) -> bool:
        before = len(self.goals)
        self.goals = [g for g in self.goals if g.goal_id != goal_id]
        if len(self.goals) < before:
            self._save()
            return True
        return False

    def get_active_goals(self) -> list[AgentGoal]:
        return [g for g in self.goals if g.status == "active"]

    def get_goal_by_id(self, goal_id: str) -> AgentGoal | None:
        for g in self.goals:
            if g.goal_id == goal_id:
                return g
        return None

    def update_goal_status(self, goal_id: str, status: str) -> bool:
        for i, g in enumerate(self.goals):
            if g.goal_id == goal_id:
                self.goals[i] = AgentGoal(
                    goal_id=g.goal_id, goal_type=g.goal_type,
                    description=g.description, target=g.target,
                    criteria=g.criteria, status=status,
                    created_at=g.created_at, results=g.results,
                )
                self._save()
                return True
        return False

    def record_outcome(self, outcome: TradeOutcome):
        self.outcomes.append(outcome)
        self._save()

    def get_goal_progress(self, goal_id: str) -> GoalProgress | None:
        goal = self.get_goal_by_id(goal_id)
        if not goal:
            return None
        target = goal.criteria.get("target_amount", goal.criteria.get("budget", 500))
        return track_goal_progress(goal_id, target, self.outcomes)

    def format_goals_status(self) -> str:
        """格式化所有目标状态，用于 LLM 上下文或命令输出。"""
        active = self.get_active_goals()
        if not active:
            return "当前没有活跃的交易目标。\n使用 `/goal set 目标描述` 创建目标。"
        lines = ["## 当前交易目标\n"]
        for g in active:
            progress = self.get_goal_progress(g.goal_id)
            progress_text = ""
            if progress:
                progress_text = f" | 进度: {progress.current_amount}/{progress.target_amount}p ({progress.estimated_completion})"
            lines.append(f"- **{g.description}** [{g.goal_id[:6]}]{progress_text}")
            lines.append(f"  类型: {g.goal_type} | 目标: {g.target} | 创建: {g.created_at[:10]}")
        lines.append(f"\n共 {len(active)} 个活跃目标，{len(self.goals) - len(active)} 个已完成/已放弃。")
        return "\n".join(lines)

    def generate_review(self, goal_id: str) -> str:
        """为目标生成复盘报告。"""
        goal = self.get_goal_by_id(goal_id)
        if not goal:
            return "目标不存在。"
        related = [o for o in self.outcomes if o.goal_id == goal_id]
        total_profit = sum(o.actual_profit for o in related)
        wins = sum(1 for o in related if o.actual_profit > 0)
        losses = sum(1 for o in related if o.actual_profit < 0)
        win_rate = wins / len(related) * 100 if related else 0

        lines = [f"## 目标复盘: {goal.description}"]
        lines.append(f"- 状态: {goal.status}")
        lines.append(f"- 交易次数: {len(related)}")
        lines.append(f"- 胜率: {win_rate:.0f}% ({wins}胜/{losses}负)")
        lines.append(f"- 累计利润: {total_profit}p")

        if related:
            best = max(related, key=lambda o: o.actual_profit)
            worst = min(related, key=lambda o: o.actual_profit)
            lines.append(f"- 最佳交易: {best.item_id} +{best.actual_profit}p")
            lines.append(f"- 最差交易: {worst.item_id} {worst.actual_profit}p")

        target = goal.criteria.get("target_amount", goal.criteria.get("budget", 500))
        if total_profit >= target:
            lines.append(f"\n**目标达成！** 累计 {total_profit}p >= 目标 {target}p")
        else:
            lines.append(f"\n**未达成** 累计 {total_profit}p / 目标 {target}p")

        return "\n".join(lines)
