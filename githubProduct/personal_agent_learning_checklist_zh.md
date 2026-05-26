# 个人 Agent 项目准备学习清单

生成日期：2026-05-25

目标目录：`F:\giteeProject\warframe\githubProduct`

## 推荐学习顺序

| 顺序 | 项目 | 本地目录 | 学习重点 | 预期收获 |
| --- | --- | --- | --- | --- |
| 1 | CowAgent | `CowAgent` | 中文个人 Agent Harness、多渠道接入、规划、记忆、知识库、Skills、MCP、浏览器和定时任务工具 | 最适合作为个人助手主架构参考 |
| 2 | OpenManus | `OpenManus` | 通用任务 Agent 的最小闭环：规划、工具调用、浏览器自动化、文件操作 | 快速理解 Agent 基础执行链路 |
| 3 | LangManus | `langmanus` | Coordinator、Planner、Supervisor、Researcher、Coder、Browser、Reporter 多角色协作 | 学习深度研究和报告生成型 Agent |
| 4 | OpenHuman | `OpenHuman` | 本地优先记忆、Obsidian 风格知识库、个人数据连接器、模型路由、语音能力 | 学习个人数据如何沉淀为长期上下文 |
| 5 | EchoBot | `EchoBot` | Decision / Roleplay / Agent 三层拆分、Live2D、语音、长期记忆、异步任务 | 学习人格化助手如何不牺牲生产力任务 |
| 6 | Open-AutoGLM | `Open-AutoGLM` | 手机 / GUI Agent、视觉语言模型、ADB/HDC 操作循环、敏感操作确认、人类接管 | 学习端侧自动化和中文 App 操作 |
| 7 | OpenClaw | `OpenClaw` | 常驻个人助手、多渠道入口、Skills、Memory、语音、Canvas、插件扩展生态 | 学习大型个人 Agent 操作系统的模块边界 |
| 8 | Suna / Kortix | `suna` | 沙盒电脑、24/7 运行、Skills、触发器、文件系统、全栈 Web/移动/桌面产品 | 学习重型 Agent Runtime 和产品化部署 |

## 分主题学习清单

### 1. 个人助手产品形态

优先看：`CowAgent`、`OpenHuman`、`EchoBot`、`OpenClaw`

- 聊天入口之外，如何接入 Web、微信、飞书、QQ、Telegram、Slack 等渠道。
- 个人助手如何保存配置、身份、偏好、任务记录和长期记忆。
- 人格化交互和后台生产力任务如何分离。
- 一键安装、Web 控制台、CLI 管理命令如何降低上手门槛。

### 2. Agent Harness 架构

优先看：`CowAgent`、`OpenManus`、`OpenClaw`、`suna`

- 消息输入 -> 任务规划 -> 工具/技能调用 -> 记忆检索 -> 输出回复。
- Tool registry、Skill registry、MCP 工具如何抽象。
- 文件、终端、浏览器、搜索、调度器等工具如何统一调用。
- 权限、确认、人类接管、错误恢复放在哪一层。

### 3. 记忆和知识库

优先看：`OpenHuman`、`CowAgent`

- 短期上下文、每日摘要、核心记忆如何分层。
- Markdown / Obsidian 风格知识库如何做到可读、可改、可同步。
- 向量检索、关键词检索、知识图谱如何组合。
- 个人数据连接器如何周期性拉取和蒸馏。

### 4. 多 Agent 协作

优先看：`LangManus`、`OpenManus`、`suna`

- Coordinator、Planner、Supervisor、Researcher、Coder、Browser、Reporter 各自职责。
- 任务计划如何表示、更新、终止和复盘。
- 多 Agent 什么时候有价值，什么时候单 Agent 加好工具更简单。
- 最终报告如何从工具轨迹和中间结果生成。

### 5. 浏览器、手机和 GUI 自动化

优先看：`Open-AutoGLM`、`OpenManus`

- 浏览器自动化如何安装、初始化、执行和回放。
- 手机屏幕如何用视觉语言模型理解。
- ADB/HDC 如何执行点击、输入、滑动等动作。
- 登录、验证码、付款、删除等敏感操作如何交给用户确认。

### 6. 语音和陪伴式体验

优先看：`EchoBot`、`OpenHuman`、`OpenClaw`

- STT/TTS 接入位置。
- 语音会话状态和文本任务状态如何同步。
- 快速情绪/角色回复和慢速后台任务如何并行。
- Live2D、桌面吉祥物、移动端、消息平台展示层如何与核心 Agent 解耦。

### 7. 部署和长期运行

优先看：`CowAgent`、`suna`、`OpenClaw`、`OpenHuman`

- Docker compose、本地运行、服务器运行的配置差异。
- 服务启动、停止、更新、日志和状态检查命令。
- API key、模型供应商、搜索服务、语音服务如何配置。
- 持久化工作区、沙盒、文件系统和数据库如何设计。

## 第一轮建议目标

第一轮不要急着运行所有项目。建议先完成：

1. 阅读 `CowAgent` README 和架构文档，画出自己的 Agent 主链路。
2. 跑通 `OpenManus` 的最小 demo，理解 planner + tools 的执行循环。
3. 阅读 `LangManus` 的多角色架构，决定自己的项目是否真的需要多 Agent。
4. 从 `OpenHuman` 和 `CowAgent` 抽出一套适合自己的记忆分层设计。
5. 从 `EchoBot` 学习如何把“人设回复”和“后台任务执行”拆开。
