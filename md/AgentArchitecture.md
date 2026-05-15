# 智能体架构说明

> 本文档描述 Warframe 交易助手当前的真实架构边界：本地优先、规则驱动、工具化执行，并在必要时接入云端增强分析。

---

## 1. 架构原则

这个项目不是“纯聊天机器人”，而是一个 **交易智能体系统**：

- **规则与数据** 负责尽可能确定的判断
- **LLM** 负责表达、路由、复杂问题拆解，以及一部分可选深度分析
- **后台监控** 负责持续扫描、主动提醒和事件驱动推送
- **Web / CLI / 飞书** 只是不同的交互入口

当前实现是 **本地优先 + 可选云端增强**：

- 本地模型：常规对话、工具路由、物品模糊解析、embedding / RAG 等
- 云端模型：复杂分析、自动路由增强、Scout 预筛选
- 若未配置 `CLOUD_API_KEY`，自动路由会保持在本地模型路径

---

## 2. 分层结构

```text
用户交互层
  ├─ chat.py                    对话入口
  ├─ web/app.py                 Web API + WebSocket + 静态前端
  └─ feishu.py                  飞书机器人

智能体编排层
  ├─ tool_router.py             ReAct 工具路由 / plan / 深度分析 / Riven 查询
  ├─ llm.py                     本地/云端模型调用与自动路由
  └─ session.py                 会话上下文与追问复用

业务能力层
  ├─ market.py                  市场数据
  ├─ warframes.py               Prime 套装与补件
  ├─ mod_flipper.py             Mod 翻转
  ├─ set_profit.py              套装利润
  ├─ investment.py              投资顾问
  ├─ riven.py                   Riven / 紫卡
  ├─ relics.py                  遗物查询
  ├─ events.py / baro.py        游戏事件与 Baro 推荐
  ├─ strategies.py              交易策略
  └─ goals.py                   目标创建、执行、复盘

状态与知识层
  ├─ memory.py                  收藏、提醒、偏好、订阅、建议
  ├─ price_history.py           价格快照与趋势
  ├─ trade_history.py           交易记录
  ├─ knowledge.py               市场知识累积
  ├─ feedback.py                反馈信号
  └─ patterns.py                模式发现

主动行为层
  ├─ monitor.py                 定时扫描、异常检测、主动推送
  ├─ push.py                    WxPusher
  └─ feishu.py                  飞书推送
```

---

## 3. 交互入口

### 3.1 CLI

`main.py` 提供主菜单，支持：

- 单品查询
- 日报生成
- 字典重建
- 对话模式
- 启动 Web UI

### 3.2 Web

`warframe_agent/web/app.py` 是当前最大的整合层，负责：

- HTTP API
- WebSocket 聊天与通知
- 推送配置接口
- 交易、目标、Riven、Relic、Wiki 等工具型 API
- 监控器和前端静态资源挂载

### 3.3 飞书

`warframe_agent/feishu.py` 提供飞书机器人能力，与聊天、推送、订阅和后台监控联动。

---

## 4. LLM 在系统中的角色

LLM 不是唯一决策源，而是系统中的一个能力层。

### 本地模型主要负责

- 日常自然语言对话
- ReAct 工具路由
- 物品模糊解析辅助
- RAG / embedding 相关能力

### 云端模型主要负责

- 深度分析（如单品投资价值）
- 复杂问题的自动路由增强
- Scout 预筛选（例如先从候选池中筛出更值得详细查询的对象）

### 规则/数据层负责

- 市场数据读取与格式化
- 价格趋势和历史记录
- 交易记录与统计
- 异常检测、主动建议、目标执行、订阅匹配

所以更准确的描述是：

> **规则与数据决定“事实”和“大部分判断”，LLM 负责“怎么说、调用什么工具、什么时候需要更深分析”。**

---

## 5. 典型数据流

### 5.1 普通查价

```text
用户输入“充沛多少钱”
  → chat.py 接收消息
  → dictionary.py / 名称解析命中物品
  → market.py 拉取订单
  → formatter.py 生成显示文本和私聊命令
  → llm.py / chat.py 组织自然语言回复
```

### 5.2 模糊或复杂请求

```text
用户输入“对比充沛和复仇者哪个更值得投资”
  → tool_router.py 识别复杂请求
  → plan / 多工具调用
  → price_trend / investment / query_price 等能力组合执行
  → llm.py 汇总结果生成回答
  → 若启用云端增强，可走 cloud / scout 路径
```

### 5.3 主动提醒

```text
monitor.py 定时扫描
  → price_history.py / market.py 获取最新状态
  → rules.py / knowledge.py / feedback.py 判断异常或机会
  → push.py / feishu.py / WebSocket 推送到用户
```

---

## 6. 当前核心模块

### 用户交互层

- `chat.py`：聊天入口、斜杠命令、上下文处理
- `web/app.py`：Web 聚合入口
- `feishu.py`：飞书消息收发
- `formatter.py`：价格文本和私聊命令格式化
- `session.py`：会话上下文与追问复用

### 编排与路由层

- `tool_router.py`：工具 schema、plan、事件/投资/深度分析/Riven 路由
- `llm.py`：本地与云端模型统一接口、自动路由
- `dictionary.py` / `rag.py` / `names.py`：物品解析与搜索回退

### 业务能力层

- `warframes.py`：Prime 套装定价和补件
- `mod_flipper.py` / `set_profit.py` / `investment.py`
- `riven.py` / `relics.py`
- `events.py` / `baro.py`
- `strategies.py` / `scanner.py`

### 状态与学习层

- `memory.py`
- `price_history.py`
- `trade_history.py`
- `knowledge.py`
- `feedback.py`
- `patterns.py`
- `conversation_log.py`

---

## 7. 测试现状

当前仓库快照下，测试覆盖已经扩展到：

- 55 个测试文件
- 545 个测试用例（含 75 个紫卡专项）

重点覆盖：

- 聊天、路由、RAG、上下文复用
- Web API、WebSocket、推送配置
- 监控、趋势、异常检测、主动推送
- Prime 套装、遗物、Riven、策略、投资工具
- 交易历史、目标系统、飞书集成

运行：

```bash
python -m pytest tests -q
```

---

## 8. 当前已知架构问题

这些问题不影响理解系统，但会影响后续维护：

1. `warframe_agent/web/app.py` 过大，承担过多职责。
2. 前端 JS 仍有较多 `innerHTML` 与内联事件处理。
3. 主文档与代码容易发生漂移，需要持续同步。
4. 本地配置、日志和运行态文件需要更严格的提交隔离。

这些问题已在 [`../docs/security-and-hardening-execution-plan.md`](../docs/security-and-hardening-execution-plan.md) 中列为后续分批整改项。

---

## 9. 总结

可以把这个项目理解为：

- **数据层**：市场、事件、遗物、历史、交易
- **判断层**：规则、知识、反馈、目标、监控
- **表达与编排层**：LLM、工具路由、plan、RAG
- **交互层**：CLI、Web、飞书、推送

它不是“单个模型回答问题”，而是一个围绕 Warframe 交易场景构建的多模块智能体系统。