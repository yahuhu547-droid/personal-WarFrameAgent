"""Mod 翻转分析器 — 找出最值得低级买、满级卖的 Mod。"""
from __future__ import annotations

import json
import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

from . import config
from .formatter import market_item_url, summarize_trade_order
from .market import MarketOrder, best_buyers, best_sellers, build_buy_plan, fetch_item_statistics, fetch_orders
from .trade_plan import build_trade_plan, trade_step_from_order
from .names import display_item_name

# 内融升级总消耗 (max_rank, rarity) -> endo
# 来源: Warframe Wiki，R10 无论稀有度都是 20,470 内融
ENDO_COST_TABLE: dict[tuple[int, str], int] = {
    (10, "COMMON"): 20470,
    (10, "UNCOMMON"): 20470,
    (10, "RARE"): 20470,
    (10, "RARE_LEGACY"): 20470,
    (10, "LEGENDARY"): 20470,  # Primed Mod
    (5, "COMMON"): 1280,
    (5, "UNCOMMON"): 1280,
    (5, "RARE"): 1280,
    (5, "RARE_LEGACY"): 1280,
    (5, "LEGENDARY"): 1280,
    (3, "COMMON"): 320,
    (3, "UNCOMMON"): 320,
    (3, "RARE"): 320,
    (2, "COMMON"): 80,
    (2, "UNCOMMON"): 80,
    (2, "RARE"): 80,
}

HIGH_LIQUIDITY_ARCANES = [
    "arcane_energize",
    "arcane_grace",
    "arcane_guardian",
    "arcane_barrier",
    "arcane_avenger",
    "arcane_velocity",
    "arcane_precision",
    "arcane_rage",
]


@dataclass(frozen=True)
class ModFlipResult:
    item_id: str
    display_name: str
    r0_buy_price: int
    r10_sell_price: int
    flip_profit: int
    roi_pct: float
    endo_cost: int
    plat_per_1k_endo: float
    value_score: float
    volume_48h: int | None
    max_rank: int
    rarity: str
    is_prime: bool
    market_url: str = ""
    r0_seller: dict | None = None
    max_rank_buyer: dict | None = None
    required_quantity: int = 1
    trade_plan: dict | None = None


def get_endo_cost(max_rank: int, rarity: str) -> int:
    """获取升级到满级所需的内融总量。"""
    rarity_upper = rarity.upper()
    for key in [(max_rank, rarity_upper), (max_rank, "RARE"), (10, "RARE")]:
        if key in ENDO_COST_TABLE:
            return ENDO_COST_TABLE[key]
    # 默认按 R10 计算
    return 20470


def required_rank0_copies(max_rank: int) -> int:
    return (max_rank + 1) * (max_rank + 2) // 2


def _is_arcane_item(item_id: str) -> bool:
    return str(item_id or "").lower().startswith("arcane_")


def _market_order_from_buy_plan_entry(entry, item_id: str, rank: int) -> MarketOrder:
    return MarketOrder(
        order_type="sell",
        platinum=entry.platinum,
        quantity=entry.quantity,
        user_name=entry.user_name,
        status="ingame",
        reputation=entry.reputation,
        mod_rank=rank,
    )


def _normalized_tags(item: dict) -> set[str]:
    return {str(tag).lower() for tag in item.get("tags", [])}


def _item_url_name(item: dict) -> str:
    return item.get("url_name") or item.get("item_id", "")


def is_tradeable_mod(item: dict) -> bool:
    tags = _normalized_tags(item)
    if "mod" not in tags:
        return False
    if not item.get("tradable", False):
        return False
    max_rank = item.get("modMaxRank") or item.get("fusionLimit", 0)
    return max_rank >= 5 and bool(_item_url_name(item))


def is_tradeable_arcane(item: dict) -> bool:
    tags = _normalized_tags(item)
    url_name = _item_url_name(item).lower()
    name = (item.get("en_name") or item.get("item_name") or url_name).lower()
    if not url_name:
        return False
    if "arcane_helmet" in tags or "arcane_helmet" in url_name or "helmet" in name:
        return False
    if tags.intersection({"skin", "cosmetic", "glyph"}) or any(word in name for word in ("skin", "glyph")):
        return False
    return url_name.startswith("arcane_") or "arcane_enhancement" in tags


def _candidate_priority(candidate: dict) -> tuple[int, str]:
    url_name = candidate["url_name"]
    if url_name in HIGH_LIQUIDITY_ARCANES:
        return (0, url_name)
    if candidate.get("is_prime") or url_name.startswith("galvanized_"):
        return (1, url_name)
    if candidate.get("is_arcane"):
        return (2, url_name)
    return (3, url_name)


