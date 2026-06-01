# Step 36：长期运行与运维健康摘要

日期：2026-05-28

## 来源项目

- CowAgent：多入口服务状态与任务运行可见性。
- Suna / Kortix：长期 workspace、后台任务与服务健康面板。
- OpenClaw：channels / gateway / extensions 的运行状态聚合思路。

## 借鉴点

- 把分散的 scheduler、后台任务、推送通道和日报状态收敛成一个只读 health summary。
- 使用短 reason code 表示退化原因，避免把错误详情、任务结果或外部凭据塞进运维面板。
- 运维面板先做“看见问题”，不直接提供 start / stop / retry / repair 控制。

## Warframe 映射

- 后端在 `/api/runtime/status` 新增 `ops_health`。
- `ops_health.components` 只包含聚合计数和布尔状态：
  - `scheduler`
  - `background_tasks`
  - `feishu`
  - `wxpusher`
  - `daily_report`
- 前端 Runtime 面板新增 `Ops Health` 摘要卡和只读详情区。

## 安全边界

- 不新增 scheduler 控制端点。
- 不新增重试、启动、停止按钮。
- 不调用 shell、Browser / GUI 自动化或云端模型。
- 不返回 Push token、UID、Feishu app_secret、chat_id、raw task result、job error detail、profile URL、`/w` 或 token。
- `ops_health` 不暴露单个 job id、task id 或错误摘要，只返回 reason code 和聚合计数。

## 已实现内容

- `warframe_agent/web/app.py`
  - 新增 `_ops_health_snapshot(...)`。
  - `/api/runtime/status` 返回 `ops_health`，并用该摘要的状态作为顶层 runtime 状态。
- `warframe_agent/web/static/js/app.js`
  - Runtime 面板显示 `Ops Health` 摘要卡。
  - 新增 `renderRuntimeOpsHealth(...)` 与 `renderRuntimeOpsComponent(...)`。
- `tests/test_web_api.py`
  - 新增 `test_runtime_status_includes_safe_ops_health_summary`。
- `tests/test_web_ui_playwright.py`
  - Runtime mock payload 新增 `ops_health`。
  - 面板测试断言 reason code 与安全渲染。

## 验证记录

- API 红测：`ops_health` 缺失时失败于 `KeyError: 'ops_health'`。
- UI 红测：Runtime 面板缺少 `Ops Health` 时失败。
- API green：`tests/test_web_api.py -k "ops_health or runtime_status_endpoint"` 为 `2 passed, 69 deselected`。
- Runtime Playwright green：`test_runtime_panel_renders_jobs_tasks_and_safe_state` 为 `1 passed`。
- Sidebar static contract：`test_sidebar_static_contracts_match_warframe_player_context` 为 `1 passed`。
- Python AST：`warframe_agent/web/app.py` 为 `AST OK`。
- JavaScript 语法：`node --check warframe_agent\web\static\js\app.js` 退出码 0。
- `git diff --check`：退出码 0，仅提示相关工作区文件下次 Git 触碰时 LF 会转换为 CRLF。

备注：普通沙箱导入 Web app 或启动 uvicorn 时仍会受既有 SQLite WAL / uvicorn 可写环境限制影响，Web API 与 Runtime Playwright 目标测试需在项目可写运行环境中补跑。

## 后续建议

下一步可以从剩余学习队列继续选择：

- 可检查知识库与记忆 vault。
- Browser / GUI Agent 安全边界。
- 语音和陪伴式体验评估。
- 若继续 Step 35 分支，则优先设计“软拦截 -> 用户确认 -> 受控执行”。
