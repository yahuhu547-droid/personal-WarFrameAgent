# Plan Reviewer Verifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first safe code step from Step 34: add a read-only Planner Reviewer / Verifier summary to existing AgentPlan snapshots without introducing full multi-agent orchestration.

**Architecture:** Keep `ChatAgent + ToolRouter + ModelOrchestrator` as the main path. Add lightweight plan-review dataclasses and deterministic review logic inside `warframe_agent/tool_router.py`, serialize the safe summary through `/api/runtime/status`, and render it in the existing runtime panel. The reviewer does not call cloud models and does not execute tools; plans with `review.status == "blocked"` are soft-blocked before executor calls, while approved plans keep the existing execution order.

**Tech Stack:** Python dataclasses, pytest, FastAPI runtime status serialization, existing Web static JS, Markdown docs.

---

## Route Assignment

来源项目：LangManus / OpenManus / Suna。

借鉴点：LangManus planner constraints, OpenManus planning state, Suna worker verification summary.

Warframe 映射：`AgentPlanSnapshot` gains `verification_note`, `blocked_reason`, and a read-only `review`; Web runtime panel displays the review without exposing raw arguments, raw result summaries, model context, API keys, profile URLs, `/w`, or cloud-provider secrets.

安全边界：No full multi-agent system, no Browser/Coder/Sandbox worker, no direct cloud calls. The reviewer is deterministic and consumes only plan steps plus existing `ToolRegistry` metadata. Three cloud AI models remain routed only through `ModelOrchestrator` / `llm.py`.

验证方式：Unit tests for review logic and trace snapshots, Web API serialization test, JS static contract test, JSON/Markdown/diff checks.

---

## Files

- Modify: `F:\giteeProject\warframe\warframe_agent\tool_router.py`
- Modify: `F:\giteeProject\warframe\warframe_agent\web\app.py`
- Modify: `F:\giteeProject\warframe\warframe_agent\web\static\js\app.js`
- Modify: `F:\giteeProject\warframe\tests\test_plan.py`
- Modify: `F:\giteeProject\warframe\tests\test_tool_router.py`
- Modify: `F:\giteeProject\warframe\tests\test_web_api.py`
- Modify: `F:\giteeProject\warframe\tests\test_web_ui_playwright.py`
- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_warframe_migration_step35_plan_reviewer_verifier_zh.md`
- Modify: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\09-personal-agent-foundation.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`

Do not edit external reference repos or `.env`.

---

### Task 1: Red Tests For Plan Review

**Files:**
- Modify: `F:\giteeProject\warframe\tests\test_plan.py`
- Modify: `F:\giteeProject\warframe\tests\test_tool_router.py`

- [ ] **Step 1: Add tests for deterministic plan review**

Add tests that import `review_execution_plan` and assert:

- all read-only known tools produce `status == "ok"`
- unknown plan step produces `status == "blocked"` and `blocked_reason == "unknown_tool"`
- sensitive argument keys produce `status == "blocked"` and `blocked_reason == "sensitive_arguments"`
- side-effect tools from a custom `ToolRegistry` produce `status == "blocked"` and `blocked_reason == "side_effect_tool"`

- [ ] **Step 2: Add trace snapshot test**

Extend the existing plan snapshot test to assert:

- `trace.plan.review.status` exists
- `trace.plan.review.verification_note` exists
- each `AgentPlanStep` has `verification_note`
- unsafe step arguments are redacted in `args_summary`

- [ ] **Step 3: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plan.py tests\test_tool_router.py -k "plan_review or agent_plan" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected before implementation: failures for missing `review_execution_plan` / new fields.

### Task 2: Implement Read-Only Reviewer

**Files:**
- Modify: `F:\giteeProject\warframe\warframe_agent\tool_router.py`

- [ ] **Step 1: Add dataclasses**

Add:

```python
@dataclass(frozen=True)
class PlanReviewIssue:
    step_index: int
    tool_name: str
    code: str

@dataclass(frozen=True)
class PlanReviewSummary:
    status: str = "ok"
    verification_note: str = "plan_review=ok"
    blocked_reason: str = ""
    issue_count: int = 0
    unknown_tool_count: int = 0
    side_effect_tool_count: int = 0
    sensitive_argument_count: int = 0
```

Do not include raw arguments or model text in review objects.

- [ ] **Step 2: Add fields to snapshots**

Add to `AgentPlanStep`:

```python
verification_note: str = ""
blocked_reason: str = ""
```

Add to `AgentPlanSnapshot`:

```python
verification_note: str = ""
blocked_reason: str = ""
review: PlanReviewSummary | None = None
```

- [ ] **Step 3: Add review_execution_plan**

Review only metadata:

- unknown tool -> blocked
- `ToolSpec.side_effect` -> blocked
- sensitive argument key -> blocked
- otherwise ok

Return a `PlanReviewSummary`.

- [ ] **Step 4: Attach review in _register_trace_plan**

When registering a plan:

- compute the review with `_DEFAULT_REGISTRY`
- set snapshot `review`
- set snapshot `verification_note`
- set snapshot `blocked_reason`
- set per-step `verification_note` / `blocked_reason` by the matching issue code

After reviewer follow-up, blocked plans must stop before executor calls; approved plans still execute in the existing order.

- [ ] **Step 5: Run target unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plan.py tests\test_tool_router.py -k "plan_review or agent_plan" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: pass.

### Task 3: Safe Runtime API Serialization

**Files:**
- Modify: `F:\giteeProject\warframe\warframe_agent\web\app.py`
- Modify: `F:\giteeProject\warframe\tests\test_web_api.py`

- [ ] **Step 1: Extend API tests**

Update `test_runtime_status_includes_safe_agent_trace_snapshot` to set `verification_note`, `blocked_reason`, and `review`, then assert the response contains safe review fields and no sensitive values.

- [ ] **Step 2: Serialize safe plan review**

Add helper:

```python
def _safe_agent_plan_review(review: Any) -> dict[str, Any]:
    ...
```

Expose only:

- `present`
- `status`
- `verification_note`
- `blocked_reason`
- `issue_count`
- `unknown_tool_count`
- `side_effect_tool_count`
- `sensitive_argument_count`

- [ ] **Step 3: Include step notes**

`_safe_agent_plan_step` should include sanitized `verification_note` and `blocked_reason`.

- [ ] **Step 4: Run Web API target**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_safe_agent_trace_snapshot" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: pass, unless the known sandbox SQLite WAL issue blocks Web app import.

### Task 4: Runtime Panel Display

**Files:**
- Modify: `F:\giteeProject\warframe\warframe_agent\web\static\js\app.js`
- Modify: `F:\giteeProject\warframe\tests\test_web_ui_playwright.py`

- [ ] **Step 1: Add static contract assertions**

Extend existing runtime/plan static contract test to require:

- `verification_note`
- `blocked_reason`
- plan review rendering
- no `raw_arguments`, `result_summary`, `model_context`, `/w`, token leaks

- [ ] **Step 2: Render plan review**

In `renderRuntimeAgentPlan(plan)`, show a small safe review line:

```text
review_status=... | verification=... | blocked=...
```

In `renderRuntimeAgentPlanStep(step)`, show safe `verification_note` / `blocked_reason` only when present.

- [ ] **Step 3: Run JS static contract**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: pass. Full Playwright may still require non-sandbox if Web server import hits SQLite WAL.

### Task 5: Docs Sync

**Files:**
- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_warframe_migration_step35_plan_reviewer_verifier_zh.md`
- Modify: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\09-personal-agent-foundation.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`

- [ ] **Step 1: Write Step 35 doc**

Document:

- source projects
- borrowed idea
- Warframe mapping
- safety boundary
- verification commands and results
- note that three cloud AI models remain behind `ModelOrchestrator`

- [ ] **Step 2: Append route ledger note**

Add Step 35 result and next queue update.

- [ ] **Step 3: Append rebuilt notes**

Sync `09-personal-agent-foundation.md` and `10-learning-route-audit.md`.

### Task 6: Final Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plan.py tests\test_tool_router.py -k "plan_review or agent_plan" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_safe_agent_trace_snapshot" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_sidebar_static_contracts_match_warframe_player_context -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/tool_router.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
node --check warframe_agent\web\static\js\app.js
git diff --check -- warframe_agent/tool_router.py warframe_agent/web/app.py warframe_agent/web/static/js/app.js tests/test_plan.py tests/test_tool_router.py tests/test_web_api.py tests/test_web_ui_playwright.py githubProduct/personal_agent_warframe_migration_step35_plan_reviewer_verifier_zh.md githubProduct/personal_agent_learning_route_ledger_zh.md md/rebuilt/09-personal-agent-foundation.md md/rebuilt/10-learning-route-audit.md docs/superpowers/plans/2026-05-27-plan-reviewer-verifier.md
```

Expected: targeted tests pass. If Web API / Playwright hit the known sandbox SQLite WAL problem, record the failure and run the static tests that do not require Web app import.

---

## Completion Criteria

- Existing AgentPlan snapshots include deterministic read-only review metadata.
- Runtime API and Web panel expose only safe review summaries.
- No cloud model calls are added.
- No external reference repo source is edited.
- `md/rebuilt` is synced.
- No GitHub commit or push is performed.
