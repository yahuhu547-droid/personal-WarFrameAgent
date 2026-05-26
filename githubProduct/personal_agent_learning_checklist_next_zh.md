# 个人 Agent 下一轮学习清单

生成日期：2026-05-25

## 优先级

1. 先学 OpenManus：最小 Agent 闭环已经能本地导入和实例化。
2. 再学 CowAgent：最适合抽个人助手机制。
3. 并行读 EchoBot、OpenClaw：分别补人格化和常驻多渠道架构。
4. 之后读 OpenHuman、LangManus：补长期记忆和多 Agent 编排。
5. 暂缓 Open-AutoGLM、Suna：前者要设备，后者太重。

## OpenManus

- 阅读 `app\agent\base.py`：Agent 状态、memory、step loop。
- 阅读 `app\agent\react.py`：think/act 抽象。
- 阅读 `app\agent\toolcall.py`：LLM tool call 到工具执行的主链路。
- 阅读 `app\agent\manus.py`：默认工具组合与 MCP 初始化。
- 阅读 `app\tool\tool_collection.py`：工具注册、schema、分发。
- 阅读 `app\tool\browser_use_tool.py`：浏览器上下文如何进入下一轮 prompt。
- 阅读 `app\flow\planning.py`：什么时候加入 planning flow。

## CowAgent

- 阅读 `bridge\agent_initializer.py`：初始化流程。
- 阅读 `bridge\agent_bridge.py`：通道与 Agent Core 的桥接。
- 阅读 `channel`：多平台入口抽象。
- 阅读 `agent\tools`：文件、终端、浏览器、搜索、MCP、scheduler。
- 阅读 `agent\memory`：短期/长期记忆边界。
- 准备本地配置，把 `~/cow`、浏览器 profile、凭据路径都改到 `githubProduct\CowAgent-data`。

## EchoBot

- 阅读 `echobot\orchestration\decision.py`。
- 阅读 `echobot\orchestration\roleplay.py`。
- 阅读 `echobot\orchestration\coordinator.py`。
- 阅读 `echobot\agent.py`。
- 汇总安全开关默认值，运行前改成 read-only / no mutation / no private network。

## OpenClaw

- 阅读 `src\entry.ts` 和 `src\gateway`。
- 阅读 `src\channels` 与 `extensions` 的边界。
- 阅读 `skills` 的 `SKILL.md` 组织方式。
- 阅读 `src\memory`。
- 运行前准备 `OPENCLAW_HOME`、`OPENCLAW_STATE_DIR`、`OPENCLAW_WORKSPACE_DIR` 指向项目目录。

## 产出物

- 画一张自己的个人 Agent 主链路图。
- 提炼一版最小工具集：文件、搜索、浏览器、AskHuman、Terminate。
- 设计一版记忆分层：会话记忆、用户偏好、长期知识库、任务日志。
- 写一版安全默认策略：read-only 起步，写文件/shell/浏览器私网/定时任务全部显式开关。
