# Personal Agent Route Ledger Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the personal Agent learning route after context compaction by creating one durable ledger that maps downloaded projects, learned ideas, Warframe migrations, remaining gaps, safety boundaries, and next tasks.

**Architecture:** This is a documentation and metadata repair task, not a product-code task. Keep the current `githubProduct/download_summary.json` object structure, add personal-agent-specific inventory fields, create a dedicated Markdown route ledger, and append a concise sync note to `md/rebuilt/10-learning-route-audit.md`.

**Tech Stack:** Markdown, JSON, PowerShell, `rg`, project-local documentation under `githubProduct`, `docs/superpowers/plans`, and `md/rebuilt`.

---

## Route Assignment

来源项目：CowAgent、OpenManus、LangManus、OpenHuman、EchoBot、Open-AutoGLM、OpenClaw、Suna/Kortix。

借鉴点：个人 Agent 项目下载状态、学习证据、已迁移能力、未覆盖主题、下一步学习顺序。

Warframe 映射：把外部项目学习路线映射到本项目 Step 1-33 的 Agent Trace、AgentPlan、记忆画像、自然语言确认、推送质量反馈等已完成工作，并标出未覆盖的多 Agent、长期运行、语音陪伴、GUI 自动化主题。

安全边界：不运行外部项目，不安装新依赖，不启动服务，不修改 8 个上游参考项目源码；只更新本项目文档和 JSON 摘要。

验证方式：`Get-Content ... | ConvertFrom-Json` 验证 JSON；`git diff --check` 验证新增/修改文档无明显空白错误；抽读 Markdown 头部确认 UTF-8 中文可读。

---

## Files

- Modify: `F:\giteeProject\warframe\githubProduct\download_summary.json`
- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`
- Modify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`
- Create: `F:\giteeProject\warframe\docs\superpowers\plans\2026-05-27-personal-agent-route-ledger-repair.md`

Do not edit:

- `F:\giteeProject\warframe\githubProduct\CowAgent`
- `F:\giteeProject\warframe\githubProduct\OpenManus`
- `F:\giteeProject\warframe\githubProduct\langmanus`
- `F:\giteeProject\warframe\githubProduct\OpenHuman`
- `F:\giteeProject\warframe\githubProduct\EchoBot`
- `F:\giteeProject\warframe\githubProduct\Open-AutoGLM`
- `F:\giteeProject\warframe\githubProduct\OpenClaw`
- `F:\giteeProject\warframe\githubProduct\suna`

---

### Task 1: Evidence Inventory

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\personal_agent_projects_study_notes.md`
- Read: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_execution_status_zh.md`
- Read: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_run_report_zh.md`
- Read: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_checklist_next_zh.md`
- Read: `F:\giteeProject\warframe\md\rebuilt\09-personal-agent-foundation.md`
- Read: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`

- [ ] **Step 1: List downloaded personal Agent directories**

Run:

```powershell
Get-ChildItem -Path 'githubProduct' -Directory | Select-Object -ExpandProperty Name
```

Expected: output includes `CowAgent`, `OpenManus`, `langmanus`, `OpenHuman`, `EchoBot`, `Open-AutoGLM`, `OpenClaw`, and `suna`.

- [ ] **Step 2: Confirm existing study evidence**

Run:

```powershell
rg -n "OpenManus|CowAgent|EchoBot|OpenClaw|OpenHuman|LangManus|Open-AutoGLM|Suna" githubProduct\personal_agent_projects_study_notes.md githubProduct\personal_agent_learning_execution_status_zh.md githubProduct\personal_agent_learning_run_report_zh.md githubProduct\personal_agent_learning_checklist_next_zh.md
```

Expected: output shows downloaded repositories, OpenManus local smoke result, and next reading order.

- [ ] **Step 3: Confirm migration evidence**

Run:

```powershell
rg -n "Agent Trace|AgentPlan|自然语言|推送质量|记忆|复盘|runtime|ToolRegistry" md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md
```

Expected: output shows Step 1-33 migration themes and the route-audit conclusion.

### Task 2: Download Summary Repair

**Files:**
- Modify: `F:\giteeProject\warframe\githubProduct\download_summary.json`

- [ ] **Step 1: Preserve current JSON object shape**

Keep top-level keys:

```json
{
  "updated_at": "2026-05-27",
  "projects": [],
  "previous_references": [],
  "personal_agent_projects": [],
  "route_repair": {}
}
```

Do not convert the file back to the old top-level array format.

- [ ] **Step 2: Add personal_agent_projects**

Add one object for each personal Agent reference with fields:

```json
{
  "name": "OpenManus",
  "url": "https://github.com/FoundationAgents/OpenManus",
  "path": "githubProduct/OpenManus",
  "status": "downloaded",
  "learning_status": "smoke_import_passed",
  "primary_learning_focus": "minimal ReAct and tool-calling loop",
  "warframe_mapping": "Agent Trace, AgentRun lifecycle, AgentPlan snapshot, tool registry safety boundaries",
  "remaining_gap": "browser/GUI automation remains verification-only in Warframe Agent"
}
```

Use analogous entries for CowAgent, LangManus, OpenHuman, EchoBot, Open-AutoGLM, OpenClaw, and Suna / Kortix.

- [ ] **Step 3: Add route_repair metadata**

Add:

```json
{
  "route_repair": {
    "reason": "Context compaction audit found download_summary was older than the personal Agent checklist and did not represent the later route.",
    "ledger": "githubProduct/personal_agent_learning_route_ledger_zh.md",
    "rebuilt_sync": "md/rebuilt/10-learning-route-audit.md",
    "next_recommended_task": "multi-agent role architecture decision based on LangManus, OpenManus, and Suna"
  }
}
```

- [ ] **Step 4: Validate JSON**

Run:

```powershell
Get-Content -Path 'githubProduct\download_summary.json' -Encoding UTF8 | ConvertFrom-Json | Out-Null
```

Expected: exit code 0 with no parser error.

### Task 3: Route Ledger Document

**Files:**
- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`

