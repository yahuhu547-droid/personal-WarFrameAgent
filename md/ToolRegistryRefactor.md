# ToolRegistry 工具体系改造记录

**阶段**: Phase 1.1 - Phase 5B + Phase 4.3  
**目标**: 借鉴 OpenHuman 智能体中的集中化工具、统一调度、长期记忆、专家子代理、结果压缩、安全护栏和可观察性思路，将 Warframe 智能体的工具定义、执行元数据、对话日志、工具调用历史、统计能力、调度底座、监控任务调度化、任务可观察性、长期交易记忆、模型上下文预算、Web/API 安全边界、外部内容 trust boundary 和专家工具逐步标准化。  
**状态**: OpenHuman 借鉴路线已完成：已完成 ToolRegistry、工具元数据、工具历史/统计、Scheduler 底座、PriceMonitor 主扫描 job、低频维护 jobs、grouped event checks job、Scheduler 只读可观察性 API、SQLite 长期交易记忆存储底座、主动推送写入 hook、Baro 推荐结构化写入、PriceMonitor 市场快照写入长期交易记忆、长期交易记忆只读查询 API、长期交易记忆 Web 观察面板、ChatAgent 用户查询安全摘要写入、ReAct / plan 模型上下文中的工具结果压缩与参数脱敏、`ToolResult` 显式 display/model_context 分层、领域工具 compact model_context、敏感交易工具 safe model_context、WebSocket 输入校验、配置 secrets allowlist serializer、前端动态 DOM XSS hardening、外部内容 untrusted-data fence，以及市场/紫卡/事件专家工具；主架构文档合并按用户要求暂不执行。

---

## 1. 改造背景

本轮改造来自对 `C:\Users\ASUSYBT4-P325\Downloads\openhuman-main` 的架构风格借鉴。最终没有直接复制 OpenHuman 功能，而是选择吸收其中更适合 Warframe 智能体长期演进的底座能力：

- 集中化 Tool Registry / Tool Loop
- 统一 Scheduler / 后台任务调度
- 长期记忆与交易历史沉淀
- 专家子代理 / 分工式能力拆分
- 工具结果压缩与上下文控制
- Prompt Injection / 外部内容安全防护
- Web 可观察性和任务面板

在本轮改造前，项目中的工具能力已经比较丰富，包括：

- 单品查价
- Prime 套装查询
- 缺件补齐
- 收藏 / 提醒扫描
- 价格提醒设置
- 价格趋势查询
- Mod 翻转
- 套装利润
- 投资顾问
- 游戏事件查询
- 深度分析
- Riven / 紫卡搜索
- plan 多步骤执行

但这些能力的定义和执行逻辑分散在不同位置：

- `warframe_agent/tool_router.py`
  - 维护 `TOOLS`
  - 维护 `TOOL_SCHEMAS`
  - 负责 ReAct 工具路由、plan 执行、工具调用解析

- `warframe_agent/chat.py`
  - `ChatAgent._execute_tool_call()` 中维护长 if-chain
  - 每个工具的实际执行逻辑硬编码在聊天 Agent 内部

这种结构短期可用，但继续扩展后会带来几个问题：

1. 工具定义和执行逻辑容易不一致。
2. 新增工具需要同时修改多处代码。
3. 工具调用缺少统一的执行结果结构。
4. 难以记录工具调用历史、耗时、错误和参数摘要。
5. 后续做 Web 可观察性、调度中心、专家子代理时缺少统一底座。

因此，本轮改造的核心目标是：

> 建立一个后端统一 ToolRegistry，让工具定义、schema 导出、执行入口、执行元数据和日志持久化逐步标准化。

---

## 2. Phase 1.1：统一 ToolRegistry

### 2.1 新增文件

新增：

```text
warframe_agent/tool_registry.py
```

核心结构：

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    required: tuple[str, ...] = ()
    handler: Callable[[dict[str, Any]], str | None] | None = None
    expose_schema: bool = True
```

```python
@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str | None = None
    error: str | None = None
```

```python
class ToolRegistry:
    def register(self, spec: ToolSpec) -> None
    def get(self, name: str) -> ToolSpec | None
    def names(self) -> set[str]
    def with_handler(self, name: str, handler: Callable) -> None
    def list_tools(self) -> list[dict]
    def list_tool_schemas(self) -> list[dict]
    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult
```

### 2.2 默认工具注册表

新增：

```python
def create_default_tool_registry() -> ToolRegistry
```

默认注册以下工具：

| 工具名 | 说明 |
|------|------|
| `query_price` | 查询单个物品实时价格 |
| `query_set` | 查询 Prime 套装价格 |
| `query_missing_parts` | 计算套装缺件补齐成本 |
| `scan_favorites` | 扫描收藏和提醒 |
| `set_alert` | 设置价格提醒 |
| `price_trend` | 查询价格趋势 |
| `general_chat` | 一般闲聊，不进入 Ollama function schema |
| `mod_flipper` | Mod 翻转扫描 |
| `set_profit` | Prime 套装利润扫描 |
| `investment_advisor` | 投资顾问 |
| `plan` | 多步骤任务分解 |
| `query_events` | 查询游戏事件 |
| `deep_analysis` | 云端深度分析 |
| `riven_search` | Riven / 紫卡搜索 |

### 2.3 改造 `tool_router.py`

原先 `TOOL_SCHEMAS` 和 `TOOLS` 是手写列表。

现在改为由默认注册表生成：

```python
_DEFAULT_REGISTRY = create_default_tool_registry()
TOOL_SCHEMAS = _DEFAULT_REGISTRY.list_tool_schemas()
TOOLS = _DEFAULT_REGISTRY.list_tools()
```

这样保留了旧导入方式：

```python
from warframe_agent.tool_router import TOOL_SCHEMAS, TOOLS
```

同时避免工具定义重复维护。

### 2.4 改造 `ChatAgent`

`ChatAgent` 初始化时创建实例级注册表：

```python
self.tool_registry = self._build_tool_registry()
```

新增：

```python
def _build_tool_registry(self):
    registry = create_default_tool_registry()
    registry.with_handler("query_price", self._tool_query_price)
    ...
    return registry
```

原来的 `_execute_tool_call()` 长 if-chain 被替换为统一执行入口：

```python
def _execute_tool_call(self, tool_call, message: str = "") -> str | None:
    args = dict(tool_call.arguments)
    if message and "__message" not in args:
        args["__message"] = message
    result = self.tool_registry.execute(tool_call.name, args)
    return result.content if result.ok else None
```

实际业务逻辑拆成多个私有 handler：

- `_tool_query_price()`
- `_tool_query_set()`
- `_tool_query_missing_parts()`
- `_tool_scan_favorites()`
- `_tool_set_alert()`
- `_tool_price_trend()`
- `_tool_general_chat()`
- `_tool_mod_flipper()`
- `_tool_set_profit()`
- `_tool_investment_advisor()`
- `_tool_query_events()`
- `_tool_deep_analysis()`
- `_tool_riven_search()`

### 2.5 保留行为

本阶段没有重写聊天主流程。

以下路径保持原样：

- 确定性紫卡解析
- Baro 推荐
- Baro 追问
- 游戏事件快路径
- watchlist 命令
- 普通物品上下文匹配
- Web API / WebSocket 返回格式

---

## 3. Phase 1.2：内部工具执行元数据

### 3.1 新增执行元数据结构

在 `tool_registry.py` 中新增：

```python
@dataclass(frozen=True)
class ToolExecutionMetadata:
    tool_name: str
    args_summary: dict[str, Any]
    ok: bool
    error: str | None
    duration_ms: float
    timestamp: str
    message_context: str | None = None
```

并扩展 `ToolResult`：

```python
@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str | None = None
    error: str | None = None
    metadata: ToolExecutionMetadata | None = None
```

### 3.2 记录内容

每次工具执行都会生成 metadata，包括：

- 工具名
- 参数摘要
- 是否成功
- 错误信息
- 执行耗时
- UTC ISO 时间戳
- 用户消息上下文

覆盖所有执行路径：

- 成功执行
- 未知工具
- 缺少 required 参数
- 工具未绑定 handler
- handler 抛异常

### 3.3 参数摘要与脱敏

新增摘要逻辑：

- `_summarize_arguments()`
- `_summarize_value()`
- `_is_sensitive_key()`
- `_build_metadata()`

敏感 key 会被写为：

```text
[REDACTED]
```

当前脱敏匹配：

- `password`
- `token`
- `secret`
- `api_key`
- `apikey`
- `authorization`
- `cookie`

`__message` 不进入 `args_summary`，而是单独存入 `message_context`。

### 3.4 ChatAgent 捕获 metadata

`ChatAgent` 新增：

```python
self.tool_execution_metadata = []
```

`_execute_tool_call()` 执行后追加：

```python
if result.metadata:
    self.tool_execution_metadata.append(result.metadata)
```

ReAct 路径也传入用户消息上下文：

```python
tool_executor=lambda tc: self._execute_tool_call(tc, message)
```

### 3.5 不暴露给用户

本阶段只在内存中保存 metadata。

不会写入：

- 用户回复
- ReAct tool-role message
- Web API 响应
- AgentMemory
- conversation log

---

## 4. Phase 1.3：持久化工具执行元数据

### 4.1 复用现有 conversation log

项目已有：

```text
warframe_agent/conversation_log.py
```

其中 `ConversationEntry` 已经预留字段：

```python
tool_calls: list[dict] | None = None
```

本阶段复用该字段，将工具调用摘要写入：

```text
data/conversation_logs.jsonl
```

### 4.2 持久化格式

每条 tool call 写入：

```python
{
    "tool_name": meta.tool_name,
    "args_summary": meta.args_summary,
    "ok": meta.ok,
    "error": meta.error,
    "duration_ms": round(meta.duration_ms, 2),
    "timestamp": meta.timestamp,
}
```

明确不写入：

- raw `arguments`
- raw tool result
- LLM prompt
- ReAct messages
- `message_context`

`message_context` 不写入的原因是它与 `ConversationEntry.user_message` 信息重复。

### 4.3 ChatAgent 日志消费

`_log_answer()` 现在会消费本轮工具 metadata：

```python
tool_calls = self._consume_tool_execution_metadata()
```

并写入：

```python
ConversationEntry(
    user_message=message,
    assistant_reply=reply,
    tool_calls=tool_calls or None,
    contexts=[ctx.item_id for ctx in contexts] if contexts else None,
)
```

新增：

```python
def _consume_tool_execution_metadata(self) -> list[dict]:
    records = [_tool_metadata_to_dict(meta) for meta in self.tool_execution_metadata]
    self.tool_execution_metadata = []
    return records
