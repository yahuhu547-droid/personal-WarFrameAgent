# Opportunity Review Recording Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe chat command that records a real pushed opportunity (`OPxxxxxx`) into SQLite `opportunity_outcomes`, so personal profile feedback has durable data to learn from.

**Architecture:** Keep the write path in `ChatAgent`, because it already owns `/review`, `TradingMemoryDB`, and `OpportunityLookupStore` injection. The command reads a short-lived OP snapshot from `OpportunityLookupStore`, extracts only safe trade-plan summary fields, then calls `TradingMemoryDB.record_opportunity_outcome`; scanners remain DB-free and profile construction continues to receive explicit injected outcomes.

**Tech Stack:** Python, pytest, existing `warframe_agent.chat`, `warframe_agent.opportunity_lookup`, `warframe_agent.trading_memory`, `tests/test_chat_memory_commands.py`.

---

## File Structure

- Modify: `warframe_agent/chat.py`
  - Extend `/review` handling with a recording subcommand.
  - Add small helpers for parsing status/profit/feedback and safe metadata extraction.
  - Keep existing `/review [status]` listing behavior unchanged.
- Modify: `tests/test_chat_memory_commands.py`
  - Add regression tests for successful OP outcome recording.
  - Add regression tests for bad OP ID, missing lookup detail, missing DB, and invalid profit.
- Create: `githubProduct/personal_agent_warframe_migration_step11_opportunity_review_recording_zh.md`
  - Capture the learning note for this migration step.
- Modify: `md/rebuilt/03-user-interfaces.md`
  - Document the new chat command.
- Modify: `md/rebuilt/05-data-memory.md`
  - Document the new data path from `OpportunityLookupStore` to `opportunity_outcomes`.
- Modify: `md/rebuilt/07-operations-testing.md`
  - Add focused verification commands.
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - Record the Step 11 learning outcome.

---

### Task 1: Red Tests For Recording Real OP Outcomes

**Files:**
- Modify: `tests/test_chat_memory_commands.py`

- [ ] **Step 1: Add imports and helpers**

Add imports:

```python
from datetime import datetime, timezone

from warframe_agent.opportunity_lookup import OpportunityLookupStore
```

Add a helper plan inside the test file:

```python
def _reviewable_trade_plan():
    return {
        "source": "arcane_flip",
        "strategy": "arcane_r0_to_r5",
        "display_name": "Arcane Energize",
        "item_id": "arcane_energize",
        "required_quantity": 21,
        "total_cost": 179,
        "total_revenue": 210,
        "profit": 31,
        "roi_pct": 17.3,
        "risk_level": "medium",
        "profit_bucket": "small",
        "plan_signature": "sig-safe",
        "safe_summary": {
            "source": "arcane_flip",
            "strategy": "arcane_r0_to_r5",
            "item_id": "arcane_energize",
            "required_quantity": 21,
            "total_cost": 179,
            "total_revenue": 210,
            "profit": 31,
            "roi_pct": 17.3,
            "risk_level": "medium",
            "profit_bucket": "small",
            "plan_signature": "sig-safe",
        },
        "buy_steps": [
            {
                "player": "UnsafeSeller",
                "profile_url": "https://warframe.market/profile/UnsafeSeller",
                "whisper": "/w UnsafeSeller hi",
                "unit_price": 9,
                "quantity": 21,
            }
        ],
        "sell_steps": [],
    }
```

- [ ] **Step 2: Add the success test**

Add:

```python
    def test_review_done_command_records_real_opportunity_outcome_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())
            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )

            try:
                reply = agent.answer(f"/review done {opportunity_id} 45 good")
                records = db.get_opportunity_outcomes(status="completed", item_name="arcane_energize", limit=10)
            finally:
                db.close()

        self.assertIn("已记录机会复盘", reply)
        self.assertIn(opportunity_id, reply)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.opportunity_id, opportunity_id)
        self.assertEqual(record.item_name, "arcane_energize")
        self.assertEqual(record.source, "arcane_flip")
        self.assertEqual(record.strategy, "arcane_r0_to_r5")
        self.assertEqual(record.status, "completed")
        self.assertEqual(record.expected_profit, 31)
        self.assertEqual(record.actual_profit, 45)
        self.assertEqual(record.user_feedback, "good")
        serialized = str(record.metadata)
        self.assertIn("safe_summary", serialized)
        self.assertNotIn("UnsafeSeller", serialized)
        self.assertNotIn("profile", serialized.lower())
        self.assertNotIn("/w ", serialized)
```

- [ ] **Step 3: Add validation tests**

Add:

```python
    def test_review_done_command_rejects_missing_db_missing_lookup_and_bad_profit(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())

            no_db_agent = ChatAgent(
                memory=AgentMemory.default(),
                memory_path=Path(tmp) / "memory.json",
                opportunity_lookup_store=lookup,
            )
            self.assertIn("暂无机会复盘数据", no_db_agent.answer(f"/review done {opportunity_id} 45 good"))

            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )
            try:
                self.assertIn("实际利润必须是整数", agent.answer(f"/review done {opportunity_id} nope good"))
                self.assertIn("机会 ID 格式不正确", agent.answer("/review done abc 45 good"))
                self.assertIn("不存在或已过期", agent.answer("/review done OPZZZZZZ 45 good"))
                self.assertEqual(db.get_opportunity_outcomes(limit=10), [])
            finally:
                db.close()
```

