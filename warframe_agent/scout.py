"""多模型智能预筛选 — 用云端 LLM 从大量候选中筛选最值得关注的物品。

核心思路：云端模型基于训练知识和缓存数据判断哪些物品最可能盈利，
本地代码只对筛选后的少量候选发起真实 API 请求，大幅减少 warframe.market 调用量。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable

from . import config
from .llm import _cloud_chat_sync

logger = logging.getLogger(__name__)

# 预筛选结果缓存: key -> (timestamp, item_ids)
_scout_cache: dict[str, tuple[float, list[str]]] = {}

# 各扫描类型的 prompt 模板
_PROMPT_MOD_FLIPPER = """你是 Warframe Mod 交易专家。以下 Mod 列表中，哪些最可能通过"低级买(R0)高级卖(R10/R5)"盈利？

重点考虑：
- Meta Mod（如充沛/复仇者/川流不息/过度延展等常用 Mod）
- 价差空间大的 Mod
- 48h 成交量高的 Mod（流动性好，容易出手）
- Primed Mod 通常利润更高

候选 Mod 列表（共 {total} 个）：
{summary}

返回 JSON 数组，包含最多 {limit} 个 url_name，按预期盈利从高到低排序。
只返回 JSON 数组，不要其他文字。示例：["arcane_energize", "primed_flow"]"""

_PROMPT_SET_PROFIT = """你是 Warframe Prime 套装交易专家。以下 Prime 套装中，哪些最可能通过"买部件→卖套装"或"买套装→卖部件"盈利？

重点考虑：
- 热门战甲/武器的套装（需求量大）
- 套装 vs 拆件价差大的
- 48h 成交量高的（流动性好）
- 刚回归 Vault 的套装（价格波动期机会多）

候选套装列表（共 {total} 个）：
{summary}

返回 JSON 数组，包含最多 {limit} 个 base_id，按预期盈利从高到低排序。
只返回 JSON 数组，不要其他文字。示例：["rhino_prime", "volt_prime"]"""

_PROMPT_INVESTMENT = """你是 Warframe 投资顾问。以下 Prime 套装中，哪些最值得投资（预算 {budget}p）？

重点考虑：
- ROI 高的套装
- 即将 Vault 的套装（囤货等涨价）
- 刚 Vault 回归的套装（价格低谷期买入）
- 风险等级：优先 low/medium，避免 high

当前事件信息：
{event_info}

候选套装列表（共 {total} 个）：
{summary}

