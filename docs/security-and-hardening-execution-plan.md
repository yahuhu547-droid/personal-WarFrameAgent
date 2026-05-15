# Warframe 项目安全加固与分阶段整改执行计划

## 背景

本计划用于跟踪 Warframe 交易助手的安全、文档、前端和维护性整改。当前项目功能和测试基线较稳定，但审查发现以下优先问题：

- 本地敏感配置、推送配置、飞书会话标识和运行日志容易进入提交候选。
- 主文档与当前实现不一致，尤其是本地/云端模型、模块清单、Web API 覆盖范围和测试规模。
- Web 前端存在较多 `innerHTML` 与内联 `onclick`，部分位置会插入 API 或用户可控数据。
- `warframe_agent/web/app.py` 承担过多职责，后续应在安全基线稳定后逐步拆分。

## 风险摘要

### P0：凭据与本地运行态文件

已发现本地配置和日志中存在第三方服务凭据、推送配置或用户/会话标识。仓库将通过 `.gitignore` 防止后续误提交，但这不会撤销已经暴露过的凭据。

必须人工完成：

- 轮换飞书 App Secret。
- 轮换 WxPusher App Token。
- 轮换云端模型 API Key。
- 清理或归档包含访问票据、用户标识、会话内容的旧日志。

### P1：前端动态 HTML 注入面

前端应逐步把 API/用户数据渲染从字符串模板迁移到 DOM API：

- 普通文本使用 `textContent`。
- 动态事件使用 `addEventListener`。
- 富文本仅允许经过明确净化的 Markdown/HTML 渲染路径。

### P1：文档漂移

主文档需要优先与当前实现对齐，历史阶段文档应标注为历史快照，避免误导后续维护。

### P2：Web 后端维护性

`warframe_agent/web/app.py` 应在测试和安全加固后按路由域拆分，拆分时保持 API 合约不变。

## 执行阶段

### Batch 1：安全基线

- 更新 `.gitignore`，忽略本地敏感配置、日志、数据库 sidecar、测试/UI 产物。
- 保留本地配置文件，不在自动整改中删除用户环境。
- 记录凭据轮换事项。

验证：

- `git status --short`
- `git diff --check`

### Batch 2：主文档同步

- 更新 `md/README.md`。
- 更新 `md/AgentArchitecture.md`。
- 必要时标注 `md/WebService.md` 的历史快照属性。

验证：

- 搜索 `完全本地`、`零云端`、`409`、`40+`、`35+ API` 等旧描述。
- `python -m pytest tests -q`

### Batch 3：后端输入验证

- 收紧 `warframe_agent/web/app.py` 中 Pydantic 请求模型。
- 对关键 query/body 参数增加长度、枚举、范围约束。
- 补充 API 负向测试。

验证：

- `python -m pytest tests/test_web_api.py -q`
- `python -m pytest tests -q`

### Batch 4：前端 XSS 热点治理

优先处理：

- `warframe_agent/web/static/js/sidebar.js`
- 收藏列表、提醒列表、关注列表、搜索建议等用户/API 数据渲染区域。

验证：

- `python start_web.py`
- 使用 Playwright 以真实用户角色测试聊天、收藏、提醒、关注、价格详情、图表。
- 使用包含 HTML 标签、引号、反引号的测试数据确认只按文本显示。
- 浏览器控制台无新错误。
- `python -m pytest tests -q`

### Batch 5：前端回归测试补强

- 整理或新增稳定的 Playwright 测试。
- 覆盖恶意字符串渲染、按钮事件、空状态和正常状态。

验证：

- 运行前端 smoke 测试。
- 确认截图和测试输出不会污染 git 状态。

### Batch 6：Web 后端模块化

- 按路由域逐步拆分 `warframe_agent/web/app.py`。
- 优先拆低耦合路由，如 history/trades。
- 保持 endpoint 路径、请求体、响应格式不变。

验证：

- 路由清单迁移前后保持一致。
- `python -m pytest tests/test_web_api.py -q`
- `python -m pytest tests -q`
- Web 启动和 WebSocket 手动验证。

### Batch 7：历史文档一致性清理

- 标注历史阶段文档。
- 清理主文档间互相矛盾的陈述。

验证：

- 搜索旧数字和旧架构声明。
- 主入口文档互相一致。

## 执行记录

| 批次 | 状态 | 验证 |
|------|------|------|
| Batch 1 | 已完成 | `git status --short` 已不再显示飞书/推送配置、日志、数据库 sidecar 和截图目录；`git diff --check` 仅提示 LF/CRLF 换行差异 |
| Batch 2 | 已完成 | `md/README.md` 与 `md/AgentArchitecture.md` 已同步；旧描述扫描为空；全量测试 496 passed |
| Batch 3 | 已完成 | `warframe_agent/web/app.py` 已收紧 body/query 输入校验；`python -m pytest tests/test_web_api.py -q` 25 passed；`python -m pytest tests -q` 499 passed |
| Batch 4 | 已完成 | `sidebar.js` 收藏/提醒和利润建议、`app.js` 关注列表已迁移到 DOM/textContent/addEventListener；Playwright 用户视角 XSS 检查通过；`python -m pytest tests -q` 499 passed |
| Batch 5 | 已完成 | 新增 `tests/test_web_ui_playwright.py`，以用户路径验证聊天、收藏、提醒、关注、更多菜单、交易历史、利润计算器、报告与恶意字符串渲染；`python -m pytest tests/test_web_ui_playwright.py -q` 2 passed；全量测试 501 passed |
| Batch 6 | 未开始 | - |
| Batch 7 | 未开始 | - |
