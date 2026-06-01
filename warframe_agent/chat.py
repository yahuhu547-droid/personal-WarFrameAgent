from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import AsyncIterator, Callable, Iterable

import requests

from . import config
from .bilibili_recommendations import (
    BilibiliRecommendationService,
    BilibiliRecommendationStore,
    format_bilibili_recommendations,
    is_bilibili_recommendation_intent,
)
from .experts import ExpertRequest, run_expert
from .dictionary import ItemResolver, normalize_lookup_key
from .events import EventTracker
from .formatter import build_whisper
from .game_data import GameDataStore
from .knowledge import MarketKnowledge
from .market import MarketOrder, best_buyers, best_sellers, fetch_orders
from .memory import AgentMemory, normalize_opportunity_filter
from .memory_recall import MemoryRecallService
from .names import display_item_name, english_name, load_item_data
from .opportunity_lookup import (
    OpportunityLookupStore,
    format_opportunity_lookup_reply,
    is_opportunity_lookup_id,
    normalize_opportunity_lookup_id,
    opportunity_not_found_message,
)
from .price_history import PriceHistoryDB
from .push import PushConfig
from .rag import smart_search_rag
from .session import SessionContext, is_followup
from .riven import _looks_like_riven_query
from .tool_context import wrap_untrusted_model_text
from .tool_router import build_router_prompt, parse_tool_call, select_candidate_tools
from .tool_registry import ToolResult, create_default_tool_registry
from .trade_intent import detect_trade_intent, detect_completed_trade, detect_trend_query, detect_compare_query
from .warframes import price_warframe_query

logger = logging.getLogger(__name__)


EXIT_COMMANDS = {"q", "quit", "exit", "退出", "关闭"}
RIVEN_ONLINE_STATUSES = ("ingame", "online")
RIVEN_ALL_STATUSES = ()
RIVEN_INGAME_STATUSES = ("ingame",)
RIVEN_INGAME_KEYWORDS = ("游戏中", "在游戏中", "游戏里的", "ingame", "in game")
RIVEN_ONLINE_KEYWORDS = ("在线", "online", "在线玩家", "在线的", "在线卖家")
RIVEN_ALL_STATUS_KEYWORDS = ("全部", "所有", "离线", "offline", "包括离线", "离线也要")


def _tool_metadata_to_dict(meta) -> dict:
    return {
        "tool_name": meta.tool_name,
        "args_summary": _json_safe_tool_value(meta.args_summary),
        "ok": meta.ok,
        "error": meta.error,
        "duration_ms": round(meta.duration_ms, 2),
        "timestamp": meta.timestamp,
    }


def _json_safe_tool_value(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > 500:
            return f"{value[:300]}... [len={len(value)}]"
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe_tool_value(val) for key, val in list(value.items())[:50]}
    if isinstance(value, (list, tuple)):
        return [_json_safe_tool_value(item) for item in list(value)[:50]]
    text = repr(value)
    if len(text) > 300:
        return f"{text[:200]}... [len={len(text)}]"
    return text


def _riven_statuses_from_message(message: str, default_online: bool = False) -> tuple[str, ...] | None:
    lowered = message.lower()
    if any(keyword in lowered for keyword in RIVEN_ALL_STATUS_KEYWORDS):
        return RIVEN_ALL_STATUSES
    if any(keyword in lowered for keyword in RIVEN_INGAME_KEYWORDS):
        return RIVEN_INGAME_STATUSES
    if any(keyword in lowered for keyword in RIVEN_ONLINE_KEYWORDS):
        return RIVEN_ONLINE_STATUSES
    return RIVEN_ONLINE_STATUSES if default_online else None


def _riven_status_label(statuses: tuple[str, ...]) -> str:
    if statuses == RIVEN_INGAME_STATUSES:
        return "游戏中卖家"
    if statuses == RIVEN_ONLINE_STATUSES:
        return "在线卖家"
    if statuses == RIVEN_ALL_STATUSES:
        return "全部卖家"
    return "卖家"


def build_system_context(
    knowledge: MarketKnowledge | None = None,
    event_tracker: EventTracker | None = None,
    memory: AgentMemory | None = None,
    game_data: GameDataStore | None = None,
    current_item_ids: list[str] | None = None,
) -> str:
    """构建富上下文注入 system prompt，让 LLM 拥有市场知识、事件、交易历史、游戏数据。"""
    parts = []

    # 1. 当前查询物品的详细情报
    if current_item_ids and game_data:
        for item_id in current_item_ids[:3]:
            block = _build_item_knowledge_block(item_id, knowledge, game_data)
            if block:
                parts.append(block)

    # 2. 市场概况
    if knowledge:
        summary = knowledge.get_market_summary()
        trend = summary.get("trend_direction", "unknown")
        total = summary.get("total_items", 0)
        if total > 0:
            parts.append(f"[市场概况] 趋势={trend}，跟踪物品={total}")
            best = summary.get("best_category", "")
            if best:
                parts.append(f"最佳品类: {best}")
        # 热门物品（带扫描置信度）
        for cat in ("mod", "prime_set"):
            health = knowledge.get_category_health(cat)
            if health and health.top_items:
                item_labels = []
                for iid in health.top_items[:3]:
                    stats = knowledge.get_item_stats(iid)
                    name = display_item_name(iid)
                    if stats and stats.scan_count >= 5:
                        item_labels.append(f"{name}[高置信]")
                    elif stats and stats.scan_count >= 3:
                        item_labels.append(name)
                    else:
                        item_labels.append(f"{name}[低样本]")
                parts.append(f"{cat} 热门: {', '.join(item_labels)}")
        # 事件影响的物品
        event_items = [
            (iid, ik.event_context)
            for iid, ik in knowledge._items.items()
            if ik.event_context
        ]
        if event_items:
            labels = [f"{display_item_name(iid)}({ctx})" for iid, ctx in event_items[:3]]
            parts.append(f"事件影响: {', '.join(labels)}")

    # 3. 游戏事件
    if event_tracker:
        events = event_tracker.get_active_events()
        if events:
            event_descs = [f"{e.event_type}: {e.description[:40]}" for e in events[:3]]
            parts.append(f"[游戏事件] {'; '.join(event_descs)}")

    # 4. 交易胜率
    if memory and memory.trade_outcomes:
        outcomes = memory.trade_outcomes
        wins = sum(1 for o in outcomes if o.actual_profit > 0)
        total_profit = sum(o.actual_profit for o in outcomes)
        parts.append(f"[交易统计] 胜率={wins}/{len(outcomes)}，累计利润={total_profit}p")

    # 6. 策略反馈（样本 >= 3 才显示）
    if memory and memory.trade_outcomes and len(memory.trade_outcomes) >= 3:
        try:
            from .feedback import FeedbackAnalyzer
            analyzer = FeedbackAnalyzer()
            strategy_feedback = analyzer.analyze_strategies(memory.trade_outcomes)
            if strategy_feedback:
                fb_lines = []
                for sf in strategy_feedback[:3]:
                    label = {"mod_flip": "Mod翻转", "set_profit": "套装利润", "investment": "投资翻转"}.get(sf.strategy, sf.strategy)
                    fb_lines.append(f"{label}: 胜率={sf.win_rate:.0%}, 平均利润={sf.avg_profit:.0f}p, 样本={sf.sample_size}")
                if fb_lines:
                    parts.append("[策略表现]\n" + "\n".join(fb_lines))
        except Exception:
            pass

    return "\n".join(parts) if parts else ""


def _build_item_knowledge_block(
    item_id: str,
    knowledge: MarketKnowledge | None,
    game_data: GameDataStore,
) -> str | None:
    """为单个物品构建详细知识块，注入 LLM 上下文。"""
    lines = []
    name = display_item_name(item_id)

    # 知识库统计
    if knowledge:
        stats = knowledge.get_item_stats(item_id)
        if stats:
            if stats.trend != "stable":
                lines.append(f"趋势={stats.trend}")
            if stats.event_context:
                lines.append(f"事件影响={stats.event_context}")
            if stats.volatility > 30:
                lines.append(f"波动率={stats.volatility:.0f}(高)")

    # Mod/Arcane 效果描述
    mod_info = game_data.get_mod_info(name)
    if mod_info:
        lines.append(mod_info)

    # 杜卡特值
    ducat = game_data.get_ducat_value(item_id)
    if ducat:
        lines.append(f"杜卡特值={ducat}")

    if not lines:
        return None
    return f"[物品情报: {name}]\n" + "\n".join(lines)
WATCHLIST_COMMANDS = {"watchlist", "关注列表", "扫描关注", "每日关注"}


@dataclass(frozen=True)
class ItemContext:
    item_id: str
    text: str
    best_sell_price: int | None = None
    best_buy_price: int | None = None
    best_seller: MarketOrder | None = None
    best_buyer: MarketOrder | None = None
    model_context: str | None = None


@dataclass(frozen=True)
class ChatModeDecision:
    mode: str
    reason: str = ""


@dataclass(frozen=True)
class PendingGoalConfirmation:
    description: str
    goal_type: str
    criteria: dict
    summary: str


@dataclass(frozen=True)
class GoalStatusIntent:
    action: str
    selector_type: str
    selector: str


@dataclass(frozen=True)
class PendingGoalStatusConfirmation:
    action: str
    goal_id: str
    description: str
    target_status: str


@dataclass(frozen=True)
class PriceAlertIntent:
    action: str
    item_name: str
    direction: str
    price: int


@dataclass(frozen=True)
class FavoriteIntent:
    action: str
    item_name: str


@dataclass(frozen=True)
class PreferenceIntent:
    updates: dict[str, object]
    summary_parts: list[str]


@dataclass(frozen=True)
class ReviewDoneIntent:
    lookup_id: str
    actual_profit: int
    feedback: str


@dataclass(frozen=True)
class PendingReviewDoneConfirmation:
    lookup_id: str
    actual_profit: int
    feedback: str
    item_id: str
    expected_profit: int


@dataclass(frozen=True)
class FissureAlertIntent:
    action: str
    tokens: list[str]
    index: int | None = None
    note: str = ""


@dataclass(frozen=True)
class PendingFissureAlertConfirmation:
    action: str
    tokens: list[str]
    index: int | None = None
    note: str = ""


@dataclass(frozen=True)
class PendingAgentPlanConfirmation:
    original_message: str
    confirmation_token: str
    blocked_reason: str
    candidate_tools: tuple[str, ...] | None = None


def is_chat_exit(message: str) -> bool:
    return message.strip().lower() in EXIT_COMMANDS


def is_watchlist_command(message: str) -> bool:
    return message.strip().lower() in WATCHLIST_COMMANDS


_PRICE_ALERT_REMINDER_TERMS = (
    "提醒我", "通知我", "提醒", "通知", "盯一下", "盯着", "盯",
    "价格提醒", "alert me", "notify me",
)
_PRICE_ALERT_CANCEL_TERMS = (
    "取消", "删除", "移除", "关闭", "不要", "不用",
    "cancel", "remove", "delete", "off",
)
_PRICE_ALERT_BELOW_TERMS = ("低于", "低过", "小于", "跌到", "跌破", "降到", "below", "<=")
_PRICE_ALERT_ABOVE_TERMS = ("高于", "超过", "大于", "涨到", "涨破", "above", ">=")
_PRICE_ALERT_FILLER_TERMS = (
    "帮我", "请", "当", "如果", "一下", "价格", "的时候", "时", "就",
    "me", "when", "if",
)


_FAVORITE_REMOVE_TERMS = (
    "取消关注", "取消收藏", "移除关注", "移除收藏", "删除关注", "删除收藏",
    "不再关注", "别关注", "不要关注", "不用关注", "取消", "移除", "删除",
    "remove favorite", "unfavorite",
)
_FAVORITE_ADD_TERMS = (
    "帮我关注", "帮我收藏", "关注一下", "收藏一下", "加入关注", "加入收藏",
    "添加关注", "添加收藏", "加到关注", "加到收藏", "关注", "收藏",
    "favorite",
)
_FAVORITE_QUESTION_TERMS = (
    "值得关注", "是否值得", "要不要关注", "能不能关注", "可不可以关注",
    "该不该关注", "关注什么", "怎么关注", "吗", "么", "？", "?",
)
_FAVORITE_BLOCKED_TERMS = (
    "关注价格", "价格提醒", "价格通知", "低于", "高于", "提醒我", "通知我",
    "扫描关注", "每日关注", "交易机会", "机会推送", "关注推送",
    "只看赋能", "只检测mod", "只检测MOD", "只检测卡",
)
_FAVORITE_FILLER_TERMS = (
    "帮我", "请", "一下", "这个", "物品", "道具", "吧", "把", "加入",
    "添加", "加到", "到", "进", "列表", "收藏夹", "里", "中",
)


_PREFERENCE_ANCHOR_TERMS = (
    "我的", "我预算", "我偏好", "偏好", "设置", "设为", "调整", "改成",
    "以后", "今后", "帮我记", "记住", "我希望", "我想", "只看",
    "平台", "跨平台", "crossplay", "最多", "最大", "返回", "显示",
)
_PREFERENCE_QUESTION_TERMS = (
    "买什么", "够吗", "是什么意思", "有哪些", "推荐", "要不要", "该不该",
    "怎么", "什么", "多少", "吗", "么", "？", "?",
)
_PREFERENCE_BLOCKED_TERMS = (
    "提醒我", "通知我", "价格提醒", "价格通知", "低于", "高于",
    "帮我收藏", "帮我关注", "取消收藏", "取消关注", "关注列表",
    "交易机会", "机会推送", "一周赚", "制定", "计划",
)
_PREFERENCE_LOW_RISK_TERMS = ("低风险", "风险低", "保守", "稳健", "偏低风险")
_PREFERENCE_MEDIUM_RISK_TERMS = ("中风险", "中等风险", "均衡", "平衡")
_PREFERENCE_HIGH_RISK_TERMS = ("高风险", "风险高", "激进", "高收益高风险")
_PREFERENCE_CATEGORY_TERMS = (
    ("mod", ("mod", "卡片", "振幅晶体")),
    ("arcane", ("赋能", "arcane")),
    ("prime_set", ("prime套装", "prime套", "p套", "套装")),
    ("prime_part", ("prime部件", "部件", "蓝图", "机体", "系统", "头部")),
    ("riven", ("紫卡", "riven")),
    ("baro", ("虚空商人", "baro")),
)
_PREFERENCE_PLATFORM_TERMS = ("pc", "xbox", "ps4", "ps5", "switch")


_GOAL_STATUS_CANCEL_CONTEXT_TERMS = (
    "不要完成", "别完成", "暂不完成", "不要放弃", "别放弃", "暂不放弃",
    "完成了吗", "怎么完成", "该放弃", "要不要放弃", "完成后", "一笔交易",
    "reviewdone", "/reviewdone",
)
_GOAL_STATUS_COMPLETE_TERMS = ("标记完成", "完成目标", "目标完成", "完成", "达成", "done", "achieved")
_GOAL_STATUS_DROP_TERMS = ("放弃目标", "目标放弃", "放弃", "不做", "abandon", "drop")
_GOAL_STATUS_ORDINAL_NUMBERS = {
    "1": 1, "一": 1, "第一个": 1,
    "2": 2, "二": 2, "两": 2, "第二个": 2,
    "3": 3, "三": 3, "第三个": 3,
    "4": 4, "四": 4, "第四个": 4,
    "5": 5, "五": 5, "第五个": 5,
}


_REVIEW_DONE_ANCHOR_TERMS = (
    "复盘", "记录", "记一下", "记为", "实际", "结果", "已完成", "完成了",
    "反馈", "review", "record",
)
_REVIEW_DONE_BLOCKED_TERMS = (
    "怎么", "如何", "教程", "用法", "预计", "预期", "目标利润", "预算",
    "等卖掉", "以后", "完成后用/reviewdone", "/reviewdone",
)
_REVIEW_DONE_QUESTION_TERMS = ("吗", "么", "？", "?")
_REVIEW_GOOD_TERMS = ("不错", "很好", "顺利", "成功", "满意", "good", "accepted")
_REVIEW_BAD_TERMS = ("不好", "不行", "失败", "踩坑", "亏", "bad", "rejected")
_REVIEW_IGNORED_TERMS = ("没做", "没成交", "跳过", "忽略", "取消", "ignored")
_REVIEW_NEUTRAL_TERMS = ("一般", "持平", "没赚没亏", "neutral")


_FISSURE_ALERT_WORDS = ("裂缝", "裂隙", "虚空裂缝", "虚空裂隙", "fissure")
_FISSURE_ALERT_SUBSCRIBE_TERMS = (
    "提醒我", "通知我", "订阅", "关注", "盯一下", "盯着", "叫我", "告诉我",
    "alert me", "notify me", "subscribe",
)
_FISSURE_ALERT_REMOVE_TERMS = (
    "取消", "删除", "移除", "不再提醒", "不提醒", "关闭", "cancel", "remove", "delete",
)
_FISSURE_ALERT_QUERY_TERMS = (
    "现在", "当前", "有什么", "哪些", "哪里", "在哪", "适合", "怎么", "列表",
    "有吗", "吗", "？", "?",
)
_FISSURE_ALERT_BLOCKED_TERMS = ("热美亚", "thermia", "收益", "怎么刷", "不要直接提醒")
_FISSURE_ALERT_ORDINAL_NUMBERS = {
    "1": 1, "一": 1, "第一个": 1,
    "2": 2, "二": 2, "两": 2, "第二个": 2,
    "3": 3, "三": 3, "第三个": 3,
    "4": 4, "四": 4, "第四个": 4,
    "5": 5, "五": 5, "第五个": 5,
    "6": 6, "六": 6, "第六个": 6,
    "7": 7, "七": 7, "第七个": 7,
    "8": 8, "八": 8, "第八个": 8,
    "9": 9, "九": 9, "第九个": 9,
    "10": 10, "十": 10, "第十个": 10,
}
_FISSURE_ALERT_TOKEN_ALIASES = (
    ("钢铁之路", "钢铁"),
    ("steelpath", "steelpath"),
    ("steel", "steel"),
    ("钢铁", "钢铁"),
    ("普通", "普通"),
    ("normal", "normal"),
    ("古纪", "古纪"),
    ("前纪", "前纪"),
    ("中纪", "中纪"),
    ("后纪", "后纪"),
    ("遗珍", "遗珍"),
    ("仲裁", "仲裁"),
    ("lith", "lith"),
    ("meso", "meso"),
    ("neo", "neo"),
    ("axi", "axi"),
    ("requiem", "requiem"),
    ("arbitration", "arbitration"),
    ("移动防御", "移动防御"),
    ("歼灭", "歼灭"),
    ("捕获", "捕获"),
    ("防御", "防御"),
    ("生存", "生存"),
    ("救援", "救援"),
    ("破坏", "破坏"),
    ("间谍", "间谍"),
    ("拦截", "拦截"),
    ("挖掘", "挖掘"),
    ("炼金", "炼金"),
    ("中断", "中断"),
    ("刺杀", "刺杀"),
    ("虚空", "虚空"),
    ("地球", "地球"),
    ("火星", "火星"),
    ("金星", "金星"),
    ("水星", "水星"),
    ("木星", "木星"),
    ("土星", "土星"),
    ("天王星", "天王星"),
    ("海王星", "海王星"),
    ("冥王星", "冥王星"),
    ("塞德娜", "塞德娜"),
    ("火卫一", "火卫一"),
    ("谷神星", "谷神星"),
    ("欧罗巴", "欧罗巴"),
)


def _parse_fissure_alert_index(text: str) -> int | None:
    match = re.search(r"第\s*([0-9一二两三四五六七八九十]+)\s*(?:个|条)?", text)
    if match:
        value = match.group(1)
        if value.isdigit():
            return int(value)
        return _FISSURE_ALERT_ORDINAL_NUMBERS.get(value)
    digit_match = re.search(r"\b([1-9][0-9]*)\b", text)
    if digit_match:
        return int(digit_match.group(1))
    return None


def _extract_fissure_alert_tokens(text: str) -> list[str]:
    compact = re.sub(r"\s+", "", text.lower())
    matches = []
    for term, token in _FISSURE_ALERT_TOKEN_ALIASES:
        position = compact.find(term.lower())
        if position >= 0:
            matches.append((position, -len(term), token))
    matches.sort()
    tokens = []
    for _, _, token in matches:
        if token not in tokens:
            tokens.append(token)
    return tokens


def _parse_natural_language_fissure_alert(message: str) -> FissureAlertIntent | None:
    text = (message or "").strip()
    if not text or text.startswith("/"):
        return None
    compact = re.sub(r"\s+", "", text.lower())
    if not any(term.lower() in compact for term in _FISSURE_ALERT_WORDS):
        return None
    if any(term.lower() in compact for term in _FISSURE_ALERT_BLOCKED_TERMS):
        return None

    has_remove = any(term.lower() in compact for term in _FISSURE_ALERT_REMOVE_TERMS)
    if has_remove:
        index = _parse_fissure_alert_index(text)
        if index is None:
            return None
        return FissureAlertIntent(action="remove", tokens=[], index=index, note=f"第{index}条裂缝订阅")

    if not any(term.lower() in compact for term in _FISSURE_ALERT_SUBSCRIBE_TERMS):
        return None
    if any(term.lower() in compact for term in _FISSURE_ALERT_QUERY_TERMS):
        return None

    tokens = _extract_fissure_alert_tokens(text)
    if not tokens:
        return None
    return FissureAlertIntent(action="add", tokens=tokens, note="、".join(tokens))


def _parse_review_done_profit(text: str) -> int | None:
    patterns = (
        r"(?:实际|最后|净)?\s*(?:赚了?|盈利|利润|净赚)\s*([+-]?\d+)\s*(?:p|pt|白金|铂金)?",
        r"(?:实际|最后)?\s*(?:亏了?|亏损)\s*([+-]?\d+)\s*(?:p|pt|白金|铂金)?",
        r"(?:实际利润|实际收益|利润是|收益是)\s*([+-]?\d+)\s*(?:p|pt|白金|铂金)?",
    )
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = int(match.group(1))
        if index == 1 and value > 0:
            value = -value
        return value
    return None


def _parse_review_done_feedback(text: str, actual_profit: int) -> str:
    compact = re.sub(r"\s+", "", text.lower())
    if any(term.lower() in compact for term in _REVIEW_IGNORED_TERMS):
        return "ignored"
    if any(term.lower() in compact for term in _REVIEW_BAD_TERMS):
        return "bad"
    if any(term.lower() in compact for term in _REVIEW_NEUTRAL_TERMS):
        return "neutral"
    if any(term.lower() in compact for term in _REVIEW_GOOD_TERMS):
        return "good"
    return ChatAgent._default_feedback_for_profit(actual_profit)


def _parse_natural_language_review_done(message: str) -> ReviewDoneIntent | None:
    text = (message or "").strip()
    if not text or text.startswith("/"):
        return None
    compact = re.sub(r"\s+", "", text.lower())
    if any(term.lower() in compact for term in _REVIEW_DONE_QUESTION_TERMS):
        return None
    if any(term.lower() in compact for term in _REVIEW_DONE_BLOCKED_TERMS):
        return None
    if not any(term.lower() in compact for term in _REVIEW_DONE_ANCHOR_TERMS):
        return None

    lookup_match = re.search(r"\bOP[A-Z0-9]{6}\b", text, flags=re.IGNORECASE)
    if not lookup_match:
        return None
    lookup_id = normalize_opportunity_lookup_id(lookup_match.group(0))
    if not is_opportunity_lookup_id(lookup_id):
        return None

    actual_profit = _parse_review_done_profit(text)
    if actual_profit is None:
        return None
    feedback = _parse_review_done_feedback(text, actual_profit)
    return ReviewDoneIntent(lookup_id=lookup_id, actual_profit=actual_profit, feedback=feedback)


def _parse_goal_status_ordinal(value: str) -> int | None:
    normalized = (value or "").strip()
    if normalized.isdigit():
        return int(normalized)
    return _GOAL_STATUS_ORDINAL_NUMBERS.get(normalized)


def _parse_natural_language_goal_status(message: str) -> GoalStatusIntent | None:
    text = (message or "").strip()
    if not text or text.startswith("/"):
        return None
    compact = re.sub(r"\s+", "", text.lower())
    if "目标" not in compact and "goal" not in compact:
        return None
    if any(term.lower() in compact for term in _GOAL_STATUS_CANCEL_CONTEXT_TERMS):
        return None

    if any(term.lower() in compact for term in _GOAL_STATUS_DROP_TERMS):
        action = "drop"
    elif any(term.lower() in compact for term in _GOAL_STATUS_COMPLETE_TERMS):
        action = "complete"
    else:
        return None

    ordinal_match = re.search(r"第\s*([0-9一二两三四五])\s*个?\s*目标", text, flags=re.IGNORECASE)
    if ordinal_match:
        ordinal = _parse_goal_status_ordinal(ordinal_match.group(1))
        if ordinal:
            return GoalStatusIntent(action=action, selector_type="index", selector=str(ordinal))

    id_match = re.search(
        r"(?:目标|goal)\s*([0-9a-f]{4,12})|([0-9a-f]{4,12})\s*(?:这个)?(?:目标|goal)",
        text,
        flags=re.IGNORECASE,
    )
    if id_match:
        return GoalStatusIntent(action=action, selector_type="id", selector=(id_match.group(1) or id_match.group(2)).lower())

    fragment = text
    for term in (*_GOAL_STATUS_COMPLETE_TERMS, *_GOAL_STATUS_DROP_TERMS, "目标", "这个", "把", "标记", "为", "了", "第"):
        fragment = re.sub(re.escape(term), " ", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"[\s，。！？?：:；;、,.!]+", " ", fragment).strip()
    if len(fragment) >= 2:
        return GoalStatusIntent(action=action, selector_type="description", selector=fragment)
    return None


def _parse_natural_language_price_alert(message: str) -> PriceAlertIntent | None:
    text = (message or "").strip()
    if not text:
        return None
    compact = re.sub(r"\s+", "", text.lower())
    if not any(term in compact for term in _PRICE_ALERT_REMINDER_TERMS):
        return None

    direction = ""
    direction_terms = ()
    if any(term in compact for term in _PRICE_ALERT_BELOW_TERMS):
        direction = "below"
        direction_terms = _PRICE_ALERT_BELOW_TERMS
    elif any(term in compact for term in _PRICE_ALERT_ABOVE_TERMS):
        direction = "above"
        direction_terms = _PRICE_ALERT_ABOVE_TERMS
    else:
        return None

    price_match = re.search(r"(\d+)\s*(?:p|pt|白金|铂金|platinum)?", text, flags=re.IGNORECASE)
    if not price_match:
        return None
    price = int(price_match.group(1))

    action = "remove" if any(term in compact for term in _PRICE_ALERT_CANCEL_TERMS) else "add"
    item_name = text
    item_name = item_name.replace(price_match.group(0), " ")
    for term in sorted(
        (*_PRICE_ALERT_REMINDER_TERMS, *_PRICE_ALERT_CANCEL_TERMS, *direction_terms, *_PRICE_ALERT_FILLER_TERMS),
        key=len,
        reverse=True,
    ):
        item_name = re.sub(re.escape(term), " ", item_name, flags=re.IGNORECASE)
    item_name = re.sub(r"[\s，,。！？!?:：；;]+", " ", item_name).strip()
    if not item_name:
        return None
    return PriceAlertIntent(action=action, item_name=item_name, direction=direction, price=price)


