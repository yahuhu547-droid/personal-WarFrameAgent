# 个人 Agent 项目学习执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 8 个个人 Agent 参考项目完成第一轮可执行研读，产出可继续实操的学习路线、入口文件、运行命令和可借鉴设计点。

**Architecture:** 本计划采用“一个项目一个研读单元”的方式执行。每个子代理只读自己的项目目录，不安装依赖、不启动长期服务、不修改上游仓库；主代理负责整合结果到总报告。

**Tech Stack:** GitHub 参考仓库、Markdown 研读报告、PowerShell、本地文件系统、子代理并行研读。

---

## 输出文件

- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_run_report_zh.md`
- Read: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_checklist_zh.md`
- Read: `F:\giteeProject\warframe\githubProduct\personal_agent_projects_study_notes.md`

## 执行边界

- 不运行一键安装脚本，例如 `curl | bash`、`irm | iex`。
- 不安装依赖，除非用户之后明确要求跑通某个项目。
- 不启动长驻服务，除非用户之后明确要求。
- 允许执行只读命令：`rg --files`、`Get-Content`、`git remote get-url origin`、`git rev-parse --short HEAD`、读取 README / docs / config 示例。
- 允许生成本地 Markdown 学习报告。

## 子代理输出格式

每个项目研读结果必须包含：

1. 项目定位：一句话说明它属于哪类个人 Agent。
2. 关键入口：README、架构文档、主程序入口、配置文件、工具/技能/记忆相关目录。
3. 本地运行路径：README 中推荐的运行命令，标明是否需要外部服务、API key、Docker、移动设备或浏览器。
4. 可借鉴点：不少于 5 条，尽量落到模块或文件夹。
5. 风险/代价：依赖复杂度、平台限制、服务成本、权限风险。
6. 学习优先级：A / B / C，并说明原因。
7. 下一步建议：如果要真正跑起来，第一条最小安全命令是什么。

---

### Task 1: CowAgent 研读

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\CowAgent\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\CowAgent\docs\zh\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\CowAgent\pyproject.toml`
- Read: `F:\giteeProject\warframe\githubProduct\CowAgent\plugins\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\CowAgent\skills\README.md`

- [ ] **Step 1:** 定位 CowAgent 的主架构、核心目录和运行入口。
- [ ] **Step 2:** 找出 channel、agent、plugins、skills、memory、tools、scheduler、MCP 相关路径。
- [ ] **Step 3:** 摘出最适合本项目借鉴的“中文个人 Agent 主架构”设计点。
- [ ] **Step 4:** 给出最小安全运行前置条件，不实际安装。

### Task 2: OpenManus 研读

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\OpenManus\README_zh.md`
- Read: `F:\giteeProject\warframe\githubProduct\OpenManus\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\OpenManus\requirements.txt`
- Read: `F:\giteeProject\warframe\githubProduct\OpenManus\app`
- Read: `F:\giteeProject\warframe\githubProduct\OpenManus\config`

- [ ] **Step 1:** 定位 planner、agent、tool、browser、config 的实现路径。
- [ ] **Step 2:** 梳理从用户任务到工具执行的最小闭环。
- [ ] **Step 3:** 标出最适合先跑 demo 的命令和必要配置。
- [ ] **Step 4:** 对比 CowAgent，说明 OpenManus 更适合学习哪一层。

### Task 3: LangManus 研读

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\langmanus\README_zh.md`
- Read: `F:\giteeProject\warframe\githubProduct\langmanus\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\langmanus\pyproject.toml`
- Read: `F:\giteeProject\warframe\githubProduct\langmanus\src`

- [ ] **Step 1:** 定位 coordinator、planner、supervisor、researcher、coder、browser、reporter。
- [ ] **Step 2:** 梳理多 Agent 任务流和状态流。
- [ ] **Step 3:** 总结哪些角色可以迁移到自己的个人 Agent。
- [ ] **Step 4:** 判断它是否适合作为第一批运行项目。

### Task 4: OpenHuman 研读

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\OpenHuman\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\OpenHuman\README.zh-CN.md`
- Read: `F:\giteeProject\warframe\githubProduct\OpenHuman\src\openhuman\agent\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\OpenHuman\src\openhuman\memory\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\OpenHuman\src\openhuman\skills\README.md`

