from __future__ import annotations

import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import config
from .names import preferred_chinese_name
from .trade_plan import safe_warframe_market_url

OPPORTUNITY_ID_PATTERN = re.compile(r"OP[A-Z0-9]{6}")
DEFAULT_TTL_HOURS = 48


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def normalize_opportunity_lookup_id(value: str) -> str:
    return str(value or "").strip().upper()


def is_opportunity_lookup_id(value: str) -> bool:
    return bool(OPPORTUNITY_ID_PATTERN.fullmatch(normalize_opportunity_lookup_id(value)))


@dataclass(frozen=True)
class OpportunityLookupDetail:
    lookup_id: str
    created_at: datetime
    expires_at: datetime
    item_id: str
    item_display: str
    plan_signature: str
    content: dict[str, Any]


class OpportunityLookupStore:
    def __init__(self, path: Path | str | None = None, *, now: Callable[[], datetime] = _utc_now):
        self.path = Path(path) if path is not None else config.DATA_DIR / "opportunity_lookup.db"
        self.now = now
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunity_details (
                    lookup_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    item_display TEXT NOT NULL,
                    plan_signature TEXT,
                    content_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_opportunity_details_expires_at ON opportunity_details(expires_at)")

    def create(self, item_id: str, item_display: str, plan: dict[str, Any], *, ttl_hours: int = DEFAULT_TTL_HOURS) -> str:
        self.cleanup_expired()
        created_at = self.now().astimezone(timezone.utc)
        expires_at = created_at + timedelta(hours=ttl_hours)
        content = _sanitize_plan(plan)
        plan_signature = str(content.get("plan_signature") or "")
        for _ in range(10):
            lookup_id = self._new_lookup_id()
            try:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO opportunity_details
                        (lookup_id, created_at, expires_at, item_id, item_display, plan_signature, content_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            lookup_id,
                            _iso(created_at),
                            _iso(expires_at),
                            str(item_id or content.get("item_id") or ""),
                            str(item_display or content.get("display_name") or content.get("item_id") or "交易机会"),
                            plan_signature,
                            json.dumps(content, ensure_ascii=False),
                        ),
                    )
                return lookup_id
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("无法生成唯一机会 ID")

    def get(self, lookup_id: str) -> OpportunityLookupDetail | None:
        self.cleanup_expired()
        normalized = normalize_opportunity_lookup_id(lookup_id)
        if not is_opportunity_lookup_id(normalized):
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT lookup_id, created_at, expires_at, item_id, item_display, plan_signature, content_json
                FROM opportunity_details
                WHERE lookup_id = ?
                """,
                (normalized,),
            ).fetchone()
        if not row:
            return None
        return OpportunityLookupDetail(
            lookup_id=row[0],
            created_at=_parse_iso(row[1]),
            expires_at=_parse_iso(row[2]),
            item_id=row[3],
            item_display=row[4],
            plan_signature=row[5] or "",
            content=json.loads(row[6]),
        )

    def cleanup_expired(self) -> int:
        cutoff = _iso(self.now().astimezone(timezone.utc))
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM opportunity_details WHERE expires_at <= ?", (cutoff,))
            return int(cur.rowcount or 0)

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM opportunity_details").fetchone()
        return int(row[0])

    def _new_lookup_id(self) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "OP" + "".join(secrets.choice(alphabet) for _ in range(6))


def _sanitize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    content = dict(plan or {})
    content["buy_steps"] = [_sanitize_step(step) for step in content.get("buy_steps") or [] if isinstance(step, dict)]
    content["sell_steps"] = [_sanitize_step(step) for step in content.get("sell_steps") or [] if isinstance(step, dict)]
    return content


def _sanitize_step(step: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(step)
    cleaned["market_url"] = safe_warframe_market_url(str(cleaned.get("market_url") or ""))
    cleaned["profile_url"] = safe_warframe_market_url(str(cleaned.get("profile_url") or ""))
    cleaned["whisper"] = str(cleaned.get("whisper") or "")
    return cleaned


def opportunity_not_found_message(lookup_id: str) -> str:
    normalized = normalize_opportunity_lookup_id(lookup_id)
    return f"机会 ID {normalized} 不存在或已过期。请等待下一次推送，或重新运行相关扫描。"


def format_opportunity_lookup_reply(detail: OpportunityLookupDetail | None, *, now: datetime | None = None) -> str:
    if detail is None:
        return "机会 ID 不存在或已过期。请等待下一次推送，或重新运行相关扫描。"
    current = (now or _utc_now()).astimezone(timezone.utc)
    remaining_hours = max(0, int((detail.expires_at - current).total_seconds() // 3600))
    plan = detail.content
    profit = plan.get("profit", 0)
    profit_text = f"+{profit}" if isinstance(profit, (int, float)) and profit >= 0 else str(profit)
    lines = [
        f"机会 {detail.lookup_id}：{_detail_display_name(detail)}",
        "",
        f"策略：{plan.get('display_strategy') or plan.get('strategy') or '-'}",
    ]
    if _looks_like_set_plan(plan):
        lines.append("说明：Set 订单不是单独物品，游戏内需交付全部对应部件。")
    lines.extend([
        f"成本：{plan.get('total_cost', 0)}p",
        f"目标收入：{plan.get('total_revenue', 0)}p",
        f"预计利润：{profit_text}p",
        f"ROI：{plan.get('roi_pct', 0)}%",
        f"风险：{plan.get('risk_level') or '-'}",
        f"有效期：剩余 {remaining_hours} 小时",
    ])
    buy_steps = plan.get("buy_steps") or []
    sell_steps = plan.get("sell_steps") or []
    if buy_steps:
        lines.extend(["", _buy_section_title(plan)])
        lines.extend(_format_steps(buy_steps))
    if sell_steps:
        lines.extend(["", _sell_section_title(plan)])
        lines.extend(_format_steps(sell_steps))
    lines.extend(["", "提示：该机会基于推送时快照，订单可能变化，请以 warframe.market 实时状态为准。"])
    return "\n".join(lines)


def _detail_display_name(detail: OpportunityLookupDetail) -> str:
    plan = detail.content
    english_name = _english_display_name(str(plan.get("display_name") or detail.item_display or detail.item_id))
    chinese_name = str(plan.get("zh_name") or plan.get("cn_name") or "").strip()
    if not chinese_name:
        chinese_name = _chinese_from_display_name(str(plan.get("display_name") or ""))
    if not chinese_name:
        chinese_name = preferred_chinese_name(detail.item_id) or ""
    if chinese_name and chinese_name != english_name:
        return f"{english_name}（游戏内：{chinese_name}）"
    return english_name


def _english_display_name(value: str) -> str:
    parts = [part.strip() for part in str(value or "").split("/")]
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return str(value or "交易机会").strip() or "交易机会"


def _chinese_from_display_name(value: str) -> str:
    parts = [part.strip() for part in str(value or "").split("/")]
    if len(parts) >= 2 and _has_chinese(parts[0]):
        return parts[0]
    return ""


def _has_chinese(value: str) -> bool:
    return any("一" <= char <= "鿿" for char in value)


def _looks_like_set_plan(plan: dict[str, Any]) -> bool:
    text = " ".join(str(plan.get(key) or "") for key in ("item_id", "strategy", "display_strategy"))
    return "set" in text.lower() or "套装" in text or "整套" in text


def _buy_section_title(plan: dict[str, Any]) -> str:
    source = str(plan.get("source") or "")
    strategy = str(plan.get("strategy") or "")
    if source == "arcane_flip" or strategy.startswith("arcane_r0_to_r"):
        required = plan.get("required_quantity") or sum(int(step.get("quantity") or 0) for step in plan.get("buy_steps") or [])
        return f"赋能满级合成买入：需要 R0 × {required}"
    if source == "mod_flip" or strategy.startswith("mod_r0_to_r"):
        return "MOD 升级买入："
    if strategy == "buy_set_sell_parts":
        return "买入完整套装订单：需确认卖家能一次性交付全部部件"
    return "需要买入的部件：" if _looks_like_set_plan(plan) else "买入："


def _sell_section_title(plan: dict[str, Any]) -> str:
    source = str(plan.get("source") or "")
    strategy = str(plan.get("strategy") or "")
    if source == "arcane_flip" or strategy.startswith("arcane_r0_to_r"):
        return "满级赋能卖出买家："
    if source == "mod_flip" or strategy.startswith("mod_r0_to_r"):
        return "满级 MOD 卖出买家："
    if strategy == "buy_set_sell_parts":
        return "拆分卖出部件：逐个匹配部件买家"
    return "完整套装订单买家：" if _looks_like_set_plan(plan) else "卖出："


def _format_steps(steps: list[dict[str, Any]]) -> list[str]:
    lines = []
    for index, step in enumerate(steps, 1):
        label = str(step.get("label") or step.get("display_name") or step.get("item_id") or "交易步骤")
        player = str(step.get("player") or "未知玩家")
        unit_price = step.get("unit_price", "-")
        quantity = step.get("quantity", 1)
        subtotal = step.get("subtotal", "-")
        lines.append(f"{index}. {label} — {player} — {unit_price}p × {quantity} = {subtotal}p")
        market_url = safe_warframe_market_url(str(step.get("market_url") or ""))
        profile_url = safe_warframe_market_url(str(step.get("profile_url") or ""))
        whisper = str(step.get("whisper") or "")
        if market_url:
            lines.append(f"   市场：{market_url}")
        if profile_url:
            lines.append(f"   玩家主页：{profile_url}")
        if whisper:
            lines.append(f"   游戏内私聊：{whisper}")
    return lines
