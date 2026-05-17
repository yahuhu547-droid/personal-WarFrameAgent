from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, replace
from typing import AsyncIterator, Callable, Iterable

import requests

from . import config
from .dictionary import ItemResolver, normalize_lookup_key
from .events import EventTracker
from .formatter import build_whisper
from .game_data import GameDataStore
from .knowledge import MarketKnowledge
from .market import MarketOrder, best_buyers, best_sellers, fetch_orders
from .memory import AgentMemory
from .names import display_item_name, load_item_data
from .price_history import PriceHistoryDB
from .rag import smart_search_rag
from .session import SessionContext, is_followup
from .riven import _looks_like_riven_query
from .tool_router import build_router_prompt, parse_tool_call
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


def is_chat_exit(message: str) -> bool:
    return message.strip().lower() in EXIT_COMMANDS


def is_watchlist_command(message: str) -> bool:
    return message.strip().lower() in WATCHLIST_COMMANDS


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
    )


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
        self.game_data = GameDataStore()
        self._last_baro_recommendations = []
        self._baro_item_info_lookup = None

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

    def answer(self, message: str) -> str:
        self._reload_memory()
        stripped = message.strip()
        if stripped.startswith("/"):
            return self._handle_agent_command(stripped)
        if is_watchlist_command(message):
            return self.scan_watchlist()
        cycle_result = self._try_cycle_intent(message)
        if cycle_result:
            self.session.add_exchange(message, cycle_result)
            self._log_answer(message, cycle_result)
            return cycle_result
        self._remember_common_question(message)
        baro_followup = self._try_baro_order_followup(message)
        if baro_followup:
            self.session.add_exchange(message, baro_followup)
            self._log_answer(message, baro_followup)
            return baro_followup
        baro_answer = self._try_baro_recommendation(message)
        if baro_answer:
            self.session.add_exchange(message, baro_answer)
            self._log_answer(message, baro_answer)
            return baro_answer
        # 紫卡查询：优先确定性解析，避免 LLM 路由误判
        if _looks_like_riven_query(message):
            riven_result = self._try_deterministic_riven(message)
            if riven_result:
                self.session.add_exchange(message, riven_result)
                self._log_answer(message, riven_result)
                return riven_result
        # 紫卡追问：基于上一次查询过滤（在线/便宜）
        riven_followup = self._try_riven_followup(message)
        if riven_followup:
            self.session.add_exchange(message, riven_followup)
            self._log_answer(message, riven_followup)
            return riven_followup
        # Prime 重生 / Vault 查询：直接走事件格式化，避免物品匹配误触发
        if _is_prime_resurgence_query(message):
            result = self._handle_vault_command()
            self.session.add_exchange(message, result)
            self._log_answer(message, result)
            return result
        # 事件类/交易工具类查询直接走路由器，避免物品匹配误触发交易流程
        if _is_event_query(message) or _is_trading_tool_query(message):
            if _is_event_query(message) and not _is_specific_event_list_query(message):
                result = self._handle_limited_event_query()
                self.session.add_exchange(message, result)
                self._log_answer(message, result)
                return result
            if _is_specific_event_list_query(message):
                routed = self._handle_specific_event_query(message)
            else:
                routed = self._try_router(message)
            if routed:
                self.session.add_exchange(message, routed)
                self._log_answer(message, routed)
                return routed
            # 路由失败时不要 fallthrough 到物品匹配，返回通用提示
            if _is_trading_tool_query(message):
                fallback = "交易工具暂时无法使用，请稍后重试。你也可以直接输入物品名称查询价格。"
                self._log_answer(message, fallback)
                return fallback
            if _is_event_query(message):
                fallback = self._handle_limited_event_query()
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
            routed = self._try_router(message)
            if routed:
                self.session.add_exchange(message, routed)
                self._log_answer(message, routed)
                return routed
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
            self.session.add_exchange(message, deterministic_answer)
            self._log_answer(message, deterministic_answer, contexts)
            return deterministic_answer
        current_ids = [ctx.item_id for ctx in contexts]
        market_ctx = build_system_context(self.knowledge, self.event_tracker, memory=self.memory, game_data=self.game_data, current_item_ids=current_ids)
        prompt_messages = build_chat_messages(message, contexts, self.memory, self.session.to_messages(current_query=message), market_ctx or None)
        try:
            answer = self._call_llm_messages(prompt_messages).strip()
            if answer:
                checked = _self_check(answer, contexts)
                if checked:
                    answer = checked
                self.session.add_exchange(message, answer)
                self._log_answer(message, answer, contexts)
                return answer
        except Exception as exc:
            logger.debug("LLM 调用失败，使用回退: %s", exc)
            result = fallback_answer(message, contexts, llm_failed=True)
            self.session.add_exchange(message, result)
            self._log_answer(message, result, contexts)
            return result
        result = fallback_answer(message, contexts)
        self.session.add_exchange(message, result)
        self._log_answer(message, result, contexts)
        return result

    def _log_answer(self, message: str, reply: str, contexts=None) -> None:
        try:
            from .conversation_log import log_conversation, ConversationEntry
            log_conversation(ConversationEntry(
                user_message=message,
                assistant_reply=reply,
                contexts=[ctx.item_id for ctx in contexts] if contexts else None,
            ))
        except Exception as exc:
            logger.debug("对话日志记录失败: %s", exc)

    async def answer_stream(self, message: str) -> AsyncIterator[str]:
        """流式版本的 answer，逐 token yield。对于不需要 LLM 的路径，一次性 yield 全文。"""
        self._reload_memory()
        stripped = message.strip()
        if stripped.startswith("/"):
            result = self._handle_agent_command(stripped)
            self._log_answer(message, result)
            yield result
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
        self._remember_common_question(message)
        baro_followup = self._try_baro_order_followup(message)
        if baro_followup:
            self.session.add_exchange(message, baro_followup)
            self._log_answer(message, baro_followup)
            yield baro_followup
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
            if riven_result:
                self.session.add_exchange(message, riven_result)
                self._log_answer(message, riven_result)
                yield riven_result
                return
        # 紫卡追问：基于上一次查询过滤（在线/便宜）
        riven_followup = self._try_riven_followup(message)
        if riven_followup:
            self.session.add_exchange(message, riven_followup)
            self._log_answer(message, riven_followup)
            yield riven_followup
            return
        # Prime 重生 / Vault 查询：直接走事件格式化，避免物品匹配误触发
        if _is_prime_resurgence_query(message):
            result = self._handle_vault_command()
            self.session.add_exchange(message, result)
            self._log_answer(message, result)
            yield result
            return
        # 事件类/交易工具类查询直接走路由器，避免物品匹配误触发交易流程
        if _is_event_query(message) or _is_trading_tool_query(message):
            if _is_event_query(message) and not _is_specific_event_list_query(message):
                result = self._handle_limited_event_query()
                self.session.add_exchange(message, result)
                self._log_answer(message, result)
                yield result
                return
            if _is_specific_event_list_query(message):
                routed = self._handle_specific_event_query(message)
            else:
                routed = self._try_router(message)
            if routed:
                self.session.add_exchange(message, routed)
                self._log_answer(message, routed)
                yield routed
                return
            if _is_trading_tool_query(message):
                fallback = "交易工具暂时无法使用，请稍后重试。你也可以直接输入物品名称查询价格。"
                self._log_answer(message, fallback)
                yield fallback
                return
            if _is_event_query(message):
                result = self._handle_limited_event_query()
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
            routed = self._try_router(message)
            if routed:
                self.session.add_exchange(message, routed)
                self._log_answer(message, routed)
                yield routed
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
            self.session.add_exchange(message, deterministic_answer)
            self._log_answer(message, deterministic_answer, contexts)
            yield deterministic_answer
            return
        current_ids = [ctx.item_id for ctx in contexts]
        market_ctx = build_system_context(self.knowledge, self.event_tracker, memory=self.memory, game_data=self.game_data, current_item_ids=current_ids)
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
            result = fallback_answer(message, contexts, llm_failed=True)
            self.session.add_exchange(message, result)
            self._log_answer(message, result, contexts)
            yield result
            return
        reply_text = "".join(full_reply).strip()
        if reply_text:
            checked = _self_check(reply_text, contexts)
            if checked:
                reply_text = checked
            self.session.add_exchange(message, reply_text)
            self._log_answer(message, reply_text, contexts)
        else:
            result = fallback_answer(message, contexts)
            self.session.add_exchange(message, result)
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

    def _render_memory_summary(self) -> str:
        favorites = "、".join(display_item_name(item_id) for item_id in self.memory.favorite_items[:5]) or "无"
        alerts = "、".join(
            f"{display_item_name(alert.item_id)} {('低于' if alert.direction == 'below' else '高于')} {alert.price}p"
            for alert in self.memory.price_alerts[:5]
        ) or "无"
        questions = "、".join(self.memory.common_questions[-5:]) or "无"
        lines = [
            "记忆摘要：",
            f"偏好: platform={self.memory.preferences.platform}, crossplay={self.memory.preferences.crossplay}, max_results={self.memory.preferences.max_results}",
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
            lines = [
                "当前偏好设置:",
                f"  平台: {p.platform}",
                f"  跨平台: {'开' if p.crossplay else '关'}",
                f"  最大结果数: {p.max_results}",
                "",
                "修改: /pref platform pc | /pref crossplay on | /pref max 5",
            ]
            return "\n".join(lines)
        if len(args) < 2:
            return "用法: /pref platform pc | /pref crossplay on | /pref max 5"
        key = args[0].lower()
        value = args[1].lower()
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
        return "不支持的偏好设置，可选: platform / crossplay / max"

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
        from .goals import GoalTracker, create_goal
        tracker = GoalTracker()
        if not args:
            return tracker.format_goals_status()
        sub = args[0].lower()
        if sub in ("set", "add", "新建"):
            desc = " ".join(args[1:]) if len(args) > 1 else ""
            if not desc:
                return "请指定目标描述，例如: /goal set 一周内赚500p"
            goal = create_goal(
                goal_type="maximize_profit",
                description=desc,
                target="all",
                criteria={"budget": 500, "min_roi": 10},
            )
            tracker.add_goal(goal)
            return f"已创建目标: {desc}\n目标 ID: {goal.goal_id[:6]}\n使用 /goal 查看进度"
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
            return "用法: /relic 物品名 | /relic 遗物名\n示例: /relic 犀牛 Prime 蓝图 | /relic Lith B1"
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
            if sellers:
                lowest_buy = f"最低买入价 {sellers[0].platinum}p"
            if buyers:
                parts.append(f"最高卖出价 {buyers[0].platinum}p")
            if sellers:
                parts.append(lowest_buy)
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

    def _try_baro_order_followup(self, message: str) -> str | None:
        if not self._last_baro_recommendations:
            return None
        from .baro import (
            find_baro_recommendation,
            format_baro_order_details,
            is_baro_order_detail_request,
            parse_order_detail_limits,
        )
        if not is_baro_order_detail_request(message):
            return None
        recommendation = find_baro_recommendation(self._last_baro_recommendations, message)
        if not recommendation:
            return None
        buyer_limit, seller_limit = parse_order_detail_limits(message)
        return format_baro_order_details(recommendation, seller_limit=seller_limit, buyer_limit=buyer_limit)

    def _try_router(self, message: str) -> str | None:
        result = self._try_react_loop(message)
        if result:
            return result
        return self._try_router_legacy(message)

    def _try_react_loop(self, message: str) -> str | None:
        from .tool_router import react_loop
        try:
            return react_loop(
                message=message,
                tool_executor=self._execute_tool_call,
                model_call=self._react_model_call,
            )
        except Exception as exc:
            logger.debug("ReAct 循环失败: %s", exc)
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
        caller = self.router_call or self.model_call
        try:
            router_prompt = build_router_prompt(message)
            raw = caller(router_prompt).strip()
            tool_call = parse_tool_call(raw)
            if not tool_call:
                return None
            return self._execute_tool_call(tool_call, message)
        except Exception as exc:
            logger.debug("工具路由失败: %s", exc)
            return None

    def _execute_tool_call(self, tool_call, message: str = "") -> str | None:
        args = tool_call.arguments
        if tool_call.name == "query_price":
            item_name = args.get("item_name", message)
            item_id = self._resolve_item_id_for_command(item_name)
            if not item_id:
                return None
            contexts = self._contexts_for_items([item_id])
            if not contexts:
                return None
            self.session.update([item_id])
            det = _deterministic_trade_intent_answer(message, contexts)
            if det:
                return det
            return fallback_answer(message, contexts)
        if tool_call.name == "query_set":
            warframe_name = args.get("warframe_name", message)
            result = price_warframe_query(warframe_name, self.warframe_items, self.order_fetcher)
            return result or None
        if tool_call.name == "scan_favorites":
            return self._handle_scan_command()
        if tool_call.name == "set_alert":
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
        if tool_call.name == "price_trend":
            item_name = args.get("item_name", message)
            item_id = self._resolve_item_id_for_command(item_name)
            if not item_id or not self.price_db:
                return None
            trend = self.price_db.trend_summary(item_id)
            if trend:
                return f"{display_item_name(item_id)}\n{trend}"
            return f"{display_item_name(item_id)}\n暂无历史价格数据"
        if tool_call.name == "query_missing_parts":
            warframe_name = args.get("warframe_name", message)
            owned_raw = args.get("owned_parts", "")
            owned_parts = [p.strip() for p in owned_raw.replace("、", ",").replace("，", ",").split(",") if p.strip()]
            return self._query_missing_parts(warframe_name, owned_parts)
        if tool_call.name == "general_chat":
            return None
        if tool_call.name == "mod_flipper":
            from .mod_flipper import scan_all_mod_flips
            from .scout import scout_mod_candidates
            min_profit = int(args.get("min_profit", 5))
            limit = int(args.get("limit", 20))
            results = scan_all_mod_flips(
                self.warframe_items or [],
                self.order_fetcher,
                min_profit=min_profit,
                limit=limit,
                scout_fn=scout_mod_candidates,
            )
            if not results:
                return "没有找到符合条件的 Mod 翻转机会"
            lines = ["## Mod 翻转排行榜\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. **{r.display_name}** (R0→R{r.max_rank})")
                lines.append(f"   买 R0: {r.r0_buy_price}p → 卖 R{r.max_rank}: {r.r10_sell_price}p")
                lines.append(f"   利润: {r.flip_profit}p | 每千内融: {r.plat_per_1k_endo:.1f}p | 48h成交: {r.volume_48h or '未知'}笔")
            return "\n".join(lines)
        if tool_call.name == "set_profit":
            from .set_profit import scan_all_set_profits
            from .scout import scout_set_candidates
            min_profit = int(args.get("min_profit", 5))
            limit = int(args.get("limit", 20))
            results = scan_all_set_profits(
                self.warframe_items or [],
                self.order_fetcher,
                min_profit=min_profit,
                limit=limit,
                scout_fn=scout_set_candidates,
            )
            if not results:
                return "没有找到符合条件的套装利润机会"
            lines = ["## Prime 套装利润排行榜\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. **{r.display_name}**")
                lines.append(f"   最佳策略: {r.best_strategy} | 利润: +{r.best_profit}p")
                lines.append(f"   整套买: {r.set_buy_price or '无'}p | 拆件卖合计: {r.parts_sell_total}p")
                if r.volume_48h:
                    lines.append(f"   48h成交: {r.volume_48h}笔")
            return "\n".join(lines)
        if tool_call.name == "investment_advisor":
            from .investment import scan_prime_investments
            from .scout import scout_investment_candidates
            budget = int(args.get("budget", 1000))
            min_roi = float(args.get("min_roi", 10))
            limit = int(args.get("limit", 15))
            results = scan_prime_investments(
                self.warframe_items or [],
                self.order_fetcher,
                budget=budget,
                min_roi_pct=min_roi,
                limit=limit,
                scout_fn=lambda groups: scout_investment_candidates(groups, budget=budget),
            )
            if not results:
                return "没有找到符合条件的投资机会"
            lines = [f"## 投资顾问 (预算 {budget}p, ROI >= {min_roi}%)\n"]
            for i, r in enumerate(results, 1):
                risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(r.risk_level, "⚪")
                lines.append(f"{i}. **{r.display_name}** {risk_icon}")
                lines.append(f"   买入成本: {r.buy_cost}p → 卖出: {r.sell_price}p | 每套利润: +{r.profit_per_set}p")
                lines.append(f"   ROI: {r.roi_pct:.1f}% | 可购 {r.sets_affordable} 套 | 总利润: +{r.total_profit}p")
                lines.append(f"   48h成交: {r.volume_48h or '未知'}笔 | 风险: {r.risk_level}")
            return "\n".join(lines)
        if tool_call.name == "query_events":
            return self._handle_limited_event_query()
        if tool_call.name == "deep_analysis":
            item_name = args.get("item_name", message)
            return self._deep_analysis(item_name)
        if tool_call.name == "riven_search":
            return self._handle_riven_search(args)
        return None

    def _handle_limited_event_query(self) -> str:
        from .events import EventTracker
        try:
            tracker = self.event_tracker or EventTracker()
            if not self.event_tracker:
                tracker.load_cache()
            events = tracker.get_limited_events()
        except Exception as exc:
            logger.debug("限时活动查询失败: %s", exc)
            return "暂时无法获取限时活动信息。"

        if not events:
            return "当前没有检测到热美亚裂缝、兽之腹等限时活动。"
        lines = ["当前限时活动:"]
        for event in events:
            lines.append(f"- {event.description}")
        return "\n".join(lines)

    def _handle_specific_event_query(self, message: str) -> str:
        from .events import EventTracker
        tracker = self.event_tracker or EventTracker()
        if not self.event_tracker:
            tracker.load_cache()
        events = tracker.get_active_events()
        lower = message.lower()
        if any(kw in lower for kw in ("裂缝", "裂隙", "fissure")):
            selected = [event for event in events if event.event_type == "void_fissure"]
            title = "当前虚空裂缝/裂隙:"
        elif any(kw in lower for kw in ("风暴", "虚空风暴")):
            selected = [event for event in events if event.event_type == "void_storm"]
            title = "当前虚空风暴:"
        elif any(kw in lower for kw in ("入侵", "invasion")):
            selected = [event for event in events if event.event_type == "invasion"]
            title = "当前入侵:"
        elif any(kw in lower for kw in ("警报", "alert")):
            selected = [event for event in events if event.event_type == "alert"]
            title = "当前警报:"
        else:
            selected = []
            title = "当前事件:"
        if not selected:
            return f"{title}\n暂无。"
        lines = [title]
        for event in selected[:20]:
            lines.append(f"- {event.description}")
        return "\n".join(lines)

    def _try_deterministic_riven(self, message: str) -> str | None:
        """确定性紫卡路由：直接解析查询，不依赖 LLM 路由。"""
        from .riven import parse_riven_query, search_rivens, format_riven_results

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
        return format_riven_results(query, results)

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

    def _try_riven_followup(self, message: str) -> str | None:
        """基于上一次紫卡查询的追问（翻页/在线/便宜/无负等过滤条件）。"""
        from .riven import _extract_max_price, search_rivens, format_riven_results
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
        self.session.update([query.weapon_url_name], "riven", "riven_followup")
        return text + boundary_note

    def _handle_riven_search(self, args: dict) -> str:
        """处理紫卡搜索工具调用。"""
        from .riven import RivenQuery, parse_riven_query, search_rivens, format_riven_results, RIVEN_ATTRIBUTES, COMPOUND_KEYWORDS

        weapon = args.get("weapon", "")
        if not weapon:
            return "请指定武器名称，如：斯特朗双爆紫卡无负"

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
        return format_riven_results(query, results)

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
        self.memory.save(self.memory_path)

    def _reload_memory(self) -> None:
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
    context_text = "\n\n".join(context.text for context in contexts)
    memory_text = _memory_prompt(contexts, memory)
    return (
        "你是资深星际战甲玩家和中文交易助手。请用老玩家视角回答，重点说明能不能买、能不能卖、价差和注意事项。"
        "所有识别出的商品名必须尽量使用 `中文名 / English Name / market_id` 格式。"
        "所有价格单位都是 Warframe 白金 platinum，绝不是美元、人民币或其他现实货币。"
        "不要编造没有提供的实时价格。\n\n"
        f"长期记忆与偏好:\n{memory_text}\n\n"
        f"实时市场上下文:\n{context_text}\n\n"
        f"玩家问题: {message}\n"
        "请给出简洁中文建议，并保留可复制的私聊命令。"
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
        "- 有推荐交易对象时必须提供 /w 私聊命令\n\n"
        "## 回答策略\n"
        "价格查询类问题，按以下步骤思考：\n"
        "1. 识别物品类型（Mod/战甲/赋能/遗物等）\n"
        "2. 分析当前市场数据（卖价、收价、价差）\n"
        "3. 结合趋势和事件给出建议\n"
        "4. 提供可执行的操作（私聊命令等）\n\n"
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
        "推荐购买: /w seller Hi! I want to buy: \"Arcane Energize\" for 45 platinum.\n"
        "建议: 价差适中，适合直接购买。满级赋能流动性好，48h 成交量充足。\n\n"
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
        parts.append(f"\n## 市场智能\n{market_context}")

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
        context_text = "\n\n".join(context.text for context in contexts)
        messages.append({"role": "user", "content": f"实时市场上下文:\n{context_text}\n\n玩家问题: {message}\n请给出简洁中文建议，并保留可复制的私聊命令。"})
    else:
        messages.append({"role": "user", "content": f"玩家问题: {message}\n请给出简洁中文建议。"})
    return messages


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
    header = "| 物品 | 最低卖价 | 最高价 | 价差 | 建议 |"
    separator = "|------|---------|--------|------|------|"
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
    "baro", "虚空商人", "入侵", "invasion", "警报", "alert", "虚空风暴",
    "钢铁歼灭", "钢铁防御", "钢铁生存", "开核桃", "遗物", "核桃",
    "刷什么", "现在刷", "当前刷", "可以刷", "有什么活动",
    "重生", "prime重生", "prime 重生", "resurgence", "prime resurgence", "prime vault",
}


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


def _is_specific_event_list_query(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in ("裂缝", "裂隙", "fissure", "虚空风暴", "风暴", "入侵", "invasion", "警报", "alert"))


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

    # 2. 私聊命令检测：有推荐卖家/买家时必须包含 /w
    has_recommendation = any(
        kw in answer for kw in ["推荐购买", "推荐出售", "推荐卖家", "推荐买家", "最低卖", "最高收"]
    )
    has_whisper = "/w " in answer or "/W " in answer
    # 2b. 无交易上下文时出现私聊命令 = LLM 混入了无关数据
    if has_whisper and not contexts:
        warnings.append("回答中包含私聊命令但查询与交易无关，可能混入了不相关数据")
    if has_recommendation and not has_whisper and contexts:
        for ctx in contexts:
            if ctx.best_sell_price or ctx.best_buy_price:
                warnings.append("有推荐交易对象但缺少 /w 私聊命令")
                break

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





