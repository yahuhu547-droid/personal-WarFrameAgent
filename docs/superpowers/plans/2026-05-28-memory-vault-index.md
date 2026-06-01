# Memory Vault Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only, inspectable Memory Vault index over the existing safe trading memory and conversation summaries.

**Architecture:** Add a small `warframe_agent.memory_vault` module that converts allowlisted memory records into safe index entries and a Markdown preview. Expose it through a read-only FastAPI endpoint that uses existing `TradingMemoryDB.open_readonly_if_exists()` and `load_conversations()`, with no vector database, no cloud model calls, and no new dependencies.

**Tech Stack:** Python dataclasses, existing SQLite-backed `TradingMemoryDB`, existing `conversation_log` summaries, FastAPI `JSONResponse`, pytest.

---

## Context

- Source projects borrowed from: OpenHuman and CowAgent.
- Borrowed idea: memory should be inspectable as a durable knowledge vault, not only hidden model context.
- Warframe mapping: expose a safe, structured vault snapshot for future review, debugging, and cross-session continuity.
- Safety boundary: never expose raw user messages, raw assistant replies, raw tool args/results, player names, `/w` whispers, Warframe Market profile URLs, tokens, auth headers, cookies, chat IDs, or prompt-injection role markers.

## Completion Definition

- `GET /api/memory/vault` returns:
  - `generated_at`
  - `total`
  - `source_counts`
  - `entries`
  - `markdown_preview`
- Vault entries are built from existing safe sources:
  - `user_query`
  - `market_snapshot`
  - `recommendation`
  - `push_history`
  - `opportunity_outcome`
  - `conversation_log`
- Unit and API tests prove the vault includes useful facts while redacting sensitive data.
- Docs are synced to `githubProduct/`, `md/rebuilt/`, and `AGENTS.md`.

## File Structure

- Create: `warframe_agent/memory_vault.py`
  - Owns `MemoryVaultEntry`, `MemoryVaultSnapshot`, snapshot building, safe serialization, Markdown preview generation.
- Create: `tests/test_memory_vault.py`
  - Unit tests for vault aggregation, ordering, limits, Markdown preview, and sensitive data filtering.
- Modify: `warframe_agent/web/app.py`
  - Adds `_query_memory_vault()` helper and `GET /api/memory/vault`.
- Modify: `tests/test_web_api.py`
  - Adds API coverage for the new read-only endpoint.
- Create: `githubProduct/personal_agent_warframe_migration_step37_memory_vault_index_zh.md`
  - Records the learning source, borrowed point, implementation boundary, and verification.
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
  - Adds Step 37 route ledger entry.
- Modify: `md/rebuilt/05-data-memory.md`
  - Adds the vault index to the data and memory map.
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - Adds Step 37 to the personal-agent foundation timeline.
- Modify: `md/rebuilt/10-learning-route-audit.md`
  - Adds the Step 37 audit result.
- Modify: `AGENTS.md`
  - Updates current progress, commands, verification summary, and next-step queue.

## Task 1: Unit Red Test

**Files:**
- Create: `tests/test_memory_vault.py`

- [x] **Step 1: Write failing vault safety test**

Add this test file:

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from warframe_agent.conversation_log import ConversationEntry
from warframe_agent.trading_memory import TradingMemoryDB


