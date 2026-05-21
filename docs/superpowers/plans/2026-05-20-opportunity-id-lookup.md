# Opportunity ID Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add short-lived opportunity IDs to actionable trading opportunity pushes so the user can type the ID in Feishu/chat and receive all related market links, player profile links, and in-game whisper commands.

**Architecture:** Add a focused `opportunity_lookup` module that owns ID generation, short-term SQLite storage, expiry cleanup, and Feishu/chat response formatting. Wire push delivery to create lookup records only when a proactive opportunity has a `trade_plan`, pass the generated ID into WxPusher/Feishu formatting, and route bare IDs plus `/opp` commands in `ChatAgent` before ordinary item lookup. Keep long-term `push_history` sanitized.

**Tech Stack:** Python, sqlite3, pytest, existing `warframe_agent` modules (`trade_plan`, `push`, `chat`, `web.app`, `feishu`).

---

## File structure

- Create `warframe_agent/opportunity_lookup.py`: short-term opportunity lookup store, ID matching, response formatting.
- Modify `warframe_agent/push.py`: accept optional opportunity ID in `format_trade_plan_push()` and prepend the WxPusher lookup hint.
- Modify `warframe_agent/feishu.py`: accept optional opportunity ID in `build_trade_plan_card_elements()` and show lookup hint in Feishu proactive card.
- Modify `warframe_agent/web/app.py`: create lookup records in `broadcast_proactive_push()` and pass ID to push/card formatters and WebSocket payload.
- Modify `warframe_agent/chat.py`: instantiate lookup store and route bare IDs plus `/opp`, `/opportunity`, `/机会` commands.
- Add `tests/test_opportunity_lookup.py`: store, expiry, ID, formatting tests.
- Modify `tests/test_push.py`: verify WxPusher ID hint.
- Modify `tests/test_feishu.py`: verify Feishu card ID hint.
- Modify/add chat tests in `tests/test_chat.py`: verify lookup routing.
- Update `md/rebuilt/05-data-memory.md` and `md/rebuilt/07-operations-testing.md` after implementation.

## Task 1: Opportunity lookup store and formatter

**Files:**
- Create: `warframe_agent/opportunity_lookup.py`
- Test: `tests/test_opportunity_lookup.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_opportunity_lookup.py` with:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from warframe_agent.opportunity_lookup import (
    OPPORTUNITY_ID_PATTERN,
    OpportunityLookupStore,
    format_opportunity_lookup_reply,
    is_opportunity_lookup_id,
)


def _plan() -> dict:
    return {
        "display_name": "Akbolto Prime",
        "display_strategy": "拆件买入 -> 完整套装订单卖出",
        "strategy": "buy_parts_sell_set",
        "item_id": "akbolto_prime_set",
        "total_cost": 39,
        "total_revenue": 80,
        "profit": 35,
        "roi_pct": 89.7,
        "risk_level": "medium",
        "plan_signature": "sig-akbolto",
        "buy_steps": [
            {
                "label": "Akbolto Prime Blueprint",
                "player": "SellerA",
                "unit_price": 10,
                "quantity": 1,
                "subtotal": 10,
                "market_url": "https://warframe.market/items/akbolto_prime_blueprint",
                "profile_url": "https://warframe.market/profile/SellerA",
                "whisper": "/w SellerA Hi! I want to buy.",
            }
        ],
        "sell_steps": [
            {
                "label": "Akbolto Prime Set",
                "player": "BuyerD",
                "unit_price": 80,
                "quantity": 1,
                "subtotal": 80,
                "market_url": "https://warframe.market/items/akbolto_prime_set",
                "profile_url": "https://warframe.market/profile/BuyerD",
                "whisper": "/w BuyerD Hi! I want to sell.",
            }
        ],
    }


def test_create_and_get_opportunity_detail(tmp_path):
    store = OpportunityLookupStore(tmp_path / "lookup.db")

    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", _plan())
    detail = store.get(lookup_id)

    assert OPPORTUNITY_ID_PATTERN.fullmatch(lookup_id)
    assert detail is not None
    assert detail.lookup_id == lookup_id
    assert detail.item_display == "Akbolto Prime"
    assert detail.content["buy_steps"][0]["player"] == "SellerA"
    assert detail.content["sell_steps"][0]["whisper"].startswith("/w BuyerD")


