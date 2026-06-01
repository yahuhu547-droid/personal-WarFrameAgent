# Task Master AI + Claude Squad Sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up a runnable, isolated Task Master AI + Claude Squad trial under `F:\giteeProject\warframe\githubProduct` without modifying the current `warframe` business code or Claude/task configuration.

**Architecture:** The trial uses `githubProduct` as the only download, dependency, cache, and sandbox root. Task Master AI is installed project-locally inside `agent-sandbox/.tools`, wrapped by a sandbox-local runner, and used against a small PRD file. Claude Squad is cloned and inspected, then built or smoke-tested only if local prerequisites are available without global installs.

**Tech Stack:** Git, Node.js/npm, Task Master AI, Claude Code CLI, Claude Squad, optional Go and tmux prerequisites.

---

## File Structure

Create or use these paths only:

- Create directory: `F:\giteeProject\warframe\githubProduct\task-master-ai\`
  - Shallow clone of `https://github.com/eyaltoledano/claude-task-master.git`.
- Create directory: `F:\giteeProject\warframe\githubProduct\claude-squad\`
  - Shallow clone of `https://github.com/smtg-ai/claude-squad.git`.
- Create directory: `F:\giteeProject\warframe\githubProduct\agent-sandbox\`
  - Trial workspace. All Task Master trial files live here.
- Create directory: `F:\giteeProject\warframe\githubProduct\agent-sandbox\.tools\task-master\`
  - Local npm prefix for Task Master AI.
- Create file: `F:\giteeProject\warframe\githubProduct\agent-sandbox\trial-prd.md`
  - Small PRD used for Task Master trial task generation.
- Create file: `F:\giteeProject\warframe\githubProduct\agent-sandbox\run-task-master.sh`
  - Wrapper that runs the locally installed Task Master AI binary and keeps npm cache on F drive.
- Create file: `F:\giteeProject\warframe\githubProduct\agent-sandbox\setup-report.md`
  - Human-readable record of what worked, what failed, and any blockers.
- Create directory: `F:\giteeProject\warframe\githubProduct\agent-sandbox\bin\`
  - Optional local build output for Claude Squad if prerequisites exist.
- Create directories under `F:\giteeProject\warframe\githubProduct\caches\`: `npm`, `pip`, `go`, `tmp`.

Do not modify:

- `F:\giteeProject\warframe\warframe_agent\`
- `F:\giteeProject\warframe\tests\`
- `F:\giteeProject\warframe\.claude\`
- Existing Claude Code project settings
- Existing Task Master project files, if any appear outside `githubProduct\agent-sandbox`

Do not run `git commit` during implementation. The repository is already dirty, and the sandbox contains external repositories that should not be committed with this work.

---

### Task 1: Prepare sandbox directories and baseline files

**Files:**
- Create: `F:\giteeProject\warframe\githubProduct\agent-sandbox\trial-prd.md`
- Create: `F:\giteeProject\warframe\githubProduct\agent-sandbox\setup-report.md`
- Create directories listed in File Structure

- [ ] **Step 1: Verify baseline tools**

Run:

```bash
git --version && node --version && npm --version && claude --version
```

Expected:

- `git --version` prints an installed Git version.
- `node --version` prints an installed Node.js version.
- `npm --version` prints an installed npm version.
- `claude --version` prints an installed Claude Code version.

If this command fails before printing all four tools, stop and report the missing tool.

- [ ] **Step 2: Check optional Claude Squad prerequisites**

Run:

```bash
go version; tmux -V
```

Expected:

- If both commands print versions, Claude Squad can probably be built and run locally.
- If either command is missing, continue with Task Master setup and clone Claude Squad, but treat Claude Squad runtime verification as blocked until the user chooses a Go/tmux installation strategy.

- [ ] **Step 3: Create sandbox and cache directories**

Run:

```bash
mkdir -p "F:/giteeProject/warframe/githubProduct/task-master-ai" "F:/giteeProject/warframe/githubProduct/claude-squad" "F:/giteeProject/warframe/githubProduct/agent-sandbox/.tools/task-master" "F:/giteeProject/warframe/githubProduct/agent-sandbox/bin" "F:/giteeProject/warframe/githubProduct/caches/npm" "F:/giteeProject/warframe/githubProduct/caches/pip" "F:/giteeProject/warframe/githubProduct/caches/go" "F:/giteeProject/warframe/githubProduct/caches/tmp"
```

Expected: command exits successfully and creates only directories under `F:/giteeProject/warframe/githubProduct`.

- [ ] **Step 4: Write the trial PRD**

Create `F:\giteeProject\warframe\githubProduct\agent-sandbox\trial-prd.md` with exactly:

```markdown
# Trial PRD: Local Agent Sandbox

