from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import re
from typing import Any, Iterable

from .memory import PROFILE_CATEGORIES, AgentMemory


_CATEGORY_LABELS = {
    "mod": "MOD",
    "arcane": "赋能",
    "prime_set": "Prime 套装",
    "prime_part": "Prime 部件",
    "riven": "紫卡",
    "baro": "Baro",
}
_KNOWN_OUTCOME_SOURCES = {"mod_flipper", "mod_flip", "set_profit", "investment"}
_SAFE_FEEDBACK_IDENTIFIER_RE = re.compile(r"[^a-z0-9_]+")
_SENSITIVE_FEEDBACK_TEXT_RE = re.compile(
    r"(?i)(/w\b|warframe\.market/profile|profile_url|token|secret|api[_-]?key|authorization|cookie|bearer\s+\S+|raw_orders)"
)
_TERMINAL_SQLITE_OUTCOME_STATUSES = {"completed", "skipped", "failed", "expired", "accepted", "rejected"}
_GOOD_FEEDBACK_VALUES = {"good", "accepted"}
_BAD_FEEDBACK_VALUES = {"bad", "rejected"}


@dataclass(frozen=True)
class OutcomeFeedbackSignal:
    key: str
    source: str
    strategy: str
    category: str
    count: int
    win_count: int
    loss_count: int
    avg_actual_profit: float
    good_rate: float


@dataclass(frozen=True)
class PersonalTradingProfile:
    risk_appetite: str
    budget_min: int
    budget_max: int
    budget_label: str
    preferred_categories: list[str] = field(default_factory=list)
    derived_categories: list[str] = field(default_factory=list)
    max_turnaround_days: int = 7
    min_roi_pct: int = 0
    completed_outcome_count: int = 0
    total_actual_profit: int = 0
    win_rate: float = 0.0
    outcome_feedback: list[OutcomeFeedbackSignal] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)


def build_personal_profile(
    memory: AgentMemory,
    *,
    opportunity_outcomes: Iterable[Any] | None = None,
) -> PersonalTradingProfile:
    prefs = memory.preferences
    outcomes = _combined_outcomes(memory, opportunity_outcomes)
    wins = sum(1 for outcome in outcomes if _outcome_actual_profit(outcome) > 0)
    total_profit = sum(_outcome_actual_profit(outcome) for outcome in outcomes)
    derived_categories = _derive_categories(memory, outcomes)
    outcome_feedback = _derive_outcome_feedback(outcomes)
    budget_label = _format_budget(prefs.budget_min, prefs.budget_max)
    summary_lines = [
        f"风险偏好={prefs.risk_appetite}",
        f"预算={budget_label}",
        f"最低ROI={prefs.min_roi_pct}%",
        f"最长周转={prefs.max_turnaround_days}天",
    ]
    if prefs.preferred_categories:
        summary_lines.append("显式偏好=" + "、".join(_category_label(c) for c in prefs.preferred_categories))
    if derived_categories:
        summary_lines.append("行为偏好=" + "、".join(_category_label(c) for c in derived_categories[:3]))
    if outcomes:
        summary_lines.append(f"历史结果={wins}/{len(outcomes)}盈利，累计{total_profit}p")
    return PersonalTradingProfile(
        risk_appetite=prefs.risk_appetite,
        budget_min=prefs.budget_min,
        budget_max=prefs.budget_max,
        budget_label=budget_label,
        preferred_categories=list(prefs.preferred_categories),
        derived_categories=derived_categories,
        max_turnaround_days=prefs.max_turnaround_days,
        min_roi_pct=prefs.min_roi_pct,
        completed_outcome_count=len(outcomes),
        total_actual_profit=total_profit,
        win_rate=round(wins / len(outcomes), 3) if outcomes else 0.0,
        outcome_feedback=outcome_feedback,
        summary_lines=summary_lines,
    )