def _parse_natural_language_favorite(message: str) -> FavoriteIntent | None:
    text = (message or "").strip()
    if not text or is_watchlist_command(text):
        return None
    compact = re.sub(r"\s+", "", text.lower())
    if any(term.lower() in compact for term in _FAVORITE_QUESTION_TERMS):
        return None
    if any(term.lower() in compact for term in _FAVORITE_BLOCKED_TERMS):
        return None

    action = ""
    action_terms: tuple[str, ...] = ()
    if any(term.lower() in compact for term in _FAVORITE_REMOVE_TERMS):
        action = "remove"
        action_terms = _FAVORITE_REMOVE_TERMS
    elif any(term.lower() in compact for term in _FAVORITE_ADD_TERMS):
        action = "add"
        action_terms = _FAVORITE_ADD_TERMS
    else:
        return None

    item_name = text
    for term in sorted((*action_terms, *_FAVORITE_FILLER_TERMS), key=len, reverse=True):
        item_name = re.sub(re.escape(term), " ", item_name, flags=re.IGNORECASE)
    item_name = re.sub(r"[\s，。！？?：:；;、,.!]+", " ", item_name).strip()
    if not item_name:
        return None
    return FavoriteIntent(action=action, item_name=item_name)


def _parse_natural_language_preference(message: str) -> PreferenceIntent | None:
    text = (message or "").strip()
    if not text:
        return None
    compact = re.sub(r"\s+", "", text.lower())
    if not any(term.lower() in compact for term in _PREFERENCE_ANCHOR_TERMS):
        return None
    if any(term.lower() in compact for term in _PREFERENCE_QUESTION_TERMS):
        return None
    if any(term.lower() in compact for term in _PREFERENCE_BLOCKED_TERMS):
        return None

    updates: dict[str, object] = {}
    summary_parts: list[str] = []

    budget_match = re.search(
        r"(?:预算|本金|投入|资金)[^\d]{0,8}(\d+)(?:\s*(?:-|到|至|~|－|—)\s*(\d+))?\s*(?:p|pt|白金|铂金)?",
        text,
        flags=re.IGNORECASE,
    )
    if budget_match:
        first = int(budget_match.group(1))
        second = int(budget_match.group(2)) if budget_match.group(2) else 0
        if second:
            budget_min, budget_max = (first, second) if first <= second else (second, first)
        else:
            budget_min, budget_max = 0, first
        updates["budget_min"] = budget_min
        updates["budget_max"] = budget_max
        summary_parts.append(f"预算={budget_min}-{budget_max}p")

    if any(term in compact for term in _PREFERENCE_LOW_RISK_TERMS):
        updates["risk_appetite"] = "low"
        summary_parts.append("风险=low")
    elif any(term in compact for term in _PREFERENCE_MEDIUM_RISK_TERMS):
        updates["risk_appetite"] = "medium"
        summary_parts.append("风险=medium")
    elif any(term in compact for term in _PREFERENCE_HIGH_RISK_TERMS):
        updates["risk_appetite"] = "high"
        summary_parts.append("风险=high")

    roi_match = re.search(
        r"(?:最低\s*(?:roi|利润|收益率)|(?:roi|收益率)\s*(?:至少|最低)|至少)[^\d]{0,8}(\d+)\s*%?",
        text,
        flags=re.IGNORECASE,
    )
    if roi_match:
        roi = int(roi_match.group(1))
        updates["min_roi_pct"] = roi
        summary_parts.append(f"最低ROI={roi}%")

    turnaround_match = re.search(r"(?:最长|最多|可接受|接受)?(?:周转|出货|持有)[^\d]{0,8}(\d+)\s*天", text)
    if turnaround_match:
        days = int(turnaround_match.group(1))
        updates["max_turnaround_days"] = days
        summary_parts.append(f"最长周转={days}天")

    categories = []
    for category, terms in _PREFERENCE_CATEGORY_TERMS:
        if any(term.lower() in compact for term in terms):
            categories.append(category)
    if categories:
        updates["preferred_categories"] = categories
        summary_parts.append("品类=" + ",".join(categories))

    if "平台" in compact:
        for platform in _PREFERENCE_PLATFORM_TERMS:
            if platform in compact:
                updates["platform"] = platform
                summary_parts.append(f"平台={platform}")
                break

    if "跨平台" in compact or "crossplay" in compact:
        if any(term in compact for term in ("关闭", "关掉", "不开", "禁用", "off", "false", "no")):
            updates["crossplay"] = False
            summary_parts.append("跨平台=off")
        elif any(term in compact for term in ("开启", "打开", "启用", "开", "on", "true", "yes")):
            updates["crossplay"] = True
            summary_parts.append("跨平台=on")

    max_match = re.search(r"(?:最多|最大|返回|显示|结果数)[^\d]{0,8}(\d+)\s*(?:个|条|结果)?", text)
    if max_match:
        max_results = int(max_match.group(1))
        if 1 <= max_results <= 50:
            updates["max_results"] = max_results
            summary_parts.append(f"结果数={max_results}")

    if not updates:
        return None
    return PreferenceIntent(updates=updates, summary_parts=summary_parts)


def build_item_context(item_id: str, orders: Iterable[dict]) -> str:
    return build_item_context_result(item_id, orders).text


def build_item_context_result(item_id: str, orders: Iterable[dict]) -> ItemContext:
    order_list = list(orders)

    # 检测是否有 rank/mod_rank 字段（赋能/Mod），统一用满级比较
    rank_filter = None
    ranks = []
    for o in order_list:
        r = o.get("rank") if o.get("rank") is not None else o.get("mod_rank")
        if r is not None:
            ranks.append(r)
    if ranks:
        rank_filter = max(ranks)

    sellers = best_sellers(order_list, limit=5, rank_filter=rank_filter)
    buyers = best_buyers(order_list, limit=5, rank_filter=rank_filter)
    lines = [f"物品: {display_item_name(item_id)}"]

    best_seller = sellers[0] if sellers else None
    best_buyer = buyers[0] if buyers else None
    if best_seller:
        lines.append(f"最低卖价: {best_seller.platinum}p，数量 {best_seller.quantity}，卖家 {best_seller.user_name}，声望 {best_seller.reputation}")
        lines.append(f"推荐购买私聊: {build_whisper(best_seller.user_name, item_id, best_seller.platinum, 'sell')}")
    else:
        lines.append("最低卖价: 暂无在线卖家")
    if best_buyer:
        lines.append(f"最高收价: {best_buyer.platinum}p，数量 {best_buyer.quantity}，买家 {best_buyer.user_name}，声望 {best_buyer.reputation}")
        lines.append(f"推荐出售私聊: {build_whisper(best_buyer.user_name, item_id, best_buyer.platinum, 'buy')}")
    else:
        lines.append("最高收价: 暂无在线买家")
    if best_seller and best_buyer:
        lines.append(f"价差: {best_seller.platinum - best_buyer.platinum}p")

    # 赋能/Mod：额外显示 rank 0 零散价格
    rank0_sell = None
    if (item_id.startswith("arcane_") or item_id.startswith("mod_")) and rank_filter is not None and rank_filter > 0:
        rank0_sellers = best_sellers(order_list, limit=1, rank_filter=0)
        if rank0_sellers:
            rank0_sell = rank0_sellers[0].platinum
            lines.append(f"零散价格（rank 0）: {rank0_sell}p")
        lines.append(f"满级价格（rank {rank_filter}）: {best_seller.platinum}p" if best_seller else f"满级价格: 暂无")

    return ItemContext(
        item_id=item_id,
        text="\n".join(lines),
        best_sell_price=best_seller.platinum if best_seller else None,
        best_buy_price=best_buyer.platinum if best_buyer else None,
        best_seller=best_seller,
        best_buyer=best_buyer,
        model_context=build_safe_query_price_model_context(
            item_id,
            best_seller=best_seller,
            best_buyer=best_buyer,
            rank_filter=rank_filter,
            rank0_sell=rank0_sell,
        ),
    )


def build_safe_query_price_model_context(
    item_id: str,
    *,
    best_seller: MarketOrder | None = None,
    best_buyer: MarketOrder | None = None,
    rank_filter: int | None = None,
    rank0_sell: int | None = None,
    extra_lines: list[str] | None = None,
) -> str:
    """Build allowlisted query_price context for model/session history.

    Deliberately excludes player names, profile URLs, whisper commands and raw order data.
    """
    lines = [
        "tool=query_price",
        f"item_id={item_id}",
        f"display_name={display_item_name(item_id)}",
    ]
    if best_seller:
        lines.append(f"最低卖价: {best_seller.platinum}p")
        lines.append(f"sell_quantity={best_seller.quantity}")
        lines.append(f"sell_reputation={best_seller.reputation}")
        if best_seller.mod_rank is not None:
            lines.append(f"sell_rank={best_seller.mod_rank}")
    else:
        lines.append("最低卖价: 暂无在线卖家")
    if best_buyer:
        lines.append(f"最高收价: {best_buyer.platinum}p")
        lines.append(f"buy_quantity={best_buyer.quantity}")
        lines.append(f"buy_reputation={best_buyer.reputation}")
        if best_buyer.mod_rank is not None:
            lines.append(f"buy_rank={best_buyer.mod_rank}")
    else:
        lines.append("最高收价: 暂无在线买家")
    if best_seller and best_buyer:
        lines.append(f"价差: {best_seller.platinum - best_buyer.platinum}p")
    if rank0_sell is not None:
        lines.append(f"rank0_sell={rank0_sell}p")
    if rank_filter is not None:
        lines.append(f"rank_filter={rank_filter}")
    if extra_lines:
        lines.extend(str(line) for line in extra_lines if line)
    return "\n".join(lines)


def _context_model_text(context: ItemContext) -> str:
    return context.model_context or build_safe_query_price_model_context(
        context.item_id,
        best_seller=context.best_seller,
        best_buyer=context.best_buyer,
    )


def safe_query_price_context_from_contexts(contexts: list[ItemContext]) -> str:
    return "\n\n".join(_context_model_text(context) for context in contexts)


