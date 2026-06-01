from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from .market import best_buyers, best_sellers
from .relics import RelicDrop, RelicInfo, TIER_MAP

OrderFetcher = Callable[[str], Iterable[dict]]


class DucatProvider(Protocol):
    def get_ducat_value(self, item_id: str) -> int | None: ...


@dataclass(frozen=True)
class RelicRewardValue:
    part_name: str
    market_id: str
    rarity: str
    drop_rate: float
    lowest_sell_price: int | None = None
    highest_buy_price: int | None = None
    valuation_price: int | None = None
    valuation_source: str | None = None
    ducat_value: int | None = None
    ducats_per_plat: float | None = None
    expected_platinum: float = 0.0
    expected_ducats: float = 0.0
    recommendation: str = "数据不足"
    data_warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RelicValueReport:
    relic_name: str
    tier: str
    is_vaulted: bool
    reward_values: list[RelicRewardValue]
    expected_platinum: float
    expected_ducats: float
    top_platinum_reward: RelicRewardValue | None = None
    top_ducat_efficiency_reward: RelicRewardValue | None = None
    summary_recommendation: str = "数据不足"


def price_relic_reward(
    drop: RelicDrop,
    order_fetcher: OrderFetcher,
    game_data: DucatProvider,
) -> RelicRewardValue:
    warnings: list[str] = []
    order_list = list(order_fetcher(drop.market_id)) if drop.market_id else []
    sellers = best_sellers(order_list, limit=1)
    buyers = best_buyers(order_list, limit=1)

    lowest_sell = sellers[0].platinum if sellers else None
    highest_buy = buyers[0].platinum if buyers else None
    valuation_price = highest_buy if highest_buy is not None else lowest_sell
    valuation_source = None
    if highest_buy is not None:
        valuation_source = "highest_buy"
    elif lowest_sell is not None:
        valuation_source = "lowest_sell_fallback"
        warnings.append("无在线买家，使用最低卖价估算")
    else:
        warnings.append("缺少市场价格")

    ducat_value = game_data.get_ducat_value(drop.market_id) if drop.market_id else None
    if ducat_value is None:
        warnings.append("未知杜卡德值")

    ducats_per_plat = None
    if ducat_value is not None and lowest_sell and lowest_sell > 0:
        ducats_per_plat = round(ducat_value / lowest_sell, 2)

    expected_platinum = round(drop.drop_rate * valuation_price, 2) if valuation_price is not None else 0.0
    expected_ducats = round(drop.drop_rate * ducat_value, 2) if ducat_value is not None else 0.0
    recommendation = _recommend_reward(valuation_price, ducat_value, ducats_per_plat)

    return RelicRewardValue(
        part_name=drop.part_name,
        market_id=drop.market_id,
        rarity=drop.rarity,
        drop_rate=drop.drop_rate,
        lowest_sell_price=lowest_sell,
        highest_buy_price=highest_buy,
        valuation_price=valuation_price,
        valuation_source=valuation_source,
        ducat_value=ducat_value,
        ducats_per_plat=ducats_per_plat,
        expected_platinum=expected_platinum,
        expected_ducats=expected_ducats,
        recommendation=recommendation,
        data_warnings=warnings,
    )


def analyze_relic_value(
    relic_info: RelicInfo,
    order_fetcher: OrderFetcher,
    game_data: DucatProvider,
) -> RelicValueReport:
    rewards = [price_relic_reward(drop, order_fetcher, game_data) for drop in relic_info.drops]
    expected_platinum = round(sum(reward.expected_platinum for reward in rewards), 2)
    expected_ducats = round(sum(reward.expected_ducats for reward in rewards), 2)
    priced_rewards = [reward for reward in rewards if reward.valuation_price is not None]
    efficiency_rewards = [reward for reward in rewards if reward.ducats_per_plat is not None]
    top_platinum = max(priced_rewards, key=lambda reward: reward.valuation_price or 0) if priced_rewards else None
    top_efficiency = max(efficiency_rewards, key=lambda reward: reward.ducats_per_plat or 0) if efficiency_rewards else None

    return RelicValueReport(
        relic_name=relic_info.name,
        tier=relic_info.tier,
        is_vaulted=relic_info.is_vaulted,
        reward_values=rewards,
        expected_platinum=expected_platinum,
        expected_ducats=expected_ducats,
        top_platinum_reward=top_platinum,
        top_ducat_efficiency_reward=top_efficiency,
        summary_recommendation=_recommend_report(expected_platinum, expected_ducats, top_efficiency),
    )


