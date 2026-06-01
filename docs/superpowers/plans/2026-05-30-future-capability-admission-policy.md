# Future Capability Admission Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only future capability admission policy so post-learning high-risk ideas cannot be mistaken for already-enabled runtime features.

**Architecture:** Follow the existing policy-module pattern used by `browser_gui_safety.py`, `gateway_policy.py`, and `plugin_policy.py`: a pure classifier plus a safe aggregate snapshot embedded in `build_runtime_safety_policy(...)`. The policy does not register tools, install plugins, enable connectors, start services, or add UI controls.

**Tech Stack:** Python, pytest, existing runtime safety policy builder, Markdown route ledger and rebuilt docs.

---

## File Structure

- `warframe_agent/future_capability_policy.py`: new pure classifier and snapshot builder for future-stage high-risk capability admission.
- `tests/test_future_capability_policy.py`: unit tests for classification, frozen voice boundary, safe snapshot, and redaction.
- `warframe_agent/safety_policy.py`: import and embed `future_capability_policy`; add `future_capability_admission` capability.
- `tests/test_tool_registry.py`: extend runtime safety policy aggregate test.
- `docs/superpowers/plans/2026-05-30-future-capability-admission-policy.md`: this implementation plan.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: route ledger Step 48 update.
- `githubProduct/personal_agent_warframe_migration_step48_future_capability_admission_zh.md`: Step 48 learning report.
- `md/rebuilt/06-tools-models-safety.md`: safety docs update.
- `md/rebuilt/09-personal-agent-foundation.md`: foundation docs update.
- `md/rebuilt/10-learning-route-audit.md`: route audit update.
- `AGENTS.md`: cross-session progress and commands.

## Execution Sequence

### Task 48: Future Capability Admission Policy

**Files:**
- Create: `warframe_agent/future_capability_policy.py`
- Create: `tests/test_future_capability_policy.py`
- Modify: `warframe_agent/safety_policy.py`
- Modify: `tests/test_tool_registry.py`
- Modify docs listed above.

- [x] **Step 1: Write failing tests**

Create tests requiring:

```python
from warframe_agent.future_capability_policy import (
    build_future_capability_policy,
    classify_future_capability,
)


def test_future_capability_requires_new_stage_design_for_browser_executor():
    decision = classify_future_capability(
        "browser_gui_executor",
        request_text="enable Playwright login automation token=secret-token /w Player",
    )
    assert decision["decision"] == "requires_new_stage_design"
    assert decision["runtime_enabled"] is False
    assert decision["requires_explicit_user_approval"] is True
    assert "secret-token" not in str(decision)


def test_future_capability_freezes_real_voice_by_user_instruction():
    decision = classify_future_capability("real_voice_service", request_text="turn on microphone")
    assert decision["decision"] == "frozen_by_current_user_instruction"
    assert decision["runtime_enabled"] is False


def test_future_capability_blocks_public_webhooks_and_dms():
    for name in ("anonymous_webhook", "public_comment_commands", "seller_dm_commands"):
        decision = classify_future_capability(name)
        assert decision["decision"] == "blocked_public_or_private_inbound"
        assert decision["runtime_enabled"] is False


def test_future_capability_allows_design_docs_only():
    decision = classify_future_capability("design_doc")
    assert decision["decision"] == "allow_design_only"
    assert decision["runtime_enabled"] is False


def test_future_capability_snapshot_is_safe_and_aggregate_only():
    policy = build_future_capability_policy()
    assert policy["default_mode"] == "design_required_before_runtime"
    assert policy["runtime_enablement_allowed"] is False
    assert policy["decision_counts"]["requires_new_stage_design"] >= 1
    assert policy["decision_counts"]["frozen_by_current_user_instruction"] >= 1
    serialized = str(policy)
    for forbidden in ("secret-token", "api_key", "account_id", "raw_payload", "handler", "params", "/w", "Player"):
        assert forbidden not in serialized
```

- [x] **Step 2: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_tool_registry.py -k "future_capability or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-red -p no:cacheprovider
```

Expected: fail because `warframe_agent.future_capability_policy` does not exist.

- [x] **Step 3: Implement the pure policy module**

Create `future_capability_policy.py` with:

```python
POLICY_VERSION = "2026-05-30.future-capability-admission-v1"

def classify_future_capability(capability: str, *, request_text: str = "") -> dict[str, Any]:
    ...

def build_future_capability_policy() -> dict[str, Any]:
    ...
```

Required decisions:
- `allow_design_only`
- `requires_new_stage_design`
- `frozen_by_current_user_instruction`
- `blocked_public_or_private_inbound`
- `blocked_uncontrolled_runtime`

Required safe fields:
- `capability`
- `decision`
- `runtime_enabled`
- `requires_new_stage_design`
- `requires_explicit_user_approval`
- `reason`
- `request_summary`

- [x] **Step 4: Integrate runtime safety**

Update `build_runtime_safety_policy(...)`:

```python
from .future_capability_policy import build_future_capability_policy

"future_capability_admission": _capability(
    available=True,
    default="design_required",
    requires_explicit_enable=True,
    enabled=False,
    scope="future_high_risk_features_policy_only",
),
"future_capability_policy": build_future_capability_policy(),
```

Add a guardrail line explaining that completed learning does not imply high-risk runtime features are enabled.

- [x] **Step 5: Run green tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_tool_registry.py -k "future_capability or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-green -p no:cacheprovider
```

Expected: tests pass.

- [x] **Step 6: Update documentation**

Document Step 48 in:
- `githubProduct/personal_agent_warframe_migration_step48_future_capability_admission_zh.md`
- `githubProduct/personal_agent_learning_route_ledger_zh.md`
- `md/rebuilt/06-tools-models-safety.md`
- `md/rebuilt/09-personal-agent-foundation.md`
- `md/rebuilt/10-learning-route-audit.md`
- `AGENTS.md`

Wording requirements:
- Old non-voice learning-borrowing route is complete.
- Step 48 is a new-stage safety admission layer, not an unfinished old queue item.
- Real voice remains frozen by current user instruction.
- No real Browser/GUI executor, service recovery, arbitrary trigger platform, plugin install, connector enablement, webhook, DM command, shell, or file-write runtime is enabled.

- [x] **Step 7: Final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-final -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step48-web-api-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/future_capability_policy.py','warframe_agent/safety_policy.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\future_capability_policy.py warframe_agent\safety_policy.py tests\test_future_capability_policy.py tests\test_tool_registry.py docs\superpowers\plans\2026-05-30-future-capability-admission-policy.md githubProduct\personal_agent_warframe_migration_step48_future_capability_admission_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\06-tools-models-safety.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

Expected: tests pass, AST OK, diff check exits 0. LF/CRLF warnings are acceptable.

Observed: policy tests `20 passed, 33 deselected`; Web API ordinary sandbox failed on SQLite WAL database open, writable environment rerun `1 passed, 71 deselected`; AST OK; `git diff --check` exited 0 with LF/CRLF warnings only.

## Self-Review

- Spec coverage: covers the recommended next step after the old learning route is complete.
- Placeholder scan: no open-ended implementation steps remain.
- Type consistency: follows existing policy module patterns and runtime safety keys.
- Safety boundary: this plan is policy-only and does not enable voice, Browser/GUI execution, service recovery, arbitrary triggers, plugin installation, connectors, public webhooks, platform DMs, shell, or generic file writes.