- [ ] **Step 1: Create route ledger**

The document must include:

- current route conclusion
- project inventory table
- original-theme coverage table
- completed migration map
- remaining learning queue
- next-task selection rule
- compaction guardrail

- [ ] **Step 2: Include the fixed route format**

Every next learning task should use:

```markdown
来源项目 / 借鉴点 / Warframe 映射 / 安全边界 / 验证方式
```

- [ ] **Step 3: Set next recommended task**

Set the next recommended task to:

```markdown
LangManus / OpenManus / Suna 多 Agent 角色架构决策：判断 Warframe Agent 是否需要显式 coordinator/planner/supervisor/reporter 分层，或者继续保持单 Agent + 工具路由。
```

### Task 4: Rebuilt Sync

**Files:**
- Modify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`

- [ ] **Step 1: Append sync note**

Append a section named:

```markdown
## 2026-05-27 追加：路线账本修复
```

It must point to:

- `githubProduct/personal_agent_learning_route_ledger_zh.md`
- updated `githubProduct/download_summary.json`
- the next recommended multi-agent architecture decision task

- [ ] **Step 2: Keep the note concise**

Do not duplicate the whole route ledger. The rebuilt note should only record what changed and why.

### Task 5: Final Verification

**Files:**
- Verify: `F:\giteeProject\warframe\githubProduct\download_summary.json`
- Verify: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_route_ledger_zh.md`
- Verify: `F:\giteeProject\warframe\md\rebuilt\10-learning-route-audit.md`

- [ ] **Step 1: JSON parse**

Run:

```powershell
Get-Content -Path 'githubProduct\download_summary.json' -Encoding UTF8 | ConvertFrom-Json | Out-Null
```

Expected: exit code 0.

- [ ] **Step 2: Markdown smoke read**

Run:

```powershell
Get-Content -Path 'githubProduct\personal_agent_learning_route_ledger_zh.md' -Encoding UTF8 -TotalCount 30
Get-Content -Path 'md\rebuilt\10-learning-route-audit.md' -Encoding UTF8 -Tail 30
```

Expected: Chinese text is readable and includes the route ledger repair note.

- [ ] **Step 3: Diff whitespace check**

Run:

```powershell
git diff --check -- githubProduct/download_summary.json githubProduct/personal_agent_learning_route_ledger_zh.md md/rebuilt/10-learning-route-audit.md docs/superpowers/plans/2026-05-27-personal-agent-route-ledger-repair.md
```

Expected: exit code 0, allowing only existing Git CRLF warnings if they appear.

---

## Completion Criteria

- `download_summary.json` represents both the early Warframe/video references and the later personal Agent project batch.
- `personal_agent_learning_route_ledger_zh.md` can be used after context compaction to select the next learning task without relying on conversation memory.
- `md/rebuilt/10-learning-route-audit.md` is synced with the route repair outcome.
- No upstream reference project source is edited.
- No GitHub commit or push is performed.