def get_tradeable_mods(items: list[dict]) -> list[dict]:
    """从 items_full.json 中筛选可交易的高等级 Mod 与赋能。"""
    mods = []
    for item in items:
        url_name = _item_url_name(item)
        if not url_name:
            continue
        name = item.get("en_name") or item.get("item_name") or url_name
        name_lower = name.lower()
        item_id_lower = url_name.lower()
        is_arcane = is_tradeable_arcane(item)
        if is_arcane:
            max_rank = item.get("modMaxRank") or item.get("fusionLimit") or 5
            rarity = item.get("rarity", "LEGENDARY")
            is_prime = False
        elif is_tradeable_mod(item):
            max_rank = item.get("modMaxRank") or item.get("fusionLimit", 0)
            rarity = item.get("rarity", "RARE")
            is_prime = "primed" in name_lower or "primed" in item_id_lower or "prime" in item_id_lower
        else:
            continue
        mods.append({
            "url_name": url_name,
            "item_name": name,
            "max_rank": max_rank,
            "rarity": rarity,
            "is_prime": is_prime,
            "is_arcane": is_arcane,
        })
    mods.sort(key=_candidate_priority)
    return mods


def analyze_mod_flip(
    item_id: str,
    max_rank: int,
    rarity: str,
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    is_prime: bool = False,
) -> ModFlipResult | None:
    """分析单个 Mod 的翻转利润。"""
    try:
        orders = order_fetcher(item_id)
    except Exception as exc:
        logger.debug("获取 %s 订单失败: %s", item_id, exc)
        return None

    is_arcane = _is_arcane_item(item_id)
    required_quantity = required_rank0_copies(max_rank) if is_arcane else 1

    # R0 价格: Mod 为最低卖价，赋能为聚合买够满级所需 R0 的总成本。
    r0_sellers = best_sellers(orders, limit=1, rank_filter=0)
    if not r0_sellers:
        return None
    buy_steps = []
    if is_arcane:
        buy_plan = build_buy_plan(orders, needed=required_quantity, rank_filter=0)
        if not buy_plan.fulfilled:
            return None
        r0_buy = buy_plan.total_cost
        for entry in buy_plan.entries:
            order = _market_order_from_buy_plan_entry(entry, item_id, 0)
            buy_steps.append(trade_step_from_order(
                side="buy",
                label="买入 R0",
                item_id=item_id,
                order=order,
                quantity=entry.quantity,
                rank=0,
            ))
    else:
        r0_buy = r0_sellers[0].platinum
        buy_steps.append(trade_step_from_order(
            side="buy",
            label="买入 R0",
            item_id=item_id,
            order=r0_sellers[0],
            quantity=1,
            rank=0,
        ))

    # 满级价格: 最高收价 (卖出收入)
    r10_buyers = best_buyers(orders, limit=1, rank_filter=max_rank)
    if not r10_buyers:
        return None
    r10_sell = r10_buyers[0].platinum

    flip_profit = r10_sell - r0_buy
    if flip_profit <= 0:
        return None

    # ROI% = (利润 / 成本) * 100
    roi_pct = (flip_profit / r0_buy * 100) if r0_buy > 0 else 0.0

    endo_cost = get_endo_cost(max_rank, rarity)
    plat_per_1k = (flip_profit / (endo_cost / 1000)) if endo_cost > 0 else 0.0

    # 获取 48h 成交量
    stats = fetch_item_statistics(item_id)
    volume_48h = stats.get("volume_48h") if stats else None

    # Value Score = plat_per_1k_endo * log2(volume + 1)
    value_score = plat_per_1k * math.log2((volume_48h or 0) + 1)

    display = display_item_name(item_id)
    sell_steps = [trade_step_from_order(
        side="sell",
        label=f"出售 R{max_rank}",
        item_id=item_id,
        order=r10_buyers[0],
        quantity=1,
        rank=max_rank,
    )]
    source = "arcane_flip" if is_arcane else "mod_flip"
    strategy = f"arcane_r0_to_r{max_rank}" if is_arcane else f"mod_r0_to_r{max_rank}"
    display_strategy = (
        f"买 {required_quantity} 个 R0 -> 合成 R{max_rank} -> 卖出"
        if is_arcane else f"买 R0 -> 升到 R{max_rank} -> 卖出"
    )
    trade_plan = build_trade_plan(
        source=source,
        strategy=strategy,
        display_strategy=display_strategy,
        item_id=item_id,
        display_name=display,
        required_quantity=required_quantity,
        buy_steps=buy_steps,
        sell_steps=sell_steps,
        total_cost=r0_buy,
        total_revenue=r10_sell,
        profit=flip_profit,
        roi_pct=roi_pct,
        volume_48h=volume_48h,
        risk_level="medium",
    )

    return ModFlipResult(
        item_id=item_id,
        display_name=display,
        r0_buy_price=r0_buy,
        r10_sell_price=r10_sell,
        flip_profit=flip_profit,
        roi_pct=roi_pct,
        endo_cost=endo_cost,
        plat_per_1k_endo=plat_per_1k,
        value_score=value_score,
        volume_48h=volume_48h,
        max_rank=max_rank,
        rarity=rarity,
        is_prime=is_prime,
        market_url=market_item_url(item_id),
        r0_seller=summarize_trade_order(r0_sellers[0], item_id),
        max_rank_buyer=summarize_trade_order(r10_buyers[0], item_id),
        required_quantity=required_quantity,
        trade_plan=trade_plan,
    )