## Objective

Validate that Task Master AI can turn a small requirement into a task list for a local sandbox project.

## Requirements

1. Create a text-only hello command for a demo CLI.
2. The command should print `hello from agent sandbox`.
3. Add one test that verifies the command output.
4. Do not call external services from the demo CLI.

## Acceptance Criteria

- The task list includes implementation and verification work.
- The task list is small enough for one or two Claude Code sessions.
- No files outside `agent-sandbox` are required for the trial.
```

- [ ] **Step 5: Write the initial setup report**

Create `F:\giteeProject\warframe\githubProduct\agent-sandbox\setup-report.md` with exactly:

```markdown
# Task Master AI + Claude Squad Sandbox Report

## Root

`F:\giteeProject\warframe\githubProduct`

## Baseline

- Git: pending
- Node.js: pending
- npm: pending
- Claude Code: pending
- Go: pending
- tmux: pending

## Task Master AI

- Clone: pending
- Local install: pending
- CLI smoke test: pending
- Sandbox task workflow: pending

## Claude Squad

- Clone: pending
- Prerequisites: pending
- Build or install: pending
- CLI smoke test: pending

## Notes

No global installs, pushes, PRs, remote changes, or secrets are used in this sandbox trial.
```

---

### Task 2: Clone both upstream projects without overwriting existing checkouts

**Files:**
- Create or reuse: `F:\giteeProject\warframe\githubProduct\task-master-ai\`
- Create or reuse: `F:\giteeProject\warframe\githubProduct\claude-squad\`
- Modify: `F:\giteeProject\warframe\githubProduct\agent-sandbox\setup-report.md`

- [ ] **Step 1: Clone or reuse Task Master AI**

Run:

```bash
if [ -d "F:/giteeProject/warframe/githubProduct/task-master-ai/.git" ]; then git -C "F:/giteeProject/warframe/githubProduct/task-master-ai" status --short; else rmdir "F:/giteeProject/warframe/githubProduct/task-master-ai" 2>/dev/null || true; git clone --depth 1 https://github.com/eyaltoledano/claude-task-master.git "F:/giteeProject/warframe/githubProduct/task-master-ai"; fi
```

Expected:

- Existing checkout: prints its status and does not overwrite it.
- New checkout: creates `task-master-ai/.git` and exits successfully.

- [ ] **Step 2: Clone or reuse Claude Squad**

Run:

```bash
if [ -d "F:/giteeProject/warframe/githubProduct/claude-squad/.git" ]; then git -C "F:/giteeProject/warframe/githubProduct/claude-squad" status --short; else rmdir "F:/giteeProject/warframe/githubProduct/claude-squad" 2>/dev/null || true; git clone --depth 1 https://github.com/smtg-ai/claude-squad.git "F:/giteeProject/warframe/githubProduct/claude-squad"; fi
```

Expected:

- Existing checkout: prints its status and does not overwrite it.
- New checkout: creates `claude-squad/.git` and exits successfully.

- [ ] **Step 3: Record clone revisions**

Run:

```bash
git -C "F:/giteeProject/warframe/githubProduct/task-master-ai" rev-parse --short HEAD && git -C "F:/giteeProject/warframe/githubProduct/claude-squad" rev-parse --short HEAD
```

Expected: prints two short commit hashes.

Update `setup-report.md`:

```markdown
## Task Master AI

- Clone: complete, commit `<task-master-short-hash>`
- Local install: pending
- CLI smoke test: pending
- Sandbox task workflow: pending

## Claude Squad

