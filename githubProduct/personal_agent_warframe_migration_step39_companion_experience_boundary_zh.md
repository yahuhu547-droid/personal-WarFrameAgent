# Step 39：语音和陪伴式体验安全边界

日期：2026-05-28

## 来源项目

- EchoBot：Decision / Roleplay / Agent 分层、语音、Live2D、即时陪伴回复与后台任务分离。
- OpenHuman：本地优先个人记忆、语音入口、可检查个人上下文。
- OpenClaw：常驻个人助手、多渠道入口、voice / canvas / plugins 的产品边界。

## 借鉴点

- 文本陪伴和生产力任务需要分层，不能因为“陪我”就直接触发交易或后台动作。
- 语音、麦克风、录音、Live2D、平台 token 和后台监听都属于高权限体验层，必须先有明确策略边界。
- Warframe 游戏内“同伴/宠物/库娃/库狛/守护”是游戏建议主题，不应误判为人格陪伴或语音入口。

## 本项目映射

- 新增 `warframe_agent/companion_experience.py`：
  - `classify_companion_experience_request(...)`
  - `build_companion_experience_policy()`
- `/api/runtime/status.safety_policy` 新增：
  - `capabilities.voice_companion_experience`
  - `companion_experience_policy`
- 不修改 `ChatAgent.answer()`，不修改 system prompt，不新增前端按钮，不注册新工具。

## 安全边界

- 本步只做只读策略快照和 deterministic 分类器。
- 不下载模型，不安装依赖，不接 TTS/STT，不读 `.env`，不新增 API key 配置。
- 不启用麦克风、录音、后台监听、Live2D、桌面宠物、平台 token 或语音服务。
- 私聊卖家、下单、联系买家等交易动作继续 `blocked_sensitive_action`。
- 陪伴式后台任务只允许走现有提醒/任务/用户确认流程，不新增任意 scheduler 或后台 worker。
- 策略输出不返回原始消息、玩家名、profile、`/w`、token、音频 URL、录音路径或平台凭据。

## 已落地能力

| 类别 | 决策 | 说明 |
| --- | --- | --- |
| `text_companion` | `allow_text_only` | 文本陪伴留在普通聊天路径。 |
| `voice_companion` / `live2d_companion` / `background_listening` | `blocked_unavailable_runtime` | 语音、Live2D、录音、后台监听默认不可用。 |
| `background_task_companion` | `requires_existing_confirmation_flow` | 只能复用既有确认式提醒和任务。 |
| `trade_action` | `blocked_sensitive_action` | 私聊、下单、交易动作不放行。 |
| `gameplay_companion` | `route_general_chat` | 游戏内同伴/宠物按普通游戏建议处理。 |

## 验证结果

- 单元红测：`tests/test_companion_experience.py` 初次运行按预期失败于 `ModuleNotFoundError: No module named 'warframe_agent.companion_experience'`。
- Unit green：`tests/test_companion_experience.py` 为 `6 passed`。
- Runtime policy 红测：`tests/test_tool_registry.py -k "runtime_safety_policy_embeds_tool_registry_summary_without_tool_details"` 初次运行按预期失败于缺少 `companion_experience_policy`。
- Runtime policy green：同一目标测试实现后为 `1 passed, 33 deselected`。
- Web API 目标测试：普通沙箱仍受既有 SQLite WAL 权限限制，导入 `warframe_agent.web.app` 时失败于 `sqlite3.OperationalError: unable to open database file`；本次提权重跑因本地 Codex 登录 token 失效未能执行，需要在可写运行环境中补跑。

## 路线状态

Step 39 覆盖了剩余学习队列中的“语音和陪伴式体验评估”。它没有把语音/Live2D 做成真实产品功能，而是先把高权限体验层的安全边界固化到 runtime safety policy，避免后续上下文压缩后误把 EchoBot / OpenHuman / OpenClaw 的语音能力直接迁移成默认可用能力。

后续如果继续学习借鉴，主线队列已基本覆盖；更合理的下一步是回到 Step 35 分支，设计“软拦截 -> 用户确认 -> 受控执行”的确认链路，或者做一次总账本复盘，决定是否开启新的学习批次。
