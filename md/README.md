# Warframe Trading Agent

基于 Python + Ollama 本地大模型（qwen3:8b）的 Warframe 游戏交易智能助手。完全本地运行，无需云端 API，保护用户隐私。

![UI Preview](docs/ui_preview.png)

## 功能特性

### 核心查价

- **实时查价** — 查询 warframe.market v2 API 的最低卖价、最高收价、价差，显示卖家/买家声望
- **游戏内私聊命令** — 自动生成 `/w 玩家名 Hi! I want to buy/sell...` 格式的交易私聊，支持一键复制到剪贴板
- **赋能满级估算** — 自动计算 arcane 类物品 21 个满级的总花费
- **交易意图检测** — 识别"想买"、"想出"、"能卖吗"等中文表达，给出针对性的买入/卖出建议

### 物品名称解析（6 层 fallback）

1. 手动别名表（`data/item_aliases.json`）
2. 本地物品字典（从游戏导出数据构建）
3. 生成式别名（自动从中英文数据生成）
4. 标准化 market_id（空格→下划线、大小写归一化）
5. LLM 模糊匹配（Ollama 推理）
6. RAG 语义搜索（关键词匹配 + 编辑距离）

### Agent 能力

- **LLM 工具路由** — qwen3:8b 模型实现 function calling，自动将自然语言分发到 7 个工具：
  - `query_price`: 查询单品实时价格
  - `query_set`: Prime 套装整套 vs 拆件对比
  - `query_missing_parts`: 计算补齐套装缺失部件花费
  - `scan_favorites`: 扫描关注列表当前状态
  - `set_alert`: 设置价格提醒
  - `price_trend`: 查看价格历史趋势
  - `general_chat`: 一般交易问题闲聊
- **ReAct 多步推理** — 支持链式工具调用（如"我有50p买什么赋能倒卖最赚"→ 查询多个赋能 → 对比 → 推荐）
- **多轮对话** — session history 注入 LLM，上下文连贯
- **行为学习** — 分析用户查询模式构建画像，个性化回答
- **主动智能** — 价格异常检测 + 趋势监控，Agent 主动给出建议
- **语义 RAG** — nomic-embed-text 向量搜索，支持"回蓝的赋能"→ arcane_energize 等语义匹配
- **后台价格监控** — daemon 线程每 5 分钟扫描关注物品和价格提醒，触发阈值时主动推送通知
- **价格历史追踪** — SQLite 自动记录每次查询的价格快照，支持趋势分析（上涨/下跌/持平）
- **会话上下文** — 检测追问关键词（"那散件呢"、"涨了吗"、"比昨天"等 14 种模式），自动复用上次查询物品
- **持久化记忆系统** — 不可变 dataclass 设计，支持：
  - 收藏列表（`/fav add/remove`）
  - 价格提醒（`/alert add/remove`，支持 below/above 方向，可添加备注）
  - 交易偏好（平台、crossplay、最大结果数）
  - 关注列表（定时推送，支持 daily/hourly/weekly）
  - 常见问题自动记录
  - 智能建议（异常检测结果）

### Prime 套装

- **整套 vs 拆件对比** — 自动查询套装价格和所有散件价格之和，计算哪种更划算
- **补件计算** — 输入已有部件，计算补齐剩余部件的最低花费
- **通用化支持** — 支持所有 Prime 战甲和武器，自动识别部件关系

### 斜杠命令系统

| 命令 | 功能 |
|------|------|
| `/help` | 查看所有可用命令 |
| `/memory` | 查看记忆摘要（偏好、收藏、提醒、常见问题） |
| `/scan` | 手动触发全量扫描（收藏价格 + 提醒检查） |
| `/fav add 物品名` | 添加收藏 |
| `/fav remove 物品名` | 移除收藏 |
| `/alert add 物品名 below 45` | 设置价格提醒 |
| `/alert remove 物品名 below 45` | 移除价格提醒 |
| `/pref platform pc` | 设置交易平台 |
| `/pref crossplay on` | 设置跨平台 |
| `/pref max 10` | 设置最大显示结果数 |

### 其他

- **每日价格报告** — 批量生成关注物品的价格表，输出到 `reports/` 目录
- **本地物品字典重建** — 从游戏导出数据重新生成中英文映射

## 技术栈

- **Python 3.14** — 纯标准库 + 最少外部依赖
- **Ollama**（qwen3:8b, 5.2GB）— 本地推理，零云端调用
- **FastAPI + WebSocket** — Web 后端 + 流式通信
- **warframe.market v2 API** — 实时交易数据
- **SQLite** — 价格历史 + 交易历史持久化存储
- **Playwright** — 浏览器自动化抓取（绕过 Cloudflare）
- **Chart.js** — 价格趋势可视化
- **纯 HTML/CSS/JS** — 前端无构建工具，Tenno 科技终端风格
- **169 个单元测试** — 覆盖所有核心模块和 Web API

## 快速开始

### 前置要求

