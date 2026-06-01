# Scout Push Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe Scout-style quality summary for proactive opportunity pushes, so the agent can learn whether pushed opportunities are later reviewed, completed, rejected, or profitable without storing raw player/order details.

**Architecture:** Reuse existing `push_history` and `opportunity_outcomes` tables; do not add schema or install packages. Add a deterministic aggregation method on `TradingMemoryDB` that groups opportunity pushes and outcomes by safe `(item_name, source, strategy, category)` signals, returning only counts, rates, and profit aggregates. Keep user-visible push cards unchanged.

**Tech Stack:** Python dataclasses, SQLite-backed `TradingMemoryDB`, pytest, existing proactive push tests.

---

## File Map

- Modify: `warframe_agent/trading_memory.py`
  - Add `PushQualitySignal` dataclass.
  - Add `TradingMemoryDB.summarize_push_quality(...)`.
  - Add safe helper functions for opportunity source, strategy, category, good/bad classification, and rates.
- Modify: `warframe_agent/web/app.py`
  - Add a safe serializer and read-only `GET /api/trading-memory/push-quality` endpoint.
- Modify: `tests/test_trading_memory.py`
  - Add red tests for safe aggregation and filtering.
- Modify: `tests/test_proactive_push.py`
  - Add a regression test proving recorded proactive push metadata contains enough safe quality keys for aggregation.
- Modify: `tests/test_web_api.py`
  - Add an API regression test proving the endpoint returns only safe aggregate fields.
- Create: `githubProduct/personal_agent_warframe_migration_step17_scout_push_quality_zh.md`
  - Record what was learned and verified.
- Modify: `md/rebuilt/04-web-api-reference.md`
  - Document the new push quality endpoint.
- Modify: `md/rebuilt/05-data-memory.md`
  - Document push quality summaries.
- Modify: `md/rebuilt/07-operations-testing.md`
  - Add verification commands.
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - Mark Step 17 as completed.

## Task 1: Safe Push Quality Aggregation

**Files:**
- Test: `tests/test_trading_memory.py`
- Modify: `warframe_agent/trading_memory.py`

- [x] **Step 1: Write the failing aggregation test**

Add:

```python
def test_push_quality_summary_aggregates_safe_pushes_and_outcomes(self):
    with tempfile.TemporaryDirectory() as tmp:
        db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
        db.record_push(
            "opportunity",
            "交易机会 arcane_energize",
            item_name="arcane_energize",
            metadata={
                "opportunity_source": "mod_flipper",
                "strategy": "arcane_rank0_to_max",
                "profit": 40,
                "roi_pct": 30,
                "profile_url": "https://warframe.market/profile/SecretSeller",
                "whisper": "/w SecretSeller hi",
            },
        )
        db.record_push(
            "opportunity",
            "交易机会 arcane_energize again",
            item_name="arcane_energize",
            metadata={"opportunity_source": "mod_flipper", "strategy": "arcane_rank0_to_max", "profit": 30},
        )
        db.record_opportunity_outcome(
            "OPGOOD1",
            "arcane_energize",
            "mod_flipper",
            "arcane_rank0_to_max",
            "completed",
            40,
            50,
            "good",
            {"safe_summary": {"roi_pct": 30, "profile_url": "https://warframe.market/profile/SecretSeller"}},
        )
        db.record_opportunity_outcome(
            "OPBAD1",
            "arcane_energize",
            "mod_flipper",
            "arcane_rank0_to_max",
            "rejected",
            40,
            0,
            "bad",
            {"safe_summary": {"roi_pct": 30, "whisper": "/w SecretSeller hi"}},
        )

        summaries = db.summarize_push_quality(limit=20)
        db.close()

    self.assertEqual(len(summaries), 1)
    signal = summaries[0]
    self.assertEqual(signal.item_name, "arcane_energize")
    self.assertEqual(signal.source, "mod_flipper")
    self.assertEqual(signal.strategy, "arcane_rank0_to_max")
    self.assertEqual(signal.category, "arcane")
    self.assertEqual(signal.sent_count, 2)
    self.assertEqual(signal.reviewed_count, 2)
    self.assertEqual(signal.completed_count, 1)
    self.assertEqual(signal.rejected_count, 1)
    self.assertEqual(signal.good_count, 1)
    self.assertEqual(signal.bad_count, 1)
    self.assertEqual(signal.avg_expected_profit, 40.0)
    self.assertEqual(signal.avg_actual_profit, 25.0)
    self.assertEqual(signal.good_rate, 0.5)
    self.assertEqual(signal.false_positive_rate, 0.5)
    serialized = str(signal)
    for forbidden in ["SecretSeller", "profile", "/w", "whisper"]:
        self.assertNotIn(forbidden, serialized)
```

