# Step 55：全量测试失败修复记录

## 任务定位

- 本步响应 Step 54 找出的 8 个全量测试失败。
- 本步目标是先修复已复现的根因，并尽可能跑定向验证；不新增学习借鉴功能，不启用高权限运行时能力。
- 当前结果不是“全量已绿”：6 个非 UI 失败已修复并验证，2 个前端 Playwright 失败已打补丁但受当前可写运行环境/额度限制，尚未完成浏览器绿测。

## 根因与修复

| 失败类别 | 根因 | 修复 |
| --- | --- | --- |
| 聊天别名 / RAG / 记忆 prompt 5 个失败 | `ChatAgent.answer(...)` 在 `market_analysis` 模式下直接返回确定性 `fallback_answer(...)`，导致注入 `model_call` 的测试无法观察 prompt，记忆提醒也不会注入 prompt。 | `warframe_agent/chat.py` 保留默认 `call_ollama_chat` 的确定性市场直答；注入 `model_call` 的纯市场问题回到 prompt 路径。混入攻略/视频词的价格问题继续走确定性价格模式，避免误触发 B 站推荐。 |
| Router plan 聚合 1 个失败 | 测试 payload 包含 `token`、`__message`、`message_context`，但 Step 35+ 安全策略会在计划执行前以 `sensitive_arguments` 阻断。 | 更新 `tests/test_router.py` 的该测试，只使用安全 plan args，保留长工具结果里的 `token=secret-token` 来验证结果脱敏和预算压缩。生产安全策略不放宽。 |
| WebSocket 错误路径 1 个失败 | 测试 MockWebSocket 使用数字 `readyState`，没有提供 `WebSocket.OPEN/CONNECTING/CLOSED` 静态常量；现有代码因此无法识别 mock 已打开，并过早走 REST fallback。 | `warframe_agent/web/static/js/chat.js` 新增 WebSocket 状态兼容 helper，并在发送前等待短时间让 connecting socket 打开。 |
| XSS 文本泄漏 1 个失败 | `DOMPurify` 阻止真实 `img` 节点，但 Markdown 会把原始 `<img ... data-xss=...>` 作为转义文本保留下来，`innerHTML` 仍含 `data-xss` 字符串。 | `chat.js` 在 Markdown 渲染前剥离 `script/style/iframe/object/embed/img` 这类 unsafe inline HTML 片段，并禁止 `data-xss` 属性。 |

## 已验证结果

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_alias_priority.py::ChatAliasPriorityTests::test_manual_alias_key_overrides_generated_duplicate_key tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_generated_alias_substring_is_detected tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_memory_alert_is_added_to_prompt tests\test_chat_rag_fallback.py::ChatRagFallbackTests::test_chat_uses_rag_result_when_alias_lookup_fails tests\test_short_name_regression.py::ShortNameRegressionTests::test_short_chinese_name_inside_sentence_is_resolved -q --basetemp .pytest-tmp-step55-chat-targeted-2 -p no:cacheprovider
```

结果：`5 passed`。

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py tests\test_chat_alias_priority.py tests\test_chat_memory_integration.py tests\test_chat_rag_fallback.py tests\test_short_name_regression.py -q --basetemp .pytest-tmp-step55-chat-broad-2 -p no:cacheprovider
```

结果：`79 passed`。

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_router.py::ReactLoopTests::test_plan_aggregation_redacts_and_budgets_context tests\test_plan.py tests\test_tool_context.py -q --basetemp .pytest-tmp-step55-router-broad-2 -p no:cacheprovider
```

结果：`37 passed`。

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_alias_priority.py::ChatAliasPriorityTests::test_manual_alias_key_overrides_generated_duplicate_key tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_generated_alias_substring_is_detected tests\test_chat_memory_integration.py::ChatMemoryIntegrationTests::test_memory_alert_is_added_to_prompt tests\test_chat_rag_fallback.py::ChatRagFallbackTests::test_chat_uses_rag_result_when_alias_lookup_fails tests\test_short_name_regression.py::ShortNameRegressionTests::test_short_chinese_name_inside_sentence_is_resolved tests\test_router.py::ReactLoopTests::test_plan_aggregation_redacts_and_budgets_context -q --basetemp .pytest-tmp-step55-targeted-non-ui -p no:cacheprovider
```

结果：`6 passed`。

补充语法检查：

```powershell
node --check warframe_agent\web\static\js\chat.js
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/tool_router.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
```

结果：`node --check` 退出码 0；AST 检查输出 `AST OK`。

## 尚未完成的验证

普通沙箱运行两个前端 Playwright 目标测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message tests\test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe -q --basetemp .pytest-tmp-step55-ui -p no:cacheprovider
```

结果：两个用例均在 setup 阶段失败于 `RuntimeError: Web server did not become ready`，没有进入断言。

可写环境复跑请求被本地 quota / approval 层拒绝，因此本步不能声称这两个 Playwright 用例已经绿，也不能声称全量 `pytest tests` 已绿。

## 当前结论

- 8 个失败中，6 个非 UI 失败已经完成代码或测试契约修复，并通过定向与扩展回归验证。
- 2 个 UI 失败的生产补丁已实现，但需要后续在可写 Playwright 环境补跑确认。
- 学习借鉴路线仍保持 Step 51 完成验收状态；Step 55 是项目质量修复，不是重启旧学习队列。

## 安全边界

- 未安装依赖，未下载文件，未上传 GitHub。
- 未启用 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。
- 未放宽 ToolRouter 对敏感 plan 参数的拦截策略。