class ChatAgent:
    def __init__(
        self,
        resolver: ItemResolver | None = None,
        order_fetcher: Callable[[str], list[dict]] = fetch_orders,
        model_call: Callable[[str], str] | None = None,
        watchlist: dict[str, list[str]] | None = None,
        memory: AgentMemory | None = None,
        memory_path = None,
        rag_search: Callable[[str], list[str]] | None = None,
        warframe_items: list[dict] | None = None,
        price_db: PriceHistoryDB | None = None,
        router_call: Callable[[str], str] | None = None,
        knowledge: MarketKnowledge | None = None,
        event_tracker: EventTracker | None = None,
        trading_memory_db=None,
        opportunity_lookup_store: OpportunityLookupStore | None = None,
    ):
        self.resolver = resolver or ItemResolver()
        self.order_fetcher = order_fetcher
        self.model_call = model_call or call_ollama_chat
        self.watchlist = watchlist
        self.memory_path = memory_path or config.AGENT_MEMORY_PATH
        self.memory = memory or AgentMemory.load(self.memory_path)
        self.rag_search = rag_search or self._default_rag_search
        self.warframe_items = warframe_items or self._load_items_full()
        self.price_db = price_db
        self.session = SessionContext()
        self.router_call = router_call
        self.knowledge = knowledge
        self.event_tracker = event_tracker
        self.trading_memory_db = trading_memory_db
        self.opportunity_lookup_store = opportunity_lookup_store or OpportunityLookupStore()
        self.bilibili_recommendations_path = config.BILIBILI_RECOMMENDATIONS_PATH
        self.game_data = GameDataStore()
        self.model_orchestrator = None
        self.tool_registry = self._build_tool_registry()
        self.tool_execution_metadata = []
        self.last_agent_trace = None
        self._last_baro_recommendations = []
        self._baro_item_info_lookup = None
        self._pending_goal_confirmation: PendingGoalConfirmation | None = None
        self._pending_goal_status_confirmation: PendingGoalStatusConfirmation | None = None
        self._pending_review_done_confirmation: PendingReviewDoneConfirmation | None = None
        self._pending_fissure_alert_confirmation: PendingFissureAlertConfirmation | None = None
        self._pending_agent_plan_confirmation: PendingAgentPlanConfirmation | None = None

    @staticmethod
    def _load_items_full() -> list[dict]:
        """懒加载 items_full.json 并合并 tradable/fusionLimit 字段。"""
        import json
        from pathlib import Path
        path = config.ITEMS_FULL_PATH
        if not path.exists():
            return []
        try:
            items = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return []

        # 从 warframe-items Mods.json 合并 tradable 和 fusionLimit
        mods_path = Path(__file__).resolve().parent.parent / "githubProduct" / "warframe-items" / "data" / "json" / "Mods.json"
        if mods_path.exists():
            try:
                mods_lookup: dict[str, dict] = {}
                for mod in json.loads(mods_path.read_text(encoding="utf-8")):
                    key = mod.get("name", "").lower().replace(" ", "_").replace("'", "")
                    mods_lookup[key] = mod
                for item in items:
                    if "mod" not in item.get("tags", []):
                        item.setdefault("tradable", True)
                        continue
                    item_id = item.get("item_id", "")
                    mod_data = mods_lookup.get(item_id, {})
                    if not mod_data:
                        en_key = item.get("en_name", "").lower().replace(" ", "_").replace("'", "")
                        mod_data = mods_lookup.get(en_key, {})
                    if mod_data:
                        item.setdefault("tradable", mod_data.get("tradable", False))
                        item.setdefault("modMaxRank", mod_data.get("fusionLimit", 0))
                        item.setdefault("rarity", mod_data.get("rarity", "RARE"))
            except Exception:
                pass

        return items

    def _call_llm_messages(self, messages: list[dict[str, str]]) -> str:
        """使用 messages 格式调用 LLM，自动路由本地/云端模型"""
        # 如果 model_call 是注入的（非默认），直接用旧方式
        if self.model_call is not call_ollama_chat:
            parts = []
            for msg in messages:
                if msg["role"] == "system":
                    parts.insert(0, msg["content"])
                else:
                    parts.append(msg["content"])
            return self.model_call("\n\n".join(parts))
        try:
            from .llm import chat_with_model
            return chat_with_model(messages)
        except Exception as exc:
            logger.debug("chat_with_model 调用失败: %s", exc)
        try:
            from .llm import chat_with_ollama
            return chat_with_ollama(messages)
        except Exception as exc:
            logger.debug("chat_with_ollama 调用失败: %s", exc)
        parts = []
        for msg in messages:
            if msg["role"] == "system":
                parts.insert(0, msg["content"])
            else:
                parts.append(msg["content"])
        return self.model_call("\n\n".join(parts))

    def _try_direct_market_intent(self, message: str) -> str | None:
        lowered = message.lower()
        wants_link = any(keyword in lowered or keyword in message for keyword in ("市场链接", "链接", "url", "warframe.market", "market"))
        wants_seller = any(keyword in message for keyword in ("最便宜卖家", "最低卖家", "最低价卖家", "便宜卖家"))
        wants_bargain = any(keyword in message for keyword in ("砍价", "讲价", "还价", "压价"))
        if not (wants_link or wants_seller or wants_bargain):
            return None

        item_id = self._resolve_direct_market_item_id(message)
        if not item_id:
            return None
        item_display = display_item_name(item_id)
        market_url = f"https://warframe.market/items/{item_id}"
        if wants_link and not (wants_seller or wants_bargain):
            return f"{item_display}\n市场链接: {market_url}"

        context = build_item_context_result(item_id, self.order_fetcher(item_id))
        seller = context.best_seller
        if not seller:
            return f"{item_display}\n当前没有在线卖家。\n市场链接: {market_url}"
        whisper = build_whisper(seller.user_name, item_id, seller.platinum, "sell")
        if wants_seller:
            return "\n".join([
                item_display,
                f"最低卖家: {seller.user_name}，价格 {seller.platinum}p，数量 {seller.quantity}",
                f"购买私聊: {whisper}",
                f"市场链接: {market_url}",
            ])

        target = _extract_platinum_amount(message)
        if target is None:
            discount = max(1, min(10, round(seller.platinum * 0.1)))
            target = max(1, seller.platinum - discount)
        script = f"/w {seller.user_name} Hi, would you take {target}p for {english_name(item_id)}?"
        return "\n".join([
            item_display,
            f"当前最低卖家: {seller.user_name}，标价 {seller.platinum}p",
            f"砍价话术: {script}",
            "如果对方不接受，可以改用原价购买私聊:",
            whisper,
            f"市场链接: {market_url}",
        ])

    def _resolve_direct_market_item_id(self, message: str) -> str | None:
        from .warframes import parse_warframe_query

        query = parse_warframe_query(message, self.warframe_items)
        if query:
            return query.item_ids()[0]

        item_ids = self._item_ids_from_alias_substrings(message)
        if item_ids:
            return item_ids[0]

        try:
            return self.resolver.resolve(message).item_id
        except (LookupError, ValueError):
            pass

        noise_terms = (
            "市场链接", "链接", "url", "warframe.market", "market",
            "最便宜卖家", "最低卖家", "最低价卖家", "便宜卖家",
            "砍价", "讲价", "还价", "压价", "帮我", "给我", "跟卖家", "卖家", "的",
        )
        for token in _message_tokens(message):
            if token in noise_terms:
                continue
            try:
                return self.resolver.resolve(token).item_id
            except (LookupError, ValueError):
                continue
        return None

    def answer(self, message: str) -> str:
        self._reload_memory()
        stripped = message.strip()
        if is_opportunity_lookup_id(stripped):
            result = self._handle_opportunity_lookup([stripped])
            self._log_answer(message, result)
            return result
        if stripped.startswith("/"):
            return self._handle_agent_command(stripped)
        agent_plan_confirmation = self._try_agent_plan_confirmation_response(message)
        if agent_plan_confirmation:
            self._log_answer(message, agent_plan_confirmation)
            return agent_plan_confirmation
        review_confirmation = self._try_review_done_confirmation_response(message)
        if review_confirmation:
            self._log_answer(message, review_confirmation)
            return review_confirmation
        fissure_confirmation = self._try_fissure_alert_confirmation_response(message)
        if fissure_confirmation:
            self._log_answer(message, fissure_confirmation)
            return fissure_confirmation
        goal_status_confirmation = self._try_goal_status_confirmation_response(message)
        if goal_status_confirmation:
            self._log_answer(message, goal_status_confirmation)
            return goal_status_confirmation
        goal_confirmation = self._try_goal_confirmation_response(message)
        if goal_confirmation:
            self._log_answer(message, goal_confirmation)
            return goal_confirmation
        goal_status_intent = self._try_goal_status_intent(message)
        if goal_status_intent:
            self._log_answer(message, goal_status_intent)
            return goal_status_intent
        review_intent = self._try_review_done_intent(message)
        if review_intent:
            self._log_answer(message, review_intent)
            return review_intent
        fissure_intent = self._try_fissure_alert_intent(message)
        if fissure_intent:
            self._log_answer(message, fissure_intent)
            return fissure_intent
        opportunity_control = self._try_opportunity_control(message)
        if opportunity_control:
            self._log_answer(message, opportunity_control)
            return opportunity_control
        if is_watchlist_command(message):
            return self.scan_watchlist()
        cycle_result = self._try_cycle_intent(message)
        if cycle_result:
            self.session.add_exchange(message, cycle_result)
            self._log_answer(message, cycle_result)
            return cycle_result
        price_alert_intent = self._try_price_alert_intent(message)
        if price_alert_intent:
            self._log_answer(message, price_alert_intent)
            return price_alert_intent
        favorite_intent = self._try_favorite_intent(message)
        if favorite_intent:
            self._log_answer(message, favorite_intent)
            return favorite_intent
        preference_intent = self._try_preference_intent(message)
        if preference_intent:
            self._log_answer(message, preference_intent)
            return preference_intent
        self._remember_common_question(message)
        baro_followup = self._try_baro_order_followup(message)
        baro_followup_display = self._tool_result_display_text(baro_followup)
        if baro_followup_display:
            self.session.add_exchange(message, self._tool_result_history_text(baro_followup))
            self._log_answer(message, baro_followup_display)
            return baro_followup_display
        baro_answer = self._try_baro_recommendation(message)
        if baro_answer:
            self.session.add_exchange(message, baro_answer)
            self._log_answer(message, baro_answer)
            return baro_answer
        # 紫卡查询：优先确定性解析，避免 LLM 路由误判
        if _looks_like_riven_query(message):
            riven_result = self._try_deterministic_riven(message)
            riven_display = self._tool_result_display_text(riven_result)
            if riven_display:
                self.session.add_exchange(message, self._tool_result_history_text(riven_result))
                self._log_answer(message, riven_display)
                return riven_display
        # 紫卡追问：基于上一次查询过滤（在线/便宜）
        riven_followup = self._try_riven_followup(message)
        riven_followup_display = self._tool_result_display_text(riven_followup)
        if riven_followup_display:
            self.session.add_exchange(message, self._tool_result_history_text(riven_followup))
            self._log_answer(message, riven_followup_display)
            return riven_followup_display
        # Prime 重生 / Vault 查询：直接走事件格式化，避免物品匹配误触发
        if _is_prime_resurgence_query(message):
            result = self._handle_vault_command()
            self.session.add_exchange(message, result)
            self._log_answer(message, result)
            return result
        prime_direct = self._try_direct_market_intent(message)
        if prime_direct:
            self.session.add_exchange(message, prime_direct)
            self._log_answer(message, prime_direct)
            return prime_direct
        planning_answer = self._try_planning_intent(message)
        if planning_answer:
            self.session.add_exchange(message, planning_answer)
            self._log_answer(message, planning_answer)
            return planning_answer
        direct_bilibili = self._try_direct_bilibili_recommendations(message)
        if direct_bilibili:
            self.session.add_exchange(message, direct_bilibili)
            self._log_answer(message, direct_bilibili)
            return direct_bilibili
        relic_value_intent = _is_relic_value_intent(message)
        relic_farming_intent = _is_relic_farming_intent(message)
        if relic_value_intent or relic_farming_intent:
            relic_tools = set()
            if relic_value_intent:
                relic_tools.add("relic_value")
            if relic_farming_intent:
                relic_tools.add("farming_route")
            routed = self._try_router_result(message, candidate_tools=relic_tools)
            routed_display = self._tool_result_display_text(routed)
            if routed_display:
                self.session.add_exchange(message, self._tool_result_history_text(routed))
                self._log_answer(message, routed_display)
                return routed_display
            if relic_value_intent:
                fallback = "暂时无法计算这个遗物的收益，请提供具体遗物名，例如 Lith B1。"
            else:
                fallback = "暂时无法规划这个遗物/部件的刷取路线，请提供具体遗物名或部件名。"
            self.session.add_exchange(message, fallback)
            self._log_answer(message, fallback)
            return fallback
        # 事件类/交易工具类查询直接走路由器，避免物品匹配误触发交易流程
        if _is_event_query(message) or _is_trading_tool_query(message):
            if _is_event_query(message) and not _is_specific_event_list_query(message):
                result = self._handle_limited_event_query(message)
                self.session.add_exchange(message, result)
                self._log_answer(message, result)
                return result
            if _is_specific_event_list_query(message):
                routed = self._handle_specific_event_query(message)
            else:
                routed = self._try_router_result(message)
            routed_display = self._tool_result_display_text(routed)
            if routed_display:
                self.session.add_exchange(message, self._tool_result_history_text(routed))
                self._log_answer(message, routed_display)
                return routed_display
            # 路由失败时不要 fallthrough 到物品匹配，返回通用提示
            if _is_trading_tool_query(message):
                fallback = "交易工具暂时无法使用，请稍后重试。你也可以直接输入物品名称查询价格。"
                self._log_answer(message, fallback)
                return fallback
            if _is_event_query(message):
                fallback = self._handle_limited_event_query(message)
                self._log_answer(message, fallback)
                return fallback
        warframe_answer = price_warframe_query(message, self.warframe_items, self.order_fetcher)
        if warframe_answer:
            self.session.add_exchange(message, warframe_answer)
            self._log_answer(message, warframe_answer)
            return warframe_answer
        if is_followup(message) and self.session.has_context():
            contexts = self._contexts_for_items(self.session.last_item_ids)
        else:
            contexts = self._contexts_for_message(message)
        if not contexts:
            routed = self._try_router_result(message)
            routed_display = self._tool_result_display_text(routed)
            if routed_display:
                routed_display = self._append_bilibili_recommendations(message, routed_display)
                self.session.add_exchange(message, self._tool_result_history_text(routed))
                self._log_answer(message, routed_display)
                return routed_display
            bilibili_recommendations = self._build_bilibili_recommendations(message)
            if bilibili_recommendations:
                self.session.add_exchange(message, bilibili_recommendations)
                self._log_answer(message, bilibili_recommendations)
                return bilibili_recommendations
            result = "没有找到匹配的物品，请输入 warframe.market 的 item_id，例如：充沛 / arcane_energize"
            self._log_answer(message, result)
            return result
        self.session.update([ctx.item_id for ctx in contexts])
        # 自动记录已完成的交易
        auto_trade_note = self._auto_record_trade(message, contexts)
        deterministic_answer = _deterministic_trade_intent_answer(message, contexts)
        if deterministic_answer:
            if auto_trade_note:
                deterministic_answer += "\n\n" + auto_trade_note
            self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
            self._log_answer(message, deterministic_answer, contexts)
            return deterministic_answer
        if _classify_chat_mode(message).mode == "market_analysis" and (
            self.model_call is call_ollama_chat or _message_has_guide_video_intent(message)
        ):
            result = fallback_answer(message, contexts)
            if auto_trade_note:
                result += "\n\n" + auto_trade_note
            self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
            self._log_answer(message, result, contexts)
            return result
        current_ids = [ctx.item_id for ctx in contexts]
        market_ctx = build_system_context(self.knowledge, self.event_tracker, memory=self.memory, game_data=self.game_data, current_item_ids=current_ids)
        memory_recall_ctx = self._build_memory_recall_context(message, current_ids)
        if memory_recall_ctx:
            market_ctx = f"{market_ctx}\n\n{memory_recall_ctx}" if market_ctx else memory_recall_ctx
        prompt_messages = build_chat_messages(message, contexts, self.memory, self.session.to_messages(current_query=message), market_ctx or None)
        try:
            answer = self._call_llm_messages(prompt_messages).strip()
            if answer:
                checked = _self_check(answer, contexts)
                if checked:
                    answer = checked
                answer = self._append_bilibili_recommendations(message, answer)
                self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
                self._log_answer(message, answer, contexts)
                return answer
        except Exception as exc:
            logger.debug("LLM 调用失败，使用回退: %s", exc)
            result = self._append_bilibili_recommendations(message, fallback_answer(message, contexts, llm_failed=True))
            self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
            self._log_answer(message, result, contexts)
            return result
        result = self._append_bilibili_recommendations(message, fallback_answer(message, contexts))
        self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
        self._log_answer(message, result, contexts)
        return result

    def _try_direct_bilibili_recommendations(self, message: str) -> str | None:
        if _classify_chat_mode(message).mode != "guide_video":
            return None
        lowered = message.lower()
        explicit_video = any(token in lowered for token in ("b站", "bilibili", "视频", "教程"))
        guide_intent = is_bilibili_recommendation_intent(message)
        if not (explicit_video or guide_intent):
            return None
        recommendations = self._build_bilibili_recommendations(message, empty_message=explicit_video)
        if recommendations:
            return recommendations
        if guide_intent:
            label = self._known_guide_item_label(message)
            if label:
                return f"暂未收录 {label} 的配卡/攻略 B 站视频。"
        return None

    def _try_planning_intent(self, message: str) -> str | None:
        if _classify_chat_mode(message).mode != "planning":
            return None
        hint = self._planning_goal_hint(message)
        pending = self._build_pending_goal_confirmation(hint)
        self._pending_goal_confirmation = pending
        lines = [
            "我把这条识别为计划/目标请求，不会直接下单、不会生成购买私聊。",
            "",
            "计划草案:",
            "1. 先确认预算、风险和最低 ROI；可用 /profile 查看当前偏好。",
            "2. 用投资/倒卖扫描找候选，只看利润、ROI、流动性和历史复盘表现。",
            "3. 每天复查价格和在线订单，达到目标价再手动执行交易。",
            "4. 完成后用 /review done OPID 实际利润 good|bad 记录结果。",
            "",
        ]
        if pending:
            lines.extend([
                "我也可以把它创建成长期跟踪目标。当前理解为:",
                f"- {pending.summary}",
                "是否创建？回复“确认创建”即可保存；回复“取消”则不保存。",
                "",
            ])
        else:
            lines.extend([
                "如果要创建长期跟踪目标，请补充目标金额、周期或预算后确认。",
                "",
            ])
        lines.append(f"需要跟踪目标时可以使用: /goal set {hint}")
        return "\n".join(lines)

    def _build_pending_goal_confirmation(self, description: str) -> PendingGoalConfirmation | None:
        goal_type, criteria, summary = self._goal_payload_from_description(description)
        if not self._goal_criteria_has_user_signal(criteria):
            return None
        return PendingGoalConfirmation(
            description=description,
            goal_type=goal_type,
            criteria=criteria,
            summary=summary,
        )

    def _try_agent_plan_confirmation_response(self, message: str) -> str | None:
        compact = re.sub(r"\s+", "", message.strip().lower())
        if not compact:
            return None
        if self._is_agent_plan_confirmation_cancel(compact):
            if self._pending_agent_plan_confirmation:
                self._pending_agent_plan_confirmation = None
                return "已取消待确认的计划执行。"
            return "当前没有待取消的计划确认。"
        if not self._is_agent_plan_confirmation_accept(compact):
            return None
        pending = self._pending_agent_plan_confirmation
        if not pending:
            return "当前没有待确认的计划执行。请先让我生成一个被软拦截的只读计划。"
        self._pending_agent_plan_confirmation = None
        candidate_tools = set(pending.candidate_tools) if pending.candidate_tools else None
        result = self._try_react_loop(
            pending.original_message,
            candidate_tools=candidate_tools,
            plan_confirmation_token=pending.confirmation_token,
        )
        if result:
            return result
        return "计划确认后仍无法执行；我没有执行任何步骤。请重新发起计划。"

    @staticmethod
    def _is_agent_plan_confirmation_accept(compact: str) -> bool:
        return compact in {"确认执行", "执行计划", "确认计划", "继续执行", "确认运行"}

    @staticmethod
    def _is_agent_plan_confirmation_cancel(compact: str) -> bool:
        return compact in {"取消执行", "取消计划", "不执行", "不执行计划", "放弃执行"}

    def _capture_agent_plan_confirmation(
        self,
        original_message: str,
        candidate_tools: set[str] | None,
        result: str,
        trace,
    ) -> str:
        token_match = re.search(r"confirmation_token=(plan_confirm_[0-9a-f]+)", result)
        reason_match = re.search(r"confirmable_reason=([a-z_]+)", result)
        if not token_match or not reason_match or reason_match.group(1) != "missing_verification":
            return result
        plan = getattr(trace, "plan", None)
        review = getattr(plan, "review", None) if plan is not None else None
        if getattr(review, "blocked_reason", "") != "missing_verification":
            return result
        self._pending_agent_plan_confirmation = PendingAgentPlanConfirmation(
            original_message=original_message,
            confirmation_token=token_match.group(1),
            blocked_reason="missing_verification",
            candidate_tools=tuple(sorted(candidate_tools)) if candidate_tools else None,
        )
        return self._format_agent_plan_confirmation_prompt(plan)

    @staticmethod
    def _format_agent_plan_confirmation_prompt(plan) -> str:
        goal = getattr(plan, "goal", "") or "未命名计划"
        steps = getattr(plan, "steps", []) or []
        tool_names = [getattr(step, "tool_name", "") for step in steps if getattr(step, "tool_name", "")]
        lines = [
            "计划已暂停，原因是缺少步骤验证说明。",
            f"目标: {goal}",
        ]
        if tool_names:
            lines.append(f"只读步骤: {', '.join(tool_names[:6])}")
        lines.extend([
            "这类计划只允许在你确认后重新审查并执行。",
            "回复“确认执行”继续；回复“取消执行”不执行。",
        ])
        return "\n".join(lines)

    @staticmethod
    def _goal_payload_from_description(description: str) -> tuple[str, dict, str]:
        from .goals import format_goal_criteria_summary, parse_goal_description_criteria

        criteria = parse_goal_description_criteria(description)
        goal_type = "earn_platinum" if criteria.get("target_amount") is not None else "maximize_profit"
        summary = format_goal_criteria_summary(criteria)
        return goal_type, criteria, summary

    @staticmethod
    def _goal_criteria_has_user_signal(criteria: dict) -> bool:
        defaults = {"budget": 500, "min_roi": 10}
        return any(criteria.get(key) != value for key, value in defaults.items()) or any(
            key in criteria for key in ("target_profit", "target_amount", "timeframe_days", "risk")
        )

    def _try_goal_confirmation_response(self, message: str) -> str | None:
        compact = re.sub(r"\s+", "", message.strip().lower())
        if not compact:
            return None
        if self._is_goal_confirmation_cancel(compact):
            if self._pending_goal_confirmation:
                self._pending_goal_confirmation = None
                return "已取消创建目标。"
            return "当前没有待取消的目标确认。"
        if self._is_goal_confirmation_accept(compact):
            pending = self._pending_goal_confirmation
            if not pending:
                return "当前没有待确认的目标。你可以先说“帮我制定一周赚500p的计划”。"
            self._pending_goal_confirmation = None
            return self._create_goal_from_description(pending.description)
        return None

    def _try_review_done_confirmation_response(self, message: str) -> str | None:
        compact = re.sub(r"\s+", "", message.strip().lower())
        if not compact:
            return None
        pending = self._pending_review_done_confirmation
        if not pending:
            return None
        if self._is_goal_confirmation_cancel(compact):
            self._pending_review_done_confirmation = None
            return "已取消机会复盘记录。"
        if compact in {"确认", "确认复盘", "确认记录", "记录", "复盘", "可以", "好的", "好", "yes", "y", "ok", "okay"}:
            self._pending_review_done_confirmation = None
            return self._handle_review_record_command([
                pending.lookup_id,
                str(pending.actual_profit),
                pending.feedback,
            ])
        return None

    def _try_review_done_intent(self, message: str) -> str | None:
        intent = _parse_natural_language_review_done(message)
        if not intent:
            return None
        if not self.trading_memory_db:
            return "暂无机会复盘数据。"
        detail = self.opportunity_lookup_store.get(intent.lookup_id)
        if detail is None:
            return opportunity_not_found_message(intent.lookup_id)
        safe_summary = self._opportunity_review_safe_summary(detail)
        item_id = str(safe_summary.get("item_id") or detail.item_id or "")
        expected_profit = self._safe_int(safe_summary.get("profit", 0))
        pending = PendingReviewDoneConfirmation(
            lookup_id=intent.lookup_id,
            actual_profit=intent.actual_profit,
            feedback=intent.feedback,
            item_id=item_id,
            expected_profit=expected_profit,
        )
        self._pending_review_done_confirmation = pending
        return self._format_review_done_confirmation_prompt(pending)

    @staticmethod
    def _format_review_done_confirmation_prompt(pending: PendingReviewDoneConfirmation) -> str:
        return "\n".join([
            "我理解为要记录一次机会复盘：",
            f"机会 ID: {pending.lookup_id}",
            f"物品: {pending.item_id}",
            f"预期利润: {pending.expected_profit}p",
            f"实际利润: {pending.actual_profit}p",
            f"反馈: {pending.feedback}",
            "回复“确认复盘”写入；回复“取消”不记录。",
        ])

    def _try_fissure_alert_confirmation_response(self, message: str) -> str | None:
        compact = re.sub(r"\s+", "", message.strip().lower())
        if not compact:
            return None
        pending = self._pending_fissure_alert_confirmation
        if not pending:
            return None
        if self._is_goal_confirmation_cancel(compact):
            self._pending_fissure_alert_confirmation = None
            return "已取消裂缝提醒变更。"
        if self._is_fissure_alert_confirmation_accept(compact, pending.action):
            self._pending_fissure_alert_confirmation = None
            if pending.action == "remove":
                if pending.index is None:
                    return "缺少要取消的裂缝订阅序号。"
                return self._remove_fissure_alert([str(pending.index)])
            return self._add_fissure_alert(pending.tokens)
        return None

    @staticmethod
    def _is_fissure_alert_confirmation_accept(compact: str, action: str) -> bool:
        generic = {"确认", "可以", "好的", "好", "同意", "yes", "y", "ok", "okay"}
        if compact in generic:
            return True
        if action == "add":
            return compact in {"确认订阅", "订阅", "保存订阅", "创建订阅"}
        if action == "remove":
            return compact in {"确认取消", "取消订阅", "删除", "移除", "确认删除", "确认移除"}
        return False

    def _try_fissure_alert_intent(self, message: str) -> str | None:
        intent = _parse_natural_language_fissure_alert(message)
        if not intent:
            return None
        if intent.action == "remove":
            index = intent.index or 0
            if index < 1 or index > len(self.memory.fissure_alerts):
                return f"未找到第 {index} 条裂缝订阅，当前共有 {len(self.memory.fissure_alerts)} 条。"
            alert = self.memory.fissure_alerts[index - 1]
            pending = PendingFissureAlertConfirmation(
                action="remove",
                tokens=[],
                index=index,
                note=alert.note or "全部裂缝",
            )
            self._pending_fissure_alert_confirmation = pending
            return self._format_fissure_alert_remove_confirmation_prompt(pending)

        pending = PendingFissureAlertConfirmation(
            action="add",
            tokens=list(intent.tokens),
            note=intent.note or "全部裂缝",
        )
        self._pending_fissure_alert_confirmation = pending
        return self._format_fissure_alert_add_confirmation_prompt(pending)

    @staticmethod
    def _format_fissure_alert_add_confirmation_prompt(pending: PendingFissureAlertConfirmation) -> str:
        return "\n".join([
            "我理解为要订阅裂缝提醒：",
            f"过滤条件: {pending.note or '全部裂缝'}",
            "回复“确认订阅”写入；回复“取消”不更改。",
        ])

    @staticmethod
    def _format_fissure_alert_remove_confirmation_prompt(pending: PendingFissureAlertConfirmation) -> str:
        return "\n".join([
            "我理解为要取消裂缝提醒：",
            f"订阅序号: {pending.index}",
            f"当前条件: {pending.note or '全部裂缝'}",
            "回复“确认取消”移除；回复“取消”不更改。",
        ])

    def _try_goal_status_confirmation_response(self, message: str) -> str | None:
        compact = re.sub(r"\s+", "", message.strip().lower())
        if not compact:
            return None
        pending = self._pending_goal_status_confirmation
        if not pending:
            return None
        if self._is_goal_confirmation_cancel(compact):
            self._pending_goal_status_confirmation = None
            return "已取消目标状态更新。"
        if self._is_goal_status_confirmation_accept(compact, pending.action):
            self._pending_goal_status_confirmation = None
            return self._apply_goal_status_update(pending.goal_id, pending.action)
        return None

    @staticmethod
    def _is_goal_status_confirmation_accept(compact: str, action: str) -> bool:
        generic = {"确认", "可以", "好的", "好", "同意", "yes", "y", "ok", "okay"}
        if compact in generic:
            return True
        if action == "complete":
            return compact in {"确认完成", "完成", "完成目标", "标记完成"}
        if action == "drop":
            return compact in {"确认放弃", "放弃", "放弃目标"}
        return False

    def _try_goal_status_intent(self, message: str) -> str | None:
        intent = _parse_natural_language_goal_status(message)
        if not intent:
            return None
        from .goals import GoalTracker

        tracker = GoalTracker()
        goal, error = self._resolve_goal_status_target(intent, tracker)
        if error:
            return error
        if goal is None:
            return None
        target_status = "achieved" if intent.action == "complete" else "abandoned"
        pending = PendingGoalStatusConfirmation(
            action=intent.action,
            goal_id=goal.goal_id,
            description=goal.description,
            target_status=target_status,
        )
        self._pending_goal_status_confirmation = pending
        return self._format_goal_status_confirmation_prompt(pending)

    @staticmethod
    def _resolve_goal_status_target(intent: GoalStatusIntent, tracker):
        active_goals = tracker.get_active_goals()
        if not active_goals:
            return None, "当前没有活跃的交易目标。"
        if intent.selector_type == "index":
            index = int(intent.selector) - 1
            if index < 0 or index >= len(active_goals):
                return None, f"未找到第 {intent.selector} 个活跃目标。"
            return active_goals[index], None
        if intent.selector_type == "id":
            matches = [goal for goal in active_goals if goal.goal_id.startswith(intent.selector)]
        else:
            selector = intent.selector.strip()
            matches = [
                goal for goal in active_goals
                if selector in goal.description or goal.description in selector
            ]
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            lines = ["匹配到多个活跃目标，请使用目标 ID 再试："]
            for goal in matches[:5]:
                lines.append(f"- {goal.description} [{goal.goal_id[:6]}]")
            return None, "\n".join(lines)
        return None, f"未找到匹配的活跃目标: {intent.selector}"

    @staticmethod
    def _format_goal_status_confirmation_prompt(pending: PendingGoalStatusConfirmation) -> str:
        action_label = "完成" if pending.action == "complete" else "放弃"
        status_label = "achieved" if pending.action == "complete" else "abandoned"
        return "\n".join([
            f"我理解为要{action_label}目标：{pending.description}",
            f"目标 ID: {pending.goal_id[:6]}",
            f"将变更为: {status_label}",
            f"回复“确认{action_label}”执行；回复“取消”不更改。",
        ])

    def _apply_goal_status_update(self, goal_id: str, action: str) -> str:
        from .goals import GoalTracker

        tracker = GoalTracker()
        matches = [goal for goal in tracker.goals if goal.goal_id == goal_id]
        if not matches:
            return f"未找到 ID 为 {goal_id[:6]} 的目标。"
        goal = matches[0]
        if action == "complete":
            tracker.update_goal_status(goal.goal_id, "achieved")
            review = tracker.generate_review(goal.goal_id)
            return f"目标已标记为完成：\n\n{review}"
        tracker.update_goal_status(goal.goal_id, "abandoned")
        return f"已放弃目标: {goal.description}"

    @staticmethod
    def _is_goal_confirmation_accept(compact: str) -> bool:
        return compact in {
            "确认", "确认创建", "创建", "创建目标", "保存", "保存目标",
            "可以", "好的", "好", "同意", "就这个", "yes", "y", "ok", "okay",
        }

    @staticmethod
    def _is_goal_confirmation_cancel(compact: str) -> bool:
        return compact in {
            "取消", "取消创建", "不创建", "先不创建", "不要创建", "算了", "不用了", "no", "n",
        }

    def _create_goal_from_description(self, description: str) -> str:
        from .goals import GoalTracker, create_goal

        goal_type, criteria, summary = self._goal_payload_from_description(description)
        goal = create_goal(
            goal_type=goal_type,
            description=description,
            target="all",
            criteria=criteria,
        )
        GoalTracker().add_goal(goal)
        lines = [f"已创建目标: {description}", f"目标 ID: {goal.goal_id[:6]}"]
        if summary:
            lines.append(f"已解析: {summary}")
        lines.append("使用 /goal 查看进度")
        return "\n".join(lines)

    @staticmethod
    def _planning_goal_hint(message: str) -> str:
        compact = re.sub(r"\s+", " ", message.strip())
        compact = re.sub(r"(不要直接买|不要下单|顺便给攻略视频|顺便找攻略视频|攻略视频)", "", compact)
        compact = compact.strip(" ，,。")
        return compact[:80] or "一周内赚500p"

    def _known_guide_item_label(self, message: str) -> str | None:
        normalized_message = normalize_lookup_key(message)
        for aliases in (
            getattr(self.resolver, "aliases", {}) or {},
            getattr(self.resolver, "generated_aliases", {}) or {},
        ):
            for alias_key, _item_id in sorted(aliases.items(), key=lambda entry: -len(entry[0])):
                if alias_key and alias_key in normalized_message:
                    return alias_key
        for token in _message_tokens(message):
            try:
                result = self.resolver.resolve(token)
            except (LookupError, ValueError):
                continue
            if result.source in {"alias", "dictionary", "generated_alias"}:
                return result.matched_name or token
        return None

    def _build_bilibili_recommendations(self, message: str, *, empty_message: bool = False) -> str:
        try:
            service = BilibiliRecommendationService(BilibiliRecommendationStore(self.bilibili_recommendations_path))
            matches = service.recommend(message, limit=3)
            return format_bilibili_recommendations(matches, empty_message=empty_message)
        except Exception as exc:
            logger.debug("B 站视频推荐失败: %s", exc)
            return "暂未收录相关 B 站视频。" if empty_message and is_bilibili_recommendation_intent(message) else ""

    def _append_bilibili_recommendations(self, message: str, answer: str) -> str:
        if _classify_chat_mode(message).mode != "guide_video":
            return answer
        recommendations = self._build_bilibili_recommendations(message)
        if not recommendations:
            return answer
        return f"{answer}\n\n{recommendations}" if answer else recommendations

    def _log_answer(self, message: str, reply: str, contexts=None) -> None:
        tool_calls = self._consume_tool_execution_metadata()
        self._record_user_query_memory(message, contexts, tool_calls)
        try:
            from .conversation_log import log_conversation, ConversationEntry
            log_conversation(ConversationEntry(
                user_message=message,
                assistant_reply=reply,
                tool_calls=tool_calls or None,
                contexts=[ctx.item_id for ctx in contexts] if contexts else None,
            ))
        except Exception as exc:
            logger.debug("对话日志记录失败: %s", exc)

    def _build_memory_recall_context(self, message: str, item_ids: list[str]) -> str:
        if not self.trading_memory_db or not item_ids:
            return ""
        try:
            service = MemoryRecallService(self.trading_memory_db)
            result = service.recall(
                message,
                item_name=item_ids[0],
                intent=self._infer_user_query_memory_intent(message, []),
                limit=3,
            )
            return service.format_for_model(result, max_items=3)
        except Exception as exc:
            logger.debug("长期交易记忆召回失败: %s", exc)
            return ""

    def _record_user_query_memory(self, message: str, contexts=None, tool_calls: list[dict] | None = None) -> None:
        if not self.trading_memory_db:
            return
        if message.strip().startswith("/"):
            return
        context_item_ids, tool_item_ids, item_source = self._infer_user_query_memory_item_ids(contexts, tool_calls or [])
        safe_tool_names = self._safe_tool_names_from_tool_calls(tool_calls or [])
        intent = self._infer_user_query_memory_intent(message, safe_tool_names)
        has_context_signal = bool(context_item_ids or tool_item_ids)
        has_tool_signal = bool(safe_tool_names and safe_tool_names != ["general_chat"])
        has_trade_signal = intent not in {"unknown", "price_check"}
        if not (has_context_signal or has_tool_signal or has_trade_signal):
            return
        item_ids = context_item_ids or tool_item_ids
        try:
            self.trading_memory_db.record_user_query_summary(
                intent=intent,
                item_name=item_ids[0] if item_ids else "",
                metadata={
                    "context_item_ids": item_ids,
                    "context_count": len(context_item_ids),
                    "tool_names": safe_tool_names,
                    "tool_count": len(tool_calls or []),
                    "tool_ok_count": sum(1 for call in (tool_calls or []) if call.get("ok") is True),
                    "item_source": item_source,
                },
            )
        except Exception as exc:
            logger.debug("长期交易记忆用户查询摘要写入失败: %s", exc)

    def _infer_user_query_memory_intent(self, message: str, tool_names: list[str]) -> str:
        tool_intents = {
            "query_price": "price_check",
            "price_trend": "price_trend",
            "query_set": "price_check",
            "query_missing_parts": "trading_tool",
            "scan_favorites": "watchlist_scan",
            "set_alert": "alert_create",
            "mod_flipper": "mod_flip_scan",
            "set_profit": "set_profit_scan",
            "investment_advisor": "investment_advice",
            "query_events": "event_query",
            "riven_search": "riven_search",
        }
        for tool_name in tool_names:
            if tool_name in tool_intents:
                return tool_intents[tool_name]
        completed = detect_completed_trade(message)
        if completed:
            return "completed_trade_buy" if completed[0] == "buy" else "completed_trade_sell"
        if detect_compare_query(message):
            return "price_compare"
        if detect_trend_query(message):
            return "price_trend"
        trade_intent = detect_trade_intent(message)
        if trade_intent == "buy":
            return "trade_buy"
        if trade_intent == "sell":
            return "trade_sell"
        if trade_intent == "spread":
            return "spread_check"
        if trade_intent == "overview":
            return "price_check"
        if _looks_like_riven_query(message):
            return "riven_search"
        if _is_baro_recommendation_query(message):
            return "baro_recommendation"
        if _is_event_query(message):
            return "event_query"
        return "unknown"

    def _infer_user_query_memory_item_ids(self, contexts=None, tool_calls: list[dict] | None = None) -> tuple[list[str], list[str], str]:
        context_item_ids = []
        for ctx in contexts or []:
            item_id = getattr(ctx, "item_id", "")
            if item_id and item_id not in context_item_ids:
                context_item_ids.append(item_id)
            if len(context_item_ids) >= 3:
                break
        tool_item_ids = []
        for call in tool_calls or []:
            item_id = self._resolve_user_query_memory_item_from_tool_args(call.get("args_summary"))
            if item_id and item_id not in tool_item_ids:
                tool_item_ids.append(item_id)
            if len(tool_item_ids) >= 3:
                break
        if context_item_ids and tool_item_ids:
            item_source = "mixed" if any(item_id not in context_item_ids for item_id in tool_item_ids) else "contexts"
        elif context_item_ids:
            item_source = "contexts"
        elif tool_item_ids:
            item_source = "tool_args_resolved"
        else:
            item_source = "none"
        return context_item_ids, tool_item_ids, item_source

    def _resolve_user_query_memory_item_from_tool_args(self, args_summary) -> str:
        if not isinstance(args_summary, dict):
            return ""
        for key in ("item_id", "market_id"):
            value = args_summary.get(key)
            if not isinstance(value, str) or value == "[REDACTED]":
                continue
            item_id = self._safe_memory_identifier(value)
            if item_id:
                return item_id
        for key in ("item_name", "query", "warframe_name", "weapon"):
            value = args_summary.get(key)
            if not isinstance(value, str) or value == "[REDACTED]":
                continue
            item_id = self._resolve_safe_memory_item_id(value)
            if item_id:
                return item_id
        return ""

    def _resolve_safe_memory_item_id(self, value: str) -> str:
        try:
            resolved = self.resolver.resolve(value).item_id
        except (LookupError, ValueError):
            return ""
        return self._safe_memory_identifier(resolved)

    def _safe_memory_identifier(self, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized and all(ch.isascii() and (ch.isalnum() or ch == "_") for ch in normalized):
            return normalized
        return ""

    def _safe_tool_names_from_tool_calls(self, tool_calls: list[dict]) -> list[str]:
        allowed = {
            "query_price", "price_trend", "query_set", "query_missing_parts", "scan_favorites",
            "set_alert", "mod_flipper", "set_profit", "investment_advisor", "query_events", "riven_search",
        }
        names = []
        for call in tool_calls:
            name = call.get("tool_name")
            if name in allowed and name not in names:
                names.append(name)
            if len(names) >= 5:
                break
        return names

    def _consume_tool_execution_metadata(self) -> list[dict]:
        records = [_tool_metadata_to_dict(meta) for meta in self.tool_execution_metadata]
        self.tool_execution_metadata = []
        return records

    async def answer_stream(self, message: str) -> AsyncIterator[str]:
        """流式版本的 answer，逐 token yield。对于不需要 LLM 的路径，一次性 yield 全文。"""
        self._reload_memory()
        stripped = message.strip()
        if is_opportunity_lookup_id(stripped):
            result = self._handle_opportunity_lookup([stripped])
            self._log_answer(message, result)
            yield result
            return
        if stripped.startswith("/"):
            result = self._handle_agent_command(stripped)
            self._log_answer(message, result)
            yield result
            return
        agent_plan_confirmation = self._try_agent_plan_confirmation_response(message)
        if agent_plan_confirmation:
            self._log_answer(message, agent_plan_confirmation)
            yield agent_plan_confirmation
            return
        review_confirmation = self._try_review_done_confirmation_response(message)
        if review_confirmation:
            self._log_answer(message, review_confirmation)
            yield review_confirmation
            return
        fissure_confirmation = self._try_fissure_alert_confirmation_response(message)
        if fissure_confirmation:
            self._log_answer(message, fissure_confirmation)
            yield fissure_confirmation
            return
        goal_status_confirmation = self._try_goal_status_confirmation_response(message)
        if goal_status_confirmation:
            self._log_answer(message, goal_status_confirmation)
            yield goal_status_confirmation
            return
        goal_confirmation = self._try_goal_confirmation_response(message)
        if goal_confirmation:
            self._log_answer(message, goal_confirmation)
            yield goal_confirmation
            return
        goal_status_intent = self._try_goal_status_intent(message)
        if goal_status_intent:
            self._log_answer(message, goal_status_intent)
            yield goal_status_intent
            return
        review_intent = self._try_review_done_intent(message)
        if review_intent:
            self._log_answer(message, review_intent)
            yield review_intent
            return
        fissure_intent = self._try_fissure_alert_intent(message)
        if fissure_intent:
            self._log_answer(message, fissure_intent)
            yield fissure_intent
            return
        opportunity_control = self._try_opportunity_control(message)
        if opportunity_control:
            self._log_answer(message, opportunity_control)
            yield opportunity_control
            return
        if is_watchlist_command(message):
            result = self.scan_watchlist()
            self._log_answer(message, result)
            yield result
            return
        cycle_result = self._try_cycle_intent(message)
        if cycle_result:
            self.session.add_exchange(message, cycle_result)
            self._log_answer(message, cycle_result)
            yield cycle_result
            return
        price_alert_intent = self._try_price_alert_intent(message)
        if price_alert_intent:
            self._log_answer(message, price_alert_intent)
            yield price_alert_intent
            return
        favorite_intent = self._try_favorite_intent(message)
        if favorite_intent:
            self._log_answer(message, favorite_intent)
            yield favorite_intent
            return
        preference_intent = self._try_preference_intent(message)
        if preference_intent:
            self._log_answer(message, preference_intent)
            yield preference_intent
            return
        self._remember_common_question(message)
        baro_followup = self._try_baro_order_followup(message)
        baro_followup_display = self._tool_result_display_text(baro_followup)
        if baro_followup_display:
            self.session.add_exchange(message, self._tool_result_history_text(baro_followup))
            self._log_answer(message, baro_followup_display)
            yield baro_followup_display
            return
        baro_answer = self._try_baro_recommendation(message)
        if baro_answer:
            self.session.add_exchange(message, baro_answer)
            self._log_answer(message, baro_answer)
            yield baro_answer
            return
        # 紫卡查询：优先确定性解析，避免 LLM 路由误判
        if _looks_like_riven_query(message):
            riven_result = self._try_deterministic_riven(message)
            riven_display = self._tool_result_display_text(riven_result)
            if riven_display:
                self.session.add_exchange(message, self._tool_result_history_text(riven_result))
                self._log_answer(message, riven_display)
                yield riven_display
                return
        # 紫卡追问：基于上一次查询过滤（在线/便宜）
        riven_followup = self._try_riven_followup(message)
        riven_followup_display = self._tool_result_display_text(riven_followup)
        if riven_followup_display:
            self.session.add_exchange(message, self._tool_result_history_text(riven_followup))
            self._log_answer(message, riven_followup_display)
            yield riven_followup_display
            return
        # Prime 重生 / Vault 查询：直接走事件格式化，避免物品匹配误触发
        if _is_prime_resurgence_query(message):
            result = self._handle_vault_command()
            self.session.add_exchange(message, result)
            self._log_answer(message, result)
            yield result
            return
        prime_direct = self._try_direct_market_intent(message)
        if prime_direct:
            self.session.add_exchange(message, prime_direct)
            self._log_answer(message, prime_direct)
            yield prime_direct
            return
        planning_answer = self._try_planning_intent(message)
        if planning_answer:
            self.session.add_exchange(message, planning_answer)
            self._log_answer(message, planning_answer)
            yield planning_answer
            return
        direct_bilibili = self._try_direct_bilibili_recommendations(message)
        if direct_bilibili:
            self.session.add_exchange(message, direct_bilibili)
            self._log_answer(message, direct_bilibili)
            yield direct_bilibili
            return
        relic_value_intent = _is_relic_value_intent(message)
        relic_farming_intent = _is_relic_farming_intent(message)
        if relic_value_intent or relic_farming_intent:
            relic_tools = set()
            if relic_value_intent:
                relic_tools.add("relic_value")
            if relic_farming_intent:
                relic_tools.add("farming_route")
            routed = self._try_router_result(message, candidate_tools=relic_tools)
            routed_display = self._tool_result_display_text(routed)
            if routed_display:
                self.session.add_exchange(message, self._tool_result_history_text(routed))
                self._log_answer(message, routed_display)
                yield routed_display
                return
            if relic_value_intent:
                fallback = "暂时无法计算这个遗物的收益，请提供具体遗物名，例如 Lith B1。"
            else:
                fallback = "暂时无法规划这个遗物/部件的刷取路线，请提供具体遗物名或部件名。"
            self.session.add_exchange(message, fallback)
            self._log_answer(message, fallback)
            yield fallback
            return
        # 事件类/交易工具类查询直接走路由器，避免物品匹配误触发交易流程
        if _is_event_query(message) or _is_trading_tool_query(message):
            if _is_event_query(message) and not _is_specific_event_list_query(message):
                result = self._handle_limited_event_query(message)
                self.session.add_exchange(message, result)
                self._log_answer(message, result)
                yield result
                return
            if _is_specific_event_list_query(message):
                routed = self._handle_specific_event_query(message)
            else:
                routed = self._try_router_result(message)
            routed_display = self._tool_result_display_text(routed)
            if routed_display:
                self.session.add_exchange(message, self._tool_result_history_text(routed))
                self._log_answer(message, routed_display)
                yield routed_display
                return
            if _is_trading_tool_query(message):
                fallback = "交易工具暂时无法使用，请稍后重试。你也可以直接输入物品名称查询价格。"
                self._log_answer(message, fallback)
                yield fallback
                return
            if _is_event_query(message):
                result = self._handle_limited_event_query(message)
                self.session.add_exchange(message, result)
                self._log_answer(message, result)
                yield result
                return
        warframe_answer = price_warframe_query(message, self.warframe_items, self.order_fetcher)
        if warframe_answer:
            self.session.add_exchange(message, warframe_answer)
            self._log_answer(message, warframe_answer)
            yield warframe_answer
            return
        if is_followup(message) and self.session.has_context():
            contexts = self._contexts_for_items(self.session.last_item_ids)
        else:
            contexts = self._contexts_for_message(message)
        if not contexts:
            routed = self._try_router_result(message)
            routed_display = self._tool_result_display_text(routed)
            if routed_display:
                routed_display = self._append_bilibili_recommendations(message, routed_display)
                self.session.add_exchange(message, self._tool_result_history_text(routed))
                self._log_answer(message, routed_display)
                yield routed_display
                return
            bilibili_recommendations = self._build_bilibili_recommendations(message)
            if bilibili_recommendations:
                self.session.add_exchange(message, bilibili_recommendations)
                self._log_answer(message, bilibili_recommendations)
                yield bilibili_recommendations
                return
            result = "没有找到匹配的物品，请输入 warframe.market 的 item_id，例如：充沛 / arcane_energize"
            self._log_answer(message, result)
            yield result
            return
        self.session.update([ctx.item_id for ctx in contexts])
        # 自动记录已完成的交易
        self._auto_record_trade(message, contexts)
        deterministic_answer = _deterministic_trade_intent_answer(message, contexts)
        if deterministic_answer:
            self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
            self._log_answer(message, deterministic_answer, contexts)
            yield deterministic_answer
            return
        if _classify_chat_mode(message).mode == "market_analysis":
            result = fallback_answer(message, contexts)
            self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
            self._log_answer(message, result, contexts)
            yield result
            return
        current_ids = [ctx.item_id for ctx in contexts]
        market_ctx = build_system_context(self.knowledge, self.event_tracker, memory=self.memory, game_data=self.game_data, current_item_ids=current_ids)
        memory_recall_ctx = self._build_memory_recall_context(message, current_ids)
        if memory_recall_ctx:
            market_ctx = f"{market_ctx}\n\n{memory_recall_ctx}" if market_ctx else memory_recall_ctx
        prompt_messages = build_chat_messages(message, contexts, self.memory, self.session.to_messages(current_query=message), market_ctx or None)
        # 流式调用 LLM
        full_reply = []
        try:
            from .llm import stream_chat_model
            async for token in stream_chat_model(prompt_messages):
                full_reply.append(token)
                yield token
        except Exception as exc:
            logger.debug("流式 LLM 失败，使用回退: %s", exc)
            result = self._append_bilibili_recommendations(message, fallback_answer(message, contexts, llm_failed=True))
            self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
            self._log_answer(message, result, contexts)
            yield result
            return
        reply_text = "".join(full_reply).strip()
        if reply_text:
            checked = _self_check(reply_text, contexts)
            if checked:
                reply_text = checked
            recommendations = self._build_bilibili_recommendations(message)
            if recommendations:
                yield "\n\n" + recommendations
                reply_text = f"{reply_text}\n\n{recommendations}"
            self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
            self._log_answer(message, reply_text, contexts)
        else:
            result = self._append_bilibili_recommendations(message, fallback_answer(message, contexts))
            self.session.add_exchange(message, safe_query_price_context_from_contexts(contexts))
            self._log_answer(message, result, contexts)
            yield result

    def scan_watchlist(self) -> str:
        watchlist = self.watchlist if self.watchlist is not None else _load_watchlist()
        contexts = []
        for item_ids in watchlist.values():
            for item_id in item_ids[:5]:
                try:
                    contexts.append(build_item_context_result(item_id, self.order_fetcher(item_id)))
                except requests.RequestException as exc:
                    contexts.append(ItemContext(item_id=item_id, text=f"物品: {display_item_name(item_id)}\n查询失败: {exc}"))
        if not contexts:
            return "关注列表为空，请在 data/watchlist.json 中添加关注物品"
        return fallback_answer("关注列表", contexts)

    def _handle_agent_command(self, message: str) -> str:
        tokens = message.split()
        command = tokens[0].lower()
        if command in {"/help", "/帮助"}:
            return self._command_help()
        if command in {"/memory", "/mem", "/记忆"}:
            return self._render_memory_summary()
        if command == "/fav":
            return self._handle_favorite_command(tokens[1:])
        if command == "/alert":
            return self._handle_alert_command(tokens[1:])
        if command == "/pref":
            return self._handle_preference_command(tokens[1:])
        if command in {"/profile", "/画像"}:
            return self._handle_profile_command()
        if command in {"/review", "/复盘"}:
            return self._handle_review_command(tokens[1:])
        if command == "/push":
            return self._handle_push_command(tokens[1:])
        if command == "/scan":
            return self._handle_scan_command()
        if command == "/goal":
            return self._handle_goal_command(tokens[1:])
        if command == "/fissure":
            return self._handle_fissure_command(tokens[1:])
        if command == "/cycle":
            return self._handle_cycle_command(tokens[1:])
        if command == "/trade":
            return self._handle_trade_command(tokens[1:])
        if command == "/relic":
            return self._handle_relic_command(tokens[1:])
        if command == "/strategy":
            return self._handle_strategy_command(tokens[1:])
        if command in {"/vault", "/resurgence", "/重生"}:
            return self._handle_vault_command()
        if command in {"/opp", "/opportunity", "/机会"}:
            return self._handle_opportunity_lookup(tokens[1:])
        return "未知的 Agent 命令，输入 /help 查看可用命令"

    def _command_help(self) -> str:
        return "\n".join([
            "可用命令:",
            "/memory  查看记忆摘要",
            "/scan    扫描收藏和提醒",
            "/fav add 物品名",
            "/fav remove 物品名",
            "/alert add 物品名 below 45",
            "/alert remove 物品名 below 45",
            "/pref platform pc",
            "/pref crossplay on",
            "/pref max 5",
            "/pref risk low | /pref budget 30-150 | /pref categories mod,arcane",
            "/profile           查看个人交易画像",
            "/review [status]   查看机会复盘记录",
            "/review done OPID 实际利润 [good|bad|neutral|ignored]  记录机会复盘",
            "/push opportunity off|on  暂停/开启交易机会推送",
            "/push opportunity filter mod|arcane|all  设置交易机会检测范围",
            "/opp 机会ID       查看推送机会的市场链接和游戏内私聊命令",
            "/goal              查看当前目标",
            "/goal set 目标描述   创建新目标",
            "/goal done ID      标记目标完成",
            "/goal drop ID      放弃目标",
            "/goal review ID    目标复盘",
            "/fissure add 过滤条件  订阅裂缝通知",
            "/fissure remove 序号  取消订阅",
            "/fissure list       查看订阅列表",
            "/cycle status [地点]  查看开放世界/星球状态",
            "/cycle add 地点 状态  订阅状态变化提醒",
            "/cycle list          查看状态订阅",
            "/cycle remove 序号    取消状态订阅",
            "/trade list         查看最近交易记录",
            "/trade stats        交易盈亏统计",
            "/trade add 物品名 buy 80  手动添加交易",
            "/relic 物品名       查询哪些遗物掉落该部件",
            "/relic 遗物名       查询遗物掉落物",
            "/strategy list      查看可用策略",
            "/strategy run 策略名  执行策略扫描",
            "/vault              查看 Vault / Prime 重生状态",
        ])

    def _try_opportunity_control(self, message: str) -> str | None:
        text = re.sub(r"\s+", "", message.strip().lower())
        if not text:
            return None
        if "交易机会" in text or "机会推送" in text:
            if any(word in text for word in ("暂停", "停止", "关闭", "关掉")):
                return self._set_opportunity_push_enabled(False)
            if any(word in text for word in ("开启", "恢复", "打开", "启用")) and "只检测" not in text:
                return self._set_opportunity_push_enabled(True)
            if any(word in text for word in ("只检测mod", "只检测卡", "仅检测mod", "仅检测卡")):
                return self._set_opportunity_filter("mod")
            if any(word in text for word in ("只检测赋能", "仅检测赋能", "只看赋能")):
                return self._set_opportunity_filter("arcane")
            if any(word in text for word in ("检测全部", "恢复全部", "取消过滤", "全部检测")):
                return self._set_opportunity_filter("all")
        return None

    def _set_opportunity_push_enabled(self, enabled: bool) -> str:
        cfg = PushConfig.load()
        cfg.push_proactive = enabled
        cfg.save()
        status = "开启" if enabled else "暂停"
        return f"已{status}交易机会推送。只影响主动交易机会；价格提醒、关注扫描和每日报告不受影响。"

    def _set_opportunity_filter(self, opportunity_filter: str) -> str:
        opportunity_filter = normalize_opportunity_filter(opportunity_filter)
        self.memory = self.memory.with_updated_preferences(opportunity_filter=opportunity_filter)
        self._persist_memory()
        label = {"all": "全部", "mod": "仅 MOD", "arcane": "仅赋能"}[opportunity_filter]
        return f"已设置交易机会检测范围：{label}。价格提醒、关注推送和每日报告不受影响。"

    def _try_price_alert_intent(self, message: str) -> str | None:
        intent = _parse_natural_language_price_alert(message)
        if not intent:
            return None
        item_id = self._resolve_item_id_for_command(intent.item_name)
        if not item_id:
            return f"找不到物品: {intent.item_name}，请尝试输入完整的 item_id"

        threshold_text = "低于" if intent.direction == "below" else "高于"
        if intent.action == "add":
            note = f"{display_item_name(item_id)} {threshold_text} {intent.price}p 提醒"
            self.memory = self.memory.with_price_alert(item_id, intent.direction, intent.price, note)
            self._persist_memory()
            return f"已添加提醒: {note}"

        before_count = len(self.memory.price_alerts)
        self.memory = self.memory.without_price_alert(item_id, intent.direction, intent.price)
        if len(self.memory.price_alerts) == before_count:
            return f"未找到对应提醒: {display_item_name(item_id)} {threshold_text} {intent.price}p"
        self._persist_memory()
        return f"已移除提醒: {display_item_name(item_id)} {threshold_text} {intent.price}p"

    def _try_favorite_intent(self, message: str) -> str | None:
        intent = _parse_natural_language_favorite(message)
        if not intent:
            return None
        return self._handle_favorite_command([intent.action, intent.item_name])

    def _try_preference_intent(self, message: str) -> str | None:
        intent = _parse_natural_language_preference(message)
        if not intent:
            return None
        self.memory = self.memory.with_updated_preferences(**intent.updates)
        self._persist_memory()
        summary = "，".join(intent.summary_parts)
        return f"已更新偏好: {summary}。使用 /profile 查看个人交易画像。"

    def _handle_opportunity_lookup(self, args: list[str]) -> str:
        if not args:
            return "用法：/opp OP8K3A2Q，或直接输入机会 ID。"
        lookup_id = normalize_opportunity_lookup_id(args[0])
        if not is_opportunity_lookup_id(lookup_id):
            return "机会 ID 格式不正确。请使用类似 OP8K3A2Q 的 ID。"
        detail = self.opportunity_lookup_store.get(lookup_id)
        if detail is None:
            return opportunity_not_found_message(lookup_id)
        return format_opportunity_lookup_reply(detail)

    def _handle_push_command(self, args: list[str]) -> str:
        normalized = [arg.strip().lower() for arg in args if arg.strip()]
        if not normalized:
            return "用法：/push opportunity off|on 或 /push opportunity filter mod|arcane|all"
        text = " ".join(normalized)
        if any(token in normalized for token in ("off", "false", "0", "关闭", "暂停")):
            return self._set_opportunity_push_enabled(False)
        if any(token in normalized for token in ("on", "true", "1", "开启", "恢复")):
            return self._set_opportunity_push_enabled(True)
        if "filter" in normalized or "只检测" in text or "检测" in text:
            if any(token in normalized for token in ("mod", "卡")):
                return self._set_opportunity_filter("mod")
            if any(token in normalized for token in ("arcane", "赋能")):
                return self._set_opportunity_filter("arcane")
            if any(token in normalized for token in ("all", "全部")):
                return self._set_opportunity_filter("all")
        return "用法：/push opportunity off|on 或 /push opportunity filter mod|arcane|all"

    def _render_memory_summary(self) -> str:
        favorites = "、".join(display_item_name(item_id) for item_id in self.memory.favorite_items[:5]) or "无"
        alerts = "、".join(
            f"{display_item_name(alert.item_id)} {('低于' if alert.direction == 'below' else '高于')} {alert.price}p"
            for alert in self.memory.price_alerts[:5]
        ) or "无"
        questions = "、".join(self.memory.common_questions[-5:]) or "无"
        lines = [
            "记忆摘要：",
            f"偏好: platform={self.memory.preferences.platform}, crossplay={self.memory.preferences.crossplay}, max_results={self.memory.preferences.max_results}, opportunity_filter={self.memory.preferences.opportunity_filter}",
            f"关注物品: {favorites}",
            f"价格提醒: {alerts}",
            f"常见问题: {questions}",
        ]
        if self.memory.user_profile:
            profile = self.memory.user_profile
            trade_text = {"buy": "偏好购买", "sell": "偏好出售"}.get(profile.preferred_trade_type, "买卖均衡")
            cats = "、".join(profile.favorite_categories) if profile.favorite_categories else "无"
            top_items = "、".join(list(profile.queried_items.keys())[:5]) or "无"
            lines.append(f"用户画像: {trade_text}，偏好分类: {cats}，常查物品: {top_items}")
        if self.memory.recent_suggestions:
            lines.append("最近智能建议：")
            for s in self.memory.recent_suggestions[-5:]:
                lines.append(f"  {s.message}")
        if self.memory.fissure_alerts:
            fissure_str = "、".join(a.note or "全部" for a in self.memory.fissure_alerts[:5])
            lines.append(f"裂缝订阅: {fissure_str}")
        if self.memory.cycle_alerts:
            cycle_str = "、".join(a.note or f"{a.cycle} -> {a.target_state}" for a in self.memory.cycle_alerts[:5])
            lines.append(f"状态订阅: {cycle_str}")
        return "\n".join(lines)

    def _handle_favorite_command(self, args: list[str]) -> str:
        if not args or (len(args) == 1 and args[0].lower() in {"list", "列表"}):
            if not self.memory.favorite_items:
                return "收藏列表为空，使用 /fav add 物品名 添加收藏"
            lines = ["当前收藏列表:"]
            for i, item_id in enumerate(self.memory.favorite_items, 1):
                lines.append(f"  {i}. {display_item_name(item_id)}")
            lines.append(f"\n共 {len(self.memory.favorite_items)} 个收藏")
            lines.append("使用 /fav add 物品名 添加，/fav remove 物品名 移除")
            return "\n".join(lines)
        if len(args) < 2 or args[0].lower() not in {"add", "remove"}:
            return "用法: /fav add 物品名 或 /fav remove 物品名"
        action = args[0].lower()
        item_name = " ".join(args[1:]).strip()
        item_id = self._resolve_item_id_for_command(item_name)
        if not item_id:
            return f"找不到物品: {item_name}，请尝试输入完整的 item_id"
        if action == "add":
            self.memory = self.memory.with_favorite_item(item_id)
            self._persist_memory()
            return f"已添加收藏: {display_item_name(item_id)}"
        self.memory = self.memory.without_favorite_item(item_id)
        self._persist_memory()
        return f"已移除收藏: {display_item_name(item_id)}"

    def _handle_alert_command(self, args: list[str]) -> str:
        if not args or (len(args) == 1 and args[0].lower() in {"list", "列表"}):
            if not self.memory.price_alerts:
                return "价格提醒为空，使用 /alert add 物品名 below 45 添加提醒"
            lines = ["当前价格提醒:"]
            for i, alert in enumerate(self.memory.price_alerts, 1):
                direction_cn = "低于" if alert.direction == "below" else "高于"
                lines.append(f"  {i}. {display_item_name(alert.item_id)} {direction_cn} {alert.price}p")
            lines.append(f"\n共 {len(self.memory.price_alerts)} 个提醒")
            lines.append("使用 /alert add 物品名 below 45 添加，/alert remove 物品名 below 45 移除")
            return "\n".join(lines)
        if len(args) < 4 or args[0].lower() not in {"add", "remove"}:
            return "用法: /alert add 物品名 below 45"
        action = args[0].lower()
        direction_index = None
        for i, token in enumerate(args[1:], start=1):
            if token.lower() in {"below", "above"}:
                direction_index = i
                break
        if direction_index is None or direction_index < 2:
            return "方向参数只支持 below 或 above"
        item_name = " ".join(args[1:direction_index]).strip()
        direction = args[direction_index].lower()
        if direction_index + 1 >= len(args):
            return "价格必须是整数，例如 /alert add 充沛 below 45"
        try:
            price = int(args[direction_index + 1])
        except ValueError:
            return "价格必须是整数，例如 /alert add 充沛 below 45"
        item_id = self._resolve_item_id_for_command(item_name)
        if not item_id:
            return f"找不到物品: {item_name}，请尝试输入完整的 item_id"
        if action == "add":
            note = " ".join(args[direction_index + 2:]).strip()
            if not note:
                threshold_text = "低于" if direction == "below" else "高于"
                note = f"{display_item_name(item_id)} {threshold_text} {price}p 提醒"
            self.memory = self.memory.with_price_alert(item_id, direction, price, note)
            self._persist_memory()
            return f"已添加提醒: {note}"
        self.memory = self.memory.without_price_alert(item_id, direction, price)
        self._persist_memory()
        return f"已移除提醒: {display_item_name(item_id)} {direction} {price}p"

    def _handle_preference_command(self, args: list[str]) -> str:
        if not args or (len(args) == 1 and args[0].lower() in {"list", "列表", "show", "查看"}):
            p = self.memory.preferences
            categories = ",".join(p.preferred_categories) or "未设置"
            budget = f"{p.budget_min}-{p.budget_max}p" if p.budget_min or p.budget_max else "未设置"
            lines = [
                "当前偏好设置:",
                f"  平台: {p.platform}",
                f"  跨平台: {'开' if p.crossplay else '关'}",
                f"  最大结果数: {p.max_results}",
                f"  风险偏好: {p.risk_appetite}",
                f"  预算区间: {budget}",
                f"  偏好品类: {categories}",
                f"  可接受周转: {p.max_turnaround_days} 天",
                f"  最低 ROI: {p.min_roi_pct}%",
                "",
                "修改: /pref platform pc | /pref crossplay on | /pref max 5 | /pref risk low | /pref budget 30-150 | /pref categories mod,arcane | /pref turnaround 3 | /pref min_roi 30",
            ]
            return "\n".join(lines)
        if len(args) < 2:
            return "用法: /pref platform pc | /pref crossplay on | /pref max 5 | /pref risk low | /pref budget 30-150 | /pref categories mod,arcane"
        key = args[0].lower()
        raw_value = " ".join(args[1:]).strip()
        value = raw_value.lower()
        if key == "platform":
            self.memory = self.memory.with_updated_preferences(platform=value)
            self._persist_memory()
            return f"已设置平台: {value}"
        if key == "crossplay":
            if value not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
                return "crossplay 只支持 on/off"
            crossplay = value in {"on", "true", "1", "yes"}
            self.memory = self.memory.with_updated_preferences(crossplay=crossplay)
            self._persist_memory()
            return f"已设置跨平台: {crossplay}"
        if key == "max":
            try:
                max_results = int(value)
            except ValueError:
                return "max 必须是整数，例如 /pref max 5"
            if max_results < 1 or max_results > 50:
                return "max 取值范围为 1-50"
            self.memory = self.memory.with_updated_preferences(max_results=max_results)
            self._persist_memory()
            return f"已设置最大结果数: {max_results}"
        if key in {
            "risk",
            "risk_appetite",
            "budget",
            "budget_range",
            "categories",
            "preferred_categories",
            "turnaround",
            "max_turnaround_days",
            "min_roi",
            "min_roi_pct",
        }:
            updated = self.memory.set_preference(key, raw_value)
            if updated == self.memory:
                return "偏好格式不正确。示例: /pref risk low | /pref budget 30-150 | /pref categories mod,arcane"
            self.memory = updated
            self._persist_memory()
            return "已更新偏好。使用 /profile 查看个人交易画像。"
        return "不支持的偏好设置，可选: platform / crossplay / max / risk / budget / categories / turnaround / min_roi"

    def _handle_profile_command(self) -> str:
        from .personal_profile import format_personal_profile

        return format_personal_profile(self._build_personal_profile())

    def _profile_opportunity_outcomes(self, limit: int = 100) -> list:
        if not self.trading_memory_db:
            return []
        try:
            return self.trading_memory_db.get_opportunity_outcomes(limit=limit)
        except Exception as exc:
            logger.debug("机会复盘画像读取失败: %s", exc)
            return []

    def _build_personal_profile(self):
        from .personal_profile import build_personal_profile

        return build_personal_profile(
            self.memory,
            opportunity_outcomes=self._profile_opportunity_outcomes(),
        )

    def _handle_review_command(self, args: list[str]) -> str:
        if args and args[0].strip().lower() in {"done", "complete", "完成", "记录"}:
            return self._handle_review_record_command(args[1:])
        if not self.trading_memory_db:
            return "暂无机会复盘数据。"
        status = args[0].strip().lower() if args else None
        records = self.trading_memory_db.get_opportunity_outcomes(status=status, limit=10)
        if not records:
            return "暂无机会复盘记录。"
        lines = ["机会复盘"]
        for record in records:
            metadata = record.metadata or {}
            safe_summary = metadata.get("safe_summary")
            if not isinstance(safe_summary, dict):
                safe_summary = metadata
            roi = safe_summary.get("roi_pct", "")
            risk = safe_summary.get("risk_level", "")
            detail = (
                f"- {record.opportunity_id} {record.item_name}: {record.status}, "
                f"预期 {record.expected_profit}p, 实际 {record.actual_profit}p, 反馈 {record.user_feedback}"
            )
            if roi != "":
                detail += f", ROI {roi}%"
            if risk:
                detail += f", 风险 {risk}"
            lines.append(detail)
        return "\n".join(lines)

    def _handle_review_record_command(self, args: list[str]) -> str:
        if not self.trading_memory_db:
            return "暂无机会复盘数据。"
        if len(args) < 2:
            return "用法：/review done OP8K3A2Q 实际利润 [good|bad|neutral|ignored]"
        lookup_id = normalize_opportunity_lookup_id(args[0])
        if not is_opportunity_lookup_id(lookup_id):
            return "机会 ID 格式不正确。请使用类似 OP8K3A2Q 的 ID。"
        try:
            actual_profit = int(args[1])
        except ValueError:
            return "实际利润必须是整数，例如：/review done OP8K3A2Q 45 good"
        feedback = (
            self._normalize_review_feedback(args[2])
            if len(args) >= 3
            else self._default_feedback_for_profit(actual_profit)
        )
        detail = self.opportunity_lookup_store.get(lookup_id)
        if detail is None:
            return opportunity_not_found_message(lookup_id)
        plan = detail.content if isinstance(detail.content, dict) else {}
        safe_summary = self._opportunity_review_safe_summary(detail)
        item_id = str(safe_summary.get("item_id") or detail.item_id or plan.get("item_id") or "")
        source = str(safe_summary.get("source") or plan.get("source") or "unknown")
        strategy = str(safe_summary.get("strategy") or plan.get("strategy") or source)
        expected_profit = self._safe_int(safe_summary.get("profit", plan.get("profit", 0)))
        self.trading_memory_db.record_opportunity_outcome(
            lookup_id,
            item_id,
            source,
            strategy,
            "completed",
            expected_profit,
            actual_profit,
            feedback,
            {"safe_summary": safe_summary},
        )
        return (
            f"已记录机会复盘：{lookup_id} {item_id}，"
            f"预期 {expected_profit}p，实际 {actual_profit}p，反馈 {feedback}。"
        )

    @staticmethod
    def _default_feedback_for_profit(actual_profit: int) -> str:
        if actual_profit > 0:
            return "good"
        if actual_profit < 0:
            return "bad"
        return "neutral"

    @staticmethod
    def _normalize_review_feedback(value: str) -> str:
        normalized = str(value or "neutral").strip().lower()
        allowed = {"good", "bad", "ignored", "neutral", "accepted", "rejected"}
        return normalized if normalized in allowed else "neutral"

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _opportunity_review_safe_summary(detail) -> dict:
        plan = detail.content if isinstance(detail.content, dict) else {}
        raw = plan.get("safe_summary")
        if not isinstance(raw, dict):
            raw = plan
        allowed = {
            "source",
            "strategy",
            "item_id",
            "required_quantity",
            "total_cost",
            "total_revenue",
            "profit",
            "roi_pct",
            "risk_level",
            "profit_bucket",
            "plan_signature",
            "turnaround_days",
            "budget_spent",
            "quantity",
            "confidence",
        }
        summary = {}
        for key in allowed:
            value = raw.get(key)
            if value is not None:
                summary[key] = value
        if "item_id" not in summary and detail.item_id:
            summary["item_id"] = detail.item_id
        return summary

    def _handle_scan_command(self) -> str:
        lines = ["扫描结果："]
        if self.memory.favorite_items:
            lines.append("\n关注物品当前价格：")
            for item_id in self.memory.favorite_items:
                try:
                    ctx = build_item_context_result(item_id, self.order_fetcher(item_id))
                    if ctx.best_sell_price is not None or ctx.best_buy_price is not None:
                        sell = f"卖 {ctx.best_sell_price}p" if ctx.best_sell_price is not None else "卖 暂无"
                        buy = f"收 {ctx.best_buy_price}p" if ctx.best_buy_price is not None else "收 暂无"
                        lines.append(f"  {display_item_name(item_id)}: {sell} / {buy}")
                    else:
                        lines.append(f"  {display_item_name(item_id)}: 暂无数据")
                except Exception as exc:
                    lines.append(f"  {display_item_name(item_id)}: 查询失败 ({exc})")
        triggered = []
        for alert in self.memory.price_alerts:
            try:
                ctx = build_item_context_result(alert.item_id, self.order_fetcher(alert.item_id))
                if ctx.best_sell_price is not None and alert.matches(ctx.best_sell_price):
                    triggered.append((alert, ctx.best_sell_price))
            except Exception as exc:
                logger.debug("价格提醒检查失败 %s: %s", alert.item_id, exc)
                continue
        if triggered:
            lines.append("\n触发的提醒：")
            for alert, price in triggered:
                lines.append(f"  {alert.note}: 当前 {price}p")
        elif self.memory.price_alerts:
            lines.append("\n未触发任何价格提醒。")
        if not self.memory.favorite_items and not self.memory.price_alerts:
            lines.append("关注列表和提醒均为空，请先使用 /fav 和 /alert 添加。")
        return "\n".join(lines)

    def _handle_goal_command(self, args: list[str]) -> str:
        from .goals import GoalTracker
        if not args:
            return GoalTracker().format_goals_status()
        sub = args[0].lower()
        if sub in ("set", "add", "新建"):
            desc = " ".join(args[1:]) if len(args) > 1 else ""
            if not desc:
                return "请指定目标描述，例如: /goal set 一周内赚500p"
            return self._create_goal_from_description(desc)
        tracker = GoalTracker()
        if sub in ("done", "完成"):
            gid = args[1] if len(args) > 1 else ""
            if not gid:
                return "请指定目标 ID，例如: /goal done abc123"
            matches = [g for g in tracker.goals if g.goal_id.startswith(gid)]
            if not matches:
                return f"未找到 ID 为 {gid} 的目标"
            tracker.update_goal_status(matches[0].goal_id, "achieved")
            review = tracker.generate_review(matches[0].goal_id)
            return f"目标已标记为完成！\n\n{review}"
        if sub in ("drop", "放弃"):
            gid = args[1] if len(args) > 1 else ""
            if not gid:
                return "请指定目标 ID，例如: /goal drop abc123"
            matches = [g for g in tracker.goals if g.goal_id.startswith(gid)]
            if not matches:
                return f"未找到 ID 为 {gid} 的目标"
            tracker.update_goal_status(matches[0].goal_id, "abandoned")
            return f"已放弃目标: {matches[0].description}"
        if sub in ("review", "复盘"):
            gid = args[1] if len(args) > 1 else ""
            if not gid:
                done = [g for g in tracker.goals if g.status in ("achieved", "abandoned")]
                if not done:
                    return "没有已完成的目标可复盘。"
                reviews = [tracker.generate_review(g.goal_id) for g in done[-3:]]
                return "\n\n---\n\n".join(reviews)
            matches = [g for g in tracker.goals if g.goal_id.startswith(gid)]
            if not matches:
                return f"未找到 ID 为 {gid} 的目标"
            return tracker.generate_review(matches[0].goal_id)
        if sub in ("rm", "delete", "删除"):
            gid = args[1] if len(args) > 1 else ""
            if not gid:
                return "请指定目标 ID"
            matches = [g for g in tracker.goals if g.goal_id.startswith(gid)]
            if not matches:
                return f"未找到 ID 为 {gid} 的目标"
            tracker.remove_goal(matches[0].goal_id)
            return f"已删除目标: {matches[0].description}"
        return "未知的 /goal 子命令。可用: set/add, done, drop, review, rm"

    # ── 裂缝订阅命令 ────────────────────────────────────────

    _TIER_CHINESE = {
        "古纪": "VoidT1", "前纪": "VoidT2", "中纪": "VoidT3",
        "后纪": "VoidT4", "遗珍": "VoidT5", "仲裁": "VoidT6",
        "lith": "VoidT1", "meso": "VoidT2", "neo": "VoidT3",
        "axi": "VoidT4", "requiem": "VoidT5", "arbitration": "VoidT6",
    }
    _MISSION_CHINESE = {
        "歼灭": "MT_EXTERMINATION", "捕获": "MT_CAPTURE", "防御": "MT_DEFENSE",
        "生存": "MT_SURVIVAL", "救援": "MT_RESCUE", "破坏": "MT_SABOTAGE",
        "移动防御": "MT_MOBILE_DEFENSE", "间谍": "MT_INTEL", "拦截": "MT_TERRITORY",
        "挖掘": "MT_ARTIFACT", "炼金": "MT_ALCHEMY", "中断": "MT_DISRUPTION",
        "刺杀": "MT_ASSASSINATION",
    }
    _NODE_CHINESE = {
        "虚空": "虚空", "地球": "地球", "火星": "火星", "金星": "金星",
        "水星": "水星", "木星": "木星", "土星": "土星", "天王星": "天王星",
        "海王星": "海王星", "冥王星": "冥王星", "塞德娜": "塞德娜",
        "火卫一": "火卫一", "谷神星": "谷神星", "欧罗巴": "欧罗巴",
    }

    def _handle_fissure_command(self, args: list[str]) -> str:
        from .memory import FissureAlert
        if not args:
            return "用法: /fissure add [过滤条件] | /fissure remove 序号 | /fissure list"
        sub = args[0].lower()
        if sub == "list" or sub == "列表":
            return self._list_fissure_alerts()
        if sub == "remove" or sub == "删除":
            return self._remove_fissure_alert(args[1:])
        if sub == "add" or sub == "添加":
            return self._add_fissure_alert(args[1:])
        return "未知的 /fissure 子命令。可用: add, remove, list"

    def _add_fissure_alert(self, args: list[str]) -> str:
        from .memory import FissureAlert
        node_pattern = ""
        mission_type = ""
        tier = ""
        hard = None
        note_parts = []

        for arg in args:
            lower = arg.lower()
            # 检查等级
            if lower in self._TIER_CHINESE:
                tier = self._TIER_CHINESE[lower]
                note_parts.append(f"等级={arg}")
                continue
            # 检查任务类型
            if lower in self._MISSION_CHINESE:
                mission_type = self._MISSION_CHINESE[lower]
                note_parts.append(f"任务={arg}")
                continue
            # 检查节点/星球
            if lower in self._NODE_CHINESE:
                node_pattern = self._NODE_CHINESE[lower]
                note_parts.append(f"地点={arg}")
                continue
            # 检查钢铁模式
            if lower in ("钢铁", "steelpath", "steel", "钢铁之路"):
                hard = True
                note_parts.append("仅钢铁")
                continue
            if lower in ("普通", "normal"):
                hard = False
                note_parts.append("仅普通")
                continue
            # 其他参数当作节点名子串
            node_pattern = arg
            note_parts.append(f"地点={arg}")

        note = "、".join(note_parts) if note_parts else "全部裂缝"
        alert = FissureAlert(
            node_pattern=node_pattern,
            mission_type=mission_type,
            tier=tier,
            hard=hard,
            note=note,
        )
        self.memory = self.memory.with_fissure_alert(alert)
        self._persist_memory()
        return f"已订阅裂缝通知: {note}\n当匹配的裂缝出现时会推送通知。"

    def _remove_fissure_alert(self, args: list[str]) -> str:
        if not args:
            return "请指定序号，例如: /fissure remove 1"
        try:
            index = int(args[0]) - 1
        except ValueError:
            return "序号必须是数字，例如: /fissure remove 1"
        if 0 <= index < len(self.memory.fissure_alerts):
            removed = self.memory.fissure_alerts[index]
            self.memory = self.memory.without_fissure_alert(index)
            self._persist_memory()
            return f"已取消订阅: {removed.note or '全部裂缝'}"
        return f"序号超出范围，当前共 {len(self.memory.fissure_alerts)} 条订阅"

    def _list_fissure_alerts(self) -> str:
        alerts = self.memory.fissure_alerts
        if not alerts:
            return "当前没有裂缝订阅。使用 /fissure add 添加订阅。\n示例: /fissure add 虚空 歼灭"
        lines = ["当前裂缝订阅:"]
        for i, a in enumerate(alerts, 1):
            desc = a.note or "全部裂缝"
            lines.append(f"  {i}. {desc}")
        lines.append("\n使用 /fissure remove 序号 取消订阅")
        return "\n".join(lines)

    # ── 开放世界状态订阅命令 ──────────────────────────────────

    _CYCLE_ALIASES = {
        "地球": "earth", "地球场景": "earth", "earth": "earth",
        "希图斯": "cetus", "夜灵平原": "cetus", "夜灵平野": "cetus", "平原": "cetus", "cetus": "cetus",
        "金星": "vallis", "奥布山谷": "vallis", "福尔图娜": "vallis", "金星平原": "vallis", "vallis": "vallis", "orb vallis": "vallis",
        "魔胎之境": "cambion", "火卫二": "cambion", "殁世幽都": "cambion", "cambion": "cambion",
    }
    _CYCLE_DISPLAY = {
        "earth": "地球",
        "cetus": "希图斯/夜灵平原",
        "vallis": "奥布山谷/金星",
        "cambion": "魔胎之境",
    }
    _CYCLE_STATE_ALIASES = {
        "白天": "day", "白昼": "day", "白日": "day", "day": "day",
        "黑夜": "night", "夜晚": "night", "晚上": "night", "night": "night",
        "温暖": "warm", "暖": "warm", "热": "warm", "warm": "warm",
        "寒冷": "cold", "冷": "cold", "cold": "cold",
        "fass": "fass", "法斯": "fass",
        "vome": "vome", "沃姆": "vome",
    }
    _CYCLE_STATE_DISPLAY = {
        "day": "白天", "night": "黑夜", "warm": "温暖", "cold": "寒冷", "fass": "Fass", "vome": "Vome",
    }

    def _handle_cycle_command(self, args: list[str]) -> str:
        if not args:
            return "用法: /cycle status [地点] | /cycle add 地点 状态 | /cycle remove 序号 | /cycle list"
        sub = args[0].lower()
        if sub in {"status", "状态", "当前", "查看"}:
            return self._cycle_status(" ".join(args[1:]))
        if sub in {"add", "添加", "订阅"}:
            return self._add_cycle_alert(" ".join(args[1:]))
        if sub in {"remove", "删除", "取消"}:
            return self._remove_cycle_alert(args[1:])
        if sub in {"list", "列表"}:
            return self._list_cycle_alerts()
        return "未知的 /cycle 子命令。可用: status, add, remove, list"

    def _find_cycle_alias(self, text: str) -> str:
        lowered = text.lower()
        matches = sorted(self._CYCLE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
        for alias, cycle in matches:
            if alias.lower() in lowered:
                return cycle
        return ""

    def _find_cycle_state_alias(self, text: str) -> str:
        lowered = text.lower()
        matches = sorted(self._CYCLE_STATE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
        for alias, state in matches:
            if alias.lower() in lowered:
                return state
        return ""

    def _cycle_status(self, location: str = "") -> str:
        if not self.event_tracker:
            return "暂时无法获取星球状态。"
        cycle_filter = self._find_cycle_alias(location) if location else ""
        cycles = self.event_tracker.get_cycles()
        if cycle_filter:
            cycles = [cycle for cycle in cycles if cycle.cycle == cycle_filter]
        if not cycles:
            return "暂时无法获取该星球状态。"
        if len(cycles) == 1:
            cycle = cycles[0]
            suffix = f"，预计结束: {cycle.expiry}" if cycle.expiry else ""
            return f"{cycle.cycle_display}当前为{cycle.state_display}{suffix}。"
        lines = ["当前开放世界/星球状态:"]
        for cycle in cycles:
            suffix = f"，预计结束: {cycle.expiry}" if cycle.expiry else ""
            lines.append(f"- {cycle.cycle_display}: {cycle.state_display}{suffix}")
        return "\n".join(lines)

    def _add_cycle_alert(self, text: str) -> str:
        from .memory import CycleAlert
        cycle = self._find_cycle_alias(text)
        target_state = self._find_cycle_state_alias(text)
        if not cycle or not target_state:
            return "用法: /cycle add 地点 状态，例如 /cycle add 地球 黑夜 或 /cycle add 金星 寒冷"
        note = f"{self._CYCLE_DISPLAY.get(cycle, cycle)}变为{self._CYCLE_STATE_DISPLAY.get(target_state, target_state)}"
        alert = CycleAlert(cycle=cycle, target_state=target_state, note=note, created_at=time.time())
        before_count = len(self.memory.cycle_alerts)
        self.memory = self.memory.with_cycle_alert(alert)
        self._persist_memory()
        current = self.event_tracker.get_cycle(cycle) if self.event_tracker else None
        already = current and current.state == target_state
        if len(self.memory.cycle_alerts) == before_count:
            prefix = f"已存在状态提醒：{note}。"
        else:
            prefix = f"已订阅状态提醒：{note}。"
        if already:
            return prefix + "当前已经是目标状态，本阶段不会重复推送，会在下次切换到该状态时提醒。"
        return prefix + "系统会在状态切换到目标状态时推送。"

    def _remove_cycle_alert(self, args: list[str]) -> str:
        if not args:
            return "请指定序号，例如: /cycle remove 1"
        try:
            index = int(args[0]) - 1
        except ValueError:
            return "序号必须是数字，例如: /cycle remove 1"
        if 0 <= index < len(self.memory.cycle_alerts):
            removed = self.memory.cycle_alerts[index]
            self.memory = self.memory.without_cycle_alert(index)
            self._persist_memory()
            return f"已取消状态订阅: {removed.note or '状态提醒'}"
        return f"序号超出范围，当前共 {len(self.memory.cycle_alerts)} 条订阅"

    def _list_cycle_alerts(self) -> str:
        alerts = self.memory.cycle_alerts
        if not alerts:
            return "当前没有状态订阅。使用 /cycle add 地点 状态 添加订阅。\n示例: /cycle add 地球 黑夜"
        lines = ["当前状态订阅:"]
        for i, alert in enumerate(alerts, 1):
            lines.append(f"  {i}. {alert.note or '状态提醒'}")
        lines.append("\n使用 /cycle remove 序号 取消订阅")
        return "\n".join(lines)

    def _try_cycle_intent(self, message: str) -> str | None:
        cycle = self._find_cycle_alias(message)
        if not cycle:
            return None
        state = self._find_cycle_state_alias(message)
        lowered = message.lower()
        wants_alert = any(kw in lowered for kw in ("提醒我", "通知我", "订阅", "提醒", "通知")) and any(kw in lowered for kw in ("变为", "变成", "到", "当", "时", "变"))
        if wants_alert and state:
            return self._add_cycle_alert(message)
        wants_status = any(kw in lowered for kw in ("现在", "当前", "状态", "还有多久", "冷吗", "热吗", "黑夜吗", "白天吗", "晚上吗"))
        if wants_status:
            return self._cycle_status(cycle)
        return None

    # ---- /trade 命令 ----

    def _handle_trade_command(self, args: list[str]) -> str:
        if not args:
            return "用法: /trade list [N] | /trade stats | /trade add 物品名 buy/sell 价格 | /trade undo"
        sub = args[0].lower()
        if sub == "list" or sub == "列表":
            limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
            return self._list_trades(limit)
        if sub == "stats" or sub == "统计":
            return self._trade_stats()
        if sub == "add" or sub == "添加":
            return self._add_trade(args[1:])
        if sub == "undo" or sub == "撤销":
            return self._undo_trade()
        return "未知的 /trade 子命令。可用: list, stats, add, undo"

    def _list_trades(self, limit: int = 10) -> str:
        from .trade_history import TradeHistoryDB
        db = TradeHistoryDB()
        trades = db.get_recent_trades(limit)
        if not trades:
            return "暂无交易记录。使用 /trade add 物品名 buy/sell 价格 手动添加。"
        lines = ["最近交易记录："]
        for t in trades:
            action = "买入" if t.trade_type == "buy" else "卖出"
            lines.append(f"  [{t.id}] {t.item_name} {action} {t.price}p ({t.timestamp[:16]})")
        return "\n".join(lines)

    def _trade_stats(self) -> str:
        from .trade_history import TradeHistoryDB
        db = TradeHistoryDB()
        stats = db.get_trade_stats()
        if stats["total_trades"] == 0:
            return "暂无交易记录。"
        lines = [
            "交易统计：",
            f"  总交易: {stats['total_trades']} 笔 (买入 {stats['buy_count']} / 卖出 {stats['sell_count']})",
            f"  总花费: {stats['total_spent']}p | 总收入: {stats['total_earned']}p",
            f"  净利润: {stats['net_profit']}p",
        ]
        if stats["most_traded"]:
            lines.append("  常交易: " + "、".join(f"{m['name']}({m['count']}次)" for m in stats["most_traded"]))
        return "\n".join(lines)

    def _add_trade(self, args: list[str]) -> str:
        if len(args) < 3:
            return "用法: /trade add 物品名 buy/sell 价格"
        item_name = args[0]
        trade_type = args[1].lower()
        if trade_type not in ("buy", "sell", "买", "卖"):
            return "交易类型必须是 buy/sell/买/卖"
        if trade_type == "买":
            trade_type = "buy"
        elif trade_type == "卖":
            trade_type = "sell"
        try:
            price = int(args[2])
        except ValueError:
            return "价格必须是数字"
        item_id = self._resolve_item_id_for_command(item_name)
        if not item_id:
            return f"未找到物品: {item_name}"
        from .trade_history import TradeHistoryDB
        db = TradeHistoryDB()
        db.add_trade(item_id, display_item_name(item_id), trade_type, price)
        action = "买入" if trade_type == "buy" else "卖出"
        return f"已记录: {display_item_name(item_id)} {action} {price}p"

    def _undo_trade(self) -> str:
        from .trade_history import TradeHistoryDB
        db = TradeHistoryDB()
        trades = db.get_recent_trades(1)
        if not trades:
            return "没有可撤销的交易记录。"
        t = trades[0]
        db.delete_trade(t.id)
        return f"已撤销: {t.item_name} {'买入' if t.trade_type == 'buy' else '卖出'} {t.price}p"

    # ---- /relic 命令 ----

    def _handle_relic_command(self, args: list[str]) -> str:
        if not args:
            return "用法: /relic 物品名 | /relic 遗物名 | /relic value 遗物名\n示例: /relic 犀牛 Prime 蓝图 | /relic Lith B1 | /relic value Lith B1"
        if args[0].lower() in {"value", "估值", "价值"}:
            relic_name = " ".join(args[1:]).strip()
            if not relic_name:
                return "用法: /relic value 遗物名\n示例: /relic value Lith B1"
            result = self._tool_relic_value({"relic_name": relic_name})
            return result.display_content if result.ok else (result.error or f"未找到与 '{relic_name}' 相关的遗物。")
        query = " ".join(args)
        from .relics import get_relic_db, TIER_MAP
        db = get_relic_db()
        db.load(self.warframe_items or None)

        # 先尝试按部件查找
        drops = db.find_by_part(query)
        if not drops:
            # 尝试用 resolver 解析物品名
            item_id = self._resolve_item_id_for_command(query)
            if item_id:
                drops = db.find_by_part(item_id)

        if drops:
            # 按遗物分组
            by_relic: dict[str, list] = {}
            for d in drops:
                by_relic.setdefault(d.relic_name, []).append(d)

            lines = [f"## {query} 的掉落遗物\n"]
            for relic_name, relic_drops in sorted(by_relic.items()):
                info = db.find_by_relic(relic_name)
                vaulted = " (已Vault)" if info and info.is_vaulted else ""
                tier_cn = TIER_MAP.get(relic_drops[0].relic_tier, relic_drops[0].relic_tier)
                lines.append(f"**{relic_name}** [{tier_cn}]{vaulted}")
                for d in relic_drops:
                    rate = f"{d.drop_rate*100:.1f}%"
                    lines.append(f"  - {d.part_name} ({d.rarity}, {rate})")

            # 关联当前裂缝
            from .events import EventTracker
            tracker = EventTracker()
            tracker.load_cache()
            fissures = tracker.get_active_fissures()
            if fissures:
                matching = []
                for f in fissures:
                    for relic_name in by_relic:
                        if f.tier_display and f.tier_display.lower() in relic_name.lower():
                            matching.append(f)
                            break
                if matching:
                    lines.append("\n**当前可刷裂缝：**")
                    for f in matching[:5]:
                        hard = " 钢铁" if f.hard else ""
                        lines.append(f"  - {f.tier_display} {f.mission_display}{hard} @ {f.node_display}")

            return "\n".join(lines)

        # 尝试按遗物名查找
        info = db.find_by_relic(query)
        if info:
            tier_cn = TIER_MAP.get(info.tier, info.tier)
            vaulted = " (已Vault)" if info.is_vaulted else ""
            lines = [f"## {info.name} [{tier_cn}]{vaulted}\n"]
            for d in info.drops:
                rate = f"{d.drop_rate*100:.1f}%"
                market = f" ({d.market_id})" if d.market_id else ""
                lines.append(f"  - {d.part_name} ({d.rarity}, {rate}){market}")
            return "\n".join(lines)

        return f"未找到与 '{query}' 相关的遗物或部件。"

    def _handle_strategy_command(self, args: list[str]) -> str:
        from .strategies import (
            list_strategies, get_strategy, run_strategy, format_strategy_result,
        )
        if not args or args[0] == "list":
            strategies = list_strategies()
            lines = ["可用交易策略:"]
            for s in strategies:
                lines.append(f"  [{s.risk_level}] {s.name} — {s.description}")
            lines.append("\n使用 /strategy run 策略名 执行扫描")
            return "\n".join(lines)

        if args[0] == "run":
            if len(args) < 2:
                return "用法: /strategy run 策略名\n示例: /strategy run 低风险"
            query = " ".join(args[1:])
            strategy = get_strategy(query)
            if not strategy:
                return f"未找到策略 '{query}'，使用 /strategy list 查看可用策略"
            result = run_strategy(strategy, self.order_fetcher)
            return format_strategy_result(result)

        return "用法: /strategy list | /strategy run 策略名"

    def _handle_vault_command(self) -> str:
        """显示当前 Vault / Prime 重生状态。"""
        tracker = self.event_tracker or EventTracker()
        if not self.event_tracker:
            tracker.load_cache()
        resurgence = tracker.get_prime_resurgence()
        vault_events = tracker.get_vault_status()
        if not resurgence and not vault_events:
            return "当前没有 Prime Vault / Prime 重生活动。"
        lines = []
        if resurgence and resurgence.prime_resurgence:
            rotation = resurgence.prime_resurgence
            paid_items = [item for item in rotation.items if item.prime_price]
            relic_items = [item for item in rotation.items if item.regular_price]
            relic_names = [_resurgence_relic_name(item) for item in relic_items]
            relic_names = [name for index, name in enumerate(relic_names) if name and name not in relic_names[:index]]
            warframe_items = [item for item in paid_items if _is_resurgence_warframe(item)]
            weapon_items = [item for item in paid_items if _is_resurgence_weapon(item)]
            if warframe_items:
                lines.append("返厂战甲:")
                for item in warframe_items[:12]:
                    lines.append(f"- {_resurgence_warframe_display_name(item)}{self._resurgence_price_suffix(item, relic_names)}")
            if weapon_items:
                lines.append("返厂武器:")
                for item in weapon_items[:12]:
                    lines.append(f"- {_resurgence_weapon_display_name(item)}{self._resurgence_price_suffix(item, relic_names)}")
            return "\n".join(lines)
        for event in vault_events:
            items = ", ".join(
                display_item_name(item_id) for item_id in event.items_affected[:5]
            ) if event.items_affected else "未知物品"
            lines.append(f"Vault 回归物品: {items}")
            if event.start_time:
                lines.append(f"开始时间: {event.start_time}")
            if event.end_time:
                lines.append(f"结束时间: {event.end_time}")
            lines.append("")
        return "\n".join(lines)

    def _resurgence_price_suffix(self, item, relic_names: list[str] | None = None) -> str:
        parts = [f"{item.prime_price} Regal Aya"]
        if relic_names:
            parts.append(f"可通过兑换当前 Prime 重生的{'、'.join(relic_names[:4])}刷取")
        market_id = _resurgence_market_id(item)
        if market_id:
            try:
                orders = self.order_fetcher(market_id)
                sellers = best_sellers(orders, limit=1)
                buyers = best_buyers(orders, limit=1)
            except Exception:
                sellers = []
                buyers = []
            if buyers:
                parts.append(f"最高收价 {buyers[0].platinum}p")
            if sellers:
                parts.append(f"最低卖价 {sellers[0].platinum}p")
        return f" ({'，'.join(parts)})"

    def _auto_record_trade(self, message: str, contexts: list) -> str | None:
        """检测已完成的交易语句并自动记录。返回确认消息或 None。"""
        if len(contexts) != 1:
            return None
        completed = detect_completed_trade(message)
        if not completed:
            return None
        trade_type, price = completed
        ctx = contexts[0]
        from .trade_history import TradeHistoryDB
        db = TradeHistoryDB()
        db.add_trade(ctx.item_id, display_item_name(ctx.item_id), trade_type, price)
        action = "买入" if trade_type == "buy" else "卖出"
        return f"已自动记录交易: {display_item_name(ctx.item_id)} {action} {price}p (使用 /trade list 查看)"

    def _resolve_item_id_for_command(self, item_name: str) -> str | None:
        try:
            return self.resolver.resolve(item_name).item_id
        except (LookupError, ValueError):
            matches = self._item_ids_from_alias_substrings(item_name)
            return matches[0] if matches else None

    def _try_baro_recommendation(self, message: str) -> str | None:
        if not _is_baro_recommendation_query(message):
            return None
        try:
            from .baro import analyze_baro_inventory, format_baro_report, parse_baro_rank_request
            tracker = self.event_tracker or EventTracker()
            if not self.event_tracker:
                tracker.load_cache()
            events = tracker.get_active_events()
            baro_event = next((e for e in events if e.event_type == "baro_visit" and e.baro_items), None)
            if not baro_event:
                return "当前没有检测到带库存的虚空商人事件。"
            if _is_baro_inventory_query(message):
                recommendations = analyze_baro_inventory(
                    baro_event,
                    self.order_fetcher,
                    rank_request="max",
                    item_info_lookup=self._baro_item_info_lookup,
                )
                self._last_baro_recommendations = recommendations
                return format_baro_report(recommendations)
            rank_request = parse_baro_rank_request(message)
            recommendations = analyze_baro_inventory(
                baro_event,
                self.order_fetcher,
                rank_request=rank_request,
                item_info_lookup=self._baro_item_info_lookup,
            )
            self._last_baro_recommendations = recommendations
            return format_baro_report(recommendations)
        except Exception as exc:
            logger.debug("Baro 推荐失败: %s", exc)
            return "暂时无法分析虚空商人库存。"

    def _try_baro_order_followup(self, message: str) -> ToolResult | None:
        if not self._last_baro_recommendations:
            return None
        from .baro import (
            find_baro_recommendation,
            format_baro_order_details,
            format_baro_order_details_for_model,
            is_baro_order_detail_request,
            parse_order_detail_limits,
        )
        if not is_baro_order_detail_request(message):
            return None
        if self._baro_followup_conflicts_with_direct_market_query(message):
            return None
        recommendation = find_baro_recommendation(self._last_baro_recommendations, message)
        if not recommendation:
            return None
        buyer_limit, seller_limit = parse_order_detail_limits(message)
        display = format_baro_order_details(recommendation, seller_limit=seller_limit, buyer_limit=buyer_limit)
        model_context = format_baro_order_details_for_model(recommendation, seller_limit=seller_limit, buyer_limit=buyer_limit)
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _baro_followup_conflicts_with_direct_market_query(self, message: str) -> bool:
        lowered = message.lower()
        if any(word in lowered for word in ("baro", "虚空商人", "奸商")):
            return False
        for rec in self._last_baro_recommendations:
            rec_names = (rec.market_id, display_item_name(rec.market_id), rec.item_name)
            if any(name and name.lower() in lowered for name in rec_names):
                return False
        return self._resolve_direct_market_item_id(message) is not None

    def _try_router(self, message: str) -> str | None:
        result = self._try_router_result(message)
        return self._tool_result_display_text(result)

    def _try_router_result(self, message: str, candidate_tools: set[str] | None = None) -> str | ToolResult | None:
        try:
            result = self._try_react_loop(message, candidate_tools=candidate_tools)
        except TypeError:
            if candidate_tools is not None:
                raise
            result = self._try_react_loop(message)
        if result:
            return result
        return self._try_router_legacy_result(message, candidate_tools=candidate_tools)

    def _try_react_loop(
        self,
        message: str,
        candidate_tools: set[str] | None = None,
        plan_confirmation_token: str | None = None,
    ) -> str | None:
        from .tool_router import AgentTrace, react_loop
        trace = AgentTrace()
        self.last_agent_trace = trace
        try:
            result = react_loop(
                message=message,
                tool_executor=lambda tc: self._run_tool_call(tc, message),
                model_call=self._react_model_call,
                candidate_tools=candidate_tools,
                trace=trace,
                plan_confirmation_token=plan_confirmation_token,
            )
            if isinstance(result, str):
                return self._capture_agent_plan_confirmation(message, candidate_tools, result, trace)
            return result
        except Exception as exc:
            logger.debug("ReAct 循环失败: %s", exc)
            self.last_agent_trace = trace
            return None

    def _react_model_call(self, messages: list[dict]) -> str:
        if self.router_call:
            parts = [m.get("content", "") for m in messages if m.get("role") != "system"]
            return self.router_call("\n".join(parts))
        if self.model_call is not call_ollama_chat:
            parts = [m.get("content", "") for m in messages if m.get("role") != "system"]
            return self.model_call("\n".join(parts))
        from .tool_router import _default_model_call
        return _default_model_call(messages)

    def _try_router_legacy(self, message: str) -> str | None:
        result = self._try_router_legacy_result(message)
        return self._tool_result_display_text(result)

    def _try_router_legacy_result(self, message: str, candidate_tools: set[str] | None = None) -> ToolResult | None:
        caller = self.router_call or self.model_call
        try:
            selected_tools = candidate_tools or select_candidate_tools(message)
            router_prompt = build_router_prompt(message, candidate_tools=selected_tools)
            raw = caller(router_prompt).strip()
            tool_call = parse_tool_call(raw, valid_names=selected_tools)
            if not tool_call:
                return None
            result = self._run_tool_call(tool_call, message)
            return result if result.ok else None
        except Exception as exc:
            logger.debug("工具路由失败: %s", exc)
            return None

    def _build_tool_registry(self):
        registry = create_default_tool_registry()
        registry.with_handler("query_price", self._tool_query_price)
        registry.with_handler("query_set", self._tool_query_set)
        registry.with_handler("query_missing_parts", self._tool_query_missing_parts)
        registry.with_handler("scan_favorites", self._tool_scan_favorites)
        registry.with_handler("set_alert", self._tool_set_alert)
        registry.with_handler("price_trend", self._tool_price_trend)
        registry.with_handler("general_chat", self._tool_general_chat)
        registry.with_handler("mod_flipper", self._tool_mod_flipper)
        registry.with_handler("set_profit", self._tool_set_profit)
        registry.with_handler("investment_advisor", self._tool_investment_advisor)
        registry.with_handler("query_events", self._tool_query_events)
        registry.with_handler("relic_value", self._tool_relic_value)
        registry.with_handler("farming_route", self._tool_farming_route)
        registry.with_handler("deep_analysis", self._tool_deep_analysis)
        registry.with_handler("market_expert", lambda args: self._tool_expert("market", args))
        registry.with_handler("riven_expert", lambda args: self._tool_expert("riven", args))
        registry.with_handler("event_expert", lambda args: self._tool_expert("event", args))
        registry.with_handler("riven_search", self._tool_riven_search)
        return registry

    def _run_tool_call(self, tool_call, message: str = "") -> ToolResult:
        args = dict(tool_call.arguments)
        if message and "__message" not in args:
            args["__message"] = message
        result = self.tool_registry.execute(tool_call.name, args)
        if result.metadata:
            self.tool_execution_metadata.append(result.metadata)
        return result

    def _execute_tool_call(self, tool_call, message: str = "") -> str | None:
        result = self._run_tool_call(tool_call, message)
        return result.display_content if result.ok else None

    @staticmethod
    def _tool_result_display_text(result: str | ToolResult | None) -> str | None:
        if isinstance(result, ToolResult):
            if not result.ok:
                return None
            return result.display_content if result.display_content is not None else result.content
        return result

    @staticmethod
    def _tool_result_history_text(result: str | ToolResult | None) -> str:
        if isinstance(result, ToolResult):
            return result.model_context or result.display_content or result.content or ""
        return result or ""

    def _tool_query_price(self, args: dict) -> ToolResult | None:
        message = args.get("__message", "")
        item_name = args.get("item_name", message)
        item_id = self._resolve_item_id_for_command(item_name)
        if not item_id:
            return None
        contexts = self._contexts_for_items([item_id])
        if not contexts:
            return None
        self.session.update([item_id])
        det = _deterministic_trade_intent_answer(message, contexts)
        display = det if det else fallback_answer(message, contexts)
        model_context = safe_query_price_context_from_contexts(contexts)
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _tool_query_set(self, args: dict) -> str | None:
        message = args.get("__message", "")
        warframe_name = args.get("warframe_name", message)
        result = price_warframe_query(warframe_name, self.warframe_items, self.order_fetcher)
        return result or None

    def _tool_scan_favorites(self, args: dict) -> str | None:
        return self._handle_scan_command()

    def _tool_set_alert(self, args: dict) -> str | None:
        item_name = args.get("item_name", "")
        direction = args.get("direction", "below")
        price = args.get("price", 0)
        try:
            price = int(price)
        except (ValueError, TypeError):
            return None
        item_id = self._resolve_item_id_for_command(item_name)
        if not item_id:
            return None
        threshold_text = "低于" if direction == "below" else "高于"
        note = f"{display_item_name(item_id)} {threshold_text} {price}p 提醒"
        self.memory = self.memory.with_price_alert(item_id, direction, price, note)
        self._persist_memory()
        return f"已添加提醒: {note}"

    def _tool_price_trend(self, args: dict) -> str | None:
        message = args.get("__message", "")
        item_name = args.get("item_name", message)
        item_id = self._resolve_item_id_for_command(item_name)
        if not item_id or not self.price_db:
            return None
        trend = self.price_db.trend_summary(item_id)
        if trend:
            return f"{display_item_name(item_id)}\n{trend}"
        return f"{display_item_name(item_id)}\n暂无历史价格数据"

    def _tool_query_missing_parts(self, args: dict) -> str | None:
        message = args.get("__message", "")
        warframe_name = args.get("warframe_name", message)
        owned_raw = args.get("owned_parts", "")
        owned_parts = [p.strip() for p in owned_raw.replace("、", ",").replace("，", ",").split(",") if p.strip()]
        return self._query_missing_parts(warframe_name, owned_parts)

    def _tool_relic_value(self, args: dict) -> ToolResult:
        from .relic_value import analyze_relic_value, format_relic_value_for_display, format_relic_value_for_model
        from .relics import get_relic_db

        relic_name = (args.get("relic_name") or args.get("__message") or "").strip()
        for prefix in ("/relic value", "/relic 估值", "/relic 价值"):
            if relic_name.lower().startswith(prefix):
                relic_name = relic_name[len(prefix):].strip()
        target_part = (args.get("target_part") or "").strip()
        if not relic_name:
            return ToolResult(ok=False, error="缺少遗物名称")
        db = get_relic_db()
        db.load(self.warframe_items or None)
        info = db.find_by_relic(relic_name)
        if not info:
            return ToolResult(ok=False, error=f"未找到与 '{relic_name}' 相关的遗物。")
        game_data = GameDataStore()
        report = analyze_relic_value(info, self.order_fetcher, game_data)
        display = format_relic_value_for_display(report, target_part=target_part or None)
        model_context = format_relic_value_for_model(report)
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _tool_farming_route(self, args: dict) -> ToolResult:
        from .farming_route import analyze_farming_route, format_farming_route_for_display, format_farming_route_for_model
        from .relics import get_relic_db

        target = (args.get("target") or args.get("item_name") or args.get("relic_name") or args.get("__message") or "").strip()
        if not target:
            return ToolResult(ok=False, error="缺少刷取目标")
        db = get_relic_db()
        db.load(self.warframe_items or None)
        game_data = GameDataStore()
        try:
            fissures = EventTracker().get_active_fissures()
        except Exception:
            fissures = []
        report = analyze_farming_route(target, db, game_data, fissures=fissures, order_fetcher=self.order_fetcher)
        display = format_farming_route_for_display(report)
        model_context = format_farming_route_for_model(report)
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _tool_general_chat(self, args: dict) -> str | None:
        return None

    @staticmethod
    def _format_trade_plan_display(plan: dict) -> list[str]:
        lines = [f"   策略: {plan.get('display_strategy', plan.get('strategy', ''))}"]
        lines.append(
            f"   成本: {plan.get('total_cost', 0)}p → 收入: {plan.get('total_revenue', 0)}p | "
            f"利润: +{plan.get('profit', 0)}p | ROI: {plan.get('roi_pct', 0)}%"
        )
        buy_steps = plan.get("buy_steps") or []
        if buy_steps:
            lines.append(f"   你需要买入 {sum(int(step.get('quantity') or 0) for step in buy_steps)} 个:")
            for step in buy_steps:
                lines.append(
                    f"   - {step.get('label')}: {step.get('player')} {step.get('unit_price')}p × "
                    f"{step.get('quantity')} = {step.get('subtotal')}p · {step.get('market_url')} · {step.get('profile_url')}"
                )
                if step.get("whisper"):
                    lines.append(f"     {step['whisper']}")
        sell_steps = plan.get("sell_steps") or []
        if sell_steps:
            lines.append("   你可以卖给:")
            for step in sell_steps:
                lines.append(
                    f"   - {step.get('label')}: {step.get('player')} {step.get('unit_price')}p × "
                    f"{step.get('quantity')} = {step.get('subtotal')}p · {step.get('market_url')} · {step.get('profile_url')}"
                )
                if step.get("whisper"):
                    lines.append(f"     {step['whisper']}")
        return lines

    def _tool_mod_flipper(self, args: dict) -> ToolResult:
        from .mod_flipper import format_mod_flip_results_for_model, scan_all_mod_flips
        from .scout import scout_mod_candidates
        min_profit = int(args.get("min_profit", 5))
        limit = int(args.get("limit", 20))
        personal_profile = self._build_personal_profile()
        results = scan_all_mod_flips(
            self.warframe_items or [],
            self.order_fetcher,
            min_profit=min_profit,
            limit=limit,
            scout_fn=scout_mod_candidates,
            personal_profile=personal_profile,
        )
        model_context = format_mod_flip_results_for_model(results, min_profit=min_profit, limit=limit)
        if not results:
            display = "没有找到符合条件的 Mod 翻转机会"
            return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)
        lines = ["## Mod/赋能翻转机会\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r.display_name}**")
            if r.trade_plan:
                lines.extend(self._format_trade_plan_display(r.trade_plan))
            else:
                lines.append(f"   买 R0: {r.r0_buy_price}p → 卖 R{r.max_rank}: {r.r10_sell_price}p")
                if r.r0_seller:
                    lines.append(f"   买入对象: {r.r0_seller['player']} {r.r0_seller['price']}p · {r.r0_seller['whisper']}")
                if r.max_rank_buyer:
                    lines.append(f"   出售对象: {r.max_rank_buyer['player']} {r.max_rank_buyer['price']}p · {r.max_rank_buyer['whisper']}")
                if r.market_url:
                    lines.append(f"   市场链接: {r.market_url}")
            lines.append(f"   每千内融: {r.plat_per_1k_endo:.1f}p | 48h成交: {r.volume_48h or '未知'}笔")
        display = "\n".join(lines)
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _tool_set_profit(self, args: dict) -> ToolResult:
        from .set_profit import format_set_profit_results_for_model, scan_all_set_profits
        from .scout import scout_set_candidates
        min_profit = int(args.get("min_profit", 5))
        limit = int(args.get("limit", 20))
        personal_profile = self._build_personal_profile()
        results = scan_all_set_profits(
            self.warframe_items or [],
            self.order_fetcher,
            min_profit=min_profit,
            limit=limit,
            scout_fn=scout_set_candidates,
            personal_profile=personal_profile,
        )
        model_context = format_set_profit_results_for_model(results, min_profit=min_profit, limit=limit)
        if not results:
            display = "没有找到符合条件的套装利润机会"
            return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)
        lines = ["## Prime 套装利润排行榜\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r.display_name}**")
            if r.trade_plan:
                lines.extend(self._format_trade_plan_display(r.trade_plan))
            else:
                lines.append(f"   最佳策略: {r.best_strategy} | 利润: +{r.best_profit}p")
                lines.append(f"   成本/收入: {r.parts_sell_total if r.best_strategy == '买部件→卖套装' else r.set_buy_price or 0}p → {r.set_sell_price if r.best_strategy == '买部件→卖套装' else r.parts_buy_total}p")
                if r.market_url:
                    lines.append(f"   市场链接: {r.market_url}")
            if r.volume_48h:
                lines.append(f"   48h成交: {r.volume_48h}笔")
        display = "\n".join(lines)
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _tool_investment_advisor(self, args: dict) -> ToolResult:
        from .investment import format_prime_investment_results_for_model, resolve_investment_preference_defaults, scan_prime_investments
        from .scout import scout_investment_candidates
        requested_budget = int(args["budget"]) if args.get("budget") not in (None, "") else None
        requested_min_roi = float(args["min_roi"]) if args.get("min_roi") not in (None, "") else None
        budget, min_roi = resolve_investment_preference_defaults(
            self.memory,
            budget=requested_budget,
            min_roi_pct=requested_min_roi,
            fallback_budget=1000,
            fallback_min_roi_pct=10.0,
        )
        limit = int(args.get("limit", 15))
        personal_profile = self._build_personal_profile()
        results = scan_prime_investments(
            self.warframe_items or [],
            self.order_fetcher,
            budget=budget,
            min_roi_pct=min_roi,
            limit=limit,
            scout_fn=lambda groups: scout_investment_candidates(groups, budget=budget),
            personal_profile=personal_profile,
        )
        model_context = format_prime_investment_results_for_model(results, budget=budget, min_roi_pct=min_roi, limit=limit)
        if not results:
            display = "没有找到符合条件的投资机会"
            return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)
        lines = [f"## 投资顾问 (预算 {budget}p, ROI >= {min_roi}%)\n"]
        for i, r in enumerate(results, 1):
            risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(r.risk_level, "⚪")
            lines.append(f"{i}. **{r.display_name}** {risk_icon}")
            if r.trade_plan:
                lines.extend(self._format_trade_plan_display(r.trade_plan))
            else:
                lines.append(f"   买入成本: {r.buy_cost}p → 卖出: {r.sell_price}p | 每套利润: +{r.profit_per_set}p")
            lines.append(f"   ROI: {r.roi_pct:.1f}% | 可购 {r.sets_affordable} 套 | 总利润: +{r.total_profit}p")
            lines.append(f"   48h成交: {r.volume_48h or '未知'}笔 | 风险: {r.risk_level}")
        display = "\n".join(lines)
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _tool_query_events(self, args: dict) -> ToolResult:
        event_type = args.get("type")
        display, model_context = self._query_events_result(event_type=event_type, source_query=args.get("__message"))
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _tool_deep_analysis(self, args: dict) -> str | None:
        message = args.get("__message", "")
        item_name = args.get("item_name", message)
        return self._deep_analysis(item_name)

    def _tool_expert(self, domain: str, args: dict) -> ToolResult:
        orchestrator = self._expert_orchestrator()
        question = str(args.get("question") or args.get("__message") or "")
        context = str(args.get("context") or "")
        return run_expert(
            ExpertRequest(
                domain=domain,
                question=question,
                context=context,
            ),
            orchestrator,
        )

    def _expert_orchestrator(self):
        if self.model_orchestrator is not None:
            return self.model_orchestrator
        from .llm import _cloud_chat_sync, chat_with_ollama
        from .model_orchestrator import ModelOrchestrator
        self.model_orchestrator = ModelOrchestrator(
            cloud_call=lambda messages, model: _cloud_chat_sync(messages, model=model),
            local_call=chat_with_ollama,
        )
        return self.model_orchestrator

    def _tool_riven_search(self, args: dict) -> ToolResult:
        return self._handle_riven_search(args)

    def _handle_limited_event_query(self, source_query: str | None = None) -> str:
        from .events import EventTracker
        try:
            tracker = self.event_tracker or EventTracker()
            if not self.event_tracker:
                tracker.load_cache()
            events = tracker.get_limited_events()
        except Exception as exc:
            logger.debug("限时活动查询失败: %s", exc)
            return "暂时无法获取限时活动信息。"

        requested_labels = _limited_activity_labels_from_query(source_query)
        if requested_labels:
            events = _filter_limited_events_for_query(events, source_query)
            if not events:
                return f"当前没有检测到{'、'.join(requested_labels)}。"
        if not events:
            return "当前没有检测到热美亚裂缝、兽之腹等限时活动。"
        lines = ["当前限时活动:"]
        for event in events:
            lines.append(f"- {event.description}")
        return "\n".join(lines)

    def _query_events_result(self, event_type: str | None = None, source_query: str | None = None) -> tuple[str, str]:
        from .events import EventTracker, format_events_for_display, format_events_for_model, is_supported_query_event_type
        normalized_type = _normalize_query_event_type_arg(event_type)
        if not is_supported_query_event_type(normalized_type):
            return format_events_for_display([], normalized_type), format_events_for_model([], normalized_type)
        if normalized_type == "void_fissure":
            try:
                tracker = self.event_tracker or EventTracker()
                if not self.event_tracker:
                    tracker.load_cache()
                fissures = tracker.get_active_fissures()
            except Exception as exc:
                logger.debug("虚空裂缝查询失败: %s", exc)
                fissures = []
            if fissures:
                return (
                    _format_void_fissures_for_chat(fissures, source_query),
                    _format_void_fissures_for_model(fissures, source_query),
                )
        try:
            tracker = self.event_tracker or EventTracker()
            if not self.event_tracker:
                tracker.load_cache()
            events = tracker.get_active_events()
        except Exception as exc:
            logger.debug("事件查询失败: %s", exc)
            display = "暂时无法获取游戏活动信息。"
            return display, "tool=query_events\nerror=fetch_failed"
        return format_events_for_display(events, normalized_type), format_events_for_model(events, normalized_type)

    def _handle_specific_event_query(self, message: str) -> str:
        display, _ = self._query_events_result(event_type=_event_type_from_message(message) or message, source_query=message)
        return display

    def _try_deterministic_riven(self, message: str) -> ToolResult | None:
        """确定性紫卡路由：直接解析查询，不依赖 LLM 路由。"""
        from .riven import parse_riven_query, search_rivens, format_riven_results, format_riven_results_for_model

        query = parse_riven_query(message, weapon_resolver=self._resolve_weapon_for_riven)
        if not query:
            query = self._try_model_riven_parse(message)
            if not query:
                return None
            seller_statuses = _riven_statuses_from_message(message)
            if seller_statuses is not None:
                query.seller_statuses = seller_statuses
        else:
            seller_statuses = _riven_statuses_from_message(message, default_online=True)
            if seller_statuses is not None:
                query.seller_statuses = seller_statuses
        results = search_rivens(query, page=1, page_size=self.session.last_riven_page_size)
        self.session.last_riven_query = query
        self.session.last_riven_page = 1
        display = format_riven_results(query, results)
        if _is_riven_value_question(message):
            display += "\n\n" + _build_riven_value_analysis(results)
        model_context = format_riven_results_for_model(query, results)
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _try_model_riven_parse(self, message: str):
        """???????????????????????"""
        from .riven import RivenQuery, RIVEN_ATTRIBUTES, COMPOUND_KEYWORDS
        from .dictionary import normalize_market_id

        prompt = (
            "???? Warframe ??????? JSON???? JSON??????\n"
            "??: weapon, positive_attrs, negative_attrs, no_negative, seller_status?\n"
            "???????? url_name??? critical_chance?critical_damage?multishot?base_damage_/_melee_damage?\n"
            "seller_status ??? ingame?online?all ??????\n"
            "?: {\"weapon\":\"dual_toxocyst\",\"positive_attrs\":[\"critical_chance\",\"critical_damage\"],"
            "\"negative_attrs\":[],\"no_negative\":true,\"seller_status\":\"online\"}\n"
            f"??: {message}"
        )
        try:
            raw = self._call_llm_messages([
                {"role": "system", "content": "?? Warframe ??????????? JSON?"},
                {"role": "user", "content": prompt},
            ])
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1:
                return None
            data = json.loads(raw[start:end + 1])
        except Exception as exc:
            logger.debug("????????: %s", exc)
            return None

        weapon_text = str(data.get("weapon") or "").strip()
        weapon_url = self._resolve_weapon_for_riven(weapon_text) or normalize_market_id(weapon_text)
        if not weapon_url:
            return None
        # 紫卡API不接受变体武器名，强制还原为基础版
        weapon_url = self._normalize_riven_weapon_url(weapon_url)
        message_weapon_url = self._resolve_weapon_for_riven(message)
        if message_weapon_url:
            weapon_url = self._normalize_riven_weapon_url(message_weapon_url)
        elif weapon_text.lower() not in message.lower():
            return None
        valid_attrs = set(RIVEN_ATTRIBUTES.values()) | {attr for attrs in COMPOUND_KEYWORDS.values() for attr in attrs}
        positive = [attr for attr in data.get("positive_attrs", []) if attr in valid_attrs]
        negative = [attr for attr in data.get("negative_attrs", []) if attr in valid_attrs]
        status = str(data.get("seller_status") or "").lower()
        seller_statuses = RIVEN_ONLINE_STATUSES
        if status == "ingame":
            seller_statuses = RIVEN_INGAME_STATUSES
        elif status == "online":
            seller_statuses = RIVEN_ONLINE_STATUSES
        elif status == "all":
            seller_statuses = RIVEN_ALL_STATUSES
        return RivenQuery(
            weapon_url_name=weapon_url,
            positive_attrs=list(dict.fromkeys(positive)),
            negative_attrs=list(dict.fromkeys(negative)),
            no_negative=bool(data.get("no_negative")),
            seller_statuses=seller_statuses,
        )

    def _try_riven_followup(self, message: str) -> ToolResult | None:
        """基于上一次紫卡查询的追问（翻页/在线/便宜/无负等过滤条件）。"""
        from .riven import _extract_max_price, search_rivens, format_riven_results, format_riven_results_for_model
        query = self.session.last_riven_query
        if query is None:
            return None
        lowered = message.lower()
        next_page = any(kw in lowered for kw in ["下一组", "下一批", "下页", "再来", "更多", "继续"])
        prev_page = any(kw in lowered for kw in ["上一组", "上一批", "上页", "前一页"])
        seller_statuses = _riven_statuses_from_message(message)
        status_filter = seller_statuses is not None
        cheap_only = any(kw in lowered for kw in ["便宜", "最便宜", "低价"])
        no_negative = any(kw in lowered for kw in ["无负", "不要负", "没负"])
        max_price = _extract_max_price(message)
        if not (next_page or prev_page or status_filter or cheap_only or no_negative or max_price is not None):
            return None

        from dataclasses import replace
        query = replace(query)
        page = self.session.last_riven_page
        suffix_parts = []

        if next_page:
            page += 1
        elif prev_page:
            page = max(1, page - 1)
        else:
            page = 1
            if seller_statuses is not None:
                query.seller_statuses = seller_statuses
                suffix_parts.append(_riven_status_label(seller_statuses))
            if no_negative:
                query.no_negative = True
                suffix_parts.append("无负")
            if max_price is not None:
                query.max_price = max_price
                suffix_parts.append(f"≤{max_price}p")
            if cheap_only:
                suffix_parts.append("最低价")

        results = search_rivens(query, page=page, page_size=self.session.last_riven_page_size)
        boundary_note = ""
        if next_page and results.page == self.session.last_riven_page:
            boundary_note = "\n\n已经是最后一组。"
        elif prev_page and self.session.last_riven_page == 1:
            boundary_note = "\n\n已经是第一组。"
        self.session.last_riven_query = query
        self.session.last_riven_page = results.page
        suffix = f"（{','.join(suffix_parts)}）" if suffix_parts else ""
        text = format_riven_results(query, results)
        if suffix:
            text = text.replace("紫卡搜索结果", f"紫卡搜索结果{suffix}", 1)
        display = text + boundary_note
        model_context = format_riven_results_for_model(query, results)
        if suffix:
            model_context += f"\nfollowup_filters={suffix}"
        if boundary_note:
            model_context += f"\nboundary_note={boundary_note.strip()}"
        self.session.update([query.weapon_url_name], "riven", "riven_followup")
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _handle_riven_search(self, args: dict) -> ToolResult:
        """处理紫卡搜索工具调用。"""
        from .riven import RivenQuery, parse_riven_query, search_rivens, format_riven_results, format_riven_results_for_model, RIVEN_ATTRIBUTES, COMPOUND_KEYWORDS

        weapon = args.get("weapon", "")
        if not weapon:
            display = "请指定武器名称，如：斯特朗双爆紫卡无负"
            return ToolResult(ok=True, content=display, display_content=display, model_context="tool=riven_search\nerror=missing_weapon")

        # 构建查询消息用于解析属性（始终包含"紫卡"关键词，负向属性加"负"前缀）
        fake_msg = weapon + "紫卡"
        if args.get("positive"):
            fake_msg += args["positive"]
        if args.get("negative"):
            # LLM 返回的 negative 参数如 "暴击率"，需加"负"前缀以被 _extract_attributes 识别
            neg_text = args["negative"]
            if "无负" not in neg_text and "不要负" not in neg_text:
                for cn_name in RIVEN_ATTRIBUTES:
                    if cn_name in neg_text and f"负{cn_name}" not in neg_text:
                        neg_text = neg_text.replace(cn_name, f"负{cn_name}")
            fake_msg += neg_text

        query = parse_riven_query(
            fake_msg,
            weapon_resolver=self._resolve_weapon_for_riven,
        )
        if query:
            # 紫卡API不接受变体武器名，强制还原为基础版
            query.weapon_url_name = self._normalize_riven_weapon_url(query.weapon_url_name)
        else:
            # 回退：手动构建查询
            from .dictionary import normalize_market_id
            weapon_url = normalize_market_id(weapon)
            positive = []
            no_negative = False
            negative_attrs = []
            if args.get("positive"):
                pos_text = args["positive"]
                for kw, attrs in COMPOUND_KEYWORDS.items():
                    if kw in pos_text:
                        positive.extend(attrs)
                for cn, api in RIVEN_ATTRIBUTES.items():
                    if cn in pos_text and api not in positive:
                        positive.append(api)
            if args.get("negative"):
                neg_text = args["negative"]
                if "无负" in neg_text or "不要负" in neg_text:
                    no_negative = True
                else:
                    for cn, api in RIVEN_ATTRIBUTES.items():
                        if cn in neg_text:
                            negative_attrs.append(api)
            query = RivenQuery(weapon_url_name=self._normalize_riven_weapon_url(weapon_url), positive_attrs=positive, negative_attrs=negative_attrs, no_negative=no_negative)

        # 应用 max_price 参数
        if args.get("max_price"):
            query.max_price = int(args["max_price"])
        if args.get("seller_status") in RIVEN_INGAME_STATUSES:
            query.seller_statuses = RIVEN_INGAME_STATUSES
        elif args.get("seller_status") in RIVEN_ONLINE_STATUSES or args.get("online_only"):
            query.seller_statuses = RIVEN_ONLINE_STATUSES
        elif args.get("seller_status") in ("all", "offline"):
            query.seller_statuses = RIVEN_ALL_STATUSES
        else:
            query.seller_statuses = RIVEN_ONLINE_STATUSES

        results = search_rivens(query, page=1, page_size=self.session.last_riven_page_size)
        self.session.last_riven_query = query
        self.session.last_riven_page = 1
        display = format_riven_results(query, results)
        model_context = format_riven_results_for_model(query, results)
        return ToolResult(ok=True, content=display, display_content=display, model_context=model_context)

    def _resolve_weapon_for_riven(self, name: str) -> str | None:
        """解析武器名到 market weapon_url_name（紫卡必须用普通版武器名）。"""
        from .dictionary import normalize_market_id
        normalized = normalize_market_id(name)

        # 先检查别名是否直接指向武器（不含 _set/_mod 等非武器后缀）
        alias_id = self.resolver.aliases.get(
            __import__("warframe_agent.dictionary", fromlist=["normalize_lookup_key"]).normalize_lookup_key(name)
        )
        if alias_id and not any(alias_id.endswith(s) for s in ["_set", "_mod", "_blueprint"]):
            return alias_id

        # 尝试字典解析
        try:
            result = self.resolver.resolve(name)
            item_id = result.item_id
            # 如果结果看起来像武器名（无 _set/_mod 后缀），使用它
            if not any(item_id.endswith(s) for s in ["_set", "_mod", "_blueprint"]):
                return item_id
        except Exception:
            pass

        # 回退1：如果别名指向 _prime_set，提取基础武器名（如"西诺斯" → cernos_prime_set → cernos）
        for candidate_id in [alias_id]:
            if not candidate_id:
                continue
            base = self._extract_riven_base_from_set(candidate_id)
            if base:
                return base

        # 回退2：直接用 normalized 名（如 "rubico", "soma", "strun"）
        if normalized and len(normalized) >= 2:
            return normalized
        return None

    @staticmethod
    def _extract_riven_base_from_set(item_id: str) -> str | None:
        """从 _set/_blueprint 后缀的 item_id 提取基础武器名。
        例：cernos_prime_set → cernos, akstiletto_prime_set → akstiletto.
        """
        import re
        # 移除 _set / _blueprint 后缀
        m = re.match(r'^(.*?)(?:_prime|_wraith|_vandal)?_(?:set|blueprint|chassis|systems|neuroptics)$', item_id)
        if m:
            base = m.group(1)
            if base:
                return base
        return None

    def _normalize_riven_weapon_url(self, weapon_url: str) -> str:
        """将变体武器名还原为基础版（紫卡API不接受变体前缀）。"""
        import re
        variant_prefixes = [
            "sancti_", "vaykor_", "prisma_", "wraith_", "vandal_",
            "mutalist_", "kuva_", "tenet_", "dex_",
            "secura_", "rakta_", "detonite_", "telos_", "cobra_",
        ]
        w = weapon_url.lower()
        for prefix in sorted(variant_prefixes, key=len, reverse=True):  # 长前缀优先
            if w.startswith(prefix):
                base = w[len(prefix):]
                # 验证基础版在紫卡武器列表中（如果不在，保持变体）
                # 注意：这里只做本地修正，不查API（避免额外请求）
                return base
        return weapon_url

    def _deep_analysis(self, item_name: str) -> str | None:
        """使用云端大模型对物品进行多维度深度分析。"""
        item_id = self._resolve_item_id_for_command(item_name)
        if not item_id:
            return f"未找到物品: {item_name}"

        # 收集数据
        from .market import best_buyers, best_sellers
        try:
            orders = self.order_fetcher(item_id)
        except Exception:
            orders = []

        sellers = best_sellers(orders) if orders else []
        buyers = best_buyers(orders) if orders else []
        sell_price = sellers[0].platinum if sellers else None
        buy_price = buyers[0].platinum if buyers else None

        # 知识库数据
        stats_text = ""
        if self.knowledge:
            stats = self.knowledge.get_item_stats(item_id)
            if stats:
                stats_text = (
                    f"趋势: {stats.trend}, 波动率: {stats.volatility:.1f}%, "
                    f"滚动均价(卖): {stats.rolling_avg_sell:.0f}p, 滚动均价(收): {stats.rolling_avg_buy:.0f}p, "
                    f"扫描次数: {stats.scan_count}"
                )

        # 游戏数据
        game_text = ""
        if self.game_data:
            name = display_item_name(item_id)
            mod_info = self.game_data.get_mod_info(name)
            if mod_info:
                game_text = mod_info
            ducat = self.game_data.get_ducat_value(item_id)
            if ducat:
                game_text += f"\n杜卡特值: {ducat}"

        # 价格历史
        history_text = ""
        if self.price_db:
            trend = self.price_db.trend_summary(item_id)
            if trend:
                history_text = trend

        # 构建分析 prompt
        analysis_prompt = (
            f"你是资深 Warframe 交易分析师。请对以下物品进行多维度深度分析。\n\n"
            f"## 物品: {display_item_name(item_id)} ({item_id})\n\n"
            f"## 当前市场\n"
            f"- 最低卖价: {sell_price}p\n"
            f"- 最高收价: {buy_price}p\n"
            f"- 价差: {(sell_price - buy_price) if sell_price is not None and buy_price is not None else '未知'}{'p' if sell_price is not None and buy_price is not None else ''}\n\n"
        )
        if stats_text:
            analysis_prompt += f"## 知识库数据\n{stats_text}\n\n"
        if game_text:
            analysis_prompt += f"## 游戏数据\n{game_text}\n\n"
        if history_text:
            analysis_prompt += f"## 价格趋势\n{history_text}\n\n"

        analysis_prompt += (
            "请从以下维度分析：\n"
            "1. **价格评估**: 当前价格是否合理？偏高还是偏低？\n"
            "2. **趋势判断**: 短期内会涨还是跌？\n"
            "3. **风险评估**: 波动率、流动性、封存风险\n"
            "4. **投资建议**: 现在买入/卖出/观望？理由是什么？\n"
            "5. **操作建议**: 如果要交易，推荐价格和话术\n\n"
            "用中文回答，简洁有力，附带具体数字。"
        )

        try:
            from .llm import _cloud_chat_sync
            result = _cloud_chat_sync([
                {"role": "system", "content": "你是 Warframe 交易分析师，擅长多维度市场分析。"},
                {"role": "user", "content": analysis_prompt},
            ])
            return f"## 深度分析: {display_item_name(item_id)}\n\n{result}"
        except Exception as exc:
            logger.warning("云端深度分析失败，回退本地: %s", exc)
            # 回退到本地模型
            try:
                from .llm import chat_with_ollama
                result = chat_with_ollama([
                    {"role": "system", "content": "你是 Warframe 交易分析师。"},
                    {"role": "user", "content": analysis_prompt},
                ])
                return f"## 深度分析: {display_item_name(item_id)}\n\n{result}"
            except Exception:
                return f"深度分析失败: {item_name}。请稍后重试。"

    def _query_missing_parts(self, warframe_name: str, owned_parts: list[str]) -> str | None:
        from .warframes import build_prime_groups, _load_items, PARTS, _render_missing_parts
        items = self.warframe_items or _load_items()
        groups = build_prime_groups(items)
        # 尝试匹配 base_id
        name_lower = warframe_name.lower().replace(" ", "_")
        base_id = None
        for gid, group in groups.items():
            if name_lower in gid or gid.startswith(name_lower):
                base_id = gid
                break
        if not base_id:
            return None
        group = groups.get(base_id)
        if not group:
            return None
        # 将 owned_parts 转为 part key
        owned_keys = []
        for part in owned_parts:
            part_lower = part.lower().strip()
            for key, info in PARTS.items():
                if part_lower in [t.lower() for t in info["terms"]]:
                    owned_keys.append(key)
                    break
        return _render_missing_parts(group, owned_keys, self.order_fetcher)

    def _remember_common_question(self, message: str) -> None:
        self.memory = self.memory.with_common_question(message)
        if len(self.memory.common_questions) % 5 == 0:
            self.memory = self.memory.analyze_and_update_profile()
        self._persist_memory()

    def _persist_memory(self) -> None:
        try:
            self.memory.save(self.memory_path)
        except OSError as exc:
            logger.debug("记忆持久化失败，继续回答: %s", exc)

    def _reload_memory(self) -> None:
        if not Path(self.memory_path).exists():
            return
        disk = AgentMemory.load(self.memory_path)
        self.memory = replace(
            disk,
            common_questions=self.memory.common_questions,
            user_profile=self.memory.user_profile,
            recent_suggestions=self.memory.recent_suggestions,
        )

    def _contexts_for_items(self, item_ids: list[str]) -> list[ItemContext]:
        contexts = []
        for item_id in item_ids[:3]:
            try:
                ctx = build_item_context_result(item_id, self.order_fetcher(item_id))
                if self.price_db:
                    self.price_db.record(item_id, ctx.best_sell_price, ctx.best_buy_price)
                    trend = self.price_db.trend_summary(item_id)
                    if trend:
                        ctx = ItemContext(
                            item_id=ctx.item_id,
                            text=f"{ctx.text}\n{trend}",
                            best_sell_price=ctx.best_sell_price,
                            best_buy_price=ctx.best_buy_price,
                            best_seller=ctx.best_seller,
                            best_buyer=ctx.best_buyer,
                            model_context=f"{ctx.model_context}\n{trend}" if ctx.model_context else None,
                        )
                contexts.append(ctx)
            except requests.RequestException as exc:
                contexts.append(ItemContext(item_id=item_id, text=f"物品: {display_item_name(item_id)}\n查询失败: {exc}"))
        return contexts

    def _contexts_for_message(self, message: str) -> list[ItemContext]:
        item_ids = self._item_ids_from_alias_substrings(message)
        if not item_ids:
            try:
                item_ids.append(self.resolver.resolve(message).item_id)
            except (LookupError, ValueError):
                for token in _message_tokens(message):
                    try:
                        item_id = self.resolver.resolve(token).item_id
                    except (LookupError, ValueError):
                        continue
                    if item_id not in item_ids:
                        item_ids.append(item_id)
        if not item_ids:
            # 纯指令类查询不应走 RAG 物品匹配，避免返回无关结果
            _COMMAND_ONLY = {"返回", "帮我看", "在线玩家", "在线的", "便宜的", "最便宜的",
                             "推荐", "建议", "哪个好", "哪些好"}
            if not any(kw in message for kw in _COMMAND_ONLY):
                item_ids = self.rag_search(message)
        contexts = []
        for item_id in item_ids[:3]:
            try:
                ctx = build_item_context_result(item_id, self.order_fetcher(item_id))
                if self.price_db:
                    self.price_db.record(item_id, ctx.best_sell_price, ctx.best_buy_price)
                    trend = self.price_db.trend_summary(item_id)
                    if trend:
                        ctx = ItemContext(
                            item_id=ctx.item_id,
                            text=f"{ctx.text}\n{trend}",
                            best_sell_price=ctx.best_sell_price,
                            best_buy_price=ctx.best_buy_price,
                            best_seller=ctx.best_seller,
                            best_buyer=ctx.best_buyer,
                            model_context=f"{ctx.model_context}\n{trend}" if ctx.model_context else None,
                        )
                contexts.append(ctx)
            except requests.RequestException as exc:
                contexts.append(ItemContext(item_id=item_id, text=f"物品: {display_item_name(item_id)}\n查询失败: {exc}"))
        return contexts

    def _default_rag_search(self, message: str) -> list[str]:
        return [result.item_id for result in smart_search_rag(message, limit=3)]

    def _item_ids_from_alias_substrings(self, message: str) -> list[str]:
        normalized_message = normalize_lookup_key(message)
        manual_aliases = getattr(self.resolver, "aliases", {}) or {}
        generated_aliases = getattr(self.resolver, "generated_aliases", {}) or {}
        manual_matches = _matching_alias_items(normalized_message, manual_aliases)
        if manual_matches:
            return manual_matches
        return _matching_alias_items(normalized_message, generated_aliases)