def test_get_requires_exact_lookup_id(tmp_path):
    store = OpportunityLookupStore(tmp_path / "lookup.db")
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", _plan())

    assert store.get(lookup_id.lower()) is not None
    assert store.get(lookup_id[:4]) is None


def test_expired_record_is_removed(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", _plan(), ttl_hours=1)

    later = datetime(2026, 5, 20, 14, 0, tzinfo=timezone.utc)
    expired_store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: later)

    assert expired_store.get(lookup_id) is None
    assert expired_store.count() == 0


def test_is_opportunity_lookup_id():
    assert is_opportunity_lookup_id("OP8K3A2Q") is True
    assert is_opportunity_lookup_id("op8k3a2q") is True
    assert is_opportunity_lookup_id("AKBOLTO") is False
    assert is_opportunity_lookup_id("OP123") is False


def test_format_reply_includes_links_whispers_and_set_order_note(tmp_path):
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    store = OpportunityLookupStore(tmp_path / "lookup.db", now=lambda: now)
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", _plan())
    detail = store.get(lookup_id)

    text = format_opportunity_lookup_reply(detail, now=now + timedelta(hours=1))

    assert f"机会 {lookup_id}：Akbolto Prime" in text
    assert "Set 订单不是单独物品" in text
    assert "完整套装订单买家" in text
    assert "https://warframe.market/items/akbolto_prime_blueprint" in text
    assert "https://warframe.market/profile/SellerA" in text
    assert "/w SellerA Hi! I want to buy." in text
    assert "有效期：剩余 47 小时" in text
    assert "请以 warframe.market 实时状态为准" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_opportunity_lookup.py -v`

Expected: FAIL because `warframe_agent.opportunity_lookup` does not exist.

- [ ] **Step 3: Implement module**

Create `warframe_agent/opportunity_lookup.py` with:

```python
from __future__ import annotations

import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import config
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

    def _connect(self):
        return sqlite3.connect(self.path)

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
        f"机会 {detail.lookup_id}：{detail.item_display}",
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


def _looks_like_set_plan(plan: dict[str, Any]) -> bool:
    text = " ".join(str(plan.get(key) or "") for key in ("item_id", "strategy", "display_strategy"))
    return "set" in text.lower() or "套装" in text or "整套" in text


def _buy_section_title(plan: dict[str, Any]) -> str:
    strategy = str(plan.get("strategy") or "")
    if strategy == "buy_set_sell_parts":
        return "买入完整套装订单：需确认卖家能一次性交付全部部件"
    return "需要买入的部件：" if _looks_like_set_plan(plan) else "买入："


def _sell_section_title(plan: dict[str, Any]) -> str:
    strategy = str(plan.get("strategy") or "")
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_opportunity_lookup.py -v`

Expected: PASS.

## Task 2: WxPusher and Feishu ID hints

**Files:**
- Modify: `warframe_agent/push.py:137-162`
- Modify: `warframe_agent/feishu.py`
- Test: `tests/test_push.py`
- Test: `tests/test_feishu.py`

- [ ] **Step 1: Add failing WxPusher test**

Append to `TestTradePlanPushFormatting` in `tests/test_push.py`:

```python
    def test_format_trade_plan_push_includes_opportunity_id_hint(self):
        text = format_trade_plan_push({
            "display_name": "Akbolto Prime",
            "display_strategy": "拆件买入 -> 完整套装订单卖出",
            "total_cost": 39,
            "total_revenue": 80,
            "profit": 35,
            "roi_pct": 89.7,
            "risk_level": "medium",
            "buy_steps": [],
            "sell_steps": [],
        }, opportunity_id="OP8K3A2Q")

        assert "机会ID：OP8K3A2Q" in text
        assert "在飞书输入 OP8K3A2Q" in text
        assert "48 小时" in text
        assert "请以实时市场为准" in text
