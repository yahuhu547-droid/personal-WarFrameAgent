"""WxPusher 微信推送模块。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from pathlib import Path

import requests

from . import config
from .formatter import build_whisper
from .trade_plan import trade_plan_step_lines

logger = logging.getLogger(__name__)

WXPUSHER_API = "https://wxpusher.zjiecode.com/api/send/message"
WXPUSHER_QR_API = "https://wxpusher.zjiecode.com/api/fun/create/qrcode"


@dataclass
class PushConfig:
    enabled: bool = False
    app_token: str = ""
    uids: list[str] = field(default_factory=list)
    push_alerts: bool = True
    push_watches: bool = True
    push_proactive: bool = True
    push_daily_report: bool = True
    report_time: str = "09:00"

    def save(self, path: Path = config.PUSH_CONFIG_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = config.PUSH_CONFIG_PATH) -> "PushConfig":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()


class WxPusher:
    def __init__(self, config: PushConfig):
        self.config = config

    @property
    def available(self) -> bool:
        return self.config.enabled and bool(self.config.app_token) and bool(self.config.uids)

    def send(self, title: str, content: str, content_type: int = 3) -> bool:
        if not self.available:
            return False
        payload = {
            "appToken": self.config.app_token,
            "content": content,
            "summary": title[:100],
            "contentType": content_type,
            "uids": self.config.uids,
        }
        try:
            resp = requests.post(WXPUSHER_API, json=payload, timeout=10)
            result = resp.json()
            if result.get("code") == 1000:
                logger.info("WxPusher 推送成功: %s", title)
                return True
            logger.warning("WxPusher 推送失败: %s", result.get("msg"))
            return False
        except Exception as exc:
            logger.warning("WxPusher 推送异常: %s", exc)
            return False

    def send_text(self, title: str, text: str) -> bool:
        return self.send(title, text, content_type=1)

    def send_markdown(self, title: str, md: str) -> bool:
        return self.send(title, md, content_type=3)


def _order_rank(order) -> int | None:
    return order.mod_rank if hasattr(order, "mod_rank") else order.get("mod_rank")


def _format_order_line(index: int, name: str, price: int, status: str, rank: int | None) -> str:
    details = f"Rank {rank}, {status}" if rank is not None else status
    return f"{index}. {name} - {price}p ({details})"


def format_buyers_with_whisper(item_name: str, market_id: str, buyers: list) -> str:
    """格式化买家列表，附带游戏内私聊命令。"""
    lines = [f"{item_name} 最高收价", ""]
    for i, b in enumerate(buyers, 1):
        name = b.user_name if hasattr(b, "user_name") else str(b.get("user_name", "?"))
        price = b.platinum if hasattr(b, "platinum") else b.get("platinum", 0)
        status = b.status if hasattr(b, "status") else b.get("status", "?")
        lines.append(_format_order_line(i, name, price, status, _order_rank(b)))
        lines.append(f"   {build_whisper(name, market_id, price, 'buy')}")
        lines.append("")
    lines.append(f"https://warframe.market/items/{market_id}")
    return "\n".join(lines)


def format_sellers_with_whisper(item_name: str, market_id: str, sellers: list) -> str:
    """格式化卖家列表，附带游戏内私聊命令。"""
    lines = [f"{item_name} 最低卖价", ""]
    for i, s in enumerate(sellers, 1):
        name = s.user_name if hasattr(s, "user_name") else str(s.get("user_name", "?"))
        price = s.platinum if hasattr(s, "platinum") else s.get("platinum", 0)
        status = s.status if hasattr(s, "status") else s.get("status", "?")
        lines.append(_format_order_line(i, name, price, status, _order_rank(s)))
        lines.append(f"   {build_whisper(name, market_id, price, 'sell')}")
        lines.append("")
    lines.append(f"https://warframe.market/items/{market_id}")
    return "\n".join(lines)


def _format_trade_plan_step(step: dict) -> str:
    lines = trade_plan_step_lines(step)
    if not lines:
        return ""
    head, *tail = lines
    result = [f"- {head}"]
    for line in tail:
        if line.startswith("/w "):
            result.append(f"  `{line}`")
        else:
            result.append(f"  {line}")
    return "\n".join(result)


def format_trade_plan_push(plan: dict) -> str:
    """格式化可执行交易计划，用于 WxPusher Markdown。"""
    if not isinstance(plan, dict):
        return ""
    display_name = plan.get("display_name") or plan.get("item_id") or "交易机会"
    profit = plan.get("profit", 0)
    profit_text = f"+{profit}" if isinstance(profit, (int, float)) and profit >= 0 else str(profit)
    lines = [
        f"## 交易机会：{display_name}",
        f"策略：{plan.get('display_strategy') or plan.get('strategy') or '-'}",
        f"成本：{plan.get('total_cost', 0)}p",
        f"收入：{plan.get('total_revenue', 0)}p",
        f"利润：{profit_text}p",
        f"ROI：{plan.get('roi_pct', 0)}%",
    ]
    if plan.get("risk_level"):
        lines.append(f"风险：{plan['risk_level']}")
    buy_steps = plan.get("buy_steps") or []
    if buy_steps:
        lines.extend(["", "### 买入"])
        lines.extend(_format_trade_plan_step(step) for step in buy_steps)
    sell_steps = plan.get("sell_steps") or []
    if sell_steps:
        lines.extend(["", "### 卖出"])
        lines.extend(_format_trade_plan_step(step) for step in sell_steps)
    return "\n".join(lines)


def should_send_daily_report(config: PushConfig) -> bool:
    """检查是否应该发送每日报告（时间窗口 ±6 分钟）。"""
    if not config.enabled or not config.push_daily_report:
        return False
    try:
        parts = config.report_time.split(":")
        target = dt_time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return False
    now = datetime.now().time()
    # 转为分钟比较
    now_min = now.hour * 60 + now.minute
    target_min = target.hour * 60 + target.minute
    return abs(now_min - target_min) <= 6
