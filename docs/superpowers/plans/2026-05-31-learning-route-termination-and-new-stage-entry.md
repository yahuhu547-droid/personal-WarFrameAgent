# Learning Route Termination And New Stage Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document the terminal condition for the personal Agent learning-borrowing route and define when future work must become a new stage instead of continuing the old queue.

**Architecture:** This is a documentation-only closure. It updates the route ledger, rebuilt audit docs, and `AGENTS.md` with explicit anti-loop rules; it does not modify runtime code, tests, endpoints, UI, tools, connectors, schedulers, or background workers.

**Tech Stack:** Markdown, ripgrep, git diff check.

---

## File Structure

- `docs/superpowers/plans/2026-05-31-learning-route-termination-and-new-stage-entry.md`: this Step 52 plan and execution ledger.
- `githubProduct/personal_agent_warframe_migration_step52_learning_route_termination_zh.md`: Step 52 route termination report.
- `githubProduct/personal_agent_learning_route_ledger_zh.md`: append Step 52 route ledger entry.
- `md/rebuilt/10-learning-route-audit.md`: append Step 52 route audit conclusion.
- `md/rebuilt/09-personal-agent-foundation.md`: append a short foundation-level closure note.
- `AGENTS.md`: append Step 52 progress, status, safety boundary, verification, and next-step rule.

## Execution Sequence

### Task 52: Learning Route Termination And New Stage Entry

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step52_learning_route_termination_zh.md`
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `AGENTS.md`

- [x] **Step 1: Verify current completion evidence**

Run:

```powershell
rg -n "Step 51|acceptance_status|acceptance_snapshot|最终结论|不再机械执行旧" AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\10-learning-route-audit.md warframe_agent\learning_completion.py tests\test_learning_completion.py
```

Expected: find Step 51 accepted completion evidence and "do not mechanically continue the old queue" wording.

Observed: Step 51 completion evidence is present in `AGENTS.md`, route ledger, route audit, `learning_completion.py`, and tests.

- [x] **Step 2: Write Step 52 report**

Create `githubProduct/personal_agent_warframe_migration_step52_learning_route_termination_zh.md` with:

- Step 52 is documentation-only.
- Old learning-borrowing route terminates at Step 51.
- Step 50 is the latest closure step.
- Step 51 is the accepted evidence record.
- Future high-privilege capabilities require a separate new-stage design.
- Repeated "continue until complete" requests should default to completion-state review and termination-rule maintenance, not runtime code.

- [x] **Step 3: Update route ledger**

Append Step 52 to `githubProduct/personal_agent_learning_route_ledger_zh.md` with:

- route termination rule,
- repeated-request interpretation rule,
- new-stage entry conditions,
- safety boundary,
- verification summary.

- [x] **Step 4: Update rebuilt docs**

Append Step 52 to:

- `md/rebuilt/10-learning-route-audit.md`
- `md/rebuilt/09-personal-agent-foundation.md`

Required content:

- Current route is not curved or incomplete.
- Step 52 does not reopen the old queue.
- Future work requires explicit new-stage capability naming and design approval.

- [x] **Step 5: Update AGENTS.md**

Append Step 52 with:

- 100% / 已完成 status,
- modification reason,
- impact scope,
- safety boundary,
- verification commands,
- next-step rule for future repeated requests.

- [x] **Step 6: Verify documentation**

Run:

```powershell
rg -n "Step 52|终止条件|新阶段入口|不再机械执行旧队列|future_capability_admission.enabled=False" AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\10-learning-route-audit.md md\rebuilt\09-personal-agent-foundation.md githubProduct\personal_agent_warframe_migration_step52_learning_route_termination_zh.md
git diff --check -- AGENTS.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\10-learning-route-audit.md md\rebuilt\09-personal-agent-foundation.md docs\superpowers\plans\2026-05-31-learning-route-termination-and-new-stage-entry.md githubProduct\personal_agent_warframe_migration_step52_learning_route_termination_zh.md
```

Expected: all Step 52 key phrases are present; `git diff --check` exits 0. LF/CRLF warnings are acceptable.

Observed: `rg` found Step 52, termination condition, new-stage entry, old-queue stop, and `future_capability_admission.enabled=False` wording across the expected docs; `git diff --check` exited 0.

## Self-Review

- Spec coverage: covers the user's repeated request without reopening completed runtime work.
- Placeholder scan: no TBD/TODO/fill-later items remain.
- Scope discipline: documentation-only; no runtime code, tests, endpoint, UI, connector, scheduler, or dependency changes.
- Safety boundary: no Browser/GUI executor, service recovery, arbitrary trigger platform, plugin install, connector enablement, webhook/DM command entry, GitHub upload, or real voice capability is enabled.
