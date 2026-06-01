# Multi Agent Role Architecture Decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide whether Warframe Agent should adopt LangManus/OpenManus/Suna-style explicit roles, while accounting for the project’s three cloud Scout models and existing single-Agent tool routing.

**Architecture:** This is an architecture decision and learning-migration task, not a runtime implementation. The plan compares external role patterns with local `ChatAgent`, `ToolRouter`, `AgentPlanSnapshot`, `ModelOrchestrator`, and Scout model routing, then writes a Step 34 migration decision and syncs the route ledger/rebuilt docs.

**Tech Stack:** Markdown, PowerShell, Python static reads only, `rg`, local reference repos under `githubProduct`, Warframe Agent modules `chat.py`, `tool_router.py`, `model_orchestrator.py`, `llm.py`, `scout.py`, and `config.py`.

---

## Route Assignment

来源项目：LangManus / OpenManus / Suna。

借鉴点：coordinator、planner、supervisor、researcher、browser、reporter、sandbox runtime、planning flow、tool-calling loop。

Warframe 映射：`ChatAgent`、`ToolRouter`、`AgentPlanSnapshot`、Scout 扫描、机会复盘、个人记忆、`ModelOrchestrator`、三个云端 Scout 模型。

安全边界：本轮只做只读架构决策，不新增执行器，不接管主链路，不启用 Browser/GUI 自动化，不增加外部写入；未来任何角色化执行必须复用现有确认式写入、runtime safety policy、`tool_context.py` 脱敏和 `ModelOrchestrator` 路由。

验证方式：生成角色边界表，明确“保持单 Agent / 可拆 Planner / 可拆 Reviewer / 暂不引入 Browser / 不引入 autonomous Supervisor”；验证文档可读、JSON 仍可解析、diff 无空白错误。

---

## Files

- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_warframe_migration_step34_multi_agent_role_architecture_decision_zh.md`
- Modify: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\09-personal-agent-foundation.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`
- Create: `F:\giteeProject\warframe\docs\superpowers\plans\2026-05-27-multi-agent-role-architecture-decision.md`

Read-only evidence:

- `F:\giteeProject\warframe\githubProduct\langmanus`
- `F:\giteeProject\warframe\githubProduct\OpenManus`
- `F:\giteeProject\warframe\githubProduct\suna`
- `F:\giteeProject\warframe\warframe_agent\chat.py`
- `F:\giteeProject\warframe\warframe_agent\tool_router.py`
- `F:\giteeProject\warframe\warframe_agent\model_orchestrator.py`
- `F:\giteeProject\warframe\warframe_agent\llm.py`
- `F:\giteeProject\warframe\warframe_agent\scout.py`
- `F:\giteeProject\warframe\warframe_agent\config.py`

Do not edit external reference repos.

---

### Task 1: Local Architecture Evidence

**Files:**
- Read: `F:\giteeProject\warframe\warframe_agent\chat.py`
- Read: `F:\giteeProject\warframe\warframe_agent\tool_router.py`
- Read: `F:\giteeProject\warframe\warframe_agent\model_orchestrator.py`
- Read: `F:\giteeProject\warframe\warframe_agent\llm.py`
- Read: `F:\giteeProject\warframe\warframe_agent\scout.py`
- Read: `F:\giteeProject\warframe\warframe_agent\config.py`

- [ ] **Step 1: Confirm current single-Agent entry points**

Run:

```powershell
rg -n "class ChatAgent|def _call_llm_messages|def _run_tool_plan|AgentPlanSnapshot|class ModelOrchestrator|SCOUT_MODELS" warframe_agent\chat.py warframe_agent\tool_router.py warframe_agent\model_orchestrator.py warframe_agent\config.py
```

Expected: output shows `ChatAgent`, `ToolRouter`/`AgentPlanSnapshot`, `ModelOrchestrator`, and `SCOUT_MODELS`.

- [ ] **Step 2: Confirm three cloud Scout models**

Run:

```powershell
rg -n "kimi-k2.6|glm-5.1|gpt-5.5|SCOUT_MOD_MODEL|SCOUT_SET_MODEL|SCOUT_INV_MODEL|CLOUD_API_BASE|CLOUD_API_KEY" warframe_agent\config.py warframe_agent\llm.py warframe_agent\scout.py tests\test_model_orchestrator.py tests\test_scout.py
```

Expected: output shows Mod/赋能, 套装套利, and 投资顾问 use task-specific cloud model names through config, with API key coming only from environment variables.

- [ ] **Step 3: Confirm current safety boundary**

Run:

```powershell
rg -n "tool_context|model_context|runtime safety|safety_policy|raw_arguments|profile|/w|token|api_key" warframe_agent md\rebuilt tests
```

Expected: output shows existing model-context sanitization and runtime safety docs/tests.