def format_relic_value_for_display(report: RelicValueReport, target_part: str | None = None) -> str:
    tier_cn = TIER_MAP.get(report.tier, report.tier)
    vaulted = " (已Vault)" if report.is_vaulted else ""
    lines = [
        f"## {report.relic_name} [{tier_cn}]{vaulted}",
        f"期望白金: {report.expected_platinum:.2f}p",
        f"期望杜卡德: {report.expected_ducats:.2f}",
        f"建议: {report.summary_recommendation}",
        "",
        "奖励价值:",
    ]
    normalized_target = (target_part or "").strip().lower()
    if normalized_target:
        matched = [
            reward for reward in report.reward_values
            if normalized_target in reward.part_name.lower() or normalized_target in reward.market_id.lower()
        ]
        if matched:
            reward = matched[0]
            value = f"{reward.valuation_price}p" if reward.valuation_price is not None else "未知"
            lines.insert(5, f"目标部件: {reward.part_name}，掉率 {reward.drop_rate * 100:.2f}%，估值 {value}")
            lines.insert(6, "")
        else:
            lines.insert(5, f"目标部件: 未找到目标部件 {target_part}")
            lines.insert(6, "")
    for reward in report.reward_values:
        price = f"估值 {reward.valuation_price}p" if reward.valuation_price is not None else "估值未知"
        ducat = f"杜卡德 {reward.ducat_value}" if reward.ducat_value is not None else "杜卡德未知"
        efficiency = f"，{reward.ducats_per_plat} 杜卡德/p" if reward.ducats_per_plat is not None else ""
        rate = f"{reward.drop_rate * 100:.1f}%"
        warnings = f" · {'; '.join(reward.data_warnings)}" if reward.data_warnings else ""
        lines.append(
            f"- {reward.part_name} ({reward.rarity}, {rate}): {price}，{ducat}{efficiency}，EV {reward.expected_platinum:.2f}p / {reward.expected_ducats:.2f} 杜卡德 · {reward.recommendation}{warnings}"
        )
    if report.top_platinum_reward:
        lines.append(f"\n最佳白金奖励: {report.top_platinum_reward.part_name} ({report.top_platinum_reward.valuation_price}p)")
    if report.top_ducat_efficiency_reward:
        lines.append(
            f"最佳杜卡德效率: {report.top_ducat_efficiency_reward.part_name} ({report.top_ducat_efficiency_reward.ducats_per_plat} 杜卡德/p)"
        )
    return "\n".join(lines)


def format_relic_value_for_model(report: RelicValueReport) -> str:
    lines = [
        "tool=relic_value",
        f"relic={report.relic_name}",
        f"tier={report.tier}",
        f"vaulted={report.is_vaulted}",
        f"expected_platinum={report.expected_platinum:.2f}",
        f"expected_ducats={report.expected_ducats:.2f}",
        f"summary_recommendation={report.summary_recommendation}",
    ]
    for reward in report.reward_values:
        warnings = ",".join(reward.data_warnings)
        lines.append(
            "reward="
            f"{reward.market_id}|rarity={reward.rarity}|drop_rate={reward.drop_rate:.4f}|"
            f"lowest_sell={_safe_value(reward.lowest_sell_price)}|highest_buy={_safe_value(reward.highest_buy_price)}|"
            f"valuation={_safe_value(reward.valuation_price)}|source={reward.valuation_source or 'none'}|"
            f"ducats={_safe_value(reward.ducat_value)}|ducats_per_plat={_safe_value(reward.ducats_per_plat)}|"
            f"expected_platinum={reward.expected_platinum:.2f}|expected_ducats={reward.expected_ducats:.2f}|"
            f"recommendation={reward.recommendation}|warnings={warnings}"
        )
    return "\n".join(lines)


def _recommend_reward(
    valuation_price: int | None,
    ducat_value: int | None,
    ducats_per_plat: float | None,
) -> str:
    if valuation_price is None and ducat_value is None:
        return "数据不足"
    if ducats_per_plat is not None and ducats_per_plat >= 3:
        return "偏向换杜卡德"
    if valuation_price is not None and valuation_price >= 10:
        return "偏向卖白金"
    if ducat_value is not None:
        return "可换杜卡德"
    return "可卖白金"


def _recommend_report(
    expected_platinum: float,
    expected_ducats: float,
    top_efficiency: RelicRewardValue | None,
) -> str:
    if expected_platinum <= 0 and expected_ducats <= 0:
        return "数据不足，先补价格或杜卡德数据"
    if top_efficiency and (top_efficiency.ducats_per_plat or 0) >= 3:
        return "适合关注杜卡德效率，也可按最高收价保守估算白金收益"
    if expected_platinum >= 5:
        return "白金期望较高，优先看高价奖励是否值得出售"
    return "白金期望一般，更适合按需求开或换杜卡德"


def _safe_value(value: object) -> str:
    return "unknown" if value is None else str(value)