def format_mod_flip_results_for_model(
    results: list[ModFlipResult],
    *,
    min_profit: int,
    limit: int,
    max_items: int = 8,
) -> str:
    safe_max_items = max(0, max_items)
    lines = [f"tool=mod_flipper min_profit={min_profit} limit={limit} result_count={len(results)}"]

    for index, result in enumerate(results[:safe_max_items], start=1):
        volume_48h = "null" if result.volume_48h is None else str(result.volume_48h)
        is_prime = "true" if result.is_prime else "false"
        lines.append(
            " ".join([
                f"row={index}",
                f"item_id={result.item_id}",
                f"display_name={result.display_name}",
                f"rarity={result.rarity}",
                f"max_rank={result.max_rank}",
                f"r0_buy_price={result.r0_buy_price}",
                f"r10_sell_price={result.r10_sell_price}",
                f"flip_profit={result.flip_profit}",
                f"roi_pct={result.roi_pct:.2f}",
                f"endo_cost={result.endo_cost}",
                f"plat_per_1k_endo={result.plat_per_1k_endo:.2f}",
                f"volume_48h={volume_48h}",
                f"is_prime={is_prime}",
            ])
        )

    omitted_count = len(results) - safe_max_items
    if omitted_count > 0:
        lines.append(f"omitted_count={omitted_count}")

    return "\n".join(lines)


def scan_all_mod_flips(
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    min_profit: int = 5,
    min_roi_pct: float = 0,
    limit: int = 20,
    scout_fn: Callable[[list[dict]], list[str]] | None = None,
    opportunity_filter: str = "all",
) -> list[ModFlipResult]:
    """扫描所有可交易 Mod，找出翻转机会，按利润排序。"""
    mods = get_tradeable_mods(items)
    opportunity_filter = (opportunity_filter or "all").lower()
    if opportunity_filter == "mod":
        mods = [m for m in mods if not m.get("is_arcane")]
    elif opportunity_filter == "arcane":
        mods = [m for m in mods if m.get("is_arcane")]
    high_liquidity = [m for m in mods if m["url_name"] in HIGH_LIQUIDITY_ARCANES]
    priority_mods = [m for m in mods if m.get("is_prime") or m["url_name"].startswith("galvanized_")]
    other_arcanes = [m for m in mods if m.get("is_arcane") and m["url_name"] not in HIGH_LIQUIDITY_ARCANES]
    other_mods = [m for m in mods if not m.get("is_arcane") and not m.get("is_prime") and not m["url_name"].startswith("galvanized_")]
    all_candidates = [*high_liquidity[:12], *priority_mods[:16], *other_arcanes[:6], *other_mods[:20]]

    # 智能预筛选：用云端 LLM 选出最可能盈利的候选
    if scout_fn is not None:
        try:
            scouted_ids = scout_fn(all_candidates)
            if scouted_ids:
                id_set = set(scouted_ids)
                candidates = [m for m in all_candidates if m["url_name"] in id_set]
                logger.info("Scout 预筛选: %d → %d 个 Mod", len(all_candidates), len(candidates))
            else:
                candidates = all_candidates
        except Exception as exc:
            logger.debug("Scout 预筛选失败，使用原始列表: %s", exc)
            candidates = all_candidates
    else:
        candidates = all_candidates

    def _analyze(mod: dict) -> ModFlipResult | None:
        try:
            return analyze_mod_flip(
                mod["url_name"], mod["max_rank"], mod["rarity"], order_fetcher,
                is_prime=mod.get("is_prime", False),
            )
        except Exception as exc:
            logger.debug("Mod 翻转分析失败 %s: %s", mod.get("url_name", ""), exc)
            return None

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_analyze, m): m for m in candidates}
        for future in as_completed(futures):
            result = future.result()
            if result and result.flip_profit >= min_profit and result.roi_pct >= min_roi_pct:
                results.append(result)

    results.sort(key=lambda r: (
        0 if r.item_id in HIGH_LIQUIDITY_ARCANES else 1 if r.is_prime or r.item_id.startswith("galvanized_") else 2,
        -r.flip_profit,
    ))
    return results[:limit]
