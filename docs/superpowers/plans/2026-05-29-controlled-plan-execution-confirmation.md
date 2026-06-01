# Step 41: 受控执行确认链路计划

## 背景

- Step 35 已实现 `AgentPlan` 的只读 Reviewer / Verifier：未知工具、未暴露工具、副作用工具、敏感参数、缺少验证说明都会在执行前被软拦截。
- 当前缺口是：所有 blocked plan 都只能停止，无法进入“软拦截 -> 用户确认 -> 受控执行”的下一阶段。
- 本次不放开高风险计划，只实现第一阶段最小确认链路。

## 关键假设

- 第一阶段只允许 `missing_verification` 作为可确认阻断原因。
- `unknown_tool`、`non_exposed_tool`、`side_effect_tool`、`sensitive_arguments` 继续硬拦，不能通过确认码执行。
- 确认码只绑定当前 plan 的安全指纹和阻断原因；plan 内容变化后确认码失效。
- 本次优先落在 `tool_router` 单元层，不新增 Web 按钮、后台 worker 或外部自动执行入口。

## 完成标准

| 项目 | 预期结果 | 验证方法 |
| --- | --- | --- |
| 可确认请求 | 缺少 `purpose` 的只读 plan 返回可确认状态和确认码 | `tests/test_plan.py` 新增单测 |
| 硬拦边界 | 敏感参数、副作用工具、未知/未暴露工具不生成可执行确认 | `tests/test_plan.py` 新增单测 |
| 确认执行 | `react_loop(..., plan_confirmation_token=正确确认码)` 执行只读 plan | `tests/test_plan.py` 新增集成测试 |
| 错误确认码 | 错误确认码不执行任何子工具，仍返回 blocked | `tests/test_plan.py` 新增集成测试 |
| Trace 记录 | 确认执行后 `trace.plan.verification_note` 标记 confirmed | 断言 trace 字段 |
| 文档同步 | Step 41 学习文档、路线账本、`md/rebuilt`、`AGENTS.md` 更新 | 文件 diff 检查 |

## 执行步骤

1. 保存本计划。
   - 预期结果：`docs/superpowers/plans/2026-05-29-controlled-plan-execution-confirmation.md` 存在。
   - 验证方法：文件可读，包含完成标准和测试命令。

2. 写红测。
   - 预期结果：新增测试导入尚未实现的确认请求 helper，先失败。
   - 验证方法：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plan.py -k "plan_confirmation or confirmed_missing_verification" -q --basetemp .pytest-tmp -p no:cacheprovider
```

3. 实现确认请求 helper。
   - 预期结果：
     - `build_plan_confirmation_request(plan, review=None, registry=None)` 返回结构化结果。
     - 只有 relaxed review 通过且原始阻断原因为 `missing_verification` 时生成确认码。
     - 确认码不暴露 raw args。
   - 验证方法：确认请求单测通过。

4. 接入 `react_loop`。
   - 预期结果：
     - 新增可选参数 `plan_confirmation_token`。
     - blocked plan 先生成确认请求；无确认码时仍返回 blocked 提示。
     - 正确确认码使只读 missing-verification plan 以 relaxed review 执行。
     - 错误确认码、敏感参数、副作用工具继续不执行。
   - 验证方法：确认执行与错误确认码集成测试通过。

5. 同步学习文档。
   - 预期结果：
     - 新增 `githubProduct/personal_agent_warframe_migration_step41_controlled_plan_confirmation_zh.md`。
     - 更新 `githubProduct/personal_agent_learning_route_ledger_zh.md`。
     - 更新 `md/rebuilt/09-personal-agent-foundation.md`、`md/rebuilt/10-learning-route-audit.md`，必要时补充 `md/rebuilt/06-tools-models-safety.md`。
     - 更新 `AGENTS.md` 当前进度与下一步计划。

6. 目标验证。
   - 预期结果：目标测试、AST、diff 空白检查通过。
   - 验证方法：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plan.py tests\test_tool_router.py -k "plan_review or agent_plan or plan_confirmation or confirmed_missing_verification" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
git diff --check -- warframe_agent/tool_router.py tests/test_plan.py docs/superpowers/plans/2026-05-29-controlled-plan-execution-confirmation.md githubProduct/personal_agent_warframe_migration_step41_controlled_plan_confirmation_zh.md githubProduct/personal_agent_learning_route_ledger_zh.md md/rebuilt/09-personal-agent-foundation.md md/rebuilt/10-learning-route-audit.md md/rebuilt/06-tools-models-safety.md AGENTS.md
```

## 不做范围

- 不新增 Browser / GUI / Playwright 自动执行入口。
- 不新增 Web UI 确认按钮。
- 不让 `set_alert`、私信、下单、登录、凭据输入、删除、支付等副作用动作通过确认码执行。
- 不保存 raw sensitive arguments。
- 不修改模型编排或云端模型调用链路。