def build_chat_prompt(message: str, contexts: list[ItemContext], memory: AgentMemory) -> str:
    context_text = safe_query_price_context_from_contexts(contexts)
    memory_text = _memory_prompt(contexts, memory)
    return (
        "你是资深星际战甲玩家和中文交易助手。请用老玩家视角回答，重点说明能不能买、能不能卖、价差和注意事项。"
        "所有识别出的商品名必须尽量使用 `中文名 / English Name / market_id` 格式。"
        "所有价格单位都是 Warframe 白金 platinum，绝不是美元、人民币或其他现实货币。"
        "不要编造没有提供的实时价格。\n\n"
        f"长期记忆与偏好:\n{memory_text}\n\n"
        f"实时市场安全摘要:\n{context_text}\n\n"
        f"玩家问题: {message}\n"
        "请基于摘要给出简洁中文建议；不要编造玩家名、profile 链接或私聊命令。"
    )


def build_system_prompt(
    memory: AgentMemory,
    contexts: list[ItemContext] | None = None,
    market_context: str | None = None,
) -> str:
    """构建 system 消息（persona + CoT 引导 + Few-shot + 记忆 + 市场上下文）"""
    parts = []

    # 1. 角色定义 + 行为准则
    parts.append(
        "你是资深星际战甲玩家和中文交易助手。\n\n"
        "## 行为准则\n"
        "- 所有商品名使用 `中文名 / English Name / market_id` 格式\n"
        "- 所有价格单位都是白金(platinum)，不是现实货币\n"
        "- 绝不编造未提供的实时价格，数据不足时明确说明\n"
        "- 只有工具/display 已明确提供交易对象时才可转述私聊命令，不能凭安全摘要编造玩家名\n\n"
        "## 回答策略\n"
        "价格查询类问题，按以下步骤思考：\n"
        "1. 识别物品类型（Mod/战甲/赋能/遗物等）\n"
        "2. 分析当前市场数据（卖价、收价、价差）\n"
        "3. 结合趋势和事件给出建议\n"
        "4. 只有工具/display 已提供真实玩家名和私聊命令时才转述；否则不要编造玩家名或私聊命令\n\n"
        "投资/利润类问题，按以下步骤思考：\n"
        "1. 计算成本和预期收益\n"
        "2. 评估流动性（成交量）\n"
        "3. 考虑风险因素（波动率、事件影响）\n"
        "4. 给出明确建议（买/卖/观望）"
    )

    # 2. Few-shot 示例
    parts.append(
        "\n## 示例\n\n"
        "玩家问题: 充沛赋能多少钱\n"
        "回答:\n"
        "充沛赋能 / Arcane Energize / arcane_energize\n"
        "最低卖价: 45p，最高收价: 35p，价差: 10p\n"
        "建议: 价差适中，适合直接购买。若界面已提供真实玩家私聊按钮，可使用复制命令；不要编造玩家名。\n\n"
        "玩家问题: 犀牛 Prime 一套多少钱，拆件买还是一套买\n"
        "回答:\n"
        "Rhino Prime / rhino_prime_set\n"
        "整套最低卖: 120p | 拆件买合计: 95p\n"
        "拆件比整套便宜 25p，建议拆件收。\n"
        "各部件: 蓝图 20p / 机体 30p / 头部 25p / 系统 20p"
    )

    # 3. 记忆注入（结构化）
    memory_text = _memory_prompt(contexts or [], memory)
    parts.append(f"\n## 用户画像与偏好\n{memory_text}")

    # 4. 市场智能注入
    if market_context:
        parts.append(f"\n## 市场智能\n{wrap_untrusted_model_text('market_context', market_context)}")

    return "\n".join(parts)


