# Step 44：Skills / Plugin 生态边界评估

## 任务定位

- 来源项目：OpenManus / Suna / OpenClaw / Codex skills。
- 借鉴点：个人 Agent 可以通过 skills、plugins、connectors 扩展能力，但扩展能力进入运行时前必须有审查、确认和权限边界。
- Warframe 映射：先把本项目的 skills / plugin / connector 生态整理成只读 `plugin_policy`，不安装新插件、不启用新账号连接器、不把插件能力自动映射到 ToolRegistry。
- 用户最新约束：暂时不考虑语音对话服务和真实语音；本步不涉及 TTS/STT、麦克风、录音、Live2D 或后台监听。

## 已实现能力

- 新增 `warframe_agent/plugin_policy.py`：
  - `classify_plugin_capability(...)`：按 source / capability / installed / explicit_enable 判断插件生态能力边界。
  - `build_plugin_policy()`：输出只读 skills / plugin 安全矩阵。
- `build_runtime_safety_policy(...)` 新增：
  - `capabilities.skills_plugin_ecosystem`
  - `plugin_policy`
- 当前策略：
  - `local_skill`、`system_skill`、`project_skill`：只作为 prompt / workflow guidance。
  - `personal_plugin`、`codex_plugin`、`local_plugin`：已安装时仍需 review，不能自动进入 ToolRegistry。
  - `connector`、`external_connector`、`account_connector`：必须显式启用并经用户确认。
  - shell、文件写入、浏览器控制、scheduler 创建、凭据访问、社交发帖、交易动作：默认阻断。

## 安全边界

- 本步不安装插件、不请求 plugin install、不新增 connector、不读取账号 token、不新增平台 API。
- policy 输出不包含 raw manifest、handler、params、token、secret、api_key、account_id、真实本机路径或用户账号标识。
- 插件能力即使未来被启用，也必须先映射到 `ToolRegistry` metadata、`AgentPlan` review 和用户确认链路。

## 验证结果

红测先失败于缺少 `warframe_agent.plugin_policy`：

```txt
ModuleNotFoundError: No module named 'warframe_agent.plugin_policy'
```

实现后目标测试通过：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plugin_policy.py tests\test_tool_registry.py -k "plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`7 passed, 33 deselected`。

补充 Web API 可写环境验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`1 passed, 71 deselected`。

## 后续建议

- 下一步可以把 `gateway_policy` 和 `plugin_policy` 的安全字段展示到 Runtime 面板，但只做只读展示，不加开关按钮。
- 最后做 Step 46 非语音学习路线闭环审计，确认非语音借鉴计划完成。
- 真实 Browser/GUI 自动化、服务恢复、任意触发器、真实语音和平台私信仍需单独设计。
