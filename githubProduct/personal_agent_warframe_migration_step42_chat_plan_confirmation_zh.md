# Step 42：ChatAgent 计划确认闭环

## 任务定位

- 来源项目：LangManus / OpenManus / Suna。
- 借鉴点：planner 生成计划后，reviewer 先阻断风险，再由用户确认低风险缺口。
- Warframe 映射：把 Step 41 的 `ToolRouter` 确认码接入 `ChatAgent`，让用户可以直接回复“确认执行”。
- 用户最新约束：暂时不考虑语音对话服务和真实语音，本步不涉及 TTS/STT、麦克风、录音、Live2D 或常驻陪伴。

## 已实现能力

- 新增 `PendingAgentPlanConfirmation`：
  - 只保存原始用户消息、候选工具名、阻断原因和确认码。
  - 不保存 raw plan，不保存 raw tool args。
- `ChatAgent.answer(...)` 和 `answer_stream(...)` 现在会优先处理计划确认回复：
  - “确认执行”会重新调用原始消息，并把确认码传给 `react_loop(...)`。
  - “取消执行”会清空待确认计划。
  - 普通“确认”不会触发计划执行，避免和目标/复盘/裂缝确认混淆。
- `_try_react_loop(...)` 会捕获 Step 41 返回的 `confirmation_required=true`，仅当 `confirmable_reason=missing_verification` 时保存 pending 状态。
- 用户看到的是自然语言提示，不需要复制 `plan_confirm_...` 确认码。

## 安全边界

- 只有 `missing_verification` 的只读计划能进入待确认状态。
- `side_effect_tool`、`sensitive_arguments`、`unknown_tool`、`non_exposed_tool` 不会进入 pending confirmation。
- 确认执行时仍由 `ToolRouter` 重新进行 plan 指纹匹配和 relaxed review；ChatAgent 不直接执行计划。
- 不新增 Web UI、Browser/GUI/shell/scheduler executor。
- 不新增语音、真实语音、麦克风、录音、TTS/STT 或 Live2D。

## 验证结果

红测先失败于 ChatAgent 只返回底层确认码且没有待确认状态：

```txt
4 failed
```

实现后目标测试通过：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py -k "agent_plan_confirmation" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：

```txt
5 passed, 69 deselected
```

补充联跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py tests\test_plan.py -k "agent_plan_confirmation or plan_confirmation or confirmed_missing_verification" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent\chat.py tests\test_chat.py docs\superpowers\plans\2026-05-30-agent-plan-chat-confirmation.md githubProduct\personal_agent_warframe_migration_step42_chat_plan_confirmation_zh.md githubProduct\personal_agent_learning_route_ledger_zh.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md md\rebuilt\06-tools-models-safety.md AGENTS.md
```

结果：`11 passed, 86 deselected`；AST OK；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

覆盖点：

- 初次 blocked plan 会提示“确认执行 / 取消执行”。
- 提示不会展示 `plan_confirm_`。
- 回复“确认执行”会执行同一只读计划。
- 回复“取消执行”会清空 pending。
- 副作用计划不会进入待确认状态。
- `answer_stream(...)` 与普通 `answer(...)` 走同一确认逻辑。

## 后续建议

- 非语音学习借鉴计划的下一优先级可进入“多渠道 Gateway 边界评估”或“skills / plugin 生态边界评估”。
- Browser / GUI 自动化仍只建议先做权限与审计设计，不应直接开放真实 executor。
- Step 39 语音相关 Web API 验证债务可继续记录，但按用户最新指令暂不作为当前优先任务。
