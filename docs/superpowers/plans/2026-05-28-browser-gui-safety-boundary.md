# Browser GUI Safety Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Browser / GUI Agent safety boundary snapshot before any real browser or desktop automation is exposed.

**Architecture:** Create a small `warframe_agent.browser_gui_safety` module that classifies browser/GUI actions into read-only, confirmation-required, and blocked decisions. Embed its aggregate policy into the existing `build_runtime_safety_policy(...)` response so `/api/runtime/status` can show the boundary without enabling any new action executor.

**Tech Stack:** Python dataclasses, existing `safety_policy.py`, FastAPI runtime status, pytest.

---

## Context

- Source projects borrowed from: OpenManus and Open-AutoGLM.
- Borrowed idea: browser and GUI agents are powerful only when their action space is constrained, observable, and interruptible by a human.
- Warframe mapping: future browser automation may read market pages, wiki pages, or Bilibili guide pages, but it must not log in, send whispers, place orders, delete data, pay, upload files, or operate private network targets without explicit human design and confirmation.
- Current code already has `browser_private_network` disabled in `warframe_agent/safety_policy.py`, and Playwright is used mostly for tests plus a market scraper. This task adds action-level policy detail, not a new browser agent.

## Completion Definition

- `warframe_agent.browser_gui_safety` exists and exposes:
  - `classify_browser_gui_action(...)`
  - `build_browser_gui_safety_policy()`
- The policy marks read-only public-page actions as allowed without confirmation.
- The policy marks clicks, form input, downloads, uploads, and clipboard writes as requiring human confirmation.
- The policy marks login, payment, deletion, private message / whisper, order placement, credential entry, arbitrary script execution, and private-network targets as blocked.
- `/api/runtime/status` includes `safety_policy.browser_gui_policy`.
- Docs are synced to `githubProduct/`, `md/rebuilt/`, and `AGENTS.md`.

## File Structure

- Create: `warframe_agent/browser_gui_safety.py`
  - Owns action taxonomy, domain classification, policy snapshot, and safe serialization.
- Create: `tests/test_browser_gui_safety.py`
  - Unit tests for allowed, confirmation-required, blocked, private-network, and sensitive-text cases.
- Modify: `warframe_agent/safety_policy.py`
  - Embeds `browser_gui_policy` and adds `browser_gui_automation` capability.
- Modify: `tests/test_tool_registry.py`
  - Verifies runtime policy includes browser/GUI boundary without leaking URLs, tokens, or action payloads.
- Modify: `tests/test_web_api.py`
  - Verifies `/api/runtime/status` includes the policy snapshot and keeps existing safety behavior.
- Create: `githubProduct/personal_agent_warframe_migration_step38_browser_gui_safety_boundary_zh.md`
  - Records the learning source, borrowed point, implementation boundary, and verification.
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
  - Adds Step 38 route ledger entry.
- Modify: `md/rebuilt/04-web-api-reference.md`
  - Updates runtime API safety policy description.
- Modify: `md/rebuilt/06-tools-models-safety.md`
  - Adds Browser / GUI action matrix.
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - Adds Step 38 to the personal-agent foundation timeline.
- Modify: `md/rebuilt/10-learning-route-audit.md`
  - Adds the Step 38 audit result.
- Modify: `AGENTS.md`
  - Updates current progress, commands, verification summary, and next-step queue.

## Task 1: Unit Red Test

**Files:**
- Create: `tests/test_browser_gui_safety.py`

- [x] **Step 1: Write failing action policy tests**

Add:

```python
from __future__ import annotations

import json


def test_browser_gui_policy_classifies_read_only_public_actions():
    from warframe_agent.browser_gui_safety import classify_browser_gui_action

    decision = classify_browser_gui_action(
        "read_page",
        target_url="https://warframe.market/items/arcane_energize",
    )

    assert decision["decision"] == "allow_read_only"
    assert decision["requires_human_confirmation"] is False
    assert decision["blocked"] is False
    assert decision["target_scope"] == "public_warframe_market"


def test_browser_gui_policy_requires_confirmation_for_mutating_ui_actions():
    from warframe_agent.browser_gui_safety import classify_browser_gui_action

    decision = classify_browser_gui_action(
        "type_text",
        target_url="https://wiki.warframe.com",
        text="hello",
    )

    assert decision["decision"] == "requires_human_confirmation"
    assert decision["requires_human_confirmation"] is True
    assert decision["blocked"] is False


def test_browser_gui_policy_blocks_trade_private_and_credential_actions():
    from warframe_agent.browser_gui_safety import classify_browser_gui_action

    for action in ["login", "send_whisper", "place_order", "payment", "delete", "credential_entry"]:
        decision = classify_browser_gui_action(action, target_url="https://warframe.market/profile/SecretSeller")
        assert decision["decision"] == "blocked"
        assert decision["blocked"] is True
        assert decision["requires_human_confirmation"] is True


def test_browser_gui_policy_blocks_private_network_targets_and_redacts_sensitive_text():
    from warframe_agent.browser_gui_safety import classify_browser_gui_action

    decision = classify_browser_gui_action(
        "read_page",
        target_url="http://127.0.0.1:3000/admin?token=secret-token",
        text="/w SecretSeller hi Authorization: Bearer abc",
    )

    serialized = json.dumps(decision, ensure_ascii=False)
    assert decision["decision"] == "blocked"
    assert decision["target_scope"] == "private_network"
    for forbidden in ["127.0.0.1", "secret-token", "SecretSeller", "/w", "Bearer abc", "token="]:
        assert forbidden not in serialized


def test_browser_gui_policy_snapshot_is_aggregate_only():
    from warframe_agent.browser_gui_safety import build_browser_gui_safety_policy

    policy = build_browser_gui_safety_policy()

    assert policy["default_mode"] == "read_only"
    assert policy["automation_enabled"] is False
    assert "allow_read_only" in policy["decision_counts"]
    assert "requires_human_confirmation" in policy["decision_counts"]
    assert "blocked" in policy["decision_counts"]
    serialized = json.dumps(policy, ensure_ascii=False)
    for forbidden in ["SecretSeller", "token=", "raw_arguments", "profile/"]:
        assert forbidden not in serialized
```