def build_chat_messages(
    message: str,
    contexts: list[ItemContext],
    memory: AgentMemory,
    history: list[dict[str, str]] | None = None,
    market_context: str | None = None,
) -> list[dict[str, str]]:
    """构建 Ollama chat messages 数组（支持多轮对话）"""
    messages = [{"role": "system", "content": build_system_prompt(memory, contexts, market_context)}]
    if history:
        messages.extend(history)
    if contexts:
        context_text = safe_query_price_context_from_contexts(contexts)
        messages.append({"role": "user", "content": f"实时市场安全摘要:\n{context_text}\n\n玩家问题: {message}\n请基于摘要给出简洁中文建议；不要编造玩家名、profile 链接或私聊命令。"})
    else:
        messages.append({"role": "user", "content": f"玩家问题: {message}\n请给出简洁中文建议。"})
    return messages


def _extract_platinum_amount(message: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:p|白金)", message, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _is_riven_value_question(message: str) -> bool:
    return any(keyword in message for keyword in ("值不值得", "值得买", "能买吗", "适合买", "评价", "分析"))


def _build_riven_value_analysis(results) -> str:
    rivens = list(getattr(results, "results", results) or [])
    if not rivens:
        return "购买分析: 当前没有可对比的紫卡订单，暂时不建议凭空估价。"
    priced = [r for r in rivens if getattr(r, "price", None) is not None]
    prices = [int(r.price) for r in priced]
    price_line = f"价格区间: {min(prices)}p - {max(prices)}p，低价参考约 {prices[0]}p。" if prices else "价格区间: 当前结果没有明确标价。"
    strong_stats = {
        "critical_chance": "暴击率",
        "critical_damage": "暴击伤害",
        "multishot": "多重",
        "base_damage_/_melee_damage": "基伤",
    }
    strong_hits = []
    negatives = []
    rerolls = []
    for riven in rivens[:5]:
        rerolls.append(getattr(riven, "re_rolls", 0))
        for attr in getattr(riven, "positive_attrs", []) or []:
            stat = attr.get("stat") if isinstance(attr, dict) else getattr(attr, "stat", "")
            if stat in strong_stats and strong_stats[stat] not in strong_hits:
                strong_hits.append(strong_stats[stat])
        for attr in getattr(riven, "negative_attrs", []) or []:
            stat = attr.get("stat") if isinstance(attr, dict) else getattr(attr, "stat", "")
            if stat and stat not in negatives:
                negatives.append(stat)
    stat_line = "词条: " + (f"看到 {', '.join(strong_hits)} 等有效词条。" if strong_hits else "当前前几条没有明显核心输出词条。")
    if negatives:
        stat_line += " 但有负词条，需要确认是否影响武器手感或输出。"
    reroll_line = f"洗卡: 前几条洗卡次数约 {min(rerolls)}-{max(rerolls)} 次，低洗可继续调整，高洗转手风险更高。" if rerolls else "洗卡: 未显示洗卡次数。"
    conclusion = "结论: 只建议把低价、词条匹配玩法的卡作为自用或小额尝试；不要把紫卡当稳定倒卖品，也不要高价追没有核心词条的卡。"
    return "\n".join(["购买分析:", price_line, stat_line, reroll_line, conclusion])