- Clone: complete, commit `<claude-squad-short-hash>`
- Prerequisites: pending
- Build or install: pending
- CLI smoke test: pending
```

Replace the angle-bracket values with the actual short hashes printed by the command.

- [ ] **Step 4: Inspect upstream installation docs before installing**

Read these files if present:

- `F:\giteeProject\warframe\githubProduct\task-master-ai\README.md`
- `F:\giteeProject\warframe\githubProduct\task-master-ai\package.json`
- `F:\giteeProject\warframe\githubProduct\claude-squad\README.md`
- `F:\giteeProject\warframe\githubProduct\claude-squad\go.mod`

Expected:

- Task Master AI should expose an npm package or CLI entry point.
- Claude Squad should document whether Go, tmux, git worktrees, and Claude Code are required.

If the upstream docs require a global install, a shell profile edit, or writing secrets to files, do not do that step. Continue only with local alternatives or stop and ask.

---

### Task 3: Install Task Master AI locally under the sandbox

**Files:**
- Create/modify: `F:\giteeProject\warframe\githubProduct\agent-sandbox\.tools\task-master\package.json`
- Create/modify: `F:\giteeProject\warframe\githubProduct\agent-sandbox\.tools\task-master\node_modules\`
- Create: `F:\giteeProject\warframe\githubProduct\agent-sandbox\run-task-master.sh`
- Modify: `F:\giteeProject\warframe\githubProduct\agent-sandbox\setup-report.md`

- [ ] **Step 1: Verify npm will use the F-drive cache**

Run:

```bash
NPM_CONFIG_CACHE="F:/giteeProject/warframe/githubProduct/caches/npm" npm config get cache
```

Expected: output is `F:\giteeProject\warframe\githubProduct\caches\npm` or an equivalent normalized path on F drive.

- [ ] **Step 2: Inspect Task Master package metadata from npm**

Run:

```bash
NPM_CONFIG_CACHE="F:/giteeProject/warframe/githubProduct/caches/npm" npm view task-master-ai name version bin --json
```

Expected: JSON output includes `"name": "task-master-ai"` and a `bin` field.

If npm reports that `task-master-ai` does not exist, run this fallback:

```bash
NPM_CONFIG_CACHE="F:/giteeProject/warframe/githubProduct/caches/npm" npm view taskmaster-ai name version bin --json
```

If both package names fail, stop and report that the package name has changed upstream.

- [ ] **Step 3: Install the npm package into the sandbox-local prefix**

Run:

```bash
NPM_CONFIG_CACHE="F:/giteeProject/warframe/githubProduct/caches/npm" npm install --prefix "F:/giteeProject/warframe/githubProduct/agent-sandbox/.tools/task-master" task-master-ai
```

Expected:

- npm installs under `agent-sandbox/.tools/task-master/node_modules`.
- No `npm install -g` is used.

If Step 2 showed that only `taskmaster-ai` exists, use this command instead:

```bash
NPM_CONFIG_CACHE="F:/giteeProject/warframe/githubProduct/caches/npm" npm install --prefix "F:/giteeProject/warframe/githubProduct/agent-sandbox/.tools/task-master" taskmaster-ai
```

- [ ] **Step 4: Create the sandbox wrapper**

Create `F:\giteeProject\warframe\githubProduct\agent-sandbox\run-task-master.sh` with exactly:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="F:/giteeProject/warframe/githubProduct"
PREFIX="$ROOT/agent-sandbox/.tools/task-master"
export NPM_CONFIG_CACHE="$ROOT/caches/npm"
export TMPDIR="$ROOT/caches/tmp"

PKG="task-master-ai"
if [ ! -f "$PREFIX/node_modules/$PKG/package.json" ]; then
  PKG="taskmaster-ai"
fi
if [ ! -f "$PREFIX/node_modules/$PKG/package.json" ]; then
  echo "Task Master package is not installed under $PREFIX/node_modules" >&2
  exit 1
fi

BIN=$(node -e "const pkg=require(process.argv[1]); const b=pkg.bin; if (typeof b === 'string') { console.log(pkg.name); } else { console.log(Object.keys(b)[0]); }" "$PREFIX/node_modules/$PKG/package.json")
exec npm exec --prefix "$PREFIX" -- "$BIN" "$@"
```

- [ ] **Step 5: Smoke-test the wrapper**

Run:

```bash
bash "F:/giteeProject/warframe/githubProduct/agent-sandbox/run-task-master.sh" --help
```

Expected: Task Master AI help text prints successfully.

If help text fails because the package binary has changed, inspect `agent-sandbox/.tools/task-master/node_modules/*/package.json` and update only `run-task-master.sh` to select the correct binary. Do not install globally.

- [ ] **Step 6: Update the setup report**

Update `setup-report.md` Task Master section to:

```markdown
## Task Master AI

- Clone: complete, commit `<task-master-short-hash>`
- Local install: complete under `agent-sandbox\.tools\task-master`
- CLI smoke test: complete via `run-task-master.sh --help`
- Sandbox task workflow: pending
```

---

### Task 4: Run the Task Master sandbox workflow