- [x] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_browser_gui_safety.py -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: FAIL because `warframe_agent.browser_gui_safety` does not exist yet.

## Task 2: Minimal Browser GUI Safety Module

**Files:**
- Create: `warframe_agent/browser_gui_safety.py`
- Test: `tests/test_browser_gui_safety.py`

- [x] **Step 1: Implement action classifier and policy snapshot**

Create `warframe_agent/browser_gui_safety.py` with:

```python
from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Any
```

Add decision constants:

```python
ALLOW_READ_ONLY_ACTIONS = {"open_url", "read_page", "extract_text", "screenshot", "inspect_dom"}
CONFIRMATION_ACTIONS = {"click", "type_text", "submit_form", "download_file", "upload_file", "clipboard_write"}
BLOCKED_ACTIONS = {"login", "credential_entry", "payment", "delete", "send_whisper", "private_message", "place_order", "execute_script"}
PUBLIC_READ_DOMAINS = {"warframe.market", "api.warframe.market", "wiki.warframe.com", "warframe.fandom.com", "www.bilibili.com", "bilibili.com", "b23.tv"}
```

Implement:

```python
def classify_browser_gui_action(action: str, *, target_url: str = "", text: str = "") -> dict[str, Any]:
    safe_action = _safe_identifier(action)
    target_scope = _target_scope(target_url)
    if target_scope == "private_network" or safe_action in BLOCKED_ACTIONS:
        decision = "blocked"
    elif safe_action in CONFIRMATION_ACTIONS:
        decision = "requires_human_confirmation"
    elif safe_action in ALLOW_READ_ONLY_ACTIONS and target_scope.startswith("public_"):
        decision = "allow_read_only"
    else:
        decision = "requires_human_confirmation"
    return {
        "action": safe_action or "unknown",
        "decision": decision,
        "target_scope": target_scope,
        "requires_human_confirmation": decision != "allow_read_only",
        "blocked": decision == "blocked",
        "reason": _decision_reason(decision, safe_action, target_scope),
        "text_summary": _safe_text(text, max_chars=120) if text else "",
    }
```

Implement:

```python
def build_browser_gui_safety_policy() -> dict[str, Any]:
    examples = [
        classify_browser_gui_action("read_page", target_url="https://warframe.market/items/arcane_energize"),
        classify_browser_gui_action("type_text", target_url="https://wiki.warframe.com"),
        classify_browser_gui_action("login", target_url="https://warframe.market"),
        classify_browser_gui_action("read_page", target_url="http://127.0.0.1:3000/admin?token=secret-token"),
    ]
    return {
        "policy_version": "2026-05-28.browser-gui-safety-v1",
        "default_mode": "read_only",
        "automation_enabled": False,
        "human_takeover_required": True,
        "allowed_scopes": sorted(PUBLIC_READ_DOMAINS),
        "decision_counts": _decision_counts(examples),
        "action_matrix": examples,
        "guardrails": [
            "Browser and GUI automation is not exposed as an Agent executor.",
            "Read-only public pages may be inspected only after explicit implementation.",
            "Clicks, typing, downloads, uploads, and clipboard writes require human confirmation.",
            "Login, payment, deletion, private messages, trade order placement, credentials, arbitrary scripts, and private-network targets are blocked.",
        ],
    }
```

- [x] **Step 2: Run green unit test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_browser_gui_safety.py -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: PASS.

## Task 3: Runtime Safety Policy Integration

**Files:**
- Modify: `warframe_agent/safety_policy.py`
- Modify: `tests/test_tool_registry.py`
- Modify: `tests/test_web_api.py`