def format_personal_profile(profile: PersonalTradingProfile) -> str:
    category_text = "、".join(_category_label(c) for c in profile.preferred_categories) or "未设置"
    derived_text = "、".join(_category_label(c) for c in profile.derived_categories[:5]) or "暂无"
    lines = [
        "个人交易画像",
        f"- 风险偏好: {profile.risk_appetite}",
        f"- 预算区间: {profile.budget_label}",
        f"- 偏好品类: {category_text}",
        f"- 行为推断: {derived_text}",
        f"- 最低 ROI: {profile.min_roi_pct}%",
        f"- 可接受周转: {profile.max_turnaround_days} 天内",
        f"- 历史复盘: {profile.completed_outcome_count} 条，胜率 {profile.win_rate:.0%}，累计 {profile.total_actual_profit}p",
    ]
    return "\n".join(lines)


def profile_safe_summary(profile: PersonalTradingProfile) -> dict:
    return {
        "risk_appetite": profile.risk_appetite,
        "budget_min": profile.budget_min,
        "budget_max": profile.budget_max,
        "preferred_categories": list(profile.preferred_categories),
        "derived_categories": list(profile.derived_categories[:5]),
        "max_turnaround_days": profile.max_turnaround_days,
        "min_roi_pct": profile.min_roi_pct,
        "completed_outcome_count": profile.completed_outcome_count,
        "total_actual_profit": profile.total_actual_profit,
        "win_rate": profile.win_rate,
        "outcome_feedback": [
            {
                "source": signal.source,
                "strategy": signal.strategy,
                "category": signal.category,
                "count": signal.count,
                "win_count": signal.win_count,
                "loss_count": signal.loss_count,
                "avg_actual_profit": signal.avg_actual_profit,
                "good_rate": signal.good_rate,
            }
            for signal in profile.outcome_feedback[:10]
        ],
    }


def _combined_outcomes(memory: AgentMemory, opportunity_outcomes: Iterable[Any] | None) -> list[Any]:
    outcomes: list[Any] = [outcome for outcome in memory.trade_outcomes if _is_profile_outcome(outcome)]
    if opportunity_outcomes is not None:
        outcomes.extend(outcome for outcome in opportunity_outcomes if _is_profile_outcome(outcome))
    return outcomes


def _derive_categories(memory: AgentMemory, outcomes: Iterable[Any] | None = None) -> list[str]:
    counter: Counter[str] = Counter()
    for category in memory.preferences.preferred_categories:
        counter[category] += 3
    if memory.user_profile:
        for category in memory.user_profile.favorite_categories:
            if category in PROFILE_CATEGORIES:
                counter[category] += 2
    for question in memory.common_questions:
        text = question.lower()
        if "赋能" in text or "arcane" in text:
            counter["arcane"] += 1
        if "prime" in text or "一套" in text:
            counter["prime_set"] += 1
        if "mod" in text or "卡片" in text:
            counter["mod"] += 1
        if "紫卡" in text or "riven" in text:
            counter["riven"] += 1
    for outcome in outcomes if outcomes is not None else memory.trade_outcomes:
        item_id = _safe_feedback_identifier(_outcome_item_id(outcome))
        if "arcane" in item_id:
            counter["arcane"] += 2
        elif "prime" in item_id or item_id.endswith("_set"):
            counter["prime_set"] += 2
    return [category for category, _ in counter.most_common() if category in PROFILE_CATEGORIES]


