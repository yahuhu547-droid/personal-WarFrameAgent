# Step 38 Browser / GUI Agent 安全边界

生成日期：2026-05-28

## 借鉴来源

- OpenManus：借鉴浏览器状态回灌、页面观察和动作执行前边界审查。
- Open-AutoGLM：借鉴 GUI / 移动端动作空间必须有人工接管、禁止动作和私网边界。

## 借鉴点

本步没有实现 Browser Agent，也没有新增 Playwright / ADB / HDC 执行器。实际吸收的是安全边界：

- 将浏览器和 GUI 行为分成只读、需人工确认、默认阻断三类。
- 将登录、支付、删除、私信、下单、凭据输入、任意脚本和私网目标列为 blocked。
- 将点击、输入、提交表单、下载、上传和剪贴板写入列为 requires human confirmation。
- 将公共页面读取、文本提取、截图和 DOM 检查列为未来只读候选。

## 本项目落点

新增模块：

```text
warframe_agent/browser_gui_safety.py
```

核心函数：

```text
classify_browser_gui_action(...)
build_browser_gui_safety_policy()
```

Runtime 安全策略新增：

```text
/api/runtime/status.safety_policy.browser_gui_policy
/api/runtime/status.safety_policy.capabilities.browser_gui_automation
```

其中 `browser_gui_automation` 仍为 `available=false`、`default=disabled`、`requires_explicit_enable=true`。

## 安全边界

本步只做只读策略快照，不新增任何实际自动化能力：

- 不新增 Browser Agent。
- 不注册可由 LLM 直接调用的浏览器工具。
- 不新增点击、输入、登录、下单、私信、上传、下载或剪贴板写入能力。
- 不新增 scheduler job、后台 worker 或自动触发器。
- 不读取 cookie、localStorage、sessionStorage、DOM 原文、截图 OCR 原文或完整 URL query。

输出只包含动作类别、决策、目标范围、是否需要人工确认、是否 blocked 和安全 reason。私网 URL、token、玩家名、`/w` 和 Bearer token 会被过滤或不进入输出。

## 已实现文件

- `warframe_agent/browser_gui_safety.py`
- `warframe_agent/safety_policy.py`
- `tests/test_browser_gui_safety.py`
- `tests/test_tool_registry.py`
- `tests/test_web_api.py`
- `docs/superpowers/plans/2026-05-28-browser-gui-safety-boundary.md`

## 子代理审计结论

子代理做了只读审计，建议与本步实现一致：

- 优先复用 `safety_policy.py`、`ToolRegistry` 安全元数据和 `/api/runtime/status`。
- 不改 `ChatAgent` 主链路，不新增 Playwright/ADB/HDC executor，不把 Browser/GUI 注册为 exposed tool。
- 必测私网、登录、下单、私信、删除、cookie/localStorage/sessionStorage、token、profile、`/w`、raw arguments 和 result summary 泄漏。

## 验证结果

TDD 红测：

- `tests/test_browser_gui_safety.py` 初次运行因 `ModuleNotFoundError: No module named 'warframe_agent.browser_gui_safety'` 按预期失败。
- `tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 初次运行因缺少 `browser_gui_policy` 按预期失败。
- `tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy"` 在可写运行环境中初次运行因缺少 `browser_gui_automation` 按预期失败。

Green 验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_browser_gui_safety.py -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`5 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`1 passed, 33 deselected`

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`1 passed, 71 deselected`

备注：普通沙箱导入 Web app 时仍会遇到既有 SQLite WAL 数据库文件权限限制；Web API 目标测试已在可写运行环境中补跑。

## 当前结论

Step 38 覆盖了剩余学习队列中的 Browser / GUI Agent 安全边界评估。路线没有偏离：本步没有开放 GUI 自动执行，只补上未来接入前必须存在的动作分级和 runtime 可见性。

下一步更适合继续：

- 语音和陪伴式体验评估。
- Step 35 分支的“软拦截 -> 用户确认 -> 受控执行”确认链路。
