# Warframe 个人 Agent 升级路线图

> 从"Warframe 交易工具"演进为"懂我的个人 Agent"的详细计划。
> 创建日期：2026-05-15
> 当前版本：v16.1（紫卡变体武器修复 + 中文别名 99.8% 覆盖）

---

## 总览

| 阶段 | 主题 | 工作量 | 优先级 |
|---|---|---|---|
| **Phase 34** | 用户画像系统 (Profile) | 5-7 天 | ⭐⭐⭐⭐⭐ |
| **Phase 35** | 智能晨报 / 周报 + 决策日志 | 4-5 天 | ⭐⭐⭐⭐⭐ |
| **Phase 36** | 截图识别（紫卡 / 聊天 / 库存）| 6-8 天 | ⭐⭐⭐⭐⭐ |
| **Phase 37** | Eval 框架 + 自我反思 | 3-4 天 | ⭐⭐⭐⭐ |
| **Phase 38** | 库存与 Foundry 集成 | 4-5 天 | ⭐⭐⭐ |
| **Phase 39** | 插件系统 + 安全护栏 | 5-6 天 | ⭐⭐⭐ |
| **Phase 40** | 跨设备 / 移动端 | 7-10 天 | ⭐⭐ |

**总计**：34-45 天工作量。建议按优先级分批落地。

---

## Phase 34：用户画像系统（Profile）

### 痛点
当前 `memory.py` 是简单 KV 存储（收藏、提醒、订阅），缺少对"你这个玩家"的画像建模。Agent 给的所有建议都是"通用建议"，不是"懂你的建议"。

### 目标
让 Agent 知道：
- 你当前持有多少 P（流动资金）
- 你的交易风格（短线翻倒 / 长线囤货 / Riven 玩家 / 收藏家）
- 你的长期目标（如"3 个月攒 5000P 买 Trinity Prime"）
- 你的 MR 等级（决定能否使用某些武器）
- 你已拥有什么（避免推荐你已有的物品）

### 实施步骤

#### 34.1 创建 `warframe_agent/profile.py`

```python
@dataclass
class FinancialProfile:
    current_platinum: int          # 当前持有 P
    monthly_avg_income: float      # 月度平均收入
    available_budget: int          # 可用预算（current - reserved）
    last_updated: datetime

@dataclass
class TradingStyle:
    risk_tolerance: str            # conservative / moderate / aggressive
    primary_strategy: str          # mod_flip / set_profit / riven / collection
    avg_hold_time_hours: float     # 平均持仓时长（短线 vs 长线）
    win_rate: float                # 胜率（盈利交易占比）
    avg_profit_per_trade: float    # 单笔均利润

@dataclass
class GameProfile:
    mastery_rank: int              # MR 等级
    owned_warframes: list[str]     # 已拥有 Warframes
    owned_weapons: list[str]       # 已拥有武器
    foundry_in_progress: list[dict]  # 正在造的物品

@dataclass
class LongTermGoal:
    goal_id: str
    description: str               # "买 Trinity Prime 一套"
    target_platinum: int           # 目标 P 数
    deadline: date                 # 截止日期
    progress: float                # 进度 0.0-1.0
    sub_goals: list[str]           # 子目标
```

#### 34.2 自动归纳画像

从现有数据自动构建画像：
- 从 `trade_history.py` 计算胜率、均利润、平均持仓时长
- 从 `memory.py` 提取偏好
- 从对话历史归纳风格（"你常买 mod 拆套" → primary_strategy = mod_flip）

#### 34.3 集成到聊天提示词

在 `chat.py` 系统提示词中注入用户画像摘要：

```
[用户画像]
当前 P：1,250 | 风格：保守，主玩 Mod 翻转 | MR：22
当前目标：30 天攒 3000P 买 Saryn Prime（进度 42%）
持有：[200 个 Mod，3 套 Prime 拆件]
偏好：在线玩家、单笔不超过 200P

请基于以上画像定制建议。
```

#### 34.4 画像更新机制

