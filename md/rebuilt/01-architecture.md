# 01. 总体架构

## 一句话概览

本项目是一个面向 Warframe 交易场景的智能助手：以 `ChatAgent` 为核心入口，连接 warframe.market、官方世界状态、游戏导出数据、本地/云端模型、长期记忆、后台监控、Web API、Web UI、飞书和 WxPusher 推送。

## 核心入口

| 层级 | 关键文件 | 说明 |
|---|---|---|
| 聊天 Agent | `warframe_agent/chat.py` | 自然语言入口、确定性规则、工具绑定、LLM 回退、流式回答。 |
| 轻量 Agent | `warframe_agent/agent.py` | 早期价格查询、字典重建、日报生成入口。 |
| Web 服务 | `warframe_agent/web/app.py` | FastAPI API、静态 Web UI、生命周期启动监控和飞书。 |
| 后台监控 | `warframe_agent/monitor.py` | 价格提醒、收藏扫描、事件订阅、主动建议、推送。 |
| 工具系统 | `warframe_agent/tool_registry.py`、`warframe_agent/tool_router.py` | 工具定义、参数校验、ReAct 路由、多步骤计划。 |
| 模型编排 | `warframe_agent/llm.py`、`warframe_agent/model_orchestrator.py` | 本地 Ollama、云端 OpenAI 兼容 API、自动路由与回退。 |

## 分层结构

```text
用户入口
  ├─ CLI / ChatAgent
  ├─ Web UI / FastAPI
  ├─ 飞书机器人
  └─ WxPusher 推送回调

交互与编排层
  ├─ ChatAgent
  ├─ ToolRegistry / ToolRouter / ReAct
  ├─ Slash Command
  ├─ ModelOrchestrator
  └─ Expert / Scout

业务能力层
  ├─ 市场订单、价格统计、趋势
  ├─ Prime 套装、部件、缺件、遗物
  ├─ Riven 紫卡拍卖
  ├─ Baro 虚空商人
  ├─ 世界状态、裂缝、周期、Prime 重生/Vault
  ├─ Mod/赋能倒卖、套装套利、投资顾问
  └─ 目标、规则、模式、自学习

数据与记忆层
  ├─ agent_memory.json
  ├─ price_history.db / trade_history.db / trading_memory.db
  ├─ conversation_logs.jsonl
  ├─ items_full.json / generated_aliases.json / relic 数据
  └─ price_cache.db / worldstate 缓存
```

## 主请求链路

### 普通聊天和价格查询

```text
用户问题
  -> ChatAgent.answer / answer_stream
  -> Slash Command 或确定性规则优先匹配
  -> 必要时调用 ToolRegistry 中的工具
  -> 市场/API/记忆/活动/历史模块返回结构化结果
  -> tool_context 清洗和压缩外部数据
  -> 必要时交给 LLM 综合
  -> 返回用户，同时写入会话、记忆或交易记忆
```

### Web 请求链路

```text
浏览器 / 外部客户端
  -> FastAPI endpoint
  -> 全局 ChatAgent / Monitor / DB / Push 实例
  -> 业务模块
  -> JSON 响应或静态资源
```

### 后台监控链路

```text
SchedulerRunner / PriceMonitor
  -> 周期性扫描收藏、提醒、事件、知识库、目标
  -> 记录价格历史和交易记忆
  -> 判断异常、机会、订阅命中
  -> WxPusher / 飞书 / Web UI 可见结果
```

## 关键模块边界

| 模块 | 负责 | 不负责 |
|---|---|---|
| `chat.py` | 用户输入理解、路由、回答组织。 | 直接持久化所有业务数据的底层细节。 |
| `market.py` | warframe.market 订单、统计、缓存、买卖盘整理。 | 投资策略判断和长期记忆。 |
| `events.py` | 官方世界状态、Baro、裂缝、周期、Prime 活动。 | 市场价格计算。 |
| `riven.py` | 紫卡查询解析、拍卖搜索、展示格式。 | 普通物品市场订单。 |
| `baro.py` | Baro 库存与市场价格推荐。 | 世界状态原始下载。 |
| `monitor.py` | 主动扫描、推送、调度任务整合。 | Web 路由定义。 |
| `tool_registry.py` | 工具规范、执行、结果元数据。 | LLM prompt 的路由决策。 |
| `tool_router.py` | LLM 工具选择、ReAct、多步骤计划。 | 具体工具业务实现。 |
| `tool_context.py` | 外部数据清洗、脱敏、压缩。 | 业务判断。 |

## 外部依赖边界

| 来源 | 用途 | 主要入口 |
|---|---|---|
| warframe.market API | 价格、订单、紫卡拍卖。 | `market.py`、`riven.py` |
| Warframe worldState | Baro、裂缝、活动、Prime 信息。 | `events.py` |
| warframestat.us | 开放世界周期。 | `events.py` |
| Ollama | 本地聊天、embedding、名称解析。 | `llm.py`、`rag.py` |
| OpenAI 兼容 API | 云端复杂分析、Scout。 | `llm.py`、`model_orchestrator.py`、`scout.py` |
| 飞书开放平台 | 长连接机器人。 | `feishu.py` |
| WxPusher | 微信推送。 | `push.py` |

## 架构原则

1. 确定性功能优先：价格、紫卡、Baro、活动等实时数据不依赖模型编造。
2. LLM 只做解析、综合和表达：外部事实必须来自工具或缓存。
3. 外部数据进入模型前必须经过 `tool_context.py` 清洗。
4. 用户可见的交易对象、profile 链接和 `/w` 私聊命令只在明确用户展示场景出现。
5. 后台监控和 Web API 共享同一批核心业务模块，避免重复实现。
