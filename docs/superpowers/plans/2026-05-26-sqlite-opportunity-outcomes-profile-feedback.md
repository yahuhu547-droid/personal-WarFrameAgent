# SQLite Opportunity Outcomes Profile Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explicitly inject SQLite `opportunity_outcomes` into personal profile aggregation so real reviewed OP outcomes can influence future personal scoring without scanners directly reading the database.

**Architecture:** `personal_profile.py` remains the pure aggregation layer and accepts optional outcome records. `ChatAgent` reads from its injected `trading_memory_db` and passes records into `build_personal_profile(...)`; Web profile/scan endpoints use a read-only helper around `TradingMemoryDB.open_readonly_if_exists()`. Scanners continue receiving only `PersonalTradingProfile`.

**Tech Stack:** Python dataclasses, SQLite-backed `TradingMemoryDB`, existing `OpportunityOutcomeMemory`, pytest, Markdown docs under `md/rebuilt`.

---

## File Structure

- Modify `warframe_agent/personal_profile.py`
  - Add optional `opportunity_outcomes` parameter to `build_personal_profile(...)`.
  - Aggregate both `AgentMemory.trade_outcomes` and injected `OpportunityOutcomeMemory` records.
  - Use only safe aggregate fields: source, strategy, category, count, wins/losses, avg actual profit, good rate.
- Modify `warframe_agent/chat.py`
  - Add a small safe helper that reads recent `opportunity_outcomes` from injected `trading_memory_db`.
  - Use that helper for `/profile` and scan tools that already build a personal profile.
- Modify `warframe_agent/web/app.py`
  - Add a read-only helper for profile outcome records.
  - Use it for `/api/profile`, `/api/profile/preferences`, and Web scan endpoints that build personal profiles.
- Modify `tests/test_personal_profile.py`
  - Add direct aggregation tests for `OpportunityOutcomeMemory`.
- Modify `tests/test_chat_memory_commands.py`
  - Add ChatAgent test confirming injected SQLite outcomes affect scan profile without scanners reading DB.
- Create `githubProduct/personal_agent_warframe_migration_step10_sqlite_outcome_feedback_zh.md`
  - Record what was migrated and what stayed deliberately out of scope.
- Modify `md/rebuilt/04-web-api-reference.md`, `05-data-memory.md`, `07-operations-testing.md`, `09-personal-agent-foundation.md`
  - Sync behavior and verification commands.

## Task 1: Red Tests

**Files:**
- Modify: `tests/test_personal_profile.py`
- Modify: `tests/test_chat_memory_commands.py`

- [ ] **Step 1: Add direct profile test for SQLite outcome records**

Add a test that imports `OpportunityOutcomeMemory`, passes three records into `build_personal_profile(memory, opportunity_outcomes=records)`, and asserts:

```python
assert profile.completed_outcome_count == 3
assert profile.total_actual_profit == 120
assert profile.win_rate == 1.0
assert profile.outcome_feedback[0].source == "mod_flipper"
assert profile.outcome_feedback[0].strategy == "arcane_rank0_to_max"
assert profile.outcome_feedback[0].category == "arcane"
```

Also assert serialized `profile_safe_summary(profile)` does not contain `OP`, `profile_url`, `/w`, `token`, or player names.

- [ ] **Step 2: Add ChatAgent injected DB test**

Create a temporary `TradingMemoryDB`, record three completed `mod_flipper` outcomes, inject it into `ChatAgent`, patch `warframe_agent.mod_flipper.scan_all_mod_flips`, call `_tool_mod_flipper({"limit": 1})`, and assert the scanner received a `personal_profile` with `outcome_feedback[0].count == 3`.

