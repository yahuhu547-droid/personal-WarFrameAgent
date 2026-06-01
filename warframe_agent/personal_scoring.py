from __future__ import annotations

from dataclasses import dataclass, field

from .personal_profile import PersonalTradingProfile


@dataclass(frozen=True)
class PersonalFitScore:
    personal_score: float
    reasons: list[str] = field(default_factory=list)
    category: str = "unknown"


def score_personal_fit(
    *,
    item_id: str,
    source: str,
    strategy: str,
    total_cost: int | float,
    profit: int | float,
    roi_pct: int | float,
    risk_level: str,
    profile: PersonalTradingProfile,
) -> PersonalFitScore:
    score = 50.0
    reasons: list[str] = []
    category = infer_opportunity_category(item_id=item_id, source=source, strategy=strategy)

    if profile.budget_max > 0:
        if total_cost > profile.budget_max:
            score -= 30.0
            reasons.append("超出预算")
        elif total_cost >= profile.budget_min:
            score += 18.0
            reasons.append("预算匹配")
    elif total_cost >= 0:
        score += 5.0

    preferred = set(profile.preferred_categories or profile.derived_categories)
    if preferred and category in preferred:
        score += 18.0
        reasons.append("偏好品类匹配")
    elif preferred:
        score -= 8.0

    if roi_pct >= profile.min_roi_pct:
        score += 14.0
        reasons.append("ROI 达标")
    else:
        score -= 16.0
        reasons.append("ROI 未达偏好")

    risk = (risk_level or "medium").lower()
    if _risk_matches(profile.risk_appetite, risk):
        score += 10.0
        reasons.append("风险匹配")
    elif profile.risk_appetite == "low" and risk == "high":
        score -= 22.0
        reasons.append("风险偏高")
    elif profile.risk_appetite == "high" and risk == "low":
        score -= 4.0

    if profit > 0:
        score += min(float(profit) / 10.0, 10.0)
    else:
        score -= 20.0

    feedback = _matching_feedback(profile, source, strategy, category)
    if feedback and feedback.count >= 3:
        if feedback.good_rate >= 0.67 and feedback.avg_actual_profit > 0:
            score += min(10.0, 4.0 + feedback.avg_actual_profit / 20.0)
            reasons.append("历史策略表现好")
        elif feedback.good_rate <= 0.34 or feedback.avg_actual_profit < 0:
            score -= min(12.0, 5.0 + abs(feedback.avg_actual_profit) / 15.0)
            reasons.append("历史策略需谨慎")

    return PersonalFitScore(
        personal_score=round(max(0.0, min(100.0, score)), 1),
        reasons=reasons[:6],
        category=category,
    )


def infer_opportunity_category(*, item_id: str, source: str, strategy: str) -> str:
    text = " ".join([item_id or "", source or "", strategy or ""]).lower()
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


def _risk_matches(appetite: str, risk: str) -> bool:
    if appetite == "high":
        return risk in {"medium", "high"}
    if appetite == "low":
        return risk == "low"
    return risk in {"low", "medium"}


def _matching_feedback(profile: PersonalTradingProfile, source: str, strategy: str, category: str):
    for signal in profile.outcome_feedback:
        if signal.source == source and signal.strategy == strategy and signal.category == category:
            return signal
    for signal in profile.outcome_feedback:
        if signal.source == source and signal.category == category:
            return signal
    for signal in profile.outcome_feedback:
        if signal.category == category:
            return signal
    return None