```

- [ ] **Step 2: Add failing Feishu test**

In `tests/test_feishu.py`, update or add a test around `build_trade_plan_card_elements()`:

```python
def test_trade_plan_card_includes_opportunity_id_hint():
    elements = build_trade_plan_card_elements({
        "display_name": "Akbolto Prime",
        "display_strategy": "拆件买入 -> 完整套装订单卖出",
        "total_cost": 39,
        "total_revenue": 80,
        "profit": 35,
        "roi_pct": 89.7,
        "risk_level": "medium",
        "buy_steps": [],
        "sell_steps": [],
    }, opportunity_id="OP8K3A2Q")

    text = "\n".join(str(element) for element in elements)
    assert "机会ID：OP8K3A2Q" in text
    assert "在飞书输入 OP8K3A2Q" in text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_push.py::TestTradePlanPushFormatting tests/test_feishu.py -v`

Expected: FAIL because the formatters do not accept `opportunity_id` yet.

- [ ] **Step 4: Implement formatter changes**

In `warframe_agent/push.py`, change the signature and first lines of `format_trade_plan_push()`:

```python
def format_trade_plan_push(plan: dict, opportunity_id: str = "") -> str:
    """格式化可执行交易计划，用于 WxPusher Markdown。"""
    if not isinstance(plan, dict):
        return ""
    display_name = plan.get("display_name") or plan.get("item_id") or "交易机会"
    profit = plan.get("profit", 0)
    profit_text = f"+{profit}" if isinstance(profit, (int, float)) and profit >= 0 else str(profit)
    lines = [f"## 交易机会：{display_name}"]
    if opportunity_id:
        lines.extend([
            f"机会ID：{opportunity_id}",
            f"在飞书输入 {opportunity_id} 查看买卖双方链接、玩家主页和游戏内私聊命令。",
            "该 ID 约 48 小时后过期；机会基于推送时快照，请以实时市场为准。",
            "",
        ])
    lines.extend([
        f"策略：{plan.get('display_strategy') or plan.get('strategy') or '-'}",
        f"成本：{plan.get('total_cost', 0)}p",
        f"收入：{plan.get('total_revenue', 0)}p",
        f"利润：{profit_text}p",
        f"ROI：{plan.get('roi_pct', 0)}%",
    ])
```

Keep the existing risk, buy steps, sell steps, and return logic unchanged.

In `warframe_agent/feishu.py`, change `build_trade_plan_card_elements(plan)` to `build_trade_plan_card_elements(plan, opportunity_id: str = "")`, and after the summary block insert an ID hint block when present:

```python
    if opportunity_id:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**机会ID：{opportunity_id}**\n在飞书输入 `{opportunity_id}` 查看买卖双方链接、玩家主页和游戏内私聊命令。\n该 ID 约 48 小时后过期；机会基于推送时快照，请以实时市场为准。",
            },
        })
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_push.py::TestTradePlanPushFormatting tests/test_feishu.py -v`

Expected: PASS.

## Task 3: Wire push delivery to create IDs

**Files:**
- Modify: `warframe_agent/web/app.py:2703-2759`
- Test: add focused tests if existing web tests can import `broadcast_proactive_push`; otherwise verify through formatter and chat tests plus full targeted suite.

- [ ] **Step 1: Implement push wiring**

In `warframe_agent/web/app.py`, import `OpportunityLookupStore` near other imports:

```python
from warframe_agent.opportunity_lookup import OpportunityLookupStore
```

In `broadcast_proactive_push()`, after `safe_summary` is computed, add:

```python
    opportunity_id = ""
    if push.push_type == "opportunity" and isinstance(trade_plan, dict):
        try:
            opportunity_id = OpportunityLookupStore().create(push.item_id, push.item_display, trade_plan)
        except Exception as exc:
            logger.debug("交易机会 ID 生成失败: %s", exc)