def _deterministic_trade_intent_answer(message: str, contexts: list[ItemContext]) -> str | None:
    # 多物品对比查询
    if detect_compare_query(message) and len(contexts) >= 2:
        return _render_comparison_table(contexts)
    # 趋势预测类查询
    if detect_trend_query(message) and len(contexts) == 1:
        return _render_trend_prediction(contexts[0])
    intent = detect_trade_intent(message)
    if intent == "overview" or len(contexts) != 1:
        return None
    return _render_trade_intent_context(contexts[0], intent)


def _render_trade_intent_context(context: ItemContext, intent: str) -> str | None:
    lines = [display_item_name(context.item_id)]
    if intent == "buy":
        lines.append(f"按你要买来看：当前最低卖价: {_price_text(context.best_sell_price)}")
        if context.best_seller:
            lines.append(f"推荐购买私聊: {build_whisper(context.best_seller.user_name, context.item_id, context.best_seller.platinum, 'sell')}")
        if context.best_buy_price is not None:
            lines.append(f"参考最高收价: {context.best_buy_price}p")
    elif intent == "sell":
        lines.append(f"按你要卖来看：当前最高收价: {_price_text(context.best_buy_price)}")
        if context.best_buyer:
            lines.append(f"推荐出售私聊: {build_whisper(context.best_buyer.user_name, context.item_id, context.best_buyer.platinum, 'buy')}")
        if context.best_sell_price is not None:
            lines.append(f"参考最低卖价: {context.best_sell_price}p")
    elif intent == "spread":
        lines.append(f"按你想看价差来看：最低卖价 {_price_text(context.best_sell_price)} / 最高收价 {_price_text(context.best_buy_price)}")
        if context.best_sell_price is not None and context.best_buy_price is not None:
            lines.append(f"当前价差: {context.best_sell_price - context.best_buy_price}p")
    else:
        return None
    return "\n".join(lines)


