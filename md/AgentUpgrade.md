# Warframe Agent 三大能力升级

**日期**: 2026-05-04
**版本**: v5.0

---

## 概述

本次升级为 Warframe 交易 Agent 补齐三大核心能力：

| 能力 | 解决的问题 | 关键文件 |
|------|-----------|----------|
| 规划能力 | 复杂查询（对比、投资分析）无法自动拆解 | `tool_router.py` |
| 自主触发 | 价格异常只推原始数据，无分析建议 | `monitor.py`, `price_history.py` |
| 模型微调 | 无法从用户对话中持续学习 | `conversation_log.py`, `tools/` |

---

## Phase 1: 规划能力 — plan 工具

**目标**: 复杂查询自动拆解为子任务并顺序执行。

### 1.1 新增 plan 工具

在 `TOOL_SCHEMAS` 中注册第 7 个工具：

```json
{
    "name": "plan",
    "description": "将复杂请求分解为多个子任务并按顺序执行。用于对比多个物品、投资分析、多步骤查询。",
    "parameters": {
        "goal": "用户目标简述",
        "steps": [
            {"tool": "工具名", "args": {}, "purpose": "步骤目的"}
        ]
    }
}
```

### 1.2 核心数据结构

```python
@dataclass(frozen=True)
class PlanStep:
    tool: str
    arguments: dict[str, Any]
    purpose: str = ""

@dataclass(frozen=True)
class ExecutionPlan:
    goal: str
    steps: list[PlanStep]
```

### 1.3 执行流程

```
用户: "帮我对比充沛和优雅的价格，哪个更值得投资"
  │
  ├─ LLM 返回 plan 调用
  │    goal: "对比赋能价格"
  │    steps: [
  │      {tool: "query_price", args: {item_name: "充沛"}},
  │      {tool: "query_price", args: {item_name: "优雅"}},
  │      {tool: "price_trend",  args: {item_name: "充沛"}},
  │      {tool: "price_trend",  args: {item_name: "优雅"}},
  │    ]
  │
  ├─ execute_plan() 顺序执行每一步
  │
  ├─ _format_plan_results() 聚合所有结果
  │
  └─ LLM 从聚合结果中生成最终对比分析
```

### 1.4 react_loop 集成

在 `_extract_tool_calls` 返回后，优先检查 plan 调用：

```python
plan_calls = [tc for tc in tool_calls if tc.name == "plan"]
if plan_calls:
    plan = _parse_plan(plan_calls[0])
    if plan:
        step_results = execute_plan(plan, tool_executor)
        aggregated = _format_plan_results(plan.goal, step_results)
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "tool", "content": aggregated})
        continue  # 让 LLM 从聚合结果生成最终回答
```

### 1.5 关键文件

| 文件 | 变更 |
|------|------|
| `warframe_agent/tool_router.py` | plan schema、PlanStep/ExecutionPlan、_parse_plan、execute_plan、_format_plan_results、react_loop 集成 |
| `tests/test_plan.py` | 10 个测试用例 |

---

## Phase 2: 自主触发 + LLM 分析

**目标**: 价格异常/机会检测后，用 LLM 生成自然语言分析建议。

### 2.1 EnrichedNotification

```python
@dataclass(frozen=True)
class EnrichedNotification:
    item_id: str
    item_display: str
    notification_type: str  # "anomaly", "opportunity", "trend"
    raw_data: dict
    analysis: str           # LLM 生成的分析
    priority: int
```

### 2.2 异常分析 Prompt

`build_anomaly_analysis_prompt()` 构建包含完整上下文的分析 prompt：

```
物品: 充沛赋能 (arcane_energize)
当前价格: 120p
历史均值: 80p
偏离幅度: 50%
方向: 暴涨
近期趋势: 近 7 天上涨
历史最高: 150p / 历史最低: 40p

请分析可能原因、是否机会、操作建议。
```

### 2.3 机会检测

`detect_opportunities()` 扫描收藏夹快照：

```python
def detect_opportunities(favorite_snapshots):
    for snap in favorite_snapshots:
        spread_pct = (snap.sell_price - snap.buy_price) / snap.buy_price * 100
        if spread_pct > 40:
            # 生成套利机会建议
```

- 价差 > 40% → `ProactiveSuggestion(type="opportunity")`

### 2.4 价格趋势预测

`predict_trend()` 使用最小二乘法线性回归：

```python
def predict_trend(self, item_id: str) -> dict | None:
    snapshots = self.recent(item_id, limit=10)
    # 线性回归拟合最近 10 个价格点
    return {
        "direction": "rising" / "falling" / "stable",
        "slope": 2.5,
        "predicted_next": 110,
        "data_points": 10,
        "current": 100,
    }
```

### 2.5 扫描周期集成 LLM

`PriceMonitor._run()` 中，异常检测后调用 LLM 分析：

```python
if self.llm_analyzer and suggestion.suggestion_type == "anomaly":
    prompt = build_anomaly_analysis_prompt(...)
    analysis = self.llm_analyzer(prompt)
    # 用 LLM 分析替换原始字符串
```

### 2.6 WebSocket 推送