- **被动更新**：每次交易后自动更新财务和交易风格
- **主动询问**：首次启动时询问 MR、目标、风险偏好
- **定期校准**：每周让用户确认 / 修改画像

#### 34.5 Web UI 画像面板

在侧边栏新增"我的画像"面板：
- 财务卡片（当前 P / 本月收入 / 可用预算）
- 风格雷达图（风险/收益/活跃度/多样性）
- 目标进度条
- 一键修改按钮

### 验收标准
- [ ] Agent 在所有建议中显式引用画像（"基于你保守的风格..."）
- [ ] 自动跳过已拥有的物品推荐
- [ ] 单笔建议自动控制在画像中的预算范围
- [ ] Web UI 画像面板可视化

---

## Phase 35：智能晨报 / 周报 + 决策日志

### 痛点
现在的"主动"只到价格阈值通知。用户想要的是"早上打开飞书，看到一条总结"，而不是 10 条孤立提醒。

### 目标
- 每日 8:30 推送"今日要点"摘要
- 每周日推送"本周回顾 + 下周展望"
- 所有 Agent 给出的建议进入决策日志，事后自动评估命中率

### 实施步骤

#### 35.1 新增 `warframe_agent/daily_brief.py`

```python
@dataclass
class DailyBrief:
    date: date
    morning_highlights: list[str]        # 3-5 条要点
    watchlist_changes: list[ItemChange]  # 关注列表变动
    market_events: list[str]             # Baro / Vault / 入侵
    suggested_actions: list[Action]      # 今日建议
    goal_progress: GoalSnapshot

def generate_daily_brief(profile: UserProfile) -> DailyBrief:
    """整合多个数据源生成晨报。"""
```

晨报示例：
```
🌅 今日要点（2026-05-16）

📊 你的关注：
  • Saryn Prime 一套 ↓18%（680P → 555P）— 距你的目标价仅差 55P
  • 充沛 ↑12%（80P → 90P）— 是否考虑出货？

🎯 市场事件：
  • Baro 明天来访（带 Primed Reach 等 5 件值得关注的）
  • Trinity Prime 进入 Vault 倒计时 8 天

💡 今日建议（基于你保守风格）：
  1. 卖出关注列表中"充沛 x2"——预计 +20P
  2. 等明天 Baro，预算预留 200P
  3. 你的目标"攒 3000P"还需 1740P，按当前节奏约 22 天

🏆 昨日决策回顾：
  • 我建议你 90P 买 Mesa Prime 头部 → 你买了 → 现价 110P → 浮盈 +20P ✅
```

#### 35.2 决策日志 `warframe_agent/decision_log.py`

```python
@dataclass
class Decision:
    decision_id: str
    timestamp: datetime
    type: str                       # buy/sell/hold/skip
    item_id: str
    suggested_price: int
    reasoning: str                  # Agent 给出建议时的理由
    user_action: str                # accepted / rejected / modified
    actual_price_at_action: int     # 用户实际操作时的价格
    outcome_24h: int                # 24h 后价格
    outcome_7d: int                 # 7 天后价格
    profit_loss: int                # 实际盈亏
    accuracy_score: float           # Agent 准确度评分
```

每次给出建议时调用 `log_decision()`，事后由后台 cron 更新 `outcome_*` 字段。

#### 35.3 周报模板 `weekly_report.py`

```
📅 本周回顾（2026-05-09 ~ 2026-05-15）

📈 你的战绩：
  • 完成交易 12 笔（赢 9 / 输 3）胜率 75%
  • 总盈利 +485P
  • 最佳交易：Mesa Prime 系统 (+85P)
  • 最差交易：Wukong Prime 头部 (-30P)

🎯 我的建议命中率：
  • 给出 18 条建议，你采纳 14 条
  • 采纳的 14 条中，盈利 11 条（命中率 79%）
  • 我表现最好的领域：Mod 翻转
  • 我表现最差的领域：Riven 估价 — 建议你这块多自主判断

🔮 下周展望：
  • Trinity Prime 进 Vault → 价格预计上涨 15-30%
  • 你的目标"攒 3000P"按当前节奏 18 天可达成
```