- [ ] **Step 4: Run the focused tests and confirm red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "review_done_command" -q
```

Expected before implementation: failures because `/review done ...` is still treated as status filtering.

---

### Task 2: Implement `/review done` Recording

**Files:**
- Modify: `warframe_agent/chat.py`

- [ ] **Step 1: Add subcommand dispatch**

Change `_handle_review_command` so it routes record-style subcommands first:

```python
    def _handle_review_command(self, args: list[str]) -> str:
        if args and args[0].strip().lower() in {"done", "complete", "completed", "完成", "记录"}:
            return self._handle_review_record_command(args[1:])
        if not self.trading_memory_db:
            return "暂无机会复盘数据。"
        status = args[0].strip().lower() if args else None
        records = self.trading_memory_db.get_opportunity_outcomes(status=status, limit=10)
```

- [ ] **Step 2: Add the record command helper**

Add below `_handle_review_command`:

```python
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
        feedback = args[2].strip().lower() if len(args) >= 3 else self._default_feedback_for_profit(actual_profit)
        detail = self.opportunity_lookup_store.get(lookup_id)
        if detail is None:
            return opportunity_not_found_message(lookup_id)
        plan = detail.content if isinstance(detail.content, dict) else {}
        safe_summary = self._opportunity_review_safe_summary(detail)
        source = str(safe_summary.get("source") or plan.get("source") or "unknown")
        strategy = str(safe_summary.get("strategy") or plan.get("strategy") or source)
        expected_profit = self._safe_int(safe_summary.get("profit", plan.get("profit", 0)))
        self.trading_memory_db.record_opportunity_outcome(
            lookup_id,
            str(safe_summary.get("item_id") or detail.item_id or plan.get("item_id") or ""),
            source,
            strategy,
            "completed",
            expected_profit,
            actual_profit,
            feedback,
            {"safe_summary": safe_summary},
        )
        return (
            f"已记录机会复盘：{lookup_id} {safe_summary.get('item_id') or detail.item_id}，"
            f"预期 {expected_profit}p，实际 {actual_profit}p，反馈 {feedback}。"
        )
```

- [ ] **Step 3: Add safe extraction helpers**

Add below the record helper:

```python
    @staticmethod
    def _default_feedback_for_profit(actual_profit: int) -> str:
        if actual_profit > 0:
            return "good"
        if actual_profit < 0:
            return "bad"
        return "neutral"

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
            if value is None:
                continue
            summary[key] = value
        if "item_id" not in summary and detail.item_id:
            summary["item_id"] = detail.item_id
        return summary
```

- [ ] **Step 4: Update help text**

Change `/review [status]` help to include:

```python
            "/review [status]   查看机会复盘记录",
            "/review done OPID 实际利润 [good|bad|neutral|ignored]  记录机会复盘",
```

- [ ] **Step 5: Run focused tests and confirm green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "review_done_command or review_command_lists_safe_opportunity_outcomes or sqlite_outcomes" -q
```

Expected: all selected tests pass.

---

### Task 3: Documentation Sync

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step11_opportunity_review_recording_zh.md`
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [ ] **Step 1: Add migration note**

Create a concise Chinese note describing:

```markdown
# Step 11: 真实 OP 机会复盘记录入口

- 新增 `/review done OPxxxxxx 实际利润 [good|bad|neutral|ignored]`。
- 数据来源必须是 `OpportunityLookupStore` 中未过期的真实 OP 机会。
- 写入 `TradingMemoryDB.opportunity_outcomes` 时只保存 `safe_summary`，不保存玩家名、profile 链接、`/w` 或 raw orders。
- 这一步让 Step 10 的 SQLite 复盘画像注入有真实长期数据来源。
```

- [ ] **Step 2: Update rebuilt docs**

Add short entries:

```markdown
`/review done OP8K3A2Q 45 good` 会把推送机会记录为 completed 复盘，实际利润为 45p，反馈为 good。
```

Add data-flow note:

```markdown
聊天层会先用 `OpportunityLookupStore.get(OPID)` 校验机会仍存在，再提取 `trade_plan.safe_summary` 写入 `opportunity_outcomes`。
```

- [ ] **Step 3: Add verification commands**

Add:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "review_done_command or review_command_lists_safe_opportunity_outcomes or sqlite_outcomes" -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(path.read_text(encoding='utf-8')) for path in map(pathlib.Path, ['warframe_agent/chat.py','tests/test_chat_memory_commands.py'])]; print('AST ok')"
```

---

### Task 4: Verification And Review

**Files:**
- Inspect: `warframe_agent/chat.py`
- Inspect: `tests/test_chat_memory_commands.py`
- Inspect: `md/rebuilt/*.md`
- Inspect: `githubProduct/personal_agent_warframe_migration_step11_opportunity_review_recording_zh.md`

- [ ] **Step 1: Run focused verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "review_done_command or review_command_lists_safe_opportunity_outcomes or sqlite_outcomes" -q
.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py tests/test_personal_scoring.py -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(path.read_text(encoding='utf-8')) for path in map(pathlib.Path, ['warframe_agent/chat.py','tests/test_chat_memory_commands.py'])]; print('AST ok')"
```

- [ ] **Step 2: Run subagent review**

Dispatch a read-only reviewer to check:

```text
Review Step 11 for spec compliance and safety:
- `/review done` records only real non-expired OP IDs.
- metadata remains safe and does not include players/profile/whisper/raw orders.
- existing `/review [status]` listing still works.
- scanners still do not read SQLite directly.
- docs mention Web API tests were not claimed unless run.
```

- [ ] **Step 3: Final sync note**

Report:

- Plan path.
- Files changed.
- Verification commands and observed results.
- Any skipped Web API tests and why.

## Self-review

- Spec coverage: command, safe write path, listing compatibility, docs, verification all have tasks.
- Placeholder scan: no placeholder steps remain.
- Type consistency: command uses existing `OpportunityLookupStore`, `TradingMemoryDB.record_opportunity_outcome`, and `OpportunityOutcomeMemory` paths.
- User constraint: no GitHub submission or commit; update `md/rebuilt` after implementation.
