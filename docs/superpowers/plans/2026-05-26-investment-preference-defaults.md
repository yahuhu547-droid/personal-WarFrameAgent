# Investment Preference Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the investment advisor use the user's personal budget and minimum ROI preferences when the caller does not explicitly provide those values.

**Architecture:** Add a small pure resolver in `warframe_agent/investment.py` that accepts `AgentMemory` plus optional request values and returns concrete `budget` and `min_roi_pct`. `ChatAgent._tool_investment_advisor(...)` and Web `/api/investment` call this resolver after loading memory, preserving explicit caller values and existing fallback defaults when no preference is configured.

**Tech Stack:** Python dataclasses/memory preferences, existing investment scanner, FastAPI query parameters, pytest, AST syntax checks.

---

## File Structure

- Modify `warframe_agent/investment.py`
  - Add `resolve_investment_preference_defaults(memory, budget, min_roi_pct, fallback_budget, fallback_min_roi_pct)`.
- Modify `warframe_agent/chat.py`
  - Use the resolver in `_tool_investment_advisor(...)`.
- Modify `warframe_agent/web/app.py`
  - Change `/api/investment` optional `budget` and `min_roi_pct` query params to use preferences when omitted.
- Modify `warframe_agent/web/static/js/sidebar.js`
  - Stop the default investment panel refresh from sending hard-coded budget/ROI values; only send budget when the user explicitly scans with one.
- Modify `tests/test_investment.py`
  - Add pure resolver tests for preference defaults, explicit override behavior, and explicit zero preservation.
- Modify `tests/test_chat_memory_commands.py`
  - Assert the investment tool passes preference defaults into `scan_prime_investments` when args omit budget/ROI, treats blank strings as missing, and preserves zero.
- Modify `tests/test_web_api.py`
  - Add/adjust direct endpoint and HTTP query tests proving omitted or blank `budget`/`min_roi_pct` use memory preferences while explicit values still win.
- Create `githubProduct/personal_agent_warframe_migration_step6_investment_preference_defaults_zh.md`
  - Record the learning outcome and verification results.
- Modify `md/rebuilt/*.md`
  - Synchronize the rebuilt docs. Do not commit or push to GitHub.

---

### Task 1: Pure Default Resolver

**Files:**
- Modify: `tests/test_investment.py`
- Modify: `warframe_agent/investment.py`

- [x] **Step 1: Write failing resolver tests**

Add tests:

```python
def test_resolve_investment_preference_defaults_uses_memory_when_missing():
    memory = AgentMemory.default().with_updated_preferences(budget_min=20, budget_max=180, min_roi_pct=35)

    budget, min_roi = resolve_investment_preference_defaults(
        memory,
        budget=None,
        min_roi_pct=None,
        fallback_budget=500,
        fallback_min_roi_pct=10.0,
    )

    assert budget == 180
    assert min_roi == 35.0
```

```python
def test_resolve_investment_preference_defaults_preserves_explicit_values():
    memory = AgentMemory.default().with_updated_preferences(budget_min=20, budget_max=180, min_roi_pct=35)

    budget, min_roi = resolve_investment_preference_defaults(
        memory,
        budget=75,
        min_roi_pct=12.5,
        fallback_budget=500,
        fallback_min_roi_pct=10.0,
    )

    assert budget == 75
    assert min_roi == 12.5
```

- [x] **Step 2: Verify red**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_investment.py -k "resolve_investment_preference_defaults" -q
```

Expected: import/name failure because the resolver does not exist.

- [x] **Step 3: Implement resolver**

Add this function near `format_prime_investment_results_for_model(...)`:

```python
def resolve_investment_preference_defaults(
    memory,
    *,
    budget: int | None,
    min_roi_pct: float | None,
    fallback_budget: int,
    fallback_min_roi_pct: float,
) -> tuple[int, float]:
    preferences = getattr(memory, "preferences", None)
    preference_budget = getattr(preferences, "budget_max", 0) or 0
    preference_roi = getattr(preferences, "min_roi_pct", 0) or 0
    resolved_budget = int(budget if budget is not None else (preference_budget or fallback_budget))
    resolved_min_roi = float(min_roi_pct if min_roi_pct is not None else (preference_roi or fallback_min_roi_pct))
    return max(0, resolved_budget), max(0.0, resolved_min_roi)