```

这样可以避免上一轮工具调用泄漏到下一轮对话日志。

### 4.4 JSON-safe 转换

新增：

```python
def _tool_metadata_to_dict(meta) -> dict
```

```python
def _json_safe_tool_value(value)
```

用于保证写入 JSONL 的 `args_summary` 是安全可序列化结构：

- 基础类型原样保留
- 字符串限制长度
- dict key 转字符串
- list / tuple 限制长度并递归转换
- 其它对象转为截断后的 `repr()`

---

## 5. Phase 1.4：后端只读工具调用历史查询

### 5.1 查询入口

在 `warframe_agent/conversation_log.py` 中新增：

```python
def query_tool_call_history(
    limit: int = 50,
    tool_name: str | None = None,
    ok: bool | None = None,
    session_id: str | None = None,
) -> list[dict]
```

该函数复用现有 `load_conversations()`，从 `data/conversation_logs.jsonl` 读取对话日志，并将每条 `ConversationEntry.tool_calls` 展开为独立工具调用记录。

### 5.2 返回字段

每条工具调用历史返回：

```python
{
    "tool_timestamp": tool_call.get("timestamp"),
    "tool_name": tool_call.get("tool_name"),
    "args_summary": tool_call.get("args_summary"),
    "ok": tool_call.get("ok"),
    "error": tool_call.get("error"),
    "duration_ms": tool_call.get("duration_ms"),
    "conversation_timestamp": entry.timestamp,
    "session_id": entry.session_id,
    "contexts": entry.contexts,
}
```

明确不返回：

- 完整 `user_message`
- `assistant_reply`
- raw `arguments`
- raw tool result / `content`
- LLM prompt
- ReAct messages
- `message_context`

### 5.3 查询行为

当前支持：

- `limit`：限制返回最近 N 条，`limit <= 0` 返回空列表
- `tool_name`：按工具名过滤
- `ok`：按成功 / 失败状态过滤
- `session_id`：按会话过滤

排序规则：

- 对话记录从新到旧读取
- 同一轮对话内多个工具调用也从新到旧展开
- 返回结果始终是最近的匹配工具调用优先

兼容行为：

- 日志文件不存在时返回空列表
- malformed JSONL 行沿用 `load_conversations()` 的跳过行为
- 没有 `tool_calls`、`tool_calls=None` 或 `tool_calls` 非 list 的旧日志会被忽略
- list 内非 dict 的 tool call 项会被忽略

### 5.4 本阶段边界

本阶段只做后端 helper。

没有新增：

- Web UI 工具调用时间线
- `/api/tool_events` 或 `/api/tool_calls`
- 工具调用统计聚合
- SQLite 工具日志

---

## 6. Phase 1.5：后端工具调用统计

### 6.1 统计入口

在 `warframe_agent/conversation_log.py` 中新增：

```python
def query_tool_call_stats(
    limit: int = 500,
    tool_name: str | None = None,
    session_id: str | None = None,
) -> dict
```

该函数复用 `query_tool_call_history()` 返回的安全工具调用历史，只基于安全字段做聚合统计。

### 6.2 输出结构

空统计返回：

```python
{
    "total_calls": 0,
    "success_count": 0,
    "failure_count": 0,
    "unknown_count": 0,
    "success_rate": 0.0,
    "duration_ms": {
        "count": 0,
        "avg": None,
        "min": None,
        "max": None,
    },
    "by_tool": {},
    "top_tools": [],
}
```

有数据时会返回：

- 整体调用数
- 成功数
- 失败数
- unknown 数
- 成功率
- 整体耗时统计
- `by_tool` 分工具统计
- `top_tools` 高频工具列表

### 6.3 统计规则

当前规则：

- `ok is True` 计入成功
- `ok is False` 计入失败
- `ok` 缺失或不是 bool 时计入 `unknown_count`
- `duration_ms` 只有 int / float 且不是 bool 时参与耗时统计
- `success_rate = success_count / total_calls`，无调用时为 `0.0`
- 成功率保留 4 位小数
- 平均耗时保留 2 位小数
- `top_tools` 按调用次数降序，次数相同按工具名稳定排序
- 工具名缺失时归入 `"unknown"`

### 6.4 安全边界

统计结果不返回：

- `args_summary`
- raw `arguments`
- raw tool result / `content`
- `error` 原文
- 完整 `user_message`
- `assistant_reply`
- `contexts`
- LLM prompt
- `message_context`

### 6.5 本阶段边界

本阶段只做后端统计 helper。

没有新增：

- Web UI 统计面板
- `/api/tool_stats` 或类似 endpoint
- 时间窗口过滤
- P95 / P99 耗时
- 常见失败原因文本聚类
- SQLite 工具日志

---

## 7. Phase 2.1：统一调度中心底座

### 7.1 新增文件

新增：

```text
warframe_agent/scheduler.py
```

该文件提供一个独立、无业务依赖、可测试的调度底座。当前没有接入 Web / CLI，也没有迁移 `PriceMonitor` 中的业务任务。

### 7.2 核心结构

新增：

```python
@dataclass(frozen=True)
class IntervalSchedule:
    seconds: int
    run_immediately: bool = False
```

```python
@dataclass
class ScheduledJob:
    job_id: str
    name: str
    callback: Callable[[], Any]
    schedule: IntervalSchedule
    enabled: bool = True
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    run_count: int = 0
    error_count: int = 0
```

```python
@dataclass(frozen=True)
class JobRunResult:
    job_id: str
    name: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    success: bool
    error: str | None = None
```

### 7.3 Scheduler API

新增：

```python
class Scheduler:
    def add_interval_job(...)
    def remove_job(self, job_id: str) -> bool
    def get_job(self, job_id: str) -> ScheduledJob | None
    def list_jobs(self) -> list[ScheduledJob]
    def due_jobs(self, now: datetime | None = None) -> list[ScheduledJob]
    def run_due(self, now: datetime | None = None) -> list[JobRunResult]
    def tick(self, now: datetime | None = None) -> list[JobRunResult]
```

行为：

- 支持 interval job 注册
- 拒绝重复 `job_id`
- 拒绝非正 interval
- `run_immediately=True` 时立即 due
- `due_jobs()` 只返回 enabled 且到期的 job
- 执行顺序保持注册顺序
- callback 返回值暂时忽略
- 异常 job 不阻断其它 job
- 成功 / 失败都会记录运行结果并重排下一次执行时间
- 过期 job 每次 tick 只执行一次，不做 catch-up storm
- 使用 fixed-delay 语义：`next_run_at = finished_at + interval`

### 7.4 SchedulerRunner

新增：

```python
class SchedulerRunner:
    def start(self) -> None
    def stop(self, timeout: float = 5.0) -> None
    @property
    def is_running(self) -> bool
```

行为：

- runner 线程为 daemon
- `start()` / `stop()` 幂等
- 使用 `threading.Event.wait()`，避免无法及时停止的 `time.sleep()`
- `poll_seconds` 必须大于 0

### 7.5 线程与错误边界

当前实现：

- Scheduler 内部使用锁保护 job registry
- `run_due()` 有重入保护，避免同一 scheduler 同时执行两轮 due jobs
- callback 不在 registry 锁内执行，避免长任务阻塞 `list_jobs()` / `remove_job()`
- `JobRunResult.error` 使用异常类型和截断后的异常消息
- 本阶段不持久化 job 和 run history

### 7.6 本阶段边界

本阶段只建立调度底座。

没有新增：

- 迁移 `PriceMonitor` 任务
- Web / CLI 启动 scheduler
- 持久化 Job / RunHistory
- cron 表达式
- timezone / jitter
- 重试策略
- 并发执行 job
- Web UI / API

---

## 8. Phase 2.2：PriceMonitor 接入 Scheduler 主扫描 Job

### 8.1 接入目标

Phase 2.2 没有一次性迁移所有后台任务，而是先将 `PriceMonitor` 的主扫描循环接入 Scheduler：

- 保留 `PriceMonitor.start()` / `stop()` / `_thread` / `_stop_event` 外部行为
- 保留 Web / CLI 启动方式
- 保留价格提醒、watchlist、主动推送、事件提醒、Baro、日报等业务逻辑
- 只让主扫描循环通过 `Scheduler.tick()` 触发

### 8.2 新增常量和状态

在 `warframe_agent/monitor.py` 中新增：

```python
PRICE_MONITOR_SCAN_JOB_ID = "price_monitor.scan"
PRICE_MONITOR_SCAN_JOB_NAME = "Price monitor scan"
```

`PriceMonitor.__init__()` 新增：

```python
self._scheduler: Scheduler | None = None
```

### 8.3 Scheduler 构建

新增：

```python
def _build_scheduler(self) -> Scheduler:
    scheduler = Scheduler()
    scheduler.add_interval_job(
        PRICE_MONITOR_SCAN_JOB_ID,
        PRICE_MONITOR_SCAN_JOB_NAME,
        self._run_scan_cycle,
        self.interval_seconds,
        run_immediately=True,
    )
    return scheduler
```

该 job 使用 `monitor.interval_seconds` 作为 interval，并且 `run_immediately=True`，保持原先 `start()` 后立即执行第一轮扫描的行为。

### 8.4 单轮扫描抽取

原 `_run()` 循环中的一轮业务逻辑被抽取为：

```python
def _run_scan_cycle(self) -> None
```

该方法保留原有：

- `scan_once()` 调用
- alert / watch 通知入队
- callbacks 触发
- 机会检测
- 价格突变检测
- 主动推送
- suggestion 写入 memory
- 知识库更新
- 目标生成
- 自学习闭环
- 裂缝 / 世界循环 / Baro / 事件驱动推送
- 每日报告
- 顶层异常捕获和 `logger.warning("监控主循环异常: %s", exc)`

### 8.5 主循环改造

`start()` 现在会创建 fresh scheduler，然后继续创建原有 daemon thread：

```python
self._scheduler = self._build_scheduler()
self._thread = threading.Thread(target=self._run, daemon=True)
```

`_run()` 改为：

```python
while not self._stop_event.is_set():
    scheduler.tick()
    self._stop_event.wait(self.interval_seconds)
```

这样实现了：

- 第一轮扫描仍立即执行
- 每轮扫描后仍等待 `interval_seconds`
- `stop()` 仍通过 `_stop_event` 及时停止
- 双重 `start()` 不重复创建线程或 scheduler
- Web / CLI 不需要任何改动

### 8.6 本阶段边界

本阶段没有做：

- 把知识更新、目标生成、自学习、裂缝、世界循环、Baro、事件推送、日报拆成独立 jobs
- 用 `SchedulerRunner` 替代 `PriceMonitor` 自己的线程
- Web / CLI 显式启动 scheduler
- Job / RunHistory 持久化
- Web UI / API

---

## 9. Phase 2.3：拆分 PriceMonitor 低频维护 Scheduler Jobs

### 9.1 拆分目标

Phase 2.3 继续沿用 Phase 2.2 的保守迁移策略：不替换 `PriceMonitor` 生命周期，也不改 Web / CLI 启动方式，只把已经具备低频周期语义的维护任务拆成独立 scheduler jobs。

本阶段拆分：

- 知识库更新
- 自动目标生成
- 自学习闭环

继续保留在主扫描 job 内：

- `scan_once()`
- alert / watch 通知入队和 callbacks
- 机会检测
- 价格突变检测
- 主动推送
- suggestion 写入 memory
- 裂缝 / 世界循环 / Baro / 事件驱动推送
- 每日报告

这样可以避免改变首轮扫描和用户可见通知行为。

### 9.2 Scheduler 首次延迟

`Scheduler.add_interval_job()` 新增：

```python
initial_delay_seconds: int | None = None
```

行为：

- `run_immediately=True` 时仍然立即 due
- 非立即任务可用 `initial_delay_seconds` 指定首次运行时间
- 后续仍保持 fixed-delay：`next_run_at = finished_at + seconds`
- `initial_delay_seconds < 0` 会报错
- `run_immediately=True` 不能同时传 `initial_delay_seconds`

该能力用于把旧的“每 N 次扫描”语义映射成 scheduler 时间：主扫描 job 会立即执行第一轮，所以第 N 次扫描对应的首次延迟是 `(N - 1) * interval_seconds`。

### 9.3 新增维护 jobs

`warframe_agent/monitor.py` 新增：

```python
PRICE_MONITOR_KNOWLEDGE_UPDATE_JOB_ID = "price_monitor.knowledge_update"
PRICE_MONITOR_KNOWLEDGE_UPDATE_JOB_NAME = "Price monitor knowledge update"
PRICE_MONITOR_GOAL_GENERATION_JOB_ID = "price_monitor.goal_generation"
PRICE_MONITOR_GOAL_GENERATION_JOB_NAME = "Price monitor goal generation"
PRICE_MONITOR_SELF_LEARNING_JOB_ID = "price_monitor.self_learning"
PRICE_MONITOR_SELF_LEARNING_JOB_NAME = "Price monitor self learning"
```

`PriceMonitor.__init__()` 新增：

```python
self._last_scan_result: ScanResult | None = None
```

`_run_scan_cycle()` 现在只记录最新扫描结果：

```python
self._scan_cycle_count += 1
self._last_scan_result = scan
```

原本内联的低频维护调用被移动到 no-arg scheduler callbacks：

```python
def _run_knowledge_update_job(self) -> None:
    scan = self._last_scan_result
    if scan is None:
        return
    self._run_knowledge_update(scan)