def _render_trend_prediction(context: ItemContext) -> str | None:
    """使用 price_history 预测趋势，返回确定性回答。"""
    try:
        price_db = PriceHistoryDB()
        # 获取事件上下文
        event_ctx = {}
        try:
            tracker = EventTracker()
            events = tracker.get_active_events()
            for e in events:
                if e.event_type == "baro_visit":
                    event_ctx["baro_active"] = True
        except Exception:
            pass
        prediction = price_db.predict_trend(context.item_id, event_context=event_ctx)
        if not prediction:
            return None
        lines = [f"**{display_item_name(context.item_id)}** 价格趋势分析"]
        direction_map = {"rising": "上涨 ↑", "falling": "下跌 ↓", "stable": "持平 →"}
        dir_text = direction_map.get(prediction["direction"], prediction["direction"])
        lines.append(f"趋势方向: {dir_text}")
        lines.append(f"当前价格: {prediction['current']}p")
        lines.append(f"预测价格: {prediction['predicted_next']}p")
        low, high = prediction["price_range"]
        lines.append(f"预测区间: {low}p ~ {high}p")
        lines.append(f"置信度: {prediction['confidence']:.0f}%")
        if prediction.get("event_factor"):
            lines.append(f"事件修正: {prediction['event_factor']}")
        lines.append(f"数据点: {prediction['data_points']} 个")
        if prediction["confidence"] < 30:
            lines.append("⚠ 数据量较少，预测仅供参考")
        return "\n".join(lines)
    except Exception as exc:
        logger.debug("趋势预测失败: %s", exc)
        return None


def _render_comparison_table(contexts: list[ItemContext]) -> str:
    """生成多物品对比表格。"""
    lines = ["物品对比"]
    header = "| 物品 | 最低卖价 | 最高收价 | 价差 | 建议 |"
    separator = "|------|---------|----------|------|------|"
    lines.append(header)
    lines.append(separator)

    for ctx in contexts:
        sell = f"{ctx.best_sell_price}p" if ctx.best_sell_price else "-"
        buy = f"{ctx.best_buy_price}p" if ctx.best_buy_price else "-"
        spread = ""
        advice = ""
        if ctx.best_sell_price and ctx.best_buy_price:
            s = ctx.best_sell_price - ctx.best_buy_price
            spread = f"{s}p"
            if s > 20:
                advice = "价差大，适合倒货"
            elif s < 5:
                advice = "价差小，直接买"
            else:
                advice = "价差适中"
        name = display_item_name(ctx.item_id)
        lines.append(f"| {name} | {sell} | {buy} | {spread} | {advice} |")

    # 推荐最优
    valid = [c for c in contexts if c.best_sell_price and c.best_buy_price]
    if valid:
        best = max(valid, key=lambda c: c.best_sell_price - c.best_buy_price)
        lines.append(f"\n推荐: **{display_item_name(best.item_id)}** 价差最大，适合交易")

    return "\n".join(lines)