```

- [x] **Step 4: Verify green**

Run the same pytest command and expect pass.

---

### Task 2: Chat Investment Tool Defaults

**Files:**
- Modify: `tests/test_chat_memory_commands.py`
- Modify: `warframe_agent/chat.py`

- [x] **Step 1: Write failing chat test**

Add a test near `test_scan_tools_pass_personal_profile_to_scanners`:

```python
def test_investment_tool_uses_preference_defaults_when_args_omit_budget_and_roi(self):
    memory = AgentMemory.default().with_updated_preferences(budget_min=30, budget_max=150, min_roi_pct=25)
    agent = ChatAgent(memory=memory, warframe_items=[{"url_name": "rhino_prime_set"}], order_fetcher=lambda item_id: [])

    with patch("warframe_agent.investment.scan_prime_investments", return_value=[]) as investment_scan:
        agent._tool_investment_advisor({"limit": 1})

    self.assertEqual(investment_scan.call_args.kwargs["budget"], 150)
    self.assertEqual(investment_scan.call_args.kwargs["min_roi_pct"], 25.0)
```

- [x] **Step 2: Verify red**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "investment_tool_uses_preference_defaults" -q
```

Expected: fail because chat still uses `1000/10`.

- [x] **Step 3: Implement chat resolver usage**

In `_tool_investment_advisor(...)`, import the resolver and compute:

```python
requested_budget = int(args["budget"]) if args.get("budget") not in (None, "") else None
requested_min_roi = float(args["min_roi"]) if args.get("min_roi") not in (None, "") else None
budget, min_roi = resolve_investment_preference_defaults(
    self.memory,
    budget=requested_budget,
    min_roi_pct=requested_min_roi,
    fallback_budget=1000,
    fallback_min_roi_pct=10.0,
)
```

Preserve explicit values.

---

### Task 3: Web Investment Endpoint Defaults

**Files:**
- Modify: `tests/test_web_api.py`
- Modify: `warframe_agent/web/app.py`
- Modify: `warframe_agent/web/static/js/sidebar.js`

- [x] **Step 1: Write Web default test**

Add a direct async endpoint test that patches `_load_memory_async`, `_load_items_full`, `scan_prime_investments`, and `scout_investment_candidates`. Call `investment_endpoint(budget=None, min_roi_pct=None, limit=5)` and assert the scanner receives `budget=220`, `min_roi_pct=30.0` from memory.

- [x] **Step 2: Implement optional query defaults**

Change endpoint parameters:

```python
budget: int | None = Query(None, ge=0, le=100000),
min_roi_pct: float | None = Query(None, ge=0, le=10000),
```

After loading memory:

```python
budget, min_roi_pct = resolve_investment_preference_defaults(
    memory,
    budget=budget,
    min_roi_pct=min_roi_pct,
    fallback_budget=500,
    fallback_min_roi_pct=10.0,
)
```

Then keep cache key, scanner, scout, and response logic using the resolved values.

- [x] **Step 3: Update sidebar default request**

Change the default investment advisor refresh to build query params as:

```javascript
const params = new URLSearchParams({ limit: '30' });
if (budget !== null && budget !== undefined && Number.isFinite(Number(budget))) {
    params.set('budget', String(budget));
}
```

Leave `min_roi_pct` omitted so the backend can read `preferences.min_roi_pct`.

- [x] **Step 4: Update sidebar budget summary**