**Files:**
- Modify/create within: `F:\giteeProject\warframe\githubProduct\agent-sandbox\`
- Modify: `F:\giteeProject\warframe\githubProduct\agent-sandbox\setup-report.md`

- [ ] **Step 1: Check Task Master project initialization help**

Run:

```bash
bash "F:/giteeProject/warframe/githubProduct/agent-sandbox/run-task-master.sh" init --help
```

Expected: help text for initialization prints.

If the command reports that `init` is not a valid command, run:

```bash
bash "F:/giteeProject/warframe/githubProduct/agent-sandbox/run-task-master.sh" --help
```

Then use the initialization command shown by the installed CLI. Record the exact command in `setup-report.md` before running it.

- [ ] **Step 2: Initialize only inside agent-sandbox**

Run from the sandbox directory:

```bash
cd "F:/giteeProject/warframe/githubProduct/agent-sandbox" && bash "./run-task-master.sh" init --yes
```

Expected:

- Task Master creates its own project files inside `agent-sandbox`.
- No files are created under `F:/giteeProject/warframe/.taskmaster`, `F:/giteeProject/warframe/.claude`, or business-code directories.

If the CLI does not support `--yes` and prompts interactively, stop and ask the user whether to proceed interactively. Do not guess prompt answers.

- [ ] **Step 3: Try PRD parsing with the trial PRD**

Run:

```bash
cd "F:/giteeProject/warframe/githubProduct/agent-sandbox" && bash "./run-task-master.sh" parse-prd "trial-prd.md" --num-tasks=4
```

Expected if an AI provider is already configured through environment variables: Task Master generates a small task list inside `agent-sandbox`.

Expected if no AI provider is configured: Task Master prints a missing-provider or missing-key error. This is an acceptable blocker; do not write API keys to files. Ask the user whether they want to provide an environment variable for this shell session or accept a CLI-only smoke test.

If `parse-prd` is not a valid command, run:

```bash
cd "F:/giteeProject/warframe/githubProduct/agent-sandbox" && bash "./run-task-master.sh" --help
```

Then use the PRD parsing command shown by the installed CLI. Record the exact command in `setup-report.md`.

- [ ] **Step 4: List tasks or record provider blocker**

If Step 3 generated tasks, run:

```bash
cd "F:/giteeProject/warframe/githubProduct/agent-sandbox" && bash "./run-task-master.sh" list
```

Expected: prints the generated task list.

If Step 3 was blocked by missing AI-provider credentials, update `setup-report.md` with:

```markdown
- Sandbox task workflow: blocked because Task Master AI requires an AI provider credential for PRD parsing; no secrets were written to disk.
```

- [ ] **Step 5: Update the setup report for Task Master**

If the workflow completed, update `setup-report.md` with:

```markdown
- Sandbox task workflow: complete; `trial-prd.md` was parsed and tasks were listed inside `agent-sandbox`.
```

If the workflow was blocked, keep the blocker text from Step 4 and continue to Claude Squad prerequisite verification.

---

### Task 5: Verify Claude Squad prerequisites and smoke-test if possible

**Files:**
- Create optional: `F:\giteeProject\warframe\githubProduct\agent-sandbox\bin\claude-squad.exe`
- Modify: `F:\giteeProject\warframe\githubProduct\agent-sandbox\setup-report.md`

- [ ] **Step 1: Re-check prerequisites**

Run:

```bash
git --version && claude --version && go version && tmux -V
```

Expected for full Claude Squad run:

- Git installed.
- Claude Code installed.
- Go installed.
- tmux installed.

If Go or tmux is missing, do not install it globally. Update `setup-report.md`:

```markdown
## Claude Squad

- Clone: complete, commit `<claude-squad-short-hash>`
- Prerequisites: blocked; Go and/or tmux are missing in the current shell
- Build or install: not attempted
- CLI smoke test: not attempted
```

Then stop and ask the user to choose one of these explicit next steps:

1. Install portable Go and a tmux-compatible environment under `githubProduct` if feasible.
2. Use WSL for Claude Squad while keeping project/cache directories on F drive.
3. Defer Claude Squad and use Claude Code native worktrees/subagents for the first multi-agent trial.

- [ ] **Step 2: Configure Go caches if prerequisites exist**

Run only if `go version` and `tmux -V` both succeeded:

```bash
GOMODCACHE="F:/giteeProject/warframe/githubProduct/caches/go/pkg/mod" GOCACHE="F:/giteeProject/warframe/githubProduct/caches/go/build" GOTMPDIR="F:/giteeProject/warframe/githubProduct/caches/tmp" go env GOMODCACHE GOCACHE GOTMPDIR
```

Expected: all printed paths are under `F:/giteeProject/warframe/githubProduct/caches`.

- [ ] **Step 3: Build Claude Squad locally if prerequisites exist**

Run only if Step 2 succeeded:

```bash
cd "F:/giteeProject/warframe/githubProduct/claude-squad" && if [ -d "cmd/claude-squad" ]; then PKG="./cmd/claude-squad"; else PKG="."; fi && GOMODCACHE="F:/giteeProject/warframe/githubProduct/caches/go/pkg/mod" GOCACHE="F:/giteeProject/warframe/githubProduct/caches/go/build" GOTMPDIR="F:/giteeProject/warframe/githubProduct/caches/tmp" go build -o "F:/giteeProject/warframe/githubProduct/agent-sandbox/bin/claude-squad.exe" "$PKG"
```

Expected: creates `agent-sandbox/bin/claude-squad.exe` or fails with a clear upstream build error.

If the upstream README documents a different local build command, use the README command only if it keeps caches and build output under `githubProduct`.

- [ ] **Step 4: Smoke-test Claude Squad CLI if built**

Run only if Step 3 produced the binary:

```bash
"F:/giteeProject/warframe/githubProduct/agent-sandbox/bin/claude-squad.exe" --help
```

Expected: Claude Squad help text prints.

Do not start an interactive multi-agent session during this task unless the user explicitly approves it after seeing the smoke-test result.

- [ ] **Step 5: Update the setup report for Claude Squad**

If built and smoke-tested, update `setup-report.md` with:

```markdown
## Claude Squad

