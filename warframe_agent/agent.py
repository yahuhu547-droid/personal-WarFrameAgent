from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import requests

try:
    import pyperclip
except ImportError:
    pyperclip = None

from . import config
from .dictionary import ItemResolver, ResolveResult
from .formatter import build_whisper, format_lookup_result
from .llm import resolve_with_ollama
from .market import best_buyers, best_sellers, fetch_orders, validate_item_id
from .report import write_daily_report


CATEGORY_LABELS = {
    "arcanes": "赋能",
    "prime_warframe_parts": "Prime 战甲部件",
    "popular_mods": "热门 Mod",
}


@dataclass(frozen=True)
class LookupResult:
    item_id: str
    source: str
    text: str
    copied_command: str | None


class WarframeAgent:
    def __init__(self, resolver: ItemResolver | None = None):
        self.resolver = resolver or ItemResolver(fallback=self._llm_and_validate)

    def lookup_item(self, name: str, copy_first: bool = True) -> LookupResult:
        resolved = self.resolver.resolve(name)
        orders = fetch_orders(resolved.item_id)
        sellers = best_sellers(orders)
        buyers = best_buyers(orders)
        copied_command = None
        if copy_first and sellers:
            copied_command = build_whisper(sellers[0].user_name, resolved.item_id, sellers[0].platinum, "sell")
            self._copy_to_clipboard(copied_command)
        text = format_lookup_result(resolved.item_id, resolved.source, sellers, buyers)
        if copied_command:
            text += f"\n\n已复制第一条推荐卖家私聊命令：\n{copied_command}"
        return LookupResult(resolved.item_id, resolved.source, text, copied_command)

    def rebuild_dictionary(self) -> int:
        return self.resolver.rebuild_cache()

    def generate_daily_report(self) -> Path:
        rows = []
        for category_key, item_ids in self._load_watchlist().items():
            category = CATEGORY_LABELS.get(category_key, category_key)
            for item_id in item_ids:
                rows.append(self._report_row(category, item_id))
        return write_daily_report(rows)

    def daily_summary(self, report_path: Path) -> str:
        return f"每日报告已生成：{report_path}"

    def _report_row(self, category: str, item_id: str) -> dict:
        try:
            orders = fetch_orders(item_id)
            return {
                "category": category,
                "item_id": item_id,
                "sellers": best_sellers(orders),
                "buyers": best_buyers(orders),
                "error": None,
            }
        except requests.RequestException as exc:
            return {
                "category": category,
                "item_id": item_id,
                "sellers": [],
                "buyers": [],
                "error": str(exc),
            }

    def _load_watchlist(self) -> dict[str, list[str]]:
        if not config.WATCHLIST_PATH.exists():
            return {}
        with config.WATCHLIST_PATH.open("r", encoding="utf-8-sig") as file:
            return json.load(file)

    @staticmethod
    def _copy_to_clipboard(command: str) -> None:
        if pyperclip is None:
            return
        try:
            pyperclip.copy(command)
        except pyperclip.PyperclipException:
            pass

    @staticmethod
    def _llm_and_validate(name: str) -> str | None:
        try:
            item_id = resolve_with_ollama(name)
        except Exception:
            return None
        if item_id and validate_item_id(item_id):
            return item_id
        return None