Render the default summary as `偏好预算` instead of a hard-coded `500p`; explicit `0` remains visible as `0p`.

---

### Task 4: Documentation Sync

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step6_investment_preference_defaults_zh.md`
- Modify: `md/rebuilt/02-feature-scope.md`
- Modify: `md/rebuilt/03-user-interfaces.md`
- Modify: `md/rebuilt/04-web-api-reference.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/06-tools-models-safety.md`
- Modify: `md/rebuilt/07-operations-testing.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`

- [x] **Step 1: Write learning note**

Record that Step 6 makes investment defaults consume `preferences.budget_max` and `preferences.min_roi_pct` only when the caller omits explicit values.

- [x] **Step 2: Update rebuilt docs**

Mention that `/pref budget ...` and `/pref min_roi ...` now affect default investment scans in chat and Web.

---

### Task 5: Verification

**Files:**
- No production edits.

- [x] **Step 1: Run targeted tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_investment.py -k "resolve_investment_preference_defaults" -q
& .\.venv\Scripts\python.exe -m pytest tests\test_chat_memory_commands.py -k "investment_tool_uses_preference_defaults or investment_tool_treats_blank_args or scan_tools_pass_personal_profile" -q
& .\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "investment_api_uses_preference_defaults or investment_api_http_query_omitted_and_empty_use_preference_defaults or investment_api_http_query_preserves_explicit_zero" -q
```

- [x] **Step 2: Run available syntax checks**

```powershell
& .\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/investment.py','warframe_agent/chat.py','warframe_agent/web/app.py','tests/test_investment.py','tests/test_chat_memory_commands.py','tests/test_web_api.py']; [ast.parse(pathlib.Path(f).read_text(encoding='utf-8-sig'), filename=f) for f in files]; print('AST OK')"
```

- [x] **Step 3: Record known Web test limit**

If Web API tests still fail during `warframe_agent.web.app` import because of SQLite WAL, record the exact limitation in the learning note and final response.

Observed in this workspace:

```text
pytest tests/test_web_api.py -k "investment_api_uses_preference_defaults" -q
ERROR tests/test_web_api.py - sqlite3.OperationalError: unable to open database file
```

The failure occurs during `warframe_agent.web.app` import at `PriceHistoryDB()` before the endpoint test can run.

The same Web API target passed when run in the sandbox-external writable environment:

```text
pytest tests/test_web_api.py -k "investment_api_uses_preference_defaults or investment_api_http_query_omitted_and_empty_use_preference_defaults or investment_api_http_query_preserves_explicit_zero" -q
3 passed, 65 deselected
```

---

### Task 6: Subagent Review Fixes

**Files:**
- Modify: `warframe_agent/web/app.py`
- Modify: `warframe_agent/web/static/js/sidebar.js`
- Modify: `tests/test_investment.py`
- Modify: `tests/test_chat_memory_commands.py`
- Modify: `tests/test_web_api.py`
- Modify: `md/rebuilt/*.md`
- Modify: `githubProduct/personal_agent_warframe_migration_step6_investment_preference_defaults_zh.md`

- [x] **Step 1: Address Web empty query**

Change `/api/investment` to accept raw optional strings for `budget` and `min_roi_pct`, normalize `""` to `None`, validate numeric bounds, and then call `resolve_investment_preference_defaults(...)`.

- [x] **Step 2: Address explicit zero coverage**

Add resolver, chat, and HTTP tests proving explicit `0` remains explicit rather than falling back to preferences.

- [x] **Step 3: Address UI fallback label**

Replace the summary fallback `500p` with `偏好预算`.

---

## Self-Review

- Spec coverage: Covers pure resolver, chat tool, Web endpoint, docs sync, and verification.
- Placeholder scan: No unresolved placeholders are present.
- Type consistency: Resolver returns `(int, float)` and both chat/Web pass those values into `scan_prime_investments`.
- GitHub constraint: No commit or push steps are included.
