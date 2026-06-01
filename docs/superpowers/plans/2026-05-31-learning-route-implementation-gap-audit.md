# Learning Route Implementation Gap Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the full personal Agent learning-borrowing route after Step 52 and mark historical wording that could mislead future agents into reopening the completed old queue.

**Architecture:** This is a documentation-only anti-drift pass. It adds a Step 53 report and inserts current-status notices in existing route documents; it does not modify runtime code, tests, endpoints, UI, tools, connectors, schedulers, or background workers.

**Tech Stack:** Markdown, ripgrep, pytest/AST/JS verification commands, git diff check.

---

## File Structure

- `docs/superpowers/plans/2026-05-31-learning-route-implementation-gap-audit.md`: this Step 53 plan and execution ledger.
- `githubProduct/personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md`: Step 53 full-route implementation gap audit report.
- `AGENTS.md`: update top-level learning route state and append Step 53.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: add current-authority note near historical queue and append Step 53.
- `md/rebuilt/09-personal-agent-foundation.md`: add top status note and append Step 53.
- `md/rebuilt/10-learning-route-audit.md`: add top history notice and append Step 53.

## Execution Sequence

### Task 53: Full Route Implementation Gap Audit

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md`
- Modify: `AGENTS.md`
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`

- [x] **Step 1: Run initial gap search**

Run:

```powershell
rg -n "未完成|待评估|下一步|剩余|继续旧|不再机械|终止|Step 39|Step 52|Step 53|acceptance_status|future_capability_admission.enabled=False" AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt docs\superpowers\plans
rg -n "TODO|TBD|fill later|待补|待确认|待执行|未补跑|债务" AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md docs\superpowers\plans\2026-05-31-learning-route-termination-and-new-stage-entry.md docs\superpowers\plans\2026-05-31-learning-completion-acceptance-snapshot.md
```

Observed: no code gap was found, but historical docs still contain old "remaining queue", "next step", and Step 39 debt wording that could be misread without the later Step 52 context.

- [x] **Step 2: Write Step 53 report**

Create `githubProduct/personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md` with:

- no runtime code gap found,
- route completion evidence,
- historical wording risks,
- docs updated to mark historical sections,
- no high-privilege runtime enablement,
- verification summary.

- [x] **Step 3: Add current-authority notices**

Update:

- `AGENTS.md` top project overview,
- `githubProduct/personal_agent_learning_route_ledger_zh.md` near the historical queue,
- `md/rebuilt/09-personal-agent-foundation.md` near the beginning,
- `md/rebuilt/10-learning-route-audit.md` near the beginning.

Required wording:

- Step 52 is the current route-control authority.
- Historical "remaining queue" / "next step" sections are preserved for audit history, not current instructions.
- `learning_completion.status=complete` and `acceptance_status=accepted` are current completion anchors.

- [x] **Step 4: Append Step 53 entries**

Append Step 53 sections to:

- `AGENTS.md`
- `githubProduct/personal_agent_learning_route_ledger_zh.md`
- `md/rebuilt/09-personal-agent-foundation.md`
- `md/rebuilt/10-learning-route-audit.md`

Required wording:

- Step 53 is a full-route implementation gap audit.
- It found no code/API/UI/test gap that requires new runtime implementation.
- It fixed a documentation weakness: historical wording could mislead future agents.
- Future high-privilege work must remain a new stage.

- [x] **Step 5: Run implementation verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "learning_completion or future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step53-policy -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/learning_completion.py','warframe_agent/future_capability_policy.py','warframe_agent/gateway_policy.py','warframe_agent/plugin_policy.py','warframe_agent/safety_policy.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step53-static -p no:cacheprovider
```

Expected: policy/unit tests pass, JS syntax OK, AST OK, Runtime static contract passes.

Observed: policy/unit tests `25 passed, 33 deselected`; JS syntax OK; AST OK; Runtime static contract `1 passed`.

- [x] **Step 6: Run documentation verification**

Run:

```powershell
rg -n "Step 53|实现不足复核|历史记录|当前权威|旧学习借鉴路线|acceptance_status=accepted|不再机械执行旧队列" AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md githubProduct\personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md
git diff --check -- AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md docs\superpowers\plans\2026-05-31-learning-route-implementation-gap-audit.md githubProduct\personal_agent_warframe_migration_step53_learning_route_gap_audit_zh.md
```

Expected: key Step 53 wording is present and `git diff --check` exits 0. LF/CRLF warnings are acceptable.

Observed: Step 53 wording is present across `AGENTS.md`, route ledger, rebuilt docs, and the Step 53 report; `git diff --check` exited 0.

## Self-Review

- Spec coverage: covers the user's fallback request to audit implementation gaps when no new next step is recommended.
- Placeholder scan: no TBD/TODO/fill-later items remain.
- Scope discipline: documentation-only anti-drift update; no runtime code changes.
- Safety boundary: no Browser/GUI executor, service recovery, arbitrary trigger platform, plugin install, connector enablement, webhook/DM command entry, GitHub upload, dependency download, or real voice capability is enabled.