- [ ] **Step 3: Run red tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py -k "sqlite_opportunity_outcomes" -q
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "sqlite_outcomes" -q
```

Expected: fail because `build_personal_profile(...)` does not yet accept `opportunity_outcomes`, and ChatAgent does not inject them.

## Task 2: Core Aggregation

**Files:**
- Modify: `warframe_agent/personal_profile.py`

- [ ] **Step 1: Extend function signature**

Change:

```python
def build_personal_profile(memory: AgentMemory) -> PersonalTradingProfile:
```

to:

```python
def build_personal_profile(memory: AgentMemory, opportunity_outcomes=None) -> PersonalTradingProfile:
```

- [ ] **Step 2: Add generic outcome access helpers**

Add helpers for item/source/strategy/status that support both `TradeOutcome` and `OpportunityOutcomeMemory`, always falling back to safe identifiers or `unknown`.

- [ ] **Step 3: Aggregate combined outcomes**

Use:

```python
combined_outcomes = [*memory.trade_outcomes, *(opportunity_outcomes or [])]
```

for profile counts, win rate, derived categories, and `_derive_outcome_feedback(...)`.

- [ ] **Step 4: Run profile tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py -q
```

Expected: pass.

## Task 3: Chat Injection

**Files:**
- Modify: `warframe_agent/chat.py`

- [ ] **Step 1: Add helper**

Add a private method:

```python
def _profile_opportunity_outcomes(self, limit: int = 100) -> list:
    if not self.trading_memory_db:
        return []
    try:
        return self.trading_memory_db.get_opportunity_outcomes(limit=limit)
    except Exception as exc:
        logger.debug("机会复盘画像读取失败: %s", exc)
        return []
```

- [ ] **Step 2: Add profile builder method**

Add:

```python
def _build_personal_profile(self):
    from .personal_profile import build_personal_profile
    return build_personal_profile(self.memory, opportunity_outcomes=self._profile_opportunity_outcomes())
```

- [ ] **Step 3: Replace local profile builds**

Use `self._build_personal_profile()` in `/profile`, `_tool_mod_flipper`, `_tool_set_profit`, and `_tool_investment_advisor`.

- [ ] **Step 4: Run chat tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "profile_command or scan_tools_pass_personal_profile or sqlite_outcomes" -q
```

Expected: pass.

## Task 4: Web Read-Only Injection

**Files:**
- Modify: `warframe_agent/web/app.py`

- [ ] **Step 1: Add read-only helper**

Add:

```python
def _load_profile_opportunity_outcomes(limit: int = 100) -> list:
    db = TradingMemoryDB.open_readonly_if_exists()
    if db is None:
        return []
    try:
        return db.get_opportunity_outcomes(limit=limit)
    except Exception as exc:
        logger.debug("读取个人画像机会复盘失败: %s", exc)
        return []
    finally:
        db.close()
```

- [ ] **Step 2: Update `_profile_response`**

Accept optional records:

```python
def _profile_response(memory: AgentMemory, opportunity_outcomes=None) -> dict[str, Any]:
    return {"profile": profile_safe_summary(build_personal_profile(memory, opportunity_outcomes=opportunity_outcomes))}
```

- [ ] **Step 3: Inject into endpoints**

Use `await asyncio.to_thread(_load_profile_opportunity_outcomes)` in `/api/profile`, `/api/profile/preferences`, and scan endpoints before calling `build_personal_profile(...)`.

- [ ] **Step 4: Syntax check**

Run AST parse for `warframe_agent/web/app.py`.

## Task 5: Docs and Verification

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step10_sqlite_outcome_feedback_zh.md`
- Modify: `md/rebuilt/04-web-api-reference.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [ ] **Step 1: Document behavior**

State that SQLite outcomes are now explicitly injected into profile building by Chat/Web layers, while scanners remain DB-free.

- [ ] **Step 2: Run focused verification**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py tests/test_personal_scoring.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "profile_command or scan_tools_pass_personal_profile or sqlite_outcomes" -q
.\.venv\Scripts\python.exe -m pytest tests/test_mod_flipper.py -k "personal_score" -q
.\.venv\Scripts\python.exe -m pytest tests/test_set_profit.py -k "personal_score" -q
.\.venv\Scripts\python.exe -m pytest tests/test_investment.py -k "personal_score" -q
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/personal_profile.py','warframe_agent/chat.py','warframe_agent/web/app.py','tests/test_personal_profile.py','tests/test_chat_memory_commands.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

Web API pytest may still require a writable data directory because importing `warframe_agent.web.app` creates SQLite-backed globals.

- [ ] **Step 3: Subagent review**

Ask a read-only subagent to confirm DB-free scanner boundary, safe summary boundary, test coverage, and docs accuracy.