#### 35.4 推送通道

- 飞书机器人（已有）
- WxPusher（已有）
- Web UI 顶部 Banner
- 邮件（可选）

#### 35.5 时间调度

在 `monitor.py` 中：
```python
SCHEDULE = {
    "daily_brief": "0 8 30 * * *",   # 每天 8:30
    "weekly_report": "0 9 0 * * 0",   # 每周日 9:00
    "decision_followup": "0 0 * * * *", # 每小时更新决策结果
}
```

### 验收标准
- [ ] 飞书每天 8:30 自动收到晨报
- [ ] 决策日志记录 100% 的 Agent 建议
- [ ] 周报包含命中率统计和趋势
- [ ] 支持手动触发 `/brief` 和 `/weekly`

---

## Phase 36：截图识别（紫卡 / 聊天 / 库存）

### 痛点
玩家最常见的场景：
1. 截图紫卡 → 想知道值多少 P
2. 截图聊天频道挂牌 → 想知道是不是好价
3. 截图库存 → 想批量比价

打字输入"暴击率 110% 暴击伤害 95% 多重 80%"太繁琐。

### 目标
接入 **MiMo-V2.5 视觉模型**，支持图片直接上传识别。

### API 配置

| 配置项 | 值 |
|---|---|
| 提供商 | 小米 MiMo |
| API URL | `https://token-plan-cn.xiaomimimo.com/v1` |
| API Key | `tp-cncrawr7expx7rorq0utbr3s0itlnblm9b8n6mt0fu9z2etf` |
| 模型 | `MiMo-V2.5` |
| 接口规范 | OpenAI 兼容（chat completions + 图片 base64/URL） |

### 实施步骤

#### 36.1 新增 `warframe_agent/vision.py`

```python
"""图像识别模块 — 基于 MiMo-V2.5 视觉模型。"""
import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-cncrawr7expx7rorq0utbr3s0itlnblm9b8n6mt0fu9z2etf")
MIMO_MODEL = "MiMo-V2.5"


@dataclass
class VisionResult:
    success: bool
    data: dict           # 结构化结果
    raw_text: str        # 模型原始回复
    error: str | None = None


def _encode_image(image_path: Path) -> str:
    """将本地图片编码为 base64 data URL。"""
    with image_path.open("rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    suffix = image_path.suffix.lower().strip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    return f"data:{mime};base64,{b64}"


def _call_mimo_vision(image_url: str, prompt: str, response_format: str = "json") -> str:
    """调用 MiMo-V2.5 视觉接口。"""
    payload = {
        "model": MIMO_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
    }
    if response_format == "json":
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{MIMO_BASE_URL}/chat/completions",
                           json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ── 紫卡识别 ────────────────────────────────────────────────────────────

RIVEN_PROMPT = """这是一张 Warframe 游戏内紫卡（Riven Mod）截图。
请严格输出 JSON，包含以下字段：
{
  "weapon_name": "武器英文名（如 Rubico）",
  "mod_name": "紫卡名称（如 Visi-cron）",
  "polarity": "极性（madurai / vazarin / naramon）",
  "rank": 0-8,
  "rerolls": 0,
  "positive_attrs": [
    {"stat": "属性英文名（如 critical_chance）", "value": 90.5}
  ],
  "negative_attrs": [
    {"stat": "属性英文名", "value": -30.0}
  ]
}

如果某字段无法识别，置为 null。仅输出 JSON。"""


def parse_riven_screenshot(image_path: Path) -> VisionResult:
    """识别紫卡截图，提取武器名 + 属性 + 洗卡次数。"""
    try:
        image_url = _encode_image(image_path)
        raw = _call_mimo_vision(image_url, RIVEN_PROMPT, response_format="json")
        data = json.loads(raw)
        return VisionResult(success=True, data=data, raw_text=raw)
    except Exception as exc:
        logger.warning("紫卡识别失败：%s", exc)
        return VisionResult(success=False, data={}, raw_text="", error=str(exc))


# ── 聊天截图比价 ────────────────────────────────────────────────────────

CHAT_PROMPT = """这是一张 Warframe 游戏内 Trade Chat 频道截图。
识别其中所有挂牌信息，输出 JSON 数组：
[
  {
    "player": "玩家ID",
    "direction": "WTB / WTS",
    "items": [{"name": "物品名", "price": 100}]
  }
]
仅输出 JSON。"""


def parse_trade_chat_screenshot(image_path: Path) -> VisionResult:
    """识别 Trade Chat 截图，提取所有挂牌信息。"""
    try:
        image_url = _encode_image(image_path)
        raw = _call_mimo_vision(image_url, CHAT_PROMPT, response_format="json")
        data = json.loads(raw)
        return VisionResult(success=True, data={"listings": data}, raw_text=raw)
    except Exception as exc:
        return VisionResult(success=False, data={}, raw_text="", error=str(exc))


# ── 库存识别 ────────────────────────────────────────────────────────────

INVENTORY_PROMPT = """这是一张 Warframe 库存截图（武器 / Warframe / Mod / Prime 部件）。
识别所有可见物品，输出 JSON：
{
  "category": "warframe / weapon / mod / prime_part",
  "items": [
    {"name": "物品中英文名", "quantity": 1, "rank": "M30/X8 等"}
  ]
}
仅输出 JSON。"""


def parse_inventory_screenshot(image_path: Path) -> VisionResult:
    """识别库存截图，批量提取物品。"""
    try:
        image_url = _encode_image(image_path)
        raw = _call_mimo_vision(image_url, INVENTORY_PROMPT, response_format="json")
        data = json.loads(raw)
        return VisionResult(success=True, data=data, raw_text=raw)
    except Exception as exc:
        return VisionResult(success=False, data={}, raw_text="", error=str(exc))
```