class MemoryVaultTests(unittest.TestCase):
    def _build_db(self, path: Path) -> TradingMemoryDB:
        db = TradingMemoryDB(db_path=path)
        db.record_user_query_summary(
            intent="investment_advice",
            item_name="arcane_energize",
            metadata={
                "context_item_ids": ["arcane_energize"],
                "tool_names": ["query_price", "investment_advisor"],
                "context_count": 1,
                "tool_count": 2,
                "tool_ok_count": 2,
                "item_source": "tool_args_resolved",
            },
        )
        db.record_market_snapshot(
            "arcane_energize",
            "price_monitor.scan",
            {
                "item_id": "arcane_energize",
                "sell_price": 45,
                "buy_price": 38,
                "spread": 7,
                "token": "secret-token",
                "seller": "Seller_RAW",
                "whisper": "/w Seller_RAW hi",
            },
        )
        db.record_recommendation(
            "arcane_energize",
            "opportunity",
            reason="ROI is high /w Seller_RAW token=secret-token",
            payload={"priority": 1, "roi_pct": 42, "profile_url": "https://warframe.market/profile/Seller_RAW"},
        )
        db.record_push(
            "opportunity",
            "push body /w Seller_RAW token=secret-token",
            item_name="arcane_energize",
            metadata={"source": "goal", "priority": 1, "action_suggestion": "watch", "token": "secret-token"},
        )
        db.record_opportunity_outcome(
            "op-1",
            "arcane_energize",
            "arcane_flip",
            strategy="arcane_r0_to_r5",
            status="completed",
            expected_profit=40,
            actual_profit=45,
            user_feedback="good",
            metadata={
                "safe_summary": {"profit": 45, "roi_pct": 42.9, "plan_signature": "sig-safe"},
                "profile_url": "https://warframe.market/profile/Seller_RAW",
                "whisper": "/w Seller_RAW hi",
            },
        )
        return db

    def test_memory_vault_snapshot_builds_safe_markdown_index(self):
        from warframe_agent.memory_vault import build_memory_vault_snapshot, memory_vault_snapshot_to_api

        conversations = [
            ConversationEntry(
                user_message="raw user secret-token /w Seller_RAW",
                assistant_reply="raw assistant reply profile_url=https://warframe.market/profile/Seller_RAW",
                tool_calls=[{"tool_name": "query_price", "args_summary": {"item_name": "arcane_energize", "token": "secret-token"}}],
                contexts=["arcane_energize"],
                timestamp="2026-05-28T10:00:00",
                session_id="s1",
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            db = self._build_db(Path(tmp) / "memory.db")
            snapshot = build_memory_vault_snapshot(db=db, conversations=conversations, limit=20)
            api = memory_vault_snapshot_to_api(snapshot)
            db.close()

        self.assertGreaterEqual(api["total"], 6)
        self.assertEqual(api["source_counts"]["market_snapshot"], 1)
        self.assertEqual(api["source_counts"]["opportunity_outcome"], 1)
        self.assertEqual(api["source_counts"]["conversation_log"], 1)
        self.assertIn("# Memory Vault Snapshot", api["markdown_preview"])
        self.assertIn("arcane_energize", api["markdown_preview"])
        self.assertIn("sell_price=45", api["markdown_preview"])
        self.assertIn("actual_profit=45", api["markdown_preview"])
        serialized = json.dumps(api, ensure_ascii=False)
        for forbidden in [
            "secret-token",
            "Seller_RAW",
            "/w",
            "profile_url",
            "warframe.market/profile",
            "token=",
            "whisper",
            "raw user",
            "raw assistant",
            "assistant_reply",
            "user_message",
            "args_summary",
        ]:
            self.assertNotIn(forbidden, serialized)

    def test_memory_vault_limit_applies_to_latest_safe_entries(self):
        from warframe_agent.memory_vault import build_memory_vault_snapshot

        with tempfile.TemporaryDirectory() as tmp:
            db = self._build_db(Path(tmp) / "memory.db")
            snapshot = build_memory_vault_snapshot(db=db, conversations=[], limit=2)
            db.close()

        self.assertEqual(snapshot.total, 2)
        self.assertEqual(len(snapshot.entries), 2)
        self.assertLessEqual(len(snapshot.markdown_preview), 4000)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_memory_vault.py -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: FAIL because `warframe_agent.memory_vault` does not exist yet.

## Task 2: Minimal Vault Module

**Files:**
- Create: `warframe_agent/memory_vault.py`
- Test: `tests/test_memory_vault.py`

- [x] **Step 1: Implement minimal safe snapshot builder**

Create `warframe_agent/memory_vault.py` with:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from .conversation_log import ConversationEntry
from .trading_memory import TradingMemoryDB


@dataclass(frozen=True)
class MemoryVaultEntry:
    source: str
    record_id: str
    timestamp: str
    item_name: str
    title: str
    summary: dict[str, Any]
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MemoryVaultSnapshot:
    generated_at: str
    entries: tuple[MemoryVaultEntry, ...]
    source_counts: dict[str, int]
    markdown_preview: str

    @property
    def total(self) -> int:
        return len(self.entries)
```

Then add:

```python
def build_memory_vault_snapshot(
    *,
    db: TradingMemoryDB | None,
    conversations: Iterable[ConversationEntry] | None = None,
    limit: int = 50,
) -> MemoryVaultSnapshot:
    entries: list[MemoryVaultEntry] = []
    safe_limit = max(0, min(int(limit or 0), 200))
    if db is not None:
        entries.extend(_entries_from_db(db, per_source_limit=max(safe_limit, 1)))
    entries.extend(_entries_from_conversations(conversations or []))
    entries.sort(key=lambda entry: (entry.timestamp, entry.source, entry.record_id), reverse=True)
    entries = entries[:safe_limit]
    source_counts = _source_counts(entries)
    markdown_preview = format_memory_vault_markdown(entries, source_counts)
    return MemoryVaultSnapshot(
        generated_at=datetime.now(timezone.utc).isoformat(),
        entries=tuple(entries),
        source_counts=source_counts,
        markdown_preview=markdown_preview,
    )
```

Use explicit allowlists and text sanitizers. The implementation must include only safe fields and redact or drop sensitive strings.

- [x] **Step 2: Run green unit test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_memory_vault.py -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: PASS.

## Task 3: API Red/Green

**Files:**
- Modify: `tests/test_web_api.py`
- Modify: `warframe_agent/web/app.py`

- [x] **Step 1: Add failing API test**

Add a test near `test_memory_recall_api_returns_safe_trace`:

```python
    @patch("warframe_agent.web.app.load_conversations")
    @patch("warframe_agent.web.app.TradingMemoryDB.open_readonly_if_exists")
    def test_memory_vault_api_returns_safe_preview(self, mock_open, mock_load_conversations):
        from warframe_agent.conversation_log import ConversationEntry

        db_path = Path(tempfile.gettempdir()) / "web_memory_vault_test.db"
        db = TradingMemoryDB(db_path=db_path)
        try:
            db.record_market_snapshot(
                "arcane_energize",
                "price_monitor.scan",
                {"item_id": "arcane_energize", "sell_price": 45, "buy_price": 38, "token": "secret-token", "seller": "Seller_RAW", "whisper": "/w Seller_RAW hi"},
            )
            mock_open.return_value = db
            mock_load_conversations.return_value = [
                ConversationEntry(
                    user_message="raw user secret-token",
                    assistant_reply="raw assistant /w Seller_RAW",
                    tool_calls=[{"tool_name": "query_price", "args_summary": {"token": "secret-token"}}],
                    contexts=["arcane_energize"],
                    timestamp="2026-05-28T10:00:00",
                )
            ]

            response = self.client.get("/api/memory/vault?limit=10")
        finally:
            db.close()
            try:
                db_path.unlink()
            except OSError:
                pass

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["total"], 2)
        self.assertIn("source_counts", data)
        self.assertIn("markdown_preview", data)
        self.assertIn("arcane_energize", data["markdown_preview"])
        serialized = str(data)
        for forbidden in ["secret-token", "Seller_RAW", "/w", "token=", "whisper", "raw user", "raw assistant", "args_summary"]:
            self.assertNotIn(forbidden, serialized)
```

- [x] **Step 2: Run API red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "memory_vault" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: FAIL because `/api/memory/vault` does not exist yet.

- [x] **Step 3: Add read-only endpoint**

Modify `warframe_agent/web/app.py`:

```python
from warframe_agent.conversation_log import load_conversations
from warframe_agent.memory_vault import build_memory_vault_snapshot, memory_vault_snapshot_to_api
```

Add helper near `_query_memory_recall`:

```python
def _query_memory_vault(limit: int = 50) -> dict[str, Any]:
    db = TradingMemoryDB.open_readonly_if_exists()
    try:
        conversations = load_conversations(limit=limit)
        snapshot = build_memory_vault_snapshot(db=db, conversations=conversations, limit=limit)
        return memory_vault_snapshot_to_api(snapshot)
    finally:
        if db is not None:
            db.close()
```

Add endpoint near `/api/memory/recall`:

```python
@app.get("/api/memory/vault")
async def get_memory_vault(limit: int = Query(50, ge=1, le=200)) -> JSONResponse:
    result = await asyncio.to_thread(_query_memory_vault, limit)
    return JSONResponse(result)
```

- [x] **Step 4: Run API green test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "memory_vault" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: PASS. If sandbox blocks Web app import or SQLite WAL access, rerun with an approved writable runtime.

## Task 4: Docs and Cross-Session Ledger

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step37_memory_vault_index_zh.md`
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Modify: `AGENTS.md`

- [x] **Step 1: Write Step 37 migration summary**

The summary must include:

```markdown
# Step 37 可检查 Memory Vault 索引

## 借鉴来源

- OpenHuman：可持续累积、可检查的个人记忆。
- CowAgent：把对话和任务结果沉淀成后续 Agent 可复用的知识材料。

## 本项目落点

- 新增只读 `memory_vault` 聚合层。
- 新增 `GET /api/memory/vault`。
- 只聚合安全摘要和结构化 allowlist 字段。

## 不做的事

- 不引入向量库。
- 不调用云端模型。
- 不导出原始聊天全文。
- 不暴露玩家名、私聊、profile URL、token 或工具原始参数。

## 验证

- `tests/test_memory_vault.py`
- `tests/test_web_api.py -k "memory_vault"`
```

- [x] **Step 2: Update rebuilt docs and AGENTS.md**

Record:

- progress `100%`
- status `已完成`
- reason: Step 37 implements inspectable memory vault index
- impact: `warframe_agent/memory_vault.py`, `warframe_agent/web/app.py`, memory docs, API docs
- next queue: Browser / GUI Agent safety boundary, voice/companion experience evaluation, or controlled blocked-plan confirmation chain

## Task 5: Final Verification

**Files:**
- All files touched in Tasks 1-4

- [x] **Step 1: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_memory_vault.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_memory_recall.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "memory_vault or memory_recall_api_returns_safe_trace" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: all selected tests PASS.

- [x] **Step 2: Run static checks**

Run:

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/memory_vault.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent/memory_vault.py warframe_agent/web/app.py tests/test_memory_vault.py tests/test_web_api.py githubProduct/personal_agent_warframe_migration_step37_memory_vault_index_zh.md githubProduct/personal_agent_learning_route_ledger_zh.md md/rebuilt/05-data-memory.md md/rebuilt/09-personal-agent-foundation.md md/rebuilt/10-learning-route-audit.md AGENTS.md docs/superpowers/plans/2026-05-28-memory-vault-index.md
```

Expected: `AST OK`, no whitespace errors. Git may warn about LF-to-CRLF conversion; that warning is acceptable if exit code is 0.

## Execution Note

The user already asked to continue execution and does not want GitHub sync or commits for this phase. Execute inline after saving this plan, and record results in the docs above.
