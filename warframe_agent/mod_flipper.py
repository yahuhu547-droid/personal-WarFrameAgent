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
from .market import best_buyers, best_sellers, fetch_item_statistics, fetch_orders
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
    (3, "COMMON"): 320,
    (3, "UNCOMMON"): 320,
    (3, "RARE"): 320,
    (2, "COMMON"): 80,
    (2, "UNCOMMON"): 80,
    (2, "RARE"): 80,
}


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


def get_endo_cost(max_rank: int, rarity: str) -> int:
    """获取升级到满级所需的内融总量。"""
    rarity_upper = rarity.upper()
    for key in [(max_rank, rarity_upper), (max_rank, "RARE"), (10, "RARE")]:
        if key in ENDO_COST_TABLE:
            return ENDO_COST_TABLE[key]
    # 默认按 R10 计算
    return 20470


def get_tradeable_mods(items: list[dict]) -> list[dict]:
    """从 items_full.json 中筛选可交易的高等级 Mod。"""
    mods = []
    for item in items:
        tags = item.get("tags", [])
        if "mod" not in tags:
            continue
        if not item.get("tradable", False):
            continue
        max_rank = item.get("modMaxRank") or item.get("fusionLimit", 0)
        if max_rank < 5:
            continue
        url_name = item.get("url_name") or item.get("item_id", "")
        if not url_name:
            continue
        # 判断是否为 Prime/Peculiar Mod
        name_lower = (item.get("en_name") or "").lower()
        item_id_lower = url_name.lower()
        is_prime = "primed" in name_lower or "primed" in item_id_lower or "prime" in item_id_lower
        mods.append({
            "url_name": url_name,
            "item_name": item.get("en_name") or item.get("item_name") or url_name,
            "max_rank": max_rank,
            "rarity": item.get("rarity", "RARE"),
            "is_prime": is_prime,
        })
    # Prime Mod 排在前面
    mods.sort(key=lambda m: (not m["is_prime"], m["url_name"]))
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

    # R0 价格: 最低卖价 (买入成本)
    r0_sellers = best_sellers(orders, limit=1, rank_filter=0)
    if not r0_sellers:
        return None
    r0_buy = r0_sellers[0].platinum

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

    return ModFlipResult(
        item_id=item_id,
        display_name=display_item_name(item_id),
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
    )


def scan_all_mod_flips(
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    min_profit: int = 5,
    min_roi_pct: float = 0,
    limit: int = 20,
    scout_fn: Callable[[list[dict]], list[str]] | None = None,
) -> list[ModFlipResult]:
    """扫描所有可交易 Mod，找出翻转机会，按利润排序。"""
    mods = get_tradeable_mods(items)
    all_candidates = [m for m in mods[:40] if m["url_name"]]

    # 智能预筛选：用云端 LLM 选出最可能盈利的候选
    if scout_fn is not None:
        try:
            scouted_ids = scout_fn(mods[:40])
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

    # Prime Mod 优先，然后按利润排序
    results.sort(key=lambda r: (not r.is_prime, -r.flip_profit))
    return results[:limit]
