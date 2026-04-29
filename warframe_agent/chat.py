from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Iterable

import requests

from . import config
from .dictionary import ItemResolver, normalize_lookup_key
from .formatter import build_whisper
from .market import MarketOrder, best_buyers, best_sellers, fetch_orders
from .memory import AgentMemory
from .names import display_item_name
from .price_history import PriceHistoryDB
from .rag import search_rag_items
from .session import SessionContext, is_followup
from .tool_router import build_router_prompt, parse_tool_call
from .trade_intent import detect_trade_intent
from .warframes import price_warframe_query


EXIT_COMMANDS = {"q", "quit", "exit", "退出", "关闭"}
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
    sellers = best_sellers(order_list, limit=5)
    buyers = best_buyers(order_list, limit=5)
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
    if item_id.startswith("arcane_") and best_seller:
        lines.append(f"满级估算: 21 个约 {best_seller.platinum * 21}p")
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
    ):
        self.resolver = resolver or ItemResolver()
        self.order_fetcher = order_fetcher
        self.model_call = model_call or call_ollama_chat
        self.watchlist = watchlist
        self.memory_path = memory_path or config.AGENT_MEMORY_PATH
        self.memory = memory or AgentMemory.load(self.memory_path)
        self.rag_search = rag_search or self._default_rag_search
        self.warframe_items = warframe_items
        self.price_db = price_db
        self.session = SessionContext()
        self.router_call = router_call

    def answer(self, message: str) -> str:
        stripped = message.strip()
        if stripped.startswith("/"):
            return self._handle_agent_command(stripped)
        if is_watchlist_command(message):
            return self.scan_watchlist()
        self._remember_common_question(message)
        warframe_answer = price_warframe_query(message, self.warframe_items, self.order_fetcher)
        if warframe_answer:
            self.session.add_exchange(message, warframe_answer)
            return warframe_answer
        if is_followup(message) and self.session.has_context():
            contexts = self._contexts_for_items(self.session.last_item_ids)
        else:
            contexts = self._contexts_for_message(message)
        if not contexts:
            routed = self._try_router(message)
            if routed:
                self.session.add_exchange(message, routed)
                return routed
            return "没有找到匹配的物品，请输入 warframe.market 的 item_id，例如：充沛 / arcane_energize"
        self.session.update([ctx.item_id for ctx in contexts])
        deterministic_answer = _deterministic_trade_intent_answer(message, contexts)
        if deterministic_answer:
            self.session.add_exchange(message, deterministic_answer)
            return deterministic_answer
        prompt = build_chat_prompt(message, contexts, self.memory)
        try:
            answer = self.model_call(prompt).strip()
            if answer:
                self.session.add_exchange(message, answer)
                return answer
        except Exception:
            result = fallback_answer(message, contexts, llm_failed=True)
            self.session.add_exchange(message, result)
            return result
        result = fallback_answer(message, contexts)
        self.session.add_exchange(message, result)
        return result

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
        ])

    def _render_memory_summary(self) -> str:
        favorites = "、".join(display_item_name(item_id) for item_id in self.memory.favorite_items[:5]) or "无"
        alerts = "、".join(
            f"{display_item_name(alert.item_id)} {('低于' if alert.direction == 'below' else '高于')} {alert.price}p"
            for alert in self.memory.price_alerts[:5]
        ) or "无"
        questions = "、".join(self.memory.common_questions[-5:]) or "无"
        return "\n".join([
            "记忆摘要：",
            f"偏好: platform={self.memory.preferences.platform}, crossplay={self.memory.preferences.crossplay}, max_results={self.memory.preferences.max_results}",
            f"关注物品: {favorites}",
            f"价格提醒: {alerts}",
            f"常见问题: {questions}",
        ])

    def _handle_favorite_command(self, args: list[str]) -> str:
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
            except Exception:
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

    def _resolve_item_id_for_command(self, item_name: str) -> str | None:
        try:
            return self.resolver.resolve(item_name).item_id
        except (LookupError, ValueError):
            matches = self._item_ids_from_alias_substrings(item_name)
            return matches[0] if matches else None

    def _try_router(self, message: str) -> str | None:
        caller = self.router_call or self.model_call
        try:
            router_prompt = build_router_prompt(message)
            raw = caller(router_prompt).strip()
            tool_call = parse_tool_call(raw)
            if not tool_call:
                return None
            return self._execute_tool_call(tool_call, message)
        except Exception:
            return None

    def _execute_tool_call(self, tool_call, message: str) -> str | None:
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
        if tool_call.name == "general_chat":
            return None
        return None

    def _remember_common_question(self, message: str) -> None:
        self.memory = self.memory.with_common_question(message)
        self._persist_memory()

    def _persist_memory(self) -> None:
        self.memory.save(self.memory_path)

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
        return [result.item_id for result in search_rag_items(message, limit=3)]

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


def _deterministic_trade_intent_answer(message: str, contexts: list[ItemContext]) -> str | None:
    intent = detect_trade_intent(message)
    if intent == "overview" or len(contexts) != 1:
        return None
    return _render_trade_intent_context(contexts[0], intent)


def _render_trade_intent_context(context: ItemContext, intent: str) -> str:
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
    if context.item_id.startswith("arcane_") and context.best_sell_price is not None:
        lines.append(f"满级估算: 21 个约 {context.best_sell_price * 21}p")
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
    lines = [
        f"偏好: platform={memory.preferences.platform}, crossplay={memory.preferences.crossplay}, max_results={memory.preferences.max_results}",
    ]
    if memory.favorite_items:
        lines.append(f"常看物品: {', '.join(memory.favorite_items)}")
    for context in contexts:
        if context.best_sell_price is None:
            continue
        for alert in memory.alerts_for(context.item_id, context.best_sell_price):
            lines.append(f"记忆提醒: {alert.note or context.item_id}")
    return "\n".join(lines)



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


def _load_watchlist() -> dict[str, list[str]]:
    if not config.WATCHLIST_PATH.exists():
        return {}
    with config.WATCHLIST_PATH.open("r", encoding="utf-8-sig") as file:
        return json.load(file)