- Clone: complete, commit `<claude-squad-short-hash>`
- Prerequisites: complete
- Build or install: complete under `agent-sandbox\bin`
- CLI smoke test: complete via `claude-squad.exe --help`
```

If blocked, keep the blocker text from Step 1.

---

### Task 6: Verify isolation and summarize results

**Files:**
- Modify: `F:\giteeProject\warframe\githubProduct\agent-sandbox\setup-report.md`

- [ ] **Step 1: Check sandbox-created paths**

Run:

```bash
python - <<'PY'
from pathlib import Path
root = Path('F:/giteeProject/warframe/githubProduct')
for rel in ['task-master-ai', 'claude-squad', 'agent-sandbox', 'caches/npm', 'caches/pip', 'caches/go', 'caches/tmp']:
    path = root / rel
    print(f'{rel}: {"exists" if path.exists() else "missing"}')
PY
```

Expected: each listed path prints `exists`.

- [ ] **Step 2: Check that current project config was not modified by setup**

Run:

```bash
git status --short -- .claude warframe_agent tests md data requirements.txt docs/superpowers/specs/2026-05-21-task-master-claude-squad-sandbox-design.md docs/superpowers/plans/2026-05-21-task-master-claude-squad-sandbox.md
```

Expected:

- The new design and plan docs may appear as untracked or modified.
- Pre-existing dirty files may still appear.
- No new Task Master or Claude Squad configuration should appear outside `githubProduct/agent-sandbox`.

If new files appear under `.claude` or project root task directories because of the setup, stop and report them before changing anything.

- [ ] **Step 3: Finalize setup-report status**

Append this section to `F:\giteeProject\warframe\githubProduct\agent-sandbox\setup-report.md`:

```markdown
## Isolation Check

- Sandbox root exists under `githubProduct`.
- npm cache is configured under `githubProduct\caches\npm` for Task Master commands.
- No global install was intentionally performed.
- No secrets were written to disk.
- Current `warframe` business code and Claude/task configuration were not intentionally modified.
```

- [ ] **Step 4: Report next action**

Report one of these outcomes to the user:

```text
Task Master AI is locally installed and smoke-tested. Claude Squad is built/smoke-tested. Next, we can run an approved interactive multi-agent trial.
```

or:

```text
Task Master AI is locally installed and smoke-tested. Claude Squad is cloned but blocked by missing Go/tmux. Next, choose portable Go/tmux, WSL, or Claude Code native worktrees/subagents.
```

or:

```text
Setup is blocked earlier: <specific command> failed with <specific error>. No global installs or project config changes were made.
```

---

## Self-Review

Spec coverage:

- Sandbox under `F:\giteeProject\warframe\githubProduct`: covered by Tasks 1, 2, and 6.
- Task Master AI download/local install/trial task workflow: covered by Tasks 2, 3, and 4.
- Claude Squad download/build or prerequisite blocker: covered by Tasks 2 and 5.
- Cache redirection away from C drive: covered by Tasks 1, 3, and 5.
- No global installs, no secrets, no project config edits: covered by File Structure, Tasks 3, 4, 5, and 6.

Placeholder scan: no TBD/TODO/fill-later items remain. Conditional branches have explicit commands and stop conditions.

Type/name consistency: all paths use the same `F:\giteeProject\warframe\githubProduct` root; shell commands use the Bash-compatible `F:/giteeProject/warframe/githubProduct` form.