#### 36.2 集成到 `chat.py`

新增工具：
```python
{
    "name": "analyze_screenshot",
    "description": "识别用户上传的 Warframe 截图（紫卡 / 聊天 / 库存）",
    "parameters": {
        "image_path": "图片本地路径",
        "screenshot_type": "auto / riven / chat / inventory"
    }
}
```

`auto` 模式让 MiMo 先判断截图类型，再走对应解析器。

#### 36.3 Web UI 上传支持

在聊天输入框旁加"📷 上传截图"按钮：
- 支持拖拽 / 粘贴板
- 上传后自动识别 → 调用对应工具 → 返回结构化结果
- 紫卡识别后自动调用紫卡查询，给出"这张紫卡值 80-150P"估价

#### 36.4 飞书图片消息支持

`feishu.py` 已支持文本，需扩展处理 `image_message`：
- 接收图片 → 下载 → 调用 `vision.py`
- 自动判断类型 → 给出对应分析

#### 36.5 紫卡估价整合

紫卡识别结果 → 自动调用 `search_rivens()` 比价：
```
你这张 Vermisplicer 紫卡：
  +暴击率 +135.5%
  +暴击伤害 +95.3%
  +多重 +83.4%
  -有效弹匣 -23.5%

📊 市场估价：120-180P（基于近 7 天 12 条同属性紫卡）
💡 建议：120P 收，160P 卖
```

#### 36.6 配置管理

新增 `warframe_agent/config.py`：
```python
# MiMo 视觉模型配置
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-cncrawr7expx7rorq0utbr3s0itlnblm9b8n6mt0fu9z2etf")
MIMO_MODEL = "MiMo-V2.5"
VISION_TIMEOUT = 30
VISION_CACHE_TTL = 3600  # 同一张图 1 小时内不重复识别
```

#### 36.7 缓存与速率限制

- 图片 hash 作为 cache key，避免重复识别
- 速率限制：每分钟最多 10 次调用
- 失败重试：3 次指数退避

#### 36.8 测试

`tests/test_vision.py`：
- Mock MiMo API 响应
- 测试图片编码、JSON 解析、错误处理
- 真实 API 测试（需 `RUN_INTEGRATION=1` 环境变量）