def _derive_outcome_feedback(outcomes: Iterable[Any]) -> list[OutcomeFeedbackSignal]:
    buckets: dict[tuple[str, str, str], dict[str, int]] = {}
    for outcome in outcomes:
        source = _infer_outcome_source(outcome)
        strategy = _infer_outcome_strategy(outcome, source)
        category = _infer_outcome_category(_outcome_item_id(outcome), source, strategy)
        key = (source, strategy, category)
        bucket = buckets.setdefault(key, {"count": 0, "wins": 0, "losses": 0, "profit": 0})
        actual_profit = _outcome_actual_profit(outcome)
        feedback = _safe_feedback_identifier(_outcome_feedback(outcome))
        status = _safe_feedback_identifier(_outcome_status(outcome))
        bucket["count"] += 1
        bucket["profit"] += actual_profit
        if actual_profit > 0 and feedback not in _BAD_FEEDBACK_VALUES:
            bucket["wins"] += 1
        if actual_profit < 0 or feedback in _BAD_FEEDBACK_VALUES or status in {"failed", "rejected"}:
            bucket["losses"] += 1

    signals: list[OutcomeFeedbackSignal] = []
    for (source, strategy, category), bucket in buckets.items():
        count = bucket["count"]
        if count <= 0:
            continue
        avg_profit = round(bucket["profit"] / count, 1)
        signals.append(
            OutcomeFeedbackSignal(
                key=f"{source}:{strategy}:{category}",
                source=source,
                strategy=strategy,
                category=category,
                count=count,
                win_count=bucket["wins"],
                loss_count=bucket["losses"],
                avg_actual_profit=avg_profit,
                good_rate=round(bucket["wins"] / count, 3),
            )
        )
    return sorted(signals, key=lambda signal: (signal.count, abs(signal.avg_actual_profit)), reverse=True)[:12]


def _infer_outcome_source(outcome) -> str:
    action = _safe_feedback_identifier(getattr(outcome, "source", "") or getattr(outcome, "action", ""))
    if action in _KNOWN_OUTCOME_SOURCES:
        return "mod_flipper" if action == "mod_flip" else action
    item_id = _safe_feedback_identifier(_outcome_item_id(outcome))
    if "arcane" in item_id or "mod" in item_id:
        return "mod_flipper"
    if "prime" in item_id or item_id.endswith("_set"):
        return "set_profit"
    return "unknown"


def _infer_outcome_strategy(outcome, source: str) -> str:
    strategy = _safe_feedback_identifier(getattr(outcome, "strategy", ""))
    if strategy and source != "unknown":
        return strategy
    if source == "mod_flipper":
        if "arcane" in _safe_feedback_identifier(_outcome_item_id(outcome)):
            return "arcane_rank0_to_max"
        return "mod_rank0_to_max"
    if source == "set_profit":
        return "buy_parts_sell_set"
    if source == "investment":
        return "prime_set_investment"
    return source if source in _KNOWN_OUTCOME_SOURCES else "unknown"


def _infer_outcome_category(item_id: str, source: str, strategy: str) -> str:
    text = " ".join([_safe_feedback_text(item_id), source or "", strategy or ""]).lower()
    if "arcane" in text or "赋能" in text:
        return "arcane"
    if "mod" in text:
        return "mod"
    if "riven" in text or "紫卡" in text:
        return "riven"
    if "baro" in text:
        return "baro"
    if "set" in text or "prime" in text:
        return "prime_set"
    return "unknown"


def _safe_feedback_identifier(value: str) -> str:
    if _SENSITIVE_FEEDBACK_TEXT_RE.search(str(value or "")):
        return ""
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    text = _SAFE_FEEDBACK_IDENTIFIER_RE.sub("", text)
    return re.sub(r"_+", "_", text).strip("_")[:80]


def _safe_feedback_text(value: str) -> str:
    text = str(value or "").strip()
    if _SENSITIVE_FEEDBACK_TEXT_RE.search(text):
        return ""
    return text[:120]


def _is_profile_outcome(outcome: Any) -> bool:
    status = _safe_feedback_identifier(_outcome_status(outcome))
    return not status or status in _TERMINAL_SQLITE_OUTCOME_STATUSES


def _outcome_item_id(outcome: Any) -> str:
    return str(getattr(outcome, "item_id", "") or getattr(outcome, "item_name", "") or "")


def _outcome_actual_profit(outcome: Any) -> int:
    try:
        return int(getattr(outcome, "actual_profit", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _outcome_feedback(outcome: Any) -> str:
    return str(getattr(outcome, "user_feedback", "") or "")


def _outcome_status(outcome: Any) -> str:
    return str(getattr(outcome, "status", "") or "")


def _format_budget(budget_min: int, budget_max: int) -> str:
    if budget_min and budget_max:
        return f"{budget_min}-{budget_max}p"
    if budget_max:
        return f"0-{budget_max}p"
    if budget_min:
        return f"{budget_min}p+"
    return "未设置"


def _category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, category)
