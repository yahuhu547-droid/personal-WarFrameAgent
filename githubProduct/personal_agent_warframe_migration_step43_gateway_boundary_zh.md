# Step 43：多渠道 Gateway 边界评估

## 任务定位

- 来源项目：CowAgent / Suna / OpenClaw。
- 借鉴点：个人 Agent 往往会有 Web、CLI、IM、推送、Webhook、社交平台等多入口，但每个入口的信任边界和动作权限必须明确。
- Warframe 映射：先把本项目已有聊天入口、WebSocket、Feishu、WxPusher 和未来社交 / webhook 入口收束成只读 `gateway_policy`，不新增真实连接器。
- 用户最新约束：暂时不考虑语音对话服务和真实语音；本步不涉及 TTS/STT、麦克风、录音、Live2D 或后台监听。

## 已实现能力

- 新增 `warframe_agent/gateway_policy.py`：
  - `classify_gateway_request(...)`：按 channel / action / authenticated 判断入口可信度。
  - `build_gateway_policy()`：输出只读 Gateway 安全矩阵。
- `build_runtime_safety_policy(...)` 新增：
  - `capabilities.multi_channel_gateway`
  - `gateway_policy`
- 当前策略：
  - `web_chat`、`websocket_chat`、`local_cli`：交互式用户输入。
  - `feishu_bot`：配置过的外部入口，必须复用已有确认流程。
  - `wxpusher`、`feishu_push`：只作为出站通知，不作为入站命令入口。
  - `bilibili_comment`、`anonymous_webhook`、`github_issue`、卖家 / 买家私信：默认阻断。
  - 任意工具执行、shell、浏览器控制、文件写入、下单、私信等高风险动作：默认阻断。

## 安全边界

- 本步不新增平台账号、Webhook handler、社交抓取、Browser/GUI executor、scheduler executor、语音入口或后台监听。
- policy 输出不包含 raw payload、handler、token、secret、app_secret、chat_id、玩家名、profile URL 或 `/w`。
- 外部入口即使已配置，也只能进入已有确认式聊天/任务链路，不能绕过 `ToolRouter`、`AgentPlan` review 或用户确认。

## 验证结果

红测先失败于缺少 `warframe_agent.gateway_policy`：

```txt
ModuleNotFoundError: No module named 'warframe_agent.gateway_policy'
```

实现后目标测试通过：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_tool_registry.py -k "gateway_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：

```txt
6 passed, 33 deselected
```

补充 Web API 可写环境验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：`1 passed, 71 deselected`。普通沙箱会因 SQLite WAL 数据库文件无法打开而失败；已在可写运行环境补跑通过。

## 后续建议

- 下一步可继续非语音分支：skills / plugin 生态边界评估，或 Web API / Runtime 面板展示 Gateway policy。
- 若将来要开放真实外部入口，应先设计鉴权、绑定用户、可撤销授权、速率限制、确认链路和审计摘要。
- 真实 Browser/GUI 自动化、服务恢复和任意触发器平台仍需单独设计，不应从 Gateway policy 直接放开。
