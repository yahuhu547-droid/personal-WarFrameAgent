"""交易策略模板 — 预设策略扫描，按风险等级分类。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from . import config
from .market import best_buyers, best_sellers, fetch_item_statistics, fetch_orders
from .mod_flipper import ModFlipResult, analyze_mod_flip
from .set_profit import SetProfitResult, analyze_set_profit
from .warframes import _load_items, build_prime_groups

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Strategy:
    """交易策略定义。"""
    name: str
    risk_level: str  # "低风险" / "中风险" / "高风险"
    description: str
    category: str    # "mod_flip" / "set_profit" / "vault_speculation"


@dataclass(frozen=True)
class StrategyResult:
    """策略扫描结果。"""
    strategy: Strategy
    opportunities: list[dict]  # 具体机会列表
    total_scanned: int
    summary: str


# ── 预设策略 ──────────────────────────────────────────────────────────────────

STRATEGIES: list[Strategy] = [
    Strategy(
        name="低风险赋能翻转",
        risk_level="低风险",
        description="高流动性赋能 Mod（R0 买 R5 卖），市场需求稳定，价差可预测",
        category="mod_flip",
    ),
    Strategy(
        name="中风险 Prime 拆件",
        risk_level="中风险",
        description="热门 Prime 套装拆件买卖，利润较高但需要等待买家",
        category="set_profit",
    ),
    Strategy(
        name="高风险 Vault 投机",
        risk_level="高风险",
        description="即将 Vault 的 Prime 套装囤货，长期持有等待升值",
        category="vault_speculation",
    ),
]


def get_strategy(name: str) -> Strategy | None:
    """按名称查找策略（支持模糊匹配）。"""
    name_lower = name.lower()
    for s in STRATEGIES:
        if name_lower in s.name.lower() or name_lower in s.risk_level.lower():
            return s
    return None


def list_strategies() -> list[Strategy]:
    """返回所有可用策略。"""
    return list(STRATEGIES)


# ── 策略扫描 ──────────────────────────────────────────────────────────────────

# 高流动性赋能列表（低风险策略目标）
HIGH_LIQUIDITY_ARCANES = [
    "arcane_energize",       # 充沛赋能
    "arcane_grace",          # 恩赐赋能
    "arcane_guardian",       # 守护赋能
    "arcane_barrier",        # 屏障赋能
    "arcane_avenger",        # 复仇者赋能
    "arcane_velocity",       # 速度赋能
    "arcane_precision",      # 精准赋能
    "arcane_rage",           # 狂怒赋能
]


def _scan_mod_flip_strategy(
    order_fetcher: Callable[[str], list[dict]],
    min_profit: int = 5,
) -> list[dict]:
    """低风险赋能翻转扫描。"""
    results = []
    items = _load_items()
    mods_by_id = {m["url_name"]: m for m in items if m.get("url_name")}
    for arcane_id in HIGH_LIQUIDITY_ARCANES:
        mod = mods_by_id.get(arcane_id)
        if not mod:
            continue
        try:
            max_rank = mod.get("modMaxRank", mod.get("fusionLimit", 5))
            rarity = mod.get("rarity", "RARE")
            flip = analyze_mod_flip(arcane_id, max_rank, rarity, order_fetcher)
            if flip and flip.flip_profit >= min_profit:
                results.append({
                    "item_id": arcane_id,
                    "item_name": flip.display_name,
                    "buy_price": flip.r0_buy,
                    "sell_price": flip.r5_sell,
                    "profit": flip.flip_profit,
                    "roi_pct": flip.roi_pct,
                    "volume_48h": flip.volume_48h,
                })
        except Exception as exc:
            logger.debug("赋能翻转扫描失败 %s: %s", arcane_id, exc)
    results.sort(key=lambda r: r["profit"], reverse=True)
    return results


def _scan_set_profit_strategy(
    order_fetcher: Callable[[str], list[dict]],
    min_profit: int = 5,
) -> list[dict]:
    """中风险 Prime 拆件扫描。"""
    items = _load_items()
    groups = build_prime_groups(items)
    candidates = list(groups.values())[:20]
    results = []
    for group in candidates:
        try:
            result = analyze_set_profit(group, order_fetcher)
            if result and result.best_profit >= min_profit:
                results.append({
                    "item_id": result.base_id,
                    "item_name": result.display_name,
                    "strategy": result.best_strategy,
                    "profit": result.best_profit,
                    "set_buy": result.set_buy_price,
                    "parts_sell": result.parts_sell_total,
                    "volume_48h": result.volume_48h,
                })
        except Exception as exc:
            logger.debug("套装利润扫描失败 %s: %s", group.base_id, exc)
    results.sort(key=lambda r: r["profit"], reverse=True)
    return results[:10]


def _scan_vault_speculation() -> list[dict]:
    """高风险 Vault 投机扫描 — 列出即将 Vault 的套装。

    当前实现：从已知的 Vault 周期信息中推断。
    后续可接入 events.py 的 PrimeVaultAvailabilities 数据。
    """
    # 通用 Vault 投机建议（基于经验规律）
    suggestions = [
        {
            "item_id": "current_prime_access",
            "item_name": "当前 Prime Access 套装",
            "advice": "新 Prime Access 上线后 2-3 个月是最佳囤货窗口，价格通常在 Vault 后 6 个月翻倍",
            "risk": "高 — 资金占用周期长",
        },
        {
            "item_id": "oldest_unvaulted",
            "item_name": "最老的未 Vault Prime 套装",
            "advice": "关注发布超过 18 个月的 Prime 套装，Vault 公告前 1-2 周是最后买入窗口",
            "risk": "中 — Vault 时间不可预测",
        },
    ]
    return suggestions


def run_strategy(
    strategy: Strategy,
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    min_profit: int = 5,
) -> StrategyResult:
    """执行指定策略的扫描。"""
    if strategy.category == "mod_flip":
        opportunities = _scan_mod_flip_strategy(order_fetcher, min_profit)
        summary = f"找到 {len(opportunities)} 个赋能翻转机会"
    elif strategy.category == "set_profit":
        opportunities = _scan_set_profit_strategy(order_fetcher, min_profit)
        summary = f"找到 {len(opportunities)} 个套装拆件机会"
    elif strategy.category == "vault_speculation":
        opportunities = _scan_vault_speculation()
        summary = f"Vault 投机建议 {len(opportunities)} 条"
    else:
        opportunities = []
        summary = "未知策略类型"

    return StrategyResult(
        strategy=strategy,
        opportunities=opportunities,
        total_scanned=len(opportunities),
        summary=summary,
    )


def format_strategy_result(result: StrategyResult) -> str:
    """格式化策略扫描结果为用户可读文本。"""
    lines = [f"**{result.strategy.name}** ({result.strategy.risk_level})"]
    lines.append(result.strategy.description)
    lines.append(f"扫描结果: {result.summary}")
    lines.append("")

    if not result.opportunities:
        lines.append("暂无符合条件的机会。")
        return "\n".join(lines)

    for i, opp in enumerate(result.opportunities, 1):
        if result.strategy.category == "mod_flip":
            lines.append(
                f"{i}. {opp['item_name']} — "
                f"买入 {opp['buy_price']}p → 卖出 {opp['sell_price']}p，"
                f"利润 +{opp['profit']}p (ROI {opp['roi_pct']:.0f}%)"
            )
        elif result.strategy.category == "set_profit":
            lines.append(
                f"{i}. {opp['item_name']} — "
                f"{opp['strategy']}，利润 +{opp['profit']}p"
            )
        elif result.strategy.category == "vault_speculation":
            lines.append(f"{i}. {opp['item_name']}: {opp['advice']}")
            lines.append(f"   风险: {opp['risk']}")

    return "\n".join(lines)
