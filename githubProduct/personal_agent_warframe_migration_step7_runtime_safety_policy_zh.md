# Personal Agent 学习迁移 Step 7: 运行态安全策略快照

日期: 2026-05-26

## 借鉴点

个人 Agent 项目里值得优先迁移的不是“更多权限”，而是“默认只读、能力边界可见”。本步借鉴 CowAgent / OpenClaw / EchoBot 一类常驻个人助手的安全默认策略，把当前 Warframe Agent 的外部能力边界做成 `/api/runtime/status` 的只读快照。

## 已落地内容

- 新增 `warframe_agent/safety_policy.py`，集中构建 `safety_policy`。
- `/api/runtime/status` 新增 `safety_policy` 字段。
- Web 运行态详情面板新增 Safety Policy 摘要和“安全策略”能力列表。
- 当前快照明确标出：
  - shell、通用文件写入、浏览器私网、任意调度器默认不可用。
  - warframe.market / 游戏数据网络读取是 `read_only`。
  - 项目数据写入是受控 `restricted`，只用于配置、记忆、提醒等已有 API。
  - scheduler jobs 和外部推送只返回启用状态，不返回凭据。

## 安全边界

- 本步没有新增 shell、文件、浏览器、MCP、scheduler 创建或外部推送执行能力。
- `safety_policy` 只返回布尔值、模式和固定 scope，不返回 `app_token`、UID、`app_secret`、chat_id、access token、callback body、原始消息或工具原始结果。
- 前端只展示快照，不提供开关。

## 本轮验证

- 已红绿验证: `pytest tests/test_web_api.py -k "runtime_status_includes_read_only_safety_policy" -q`
- 已通过: `pytest tests/test_web_api.py -k "runtime_status" -q`，结果 `5 passed, 64 deselected`
- 已通过: `node --check warframe_agent/web/static/js/app.js`
- 已通过: Python AST 只读解析 `warframe_agent/safety_policy.py`、`warframe_agent/web/app.py`、`warframe_agent/web/static/js/app.js`、`tests/test_web_api.py`
- 说明: 普通沙箱运行 Web API pytest 时仍会在导入 Web app 阶段触发 SQLite WAL 的 `sqlite3.OperationalError: unable to open database file`；Web API 目标测试在沙箱外可写环境中运行通过。

## 下一步建议

1. 再做一层 ToolRegistry 安全统计：工具总数、`safety_level` 分布、`side_effect` 数量和 `context_policy` 分布。
2. 做安全开关页面前，先定义“只读观察”和“允许执行”的状态机，不要直接把开关接到真实动作。
3. 继续推进机会复盘闭环，让用户结果反馈反向影响个人评分。