`tests/fixtures/screenshots/`：
- `riven_sample.png` / `riven_complex.png`
- `chat_sample.png`
- `inventory_sample.png`

### 验收标准
- [ ] 紫卡截图 → 自动提取武器名 + 属性，准确率 ≥ 90%
- [ ] 聊天截图 → 提取 ≥ 80% 挂牌信息
- [ ] 库存截图 → 识别 Prime 部件并批量比价
- [ ] Web UI 支持拖拽上传
- [ ] 飞书机器人支持图片消息
- [ ] 单图响应时间 < 5s（90 分位）

---

## Phase 37：Eval 框架 + 自我反思

### 痛点
没有评估体系 = Agent 质量在退化你也不知道。改了 prompt、换了模型，无法量化"变好了还是变差了"。

### 目标
- 建立 ~30 条真实查询的基准 benchmark
- 每次模型 / prompt 改动自动跑 eval
- Agent 每周自评建议命中率

### 实施步骤

#### 37.1 新增 `evals/` 目录

```
evals/
  benchmarks/
    queries.jsonl          # 30+ 条真实查询
    expected_outputs.jsonl # 期望输出（含 must_contain / must_not_contain）
  runners/
    run_eval.py
    judge.py               # 用 LLM 评分
  reports/
    YYYY-MM-DD.md          # 每次 eval 报告
```

#### 37.2 Benchmark 示例

`benchmarks/queries.jsonl`：
```jsonl
{"id": "riven-1", "query": "执法者双爆紫卡无负", "tags": ["riven"], "must_contain": ["magistar"], "must_not_contain": ["sancti_magistar", "vaykor_hek"]}
{"id": "riven-2", "query": "圣洁执法者紫卡", "tags": ["riven", "variant"], "must_contain": ["magistar"]}
{"id": "price-1", "query": "充沛多少钱", "tags": ["price"], "must_contain": ["arcane_energize", "P"]}
{"id": "set-1", "query": "我有 Saryn Prime 头部，缺啥", "tags": ["set"], "must_contain": ["机体", "系统"]}
{"id": "trade-1", "query": "我买了充沛 80p", "tags": ["trade", "auto-record"], "must_contain": ["已记录"]}
```

#### 37.3 评分维度

- **正确性**（hard）：must_contain 关键词全部命中
- **格式**（hard）：JSON / 表格结构正确
- **简洁性**（soft，LLM judge）：1-5 分
- **相关性**（soft，LLM judge）：1-5 分

#### 37.4 自动化运行

`run_eval.py`：
- 跑全部 benchmark，记录 pass/fail
- 调用 LLM judge 给软指标打分
- 生成对比报告（vs 上次基线）

CI 集成：
```yaml
# .github/workflows/eval.yml
on: [push]
jobs:
  eval:
    steps:
      - run: python evals/runners/run_eval.py --baseline main
      - run: python evals/runners/compare.py --threshold 0.95
```

#### 37.5 自我反思

每周日生成"Agent 自评报告"：
```
🪞 我的本周自评

✅ 我擅长的：
  • Mod 翻转推荐：命中率 85% (17/20)
  • Prime 套装比价：命中率 92% (12/13)

⚠️ 我需要改进的：
  • Riven 估价：命中率 58% (7/12)
    建议：你这块多依赖自己判断
  • Vault 时机：命中率 50% (3/6)
    问题：我对 Vault 价格反弹幅度估计偏低

📝 我从本周学到的：
  • Trinity Prime 进 Vault 后涨幅比预期大 30%
    我已更新 Vault 策略模型
```

### 验收标准
- [ ] 30+ benchmark 查询覆盖核心场景
- [ ] CI 跑 eval，回归阈值守护
- [ ] 周报包含 Agent 自评
- [ ] 每次大改动有 before/after 报告

---

## Phase 38：库存与 Foundry 集成

### 痛点
Agent 不知道你拥有什么，会推荐你已有的物品；不知道你 Foundry 在造什么，会建议你买已经在造的部件。

