# Step 49：Future Capability Runtime 可见性补齐

## 任务定位

- 路线归属：Step 49 是 Step 48 `future_capability_policy` 的 Runtime 面板只读可见性补齐，不属于旧非语音学习借鉴队列的未完成项。
- 借鉴来源：OpenManus / Suna / OpenClaw 中“高权限能力必须先可见、可审计、不可误启用”的控制面思路。
- Warframe 映射：把未来 Browser/GUI executor、服务恢复、任意触发器、插件安装、connector、真实语音等候选能力的准入矩阵展示到 Runtime 面板。
- 最新用户约束：暂不考虑语音对话服务和真实语音，因此真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续冻结。

## 已实现能力

- `warframe_agent/web/static/js/app.js` 新增 Future Capability Policy 摘要卡和详情区。
- Runtime 面板现在展示：
  - `future_capability_admission`
  - `default_mode=design_required_before_runtime`
  - `runtime_enablement_allowed=false`
  - `requires_new_stage_design`
  - `blocked_uncontrolled_runtime`
- 扩展前端敏感字段过滤，覆盖 `credential`、`user_id`、`private_network_url`、`local_path`、`raw_plan`、`raw_config` 等未来高权限场景可能出现的泄露形态。
- `tests/test_web_ui_playwright.py` 扩展静态契约和完整 Runtime 面板渲染断言。
- `tests/test_web_api.py` 补充 `future_capability_policy` 与 `future_capability_admission.enabled=False` 的 API 契约断言。

## 安全边界

- 本步只新增只读 UI 展示，不注册 ToolRegistry 工具，不新增 executor，不安装插件，不启用 connector，不启动服务。
- 不新增按钮、开关、账号输入、webhook、DM 命令入口、shell、通用文件写入、scheduler 创建、Browser/GUI 控制或真实语音能力。
- `future_capability_admission.enabled=False` 继续表示策略可见，但未来高权限运行时入口未启用。
- Runtime 面板不渲染 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_manifest、raw_arguments、raw_plan、handler、params、profile、`/w`、本机路径、私网地址或玩家私信信息。
- 所有云端模型调用边界不变：不得在展示层、policy helper 或新组件中读取 `.env`、拼 API header 或绕过 `ModelOrchestrator` / `llm.py`。

## 验证摘要

红测：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step49-red-static -p no:cacheprovider
```

结果：按预期失败于缺少 `renderRuntimeFutureCapabilityPolicy`。

绿测与补跑：

```powershell
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step49-static -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-step49-playwright-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step49-api-writable -p no:cacheprovider
```

结果：JS 语法检查退出码 0；静态契约 `1 passed`；完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`；Web API 可写环境补跑 `1 passed, 71 deselected`。普通沙箱中 Playwright 仍失败于 uvicorn 未就绪，Web API 仍失败于 SQLite WAL 数据库文件无法打开。

最终复核：policy 联跑 `20 passed, 33 deselected`；Runtime 静态契约 `1 passed`；AST OK；`node --check` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

## 后续路线

- GitHub 项目个人 Agent 非语音学习借鉴计划已经完成；Step 49 是新阶段安全准入层的可见性改善。
- 后续若要推进真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装或 connector 启用，必须另开计划和权限设计。