```

```python
def _run_goal_generation_job(self) -> None:
    self._run_goal_generation()
```

```python
def _run_self_learning_job(self) -> None:
    memory = AgentMemory.load(self.memory_path)
    self._run_self_learning(memory)
```

### 9.4 调度间隔

维护 jobs 的 interval 继续复用现有配置：

| Job | interval | initial delay |
|-----|----------|---------------|
| `price_monitor.knowledge_update` | `interval_seconds * config.KNOWLEDGE_UPDATE_INTERVAL` | `interval_seconds * (config.KNOWLEDGE_UPDATE_INTERVAL - 1)` |
| `price_monitor.goal_generation` | `interval_seconds * config.GOAL_GENERATION_INTERVAL` | `interval_seconds * (config.GOAL_GENERATION_INTERVAL - 1)` |
| `price_monitor.self_learning` | `interval_seconds * config.PATTERN_DISCOVERY_INTERVAL` | `interval_seconds * (config.PATTERN_DISCOVERY_INTERVAL - 1)` |

scan job 仍然第一个注册，并且仍然是唯一初始 due job。

### 9.5 本阶段边界

本阶段没有做：

- 拆分裂缝、开放世界循环、Baro、事件驱动推送、每日报告
- 使用 `SchedulerRunner` 替代 `PriceMonitor` 自有线程
- 并发执行 job
- Job / RunHistory 持久化
- Web UI / API

---

## 10. Phase 2.4：拆分事件类后台任务

### 10.1 拆分目标

Phase 2.4 没有一次性把所有事件检查拆成多个独立 jobs，而是先引入一个 grouped event checks job，将事件类后台检查从主扫描循环中移出，同时保留既有首轮通知语义和执行顺序。

本阶段从 `_run_scan_cycle()` 中移出：

- `_check_fissure_alerts()`
- `_check_cycle_alerts()`
- `_check_baro_recommendation()`
- `_check_event_driven_push()`
- `_check_daily_report()`

继续保留在主扫描 job 内：

- `scan_once()`
- alert / watch 通知入队和 callbacks
- 机会检测
- 价格突变检测
- 主动推送
- suggestion 写入 memory
- `_scan_cycle_count` 和 `_last_scan_result` 更新

### 10.2 新增 grouped event checks job

`warframe_agent/monitor.py` 新增：

```python
PRICE_MONITOR_EVENT_CHECKS_JOB_ID = "price_monitor.event_checks"
PRICE_MONITOR_EVENT_CHECKS_JOB_NAME = "Price monitor event checks"
```

`PriceMonitor.__init__()` 新增：

```python
self._event_checks_last_scan_cycle_count = 0
```

新增：

```python
def _run_event_checks_job(self) -> None:
    if self._scan_cycle_count <= self._event_checks_last_scan_cycle_count:
        return
    self._event_checks_last_scan_cycle_count = self._scan_cycle_count
    try:
        self._check_fissure_alerts()
        self._check_cycle_alerts()
        self._check_baro_recommendation()
        self._check_event_driven_push()
        self._check_daily_report()
    except Exception as exc:
        logger.warning("事件检查任务异常: %s", exc)
        raise
```

该 job 保留原先事件检查顺序：裂缝 → 世界循环 → Baro → 事件驱动推送 → 每日报告。

### 10.3 调度行为

`_build_scheduler()` 现在的注册顺序为：

1. `price_monitor.scan`，立即 due
2. `price_monitor.event_checks`，立即 due
3. `price_monitor.knowledge_update`，延迟 due
4. `price_monitor.goal_generation`，延迟 due
5. `price_monitor.self_learning`，延迟 due

`event_checks` 使用 `monitor.interval_seconds` 作为 interval，当前不新增独立配置。

首轮行为：

- 第一轮 scheduler tick 会先执行 scan job，再执行 event checks job。
- 裂缝、Baro、Vault / Prime Access、日报仍可在首轮 scan 完成后立即触发。
- 开放世界循环仍由 `_check_cycle_alerts()` 自身保持首轮 baseline、不推送。
- 如果尚未完成任何 scan cycle，event checks job 会安全跳过。

### 10.4 本阶段边界

本阶段没有做：

- 把五个事件检查拆成五个独立 jobs
- 为不同事件检查设置不同 interval
- 改变 `PriceMonitor._run()` 的 tick 频率
- 用 `SchedulerRunner` 替代 `PriceMonitor` 自有线程
- Job / RunHistory 持久化
- Web UI / API 可观察性
- 修改事件去重策略或每日报告重试语义

---

## 11. Phase 2.5：Scheduler 可观察性 API

### 11.1 实现目标

Phase 2.5 补齐 Scheduler 调度化后的只读观测入口，让 Web/API 层可以查看后台任务状态，而不需要直接读取内部对象。

本阶段新增：

- `serialize_scheduled_job()`
- `serialize_scheduler_jobs()`
- `PriceMonitor.scheduler_status_snapshot()`
- `GET /api/scheduler/status`

### 11.2 Scheduler snapshot

`warframe_agent/scheduler.py` 新增只读序列化 helper，输出普通 dict/list：

```python
def serialize_scheduled_job(job: ScheduledJob) -> dict[str, Any]:
    ...


def serialize_scheduler_jobs(scheduler: Scheduler) -> list[dict[str, Any]]:
    ...
```

公开字段：

- `job_id`
- `name`
- `enabled`
- `schedule.type`
- `schedule.seconds`
- `schedule.run_immediately`
- `next_run_at`
- `last_run_at`
- `run_count`
- `error_count`

安全边界：

- 不暴露 `callback`
- 不暴露 callback 返回值
- 不暴露异常文本
- 不返回 mutable `ScheduledJob` 对象

### 11.3 Monitor snapshot

`PriceMonitor.scheduler_status_snapshot()` 返回：

```json
{
  "running": false,
  "has_scheduler": true,
  "total": 5,
  "jobs": []
}
```

该方法只读：

- 不调用 `start()`
- 不调用 `_build_scheduler()`
- 不调用 `tick()`
- 不改变 job `run_count` / `error_count`
- 未启动 scheduler 时安全返回空 jobs

### 11.4 Web API

新增：

```http
GET /api/scheduler/status
```

用途：为后续 Web 任务面板和后台任务排障提供基础状态数据。当前只做只读 API，不做 UI、不做 job 管理操作。

### 11.5 本阶段边界

本阶段没有做：

- Web UI 面板
- 手动触发 job
- 启停 job
- 修改 job interval
- 记录 last error / last duration
- 持久化 Job / RunHistory
- 将 grouped event checks 拆成 per-method jobs
- 主架构文档整合

---

## 12. Phase 3.1：SQLite 长期交易记忆存储底座

### 12.1 实现目标

Phase 3.1 开始落地 OpenHuman 借鉴路线中的长期记忆主线。本阶段先建立 SQLite 存储底座，不接入 ChatAgent / Monitor 自动写入，避免在记录粒度和隐私边界未稳定前自动保存更多用户数据。

新增：

```text
warframe_agent/trading_memory.py
```

核心类：

```python
TradingMemoryDB
```

### 12.2 数据模型和表

新增四类长期记忆 dataclass：

- `UserQueryMemory`
- `MarketSnapshotMemory`
- `RecommendationMemory`
- `PushHistoryMemory`

对应 SQLite 表：

- `user_queries`
- `market_snapshots`
- `recommendations`
- `push_history`

这些表统一包含 `timestamp`，并为按时间、物品、来源和类型查询建立索引。

### 12.3 存储能力

`TradingMemoryDB` 提供：

- 用户查询记录：`record_user_query()` / `get_recent_user_queries()`
- 市场快照记录：`record_market_snapshot()` / `get_market_snapshots()`
- 推荐记录：`record_recommendation()` / `get_recommendations()`
- 推送历史记录：`record_push()` / `get_push_history()`
- 旧数据清理：`cleanup_old_data()`
- 显式关闭：`close()`

实现风格与 `PriceHistoryDB` 保持一致：

- 单 SQLite connection
- `threading.Lock`
- `check_same_thread=False`
- WAL 模式
- tempfile DB 测试隔离

### 12.4 安全和隐私边界

本阶段只提供显式写入 API：调用方传什么字段，数据库才保存什么字段。

当前没有做：

- 自动保存完整聊天内容
- 自动保存 ChatAgent 回复
- 自动记录 PriceMonitor 扫描结果
- Web API / UI 查询入口
- tool_calls / scheduler run history 迁移

metadata / payload 使用 JSON 保存；读取到损坏 JSON 时返回 `{}`，避免查询失败。

### 12.5 本阶段边界

本阶段没有做：

- ChatAgent 自动记录用户查询
- PriceMonitor 自动记录建议、推送或市场快照
- Web API / UI
- 长期记忆摘要 / 压缩
- 隐私设置 UI
- 主架构文档整合

---

## 13. Phase 3.2：长期交易记忆写入 Hook

### 13.1 实现目标

Phase 3.2 将 `TradingMemoryDB` 接入第一组低风险生产路径：`PriceMonitor` 已经结构化生成的主动推送。当前只记录 proactive push / event-driven push，不记录 ChatAgent 原始用户消息或助手回复。

### 13.2 可选注入

`PriceMonitor` 新增可选参数：

```python
trading_memory_db=None
```

默认值为 `None`，因此普通运行和测试不会隐式创建长期记忆数据库。只有调用方显式注入 `TradingMemoryDB` 时，才会写入 push history。

### 13.3 写入范围

当前写入：

- `_run_proactive_push()` 生成的规则驱动主动推送
- `_check_event_driven_push()` 生成的 Prime Vault / Prime Access 推送

写入字段：

- `push_type`
- `message`
- `item_name = push.item_id`
- metadata：`source`、`item_id`、`item_display`、`priority`、`action_suggestion`、`data`，以及结构化 event / suggestion 信息

### 13.4 安全边界

本阶段明确不写入：

- raw user query
- assistant reply
- prompt
- raw tool arguments
- chat message

DB 写入是 best-effort：`record_push()` 异常只记录 debug，不影响已有 push callback。

### 13.5 本阶段边界

本阶段没有做：

- ChatAgent 用户查询写入
- ChatAgent 回复写入
- Baro 推荐写入
- 每日报告写入
- 市场快照自动写入 TradingMemoryDB
- Web API / UI
- 主架构文档整合

---

## 14. Phase 3.3：Baro 推荐写入长期交易记忆

### 14.1 实现目标

Phase 3.3 继续扩展长期交易记忆写入范围，但仍然只接入已经结构化、低隐私风险的数据。本阶段选择 `PriceMonitor._check_baro_recommendation()` 生成的 Baro 推荐，不接入高频市场快照。

选择 Baro 推荐的原因：

- `analyze_baro_inventory()` 已经返回结构化 `BaroRecommendation` 列表。
- 推荐天然适合写入 `TradingMemoryDB.record_recommendation(recommendation_type="baro")`。
- Baro 推荐由现有 `_baro_recommendation_sent` 按 `start_time` 去重，不会高频写入。
- 不需要解析格式化报告文本，也不需要保存玩家订单详情。

### 14.2 写入 Hook

`PriceMonitor` 新增私有 helper：

```python
def _record_baro_recommendation_memory(self, recommendation, baro_event) -> None:
    ...