`broadcast_enriched()` 推送 `type: "enriched_analysis"` 消息，前端显示优先级标识 + LLM 分析文本。

### 2.7 关键文件

| 文件 | 变更 |
|------|------|
| `warframe_agent/monitor.py` | EnrichedNotification、build_anomaly_analysis_prompt、detect_opportunities、llm_analyzer 集成 |
| `warframe_agent/price_history.py` | predict_trend() 线性回归 |
| `warframe_agent/web/app.py` | broadcast_enriched() WebSocket 推送 |
| `tests/test_enriched_monitor.py` | 9 个测试用例 |

---

## Phase 3: 模型微调 Pipeline

**目标**: 收集对话 → 生成训练数据 → LoRA 微调 → 集成回 Agent。

### 3.1 对话日志收集

```python
@dataclass
class ConversationEntry:
    user_message: str
    assistant_reply: str
    tool_calls: list[dict] | None = None
    contexts: list[str] | None = None
    rating: int | None = None  # 1-5 星评分
    session_id: str = ""
```

- `log_conversation()` 追加到 `data/conversation_logs.jsonl`
- `answer()` 和 `answer_stream()` 所有返回路径均调用 `_log_answer()`

### 3.2 评分 API

```
POST /api/rate
{
    "message": "用户消息",
    "reply": "Agent 回复",
    "rating": 4,       // 1-5
    "session_id": ""
}
```

前端 agent 消息上显示 1-5 星评分按钮，点击调用此端点。

### 3.3 训练数据生成

```
tools/generate_training_data.py    # 从别名/意图模板生成合成数据
tools/merge_training_data.py       # 合并真实对话 + 合成数据，去重
```

**数据格式** (JSONL):
```json
{
    "messages": [
        {"role": "system", "content": "你是资深星际战甲玩家和中文交易助手。"},
        {"role": "user", "content": "充沛多少钱"},
        {"role": "assistant", "content": "充沛赋能当前最低卖价 45p..."}
    ],
    "source": "real",
    "rating": 5
}
```

### 3.4 LoRA 微调

```
tools/finetune.py
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--epochs` | 3 | 训练轮数 |
| `--lr` | 2e-4 | 学习率 |
| `--batch` | 2 | 每设备 batch size |
| `--lora-r` | 16 | LoRA rank |
| `--lora-alpha` | 32 | LoRA alpha |
| `--max-seq-len` | 2048 | 最大序列长度 |

**流程**:
1. 加载 `unsloth/Qwen3-8b-bnb-4bit`（4-bit 量化）
2. 应用 LoRA（target: q/k/v/o/gate/up/down_proj）
3. 加载 `data/training_data_merged.jsonl`
4. SFT 训练（cosine scheduler, warmup 10%）
5. 保存 adapter → `data/finetuned/adapter/`

### 3.5 模型重建

```
tools/rebuild_ollama_model.py
```

**流程**:
1. 加载基础模型 + LoRA adapter
2. `model.merge_and_unload()` 合并权重
3. 导出 GGUF（默认 q4_k_m 量化）
4. 生成 Modelfile（保留原 system prompt + 别名表）
5. `ollama create warframe-agent-v2 -f Modelfile`

### 3.6 关键文件

| 文件 | 说明 |
|------|------|
| `warframe_agent/conversation_log.py` | ConversationEntry、log_conversation、load_conversations |
| `warframe_agent/chat.py` | _log_answer() 集成到 answer/answer_stream |
| `warframe_agent/web/app.py` | POST /api/rate 端点 |
| `warframe_agent/web/static/js/chat.js` | 评分 UI（1-5 星） |
| `tools/generate_training_data.py` | 合成训练数据生成 |
| `tools/merge_training_data.py` | 数据合并 + 去重 |
| `tools/finetune.py` | LoRA 微调脚本 |
| `tools/rebuild_ollama_model.py` | GGUF 导出 + Ollama 模型创建 |

---

## 完整微调流程

```
1. 日常使用 Agent 对话
       ↓ 自动记录到 conversation_logs.jsonl
       ↓ 用户评分（1-5 星）

2. 积累足够数据后生成训练集
       python tools/generate_training_data.py    # 生成合成数据
       python tools/merge_training_data.py        # 合并 + 去重

3. 微调（需要 8GB+ VRAM GPU）
       python tools/finetune.py --epochs 3

4. 重建 Ollama 模型
       python tools/rebuild_ollama_model.py --model-name warframe-agent-v2

5. 使用微调模型
       # 修改 config.py 中 REACT_MODEL 或 MODEL_NAME
       # 或在 Ollama 中: ollama run warframe-agent-v2
```

---

## 测试覆盖

| 测试文件 | 用例数 | 覆盖范围 |
|----------|--------|----------|
| `tests/test_plan.py` | 10 | plan 解析、执行、react_loop 集成、失败处理 |
| `tests/test_enriched_monitor.py` | 9 | 异常 prompt、机会检测、趋势预测、LLM 分析回调 |

**总测试**: 169 → 188（+19 新测试）

---

## 配置变更

无新增配置项。使用现有 `config.py` 中的 `REACT_MODEL` 和 `MAX_TOOL_ITERATIONS`。
