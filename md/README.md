# Warframe Trading Agent

面向 Warframe 交易玩家的本地优先智能助手，提供查价、套装补齐、活动查询、交易记录、目标管理、价格监控、飞书/浏览器推送，以及 Web / CLI / 飞书三种交互方式。

当前架构是 **本地模型优先 + 可选云端增强**：

- 本地模型负责日常对话、工具路由和大部分实时查询。
- 云端模型用于可选的复杂分析、自动路由和 Scout 预筛选。
- 未配置 `CLOUD_API_KEY` 时，系统会停留在本地模型路径，不会自动走云端。

## 核心能力

### 1. 交易与价格

- 实时查询 warframe.market 最低卖价、最高收价、价差、卖家/买家信息
- 自动生成游戏内 `/w` 私聊命令
- Arcane 满级成本估算
- Prime 套装整套 vs 拆件价格对比
- 缺失部件补齐成本计算
- Mod 翻转、套装利润、投资顾问
- Riven / 紫卡检索与筛选（自动识别变体武器，强制使用基础版查询）

### 2. 游戏数据与事件

- 虚空裂缝、Baro、入侵、虚空风暴等活动查询
- 遗物掉落来源与掉落物查询
- Baro 库存分析与购买建议
- Wiki / 游戏资料接口聚合

### 3. 智能体能力

- 多轮对话与上下文追问
- 6 层物品名解析：手动别名、字典、生成式别名、标准化、LLM 模糊匹配、RAG 语义搜索
- ReAct 工具路由：查价、套装、趋势、活动、投资、Riven、深度分析等能力按需调用
- 复杂问题分解与分步执行（plan）
- 本地优先、复杂请求可选云端分析
- Scout 预筛选：先从候选池筛出更值得深入查询的条目，再做详细扫描

### 4. 自动化与主动提醒

- 收藏列表、价格提醒、关注列表
- 后台价格监控与异常提醒
- 裂缝订阅与推送
- 交易自动记录、盈亏统计
- 交易目标创建、执行、复盘
- 浏览器通知、WxPusher、飞书机器人推送

## 交互方式

### Web UI

- FastAPI + WebSocket 提供聊天、推送和工具面板
- 纯 HTML/CSS/JS 前端，无构建工具依赖
- 价格详情、趋势图、收藏/提醒/关注面板

启动：

```bash
python start_web.py
# 浏览器访问 http://127.0.0.1:8000
```

### CLI

```bash
python main.py
```

### 飞书机器人

- 支持多轮对话、查价、策略、交易和裂缝订阅
- 使用说明见 [`FeishuUserGuide.md`](FeishuUserGuide.md)

## 斜杠命令概览

| 命令 | 功能 |
|------|------|
| `/help` | 查看帮助 |
| `/memory` | 查看记忆摘要 |
| `/scan` | 扫描收藏和提醒 |
| `/fav add/remove` | 管理收藏 |
| `/alert add/remove` | 管理价格提醒 |
| `/fissure add/remove/list` | 管理裂缝订阅 |
| `/trade list/stats/add/undo` | 管理交易记录 |
| `/relic` | 查询遗物掉落或遗物内容 |
| `/strategy list/run` | 执行策略扫描 |
| `/vault` | 查询 Vault 状态 |
| `/goal` | 创建、完成、复盘目标 |
| `/pref` | 设置平台、跨平台和结果数 |

## 技术栈

- Python 3.14
- Ollama（本地对话 / 路由 / embedding）
- FastAPI + WebSocket
- warframe.market API
- Warframe World State API
- SQLite（价格历史、交易历史、缓存）
- Playwright（抓取与 WebUI 验证）
- Chart.js
- 纯 HTML / CSS / JavaScript

## 当前测试状态

当前仓库快照下，测试套件已通过：

- **55 个测试文件**
- **545 个测试用例（紫卡相关 75 个）**

覆盖聊天、Web API、价格历史、监控、推送、Riven、Relic、策略、RAG、目标系统等核心模块。

运行：

```bash
python -m pytest tests -q
```

## 项目结构

```text
warframe_agent/
  agent.py              # CLI 基础 Agent
  chat.py               # 对话式交易助手
  config.py             # 模型、路径、阈值、外部服务配置
  llm.py                # 本地/云端模型调用与自动路由
  tool_router.py        # ReAct 工具路由
  dictionary.py         # 物品名称解析
  market.py             # warframe.market API 封装
  monitor.py            # 后台扫描与主动推送
  memory.py             # 持久化记忆
  price_history.py      # 价格历史
  trade_history.py      # 交易历史
  events.py             # 游戏事件追踪
  baro.py               # Baro 推荐
  relics.py             # 遗物搜索与掉落数据
  riven.py              # Riven / 紫卡数据查询
  scout.py              # 多模型预筛选
  scanner.py            # 扫描任务支持
  strategies.py         # 交易策略
  goals.py              # 目标系统
  report.py             # 每日报告
  push.py               # WxPusher 推送
  feishu.py             # 飞书机器人
  web/
    app.py              # FastAPI 应用与 WebSocket
    static/             # Web UI 静态资源

tests/                  # 后端与集成测试
data/                   # 本地数据、缓存、配置、运行态文件
docs/                   # 设计文档、执行计划、阶段报告
md/                     # 面向项目阅读的主文档
```

## 架构概览

```text
用户输入
  ├─ CLI / Web / 飞书
  ├─ 斜杠命令 → 直接操作记忆、提醒、目标、订阅
  ├─ 确定性路径 → 别名/字典/规则直接命中
  └─ 模糊路径
       ├─ ReAct 工具路由
       ├─ RAG 语义回退
       └─ 复杂请求可选云端增强
```

## 相关文档

- [功能清单](FeatureList.md)
- [智能体架构说明](AgentArchitecture.md)
- [Web 服务与接口说明](WebService.md)
- [飞书机器人使用指南](FeishuUserGuide.md)
- [安全加固与分阶段整改执行计划](../docs/security-and-hardening-execution-plan.md)
- [UI 设计计划](../docs/ui_design_plan.md)
- [UI 实现报告](../docs/ui_implementation_report.md)
- [UI 预览](../docs/ui_preview.html)

## License

MIT
