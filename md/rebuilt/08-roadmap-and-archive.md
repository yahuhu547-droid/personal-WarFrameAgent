# 08. 规划、历史资料与旧文档归档

本文用于承接旧 `md/` 目录中的计划表、升级记录、扫描报告和待优化事项。它不作为当前功能的权威说明；当前功能以 `02-feature-scope.md` 为准。

## 1. 旧文档分类

| 旧文档 | 类型 | 建议处理 |
|---|---|---|
| `md/README.md` | 总览/入口 | 当前信息并入 `rebuilt/README.md`、`01-architecture.md`。旧文档保留作历史入口。 |
| `md/FeatureList.md` | 功能清单 | 已按领域重写到 `02-feature-scope.md`。 |
| `md/AgentArchitecture.md` | 架构说明 | 已拆入 `01-architecture.md` 和 `06-tools-models-safety.md`。 |
| `md/AIArchitectureGuide.md` | 大而全技术说明 | 已拆成架构、数据、模型、安全、运维专题。 |
| `md/WebService.md` | Web/API 说明 | 已拆入 `03-user-interfaces.md` 和 `04-web-api-reference.md`。 |
| `md/FeishuUserGuide.md` | 用户指南 | 可继续保留，也可后续迁到用户手册专题。 |
| `md/OptimizationRoadmap.md` | 扫描报告 + 优化计划 | 规划和质量问题归入本文 backlog。 |
| `md/PersonalAgentRoadmap.md` | 未来路线图 | 只保留脱敏后的方向，真实密钥示例不应迁入新文档。 |
| `md/AgentUpgrade.md` | 阶段升级记录 | 作为历史 release/phase note。 |
| `md/ToolRegistryRefactor.md` | 工具系统重构记录 | 作为工具系统历史背景，当前说明见 `06-tools-models-safety.md`。 |
| `md/WebUIScanReport.md` | Web UI 扫描报告 | 和问题建议合并为 UI backlog。 |
| `md/WebUIIssuesAndSuggestions.md` | Web UI 问题建议 | 和扫描报告合并为 UI backlog。 |
| `md/.pytest_cache/README.md` | pytest 缓存说明 | 不纳入项目文档。 |

## 2. 文档重构后的职责划分

| 内容类型 | 放置位置 |
|---|---|
| 当前架构 | `01-architecture.md` |
| 当前功能范围 | `02-feature-scope.md` |
| 用户入口和交互 | `03-user-interfaces.md` |
| API 路由参考 | `04-web-api-reference.md` |
| 数据、缓存、记忆 | `05-data-memory.md` |
| 工具、模型、安全 | `06-tools-models-safety.md` |
| 运行、测试、维护 | `07-operations-testing.md` |
| 历史计划、扫描报告、待办 | `08-roadmap-and-archive.md` |

## 3. Backlog：文档层面待完善

- 为飞书单独补一份面向最终用户的配置手册，承接 `FeishuUserGuide.md`。
- 为 Web UI 单独补一份页面结构和交互截图文档。
- 为数据构建工具补一份从 export 到 `items_full.json`、RAG、embedding 的流程图。
- 为外部 API 失败、限流、缓存失效补一份排障手册。
- 为模型路由补一份“本地/云端/auto”配置示例，但不要写真实密钥。

## 4. Backlog：质量和技术债方向

来自旧优化计划和扫描报告的方向可以归并为以下几类：

### Web UI

- 合并重复扫描报告，保留可复现的问题、截图和优先级。
- 检查移动端布局、长消息、长列表、错误提示和加载状态。
- 明确 Dashboard、交易记忆、推送配置、飞书配置的用户路径。

### 工具系统

- 保持工具注册、工具路由、工具上下文预算一致。
- 新增工具时必须补测试和文档。
- 对模型上下文中的外部数据继续做最小化和脱敏。

### 模型协作

- 持续评估 scout 预筛选准确率。
- 监控云端失败回退本地后的回答质量。
- 控制缓存 TTL 和复杂度阈值，避免过度调用云端模型。

### 监控和推送

- 避免重复推送。
- 明确每日报告时间窗口。
- 区分测试推送和真实用户推送。
- 对事件订阅、价格提醒、目标机会分别记录触发原因。

