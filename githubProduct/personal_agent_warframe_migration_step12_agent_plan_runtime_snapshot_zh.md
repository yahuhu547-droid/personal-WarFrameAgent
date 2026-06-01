# Step 12: AgentPlan 运行态只读快照

本步借鉴 OpenManus 的 plan / step 可观测性，但只做只读运行态快照，不让计划器接管 WarFrameAgent 主链路。

## 学习借鉴点

- `AgentTrace` 现在可在现有 `plan` 工具被调用时记录 `AgentPlanSnapshot`。
- 每个 `AgentPlanStep` 只记录 step index、工具名、purpose、安全参数摘要、状态、耗时、是否成功和是否有结果。
- Web `/api/runtime/status` 只展示安全 plan 快照，不展示 raw arguments、完整 result summary、final answer 原文、玩家 profile、`/w` 或 token。
- 计划状态只跟随现有执行过程：pending、running、completed、failed；它不改变工具执行顺序，也不新增工具权限。

## 使用场景

当用户问“比较多个物品”“分别查几个目标”这类会触发 `plan` 工具的问题时，运行态面板可看到最近一次计划包含哪些工具步骤、每步是否完成、耗时大致多少。排障时可以确认 Agent 是直接回答、单工具回答，还是进入了 plan 分解。

## 安全边界

计划快照是内存诊断对象，不写入长期记忆，不进入模型上下文，也不保存完整工具结果。参数摘要继续复用 `tool_context` 和 runtime status 的敏感字段过滤。