### Task 2: External Role Pattern Evidence

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\langmanus`
- Read: `F:\giteeProject\warframe\githubProduct\OpenManus`
- Read: `F:\giteeProject\warframe\githubProduct\suna`

- [ ] **Step 1: Inspect LangManus role names**

Run:

```powershell
rg -n "coordinator|planner|supervisor|researcher|coder|browser|reporter" githubProduct\langmanus
```

Expected: output identifies role files or graph nodes.

- [ ] **Step 2: Inspect OpenManus loop**

Run:

```powershell
rg -n "class BaseAgent|class ReActAgent|class ToolCallAgent|class Manus|PlanningFlow|think|act|run" githubProduct\OpenManus\app
```

Expected: output identifies the compact single-Agent loop and planning flow.

- [ ] **Step 3: Inspect Suna runtime references**

Run:

```powershell
rg -n "sandbox|trigger|agent|thread|workflow|planner|runtime" githubProduct\suna README* githubProduct\suna\core githubProduct\suna\apps
```

Expected: output identifies persistent sandbox/runtime and trigger-style architecture, without running services.

### Task 3: Write Step 34 Decision

**Files:**
- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_warframe_migration_step34_multi_agent_role_architecture_decision_zh.md`

- [ ] **Step 1: Record decision summary**

The decision must say:

```markdown
当前不引入完整 LangManus/Suna 式多 Agent 产品架构；保留 ChatAgent + ToolRouter + ModelOrchestrator 的单 Agent 主链路。
```

- [ ] **Step 2: Add role boundary table**

Include rows for:

- Coordinator
- Planner
- Supervisor
- Researcher
- Browser
- Reporter
- Reviewer
- Model Router

Each row must include: source project, Warframe mapping, decision, allowed inputs, forbidden actions, verification path.

- [ ] **Step 3: Account for three cloud AI models**

Document:

- `kimi-k2.6` for Mod/赋能 Scout prefilter
- `glm-5.1` for Prime 套装套利 Scout prefilter
- `gpt-5.5` for investment Scout and default cloud complex analysis
- all use OpenAI-compatible `CLOUD_API_BASE` and `CLOUD_API_KEY`
- no role may call cloud models directly outside `ModelOrchestrator`/`llm.py`

- [ ] **Step 4: Set next implementation boundary**

Set the safe next code step, if any, to:

```markdown
先增加“角色化观察/复盘文档或只读 Reporter”，不增加 autonomous Supervisor，也不启用 Browser/GUI Agent。
```

### Task 4: Sync Route Ledger And Rebuilt Docs

**Files:**
- Modify: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\09-personal-agent-foundation.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`

- [ ] **Step 1: Append Step 34 to route ledger**

Add a short section:

```markdown
## 2026-05-27 Step 34：多 Agent 角色架构决策
```

It must link the decision doc and record the current decision.

- [ ] **Step 2: Append Step 34 to rebuilt foundation**

Append a concise Step 34 note to `md/rebuilt/09-personal-agent-foundation.md`.

- [ ] **Step 3: Append route-audit sync**

Append a concise sync note to `md/rebuilt/10-learning-route-audit.md` saying the next task was executed and the route now moves to long-running ops, voice/persona, browser/GUI, or inspectable memory depending on the next user request.

### Task 5: Verification

**Files:**
- Verify: `F:\giteeProject\warframe\githubProduct\personal_agent_warframe_migration_step34_multi_agent_role_architecture_decision_zh.md`
- Verify: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`
- Verify: `F:\giteeProject\warframe\md\rebuilt\09-personal-agent-foundation.md`
- Verify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`
- Verify: `F:\giteeProject\warframe\githubProduct\download_summary.json`

- [ ] **Step 1: JSON parse remains valid**

Run:

```powershell
Get-Content -Path 'githubProduct\download_summary.json' -Encoding UTF8 | ConvertFrom-Json | Out-Null
```

Expected: exit code 0.

- [ ] **Step 2: Markdown smoke read**

Run:

```powershell
Get-Content -Path 'githubProduct\personal_agent_warframe_migration_step34_multi_agent_role_architecture_decision_zh.md' -Encoding UTF8 -TotalCount 40
Get-Content -Path 'md\rebuilt\09-personal-agent-foundation.md' -Encoding UTF8 -Tail 35
Get-Content -Path 'md\rebuilt\10-learning-route-audit.md' -Encoding UTF8 -Tail 35
```

Expected: Chinese text is readable and includes Step 34.

- [ ] **Step 3: Diff whitespace check**

Run:

```powershell
git diff --check -- githubProduct/personal_agent_warframe_migration_step34_multi_agent_role_architecture_decision_zh.md githubProduct/personal_agent_learning_route_ledger_zh.md md/rebuilt/09-personal-agent-foundation.md md/rebuilt/10-learning-route-audit.md docs/superpowers/plans/2026-05-27-multi-agent-role-architecture-decision.md
```

Expected: exit code 0, allowing only existing CRLF warnings if Git reports them.

---

## Completion Criteria

- Step 34 decision doc exists and answers whether to adopt explicit multi-agent roles.
- The three cloud Scout models are reflected as a model-routing constraint.
- Route ledger and `md/rebuilt` are synced.
- No external reference repo source is edited.
- No GitHub commit or push is performed.
