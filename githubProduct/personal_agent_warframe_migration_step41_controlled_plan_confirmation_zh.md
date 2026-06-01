# Step 41：AgentPlan 受控执行确认链路

## 任务定位

- 来源项目：LangManus / OpenManus / Suna。
- 借鉴点：planner 先生成多步骤计划，reviewer 在执行前给出阻断原因，用户确认只能解除低风险缺口。
- Warframe 映射：在 `ToolRouter.react_loop(...)` 中把 Step 35 的 blocked plan 软拦截扩展为“可确认的只读计划 -> 确认码 -> 重新 review -> 受控执行”。
- 安全边界：本步只允许 `missing_verification` 被用户确认执行；`unknown_tool`、`non_exposed_tool`、`side_effect_tool`、`sensitive_arguments` 继续硬拦。

## 已实现能力

- 新增 `PlanConfirmationRequest`，用于结构化表达计划是否需要确认、是否可确认、阻断原因和确认码。
- 新增 `build_plan_confirmation_request(...)`：
  - 已通过 review 的计划返回 `not_required`。
  - 只有全部 issue 都是 `missing_verification`，并且 `require_verification=False` 重新 review 后为 `ok`，才返回 `requires_confirmation`。
  - 敏感参数、副作用工具、未知工具、未暴露工具都返回 `not_confirmable` 且不生成确认码。
- `react_loop(...)` 新增可选参数 `plan_confirmation_token`：
  - 无确认码或确认码错误时继续 `plan_blocked`，不调用 `tool_executor`。
  - 正确确认码匹配当前 plan 指纹时，重新以 relaxed review 校验，校验通过才执行。
  - 确认执行后在 `trace.plan.verification_note` 中记录 `plan_review=confirmed`。
- 确认码绑定 plan 的 `goal`、每一步 `tool`、`arguments`、`purpose` 和原始阻断原因；plan 内容变化后旧确认码失效。

## 不做范围

- 不新增 Web UI 确认按钮。
- 不持久化 pending plan。
- 不新增 Browser / GUI / shell / scheduler executor。
- 不让 `set_alert`、私信、下单、登录、支付、删除、凭据输入等副作用动作通过确认码执行。
- 不保存 raw sensitive arguments。
- 不修改云端模型调用链路；三个云端 AI 仍必须通过 `ModelOrchestrator` / `llm.py`。

## 验证结果

本步先按 TDD 写红测，初次运行因缺少 `build_plan_confirmation_request` 按预期失败：

```powershell
ImportError: cannot import name 'build_plan_confirmation_request'
```

实现后目标测试通过：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_plan.py -k "plan_confirmation or confirmed_missing_verification" -q --basetemp .pytest-tmp -p no:cacheprovider
```

结果：

```txt
6 passed, 17 deselected
```

覆盖点：

- 只读 `missing_verification` plan 可生成确认请求。
- 副作用计划和敏感参数计划不可确认。
- 未知工具和未暴露工具不可确认。
- 正确确认码可执行只读 missing-verification plan。
- 错误确认码不执行。
- plan 内容变化后旧确认码不执行。

## 后续建议

- 下一步若要面向真实用户完成闭环，应单独设计 ChatAgent / Web API 的 pending confirmation 状态，避免直接持久化 raw plan。
- UI 层确认按钮必须只消费底层 `PlanConfirmationRequest` 的安全字段，不展示 raw arguments。
- 高风险 blocked reason 不应进入“用户确认即可执行”路径；若未来要支持副作用工具，必须单独做权限、可撤销、可中断和审计设计。