### 数据和记忆

- 控制交易记忆保留期。
- 避免保存原始敏感输入。
- 定期检查 SQLite 表和 JSON 文件 schema 演化。

### 近期优先级：验证闭环、运行态观测、普通物品意图

- 补齐 pytest 依赖、pytest 配置和本地产物忽略规则，避免测试文件因环境缺依赖而无法收集。
- 为 Web/飞书/调度/日报增加结构化运行态状态入口，减少依赖手工查日志和进程列表。
- 将市场链接、最低卖家、砍价等交易辅助意图从 Prime 场景扩展到普通物品，并保持确定性订单数据优先。
- 将代码完成后的新增 API、Web 状态展示和排障方式同步回 `03-user-interfaces.md`、`04-web-api-reference.md`、`07-operations-testing.md`。

## 5. 历史阶段记录

项目历史上已经经历多轮增强，旧文档中提到的阶段包括：

### 2026-05-19 飞书用户验证修复阶段

本阶段基于飞书用户视角验证结果，完成以下稳定性和回复质量修复：

- 飞书 Worker 启动前清理旧进程，并加入 `feishu_worker.lock` 单实例锁，降低重复回复风险。
- 补齐“高斯 → gauss”中文 Prime 解析，保证 `高斯 prime 多少钱` 与英文 Gauss Prime 查询一致。
- 对 Prime 场景补齐市场链接、最低卖家、砍价话术等确定性回复。
- 紫卡“值不值得买/评价/分析”会追加购买分析，同时继续遵守紫卡交易只先打招呼、不生成普通物品成交命令的规则。
- 日报调度新增显式 scheduler job，`/api/scheduler/status` 可见。
- 服务重启后验证：核心 unittest 64 个通过；实时 API smoke 覆盖市场链接、最低卖家、砍价、紫卡分析、日报 job；飞书逻辑 worker 为 1。当前遗留问题是虚拟环境缺少 pytest，需在下一阶段补齐。

### 2026-05-19 交易机会推送治理阶段

本阶段完成交易机会重复推送治理和用户可控范围过滤：

- 主动交易机会消息增加结构化原因说明，包括来源策略、利润、ROI、成本/卖价、价差阈值或风险提示。
- 使用 `dedupe_key`、长期 `push_history` 和内存 fallback 做跨扫描 cooldown 去重；利润/ROI 明显变化时允许再次推送。
- 高优先级 `goal_opportunity` 统一走 proactive push，避免 WebSocket 同时收到目标机会和主动机会两条重复消息。
- 聊天新增 `暂停交易机会`、`开启交易机会`、`/push opportunity off/on`。
- 聊天新增 `交易机会只检测MOD`、`交易机会只检测赋能`、`交易机会检测全部` 和 `/push opportunity filter ...`。
- Web 广播侧按最新 `push_proactive` 配置跳过交易机会 opportunity，但不影响 warning、价格提醒、关注、日报、裂缝或周期提醒。

### 更早阶段

- 基础交易 Agent。
- Ollama 聊天和 RAG。
- Prime 套装/缺件/别名扩展。
- 记忆、目标、规则、自学习。
- Web UI 和 API。
- 飞书、WxPusher、主动监控。
- 紫卡搜索、Baro、活动系统。
- 多模型协作、Scout、专家子代理。
- 工具注册表和工具上下文安全重构。

这些内容仅作为演进背景；判断当前能力时应以源码、测试和 `rebuilt/` 文档为准。

## 6. 清理旧文档前的检查清单

如果后续要删除或移动旧文档，建议逐项确认：

- [ ] 没有旧文档仍被 README、脚本或外部链接引用。
- [ ] `FeishuUserGuide.md` 的用户操作步骤已迁移或决定保留。
- [ ] `PersonalAgentRoadmap.md` 中的敏感示例已脱敏或移除。
- [ ] Web UI 扫描报告中的可复现问题已转为 issue/backlog。
- [ ] `ToolRegistryRefactor.md` 中仍有价值的设计约束已并入 `06-tools-models-safety.md`。
- [ ] 新文档中的 API 路径与 `warframe_agent/web/app.py` 最新路由一致。
- [ ] 新文档中的功能范围与当前测试覆盖一致。
