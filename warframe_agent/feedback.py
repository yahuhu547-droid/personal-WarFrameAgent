"""反馈分析器 — 从交易结果中提炼策略信号，注入规则引擎。"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .goals import TradeOutcome

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrategyFeedback:
    strategy: str              # "mod_flip" / "set_build" / "bargain_hunt"
    win_rate: float            # 0.0 ~ 1.0
    avg_profit: float          # 平均利润
    avg_roi: float             # 平均 ROI
    sample_size: int           # 样本数
    confidence: str            # "high" / "medium" / "low"
    recommended: bool          # 是否推荐继续
    last_updated: str


@dataclass(frozen=True)
class ItemFeedback:
    item_id: str
    times_traded: int
    total_profit: float
    avg_profit: float
    win_rate: float
    best_strategy: str
    last_traded: str


def _classify_strategy(outcome: TradeOutcome) -> str:
    """从交易结果推断策略类型。"""
    action = outcome.action.lower()
    if "mod" in action or "flip" in action:
        return "mod_flip"
    if "set" in action or "build" in action:
        return "set_build"
    if "bargain" in action or "invest" in action:
        return "bargain_hunt"
    # 从 goal_id 推断
    gid = outcome.goal_id.lower()
    if "mod" in gid or "flip" in gid:
        return "mod_flip"
    if "set" in gid or "build" in gid:
        return "set_build"
    if "bargain" in gid or "invest" in gid:
        return "bargain_hunt"
    return "unknown"


def _confidence(sample_size: int) -> str:
    if sample_size >= 10:
        return "high"
    if sample_size >= 3:
        return "medium"
    return "low"


class FeedbackAnalyzer:
    """从 TradeOutcome 列表中提取策略和物品维度的反馈。"""

    def analyze_strategies(self, outcomes: list[TradeOutcome]) -> list[StrategyFeedback]:
        """按策略分组，计算胜率、平均利润、平均 ROI。"""
        if not outcomes:
            return []

        groups: dict[str, list[TradeOutcome]] = defaultdict(list)
        for o in outcomes:
            strategy = _classify_strategy(o)
            if strategy != "unknown":
                groups[strategy].append(o)

        results = []
        for strategy, items in groups.items():
            profits = [o.actual_profit for o in items]
            wins = sum(1 for p in profits if p > 0)
            avg_profit = sum(profits) / len(profits) if profits else 0.0
            # ROI: 用 expected_profit 做分母（如果有）
            rois = []
            for o in items:
                if o.expected_profit > 0:
                    rois.append(o.actual_profit / o.expected_profit * 100)
            avg_roi = sum(rois) / len(rois) if rois else 0.0
            win_rate = wins / len(items) if items else 0.0
            sample = len(items)
            recommended = win_rate > 0.5 and avg_profit > 5
            last_ts = max((o.timestamp for o in items), default="")
            results.append(StrategyFeedback(
                strategy=strategy,
                win_rate=round(win_rate, 3),
                avg_profit=round(avg_profit, 1),
                avg_roi=round(avg_roi, 1),
                sample_size=sample,
                confidence=_confidence(sample),
                recommended=recommended,
                last_updated=last_ts,
            ))

        return results

    def analyze_items(self, outcomes: list[TradeOutcome]) -> list[ItemFeedback]:
        """按物品分组，找最佳策略。"""
        if not outcomes:
            return []

        groups: dict[str, list[TradeOutcome]] = defaultdict(list)
        for o in outcomes:
            groups[o.item_id].append(o)

        results = []
        for item_id, items in groups.items():
            profits = [o.actual_profit for o in items]
            wins = sum(1 for p in profits if p > 0)
            total_profit = sum(profits)
            avg_profit = total_profit / len(items) if items else 0.0
            win_rate = wins / len(items) if items else 0.0

            # 找最佳策略
            strategy_profits: dict[str, list[float]] = defaultdict(list)
            for o in items:
                strategy_profits[_classify_strategy(o)].append(o.actual_profit)
            best_strategy = max(
                strategy_profits.items(),
                key=lambda kv: sum(kv[1]) / len(kv[1]) if kv[1] else 0,
                default=("unknown", []),
            )[0]

            last_ts = max((o.timestamp for o in items), default="")
            results.append(ItemFeedback(
                item_id=item_id,
                times_traded=len(items),
                total_profit=total_profit,
                avg_profit=round(avg_profit, 1),
                win_rate=round(win_rate, 3),
                best_strategy=best_strategy,
                last_traded=last_ts,
            ))

        return results

    def get_strategy_ranking(self, outcomes: list[TradeOutcome]) -> list[str]:
        """按推荐度 + 平均利润排序，返回策略名列表。"""
        feedbacks = self.analyze_strategies(outcomes)
        # recommended 排前面，然后按 avg_profit 降序
        feedbacks.sort(key=lambda f: (not f.recommended, -f.avg_profit))
        return [f.strategy for f in feedbacks]

    def get_feedback_for(self, outcomes: list[TradeOutcome], strategy: str) -> StrategyFeedback | None:
        """获取指定策略的反馈。"""
        for fb in self.analyze_strategies(outcomes):
            if fb.strategy == strategy:
                return fb
        return None


# ── 自学习闭环 ──────────────────────────────────────────────

def _build_pattern_extraction_prompt(outcomes: list[TradeOutcome], existing_patterns: list[dict]) -> str:
    """构建模式提取的 LLM prompt。"""
    # 按物品分组统计
    item_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "profit": 0, "wins": 0})
    for o in outcomes:
        s = item_stats[o.item_id]
        s["count"] += 1
        s["profit"] += o.actual_profit
        if o.actual_profit > 0:
            s["wins"] += 1

    top_items = sorted(item_stats.items(), key=lambda x: -x[1]["profit"])[:10]
    items_desc = "\n".join(
        f"- {item_id}: 交易{s['count']}次, 总利润{s['profit']}p, 胜率{s['wins']/s['count']*100:.0f}%"
        for item_id, s in top_items
    )

    existing_desc = "\n".join(
        f"- [{p.get('category', '?')}] {p['description']} (置信度: {p.get('confidence', 0.5)})"
        for p in existing_patterns[:5]
    ) or "暂无"

    return (
        "你是 Warframe 交易数据分析师。从以下交易记录中发现可复用的市场规律。\n\n"
        f"## 交易数据（共 {len(outcomes)} 笔）\n{items_desc}\n\n"
        f"## 已知规律\n{existing_desc}\n\n"
        "请发现 1-3 条新规律，返回 JSON 数组，每条格式:\n"
        '{"category": "mod|set|arcane|general", "description": "规律描述（中文）", "confidence": 0.5~1.0, "evidence_count": N}\n\n'
        "规律类型示例:\n"
        "- 某类 Mod 在周末价格通常上涨\n"
        "- Prime 套装在封存后 2 周内价格会涨\n"
        "- 某个物品的翻转利润稳定在 Xp 以上\n\n"
        "只返回 JSON 数组，不要解释。"
    )


def _parse_extracted_patterns(response: str) -> list[dict]:
    """解析 LLM 返回的模式 JSON。"""
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if not match:
        return []
    try:
        raw = json.loads(match.group())
    except (json.JSONDecodeError, ValueError):
        return []

    patterns = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        desc = p.get("description", "")
        if not desc:
            continue
        category = p.get("category", "general")
        if category not in ("mod", "set", "arcane", "general"):
            category = "general"
        confidence = p.get("confidence", 0.5)
        if not (0.1 <= confidence <= 1.0):
            confidence = 0.5
        patterns.append({
            "category": category,
            "description": desc,
            "confidence": round(confidence, 2),
            "evidence_count": p.get("evidence_count", 1),
            "discovered_at": datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat(),
            "validation_count": 1,
        })
    return patterns[:3]


def discover_patterns(
    outcomes: list[TradeOutcome],
    existing_patterns: list[dict],
    llm_caller: Callable[[list[dict]], str],
) -> list[dict]:
    """用 LLM 从交易数据中发现新规律。"""
    if len(outcomes) < 5:
        return []

    prompt = _build_pattern_extraction_prompt(outcomes, existing_patterns)
    try:
        response = llm_caller([
            {"role": "system", "content": "你是数据分析师。只返回 JSON。"},
            {"role": "user", "content": prompt},
        ])
    except Exception as exc:
        logger.debug("模式提取 LLM 调用失败: %s", exc)
        return []

    new_patterns = _parse_extracted_patterns(response)

    # 去重：与已有模式比较
    existing_descs = {p["description"] for p in existing_patterns}
    unique = [p for p in new_patterns if p["description"] not in existing_descs]

    return unique


def update_pattern_confidence(patterns: list[dict], outcomes: list[TradeOutcome]) -> list[dict]:
    """根据最新交易结果更新模式置信度。

    - 连续成功 → 提升置信度
    - 连续失败 → 降级置信度
    - 置信度 < 0.2 → 标记为待删除
    """
    if not patterns or not outcomes:
        return patterns

    # 最近 10 笔交易的胜率
    recent = outcomes[-10:]
    recent_wins = sum(1 for o in recent if o.actual_profit > 0)
    recent_win_rate = recent_wins / len(recent) if recent else 0.5

    updated = []
    for p in patterns:
        conf = p.get("confidence", 0.5)
        # 胜率高 → 提升
        if recent_win_rate > 0.7:
            conf = min(conf + 0.05, 1.0)
        # 胜率低 → 降级
        elif recent_win_rate < 0.3:
            conf = max(conf - 0.1, 0.1)

        # 置信度过低，标记待删除
        if conf < 0.2:
            continue

        p["confidence"] = round(conf, 2)
        p["last_validated"] = datetime.now().isoformat()
        p["validation_count"] = p.get("validation_count", 0) + 1
        updated.append(p)

    return updated


def run_self_learning_cycle(
    outcomes: list[TradeOutcome],
    existing_patterns: list[dict],
    llm_caller: Callable[[list[dict]], str],
) -> tuple[list[dict], list[dict]]:
    """执行一轮自学习闭环：发现新规律 + 更新已有规律置信度。

    Returns:
        (updated_existing_patterns, new_patterns)
    """
    # 1. 更新已有规律置信度
    updated = update_pattern_confidence(existing_patterns, outcomes)

    # 2. 发现新规律（交易 >= 5 笔才触发）
    new_patterns = []
    if len(outcomes) >= 5:
        new_patterns = discover_patterns(outcomes, updated, llm_caller)

    return updated, new_patterns
