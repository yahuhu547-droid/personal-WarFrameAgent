# Step 50：学习借鉴与改善完成 Runtime 快照

## 任务定位

- 路线归属：Step 50 是“学习借鉴与改善完成快照”，不是旧队列补课，也不是启用新高权限能力。
- 完成结论：旧的 GitHub 项目个人 Agent 非语音学习借鉴计划已按 Step 47 完成；Step 48 / Step 49 是完成后的新阶段安全准入和 Runtime 可见性改善。
- 本步目标：把“路线完成 + 改善完成 + 后续高权限必须另开设计”做成 `/api/runtime/status.learning_completion` 和 Runtime 面板只读快照，减少跨会话和上下文压缩后的误解。

## 已实现能力

- 新增 `warframe_agent/learning_completion.py`：
  - `build_learning_completion_snapshot()`
  - `status=complete`
  - `legacy_non_voice_learning_complete=true`
  - `improvement_closure_complete=true`
  - `runtime_enablement_changed=false`
- `/api/runtime/status` 新增 top-level `learning_completion`。
- Runtime 面板新增 `Learning Completion` 摘要卡和详情区，展示最近完成步骤和仍需另开设计的高权限候选能力。
- 新增 `tests/test_learning_completion.py`，并扩展 Web API / Runtime 面板测试。

## 安全边界

- 本步只新增只读完成状态快照，不注册 ToolRegistry 工具，不新增 executor，不安装插件，不启用 connector，不启动服务。
- 不新增按钮、开关、账号输入、webhook、DM 命令入口、shell、通用文件写入、scheduler 创建、Browser/GUI 控制或真实语音能力。
- `future_capability_admission.enabled=False` 保持不变，表示策略可见但未来高权限运行时入口未启用。
- 真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续按用户当前指令冻结。
- 快照和文档不记录 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_manifest、raw_arguments、raw_plan、handler、params、profile、`/w`、本机私密路径、私网地址或玩家私信信息。
- 所有云端模型调用边界不变：不得在新快照、展示层或 helper 中读取 `.env`、拼 API header 或绕过 `ModelOrchestrator` / `llm.py`。

## 验证摘要

红测：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step50-red -p no:cacheprovider
```

结果：按预期失败于 `ModuleNotFoundError: No module named 'warframe_agent.learning_completion'`。

绿测与补跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step50-learning -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step50-static -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_endpoint or runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step50-api-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-step50-playwright-writable -p no:cacheprovider
```

结果：unit `3 passed`；JS 语法检查退出码 0；Runtime 静态契约 `1 passed`；Web API 可写环境补跑 `2 passed, 70 deselected`；完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`。普通沙箱中 Web API 仍失败于 SQLite WAL 数据库文件无法打开，Playwright 仍失败于 uvicorn 未就绪。

最终复核：policy / gateway / plugin / runtime safety 联跑 `23 passed, 33 deselected`；Runtime 静态契约复核 `1 passed`；`warframe_agent/learning_completion.py`、`warframe_agent/future_capability_policy.py`、`warframe_agent/safety_policy.py`、`warframe_agent/web/app.py` AST OK；`node --check warframe_agent\web\static\js\app.js` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

## 后续路线

- 到 Step 50 为止，“GitHub 个人 Agent 非语音学习借鉴计划完成 + Step 48/49 改善完成”已经具备代码、API、Runtime UI 和文档四层闭环。
- 后续若要推进真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装或 connector 启用，必须另开计划和权限设计。