```

`_check_baro_recommendation()` 在 `analyze_baro_inventory()` 返回推荐后，对每条推荐调用该 helper，然后再生成格式化报告：

```python
recommendations = analyze_baro_inventory(baro_event, self.order_fetcher)
for recommendation in recommendations:
    self._record_baro_recommendation_memory(recommendation, baro_event)
report = format_baro_report(recommendations)
```

这样可以证明长期记忆只依赖结构化推荐对象，而不是依赖 `format_baro_report()` 的完整文本。

### 14.3 写入字段

写入 `recommendations` 表：

```python
self.trading_memory_db.record_recommendation(
    item_name=recommendation.market_id,
    recommendation_type="baro",
    reason=recommendation.reason,
    payload={...},
)
```

payload 只包含可查询的结构化字段：

- `source = "baro_recommendation"`
- `event_type`
- `event_description`
- `baro_start_time`
- `baro_end_time`
- `item_name`
- `market_id`
- `ducat_cost`
- `credit_cost`
- `rank`
- `max_rank`
- `item_kind`
- `best_buy_price`
- `best_sell_price`

### 14.4 安全和隐私边界

本阶段明确不写入：

- `format_baro_report()` 完整文本
- `buyers`
- `sellers`
- 玩家名
- profile 链接
- whisper 文本
- raw API response
- raw chat
- prompt

DB 写入仍是 best-effort：`record_recommendation()` 异常只记录 debug，不影响 Baro report callback。

默认行为保持不变：未注入 `TradingMemoryDB` 时，`PriceMonitor` 不会隐式创建数据库，也不会写入长期交易记忆。

### 14.5 本阶段边界

本阶段没有做：

- Favorite / watchlist 市场快照自动写入
- ChatAgent 用户查询摘要写入
- Baro formatted report 持久化
- 玩家订单、profile、whisper 持久化
- Web API / UI
- tool_calls / scheduler run history 迁入 SQLite
- 主架构文档整合

---

## 15. Phase 3.4：PriceMonitor 市场快照写入长期交易记忆

### 15.1 实现目标

Phase 3.4 继续扩展长期交易记忆写入范围。本阶段选择 `PriceMonitor.scan_once()` 生成的 favorite / watchlist 市场快照，把已经结构化的 best sell / buy 价格写入 `TradingMemoryDB.record_market_snapshot()`。

本阶段不新增 SQLite schema，也不新增 warframe.market 请求；只复用扫描过程中已经生成的 `FavoriteSnapshot`。

### 15.2 写入 Hook

`PriceMonitor` 新增：

```python
MARKET_SNAPSHOT_MEMORY_SOURCE = "price_monitor.scan"
MARKET_SNAPSHOT_MEMORY_MIN_SECONDS = 3600
```

并在实例内维护轻量去重状态：

```python
self._market_snapshot_memory_last_written
```

`scan_once()` 在 favorite / watchlist loop 结束后，对 `result.favorite_snapshots` 统一调用：

```python
for snapshot in result.favorite_snapshots:
    self._record_market_snapshot_memory(snapshot)
