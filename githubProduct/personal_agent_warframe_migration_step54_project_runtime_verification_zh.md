# Step 54：项目整体验收运行与实现真实性复核

## 任务定位

- 本步响应“运行项目看看整体有没有出错的地方以及所做的各种实现有没有真正的实现”。
- 本步只做运行、验证和记录，不新增业务功能，不修复失败用例，不启用任何高权限运行时能力。
- 子代理分别复核后端/API/策略层和前端/Runtime 展示层，主线程负责运行全量测试、服务烟测和最终判定。

## 完成标准

| 检查项 | 完成标准 | 结果 |
| --- | --- | --- |
| 学习借鉴实现真实性 | 能在代码、API、Runtime UI 和测试中找到真实实现 | 通过 |
| 项目启动烟测 | 临时 uvicorn 服务可返回 `/api/runtime/status` | 通过 |
| 重点策略测试 | learning / future capability / gateway / plugin / runtime policy 目标测试通过 | 通过 |
| 前端静态契约 | Runtime 面板静态契约和 JS 语法通过 | 通过 |
| 全量测试 | `pytest tests` 全绿 | 未通过，存在 8 个失败 |

## 运行结果

### 全量 pytest

普通沙箱运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp-step54-full -p no:cacheprovider
```

结果：收集阶段因既有 SQLite WAL / 数据库文件权限限制失败，错误为 `sqlite3.OperationalError: unable to open database file`。

可写运行环境补跑：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp-step54-full-writable -p no:cacheprovider
```

结果：`8 failed, 1162 passed, 7 warnings in 342.87s`。

失败用例归类：

| 类别 | 失败用例 | 初步判断 |
| --- | --- | --- |
| 聊天查价直答与旧 prompt 断言冲突 | `test_chat_alias_priority.py::test_manual_alias_key_overrides_generated_duplicate_key`、`test_chat_memory_integration.py::test_generated_alias_substring_is_detected`、`test_chat_memory_integration.py::test_memory_alert_is_added_to_prompt`、`test_chat_rag_fallback.py::test_chat_uses_rag_result_when_alias_lookup_fails`、`test_short_name_regression.py::test_short_chinese_name_inside_sentence_is_resolved` | 当前 `ChatAgent.answer(...)` 对部分市场查价输入直接返回确定性市场摘要，未再进入测试期望的 `model_call` prompt 路径；需要单独判断是更新测试还是恢复 prompt 链路。 |
| ToolRouter 安全策略与旧期望冲突 | `test_router.py::ReactLoopTests::test_plan_aggregation_redacts_and_budgets_context` | 当前计划 review 会因 `sensitive_arguments` 阻断含敏感上下文的计划，符合 Step 35 之后的安全策略；旧测试仍期望最终回答。 |
| WebSocket 错误处理回归 | `test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message` | 测试期望显示 `WS backend exploded`，实际显示模拟查价回复；需要单独排查前端错误路径或测试 mock。 |
| 前端 XSS 文本泄漏 | `test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe` | DOM 中没有真实 `img[data-xss]` 节点，但 `innerHTML` 仍残留转义后的 `data-xss` 文本；这更像真实安全/渲染收口缺口，应优先修复。 |

## 重点学习实现验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_learning_completion.py tests\test_future_capability_policy.py tests\test_gateway_policy.py tests\test_plugin_policy.py tests\test_tool_registry.py -k "learning_completion or future_capability or gateway_policy or plugin_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp-step54-policy -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_runtime_panel_static_contracts_include_gateway_and_plugin_policy_sections -q --basetemp .pytest-tmp-step54-static -p no:cacheprovider
node --check warframe_agent\web\static\js\app.js
```

结果：

- policy / gateway / plugin / future capability / learning completion 目标联跑：`25 passed, 33 deselected`。
- Runtime 面板静态契约：`1 passed`。
- `node --check warframe_agent\web\static\js\app.js`：退出码 0。

## 语法与启动烟测

严格 `utf-8` AST 扫描暴露出历史文件 BOM 问题：`SyntaxError: invalid non-printable character U+FEFF`。使用 `utf-8-sig` 读取后，`warframe_agent` 与 `tools` 下 Python 文件 AST 扫描通过：

```powershell
.\.venv\Scripts\python.exe -B -c "import ast,pathlib; files=[str(path) for path in pathlib.Path('warframe_agent').rglob('*.py')] + [str(path) for path in pathlib.Path('tools').rglob('*.py')]; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK', len(files), 'files')"
```

结果：`AST OK 82 files`。

`compileall` 在普通环境中因写入 `tools\__pycache__` 权限不足失败，属于当前运行环境写权限限制，不能作为语法失败证据。

临时启动 uvicorn 并请求 Runtime 状态：

```powershell
.\.venv\Scripts\python.exe -m uvicorn warframe_agent.web.app:app --host 127.0.0.1 --port 8765
```

结果：

```txt
HTTP=200
learning_status=complete
acceptance_status=accepted
future_enabled=False
```

服务已在验证后停止，端口 `8765` 未留下监听进程。

## 子代理复核

| 子代理 | 分工 | 结论 |
| --- | --- | --- |
| 后端/API/策略复核 | 检查 `learning_completion`、`safety_policy`、`/api/runtime/status` 与目标测试 | 实现真实存在，目标测试 `25 passed, 33 deselected`；普通沙箱 Web API 仍受 SQLite WAL 限制。 |
| 前端/Runtime 复核 | 检查 `app.js` 是否真实读取并渲染 runtime policy / learning completion | 实现真实存在，JS 语法和 Runtime 静态契约通过；完整 Playwright 在普通沙箱仍会遇到 uvicorn 未就绪限制。 |

主线程复核后，子代理结论与主线程证据一致。

## 最终结论

- 学习借鉴相关实现不是“只写了计划”：`learning_completion`、`future_capability_policy`、`gateway_policy`、`plugin_policy`、`safety_policy`、`/api/runtime/status` 和 Runtime 面板展示均有真实代码与测试覆盖。
- 当前完成锚点在服务烟测中可见：`learning_completion.status=complete`、`acceptance_status=accepted`、`future_capability_admission.enabled=False`。
- 项目整体尚不能宣称全量绿色：全量 pytest 在可写运行环境下仍有 8 个失败。
- 后续修复优先级建议：先修前端 XSS 文本泄漏和 WebSocket 错误路径，再处理聊天查价直答与旧 prompt 测试之间的契约取舍，最后复核 ToolRouter 安全策略相关旧断言。

## 安全边界

- 本步没有安装依赖、下载文件或上传 GitHub。
- 本步没有启用 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。
- 本步没有修改运行时代码，只追加验收计划、报告和 rebuilt / AGENTS 状态记录。
