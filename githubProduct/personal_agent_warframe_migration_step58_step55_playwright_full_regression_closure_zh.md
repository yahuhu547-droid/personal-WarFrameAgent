# Step 58：Step55 Playwright 与全量回归收尾

## 任务定位

Step 58 是项目质量修复收尾，不是旧个人 Agent 学习借鉴队列重启，也不是高权限能力启用。

本步目标是关闭 Step 55 遗留验证债务：

- 两个前端 Playwright 目标测试必须有新鲜结果。
- 完整 `pytest tests` 必须有新鲜结果。
- 如果失败，必须记录明确根因；如果通过，才能把 Step55 的 Playwright / 全量回归债务标记为关闭。

## 根因复核

普通沙箱中两个目标 Playwright 用例仍在 setup 阶段失败：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message tests\test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe -q --basetemp .pytest-tmp-step58-ui-targets -p no:cacheprovider
```

结果：`2 errors`，均为 `RuntimeError: Web server did not become ready`。

直接启动 uvicorn 暴露了真实原因：

```powershell
.\.venv\Scripts\python.exe -m uvicorn warframe_agent.web.app:app --host 127.0.0.1 --port 8000 --log-level info
```

结果：导入 `warframe_agent.web.app` 时初始化 `TradeHistoryDB()`，执行 `PRAGMA journal_mode=WAL` 报 `sqlite3.OperationalError: unable to open database file`。因此普通沙箱失败是 SQLite WAL / 数据目录写入限制，不是浏览器断言失败。

可写运行环境中目标测试进入真实浏览器断言，初次结果为 `1 passed, 1 failed`。失败点是聊天消息 DOM 的 `data-raw` 属性仍保存原始回复，导致转义后的 `data-xss` 属性名残留在 `node.innerHTML` 中。可见内容和执行型 XSS 已被净化，但 DOM 属性存储仍不满足测试契约。

## 已修复内容

修改文件：`warframe_agent/web/static/js/chat.js`

最小修复：

- 新增 `safeChatRawText(...)`，复用 `stripUnsafeInlineHtml(...)` 作为 agent 消息的安全原文存储层。
- `renderMarkdown(...)` 继续先剥离危险 inline HTML，再交给 `marked` / `DOMPurify`。
- agent 消息的 `data-raw`、WebSocket token 累积、done reply、direct reply 和 REST fallback reply 都改为保存安全文本。
- 保留 whisper 命令识别、复制按钮和聊天历史持久化行为。

未修改范围：

- 未修改 `tests/test_web_ui_playwright.py`。
- 未修改 `chart.js`，compare / chart XSS 断言在 chat 修复后已通过。
- 未修改 Step57 活动 / Baro 逻辑、ChatAgent 后端业务逻辑、ToolRouter 或 safety policy。

## 验证摘要

JavaScript 语法检查：

```powershell
node --check warframe_agent\web\static\js\chat.js
node --check warframe_agent\web\static\js\chart.js
```

结果：两个命令退出码均为 0。

两个 Step55 Playwright 目标测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_ui_playwright.py::test_chat_websocket_error_stops_loading_and_renders_message tests\test_web_ui_playwright.py::test_chat_response_whisper_compare_and_chart_are_xss_safe -q --basetemp .pytest-tmp-step58-ui-targets-final -p no:cacheprovider
```

结果：`2 passed in 28.70s`。

完整全量回归：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp-step58-full-final -p no:cacheprovider
```

结果：`1182 passed, 7 warnings in 331.32s`。

AST 和 diff 检查：

```powershell
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/chat.py','warframe_agent/baro.py','warframe_agent/events.py','warframe_agent/web/app.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8-sig')) for path in files]; print('AST OK')"
git diff --check -- AGENTS.md md\rebuilt\09-personal-agent-foundation.md md\rebuilt\10-learning-route-audit.md githubProduct\personal_agent_warframe_migration_step58_step55_playwright_full_regression_closure_zh.md docs\superpowers\plans\2026-06-01-step55-playwright-full-regression-closure.md tests\test_web_ui_playwright.py warframe_agent\web\static\js\chat.js warframe_agent\web\static\js\chart.js
```

结果：`AST OK`；`git diff --check` 退出码 0，仅有 LF/CRLF 提示。

## 结论

Step55 剩余的两个前端 Playwright 目标测试已经通过，完整 `pytest tests` 也已通过。Step55 遗留的 Playwright / 全量回归验证债务关闭。

普通沙箱仍可能因 SQLite WAL / 数据目录写入限制无法启动 uvicorn；该限制已被记录为环境约束，不影响本次可写运行环境验证结论。

## 安全边界

- 未安装依赖。
- 未下载文件到 C 盘。
- 未上传 GitHub。
- 未新增或启用 Browser/GUI executor、shell executor、service recovery、任意触发器平台、plugin install、connector enable、webhook / DM 命令入口或真实语音能力。
- 未放宽 XSS 断言；`img[data-xss]`、`data-xss`、事件属性和 raw HTML 不允许回到聊天消息 DOM。