```

这样直接调用 `scan_once()` 和 scheduler 驱动的 `_run_scan_cycle()` 都会自然覆盖；alert-only item 当前不产生 `FavoriteSnapshot`，本阶段不改变该行为。

### 15.3 写入字段

写入 `market_snapshots` 表：

```python
self.trading_memory_db.record_market_snapshot(
    item_name=snapshot.item_id,
    source=MARKET_SNAPSHOT_MEMORY_SOURCE,
    payload=payload,
)
```

payload 只包含 allowlist 字段：

```python
{
    "source": "price_monitor.scan",
    "item_id": snapshot.item_id,
    "sell_price": snapshot.sell_price,
    "buy_price": snapshot.buy_price,
    "spread": ...,  # 双侧价格都存在时才计算
}
```

### 15.4 去重和空值策略

当前策略：

- `sell_price is None and buy_price is None` 时跳过，不写入空快照。
- sell-only / buy-only 快照保留，`spread` 为 `None`。
- 同一 `item_id` 在 `MARKET_SNAPSHOT_MEMORY_MIN_SECONDS` 内价格签名 `(sell_price, buy_price)` 完全相同时跳过。
- 如果价格变化，即使仍在限频窗口内也会再次写入。
- 只有 DB 写入成功后才更新内存去重状态。

这是轻量 in-memory 策略，不做 DB unique index，也不跨进程持久化 dedupe 状态。

### 15.5 安全和隐私边界

本阶段明确不写入：

- `FavoriteSnapshot.item_display`
- `WatchItem.item_name`
- `WatchItem.content`
- `WatchItem.frequency`
- `WatchItem.time`
- `PriceAlert.note`
- raw orders
- `buyers` / `sellers`
- 玩家名 / user object
- profile 链接
- whisper 文本
- raw API response
- raw chat
- prompt
- assistant reply

DB 写入仍是 best-effort：`record_market_snapshot()` 异常只记录 debug，不影响 `scan_once()` 返回、alert/watch notification、price history 或 scheduler 行为。

默认行为保持不变：未注入 `TradingMemoryDB` 时，`PriceMonitor` 不会隐式创建数据库，也不会写入长期交易记忆。

### 15.6 本阶段边界

本阶段没有做：

- ChatAgent `/scan` 或工具调用路径的 market snapshot 写入
- ChatAgent 用户查询摘要写入
- Web/API 查询长期交易记忆
- market snapshot persistent dedupe / DB unique index
- 可配置 snapshot 写入频率 UI
- `fetch_item_statistics()` / volume_48h 写入
- raw order / 玩家详情 / whisper / profile 持久化
- tool_calls / scheduler run history 迁入 SQLite
- 主架构文档整合

---

## 16. Phase 3.5：长期交易记忆只读查询 API

### 16.1 实现目标

Phase 3.5 为已经写入的长期交易记忆补齐 Web/API 只读观察入口。当前只暴露三类已经结构化、隐私风险较低的数据：

- market snapshots
- recommendations
- push history

本阶段不暴露 `user_queries`，因为 `UserQueryMemory.query_text` 可能包含原始用户消息，需要后续单独设计摘要和脱敏策略。

### 16.2 Read-open-if-exists

`TradingMemoryDB` 新增只读打开能力：

```python
TradingMemoryDB.open_readonly_if_exists(...)
```

行为：

- DB 文件不存在时返回 `None`。
- 不创建目录。
- 不创建 DB 文件。
- 不创建表或索引。
- 不启用 WAL。
- DB 文件存在时用 SQLite `mode=ro` 打开。

Web API 通过私有 helper 查询：

```python
_query_trading_memory(method_name, **kwargs)
```

该 helper 每次 read-open-if-exists、执行 getter、最后 close；如果 DB 不存在，返回空列表。

### 16.3 新增 API

新增只读 endpoints：

```http
GET /api/trading-memory/market-snapshots
GET /api/trading-memory/recommendations
GET /api/trading-memory/push-history
```

支持参数：

- `limit`：`1..500`
- `since`
- `item_name`
- `source`（market snapshots）
- `recommendation_type`（recommendations）
- `push_type`（push history）

返回：

- `market_snapshots` + `count`
- `recommendations` + `count`
- `push_history` + `count`

### 16.4 API 输出 allowlist

API 不直接返回 raw `payload` 或 raw `metadata`，而是使用私有 serializer 输出 allowlist 字段。

Market snapshot 输出：

- `id`
- `timestamp`
- `item_name`
- `source`
- `item_id`
- `sell_price`
- `buy_price`
- `spread`

Recommendation 输出：

- `id`
- `timestamp`
- `item_name`
- `recommendation_type`
- `reason`
- `source`
- `event_type`
- `event_description`
- `baro_start_time`
- `baro_end_time`
- `market_id`
- `display_name`
- `ducat_cost`
- `credit_cost`
- `rank`
- `max_rank`
- `item_kind`
- `best_buy_price`
- `best_sell_price`

Push history 输出：

- `id`
- `timestamp`
- `push_type`
- `item_name`
- `message`
- `source`
- `item_id`
- `item_display`
- `priority`
- `action_suggestion`
- `suggestion_type`
- `event_type`
- `event_description`
- `items_affected`（仅保留字符串列表）

### 16.5 安全和隐私边界

本阶段明确不返回：

- `user_queries`
- raw `payload`
- raw `metadata`
- raw orders
- `buyers` / `sellers`
- 玩家名 / user object
- profile 链接
- whisper 文本
- raw API response
- raw chat
- prompt
- assistant reply
- token / secret 类字段

GET endpoints 不调用任何 `record_*()`、`cleanup_old_data()` 或 monitor/scheduler 写入行为。

### 16.6 本阶段边界

本阶段没有做：

- `GET /api/trading-memory/user-queries`
- ChatAgent 用户查询摘要写入
- Web UI 面板
- Trading memory 聚合统计 / summary endpoint
- POST/PUT/PATCH/DELETE trading-memory endpoints
- cleanup API
- payload / metadata 任意 JSON key 查询
- cursor / offset pagination
- 将 `PriceMonitor` 改为默认注入 `TradingMemoryDB`
- Memory Tree / 长期记忆摘要压缩
- tool_calls / scheduler run history 迁入 SQLite
- 主架构文档整合

---

## 17. Phase 3.6：长期交易记忆 Web 观察面板

### 17.1 实现目标

Phase 3.6 在现有 Web 单页应用的“更多功能”菜单中新增 `长期交易记忆` 入口，打开右侧 detail panel 后可以只读查看 Phase 3.5 已暴露的三类长期交易记忆：

- 市场快照（market snapshots）
- 推荐记录（recommendations）
- 推送历史（push history）

本阶段没有新增后端 API，而是直接复用已有 `GET /api/trading-memory/*` endpoints。

### 17.2 UI 行为

新增入口：

```text
更多功能 → 长期交易记忆
```

面板包含三个 tab：

- `市场快照`
- `推荐记录`
- `推送历史`

通用过滤能力：

- `item_name`
- 时间范围：全部 / 24h / 7d / 30d
- `limit`：25 / 50 / 100

类型过滤能力：

- `source`（市场快照）
- `recommendation_type`（推荐记录）
- `push_type`（推送历史）

每个 tab 只请求自己的 endpoint，并展示 compact card/list。空结果显示面板内 empty state；HTTP / fetch 错误显示面板内错误状态，不导致页面崩溃。

### 17.3 前端安全边界

长期交易记忆里的 `reason`、`message`、`event_description`、`item_name` 等字段虽然来自后端 allowlist serializer，但前端仍按不可信文本处理：

- 动态文本渲染前统一转义。
- 不把 API 字符串插入 inline event handler。
- 不把 API 字符串作为动态链接或危险 attribute。
- 不渲染 raw `payload`、raw `metadata`、raw orders、profile、whisper、prompt、assistant reply 或 raw chat。
- 不展示 `user_queries`。

Playwright 测试使用 XSS payload 覆盖 market snapshot、recommendation 和 push history 的可见字段，验证不会生成可执行 DOM，也不会触发 `window.__xssHits`。

### 17.4 只读边界

Web 面板只发出 GET 请求：

```http
GET /api/trading-memory/market-snapshots
GET /api/trading-memory/recommendations
GET /api/trading-memory/push-history
```

不提供：

- edit
- delete
- cleanup
- replay / retry
- re-query
- 手动扫描
- scheduler 控制
- POST / PUT / PATCH / DELETE trading-memory 操作

### 17.5 本阶段边界

本阶段没有做：

- backend summary endpoint
- `user_queries` Web 展示
- ChatAgent 用户查询摘要写入
- Trading memory cleanup / delete / edit API
- Trading memory chart
- 导出功能
- scheduler job Web 管理
- tool-call history/stats Web API 或面板
- Memory Tree / 长期记忆摘要压缩
- 主架构文档整合

---

## 18. Phase 3.7：ChatAgent 用户查询安全摘要写入

### 18.1 实现目标

Phase 3.7 解决 `TradingMemoryDB.user_queries` 仍是 legacy raw-query 风格的问题：生产聊天路径如果直接调用 `record_user_query()`，会有保存完整用户消息、助手回复、prompt 或工具原始参数的风险。

本阶段新增安全写入路径：

```python
TradingMemoryDB.record_user_query_summary(
    intent="price_check",
    item_name="arcane_energize",
    metadata={...},
)
```

该方法由 DB 层内部构造 `query_text`，调用方不能传入任意 raw summary 文本。示例：

```text
summary:v1 intent=price_check item=arcane_energize contexts=1 tools=query_price
```

### 18.2 安全摘要规则

持久化内容只允许 deterministic / allowlist 字段：

- `intent`：closed enum，不认识的值统一为 `unknown`
- `item_name`：只允许 normalized market id，例如 `arcane_energize`
- `metadata.storage_kind = "summary"`
- `metadata.source = "chat_agent"`
- `metadata.summary_strategy = "deterministic_v1"`
- `metadata.raw_query_stored = False`
- `metadata.assistant_reply_stored = False`
- `metadata.context_item_ids`：最多 3 个 normalized item id
- `metadata.tool_names`：最多 5 个 safe tool name
- `metadata.context_count` / `tool_count` / `tool_ok_count`
- `metadata.item_source`：`contexts` / `tool_args_resolved` / `mixed` / `none`

显式不保存：

- raw user message
- assistant reply
- prompt / system prompt
- raw tool args 或 `args_summary` dump
- `__message` / `message_context`
- token / secret / api_key / authorization / cookie
- whisper / profile / orders / buyers / sellers / player name
- 中文别名或 display name

### 18.3 ChatAgent 集成方式

`ChatAgent` 新增可选依赖注入：

```python
ChatAgent(..., trading_memory_db=None)
```

默认不创建 `TradingMemoryDB()`，也不改变 Web app 启动行为。只有外部显式注入 DB 时，才在 `_log_answer()` 中 best-effort 写入安全摘要。

写入信号来源：

1. `contexts` 中的 `ctx.item_id`
2. 工具 metadata 中 `args_summary` 的 `item_id` / `market_id` / `item_name` / `query` 等字段，经 resolver 或 identifier 规则归一后只保存 market id
3. deterministic intent detectors 和 safe tool name map

DB 写入失败只记录 debug，不阻断 `answer()` 或 `answer_stream()`。

### 18.4 Web/API 暴露边界

本阶段仍不新增：

```http
GET /api/trading-memory/user-queries
```

也不新增 Web UI tab。`record_user_query()` 保留 legacy/raw-compatible 行为，只用于兼容历史测试和已有数据边界；ChatAgent 新路径只调用 `record_user_query_summary()`。

### 18.5 本阶段边界

本阶段没有做：

- user query Web/API 暴露
- user query Web UI tab
- LLM 摘要
- 自动迁移旧 raw `user_queries`
- 清理 conversation log、AgentMemory 或浏览器 localStorage 中的既有 raw stores
- 默认在 Web app 中启用 `TradingMemoryDB` 写入
- 主架构文档整合

---

## 19. Phase 4.1：工具结果模型上下文压缩与 Plan 聚合脱敏

### 19.1 实现目标

Phase 4.1 开始落地 OpenHuman 借鉴路线中的“工具结果压缩与上下文控制”。本阶段只处理模型上下文中的工具结果，不改变用户可见输出和 `ToolResult.content` raw 语义。

新增：

```text
warframe_agent/tool_context.py
```

核心能力：

- `compress_tool_result_for_model()`：工具结果进入 ReAct tool message 前做 deterministic 脱敏和预算裁剪。
- `summarize_tool_arguments_for_model()`：plan step arguments 进入模型上下文前只输出安全摘要。
- `format_plan_results_for_model()`：plan 多步骤聚合结果受单步预算和总预算控制。

新增配置：

```python
TOOL_CONTEXT_MAX_CHARS = 2000
TOOL_CONTEXT_MAX_LINES = 60
PLAN_CONTEXT_MAX_CHARS = 6000
PLAN_STEP_CONTEXT_MAX_CHARS = 1500
PLAN_ARGS_MAX_CHARS = 600
```

### 19.2 压缩和脱敏规则

工具结果进入模型上下文前会先做敏感 key-value 脱敏：

- `password`
- `token`
- `secret`
- `api_key` / `apikey`
- `authorization`
- `cookie`
- `Bearer ...`

短结果如果没有超出字符和行数预算，会保持原样进入模型上下文，避免影响常规查价、事件查询和短工具答复。

长结果只保留前部内容，并追加确定性标记：

```text
[工具结果已压缩: tool=query_price original_chars=... original_lines=...]
```

Plan 聚合中不再 raw dump step arguments，而是：

- 省略 `__message`、`message_context`、`prompt`、`raw_chat`、`assistant_reply`
- 敏感字段统一写为 `[REDACTED]`
- 长字符串、长 list、长 dict 只保留摘要
- 对每步结果和整个 plan aggregate 分别套预算

### 19.3 接入边界

`warframe_agent/tool_router.py` 的 ReAct 路径现在在 append tool-role message 前调用压缩 helper：

```python
tool_content = result or f"工具 {tc.name} 执行失败或无结果"
messages.append({
    "role": "tool",
    "content": compress_tool_result_for_model(tc.name, tool_content),
})
```

Plan 路径保留 `execute_plan()` 返回 raw `(PlanStep, result)`，只让 `_format_plan_results()` 委托 `format_plan_results_for_model()`，因此实际工具 handler 和 raw result 不被修改。

### 19.4 保留行为

本阶段明确不改变：

- `ToolRegistry.execute()` 返回的 `ToolResult.content`
- `ChatAgent._execute_tool_call()` 返回给 legacy/direct router 的用户可见文本
- 各工具 handler 自身输出格式
- conversation log 记录策略
- trading memory 写入策略
- Web API / Web UI / 数据库 schema

这意味着 legacy/direct router 的长工具输出仍会完整展示给用户；只有发给模型继续推理的 tool message 会被压缩。

### 19.5 本阶段边界

本阶段没有做：

- domain-specific `ToolResult.model_context` 压缩器
- LLM 语义摘要工具结果
- domain-specific Riven / Baro / Mod / Investment 压缩器
- 专家子代理框架
- 外部内容 prompt-injection trust boundary 标签
- user query summaries API / UI
- 新增持久化表
- 主架构文档整合

---

## 20. Phase 4.2A：ToolResult 显式模型上下文分层

### 20.1 实现目标

Phase 4.2A 在 Phase 4.1 的调用点压缩基础上，把工具结果的用户可见文本和模型上下文文本显式分层，降低后续新增 ReAct / plan / 专家工具路径时误把 raw 输出送进模型的风险。

`ToolResult` 现在包含：

```python
@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str | None = None
    error: str | None = None
    metadata: ToolExecutionMetadata | None = None
    display_content: str | None = None
    model_context: str | None = None
```

字段语义：

- `content`：历史兼容字段，仍保存 handler 返回的 raw/display 文本。
- `display_content`：用户可见文本，默认等于 `content`。
- `model_context`：模型上下文专用文本，默认由 `compress_tool_result_for_model()` 生成。

### 20.2 接入方式

`ToolRegistry.execute()` 成功路径会同时填充三层语义：

```python
content = spec.handler(arguments)
return ToolResult(
    ok=True,
    content=content,
    display_content=content,
    model_context=compress_tool_result_for_model(name, content or ""),
    metadata=metadata,
)
```

`ChatAgent._execute_tool_call()` 改为返回 `display_content`，因此 legacy/direct 用户可见输出继续保持完整 raw/display 文本。

`tool_context.py` 新增：

```python
tool_result_model_context(tool_name, result_or_content, fallback="")
```

该 helper：

- 优先使用 `ToolResult.model_context`
- plain string 继续走 Phase 4.1 的通用压缩 / 脱敏
- `None` 使用安全 fallback
- 对 explicit model context 仍做敏感文本 redaction，并按调用方预算截断

`tool_router.react_loop()` 和 plan aggregate 现在通过该 helper 获取模型上下文，避免重复压缩 explicit `model_context`，也避免 raw `content` / `display_content` 直接进入模型。

### 20.3 保留行为

本阶段明确保持：

- handler 输出格式不变
- `ToolResult.content` 兼容旧语义
- direct / legacy router 用户可见输出不被压缩
- conversation log 仍只记录 tool metadata，不记录 raw result 或 model context
- trading memory 行为不变
- Web API / UI / DB schema 不变

### 20.4 本阶段边界

本阶段没有做：

- domain-specific Riven / Baro / Mod / Investment 压缩器
- LLM 语义摘要工具结果
- 专家子代理框架
- 外部内容 prompt-injection trust boundary 标签
- user query summaries API / UI
- WebSocket 输入校验统一
- 前端 DOM 后处理安全修复
- config secrets API 审查
- 新增持久化表
- 主架构文档整合

---

## 21. Phase 4.2B：首批领域工具 compact model_context

### 21.1 实现目标

Phase 4.2B 在 `ToolResult.model_context` 分层基础上，为首批高容量但低联系方式风险的交易分析工具生成领域结构化模型上下文。

首批覆盖：

- `mod_flipper`
- `set_profit`
- `investment_advisor`

这三类工具都已经在 handler 内拿到结构化 dataclass 结果，再格式化用户可见 Markdown；因此本阶段直接从结构化结果生成 compact model context，不解析 display Markdown。

### 21.2 Registry 与 ChatAgent plumbing

`ToolSpec.handler` 兼容返回：

```python
str | ToolResult | None
```

`ToolRegistry.execute()` 新增 coercion 逻辑：

- plain string / `None`：保持 Phase 4.1 通用压缩 fallback
- explicit `ToolResult`：保留 `content` / `display_content` / `model_context`
- explicit `ToolResult` 缺少 `display_content` 时回填 `content`
- explicit `ToolResult` 缺少 `model_context` 时回退到通用压缩
- metadata 仍由 registry 统一补齐

`ChatAgent` 新增完整结果路径：

```python
def _run_tool_call(...) -> ToolResult
```

ReAct 使用 `_run_tool_call()`，因此 tool-role message 能拿到 explicit domain `model_context`；legacy/direct `_execute_tool_call()` 仍只返回 `display_content`，用户可见输出保持原 Markdown。

### 21.3 领域压缩器

新增 formatter：

```python
format_mod_flip_results_for_model(...)
format_set_profit_results_for_model(...)
format_prime_investment_results_for_model(...)
```

`mod_flipper` model context 保留：

- `tool=mod_flipper`、`min_profit`、`limit`、`result_count`
- top rows：`item_id`、`display_name`、`rarity`、`max_rank`、`r0_buy_price`、`r10_sell_price`、`flip_profit`、`roi_pct`、`endo_cost`、`plat_per_1k_endo`、`volume_48h`、`is_prime`
- `omitted_count` 表示被省略结果数

`set_profit` model context 保留：

- `tool=set_profit`、`min_profit`、`limit`、`result_count`
- top rows：`base_id`、`display_name`、`best_strategy`、`best_profit`、两种利润、整套/拆件价格、`part_count`、`volume_48h`
- `omitted_count` 表示被省略结果数

`investment_advisor` model context 保留：

- `tool=investment_advisor`、`budget`、`min_roi`、`limit`、`result_count`
- top rows：`base_id`、`display_name`、`set_item_id`、`strategy`、买卖价格、利润、ROI、可买套数、总利润、风险、成交量、`part_count`
- `omitted` 表示被省略结果数
- 不 dump raw `part_details`

### 21.4 延期项

本阶段没有压缩：

- `riven_search`：涉及卖家状态、卖家名、whisper 和分页追问，边界更敏感。
- `query_price`：高频核心交易路径仍可能需要 `/w` 命令和玩家信息。
- Baro / `query_events`：direct event 路径和 tool 路径仍需后续统一。

### 21.5 验证结果

已通过：

```bash
python -m pytest tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py -q
# 31 passed

python -m pytest tests/test_tool_registry.py tests/test_router.py tests/test_tool_router.py -q
# 58 passed

python -m pytest tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py tests/test_tool_context.py tests/test_tool_registry.py tests/test_router.py tests/test_tool_router.py -q
# 100 passed
```

---

## 22. Phase 4.2C + Phase 5A：敏感工具上下文与 Web/API 安全边界

### 22.1 实现目标

Phase 4.2C + Phase 5A 将 Phase 4.2B 暂缓的敏感交易路径一次性推进，并同步补齐 Web/API/frontend 安全边界。

本阶段覆盖：

- `query_price` / `ItemContext`
- `riven_search`
- Baro order follow-up
- `query_events(type=...)`
- `/ws/chat` 输入校验
- `/api/push/config`、`/api/feishu/config` 配置序列化
- `chat.js` / `chart.js` / `app.js` 动态 DOM 渲染

核心边界：用户可见 `display_content` 可以继续保留交易便利信息；模型可见 `model_context` 和 session history 只能使用 allowlist compact summary。

### 22.2 敏感交易工具 safe model_context

`query_price` 现在在 `ItemContext` 中保留：

- `text`：用户可见订单摘要，仍可包含玩家名和 `/w` 私聊命令。
- `model_context`：模型可见安全摘要，只包含 item、价格、数量、声望、rank、价差等 allowlist 字段。

新增安全摘要 helper：

```python
build_safe_query_price_model_context(...)
safe_query_price_context_from_contexts(...)
```

模型 prompt、ReAct tool message 和 deterministic price session history 使用 `tool=query_price` 安全摘要，不包含：

- 玩家名
- profile URL
- `/w` / `\\w`
- raw order dict

`riven_search` 新增：

```python
format_riven_results_for_model(query, page, max_items=8)
```

该 formatter 保留 weapon、filters、pagination、mod 属性、价格、rerolls、seller_status，但不包含 seller、profile、`/w`、raw auction 或 owner identifiers。`_tool_riven_search()`、确定性紫卡查询和紫卡追问均返回 / 记录 explicit `ToolResult.model_context`。

Baro order follow-up 新增：

```python
format_baro_order_details_for_model(...)
```

用户可见订单详情仍保留玩家名、profile 和私聊命令；session history 和模型上下文只记录 item、rank、买卖价、订单数量和 spread 摘要。

### 22.3 `query_events(type=...)` 支持与事件 compact context

`query_events` 现在实际读取 schema 中声明的 `type` 参数，并支持以下 allowlist：

- `void_fissure`
- `baro_visit`
- `invasion`
- `void_storm`
- `prime_resurgence`

新增事件 formatter：

```python
filter_events_by_type(...)
format_events_for_display(...)
format_events_for_model(...)
```

无效 type 返回确定性错误摘要；ReAct / plan 消费 compact model context，不 dump raw world state。

### 22.4 WebSocket 与配置 secrets hardening

`/ws/chat` 现在复用 REST `ChatRequest` 校验边界：

- invalid JSON：返回 error，不调用 agent。
- JSON 非 object：返回 error。
- `message` 缺失、非字符串、strip 后为空、超长：返回 error。
- valid message 继续流式返回。

配置读取 endpoint 不再使用 `cfg.__dict__.copy()` 返回配置对象，而是显式 allowlist：

- `/api/push/config` 不返回 raw `app_token`，只返回 `app_token_configured` / `app_token_masked` 和非敏感字段。
- `/api/feishu/config` 不返回 raw `app_secret`，只返回 `app_secret_configured` / `app_secret_masked` 和非敏感字段。

### 22.5 前端动态 DOM XSS hardening

`chat.js` 保留 `marked.parse()` + `DOMPurify.sanitize()` 的 Markdown 渲染入口，但 `detectWhisperCommands(container)` 不再在 DOMPurify 后读写 `container.innerHTML`：

- 使用 `TreeWalker` 遍历 text nodes。
- 用 DOM fragment / `textContent` 构造 whisper code 和 copy button。
- 使用 `addEventListener`，不生成 inline `onclick`。

`chart.js` 中 compare suggestions 和 chart legend 改为 DOM API + `textContent` 写入动态 item name。

`app.js` 中 command palette 等动态 UI 改为 DOM API 构造，避免将动态数据拼入 `innerHTML`。

### 22.6 验证结果

已通过：

```bash
python -m pytest tests/test_chat.py tests/test_router.py tests/test_tool_context.py tests/test_riven.py tests/test_baro.py tests/test_events.py -q
# 153 passed

python -m pytest tests/test_web_api.py -q
# 44 passed, 1 warning

python -m pytest tests/test_web_ui_playwright.py -q
# 4 passed

python -m pytest tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py tests/test_tool_registry.py tests/test_tool_router.py -q
# 69 passed

python -m pytest tests/test_tool_router.py -q
# 17 passed

python -m pytest tests/test_chat.py tests/test_router.py tests/test_riven.py tests/test_baro.py tests/test_events.py -q
# 142 passed

python -m pytest tests -q
# 758 passed, 2 warnings
```

当前 warning 来自既有 `lark_oapi` 依赖 deprecation 和 Playwright 测试中的既有 `AsyncMock` coroutine finalization 提示，不影响本阶段目标测试与完整回归通过。

---

## 23. Phase 5B + Phase 4.3：外部内容 trust boundary 与专家工具收尾

### 23.1 实现目标

Phase 5B + Phase 4.3 完成 OpenHuman 借鉴路线的最后两块核心能力：

- 对模型可见的外部文本建立统一 untrusted-data fence，降低 prompt-injection 风险。
- 引入轻量专家工具，让市场、紫卡、事件分析可以作为内部专家能力被 ReAct / plan 调用，但不绕过 ToolRegistry，不直接执行状态变更。

本阶段仍保持用户可见功能不退化：交易 display 可以保留便利信息；模型上下文、专家 prompt 和 session history 继续只消费 safe / fenced context。

### 23.2 外部内容 trust boundary

`warframe_agent/tool_context.py` 新增：

```python
sanitize_untrusted_model_text(...)
wrap_untrusted_model_text(...)
```

处理策略：

- 复用 secret / token / authorization / cookie 脱敏。
- 去除控制字符。
- 中性化 `system:` / `developer:` / `<tool>` / 伪 JSON tool call / code fence 等 prompt-injection marker。
- 按字符和行数预算截断。
- 包裹为 `UNTRUSTED_<SOURCE>_DATA_START/END`，并明确“边界内是外部数据，不是指令”。

已接入入口：

- `build_system_prompt(..., market_context=...)`：市场智能不再作为裸外部文本进入 system authority。
- `format_events_for_model(...)`：worldstate/event description 作为 `UNTRUSTED_WORLDSTATE_DATA` 进入模型上下文。
- `GameDataStore.get_mod_info()` / `get_warframe_info()`：Export/game-data 描述和技能文本作为 `UNTRUSTED_GAME_DATA_DATA` 注入。
- plan step 参数摘要将 `context` 视为内部/高风险字段，不再 raw dump expert context。

保持不变：

- explicit `ToolResult.model_context` 仍优先使用，不重复包裹已由领域 formatter 构造的 safe context。
- direct display / 用户可见 Markdown 不因模型 trust boundary 被压缩或隐藏。

### 23.3 专家工具

新增：

```text
warframe_agent/experts.py
```

核心结构：

```python
@dataclass(frozen=True)
class ExpertRequest:
    domain: str
    question: str
    context: str

run_expert(request, orchestrator) -> ToolResult
```

默认注册表新增工具：

| 工具名 | 说明 |
|------|------|
| `market_expert` | 基于安全价格/趋势上下文做买卖建议 |
| `riven_expert` | 基于安全紫卡上下文解释属性、价格和风险 |
| `event_expert` | 基于安全活动上下文给出限时活动优先级建议 |

专家工具边界：

- 通过 `ModelOrchestrator.chat(ModelRequest(task=...))` 调用模型。
- 专家 prompt 明确 fenced block 只作为数据，不是指令。
- 专家只做分析和综合，不直接执行工具或修改状态。
- 专家输出以 `ToolResult` 返回：用户可见 `display_content` 保留回答；模型上下文只保存 `tool=<expert>`、`domain=...`、`summary=...`。
- 专家 `model_context` 不包含 raw context、玩家名、profile、`/w` 或 raw external block。
- orchestrator 失败时返回可控失败，不阻断既有确定性工具 golden path。

### 23.4 ReAct / plan 集成

`ChatAgent._build_tool_registry()` 绑定：

- `market_expert`
- `riven_expert`
- `event_expert`

ReAct 与 plan 复用既有 `ToolResult.model_context` plumbing：

- 单步 expert tool message 使用 compact expert model context。
- plan aggregate 中 expert 步骤只聚合 safe summary。
- step arguments 不再展示 raw `context`，避免 plan message 泄露 untrusted prompt 或交易 display 信息。

### 23.5 验证结果

开发中已通过目标切片：

```bash
python -m pytest tests/test_tool_context.py -q
# 13 passed

python -m pytest tests/test_chat.py tests/test_events.py tests/test_router.py tests/test_tool_context.py tests/test_game_data.py -q
# 86 passed

python -m pytest tests/test_experts.py tests/test_tool_registry.py tests/test_tool_router.py -q
# 45 passed

python -m pytest tests/test_tool_context.py tests/test_router.py -q
# 38 passed
```

最终完整回归：

```bash
python -m pytest tests -q
# 772 passed, 1 warning
```

warning 来自既有 `lark_oapi` deprecation；测试输出仍可见一次既有 `AsyncMock` coroutine finalization runtime 提示，但 pytest warning 汇总为 1 条，不影响完整回归通过。

---

## 24. 测试覆盖

### 24.1 新增测试文件

新增：

```text
tests/test_tool_registry.py
tests/test_conversation_log.py
tests/test_scheduler.py
tests/test_trading_memory.py
tests/test_tool_context.py
```

### 24.2 扩展测试文件

扩展：

```text
tests/test_tool_router.py
tests/test_router.py
tests/test_monitor.py
tests/test_proactive_push.py
tests/test_mod_flipper.py
tests/test_set_profit.py
tests/test_investment.py
```

### 24.3 覆盖内容

ToolRegistry 测试覆盖：

- 注册工具
- 重复注册报错
- legacy `TOOLS` 导出
- Ollama `TOOL_SCHEMAS` 导出
- handler 执行
- 未知工具
- 缺少参数
- 默认工具集合
- `general_chat` 不进入 function schema
- metadata 成功路径
- metadata 失败路径
- handler 异常路径
- 敏感参数脱敏
- 长参数摘要
- `__message` 隐藏和 `message_context` 提取
- 成功结果填充 `display_content` 和 `model_context`
- 长 raw content 不改变 `content` / `display_content`，但 `model_context` 会压缩
- 敏感 raw content 保留在用户可见层，进入 `model_context` 前脱敏
- 失败结果不携带 display/model context
- handler 返回 explicit `ToolResult` 时保留 `content` / `display_content` / `model_context` 并补 metadata

Tool context 测试覆盖：

- 短工具结果进入模型上下文时保持原样
- 长工具结果进入模型上下文时按字符和行数预算裁剪，并追加压缩标记
- 工具结果中的 token、authorization、cookie、Bearer secret 等敏感值会脱敏
- plan step arguments 会省略 `__message` / `message_context` 等内部字段
- plan step arguments 中的 token / api_key / cookie 等敏感字段写为 `[REDACTED]`
- 长 list / dict / string 参数只进入摘要，不 raw dump 全量
- plan aggregate 同时受 per-step 和 total 字符预算控制
- `tool_result_model_context()` 优先使用 explicit `ToolResult.model_context`
- plain string 和 `None` fallback 仍走安全压缩 / 脱敏
- plan formatter 使用 explicit model context，不泄露 raw/display tail

ChatAgent / Router 测试覆盖：

- routed 查价仍可返回价格
- `_execute_tool_call()` 能记录 metadata
- 失败工具调用也记录 metadata
- 用户回复不泄露 metadata
- ReAct tool-role message 不包含 metadata
- 工具调用能写入 conversation log
- 敏感参数不会明文进入 JSONL
- `message_context` 不持久化
- 多轮对话不会串用上一轮工具调用
- 注入 `TradingMemoryDB` 后，`answer()` 会写入一条安全用户查询摘要
- `answer_stream()` 只写入一条安全用户查询摘要，不重复
- router/tool 路径只保存 safe tool name 和 normalized item id，不保存 raw args、token、`__message` 或 `message_context`
- `record_user_query_summary()` 失败不会阻断回答
- slash command 和无交易信号的一般聊天不写入 `user_queries`
- ReAct 普通工具调用的长结果进入模型上下文前会压缩，短结果保持原样
- ReAct tool message 中的 token / authorization / cookie 等敏感值不会进入模型上下文
- plan 聚合 tool message 会脱敏 step args、压缩长结果并受总预算控制
- ReAct tool message 优先使用 `ToolResult.model_context`，不泄露 raw/display tail
- plan aggregate 优先使用 step result 的 explicit `model_context`
- legacy/direct router 用户可见长输出不被压缩
- `_execute_tool_call()` 返回 raw/display content 语义不变
- `_execute_tool_call()` 对 explicit `ToolResult` 只返回 `display_content`
- ChatAgent ReAct 路径调用真实 `mod_flipper` handler 时，tool message 使用 compact model context，不包含 display Markdown

Domain compact formatter 测试覆盖：

- `mod_flipper` model context 保留 top ranked metrics，不包含 `## Mod 翻转排行榜`
- `mod_flipper` 超过 `max_items` 时省略尾部并记录 `omitted_count`
- `set_profit` model context 保留最佳策略、利润、整套/拆件价格、part count 和成交量
- `set_profit` 超过 `max_items` 时省略尾部并记录 `omitted_count`
- `investment_advisor` model context 保留预算、ROI、风险、可买套数、总利润和 top opportunities
- `investment_advisor` 只暴露 `part_count`，不 dump raw `part_details`

Conversation log 测试覆盖：

- `ConversationEntry.tool_calls` 可以写入 JSONL
- `load_conversations()` 可以读回 `tool_calls`
- `query_tool_call_history()` 可以展开最近工具调用
- 可以按 `tool_name`、`ok`、`session_id` 过滤
- `limit` 能限制最近结果数量
- 缺失日志文件、malformed JSONL、旧格式日志不会导致查询失败
- 查询结果不包含 `user_message`、`assistant_reply`、raw arguments、raw result、prompt、`message_context`
- `query_tool_call_stats()` 可以统计整体调用数、成功数、失败数、unknown 数和成功率
- 可以统计整体与分工具耗时
- 可以生成 `by_tool` 分组和 `top_tools` 高频工具列表
- 可以按 `tool_name`、`session_id`、`limit` 限定统计范围
- 非数字耗时不会污染 duration 统计
- 统计结果不泄露 `args_summary`、raw arguments、raw result、error 原文、prompt、用户消息、助手回复或上下文

Scheduler 测试覆盖：

- interval job 注册和初始 `next_run_at`
- `run_immediately` 立即到期
- 重复 job id 和非正 interval 校验
- due jobs 只包含 enabled 且到期任务
- due job 按注册顺序执行
- 成功执行后按 fixed-delay 重排
- 异常执行会记录失败并继续后续 job
- 过期任务每次 tick 只执行一次
- 删除任务后不再执行
- disabled job 不执行但仍可列出
- `tick()` 作为 `run_due()` 别名
- runner 拒绝非正 `poll_seconds`
- runner `start()` / `stop()` 幂等
- 非立即 job 支持 `initial_delay_seconds`
- `initial_delay_seconds` 的首次运行和后续 fixed-delay 重排
- 负数 initial delay 和与 `run_immediately` 冲突的校验
- `serialize_scheduled_job()` 输出公开字段并格式化 datetime
- `serialize_scheduler_jobs()` 保留注册顺序、run/error count 和 disabled job
- scheduler snapshot 不暴露 callback 或异常文本

Monitor / Scheduler 集成测试覆盖：

- `PriceMonitor._build_scheduler()` 注册立即执行的主扫描 job
- 主扫描 job 使用 `monitor.interval_seconds`
- `_run_scan_cycle()` 保留 alert 入队和 callback 行为
- `_run_scan_cycle()` 异常只记录 warning，不向外抛出
- `PriceMonitor.start()` 双重调用不会重复创建线程或 scheduler
- 既有 `_thread` start / stop 行为继续保持
- `PriceMonitor._build_scheduler()` 注册非立即到期的低频维护 jobs
- 维护 job interval 复用现有 scan-count 配置换算后的秒数
- `_run_scan_cycle()` 记录 `_last_scan_result`，但不再内联执行知识更新、目标生成、自学习
- 知识更新 job 会复用最新扫描结果，首轮扫描前会安全跳过
- 自学习 job 会加载 fresh memory 后再执行
- `PriceMonitor._build_scheduler()` 注册立即到期的 grouped event checks job
- 第一轮 scheduler tick 保持 scan → event checks 执行顺序
- `_run_scan_cycle()` 不再内联执行裂缝、世界循环、Baro、事件推送和日报检查
- `_run_event_checks_job()` 保留事件检查既有顺序，并在未完成 scan cycle 前安全跳过
- event checks job 异常会记录 warning 并交给 Scheduler 统计失败
- cycle alert 在首轮 scheduler tick 中仍只 baseline，不推送
- `PriceMonitor.scheduler_status_snapshot()` 未启动时安全返回空状态
- `PriceMonitor.scheduler_status_snapshot()` 可以序列化现有 scheduler jobs
- scheduler status snapshot 不会触发 job tick 或改变 run count
- `PriceMonitor` 默认不创建 `TradingMemoryDB`
- 注入 `TradingMemoryDB` 后，规则驱动主动推送会写入 push history
- 注入 `TradingMemoryDB` 后，事件驱动推送会写入 push history
- TradingMemoryDB 写入失败不会阻断 proactive push callback
- push history metadata 不包含 raw chat / prompt / assistant reply 字段
- 注入 `TradingMemoryDB` 后，Baro 推荐会写入 recommendation memory
- Baro 推荐写入 payload 只包含结构化字段，不包含 formatted report、buyers、sellers、profile、whisper 或 raw chat
- Baro 推荐记忆写入失败不会阻断 report callback
- 未注入 `TradingMemoryDB` 时，Baro 推荐保持既有 callback 行为
- 同一个 Baro `start_time` 仍只记录一次推荐记忆
- 注入 `TradingMemoryDB` 后，favorite scan 会写入 market snapshot memory
- 注入 `TradingMemoryDB` 后，watchlist scan 会写入 market snapshot memory
- market snapshot payload 只包含 allowlist 字段，不包含 raw orders、玩家信息、watchlist free text、alert note、raw chat 或 prompt
- 空价格快照不写入长期交易记忆
- sell-only / buy-only 快照可写入，且 `spread` 为 `None`
- 同一 item 在限频窗口内相同价格只写一次
- 同一 item 在限频窗口内价格变化会再次写入
- market snapshot 记忆写入失败不会阻断 `scan_once()`

Web API 测试覆盖：

- `GET /api/scheduler/status` 返回 monitor scheduler snapshot
- scheduler status endpoint 只读，不触发 `start()`、`stop()`、`_build_scheduler()` 或 `tick()`
- `GET /api/trading-memory/market-snapshots` 返回 allowlist market snapshot 记录并支持过滤参数
- `GET /api/trading-memory/recommendations` 返回 allowlist recommendation 记录并支持过滤参数
- `GET /api/trading-memory/push-history` 返回 allowlist push history 记录并支持过滤参数
- trading memory endpoints 对 `limit=0` 和 `limit=501` 返回 422
- trading memory endpoints 在 DB 缺失时返回空列表和 `count=0`
- trading memory endpoints 不返回 raw `payload`、raw `metadata`、raw orders、玩家信息、profile、whisper、prompt、raw chat、assistant reply 或 token
- trading memory endpoints 只调用 getter method，不调用 `record_*()` 或 `cleanup_old_data()`
- `GET /api/trading-memory/user-queries` 保持 404，防止误暴露 `user_queries`

Web UI / Playwright 测试覆盖：

- 更多功能菜单可以打开 `长期交易记忆` detail panel
- 默认 `市场快照` tab 会渲染 sell / buy / spread
- 可以切换到 `推荐记录` 和 `推送历史` tab
- 面板过滤项会生成正确 query params，且不发送 `undefined` / `null`
- 空结果显示友好的 empty state
- endpoint HTTP 错误显示面板内错误状态，不产生 page error
- XSS payload 在长期交易记忆可见字段中只作为文本出现，不会生成可执行 DOM
- 浏览器侧 `/api/trading-memory/*` 请求全部为 GET

TradingMemoryDB 测试覆盖：

- 四类长期记忆记录可写入和查询
- `record_user_query()` 保留 legacy raw-compatible 行为
- `record_user_query_summary()` 只写 deterministic summary 和 allowlist metadata
- summary 写入会归一化 intent、item id、context item ids 和 safe tool names
- summary 写入会丢弃 raw message、prompt、assistant reply、token、whisper、orders、玩家名、中文别名和非法 metadata
- 支持按 item、type、source、since 过滤
- close 后 reopen 仍可读取已保存记录
- `cleanup_old_data()` 可按表返回删除数量
- 损坏 JSON payload 不导致查询失败
- `open_readonly_if_exists()` 在 DB 缺失时返回 `None` 且不创建文件或目录
- `open_readonly_if_exists()` 可读取已有 DB 中的长期交易记忆
- `close()` 幂等
- SQLite WAL 模式启用

### 24.4 当前测试结果

当前目标、相关和完整回归结果：

```text
python -m pytest tests/test_chat.py tests/test_router.py tests/test_tool_context.py tests/test_riven.py tests/test_baro.py tests/test_events.py -q
153 passed

python -m pytest tests/test_web_api.py -q
44 passed, 1 warning

python -m pytest tests/test_web_ui_playwright.py -q
4 passed

python -m pytest tests/test_mod_flipper.py tests/test_set_profit.py tests/test_investment.py tests/test_tool_registry.py tests/test_tool_router.py -q
69 passed

python -m pytest tests/test_tool_router.py -q
17 passed

python -m pytest tests/test_chat.py tests/test_router.py tests/test_riven.py tests/test_baro.py tests/test_events.py -q
142 passed

python -m pytest tests -q
772 passed, 1 warning
```

当前 warning 来自既有 `lark_oapi` 依赖 deprecation；测试输出中仍出现一次既有 `AsyncMock` coroutine finalization runtime 提示，但 pytest warning 汇总为 1 条，不影响测试通过。

---

## 25. 当前收益

本轮改造后，项目获得了一个更清晰的工具底座：

```text
ToolSpec
  ↓
ToolRegistry
  ↓
ToolResult
  ↓
ToolExecutionMetadata
  ↓
ConversationEntry.tool_calls
  ↓
query_tool_call_history()
  ↓
query_tool_call_stats()
  ↓
Scheduler / SchedulerRunner
  ↓
PriceMonitor._build_scheduler()
  ↓
PriceMonitor._run_scan_cycle()
  ↓
PriceMonitor maintenance jobs
  ↓
PriceMonitor event checks job
  ↓
Scheduler status snapshot
  ↓
GET /api/scheduler/status
  ↓
TradingMemoryDB
  ↓
PriceMonitor proactive push memory hook
  ↓
PriceMonitor Baro recommendation memory hook
  ↓
PriceMonitor market snapshot memory hook
  ↓
TradingMemoryDB read-only open
  ↓
GET /api/trading-memory/*
  ↓
长期交易记忆 Web 观察面板
  ↓
ChatAgent record_user_query_summary()
  ↓
compress_tool_result_for_model()
  ↓
ToolResult.model_context
  ↓
tool_result_model_context()
  ↓
format_plan_results_for_model()
```

直接收益：

1. 工具定义集中化。
2. Router schema 和 legacy tool list 不再重复维护。
3. ChatAgent 工具执行入口统一。
4. 每次工具调用都有结构化 metadata。
5. 工具参数有摘要和脱敏机制。
6. 工具调用可以随对话日志持久化。
7. 后端可以只读查询最近工具调用历史。
8. 后端可以聚合工具调用次数、成功率和耗时表现。
9. 项目有了独立、可测试的调度底座，为拆分 `PriceMonitor` 后台任务做准备。
10. `PriceMonitor` 主扫描循环已经通过 Scheduler job 驱动，且 Web / CLI 生命周期保持兼容。
11. 知识更新、目标生成、自学习已经从主扫描循环拆成独立 scheduler jobs。
12. 裂缝、世界循环、Baro、事件驱动推送和每日报告已经通过 grouped event checks job 从主扫描循环移出。
13. Scheduler job 状态已经可以通过只读 snapshot 和 `/api/scheduler/status` 暴露给 Web/API 层。
14. 项目具备了 SQLite 长期交易记忆存储底座，可沉淀用户查询、市场快照、推荐记录和推送历史。
15. `PriceMonitor` 已支持将结构化主动推送写入长期记忆，且默认不隐式创建数据库。
16. Baro 推荐已支持以 recommendation memory 形式保存结构化推荐字段，且不保存格式化报告文本或玩家订单详情。
17. favorite / watchlist 扫描已支持以 market snapshot memory 形式保存结构化 best sell / buy 价格，并带有空快照跳过和内存限频去重。
18. 长期交易记忆已经具备只读 API，可安全查询 market snapshots、recommendations 和 push history，且不会因 GET 请求创建 DB 或返回 raw payload/metadata。
19. Web UI 已具备长期交易记忆只读观察面板，可通过 tab 和过滤项查看市场快照、推荐记录与推送历史，并有 XSS 防护和只读请求验证。
20. ChatAgent 已支持可选注入 `TradingMemoryDB`，以 deterministic summary 方式写入用户查询记忆，不保存 raw message、助手回复、prompt、raw args、token、whisper 或玩家订单详情。
21. ReAct tool message 和 plan aggregate 已具备模型上下文专用压缩层，长结果和敏感字段不会继续无界进入模型上下文。
22. `ToolResult` 已显式区分 `content` / `display_content` / `model_context`，direct 用户输出和模型上下文输出边界更清晰。
23. `query_price`、`riven_search`、Baro order follow-up 和 `query_events` 已具备敏感交易工具 safe model_context，玩家名、profile、whisper 和 raw orders 不再进入模型上下文或相关 session history。
24. `/ws/chat` 与 REST chat 共享输入校验边界，配置读取 API 不再返回 raw secrets。
25. 前端动态 DOM 渲染已减少 post-DOMPurify `innerHTML` 重写和动态 HTML 拼接风险。
26. 外部文本进入模型前已有统一 trust boundary，可将 worldstate、game export、market context 等视为 untrusted data 而不是高权限指令。
27. `market_expert`、`riven_expert`、`event_expert` 已作为内部专家工具接入 ToolRegistry / ReAct / plan，只做分析综合，不绕过工具执行边界。

---

## 26. 明确未做的非目标

本轮没有做以下内容：

- Web UI 展示工具调用时间线
- `/api/tool_events`
- Web UI 统计面板
- 长期交易记忆图表 / 聚合统计面板
- Scheduler job 管理 API（启停、手动触发、修改 interval）
- Scheduler last error / last duration 记录
- SQLite 工具日志
- 将 grouped event checks 进一步拆成 per-method jobs（只有当确实需要独立 interval 或可观察性时再做）
- 持久化 Job / RunHistory
- 进一步扩展 domain-specific 工具结果压缩器到后续新增工具
- `user_queries` 只读 API / Web UI 展示（需先确认只返回 summary 记录）
- 日报写入长期交易记忆
- Memory Tree / 长期交易记忆摘要和压缩
- 将这些改造整合进 `README.md` / `AgentArchitecture.md`

这些内容是明确非目标或后续产品化扩展；不影响 OpenHuman 借鉴路线完成。主架构文档合并按用户要求暂不执行。

---

## 27. OpenHuman 借鉴路线完成状态

OpenHuman 借鉴路线已完成。本项目没有直接复制 OpenHuman，而是把适合 Warframe 智能体的底座能力落地为以下模块：

### 27.1 已完成的借鉴能力

| OpenHuman 借鉴方向 | 当前落地状态 |
|-------------------|--------------|
| 集中化 Tool Registry / Tool Loop | 已完成：`ToolRegistry`、统一 schema 导出、`ChatAgent` 统一执行入口 |
| 工具执行元数据 | 已完成：`ToolExecutionMetadata`、耗时、错误、参数摘要、敏感字段脱敏 |
| 工具调用历史与统计 | 已完成：`ConversationEntry.tool_calls`、`query_tool_call_history()`、`query_tool_call_stats()` |
| 统一 Scheduler 底座 | 已完成：`Scheduler`、`SchedulerRunner`、fixed-delay、首次延迟、错误隔离 |
| PriceMonitor 调度化 | 已完成：主扫描 job、event checks job、知识更新 job、目标生成 job、自学习 job |
| Scheduler 可观察性 API | 已完成：job snapshot、monitor status snapshot、`GET /api/scheduler/status` |
| SQLite 长期交易记忆底座 | 已完成：`TradingMemoryDB`、四类记忆表、过滤查询、retention cleanup |
| 长期交易记忆写入 hook | 已完成：`PriceMonitor` 可选注入 DB，记录结构化 proactive / event-driven push history、Baro recommendation memory 和 market snapshot memory |
| 长期交易记忆只读 API | 已完成：read-open-if-exists、allowlist serializers、market snapshots / recommendations / push history 查询 endpoints |
| 长期交易记忆 Web 观察面板 | 已完成：更多功能入口、三类记忆 tab、过滤、empty/error state、XSS 防护和浏览器侧只读 GET 验证 |
| ChatAgent 用户查询安全摘要写入 | 已完成：可选注入 `TradingMemoryDB`、deterministic summary、allowlist metadata、DB 失败不阻断回答、不暴露 Web/API/UI |
| 工具结果压缩与上下文控制 | 已完成 Phase 4.1 - 4.2C：ReAct tool message 和 plan aggregate 模型上下文专用压缩、敏感字段脱敏、per-step / total 预算、`ToolResult.model_context` 显式分层，并为 `mod_flipper` / `set_profit` / `investment_advisor` / `query_price` / `riven_search` / Baro / `query_events` 增加 compact/safe context；用户可见 direct 输出保持 raw/display |
| Web/API 安全边界 | 已完成 Phase 5A：WebSocket chat 输入校验、配置 secrets allowlist serializer、前端动态 DOM XSS hardening 和 Playwright 回归 |
| 外部内容安全护栏 | 已完成 Phase 5B：`sanitize_untrusted_model_text()` / `wrap_untrusted_model_text()`，market context、worldstate、game export 和 plan/expert context 边界收口 |
| 专家子代理 | 已完成 Phase 4.3：`market_expert` / `riven_expert` / `event_expert` 通过 ToolRegistry、ModelOrchestrator、ReAct / plan 统一接入 |

### 27.2 收尾说明

OpenHuman 借鉴计划到此完成。以下项目有参考价值但本轮明确不做：

1. **user query summaries 只读 API / UI**
   - 当前继续保持 `GET /api/trading-memory/user-queries` 不暴露，避免把用户查询记忆产品化前过早开放。

2. **更重的 observability 面板**
   - 工具时间线、统计面板、Scheduler 管理 API、持久化 run history 等属于产品化扩展，不是借鉴路线完成的必要条件。

3. **Memory Tree / 自动摘要压缩**
   - 当前长期交易记忆已经有结构化 DB、只读 API 和 Web 观察面板；树状记忆 UI 与自动摘要留作后续独立产品需求。

4. **主架构文档合并**
   - 按用户要求暂不合并到 `md/README.md`、`md/AgentArchitecture.md`、`md/FeatureList.md`。
