# Step 14: 运行态验证闭环

## 本步目标

本步不新增大功能，目标是把 Step 4-13 的运行态、安全策略、ToolRegistry、AgentTrace、AgentPlan、个人画像反馈和机会复盘命令做一次集中补验证。Rawls 子代理只读梳理后建议先补齐验证闭环，再继续做普通物品交易辅助意图、长期记忆 vault 化或 Scout 推送质量评估。

## 验证中发现并修复的问题

1. `/api/runtime/status.recent_tool_calls.items[].args_summary` 可能从历史日志中带出 `message_context`、`prompt`、`model_context` 等模型不应见字段。
   - 修复：扩展 `warframe_agent/web/app.py` 的运行态敏感键过滤，跳过 `message_context`、`prompt`、`raw_arguments`、`result_summary`、`display_content`、`model_context`、`final_answer`、`profile`、`whisper` 等键。

2. ToolRegistry 聚合摘要字段 `hidden_schema_count` 与测试中模拟的敏感值 `hidden` 撞名，会让安全断言误判为泄漏。
   - 修复：将聚合字段改为 `private_schema_count`，前端显示为 `private_schema`。
   - 补充测试：`tests/test_tool_registry.py` 明确断言 `private_schema_count`，并确认摘要中不出现 `hidden`。

## 已运行验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_registry.py -k "tool_registry_safety_summary or runtime_safety_policy_embeds_tool_registry_summary" -q
# 2 passed

.\.venv\Scripts\python.exe -m pytest tests/test_personal_profile.py -k "sqlite_opportunity_outcomes or outcome_feedback" -q
# 2 passed

.\.venv\Scripts\python.exe -m pytest tests/test_chat_memory_commands.py -k "sqlite_outcomes or review" -q
# 5 passed

.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -k "runtime_status" -q
# 普通沙箱导入 Web app 时复现 SQLite WAL 写目录限制
# 可写环境重跑后：5 passed

.\.venv\Scripts\python.exe -m pytest tests/test_web_ui_playwright.py -k "runtime_panel" -q
# 2 passed

node --check warframe_agent/web/static/js/app.js
# passed
```

## 当前结论

- Runtime status API 已覆盖基础状态、AgentTrace、AgentPlan、安全策略、后台任务、WxPusher/Feishu 安全视图和最近工具调用安全摘要。
- Web Runtime 面板已覆盖 AgentTrace 和 AgentPlan 可见摘要，并确认 token、raw arguments、result summary、final answer、玩家名和 `/w` 不进入 DOM。
- ToolRegistry 安全摘要保持聚合级别，只暴露数量和分布，不暴露工具名、handler、参数 schema、ToolResult、message context 或 model context。
- 机会复盘和 SQLite 画像反馈链路目标测试通过。

## 下一轮剩余学习任务建议

1. 普通物品交易辅助意图扩展：把市场链接、最低卖家、砍价等确定性能力从 Prime 场景扩展到普通物品。
2. 长期记忆 vault 化：借鉴 OpenHuman 的 Markdown vault + SQLite metadata，把复盘记忆整理成用户可审计、可迁移的资料层。
3. Scout 推送质量评估：为主动机会、事件订阅、价格提醒和目标机会记录触发原因与反馈质量。
4. 聊天模式分层：借鉴 EchoBot 的 `auto/chat_only/force_agent` 思路，把即时陪伴回复和后台工具执行模式做成显式可观察状态。

本步未安装新包，也未提交或推送 GitHub。