```

Add `"opportunity_id": opportunity_id` to the WebSocket `message` dict.

Change the WxPusher call to:

```python
format_trade_plan_push(trade_plan, opportunity_id=opportunity_id)
```

Change the Feishu card call to:

```python
build_trade_plan_card_elements(trade_plan, opportunity_id=opportunity_id)
```

- [ ] **Step 2: Run existing proactive/push tests**

Run: `pytest tests/test_push.py tests/test_feishu.py tests/test_proactive_push.py -v`

Expected: PASS.

## Task 4: Chat and Feishu lookup routing

**Files:**
- Modify: `warframe_agent/chat.py:1-39`, `warframe_agent/chat.py:360-398`, `warframe_agent/chat.py:540-548`, `warframe_agent/chat.py:886-895`, `warframe_agent/chat.py:1078-1145`
- Test: `tests/test_chat.py`

- [ ] **Step 1: Add failing chat tests**

Add to `tests/test_chat.py`:

```python
from warframe_agent.opportunity_lookup import OpportunityLookupStore


def test_chat_returns_opportunity_detail_for_bare_id(tmp_path):
    store = OpportunityLookupStore(tmp_path / "lookup.db")
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", {
        "display_name": "Akbolto Prime",
        "display_strategy": "拆件买入 -> 完整套装订单卖出",
        "strategy": "buy_parts_sell_set",
        "item_id": "akbolto_prime_set",
        "total_cost": 39,
        "total_revenue": 80,
        "profit": 35,
        "roi_pct": 89.7,
        "risk_level": "medium",
        "buy_steps": [{
            "label": "Akbolto Prime Blueprint",
            "player": "SellerA",
            "unit_price": 10,
            "quantity": 1,
            "subtotal": 10,
            "market_url": "https://warframe.market/items/akbolto_prime_blueprint",
            "profile_url": "https://warframe.market/profile/SellerA",
            "whisper": "/w SellerA Hi! I want to buy.",
        }],
        "sell_steps": [],
    })
    agent = ChatAgent(opportunity_lookup_store=store)

    reply = agent.answer(lookup_id)

    assert f"机会 {lookup_id}：Akbolto Prime" in reply
    assert "https://warframe.market/profile/SellerA" in reply
    assert "/w SellerA Hi! I want to buy." in reply


def test_chat_returns_opportunity_detail_for_opp_command(tmp_path):
    store = OpportunityLookupStore(tmp_path / "lookup.db")
    lookup_id = store.create("akbolto_prime_set", "Akbolto Prime", {
        "display_name": "Akbolto Prime",
        "display_strategy": "拆件买入 -> 完整套装订单卖出",
        "strategy": "buy_parts_sell_set",
        "item_id": "akbolto_prime_set",
        "total_cost": 39,
        "total_revenue": 80,
        "profit": 35,
        "roi_pct": 89.7,
        "risk_level": "medium",
        "buy_steps": [],
        "sell_steps": [],
    })
    agent = ChatAgent(opportunity_lookup_store=store)

    assert f"机会 {lookup_id}：Akbolto Prime" in agent.answer(f"/opp {lookup_id}")
    assert f"机会 {lookup_id}：Akbolto Prime" in agent.answer(f"/机会 {lookup_id}")


def test_chat_missing_opportunity_id_does_not_fall_through_to_item_search(tmp_path):
    store = OpportunityLookupStore(tmp_path / "lookup.db")
    agent = ChatAgent(opportunity_lookup_store=store)

    reply = agent.answer("OP8K3A2Q")

    assert "机会 ID OP8K3A2Q 不存在或已过期" in reply
    assert "没有找到匹配的物品" not in reply
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -v`

Expected: FAIL because `ChatAgent` does not accept `opportunity_lookup_store` and does not route IDs.

- [ ] **Step 3: Implement chat routing**

In `warframe_agent/chat.py`, add imports:

```python
from .opportunity_lookup import (
    OpportunityLookupStore,
    format_opportunity_lookup_reply,
    is_opportunity_lookup_id,
    opportunity_not_found_message,
    normalize_opportunity_lookup_id,
)
```

Add `opportunity_lookup_store=None` to `ChatAgent.__init__()` parameters and set:

```python
        self.opportunity_lookup_store = opportunity_lookup_store or OpportunityLookupStore()
```

In `answer()`, after `stripped = message.strip()` and before slash command handling, add:

```python
        if is_opportunity_lookup_id(stripped):
            result = self._handle_opportunity_lookup([stripped])
            self._log_answer(message, result)
            return result
