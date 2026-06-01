# Step 46：非语音学习借鉴路线闭环审计

## 结论

截至 2026-05-30，暂不考虑语音对话服务和真实语音的前提下，个人 Agent 学习借鉴路线已完成代码与文档闭环。

最终补跑：Step 45 的 Runtime 面板 Playwright 目标测试 `test_runtime_panel_renders_jobs_tasks_and_safe_state` 已在可写运行环境补跑通过，结果为 `1 passed`。普通沙箱中仍会出现 uvicorn 未就绪，因此后续同类浏览器目标测试仍应使用可写运行环境补跑。

## 覆盖矩阵

| 来源项目 | 已借鉴主题 | Warframe 映射 | 当前状态 |
| --- | --- | --- | --- |
| CowAgent | 长期运行、运维健康、多入口边界 | `ops_health`、`gateway_policy`、route ledger | 已完成 |
| OpenManus | Tool / planner / browser 边界 | `AgentPlan` review、`browser_gui_safety`、`gateway_policy` | 已完成 |
| LangManus | planner-reviewer-verifier、多角色保守落地 | `review_execution_plan(...)`、确认链路、保留单 Agent 主链路 | 已完成 |
| OpenHuman | 可检查记忆、陪伴边界 | `memory_vault`、text-only companion boundary | 已完成；真实语音冻结 |
| EchoBot | 陪伴、语音、persona 与后台任务分离 | `companion_experience_policy`，真实语音禁用 | 已覆盖安全边界；真实语音冻结 |
| Open-AutoGLM | Browser / GUI 自动化风险 | `browser_gui_safety` 行为矩阵 | 已完成安全边界；真实 GUI executor 未开放 |
| OpenClaw | 运行态、插件、Gateway、自动化边界 | `gateway_policy`、`plugin_policy`、Runtime 可见性 | 已完成；Playwright 补跑已通过 |
| Suna / Kortix | agent runtime、控制面、worker / sandbox 权限 | `runtime_status`、`ToolRegistry` 聚合、只读 Runtime 面板 | 已完成；高权限 sandbox 未开放 |

## 已完成能力

- 单 Agent 主链路保留：`ChatAgent + ToolRouter + ModelOrchestrator`。
- 多 Agent 思路保守迁移：只拆 `AgentPlan`、reviewer、verifier 和 confirmation，不引入完整多 Agent runtime。
- 计划确认链路：Step 41 底层确认码，Step 42 ChatAgent “确认执行 / 取消执行”闭环。
- 运维健康：`ops_health` 只读摘要。
- 可检查记忆：`memory_vault` 和 `GET /api/memory/vault`。
- Browser / GUI：`browser_gui_safety` 只读行为矩阵，不开放 executor。
- 语音 / 陪伴：`companion_experience_policy` 只定义 text-only 与禁用边界，真实语音冻结。
- 多渠道入口：`gateway_policy` 定义 Web/WS/CLI、Feishu、WxPusher、公共评论、匿名 webhook、高风险动作边界。
- Skills / Plugin：`plugin_policy` 定义 guidance-only、review、explicit enable 和高风险能力阻断。
- Runtime 可见性：Runtime 面板显示 Gateway / Plugin policy 的只读安全摘要。

## 安全边界总表

| 分支 | 当前处理 |
| --- | --- |
| 真实语音 / TTS / STT / 麦克风 / 录音 / Live2D | 冻结，不推进 |
| Browser / GUI 自动执行 | 仅安全矩阵，不开放 executor |
| shell / 通用文件写入 | 不暴露给 Agent runtime |
| 任意 scheduler / 触发器平台 | 不开放，只报告已注册任务 |
| public comments / anonymous webhook / seller DM / buyer DM | blocked |
| 插件安装 / connector 启用 | 不自动安装，不自动启用 |
| 云端模型调用 | 必须经 `ModelOrchestrator` / `llm.py` |
| raw payload / raw manifest / raw tool args / token / secret / account_id / profile / `/w` | 不进入 Runtime 面板或长期摘要 |

## 验证摘要

已通过：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_tool_registry.py -k "gateway_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_plugin_policy.py tests\test_tool_registry.py -k "plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
```

结果：

- Gateway / runtime policy：`6 passed, 33 deselected`。
- Plugin / runtime policy：`7 passed, 33 deselected`。
- Web API runtime safety：`1 passed, 71 deselected`。
- Runtime static contract：`1 passed`。
- JS syntax：退出码 0。

最终联跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/gateway_policy.py','warframe_agent/plugin_policy.py','warframe_agent/safety_policy.py','warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\gateway_policy.py warframe_agent\plugin_policy.py warframe_agent\safety_policy.py warframe_agent\web\static\js\app.js warframe_agent\chat.py warframe_agent\tool_router.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py tests\test_web_api.py tests\test_web_ui_playwright.py docs\superpowers\plans\2026-05-30-multi-channel-gateway-boundary.md docs\superpowers\plans\2026-05-30-non-voice-learning-closure.md githubProduct\personal_agent_warframe_migration_step43_gateway_boundary_zh.md githubProduct\personal_agent_warframe_migration_step44_plugin_policy_zh.md githubProduct\personal_agent_warframe_migration_step45_runtime_policy_visibility_zh.md githubProduct\personal_agent_warframe_migration_step46_non_voice_learning_closure_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\06-tools-models-safety.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md AGENTS.md
```

结果：Gateway / Plugin / runtime policy 联跑 `12 passed, 33 deselected`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

最终 Playwright 补跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-final-playwright-writable -p no:cacheprovider
```

结果：`1 passed`。

## 后续路线

- Step 45 Playwright 目标测试已补跑通过，Step 45 可保持 `100% / 已完成`。
- 若未来继续学习借鉴，应另开新阶段，而不是继续旧队列：
  - 真实 Browser/GUI executor 权限设计。
  - 服务恢复 / 任意触发器平台设计。
  - 真实语音 / Live2D 权限链路设计。
  - 受控插件安装与 connector 启用设计。
