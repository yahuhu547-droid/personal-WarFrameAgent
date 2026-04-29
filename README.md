# Warframe Trading Agent

基于 Python + Ollama 本地大模型（qwen3:8b）的 Warframe 游戏交易智能助手。完全本地运行，无需云端 API，保护用户隐私。

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
- **后台价格监控** — daemon 线程每 5 分钟扫描关注物品和价格提醒，触发阈值时主动推送通知
- **价格历史追踪** — SQLite 自动记录每次查询的价格快照，支持趋势分析（上涨/下跌/持平）
- **会话上下文** — 检测追问关键词（"那散件呢"、"涨了吗"、"比昨天"等 14 种模式），自动复用上次查询物品
- **持久化记忆系统** — 不可变 dataclass 设计，支持：
  - 收藏列表（`/fav add/remove`）
  - 价格提醒（`/alert add/remove`，支持 below/above 方向）
  - 交易偏好（平台、crossplay、最大结果数）
  - 常见问题自动记录

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

- **Python 3.14** — 纯标准库 + 最少外部依赖（requests, ollama, pyperclip）
- **Ollama**（qwen3:8b, 5.2GB）— 本地推理，零云端调用
- **warframe.market v2 API** — 实时交易数据
- **SQLite** — 价格历史持久化存储
- **threading** — daemon 线程后台监控
- **dataclasses (frozen=True)** — 不可变数据模型，线程安全
- **95 个单元测试** — 覆盖所有核心模块，依赖注入支持完整 mock

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

双击 `start_agent.bat`（主菜单）或 `start_chat.bat`（直接进入对话模式）。

或命令行：

```bash
python main.py
```

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
  llm.py               # Ollama LLM 调用封装
  market.py            # warframe.market v2 API 客户端
  memory.py            # 持久化记忆系统（不可变 dataclass）
  monitor.py           # 后台价格监控（daemon 线程）
  names.py             # 物品显示名称 + 模块级缓存
  price_history.py     # SQLite 价格历史追踪
  rag.py               # RAG 语义搜索（关键词 + 编辑距离）
  session.py           # 会话上下文 + 追问检测
  tool_router.py       # LLM 工具路由（function calling）
  trade_intent.py      # 交易意图检测（买入/卖出/观望）
  warframes.py         # Prime 套装定价 + 补件计算
tests/                 # 30 个测试文件，95 个测试用例
data/                  # 物品数据、别名映射、记忆存储
tools/                 # Ollama 模型构建 + 数据生成脚本
```

## 测试

```bash
python -m unittest discover -s tests -v
```

30 个测试文件，95 个测试用例，覆盖：
- 物品解析全链路（别名、字典、生成式、标准化、LLM、RAG）
- 对话系统（查价、追问、斜杠命令、记忆操作、RAG 降级）
- 后台监控（扫描触发、通知队列、线程生命周期、网络容错）
- 价格历史（记录/查询、趋势计算、边界情况）
- 会话上下文（追问检测、物品复用、历史记录）
- LLM 工具路由（prompt 构建、JSON 解析、嵌套大括号、降级回退）
- Prime 套装（整套定价、拆件对比、补件计算、部件分组）
- 交易意图（买入/卖出/观望识别）
- 市场 API 客户端（排序、过滤、格式化）

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

## License

MIT