```

In `answer_stream()`, after `stripped = message.strip()` and before slash command handling, add the same check but `yield result` and `return`.

In `_handle_agent_command()`, before the final unknown command, add:

```python
        if command in {"/opp", "/opportunity", "/机会"}:
            return self._handle_opportunity_lookup(tokens[1:])
```

In `_command_help()`, add:

```python
            "/opp 机会ID       查看推送机会的市场链接和游戏内私聊命令",
```

Add method near `_handle_push_command()`:

```python
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
```

- [ ] **Step 4: Run chat tests**

Run: `pytest tests/test_chat.py -v`

Expected: PASS.

## Task 5: Documentation updates in md/rebuilt

**Files:**
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/07-operations-testing.md`

- [ ] **Step 1: Read docs**

Read both files and find sections about memory/storage and operations/testing.

- [ ] **Step 2: Update data/memory doc**

Add a concise section describing `data/opportunity_lookup.db`:

```markdown
### 机会 ID 短期详情

交易机会推送如果带有可执行 `trade_plan`，系统会生成 `OPxxxxxx` 短 ID，并把完整买卖计划快照保存到 `data/opportunity_lookup.db`。该库只用于飞书/聊天输入 ID 后返回 warframe.market 链接、玩家主页和游戏内私聊命令，默认 48 小时过期，并在读写时清理。长期 `push_history` 仍只保存安全摘要，不保存玩家名、链接或 whisper。
```

- [ ] **Step 3: Update operations/testing doc**

Add a concise testing/usage note:

```markdown
### 交易机会 ID 验证

当 WxPusher 收到带 `机会ID：OPxxxxxx` 的交易机会后，可在飞书或聊天框直接输入该 ID，也可输入 `/opp OPxxxxxx` 或 `/机会 OPxxxxxx`。预期回复包含买入/卖出步骤、warframe.market 链接、玩家主页、游戏内私聊命令和 48 小时有效期提示。过期或不存在的 ID 应返回明确过期提示，不应落入普通物品搜索。
```

- [ ] **Step 4: No docs-only tests needed**

Proceed to full targeted validation.

## Task 6: Full targeted validation

**Files:**
- All modified files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest tests/test_opportunity_lookup.py tests/test_push.py tests/test_feishu.py tests/test_chat.py tests/test_proactive_push.py -v
```

Expected: PASS.

- [ ] **Step 2: Run broader relevant tests**

Run:

```bash
pytest tests/test_tool_router.py tests/test_tool_registry.py tests/test_experts.py -v
```

Expected: PASS.

- [ ] **Step 3: Inspect git diff**

Run:

```bash
git diff -- warframe_agent/opportunity_lookup.py warframe_agent/push.py warframe_agent/feishu.py warframe_agent/web/app.py warframe_agent/chat.py tests/test_opportunity_lookup.py tests/test_push.py tests/test_feishu.py tests/test_chat.py md/rebuilt/05-data-memory.md md/rebuilt/07-operations-testing.md docs/superpowers/specs/2026-05-20-opportunity-id-lookup-design.md docs/superpowers/plans/2026-05-20-opportunity-id-lookup.md
```

Expected: Diff only contains the intended opportunity ID lookup feature, spec/plan docs, and requested rebuilt docs updates.

---

## Self-review

Spec coverage:
- ID lifecycle: Task 1 and Task 3.
- Short-term storage and expiry: Task 1.
- WxPusher ID hint: Task 2 and Task 3.
- Feishu/chat ID lookup: Task 4.
- Set-order wording: Task 1 formatter tests and implementation.
- Cleanup: Task 1.
- Long-term memory safety boundary: Task 1 storage separation and Task 6 diff/testing, plus existing proactive push tests.
- `md/rebuilt` update: Task 5.

Placeholder scan: no TBD/TODO placeholders remain in implementation steps.

Type consistency: `OpportunityLookupStore`, `OpportunityLookupDetail`, `format_opportunity_lookup_reply`, `is_opportunity_lookup_id`, and `opportunity_id` names are used consistently across tasks.