### 目标
集成 Warframe 官方 Profile API，自动同步：
- 持有 Warframes / 武器列表
- Foundry 进度（正在造的物品 + 完成时间）
- MR 等级
- 总在线时长

### 实施步骤

#### 38.1 调研官方 Profile API

Warframe 提供：
- `https://api.warframestat.us/{platform}/profile/{username}` (第三方)
- 官方 GraphQL 端点（需登录）

需要确认：
- 是否需要授权 token
- 同步频率限制

#### 38.2 新增 `warframe_agent/profile_sync.py`

```python
@dataclass
class GameInventory:
    warframes: list[OwnedItem]
    weapons: list[OwnedItem]
    prime_parts: list[OwnedItem]
    foundry: list[FoundryItem]
    last_synced: datetime

@dataclass
class FoundryItem:
    item_id: str
    completion_at: datetime
    rushable: bool
    rush_cost_p: int

def sync_from_warframe_api(username: str, platform: str) -> GameInventory:
    """从 warframestat.us 同步玩家库存。"""
```

#### 38.3 推荐过滤

修改 `investment.py`：
```python
def filter_owned_items(candidates, inventory):
    """过滤已拥有 / 正在造的物品。"""
    owned = {item.item_id for item in inventory.warframes + inventory.weapons}
    in_foundry = {item.item_id for item in inventory.foundry}
    return [c for c in candidates if c.item_id not in owned | in_foundry]
```

#### 38.4 Foundry 提醒

后台监控 Foundry：
- 完成前 1 小时提醒
- "你的 Saryn Prime 系统造完了，可以申领"

#### 38.5 Web UI 库存面板

侧边栏新增"我的库存"：
- Warframes / 武器分类
- 收藏过滤（已有 / 缺失）
- Foundry 倒计时

### 验收标准
- [ ] 自动同步玩家库存（每天 1 次）
- [ ] 推荐自动过滤已拥有
- [ ] Foundry 完成前 1 小时推送
- [ ] 修复"推荐你已经拥有的物品"问题

---

## Phase 39：插件系统 + 安全护栏

### 痛点
现在加新工具要改 `tool_router.py` + `chat.py`。第三方贡献门槛高。

安全护栏不足：删除历史 / 清空收藏 / 单笔超限都没二次确认。

### 目标
- 工具插件化：放进 `plugins/` 自动注册
- 二次确认机制：高风险操作前 confirm
- 审计日志：所有写操作可追溯

### 实施步骤

#### 39.1 插件协议

```python
# plugins/base.py
class Plugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def schema(self) -> dict: ...

    @abstractmethod
    def execute(self, args: dict, context: Context) -> str: ...

    @property
    def risk_level(self) -> str:
        return "low"  # low / medium / high
```

#### 39.2 自动注册

```python
# plugin_loader.py
def load_plugins(plugin_dir: Path = Path("plugins")):
    plugins = {}
    for py_file in plugin_dir.glob("*.py"):
        module = importlib.import_module(...)
        for cls in module.__dict__.values():
            if isinstance(cls, type) and issubclass(cls, Plugin):
                p = cls()
                plugins[p.name] = p
    return plugins
```

#### 39.3 安全护栏

```python
def execute_with_guards(tool: Plugin, args: dict, context: Context):
    if tool.risk_level == "high":
        if not context.user_confirmed:
            return ConfirmRequest(
                action=tool.name,
                args=args,
                preview=tool.preview(args),
            )
    log_audit(tool.name, args, context.user_id)
    return tool.execute(args, context)
```

#### 39.4 高风险操作清单

- 清空收藏 / 提醒
- 删除交易历史
- 单笔超过画像预算 50% 的建议
- 调用外部 API 写入

#### 39.5 审计日志

`data/audit_log.jsonl`：
```jsonl
{"ts": "2026-05-15T10:23:45Z", "user": "default", "action": "trade.add", "args": {...}, "result": "success"}
```