- [ ] **Step 1:** 定位桌面端、agent、memory、memory tree、memory store、skills、channels。
- [ ] **Step 2:** 梳理本地优先记忆和 Obsidian 风知识库设计。
- [ ] **Step 3:** 总结个人数据接入和长期记忆的可复用结构。
- [ ] **Step 4:** 标出运行限制，例如 Tauri、Rust、Node、托管服务、API key。

### Task 5: EchoBot 研读

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\EchoBot\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\EchoBot\README_EN.md`
- Read: `F:\giteeProject\warframe\githubProduct\EchoBot\requirements.txt`
- Read: `F:\giteeProject\warframe\githubProduct\EchoBot\echobot`

- [ ] **Step 1:** 定位 Decision / Roleplay / Agent 三层实现。
- [ ] **Step 2:** 找出 Live2D、语音、skills、memory、平台接入相关路径。
- [ ] **Step 3:** 总结人格化回复与后台任务异步协同方式。
- [ ] **Step 4:** 判断最小运行 demo 的依赖和风险。

### Task 6: Open-AutoGLM 研读

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\Open-AutoGLM\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\Open-AutoGLM\README_en.md`
- Read: `F:\giteeProject\warframe\githubProduct\Open-AutoGLM\README_coding_agent.md`

- [ ] **Step 1:** 定位 Phone Agent、模型、ADB/HDC、UI 自动化相关目录。
- [ ] **Step 2:** 梳理屏幕感知 -> 动作规划 -> 设备执行 -> 人类接管闭环。
- [ ] **Step 3:** 总结适合中文 App 自动化的设计点。
- [ ] **Step 4:** 标出运行它需要的硬件、模型和权限风险。

### Task 7: OpenClaw 研读

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\OpenClaw\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\OpenClaw\package.json`
- Read: `F:\giteeProject\warframe\githubProduct\OpenClaw\docker-compose.yml`
- Read: `F:\giteeProject\warframe\githubProduct\OpenClaw\extensions`
- Read: `F:\giteeProject\warframe\githubProduct\OpenClaw\skills`

- [ ] **Step 1:** 定位 gateway、extensions、skills、memory、channels、apps。
- [ ] **Step 2:** 梳理多渠道常驻个人助手的模块边界。
- [ ] **Step 3:** 总结插件和技能生态如何设计。
- [ ] **Step 4:** 判断它作为参考阅读和实际运行的成本差异。

### Task 8: Suna / Kortix 研读

**Files:**
- Read: `F:\giteeProject\warframe\githubProduct\suna\README.md`
- Read: `F:\giteeProject\warframe\githubProduct\suna\package.json`
- Read: `F:\giteeProject\warframe\githubProduct\suna\scripts\compose\docker-compose.yml`
- Read: `F:\giteeProject\warframe\githubProduct\suna\core`
- Read: `F:\giteeProject\warframe\githubProduct\suna\apps`

- [ ] **Step 1:** 定位 sandbox/runtime、apps、API、web、desktop、mobile、skills/triggers。
- [ ] **Step 2:** 梳理“持久沙盒电脑 + Agent”运行模型。
- [ ] **Step 3:** 总结 24/7 长期运行和触发器设计。
- [ ] **Step 4:** 判断它适合作为第几阶段运行项目。

---

## 整合任务

### Task 9: 生成总报告

**Files:**
- Create: `F:\giteeProject\warframe\githubProduct\personal_agent_learning_run_report_zh.md`

- [ ] **Step 1:** 汇总 8 个项目结果。
- [ ] **Step 2:** 输出优先级矩阵：先跑、先读、暂缓。
- [ ] **Step 3:** 输出自己的个人 Agent 建议蓝图：入口、规划、工具、记忆、技能、渠道、UI、运行环境。
- [ ] **Step 4:** 输出下一阶段可执行命令清单，所有命令必须标注风险等级。

## 完成标准

- `personal_agent_learning_run_report_zh.md` 存在。
- 报告包含 8 个项目的入口、运行前置、可借鉴点、风险。
- 报告包含学习优先级和下一阶段实操建议。
- 未修改 8 个上游项目源码。