- [x] **Step 1: Add failing runtime policy tests**

In `tests/test_tool_registry.py`, extend `test_runtime_safety_policy_embeds_tool_registry_summary_without_tool_details`:

```python
    browser_policy = policy["browser_gui_policy"]
    assert browser_policy["default_mode"] == "read_only"
    assert browser_policy["automation_enabled"] is False
    assert browser_policy["human_takeover_required"] is True
    assert browser_policy["decision_counts"]["blocked"] >= 1
    assert "browser_gui_automation" in policy["capabilities"]
    assert policy["capabilities"]["browser_gui_automation"]["default"] == "disabled"
```

In `tests/test_web_api.py`, extend `test_runtime_status_includes_read_only_safety_policy`:

```python
        self.assertIn("browser_gui_policy", policy)
        self.assertFalse(policy["browser_gui_policy"]["automation_enabled"])
        self.assertTrue(policy["browser_gui_policy"]["human_takeover_required"])
        self.assertIn("browser_gui_automation", caps)
        self.assertEqual(caps["browser_gui_automation"]["default"], "disabled")
```

Add forbidden text checks:

```python
        for forbidden in ["127.0.0.1", "secret-token", "SecretSeller", "/w", "profile/"]:
            self.assertNotIn(forbidden, serialized)
```

- [x] **Step 2: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: FAIL because `browser_gui_policy` is not yet embedded.

- [x] **Step 3: Embed policy in runtime safety snapshot**

Modify `warframe_agent/safety_policy.py`:

```python
from .browser_gui_safety import build_browser_gui_safety_policy
```

Add capability:

```python
"browser_gui_automation": _capability(available=False, default="disabled", requires_explicit_enable=True),
```

Add top-level snapshot:

```python
"browser_gui_policy": build_browser_gui_safety_policy(),
```

Add guardrail:

```python
"Browser and GUI automation is not exposed; action-level policy is read-only.",
```

- [x] **Step 4: Run green tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: PASS. If Web app import hits existing SQLite WAL limits, rerun Web API target in a writable runtime.

## Task 4: Docs and Cross-Session Ledger

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step38_browser_gui_safety_boundary_zh.md`
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
- Modify: `md/rebuilt/04-web-api-reference.md`
- Modify: `md/rebuilt/06-tools-models-safety.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Modify: `AGENTS.md`

- [x] **Step 1: Write Step 38 migration summary**

The summary must include:

```markdown
# Step 38 Browser / GUI Agent 安全边界

## 借鉴来源

- OpenManus：浏览器状态回灌与任务执行前的动作边界。
- Open-AutoGLM：GUI/移动端动作空间必须有人工接管和禁止动作。

## 本项目落点

- 新增只读 `browser_gui_safety` 行为分类。
- `/api/runtime/status.safety_policy` 新增 `browser_gui_policy`。
- 不新增 Browser Agent，不执行点击、输入、登录或下单。

## 安全边界

- 只读公共页面可作为未来候选。
- 点击、输入、下载、上传、剪贴板写入必须人工确认。
- 登录、支付、删除、私信、下单、凭据输入、任意脚本和私网目标默认 blocked。

## 验证

- `tests/test_browser_gui_safety.py`
- `tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"`
- `tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"`
```

- [x] **Step 2: Update rebuilt docs and AGENTS.md**

Record:

- progress `100%`
- status `已完成`
- reason: Step 38 implements Browser / GUI safety boundary snapshot
- impact: `warframe_agent/browser_gui_safety.py`, `warframe_agent/safety_policy.py`, runtime API docs, safety docs
- next queue: voice/companion experience evaluation or controlled blocked-plan confirmation chain

## Task 5: Final Verification

**Files:**
- All files touched in Tasks 1-4

- [x] **Step 1: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_browser_gui_safety.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: all selected tests PASS.

- [x] **Step 2: Run static checks**

Run:

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/browser_gui_safety.py','warframe_agent/safety_policy.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent/browser_gui_safety.py warframe_agent/safety_policy.py tests/test_browser_gui_safety.py tests/test_tool_registry.py tests/test_web_api.py githubProduct/personal_agent_warframe_migration_step38_browser_gui_safety_boundary_zh.md githubProduct/personal_agent_learning_route_ledger_zh.md md/rebuilt/04-web-api-reference.md md/rebuilt/06-tools-models-safety.md md/rebuilt/09-personal-agent-foundation.md md/rebuilt/10-learning-route-audit.md AGENTS.md docs/superpowers/plans/2026-05-28-browser-gui-safety-boundary.md
```

Expected: `AST OK`, no whitespace errors. Git may warn about LF-to-CRLF conversion; that warning is acceptable if exit code is 0.

## Execution Note

The user asked to continue and start execution, and does not want GitHub sync for this phase. Execute inline after saving this plan, using subagents only for sidecar audit/review.
