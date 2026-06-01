# Step 45：Runtime Policy 可见性

## 任务定位

- 来源项目：Suna / OpenManus / OpenClaw 的运行态控制面和能力边界透明化思路。
- 借鉴点：高风险能力不直接开放，但要让用户在运行态看见当前边界，知道哪些入口、插件、连接器和动作是 disabled / restricted / guidance-only。
- Warframe 映射：把 Step 43 的 `gateway_policy` 和 Step 44 的 `plugin_policy` 只读展示到 Runtime 面板。
- 用户最新约束：暂时不考虑语音对话服务和真实语音；本步不涉及 TTS/STT、麦克风、录音、Live2D 或后台监听。

## 已实现能力

- `warframe_agent/web/static/js/app.js`：
  - Runtime 摘要卡新增 `Gateway Policy` 和 `Plugin Policy`。
  - Runtime 详情新增只读 `renderRuntimeGatewayPolicy(...)` 和 `renderRuntimePluginPolicy(...)`。
  - 只展示 default、runtime 是否启用、decision counts、channel / capability、decision、trust boundary 和 reason。
  - 新增 `policyDecisionCount(...)`。
  - 前端敏感 key / text 过滤补充 `account_id`、`api_key`、`handler`、`params`、`manifest`、`payload`、`GatewayLeak`、`account-123` 等。
- `tests/test_web_ui_playwright.py`：
  - Runtime 面板 fixture 增加 `gateway_policy` / `plugin_policy` 的安全快照。
  - Runtime 面板测试增加 Gateway / Plugin policy 文本断言和泄漏禁止断言。
  - 新增静态契约测试 `test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections`。

## 安全边界

- 本步只做只读展示，不新增按钮、开关、安装入口、账号输入、Webhook、connector、Browser/GUI executor、scheduler executor 或真实外部入口。
- 前端忽略 `raw_*`、`handler`、`params`、`manifest`、`payload`、`token`、`secret`、`account_id`、`api_key` 等字段。
- 即使后端 payload 被污染，Runtime 面板也不应显示 raw payload、raw manifest、token、玩家名、profile、`/w`、账号 ID 或 API key。

## 验证结果

红测：可写环境中 Playwright 目标测试先失败于缺少 `Gateway Policy` 专门展示，说明旧 UI 只显示 capability，没有显示 policy matrix。

实现后可运行验证：

```powershell
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`node --check` 退出码 0；静态契约测试 `1 passed`。

完整浏览器目标验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-final-playwright -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-final-playwright-writable -p no:cacheprovider
```

结果：普通沙箱中仍复现 `RuntimeError: Web server did not become ready`；可写运行环境补跑通过，结果为 `1 passed`。该目标测试已经确认 Runtime 面板能展示 Gateway / Plugin policy，并过滤 raw payload、raw manifest、account id、api key、token、玩家名和 `/w` 等敏感文本。

## 后续建议

- Step 45 可标记为 `100% / 已完成`。
- 后续不应在 Runtime 面板中继续增加控制按钮或开关，除非另开新阶段完成权限、确认、审计和可中断设计。
