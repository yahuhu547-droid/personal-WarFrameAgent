# Personal Agent Learning Phase Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收束 Step 34-39 后的个人 Agent 学习借鉴路线，形成下一阶段路线图，避免上下文压缩后继续在已覆盖主题里反复绕圈。

**Architecture:** 本步只更新学习账本、总复盘文档和跨会话说明，不新增运行时代码、不新增 API、不改 Agent 执行行为。Step 39 的 Web API 可写环境补跑作为验证残留单独记录，不阻塞路线复盘。

**Tech Stack:** Markdown, JSON metadata audit, PowerShell read checks, existing pytest smoke checks for Step 39 modules.

---

## Completion Definition

- 用户可见结果：`githubProduct` 中新增 Step 40 总复盘文档，明确 Step 34-39 覆盖了哪些外部个人 Agent 借鉴主题，以及下一阶段优先级。
- 数据流：只读审计本地文档和现有代码，不读取 `.env`，不运行下载，不启动外部服务。
- 验证手段：Markdown 文档存在；路线账本、`md/rebuilt/10-learning-route-audit.md` 和 `AGENTS.md` 均同步 Step 40；目标 Step 39 单元/策略测试继续通过；`git diff --check` 对本步文件通过。
- 不做内容：不补跑被用户中断的提权 Web API 测试，不改业务逻辑，不新增 runtime executor，不推送 GitHub。

## File Map

- Create: `githubProduct/personal_agent_warframe_migration_step40_learning_phase_review_zh.md`
  - Step 34-39 总复盘、覆盖矩阵、残留风险、下一阶段候选任务排序。
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
  - 追加 Step 40，更新剩余学习队列为“下一阶段候选分支”。
- Modify: `md/rebuilt/10-learning-route-audit.md`
  - 同步路线判断，标记主线学习队列基本完成。
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
  - 追加 Step 40 完成记录。
- Modify: `AGENTS.md`
  - 更新当前进度、Step 40 验证摘要、下一步计划。
- Modify: `githubProduct/download_summary.json`
  - 仅在 `personal_agent_projects` 或 `route_repair` 已存在时补充 phase review 时间戳和摘要，不重写下载库存。

### Task 1: Route Phase Review Document

**Files:**
- Create: `githubProduct/personal_agent_warframe_migration_step40_learning_phase_review_zh.md`

- [x] **Step 1: Write the phase review document**

The document must contain:

```markdown
# Step 40：个人 Agent 学习阶段总复盘

## 覆盖矩阵
| 原始主题 | 当前状态 | 代表 Step | 结论 |

## Step 34-39 复盘
...

## 验证残留
...

## 下一阶段候选任务
...
```

- [x] **Step 2: Include safety boundaries**

The document must explicitly say:

- No GitHub push.
- No new downloads.
- No voice / GUI / shell / arbitrary scheduler executor.
- All cloud models still route through `ModelOrchestrator` / `llm.py`.
- Step 39 Web API residual is environment-bound and does not imply the safety policy code failed.

### Task 2: Ledger And Rebuilt Docs Sync

**Files:**
- Modify: `githubProduct/personal_agent_learning_route_ledger_zh.md`
- Modify: `md/rebuilt/10-learning-route-audit.md`
- Modify: `md/rebuilt/09-personal-agent-foundation.md`
- Modify: `githubProduct/download_summary.json`

- [x] **Step 1: Append Step 40 to route ledger**

Add a dated section:

```markdown
## 2026-05-29 Step 40：个人 Agent 学习阶段总复盘
```

It must state that the original main learning queue is basically covered, while several optional branches remain.

- [x] **Step 2: Convert remaining queue language**

Update the queue wording from “剩余学习队列” to “下一阶段候选分支” where appropriate, without deleting the historical queue entries.

- [x] **Step 3: Sync rebuilt audit and foundation docs**

Append a Step 40 section to both rebuilt docs with the same conclusion and residual validation note.

- [x] **Step 4: Update download summary metadata conservatively**

Only add a compact `phase_review` block under existing `route_repair` if that key exists; do not rewrite project inventory or remove old entries.

### Task 3: AGENTS.md Cross-Session State

**Files:**
- Modify: `AGENTS.md`

- [x] **Step 1: Add Step 40 progress row**

Add:

```markdown
| 2026-05-29 | Step 40 个人 Agent 学习阶段总复盘 | 100% | 已完成 | 已收束 Step 34-39 覆盖矩阵和下一阶段候选分支。 |
```

- [x] **Step 2: Preserve Step 39 residual**

Keep Step 39 at 90% unless the Web API target test is actually rerun in a writable environment and passes.

- [x] **Step 3: Update next plan**

Next plan should prioritize either:

1. Step 35 controlled execution confirmation chain.
2. A new learning batch only after explicit selection.
3. Step 39 Web API writable-environment verification when available.

### Task 4: Verification

**Files:**
- All files touched above.

- [x] **Step 1: Run Step 39 focused tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_companion_experience.py -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
```

Expected: both pass.

- [x] **Step 2: Validate JSON metadata**

```powershell
.\.venv\Scripts\python.exe -B -c "import json, pathlib; json.loads(pathlib.Path('githubProduct/download_summary.json').read_text(encoding='utf-8')); print('JSON OK')"
```

Expected: `JSON OK`.

- [x] **Step 3: Run diff whitespace check**

```powershell
git diff --check -- AGENTS.md githubProduct/personal_agent_learning_route_ledger_zh.md githubProduct/personal_agent_warframe_migration_step40_learning_phase_review_zh.md githubProduct/download_summary.json md/rebuilt/09-personal-agent-foundation.md md/rebuilt/10-learning-route-audit.md docs/superpowers/plans/2026-05-29-personal-agent-learning-phase-review.md
```

Expected: exit code 0, allowing existing line-ending warnings.
