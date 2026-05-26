# Personal Agent Projects Study Notes

Date: 2026-05-25

Source method: Bilibili search via Playwright plus GitHub repository download.

## Downloaded Repositories

| Project | Local path | GitHub | Commit | Why keep it |
| --- | --- | --- | --- | --- |
| OpenClaw | `OpenClaw` | https://github.com/openclaw/openclaw | `5d018034` | Personal always-on assistant, channels, skills, memory, voice, canvas, many extensions. |
| OpenHuman | `OpenHuman` | https://github.com/tinyhumansai/openhuman | `d997394` | Desktop personal AI with local-first memory, Obsidian-style wiki, integrations, model routing, voice. |
| OpenManus | `OpenManus` | https://github.com/FoundationAgents/OpenManus | `52a13f2` | Compact general agent implementation with planning, browser automation, file/tools workflow. |
| Suna / Kortix | `suna` | https://github.com/kortix-ai/suna | `5f725f7` | Full-stack generalist agent runtime: sandbox, persistent machine, skills, triggers, multi-channel app surface. |
| LangManus | `langmanus` | https://github.com/Darwin-lfl/langmanus | `a69eabf` | Layered multi-agent research workflow: coordinator, planner, supervisor, researcher, coder, browser, reporter. |
| Open-AutoGLM | `Open-AutoGLM` | https://github.com/zai-org/Open-AutoGLM | `86f5538` | Phone / GUI agent using visual-language perception plus ADB/HDC action execution and human takeover. |
| EchoBot | `EchoBot` | https://github.com/KdaiP/EchoBot | `08e97a4` | Persona assistant with Live2D, voice, Decision-Roleplay-Agent split, skills, long-term memory. |
| CowAgent | `CowAgent` | https://github.com/zhayujie/CowAgent | `2e6d9e0` | Chinese-friendly agent harness with channels, planning, memory, knowledge, skills, MCP, browser and scheduler tools. |

## Bilibili Search Clues

Playwright search query: `个人 Agent 项目 Github`.

Useful result patterns found on Bilibili:

- "github爆火！12个agent实战项目！从agent构建到AI数字人项目实战..."
- "【开源】AI视频剪辑 理解Agent项目-FireRed-OpenStoryline 整合包"
- "本地纯视觉自动化 Mano-P #视觉自动化 #ManoP #Mac #Github #AI工具"
- "Github一周热点115期：桌面AI超级助理、编程Agent的知识图谱..."
- "Ai Agent 项目 demo演示"

Sub-agent candidate sweep also matched Bilibili / Chinese community mentions for OpenClaw, OpenHuman, OpenManus, Suna, LangManus, Open-AutoGLM, EchoBot, ChatDev, MetaGPT, BabyAGI, XAgent, and CowAgent. This download batch focused on projects that are more directly useful for a personal agent rather than broad enterprise frameworks.

## What To Learn

### 1. Personal Agent Product Shape

Study OpenClaw, OpenHuman, EchoBot, and CowAgent first.

- How the assistant is exposed through channels instead of only a chat UI.
- How onboarding and one-line installers reduce setup friction.
- How personality / companion UX is separated from background task execution.
- How local-first state, logs, files, memory, and settings are organized.

### 2. Agent Harness Architecture

Study CowAgent, OpenClaw, OpenManus, and Suna.

- Message input -> planner -> tools/skills -> memory -> response pipeline.
- Tool registry and permission boundaries.
- Browser, terminal, file, scheduler, web search, and MCP tool abstraction.
- How to make skills installable and composable.

### 3. Memory And Knowledge

Study OpenHuman and CowAgent.

- Long-term memory layers: short context, daily summaries, core memory.
- Markdown / Obsidian-style knowledge base as an inspectable memory backend.
- Hybrid keyword + vector retrieval.
- Periodic ingestion from connectors and automatic distillation.

### 4. Multi-Agent Workflow

Study LangManus, OpenManus, and Suna.

- Role decomposition: coordinator, planner, supervisor, researcher, coder, browser, reporter.
- How plans are represented and updated during execution.
- How final reports are generated from tool traces.
- Where multi-agent systems help and where a single well-tooled agent is simpler.

### 5. GUI / Device Automation

Study Open-AutoGLM and OpenManus.

- Visual-language screen perception.
- ADB/HDC device control loop.
- Sensitive-action confirmation and human takeover.
- Browser automation setup and fallback handling.

### 6. Voice And Embodied UX

Study EchoBot, OpenHuman, and OpenClaw.

- STT/TTS integration points.
- Real-time conversation state.
- Separating fast roleplay response from slower background agent tasks.
- Live2D / mascot / channel-specific presentation layer.

### 7. Deployment And Operations

Study Suna, CowAgent, OpenClaw, and OpenHuman.

- Docker compose and local/server deployment split.
- CLI service management commands.
- Environment configuration and model-provider routing.
- Persistent sandbox / workspace design for long-running agents.

## Suggested Reading Order

1. `CowAgent`: best Chinese-friendly full-stack reference for your own assistant.
2. `OpenManus`: smallest path to understand general task agent basics.
3. `LangManus`: clean multi-agent role workflow.
4. `OpenHuman`: memory and personal data ingestion.
5. `EchoBot`: personality + async agent separation.
6. `Open-AutoGLM`: phone / GUI automation.
7. `OpenClaw`: rich channel and extension ecosystem.
8. `suna`: heavier but valuable for sandbox, 24/7 runtime, and full-stack product structure.
