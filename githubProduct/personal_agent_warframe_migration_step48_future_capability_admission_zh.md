# Step 48：未来高权限能力准入策略

## 任务定位

- 路线归属：Step 46 / Step 47 之后的新阶段安全基座，不属于旧非语音学习借鉴队列的补课。
- 借鉴来源：OpenManus / Suna / OpenClaw 中关于 sandbox、worker、connector、plugin、browser 和触发器的高权限能力边界。
- Warframe 映射：新增只读 `future_capability_policy`，让未来真实 Browser/GUI executor、服务恢复、任意触发器平台、受控插件安装、connector 启用、真实语音等能力在进入运行时前先被统一门禁描述。
- 最新用户约束：暂不考虑语音对话服务和真实语音，因此真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续冻结。

## 已实现能力

- 新增 `warframe_agent/future_capability_policy.py`：
  - `classify_future_capability(...)`
  - `build_future_capability_policy()`
- `build_runtime_safety_policy(...)` 新增：
  - `capabilities.future_capability_admission`
  - `future_capability_policy`
- 新增 `tests/test_future_capability_policy.py`，并扩展 `tests/test_tool_registry.py` 的 runtime safety 断言。
- `capabilities.future_capability_admission.enabled` 明确为 `False`，表示策略可见但未来高权限运行时入口未启用。
- `classify_future_capability(...)` 会把疑似敏感的 capability 名称归一为 `unknown_future_capability`，避免未来调用方误把 token / key 放进能力名时被序列化泄露。

## 决策矩阵

| 决策 | 适用场景 | 当前处理 |
| --- | --- | --- |
| `allow_design_only` | 设计文档、权限设计、风险评审 | 允许作为文档设计，不启用 runtime |
| `requires_new_stage_design` | Browser/GUI executor、服务恢复、任意触发器、plugin install、connector enable | 必须另开新阶段设计 |
| `frozen_by_current_user_instruction` | 真实语音、TTS/STT、麦克风、录音、Live2D、后台监听 | 按用户当前指令冻结 |
| `blocked_public_or_private_inbound` | 匿名 webhook、公共评论命令、卖家 / 买家 / 平台私信命令 | 默认阻断 |
| `blocked_uncontrolled_runtime` | shell、通用文件写入、凭据访问、社交发帖、交易动作 | 默认阻断 |

## 安全边界

- 本步只新增只读策略快照，不注册 ToolRegistry 工具，不新增 executor，不安装插件，不启用 connector，不启动服务。
- 不新增前端按钮、开关、账号输入、webhook、DM 命令入口、shell、通用文件写入、scheduler 创建、Browser/GUI 控制或真实语音能力。
- policy 输出不包含 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_manifest、raw_arguments、handler、params、玩家名、profile、`/w`、本机路径或私网地址。
- 未来高权限能力如果真的进入运行时，必须另开设计，并经过 `ToolRegistry -> AgentPlan review -> 用户确认 -> 可中断执行 -> 审计摘要`。

## 验证摘要

红测：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_tool_registry.py -k "future_capability or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-red -p no:cacheprovider
```

结果：按预期失败于 `ModuleNotFoundError: No module named 'warframe_agent.future_capability_policy'`。

绿测：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_tool_registry.py -k "future_capability or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-green -p no:cacheprovider
```

结果：初始实现为 `7 passed, 33 deselected`。

子代理复核后补充红绿测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_tool_registry.py -k "sensitive_capability_names or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-review-red -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_tool_registry.py -k "future_capability or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-review-green -p no:cacheprovider
```

结果：补充红测先失败于敏感 capability 名泄露和 `future_capability_admission.enabled=True`；修复后绿测为 `9 passed, 33 deselected`。

最终复核：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step48-final -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step48-web-api-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/future_capability_policy.py','warframe_agent/safety_policy.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

结果：policy 联跑 `20 passed, 33 deselected`；Web API 普通沙箱因 SQLite WAL 数据库文件无法打开失败，可写运行环境补跑 `1 passed, 71 deselected`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

## 后续路线

- GitHub 项目个人 Agent 非语音学习借鉴计划已经完成；Step 48 是新阶段安全准入层。
- 后续如要推进真实 Browser/GUI executor、服务恢复 / 任意触发器平台、真实语音 / Live2D、受控插件安装或 connector 启用，必须另开计划和权限设计。