def _price_text(price: int | None) -> str:
    return f"{price}p" if price is not None else "\u6682\u65e0"


def fallback_answer(message: str, contexts: list[ItemContext], llm_failed: bool = False) -> str:
    header = "(LLM 未响应，以下为实时订单数据)" if llm_failed else "我先按实时订单给你一个直接判断："
    lines = [header]
    for context in contexts:
        lines.append(context.text)
    return "\n\n".join(lines)


def call_ollama_chat(prompt: str) -> str:
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama Python package is not installed") from exc
    response = ollama.generate(model=config.MODEL_NAME, prompt=prompt)
    return response.get("response", "")


def call_ollama_router(prompt: str) -> str:
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama Python package is not installed") from exc
    response = ollama.generate(model=config.ROUTER_MODEL_NAME, prompt=prompt)
    return response.get("response", "")


def _memory_prompt(contexts: list[ItemContext], memory: AgentMemory) -> str:
    sections = []

    # 1. 触发的价格提醒（最高优先级）
    triggered_alerts = []
    for context in contexts:
        if context.best_sell_price is not None:
            for alert in memory.alerts_for(context.item_id, context.best_sell_price):
                triggered_alerts.append(alert)
    if triggered_alerts:
        alert_lines = [f"- {a.note or a.item_id}" for a in triggered_alerts]
        sections.append("[触发的提醒]\n" + "\n".join(alert_lines))

    # 2. 用户偏好
    pref_parts = [f"平台={memory.preferences.platform}"]
    if memory.user_profile:
        profile = memory.user_profile
        trade_text = {"buy": "偏好购买", "sell": "偏好出售"}.get(profile.preferred_trade_type, "均衡")
        pref_parts.append(f"交易风格={trade_text}")
        if profile.favorite_categories:
            pref_parts.append(f"偏好分类={','.join(profile.favorite_categories[:3])}")
        pref_parts.append(f"累计查询={profile.total_queries}次")
    if memory.favorite_items:
        pref_parts.append(f"常看={','.join(memory.favorite_items[:5])}")
    sections.append("[用户偏好]\n" + " | ".join(pref_parts))

    # 3. 相关智能建议（只注入与当前物品相关的）
    if memory.recent_suggestions and contexts:
        relevant = []
        for s in memory.recent_suggestions[-config.PROACTIVE_SUGGESTION_LIMIT:]:
            if any(s.item_id == ctx.item_id for ctx in contexts):
                relevant.append(s.message)
        if relevant:
            sections.append("[相关建议]\n" + "\n".join(f"- {m}" for m in relevant))

    # 4. 高置信度已学模式
    if memory.learned_patterns:
        high_conf = [p for p in memory.learned_patterns if p.get("confidence", 0) >= 0.7]
        if high_conf:
            pattern_lines = [f"- {p['description']}" for p in high_conf[:3]]
            sections.append("[已发现的规律]\n" + "\n".join(pattern_lines))

    return "\n\n".join(sections) if sections else "（无历史记忆）"



def _matching_alias_items(normalized_message: str, aliases: dict[str, str]) -> list[str]:
    matches = []
    for alias_key, item_id in sorted(aliases.items(), key=lambda entry: -len(entry[0])):
        if alias_key and alias_key in normalized_message and item_id not in matches:
            matches.append(item_id)
    return matches


def _message_tokens(message: str) -> list[str]:
    separators = "，。！？、,.!?;；:\n\t()（）[]【】"
    normalized = message
    for separator in separators:
        normalized = normalized.replace(separator, " ")
    return [token for token in normalized.split() if token]


def _resurgence_display_name(item) -> str:
    normalized_name = _resurgence_prime_name(item)
    zh = _RESURGENCE_NAME_ZH.get(normalized_name) or _RESURGENCE_NAME_ZH.get(item.item_name)
    return zh or normalized_name or item.item_name


def _resurgence_warframe_display_name(item) -> str:
    return _resurgence_prime_name(item) or item.item_name


def _resurgence_weapon_display_name(item) -> str:
    market_id = _resurgence_market_id(item)
    item_data = load_item_data().get(market_id, {}) if market_id else {}
    zh_name = item_data.get("zh_name", "")
    if zh_name:
        return re.sub(r"\s*一套$", "", zh_name).strip()
    return _RESURGENCE_NAME_ZH.get(_resurgence_prime_name(item), "") or _resurgence_prime_name(item) or item.item_name


def _is_resurgence_warframe(item) -> bool:
    return bool(_resurgence_market_id(item)) and "/Powersuits/" in item.item_type


def _is_resurgence_weapon(item) -> bool:
    market_id = _resurgence_market_id(item)
    if not market_id or _is_resurgence_warframe(item):
        return False
    item_type = item.item_type.lower()
    return "/weapons/" in item_type or "/weapon" in item_type


def _resurgence_market_id(item) -> str:
    if item.market_id.endswith("_prime_set"):
        return item.market_id
    if _is_resurgence_non_tradeable_item(item):
        return ""
    prime_name = _resurgence_prime_name(item)
    if not prime_name:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "_", prime_name.lower()).strip("_")
    return f"{slug}_set" if slug.endswith("_prime") else ""


def _resurgence_prime_name(item) -> str:
    name = item.item_name.strip()
    if not name or "Prime" not in name:
        leaf = _resurgence_item_type_leaf(item.item_type)
        if "Prime" not in leaf:
            return ""
        name = leaf
    name = re.sub(r"\b(Weapon|Blueprint|Set)\b", "", name).strip()
    match = re.match(r"^Prime\s+(.+)$", name)
    if match:
        name = f"{match.group(1).strip()} Prime"
    camel_match = re.match(r"^(.+?)Prime(?:Weapon)?$", name)
    if camel_match and " " not in name:
        name = f"{camel_match.group(1)} Prime"
    return re.sub(r"\s+", " ", name).strip()


def _resurgence_item_type_leaf(value: str) -> str:
    leaf = value.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"(?<!^)(?=[A-Z])", " ", leaf).strip()


def _is_resurgence_non_tradeable_item(item) -> bool:
    text = f"{item.item_name} {item.item_type}".lower()
    blocked = (
        "scarf", "bobble", "armor", "dangle", "extractor", "pack", "bundle",
        "syandana", "sugatra", "glyph", "decoration", "sigil", "operator",
        "accessory", "attachments", "emote", "color", "colour",
    )
    if any(word in text for word in blocked):
        return True
    if "/types/items/miscitems/" in text:
        return True
    return False


def _resurgence_relic_name(item) -> str:
    export_name = _resurgence_relic_export_name(item.item_type)
    if export_name:
        return _localize_resurgence_relic_name(export_name)
    name = item.item_name
    tier_short = _resurgence_relic_tier_short(item.item_type) or _resurgence_relic_tier_short(name)
    if tier_short:
        tier_map = {"T1": "古纪", "T2": "前纪", "T3": "中纪", "T4": "后纪", "T5": "遗珍", "Lith": "古纪", "Meso": "前纪", "Neo": "中纪", "Axi": "后纪", "Requiem": "遗珍"}
        code_match = re.search(r"Vault([A-Z]+\d*)(?:Bronze|Silver|Gold|Rare)?$", item.item_type) or re.search(r"\b([A-Z]\d+)\b", name)
        code = code_match.group(1) if code_match else ""
        return f"{tier_map.get(tier_short, tier_short)} {code}".strip()
    match = re.match(r"^(Lith|Meso|Neo|Axi|Requiem)\s+(.+)$", name)
    if not match:
        return name
    tier_map = {"Lith": "古纪", "Meso": "前纪", "Neo": "中纪", "Axi": "后纪", "Requiem": "遗珍"}
    return f"{tier_map.get(match.group(1), match.group(1))} {match.group(2)}"


_RESURGENCE_RELIC_EXPORT_CACHE: dict[str, str] | None = None


def _resurgence_relic_export_name(item_type: str) -> str:
    global _RESURGENCE_RELIC_EXPORT_CACHE
    if _RESURGENCE_RELIC_EXPORT_CACHE is None:
        _RESURGENCE_RELIC_EXPORT_CACHE = _build_resurgence_relic_export_cache()
    return _RESURGENCE_RELIC_EXPORT_CACHE.get(_normalize_resurgence_relic_type(item_type), "")


def _build_resurgence_relic_export_cache() -> dict[str, str]:
    cache: dict[str, str] = {}
    path = config.EXPORT_DIR / "ExportRelicArcane_en.json"
    if not path.exists():
        return cache
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return cache
    entries = raw.get("ExportRelicArcane", raw) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return cache
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        unique = entry.get("uniqueName", "")
        name = entry.get("name", "")
        if unique and name:
            cache[_normalize_resurgence_relic_type(unique)] = name
    return cache


def _normalize_resurgence_relic_type(item_type: str) -> str:
    return item_type.replace("/Lotus/StoreItems/", "/Lotus/")


def _localize_resurgence_relic_name(name: str) -> str:
    match = re.match(r"^(Lith|Meso|Neo|Axi|Requiem)\s+(.+?)\s+Relic$", name)
    if not match:
        return name
    tier_map = {"Lith": "古纪", "Meso": "前纪", "Neo": "中纪", "Axi": "后纪", "Requiem": "遗珍"}
    return f"{tier_map.get(match.group(1), match.group(1))} {match.group(2)}"


def _resurgence_relic_tier_short(value: str) -> str:
    match = re.search(r"(?:^|/)T([1-5])VoidProjection", value)
    if match:
        return f"T{match.group(1)}"
    match = re.search(r"\b(Lith|Meso|Neo|Axi|Requiem)\b", value)
    return match.group(1) if match else ""


_RESURGENCE_NAME_ZH = {
    "Ash Prime": "Ash Prime",
    "Banshee Prime": "Banshee Prime",
    "Chroma Prime": "Chroma Prime",
    "Ember Prime": "Ember Prime",
    "Equinox Prime": "Equinox Prime",
    "Frost Prime": "Frost Prime",
    "Hydroid Prime": "Hydroid Prime",
    "Limbo Prime": "Limbo Prime",
    "Loki Prime": "Loki Prime",
    "Mag Prime": "Mag Prime",
    "Mesa Prime": "Mesa Prime",
    "Mirage Prime": "Mirage Prime",
    "Nekros Prime": "Nekros Prime",
    "Nova Prime": "Nova Prime",
    "Nyx Prime": "Nyx Prime",
    "Rhino Prime": "犀牛 Prime",
    "Saryn Prime": "Saryn Prime",
    "Trinity Prime": "Trinity Prime",
    "Valkyr Prime": "Valkyr Prime",
    "Vauban Prime": "Vauban Prime",
    "Volt Prime": "伏特 Prime",
    "Wukong Prime": "悟空 Prime",
}


_EVENT_KEYWORDS = {
    "活动", "事件", "裂缝", "裂隙", "fissure", "虚空裂缝", "虚空裂隙",
    "baro", "虚空商人", "奸商", "入侵", "invasion", "警报", "alert", "虚空风暴",
    "钢铁歼灭", "钢铁防御", "钢铁生存", "开核桃", "遗物", "核桃",
    "刷什么", "现在刷", "当前刷", "可以刷", "有什么活动",
    "重生", "返厂", "prime重生", "prime 重生", "resurgence", "prime resurgence", "prime vault",
    "午夜电波", "电波", "nightwave", "仲裁", "arbitration", "突击", "sortie",
    "darvo", "每日特惠", "每日优惠", "扎里曼", "zariman", "赏金", "bounty",
    "热美亚", "thermia", "兽之腹", "jade shadows", "jadeshadows",
    "尸鬼", "ghoul", "利刃豺狼", "razorback", "巨人战舰", "fomorian",
}

_LIMITED_ACTIVITY_KEYWORDS = (
    "热美亚", "thermia", "兽之腹", "jade shadows", "jadeshadows",
    "尸鬼", "ghoul", "利刃豺狼", "razorback", "巨人战舰", "fomorian",
)

_LIMITED_ACTIVITY_FILTERS = (
    ("热美亚裂缝", ("热美亚", "thermia")),
    ("兽之腹", ("兽之腹", "jade shadows", "jadeshadows")),
    ("尸鬼净化", ("尸鬼", "ghoul")),
    ("利刃豺狼舰队", ("利刃豺狼", "razorback")),
    ("巨人战舰", ("巨人战舰", "fomorian")),
)


def _is_prime_resurgence_query(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in ("重生", "resurgence", "prime resurgence", "prime vault"))


def _is_baro_recommendation_query(message: str) -> bool:
    lower = message.lower()
    has_baro = any(kw in lower for kw in ("baro", "虚空商人"))
    if not has_baro:
        return False
    return any(kw in lower for kw in ("mod", "赋能", "价格", "买价", "卖价", "推荐", "有什么", "库存", "带来", "带了", "物品"))


def _is_baro_inventory_query(message: str) -> bool:
    lower = message.lower()
    has_inventory = any(kw in lower for kw in ("有什么", "哪些", "库存", "带来", "带了", "物品"))
    has_price_intent = any(kw in lower for kw in ("价格", "买价", "卖价", "推荐", "白金", "链接", "买家", "卖家", "私聊"))
    return has_inventory and not has_price_intent


def _is_event_query(message: str) -> bool:
    """判断消息是否为游戏事件查询（应直接走路由器，跳过物品匹配）。"""
    lower = message.lower()
    return any(kw in lower for kw in _EVENT_KEYWORDS)


def _is_limited_activity_query(message: str) -> bool:
    lower = message.lower()
    compact = re.sub(r"\s+", "", lower)
    return any(kw in lower or re.sub(r"\s+", "", kw) in compact for kw in _LIMITED_ACTIVITY_KEYWORDS)


def _limited_activity_labels_from_query(message: str | None) -> list[str]:
    return [
        label
        for label, aliases in _LIMITED_ACTIVITY_FILTERS
        if _query_contains_any(message, aliases)
    ]


def _filter_limited_events_for_query(events: Iterable, query: str | None = None) -> list:
    labels = _limited_activity_labels_from_query(query)
    selected = list(events)
    if not labels:
        return selected
    return [
        event
        for event in selected
        if any(label in getattr(event, "description", "") for label in labels)
    ]


def _is_relic_value_intent(message: str) -> bool:
    lower = message.lower()
    has_relic = any(kw in lower for kw in (
        "遗物", "核桃", "relic", "lith", "meso", "neo", "axi", "requiem",
        "古纪", "前纪", "中纪", "后纪", "遗珍",
    ))
    has_value = any(kw in lower for kw in (
        "收益", "价值", "估值", "期望", "值不值得", "值得开", "效率",
        "杜卡德", "杜卡", "ducat",
    ))
    return has_relic and has_value


def _is_relic_farming_intent(message: str) -> bool:
    lower = message.lower()
    has_relic = any(kw in lower for kw in (
        "遗物", "核桃", "relic", "lith", "meso", "neo", "axi", "requiem",
        "古纪", "前纪", "中纪", "后纪", "遗珍",
    ))
    has_route = any(kw in lower for kw in (
        "去哪刷", "哪里刷", "怎么刷", "刷取", "掉落", "来源",
        "哪个裂缝", "适合开", "开这个核桃", "开这个遗物",
    ))
    return has_relic and has_route


def _is_specific_event_list_query(message: str) -> bool:
    from .events import unsupported_event_type_label
    if _is_limited_activity_query(message):
        return False
    return _event_type_from_message(message) is not None or bool(unsupported_event_type_label(message)) or any(kw in message.lower() for kw in ("警报", "alert"))


def _event_type_from_message(message: str) -> str | None:
    from .events import normalize_query_event_type
    if _is_limited_activity_query(message):
        return None
    if _is_void_fissure_detail_query(message):
        return "void_fissure"
    return normalize_query_event_type(message)


_VOID_FISSURE_TIER_FILTERS = (
    ("VoidT1", ("古纪", "lith", "voidt1", "t1")),
    ("VoidT2", ("前纪", "meso", "voidt2", "t2")),
    ("VoidT3", ("中纪", "neo", "voidt3", "t3")),
    ("VoidT4", ("后纪", "axi", "voidt4", "t4")),
    ("VoidT5", ("遗珍", "requiem", "voidt5", "t5")),
    ("VoidT6", ("仲裁", "arbitration", "voidt6", "t6")),
)
_VOID_FISSURE_MISSION_FILTERS = (
    ("MT_EXTERMINATION", ("歼灭", "exterminate", "extermination", "mt_extermination")),
    ("MT_CAPTURE", ("捕获", "capture", "mt_capture")),
    ("MT_DEFENSE", ("防御", "defense", "mt_defense")),
    ("MT_SURVIVAL", ("生存", "survival", "mt_survival")),
    ("MT_RESCUE", ("救援", "rescue", "mt_rescue")),
    ("MT_SABOTAGE", ("破坏", "sabotage", "mt_sabotage")),
    ("MT_MOBILE_DEFENSE", ("移动防御", "mobile defense", "mobiledefense", "mt_mobile_defense")),
    ("MT_INTEL", ("间谍", "spy", "intel", "mt_intel", "mt_spy")),
    ("MT_SPY", ("间谍", "spy", "mt_spy")),
    ("MT_TERRITORY", ("拦截", "interception", "territory", "mt_territory")),
    ("MT_ARTIFACT", ("挖掘", "excavation", "artifact", "mt_artifact")),
    ("MT_ALCHEMY", ("炼金", "alchemy", "mt_alchemy")),
    ("MT_DISRUPTION", ("中断", "disruption", "mt_disruption")),
    ("MT_ASSASSINATION", ("刺杀", "assassination", "mt_assassination")),
)


def _is_void_fissure_detail_query(message: str) -> bool:
    has_mission = any(_query_contains_any(message, aliases) for _, aliases in _VOID_FISSURE_MISSION_FILTERS)
    has_tier = any(_query_contains_any(message, aliases) for _, aliases in _VOID_FISSURE_TIER_FILTERS)
    has_mode = _query_contains_any(message, ("钢铁", "钢铁之路", "steel", "steel path", "steelpath", "普通", "normal"))
    has_fissure = _query_contains_any(message, ("裂缝", "裂隙", "fissure", "虚空裂缝", "虚空裂隙"))
    return has_mission and (has_mode or has_tier or has_fissure)


def _query_contains_any(query: str | None, aliases: Iterable[str]) -> bool:
    lowered = str(query or "").lower()
    compact = re.sub(r"\s+", "", lowered)
    for alias in aliases:
        alias_lower = alias.lower()
        alias_compact = re.sub(r"\s+", "", alias_lower)
        if alias_lower in lowered or alias_compact in compact:
            return True
    return False


def _filter_void_fissures_for_query(fissures: Iterable, query: str | None = None) -> list:
    selected = list(fissures)
    tier_filters = {
        tier
        for tier, aliases in _VOID_FISSURE_TIER_FILTERS
        if _query_contains_any(query, aliases)
    }
    mission_filters = {
        mission
        for mission, aliases in _VOID_FISSURE_MISSION_FILTERS
        if _query_contains_any(query, aliases)
    }
    mode_filter: bool | None = None
    if _query_contains_any(query, ("钢铁", "钢铁之路", "steel", "steel path", "steelpath")):
        mode_filter = True
    elif _query_contains_any(query, ("普通", "normal")):
        mode_filter = False

    if tier_filters:
        selected = [fissure for fissure in selected if getattr(fissure, "tier", "") in tier_filters]
    if mission_filters:
        selected = [fissure for fissure in selected if getattr(fissure, "mission_type", "") in mission_filters]
    if mode_filter is not None:
        selected = [fissure for fissure in selected if bool(getattr(fissure, "hard", False)) is mode_filter]
    return selected


def _format_void_fissures_for_chat(fissures: Iterable, query: str | None = None, limit: int = 20) -> str:
    from .events import _format_worldstate_time

    selected = _filter_void_fissures_for_query(fissures, query)[:limit]
    lines = ["当前虚空裂缝/裂隙:"]
    if not selected:
        lines.append("暂无匹配裂缝。")
        return "\n".join(lines)
    for fissure in selected:
        mode = "钢铁" if getattr(fissure, "hard", False) else "普通"
        line = (
            f"- {getattr(fissure, 'tier_display', '')} "
            f"{getattr(fissure, 'mission_display', '')} "
            f"{mode} @ {getattr(fissure, 'node_display', '')}"
        )
        expiry = getattr(fissure, "expiry", "")
        if expiry:
            line += f" | 结束: {_format_worldstate_time(expiry)}"
        lines.append(line)
    return "\n".join(lines)


def _format_void_fissures_for_model(fissures: Iterable, query: str | None = None, limit: int = 20) -> str:
    selected = _filter_void_fissures_for_query(fissures, query)[:limit]
    parts = [
        "tool=query_events",
        "type=void_fissure",
        f"count={len(selected)}",
    ]
    for fissure in selected:
        mode = "steel" if getattr(fissure, "hard", False) else "normal"
        node = wrap_untrusted_model_text("worldstate", str(getattr(fissure, "node_display", "")), max_chars=80, max_lines=1)
        parts.append(
            " | ".join([
                f"tier={getattr(fissure, 'tier_display', '')}",
                f"mission={getattr(fissure, 'mission_display', '')}",
                f"mode={mode}",
                f"node={node}",
                f"expiry={getattr(fissure, 'expiry', '')}",
            ])
        )
    return "\n".join(parts)


def _normalize_query_event_type_arg(event_type: object) -> str | None:
    if event_type is None:
        return None
    from .events import normalize_query_event_type
    text = str(event_type).strip()
    return normalize_query_event_type(text) or (text if text else None)


_TRADING_TOOL_KEYWORDS = {
    "翻转", "mod翻转", "mod flip", "内融利润", "升级赚钱",
    "套装利润", "拆件赚", "拆件利润", "整套vs拆件",
    "投资", "投资推荐", "投资建议", "roi", "预算",
    "有什么mod", "哪些mod", "什么mod可以",
    "紫卡", "裂罅", "riven", "洗卡",
}


def _is_trading_tool_query(message: str) -> bool:
    """判断消息是否为交易工具查询（应直接走路由器，跳过物品匹配）。"""
    lower = message.lower()
    return any(kw in lower for kw in _TRADING_TOOL_KEYWORDS)


def _classify_chat_mode(message: str) -> ChatModeDecision:
    if _message_has_direct_market_intent(message):
        return ChatModeDecision("trade_execution", "direct_market")
    if _message_has_planning_intent(message):
        return ChatModeDecision("planning", "planning_keywords")
    if _is_event_query(message):
        return ChatModeDecision("event", "event_keywords")
    if _is_trading_tool_query(message):
        return ChatModeDecision("trading_tool", "trading_tool_keywords")
    if _message_has_market_analysis_intent(message):
        return ChatModeDecision("market_analysis", "market_keywords")
    if _message_has_guide_video_intent(message):
        return ChatModeDecision("guide_video", "guide_keywords")
    return ChatModeDecision("general", "fallback")


def _message_has_direct_market_intent(message: str) -> bool:
    lowered = message.lower()
    direct_terms = (
        "市场链接", "链接", "url", "warframe.market", "market",
        "最便宜卖家", "最低卖家", "最低价卖家", "便宜卖家",
        "砍价", "讲价", "还价", "压价",
    )
    return any(term in lowered or term in message for term in direct_terms)


def _message_has_planning_intent(message: str) -> bool:
    lowered = message.lower()
    normalized = normalize_lookup_key(message)
    planning_terms = ("计划", "规划", "目标", "步骤", "安排", "路线图", "roadmap", "plan")
    horizon_terms = ("一周", "本周", "今天开始", "长期", "短期", "每天", "阶段")
    profit_goal_terms = ("赚", "盈利", "利润目标", "目标利润", "500p", "1000p")
    has_plan = any(term in lowered or normalize_lookup_key(term) in normalized for term in planning_terms)
    has_horizon_goal = any(term in lowered or term in message for term in horizon_terms) and any(
        term in lowered or term in message for term in profit_goal_terms
    )
    return has_plan or has_horizon_goal


def _message_has_market_analysis_intent(message: str) -> bool:
    lowered = message.lower()
    normalized = normalize_lookup_key(message)
    market_terms = (
        "多少钱", "价格", "买价", "卖价", "白金", "价差", "会涨", "会跌",
        "涨吗", "跌吗", "趋势", "走势", "行情", "能不能买", "能不能卖",
        "我要买", "我要卖", "我想买", "我想卖", "最高收", "最低卖",
        "最高收价", "最低卖价", "有人收吗", "卖给谁",
    )
    return any(term in lowered or normalize_lookup_key(term) in normalized for term in market_terms)


def _message_has_guide_video_intent(message: str) -> bool:
    lowered = message.lower()
    guide_terms = ("配卡", "攻略", "视频", "教程", "b站", "bilibili", "build")
    return any(term in lowered or term in message for term in guide_terms)


def _self_check(answer: str, contexts: list[ItemContext]) -> str | None:
    """规则化自检：捕获 LLM 的严重错误，不增加额外 LLM 调用。

    发现问题时返回追加 [注意] 后缀的修正版本，无问题返回 None。
    """
    warnings = []

    # 1. 价格编造检测：回答中出现的 Np 价格必须在 contexts 中存在
    import re
    price_pattern = re.compile(r'(\d+)\s*[pP铂]')
    mentioned_prices = {int(m.group(1)) for m in price_pattern.finditer(answer)}
    if mentioned_prices and contexts:
        valid_prices = set()
        for ctx in contexts:
            if ctx.best_sell_price:
                valid_prices.add(ctx.best_sell_price)
            if ctx.best_buy_price:
                valid_prices.add(ctx.best_buy_price)
            # 允许价差计算结果（±5 范围内）
            for vp in list(valid_prices):
                for delta in range(-5, 6):
                    valid_prices.add(vp + delta)
        fabricated = mentioned_prices - valid_prices
        # 过滤掉明显不是交易价格的数字（如版本号、百分比）
        fabricated = {p for p in fabricated if 5 < p < 100000}
        if fabricated and len(fabricated) > len(mentioned_prices) * 0.5:
            warnings.append(f"回答中包含未在数据中出现的价格: {fabricated}p，可能不准确")

    # 2. 无交易上下文时出现私聊命令 = LLM 混入了无关数据
    has_whisper = "/w " in answer or "/W " in answer
    if has_whisper and not contexts:
        warnings.append("回答中包含私聊命令但查询与交易无关，可能混入了不相关数据")

    # 3. 回答截断检测
    if len(answer.strip()) < 20:
        warnings.append("回答过短，可能被截断")

    if warnings:
        return answer + "\n\n[注意] " + "；".join(warnings)
    return None


def _load_watchlist() -> dict[str, list[str]]:
    if not config.WATCHLIST_PATH.exists():
        return {}
    with config.WATCHLIST_PATH.open("r", encoding="utf-8-sig") as file:
        return json.load(file)





