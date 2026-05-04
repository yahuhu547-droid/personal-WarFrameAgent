"""Mod 翻转分析器 — 找出最值得低级买、满级卖的 Mod。"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import config
from .market import best_buyers, best_sellers, fetch_orders
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
    endo_cost: int
    plat_per_1k_endo: float
    value_score: float
    volume_48h: int | None
    max_rank: int
    rarity: str


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
        mods.append({
            "url_name": item.get("url_name", ""),
            "item_name": item.get("item_name", ""),
            "max_rank": max_rank,
            "rarity": item.get("rarity", "RARE"),
        })
    return mods


def fetch_item_statistics(item_id: str) -> dict | None:
    """获取物品的 48 小时成交量（使用 warframe.market v1 statistics）。"""
    import requests
    url = f"https://api.warframe.market/v1/items/{item_id}/statistics"
    try:
        resp = requests.get(url, headers={
            "Platform": "pc",
            "Language": "en",
        }, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            stats = data.get("payload", {}).get("statistics_closed", [])
            # 累加最近 48 小时的成交量
            volume = 0
            for stat in stats[-4:]:  # 最近 4 个 12 小时窗口
                volume += stat.get("volume", 0)
            return {"volume_48h": volume}
    except Exception:
        pass
    return None


def analyze_mod_flip(
    item_id: str,
    max_rank: int,
    rarity: str,
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
) -> ModFlipResult | None:
    """分析单个 Mod 的翻转利润。"""
    try:
        orders = order_fetcher(item_id)
    except Exception:
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
        endo_cost=endo_cost,
        plat_per_1k_endo=plat_per_1k,
        value_score=value_score,
        volume_48h=volume_48h,
        max_rank=max_rank,
        rarity=rarity,
    )


def scan_all_mod_flips(
    items: list[dict],
    order_fetcher: Callable[[str], list[dict]] = fetch_orders,
    min_profit: int = 5,
    limit: int = 20,
) -> list[ModFlipResult]:
    """扫描所有可交易 Mod，找出翻转机会，按每千内融利润排序。"""
    mods = get_tradeable_mods(items)
    results = []
    for mod in mods[:100]:  # 限制扫描数量避免 API 限流
        url_name = mod["url_name"]
        if not url_name:
            continue
        try:
            result = analyze_mod_flip(
                url_name, mod["max_rank"], mod["rarity"], order_fetcher
            )
            if result and result.flip_profit >= min_profit:
                results.append(result)
        except Exception:
            continue

    results.sort(key=lambda r: r.value_score, reverse=True)
    return results[:limit]
