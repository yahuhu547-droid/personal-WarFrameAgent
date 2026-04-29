# Warframe Trading Agent

基于 Python + Ollama 本地大模型的 Warframe 游戏交易智能助手。完全本地运行，无需云端 API，保护用户隐私。

## 功能特性

- **实时查价** — 查询 warframe.market 的卖价、收价、价差，自动生成游戏内私聊命令
- **6 层物品解析** — 中文别名 / 本地字典 / 生成式别名 / 标准化 / LLM 模糊匹配 / RAG 语义搜索
- **LLM 工具路由** — qwen3:8b 模型自动将自然语言分发到对应工具（查价、套装对比、补件计算等）
- **后台价格监控** — daemon 线程定时扫描关注物品，价格触发阈值时主动通知
- **价格历史追踪** — SQLite 记录价格快照，支持趋势分析（上涨/下跌/持平）
- **会话上下文** — 支持追问（"那散件呢"、"涨了吗"），自动复用上次查询物品
- **持久化记忆** — 收藏列表、价格提醒、交易偏好、对话记忆跨会话保存
- **Prime 套装定价** — 整套 vs 拆件价格对比，计算补齐缺失部件的最优花费
- **每日价格报告** — 批量生成关注物品的价格表

## 技术栈

- Python 3.14
- Ollama（qwen3:8b，本地推理）
- warframe.market v2 API
- SQLite（价格历史）
- 95 个单元测试

## 快速开始

### 前置要求

- Python 3.10+
- [Ollama](https://ollama.com/) 已安装并运行
- 下载模型：`ollama pull qwen3:8b`

### 安装

```bash
git clone https://github.com/<your-username>/warframe-trading-agent.git
cd warframe-trading-agent
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
warframe_agent/     # 核心模块
  agent.py          # 主 Agent 入口
  chat.py           # 对话式交易助手
  config.py         # 配置常量
  dictionary.py     # 6 层物品名称解析
  market.py         # warframe.market API 客户端
  memory.py         # 持久化记忆系统
  monitor.py        # 后台价格监控
  price_history.py  # SQLite 价格历史
  session.py        # 会话上下文
  tool_router.py    # LLM 工具路由
  ...
tests/              # 95 个单元测试
data/               # 物品数据、别名、记忆存储
tools/              # 构建脚本
```

## 测试

```bash
python -m unittest discover -s tests -v
```

## License

MIT
