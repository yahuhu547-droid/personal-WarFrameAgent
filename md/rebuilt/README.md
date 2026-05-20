# Warframe 交易助手文档总览

本目录是对 `md/` 下分散文档的重新整理版本，目标是把“当前功能说明”“架构说明”“接口参考”“运行维护”“历史计划/报告”分开维护，避免计划表、扫描报告和功能文档继续混杂。

## 文档边界

- 本目录描述当前代码库已经实现或明确存在的范围。
- 计划、扫描报告、历史升级记录统一放入 `08-roadmap-and-archive.md`，不再混入功能说明。
- 外部服务、API Key、推送令牌等只写配置位置和用途，不写真实密钥。
- 本次重构只新增文档，不删除或覆盖旧文档。

## 新文档索引

| 文档 | 用途 |
|---|---|
| `01-architecture.md` | 总体架构、核心数据流、模块边界。 |
| `02-feature-scope.md` | 当前功能范围矩阵，按业务能力归类。 |
| `03-user-interfaces.md` | 聊天、Slash Command、Web UI、飞书、WxPusher 的使用面。 |
| `04-web-api-reference.md` | FastAPI 接口按领域归档。 |
| `05-data-memory.md` | 数据来源、缓存、长期记忆、交易记忆、历史库。 |
| `06-tools-models-safety.md` | 工具注册/路由、多模型协作、外部数据安全边界。 |
| `07-operations-testing.md` | 启动、配置、测试、排障和维护建议。 |
| `08-roadmap-and-archive.md` | 旧文档归档映射、规划类内容、质量改进 backlog。 |

## 推荐阅读顺序

1. 新人或接手维护：先读 `01-architecture.md` 和 `02-feature-scope.md`。
2. 要接 API 或前端：读 `03-user-interfaces.md` 和 `04-web-api-reference.md`。
3. 要改 Agent、模型或工具：读 `06-tools-models-safety.md`。
4. 要处理数据、记忆、推送或监控：读 `05-data-memory.md` 和 `07-operations-testing.md`。
5. 要看旧计划、扫描报告、未完成事项：读 `08-roadmap-and-archive.md`。

## 旧文档处理建议

旧文档暂时保留，作为历史资料。后续如果要彻底清理，建议先确认以下迁移完成：

- `README.md`、`FeatureList.md`、`AgentArchitecture.md` 的现状信息已并入本目录。
- `AIArchitectureGuide.md`、`WebService.md` 的架构与接口信息已拆分到对应专题文档。
- `OptimizationRoadmap.md`、`PersonalAgentRoadmap.md`、`AgentUpgrade.md`、Web UI 扫描报告已归到历史和 backlog，不再作为当前功能权威来源。