- [x] **Step 2: Run red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trading_memory.py::TradingMemoryDBTests::test_push_quality_summary_aggregates_safe_pushes_and_outcomes -q
```

Expected: FAIL because `summarize_push_quality` does not exist.

- [x] **Step 3: Implement minimal aggregation**

In `warframe_agent/trading_memory.py`:

- Add `PushQualitySignal`.
- Implement `TradingMemoryDB.summarize_push_quality(push_type="opportunity", item_name=None, source=None, limit=100, since=None)`.
- Group pushes and outcomes by `(item_name, source, strategy, category)`.
- Count pushes as `sent_count`.
- Count outcomes as `reviewed_count`.
- Treat `completed` and `accepted` as completion-like.
- Treat `rejected`, `failed`, `expired`, `skipped`, `bad`, `ignored`, negative profit, or zero-profit rejected outcomes as bad/false-positive signals.
- Return only safe identifiers, counts, rates, and profit averages.

- [x] **Step 4: Run green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trading_memory.py::TradingMemoryDBTests::test_push_quality_summary_aggregates_safe_pushes_and_outcomes -q
```

Expected: PASS.

## Task 2: Filtering And Proactive Push Metadata Regression

**Files:**
- Test: `tests/test_trading_memory.py`
- Test: `tests/test_proactive_push.py`
- Modify: `warframe_agent/trading_memory.py` if needed.

- [x] **Step 1: Add filtering test**

Add a test proving `summarize_push_quality(source="set_profit")` and `item_name="rhino_prime_set"` return only the requested safe bucket.

- [x] **Step 2: Add proactive push metadata test**

Extend the existing proactive push memory regression by asserting stored metadata contains `opportunity_source`, `strategy`, `profit`, `roi_pct`, and `profit_bucket`, which are enough for Scout quality grouping.

- [x] **Step 3: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trading_memory.py -k "push_quality" -q
.\.venv\Scripts\python.exe -m pytest tests/test_proactive_push.py -k "records_to_injected_trading_memory_db or sanitizes_trade_plan_before_recording" -q --basetemp .pytest_tmp_step17_push
```

Expected: PASS.

## Task 3: Web API, Docs And Verification

**Files:**
- Modify: `warframe_agent/web/app.py`
- Test: `tests/test_web_api.py`
- Create: `githubProduct/personal_agent_warframe_migration_step17_scout_push_quality_zh.md`
- Modify: `md/rebuilt/04-web-api-reference.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: Add Web API red test**

Add `test_push_quality_endpoint_returns_safe_aggregates`, then run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k push_quality -q
```

Expected: FAIL with `404 != 200` because the endpoint is missing.

- [x] **Step 2: Implement Web API**

Add `_serialize_push_quality_signal(...)` and `GET /api/trading-memory/push-quality`, backed by `TradingMemoryDB.summarize_push_quality(...)`. The response must include only aggregate counters, rates, and safe identifiers.

- [x] **Step 3: Run Web API green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k push_quality -q
```

Expected: PASS.

- [x] **Step 4: Update docs**

Document that Scout push quality is a safe aggregate over `push_history` and `opportunity_outcomes`, not a raw order log.

- [x] **Step 5: Run verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trading_memory.py -k "push_quality or push_history or opportunity_outcomes" -q
.\.venv\Scripts\python.exe -m pytest tests/test_proactive_push.py -k "records_to_injected_trading_memory_db or sanitizes_trade_plan_before_recording" -q --basetemp .pytest_tmp_step17_push_final
.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k push_quality -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/trading_memory.py','warframe_agent/web/app.py','tests/test_trading_memory.py','tests/test_proactive_push.py','tests/test_web_api.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\trading_memory.py warframe_agent\web\app.py tests\test_trading_memory.py tests\test_proactive_push.py tests\test_web_api.py docs\superpowers\plans\2026-05-26-scout-push-quality.md githubProduct\personal_agent_warframe_migration_step17_scout_push_quality_zh.md md\rebuilt\04-web-api-reference.md md\rebuilt\05-data-memory.md md\rebuilt\07-operations-testing.md md\rebuilt\09-personal-agent-foundation.md
```

Expected: tests pass, AST OK, and `git diff --check` has no errors apart from possible CRLF warnings.

## Result

Completed on 2026-05-26. Final focused verification:

- `tests/test_trading_memory.py -k "push_quality or push_history or opportunity_outcomes"`: 6 passed.
- `tests/test_proactive_push.py -k "records_to_injected_trading_memory_db or sanitizes_trade_plan_before_recording"`: 3 passed.
- `tests/test_web_api.py -k push_quality`: 1 passed.
- Python AST parse: OK.
- `git diff --check`: no whitespace errors; only CRLF conversion warnings.