### 验收标准
- [ ] 新工具放进 plugins/ 自动可用
- [ ] 高风险操作触发确认对话
- [ ] 审计日志覆盖 100% 写操作
- [ ] 单笔超预算时强制 confirm

---

## Phase 40：跨设备 / 移动端

### 痛点
现在只能本地跑。游戏中、地铁上没法用。飞书部分解决了手机访问，但功能受限。

### 目标
- 云端部署，多设备同步
- Telegram / 微信小程序入口
- 浏览器扩展（在 warframe.market 页面叠加 Agent 建议）

### 实施步骤

#### 40.1 云端部署架构

```
┌─ 用户设备 ────┐    ┌─ 云端 ──────────────┐
│ 浏览器/扩展   │    │ FastAPI (公网)       │
│ Telegram      │ ←→ │   ↓                  │
│ 微信小程序    │    │ Agent Core           │
│ 飞书           │    │   ↓                  │
└────────────────┘    │ SQLite/Postgres      │
                      │   ↓                  │
                      │ Ollama/MiMo/Cloud    │
                      └──────────────────────┘
```

#### 40.2 数据同步

- 用户身份：JWT token
- 多端记忆同步：每个用户独立的 SQLite
- WebSocket 实时推送

#### 40.3 浏览器扩展

`extension/` 目录：
- manifest v3
- 在 warframe.market 物品页注入 Agent 面板
- 一键"问 Agent: 这个价合理吗？"
- 显示推荐挂单价 / 历史均价

#### 40.4 Telegram Bot

复用飞书的对话框架，增加 Telegram 适配器。

#### 40.5 微信小程序

简化版 Web UI：
- 查价
- 收藏 / 提醒
- 接收推送

### 验收标准
- [ ] 云端部署，HTTPS 访问
- [ ] 浏览器扩展上架（可选）
- [ ] Telegram bot 上线
- [ ] 多端记忆同步无冲突

---

## 依赖关系

```
Phase 34 (Profile)  ────┬────→ Phase 35 (晨报/周报)
                        │
                        └────→ Phase 38 (库存)
                                    ↓
Phase 36 (截图识别) ─────────────────┘
                                    ↓
Phase 37 (Eval) ────────────→ 持续应用于上述所有阶段
                                    ↓
Phase 39 (插件/护栏) ←──── 整合 ────┤
                                    ↓
Phase 40 (跨设备) ←─────── 最终交付
```

**建议路径**：

1. 先做 Phase 34 + 35（让 Agent "懂你"）
2. 再做 Phase 36（解决最大输入痛点）
3. 然后 Phase 37（给质量保障兜底）
4. 最后 Phase 38 / 39 / 40 按需选择

---

## 风险与权衡

### 模型成本
- MiMo-V2.5 视觉调用：估算单图 ~0.1 元
- 设置月度预算上限 + 缓存机制

### 数据隐私
- 用户画像、库存、交易记录是敏感数据
- 本地优先：默认数据不出本机
- 云端可选：用户主动开启同步

### Warframe ToS
- 严格遵守 ToS：不自动挂单 / 不自动 trade
- 仅做"建议生成"，不做"代用户操作"

### 维护成本
- 视觉识别准确率会随游戏 UI 改版下降
- 需要建立"用户反馈错误识别"的回流机制

---

## 当前可立即开始

**最低成本起步路径**（建议）：

1. **本周** —— Phase 34.1-34.3：创建 `profile.py` + 基础数据结构 + 系统提示词集成（2-3 天）
2. **下周** —— Phase 35.1-35.3：晨报生成器 + 决策日志（3-4 天）
3. **第三周** —— Phase 36：MiMo 视觉接入（紫卡识别优先）（5-6 天）

3 周后即可拿到一个"懂你 + 主动 + 能识图"的 Agent。

---

## 文档维护

- 每个 Phase 完成后，更新 `FeatureList.md` 和 `README.md`
- 每个 Phase 写一份 `docs/phase-XX-implementation.md` 记录决策和踩坑
- 重大架构变更同步 `AIArchitectureGuide.md` 和 `AgentArchitecture.md`
