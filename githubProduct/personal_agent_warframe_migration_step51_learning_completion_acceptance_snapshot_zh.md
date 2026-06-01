# Step 51：学习借鉴完成验收清单快照

## 任务定位

- 路线归属：Step 51 是“完成态验收防漂移”改善，不是旧学习队列补课，也不是高权限能力启用。
- 完成结论：Step 50 仍是最新闭环步骤；Step 51 只把“为什么算完成”整理成机器可读的只读 acceptance snapshot。
- 本步目标：在 `/api/runtime/status.learning_completion` 和 Runtime 面板中展示 `acceptance_status=accepted`、Step 50 闭环锚点、Step 51 验收记录锚点和安全验收 checklist，降低后续上下文压缩后误判路线未完成的概率。

## 已实现能力

- `warframe_agent/learning_completion.py` 新增：
  - `acceptance_status=accepted`
  - `acceptance_snapshot.latest_closure_step=step50_learning_completion_runtime_snapshot`
  - `acceptance_snapshot.acceptance_record_step=step51_learning_completion_acceptance_snapshot`
  - `acceptance_snapshot.all_items_passed=true`
  - 安全聚合验收 checklist。
- `completed_steps` 已补入 `step50_learning_completion_runtime_snapshot`，避免未来只看到 Step49 而误解 Step50 未落锚。
- Runtime 面板的 `Learning Completion` 区域展示 acceptance 状态、closure step、acceptance record 和 checklist 条目。
- Web API / Runtime UI / 单元测试均已补充验收字段断言。

## 验收清单含义

- 旧非语音学习借鉴路线完成。
- Step 48 / Step 49 改善完成。
- `/api/runtime/status` 已暴露完成快照。
- Runtime 面板已展示完成快照。
- 高权限运行时能力未启用。
- 真实语音运行时继续冻结。
- 未来 Browser/GUI executor、服务恢复、任意触发器、插件安装和 connector 启用仍需另开新阶段。
- Step 50 闭环快照已存在。

## 安全边界

- 本步只扩展只读完成验收快照，不新增端点、按钮、开关、ToolRegistry 工具、executor、后台 worker 或自动触发器。
- 不启用 Browser/GUI executor、shell、通用文件写入、service recovery、任意触发器、plugin install、connector enable、webhook、DM 命令入口或真实语音能力。
- `future_capability_admission.enabled=False` 保持不变。
- 真实语音、TTS/STT、麦克风、录音、Live2D 和后台监听继续按用户当前指令冻结。
- 快照和文档不记录 token、secret、password、api_key、authorization、cookie、account_id、raw_payload、raw_manifest、raw_arguments、raw_plan、handler、params、profile、`/w`、本机私密路径、私网地址或玩家私信信息。
- 所有云端模型调用边界不变：不得在新快照、展示层或 helper 中读取 `.env`、拼 API header 或绕过 `ModelOrchestrator` / `llm.py`。

## 验证摘要

红测：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step51-red -p no:cacheprovider
```

结果：按预期失败于 `KeyError: 'acceptance_status'` 和 `KeyError: 'acceptance_snapshot'`。

绿测与补跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py -q --basetemp .pytest-tmp-step51-learning -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step51-static -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py -k "runtime_status_endpoint or runtime_status_includes_read_only_safety_policy" -q --basetemp .pytest-tmp-step51-api-writable -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_renders_jobs_tasks_and_safe_state -q --basetemp .pytest-tmp-step51-playwright-writable -p no:cacheprovider
```

结果：learning completion unit `5 passed`；JS 语法检查退出码 0；Runtime 静态契约 `1 passed`；Web API 可写环境补跑 `2 passed, 70 deselected`；完整 Runtime 面板 Playwright 可写环境补跑 `1 passed`。普通沙箱中 Web API 仍失败于 SQLite WAL 数据库文件无法打开，Playwright 仍失败于 uvicorn 未就绪。

最终复核：policy / gateway / plugin / runtime safety 联跑 `25 passed, 33 deselected`；Runtime 静态契约复核 `1 passed`；`warframe_agent/learning_completion.py`、`warframe_agent/future_capability_policy.py`、`warframe_agent/safety_policy.py`、`warframe_agent/web/app.py` AST OK；`node --check warframe_agent\web\static\js\app.js` 退出码 0；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

## 后续路线

- 到 Step 51 为止，“GitHub 个人 Agent 非语音学习借鉴计划完成 + Step 48/49 改善完成 + Step 50 完成态快照验收”已经形成代码、API、Runtime UI、测试和文档闭环。
- 后续不再机械执行旧学习队列；真实高权限能力必须另开权限、确认、可中断执行、审计和回滚设计。
