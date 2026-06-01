# AgentPlan Chat Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the Step 41 `ToolRouter` confirmation token to `ChatAgent` so a user can reply "确认执行" for a safe blocked plan without copying the token.

**Architecture:** Keep raw plan data out of `ChatAgent` state. Store only the original user message, candidate tool names, blocked reason, and confirmation token; on confirmation, rerun `react_loop` against the original message with the stored token so `ToolRouter` rechecks the current plan fingerprint and relaxed review before executing.

**Tech Stack:** Python dataclasses, existing `ChatAgent`, `ToolRouter.react_loop`, pytest.

---

## Scope

Voice, TTS/STT, microphone, Live2D, real Browser/GUI automation, shell execution, scheduler creation, and external side effects are out of scope.

## Completion Criteria

| Item | Expected result | Verification |
| --- | --- | --- |
| Pending capture | A `missing_verification` read-only plan creates a pending confirmation in `ChatAgent` | `tests/test_chat.py` red/green test |
| User prompt | User sees "确认执行" / "取消执行" and does not see `plan_confirm_` | `tests/test_chat.py` assertion |
| Confirm execution | Replying "确认执行" reruns the original message with the stored token and executes only after `ToolRouter` re-review | `tests/test_chat.py` assertion on tool execution |
| Cancel | Replying "取消执行" clears pending state and later confirmation does nothing | `tests/test_chat.py` assertion |
| High-risk blocked plans | `side_effect_tool` and sensitive/unknown/non-exposed blocked plans do not create pending confirmation | `tests/test_chat.py` assertion |
| Streaming parity | `answer_stream` handles "确认执行" using the same confirmation helper | focused async test if needed |
| Docs sync | Step 42 learning doc, route ledger, `md/rebuilt`, and `AGENTS.md` updated | diff review |

## Files

- Modify: `warframe_agent/chat.py`
  - Add `PendingAgentPlanConfirmation`.
  - Add `_pending_agent_plan_confirmation`.
  - Add helpers for accept/cancel/capture/formatting.
  - Thread `plan_confirmation_token` through `_try_react_loop`.
  - Call confirmation helper from `answer` and `answer_stream`.
- Modify: `tests/test_chat.py`
  - Add focused tests for prompt, confirm, cancel, and side-effect non-capture.
- Create: `githubProduct/personal_agent_warframe_migration_step42_chat_plan_confirmation_zh.md`
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Modify: `AGENTS.md`

## Tasks

### Task 1: ChatAgent Pending Plan Confirmation Tests

**Files:**
- Modify: `tests/test_chat.py`

- [ ] **Step 1: Write failing tests**

Add tests that use a deterministic `router_call` sequence:

```python
def test_agent_plan_confirmation_prompt_does_not_show_token_or_execute():
    # first router response returns a plan with query_price and no purpose
    # expected: reply asks for "确认执行", hides plan_confirm_, no order_fetcher call
```

```python
def test_agent_plan_confirmation_executes_after_user_confirms():
    # router responses: blocked plan, same plan, final answer
    # expected: second reply is final answer and query_price executed once
```

```python
def test_agent_plan_confirmation_cancel_clears_pending_plan():
    # expected: "取消执行" clears state, later "确认执行" does not run tools
```

```python
def test_agent_plan_confirmation_does_not_capture_side_effect_plan():
    # side-effect set_alert plan remains blocked and "确认执行" reports no pending plan
```

- [ ] **Step 2: Run tests and verify red**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "agent_plan_confirmation" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: fail because `ChatAgent` does not yet store or consume pending plan confirmations.

### Task 2: Minimal ChatAgent Confirmation State

**Files:**
- Modify: `warframe_agent/chat.py`

- [ ] **Step 1: Add dataclass and state**

```python
@dataclass(frozen=True)
class PendingAgentPlanConfirmation:
    original_message: str
    confirmation_token: str
    blocked_reason: str
    candidate_tools: tuple[str, ...] | None = None
```

Initialize:

```python
self._pending_agent_plan_confirmation: PendingAgentPlanConfirmation | None = None
```

- [ ] **Step 2: Add response helper**

Implement `_try_agent_plan_confirmation_response(message)`:
- "取消执行" clears pending.
- "确认执行" reruns `_try_react_loop(original_message, candidate_tools=set(...), plan_confirmation_token=token)`.
- Generic "确认" does not trigger this path.

- [ ] **Step 3: Capture safe pending state**

When `_try_react_loop(...)` returns a blocked result containing:

```txt
confirmation_required=true; confirmation_token=plan_confirm_...; confirmable_reason=missing_verification
```

store a `PendingAgentPlanConfirmation` and return a friendly prompt that hides the token.

- [ ] **Step 4: Preserve hard blocks**

Do not store pending state unless `confirmable_reason=missing_verification` and a `plan_confirm_` token is present.

- [ ] **Step 5: Run tests and verify green**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "agent_plan_confirmation" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: pass.

### Task 3: Docs And Route Ledger

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step42_chat_plan_confirmation_zh.md`
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Document source and mapping**

Record:
- Source projects: LangManus / OpenManus / Suna.
- Borrowed point: planner review plus user confirmation.
- Warframe mapping: `ChatAgent` pending confirmation delegates final decision to `ToolRouter`.

- [ ] **Step 2: Document safety boundary**

Record:
- No voice / TTS / STT / microphone.
- No Browser / GUI / shell / scheduler executor.
- No raw plan persistence.
- Only `missing_verification` read-only plans.

- [ ] **Step 3: Update progress**

Add Step 42 as 100% only after tests and static checks pass.

### Task 4: Verification

**Files:**
- Verify changed Python and docs.

- [ ] **Step 1: Run target tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py tests\test_plan.py -k "agent_plan_confirmation or plan_confirmation or confirmed_missing_verification" -q --basetemp .pytest-tmp -p no:cacheprovider
```

- [ ] **Step 2: Run AST**

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

- [ ] **Step 3: Run diff whitespace check**

```powershell
git diff --check -- warframe_agent/chat.py tests/test_chat.py docs/superpowers/plans/2026-05-30-agent-plan-chat-confirmation.md githubProduct/personal_agent_warframe_migration_step42_chat_plan_confirmation_zh.md githubProduct/personal_agent_learning_route_ledger_zh.md md/rebuilt/09-personal-agent-foundation.md md/rebuilt/10-learning-route-audit.md AGENTS.md
```