- Python 3.10+
- [Ollama](https://ollama.com/) 已安装并运行
- 下载模型：`ollama pull qwen3:8b`

### 安装

```bash
git clone https://github.com/yahuhu547-droid/personal-WarFrameAgent.git
cd personal-WarFrameAgent
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 构建自定义模型

```bash
python tools/build_ollama_model.py
```

### 运行

**Web 模式**（推荐）：

```bash
python start_web.py
# 浏览器访问 http://localhost:8000
```

**CLI 模式**：

```bash
python main.py
```

或双击 `start_web.bat`（Web 界面）/ `start_agent.bat`（CLI 主菜单）。

### 对话示例

```
你：充沛现在多少钱
Agent：物品: 充沛赋能
      最低卖价: 45p，卖家 Player1
      最高收价: 38p，买家 Player2
      价差: 7p
      满级估算: 21 个约 945p

你：那散件呢
Agent：（自动复用上次物品，查询散件价格）

你：/alert add 充沛 below 40
Agent：已添加提醒: 充沛 低于 40p 时通知
```

## 项目结构

```
warframe_agent/        # 核心模块
  agent.py             # 主 Agent 入口，物品查询 + 报告生成
  chat.py              # 对话式交易助手，整合所有 Agent 能力
  config.py            # 配置常量（API 地址、模型名、路径）
  dictionary.py        # 6 层物品名称解析器
  formatter.py         # 输出格式化 + 游戏内私聊命令生成
  llm.py               # Ollama LLM 调用封装（单轮 + 多轮对话）
  market.py            # warframe.market v2 API 客户端（缓存 + 限速）
  memory.py            # 持久化记忆系统（不可变 dataclass + 画像 + 建议）
  monitor.py           # 后台价格监控（daemon 线程 + 异常检测）
  names.py             # 物品显示名称 + 模块级缓存
  price_history.py     # SQLite 价格历史追踪 + 趋势分析
  rag.py               # RAG 语义搜索（关键词 + 向量余弦相似度）
  scraper.py           # Playwright 浏览器抓取（绕过 Cloudflare）
  session.py           # 会话上下文 + 追问检测 + messages 构建
  tool_router.py       # ReAct 工具路由 + LLM 原生工具调用
  trade_history.py     # SQLite 交易历史记录
  trade_intent.py      # 交易意图检测（买入/卖出/观望）
  warframes.py         # Prime 套装定价 + 补件计算
  web/
    app.py             # FastAPI Web 应用（35+ API 端点 + 2 WebSocket）
    static/
      index.html       # 主页面（Tenno 科技终端风格）
      css/             # 变量、动画、主样式、响应式
      js/              # app.js, chat.js, sidebar.js, chart.js
tests/                 # 33 个测试文件，169 个测试用例
data/                  # 物品数据、别名映射、记忆存储、遗物数据
tools/                 # 数据构建 + embedding 预计算脚本
md/                    # 项目文档
```

## 测试

```bash
python -m pytest tests/ -v
```

33 个测试文件，169 个测试用例，覆盖：
- 物品解析全链路（别名、字典、生成式、标准化、LLM、RAG）
- 对话系统（查价、追问、斜杠命令、记忆操作、RAG 降级）
- 多轮对话（session history、messages 构建、上下文连贯）
- ReAct 推理（工具调用、多步分解、链式执行）
- 行为学习（用户画像、关键词分析、个性化注入）
- 主动智能（异常检测、趋势监控、建议生成）
- 语义 RAG（向量搜索、余弦相似度、embedding 缓存）
- 后台监控（扫描触发、通知队列、线程生命周期、网络容错）
- 价格历史（记录/查询、趋势计算、边界情况）
- 会话上下文（追问检测、物品复用、历史记录）
- Prime 套装（整套定价、拆件对比、补件计算、部件分组）
- 交易意图（买入/卖出/观望识别）
- 市场 API 客户端（排序、过滤、格式化）
- Web API（所有端点、WebSocket、缓存、限速）

## 架构设计

```
用户输入
  │
  ├─ 斜杠命令 (/fav, /alert, /scan, /pref, /memory)
  │    └─ 直接执行，操作记忆系统
  │
  ├─ 追问检测 ("那散件呢", "涨了吗")
  │    └─ 复用 SessionContext 中的上次物品
  │
  ├─ 确定性路径（别名/字典直接匹配）
  │    ├─ 交易意图检测 → 针对性买卖建议
  │    └─ LLM 生成自然语言回复
  │
  └─ 模糊路径（无直接匹配）
       ├─ LLM 工具路由 → 选择工具 → 执行 → 回复
       └─ RAG 语义搜索 → 降级回复
```

## 相关文档

- [UI 设计计划](docs/ui_design_plan.md) - 详细的设计理念和规范
- [UI 实现报告](docs/ui_implementation_report.md) - 实现的功能和技术细节
- [升级计划](docs/upgrade_plan.md) - Phase 5-8 的完整升级计划
- [UI 预览](docs/ui_preview.html) - 在线预览设计效果

## License

MIT
