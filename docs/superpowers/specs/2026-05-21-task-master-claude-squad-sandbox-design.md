# Task Master AI + Claude Squad Sandbox Design

## Goal

Validate a local, reversible workflow for using Task Master AI to produce and maintain task lists, then using Claude Squad to manage multiple Claude Code agent sessions for execution. The trial must not modify the current `warframe` repository's business code or Claude/task configuration.

Target workflow:

```text
User proposes task
→ Task Master AI generates and maintains a task list
→ User reviews and approves the plan
→ Claude Squad manages multiple Claude Code sessions
→ Sessions execute tasks in isolated workspaces
```

## Scope

This trial is limited to a runnable sandbox under `F:\giteeProject\warframe\githubProduct`.

Included:

- Download or clone Task Master AI into `githubProduct`.
- Download or clone Claude Squad into `githubProduct`.
- Create a sandbox directory for trial task generation and agent-session checks.
- Redirect package caches and temporary directories into `githubProduct` where the tools allow it.
- Verify basic commands and minimal task-list/session workflows.

Excluded:

- Modifying `warframe` business code.
- Adding Task Master project files to the current repository.
- Changing existing Claude Code project configuration.
- Installing global tools without explicit approval.
- Pushing code, creating PRs, or changing remotes.

## Directory Layout

Use this layout:

```text
F:\giteeProject\warframe\githubProduct\
  task-master-ai\
  claude-squad\
  agent-sandbox\
  caches\
    npm\
    pip\
    go\
    tmp\
```

`agent-sandbox` is the only directory used for trial task files. The current `warframe` repository remains untouched except for this design and the later implementation plan documentation.

## Installation Strategy

Prefer local or project-scoped installation.

- npm cache: `F:\giteeProject\warframe\githubProduct\caches\npm`
- pip cache: `F:\giteeProject\warframe\githubProduct\caches\pip`
- Go build/module cache: `F:\giteeProject\warframe\githubProduct\caches\go`
- temporary files: `F:\giteeProject\warframe\githubProduct\caches\tmp`

If a tool requires writing significant data to the user profile or C drive, stop and ask before continuing. API keys or tokens must not be written into the repository or sandbox files.

## Verification

The trial is successful when:

1. Task Master AI can be invoked from the sandbox or its local checkout.
2. Task Master AI can initialize or manage a small test task list in `agent-sandbox`.
3. Claude Squad can be built, installed locally, or invoked according to its supported workflow.
4. Claude Squad exposes a usable entry point for managing at least one Claude Code session.
5. No current `warframe` business code or Claude/task configuration is modified.

## Risk Controls

- Use isolated directories under `githubProduct`.
- Avoid global installs unless the user approves them separately.
- Avoid destructive git commands.
- Do not push, create PRs, or modify remotes.
- Do not store secrets in files.
- Report any unavoidable C-drive writes before proceeding.

## Next Step

After this design is accepted, create an implementation plan that checks prerequisites, prepares directories and cache variables, downloads the two projects, installs or builds them locally, and runs the minimal verification workflow.