返回 JSON 数组，包含最多 {limit} 个 base_id，按投资价值从高到低排序。
只返回 JSON 数组，不要其他文字。示例：["rhino_prime", "nova_prime"]"""


def _call_cloud(prompt: str, model: str) -> str | None:
    """调用指定云端模型，返回文本响应。"""
    try:
        messages = [{"role": "user", "content": prompt}]
        return _cloud_chat_sync(messages, model=model)
    except Exception as exc:
        logger.warning("Scout 云端调用失败 (%s): %s", model, exc)
        return None


def _parse_json_list(text: str) -> list[str]:
    """从 LLM 响应中容错解析 JSON 数组。"""
    if not text:
        return []
    # 尝试直接解析
    text = text.strip()
    # 提取 JSON 数组部分
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        logger.debug("Scout 响应中未找到 JSON 数组: %s", text[:200])
        return []
    try:
        result = json.loads(text[start:end + 1])
        if isinstance(result, list):
            return [str(item) for item in result if item]
    except json.JSONDecodeError as exc:
        logger.debug("Scout JSON 解析失败: %s", exc)
    return []


def _get_cached(key: str) -> list[str] | None:
    """检查预筛选缓存。"""
    if key in _scout_cache:
        ts, ids = _scout_cache[key]
        if time.time() - ts < config.SCOUT_CACHE_TTL:
            return ids
        del _scout_cache[key]
    return None


def _set_cache(key: str, ids: list[str]):
    """写入预筛选缓存。"""
    _scout_cache[key] = (time.time(), ids)


def _build_mod_summary(
    mods: list[dict],
    cached_stats: dict[str, dict] | None = None,
    price_trends: dict[str, dict] | None = None,
) -> str:
    """构建 Mod 摘要文本（名称+缓存数据+历史趋势）。"""
    lines = []
    for mod in mods:
        name = mod.get("url_name", "")
        rank = mod.get("max_rank", 0)
        rarity = mod.get("rarity", "")
        is_prime = mod.get("is_prime", False)
        vol = ""
        if cached_stats and name in cached_stats:
            vol = f", 48h成交量={cached_stats[name].get('volume_48h', '?')}"
        trend = ""
        if price_trends and name in price_trends:
            t = price_trends[name]
            direction = t.get("direction", "stable")
            change = t.get("change_pct", 0)
            trend = f", 趋势={direction}({change:+.1f}%)"
        prime_tag = " [Prime]" if is_prime else ""
        lines.append(f"- {name} (R{rank}, {rarity}{prime_tag}{vol}{trend})")
    return "\n".join(lines)


def _build_set_summary(groups: list) -> str:
    """构建套装摘要文本。"""
    lines = []
    for g in groups:
        name = g.en_title or g.base_id
        part_count = len([k for k in g.items if k != "set"])
        tags = ", ".join(g.tags) if g.tags else ""
        lines.append(f"- {g.base_id} ({name}, {part_count}部件, {tags})")
    return "\n".join(lines)


def get_event_context() -> str:
    """从 EventTracker 获取当前事件摘要，注入 scout prompt。"""
    try:
        from .events import EventTracker
        tracker = EventTracker()
        tracker.load_cache()
        events = tracker.get_active_events()
        if not events:
            return ""
        lines = []
        for e in events[:5]:
            if e.event_type == "baro_visit":
                lines.append(f"- Baro 虚空商人来访中（{e.description}），Primed Mod 价格可能波动")
            elif e.event_type == "prime_vault":
                lines.append(f"- {e.description}，相关套装价格可能上涨")
            elif e.event_type == "prime_access":
                lines.append(f"- {e.description}，新 Prime 上线，旧套装价格可能波动")
            else:
                lines.append(f"- {e.description}")
        return "\n".join(lines)
    except Exception:
        return ""


def get_user_preferences() -> str:
    """从 agent_memory 读取用户偏好，注入 scout prompt。"""
    try:
        from .memory import AgentMemory
        memory = AgentMemory.load()
        prefs = []
        if memory.trade_style:
            prefs.append(f"交易风格: {memory.trade_style}")
        if memory.budget_range:
            prefs.append(f"预算范围: {memory.budget_range}")
        if memory.risk_tolerance:
            prefs.append(f"风险偏好: {memory.risk_tolerance}")
        return ", ".join(prefs) if prefs else ""
    except Exception:
        return ""


def get_price_trends(item_ids: list[str]) -> dict[str, dict]:
    """从 price_history.db 获取物品价格趋势摘要。"""
    trends = {}
    try:
        from .price_history import PriceHistoryDB
        db = PriceHistoryDB()
        for item_id in item_ids:
            pred = db.predict_trend(item_id)
            if pred:
                trends[item_id] = {
                    "direction": pred.get("direction", "stable"),
                    "change_pct": pred.get("change_pct", 0),
                    "confidence": pred.get("confidence", 0),
                }
    except Exception:
        pass
    return trends


# ── 公开 API ─────────────────────────────────────────────────────────────


def scout_mod_candidates(
    mods: list[dict],
    cached_stats: dict[str, dict] | None = None,
) -> list[str]:
    """用 kimi-k2.6 从 Mod 列表中筛选最可能盈利的候选。"""
    cache_key = f"mod_flipper:{len(mods)}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.debug("Scout mod_flipper 缓存命中: %d 个候选", len(cached))
        return cached

    limit = config.SCOUT_MAX_CANDIDATES["mod_flipper"]
    model = config.SCOUT_MODELS["mod_flipper"]
    # 获取价格趋势增强摘要
    mod_ids = [m.get("url_name", "") for m in mods if m.get("url_name")]
    trends = get_price_trends(mod_ids)
    summary = _build_mod_summary(mods, cached_stats, price_trends=trends)
    prompt = _PROMPT_MOD_FLIPPER.format(total=len(mods), summary=summary, limit=limit)

    response = _call_cloud(prompt, model)
    ids = _parse_json_list(response)

    # 验证返回的 id 在候选列表中
    valid_ids = {m.get("url_name") for m in mods}
    ids = [i for i in ids if i in valid_ids]

    if ids:
        _set_cache(cache_key, ids)
        logger.info("Scout mod_flipper: %d → %d (%s)", len(mods), len(ids), model)
    else:
        logger.warning("Scout mod_flipper 返回空结果，将使用原始候选列表")

    return ids


def scout_set_candidates(groups: list) -> list[str]:
    """用 glm-5.1 从套装列表中筛选最可能盈利的候选。"""
    cache_key = f"set_profit:{len(groups)}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.debug("Scout set_profit 缓存命中: %d 个候选", len(cached))
        return cached

    limit = config.SCOUT_MAX_CANDIDATES["set_profit"]
    model = config.SCOUT_MODELS["set_profit"]
    summary = _build_set_summary(groups)
    prompt = _PROMPT_SET_PROFIT.format(total=len(groups), summary=summary, limit=limit)

    response = _call_cloud(prompt, model)
    ids = _parse_json_list(response)

    valid_ids = {g.base_id for g in groups}
    ids = [i for i in ids if i in valid_ids]

    if ids:
        _set_cache(cache_key, ids)
        logger.info("Scout set_profit: %d → %d (%s)", len(groups), len(ids), model)
    else:
        logger.warning("Scout set_profit 返回空结果，将使用原始候选列表")

    return ids


def scout_investment_candidates(
    groups: list,
    budget: int = 500,
    event_info: str = "",
) -> list[str]:
    """用 gpt-5.5 从套装列表中筛选最值得投资的候选。"""
    cache_key = f"investment:{len(groups)}:{budget}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.debug("Scout investment 缓存命中: %d 个候选", len(cached))
        return cached

    limit = config.SCOUT_MAX_CANDIDATES["investment"]
    model = config.SCOUT_MODELS["investment"]
    summary = _build_set_summary(groups)
    # 自动获取事件上下文和用户偏好
    events = event_info or get_event_context()
    user_prefs = get_user_preferences()
    extra_context = ""
    if user_prefs:
        extra_context = f"\n用户偏好：{user_prefs}"
    prompt = _PROMPT_INVESTMENT.format(
        total=len(groups), summary=summary, limit=limit,
        budget=budget, event_info=events or "无特殊事件",
    ) + extra_context

    response = _call_cloud(prompt, model)
    ids = _parse_json_list(response)

    valid_ids = {g.base_id for g in groups}
    ids = [i for i in ids if i in valid_ids]

    if ids:
        _set_cache(cache_key, ids)
        logger.info("Scout investment: %d → %d (%s)", len(groups), len(ids), model)
    else:
        logger.warning("Scout investment 返回空结果，将使用原始候选列表")

    return ids


def clear_scout_cache():
    """清除预筛选缓存。"""
    _scout_cache.clear()


# ── 反馈追踪 ─────────────────────────────────────────────────────────────

# 记录 scout 推荐的物品实际盈利情况: item_id -> [profit1, profit2, ...]
_scout_feedback: dict[str, list[float]] = {}


def record_scout_feedback(item_id: str, profit: float):
    """记录 scout 推荐物品的实际盈利，用于后续优化。"""
    if item_id not in _scout_feedback:
        _scout_feedback[item_id] = []
    _scout_feedback[item_id].append(profit)


def get_scout_accuracy() -> dict[str, float]:
    """获取 scout 推荐准确率（盈利物品占比）。"""
    if not _scout_feedback:
        return {}
    accuracy = {}
    for item_id, profits in _scout_feedback.items():
        profitable = sum(1 for p in profits if p > 0)
        accuracy[item_id] = profitable / len(profits) if profits else 0
    return accuracy
