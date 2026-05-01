# Warframe Agent 升级计划：从 CLI 到 Web UI

## 项目背景

### 初始状态（Phase 0-4 完成，相关描述文件在当前文件夹下单README.md里）
- 纯终端应用，只适合开发者自用
- 95 个测试全部通过
- 已实现功能：bug 修复、后台监控、价格历史、会话上下文、LLM 工具路由

### 升级目标
将项目从 CLI 工具升级为面向玩家的 Web 应用：
- ✅ 可视化界面（Web UI）
- ✅ 更好的交互体验（流式输出、加载状态、价格图表）
- ✅ 实时通知（价格提醒推送到浏览器）
- ✅ 更友好的错误处理和引导

### 技术方案
- **后端**: FastAPI + WebSocket
- **前端**: 纯 HTML/CSS/JavaScript（无需构建工具）
- **访问方式**: 浏览器访问 localhost:8000

---

## 实施计划

### Phase 5: FastAPI 后端 + WebSocket 基础

**目标**: 将 CLI 的 ChatAgent.answer() 暴露为 Web API，支持流式输出。

#### 5.1 新增依赖
- fastapi, uvicorn[standard], websockets — Web 框架 + ASGI 服务器
- aiosqlite — 异步 SQLite（解决并发写入锁问题）

#### 5.2 FastAPI 应用
**文件**: `warframe_agent/web/app.py`

实现的 API 端点：
| 端点 | 功能 |
|------|------|
| POST /api/chat | 接收消息，返回 Agent 回复 |
| GET /api/memory | 获取当前记忆摘要 |
| POST /api/fav | 添加收藏 |
| DELETE /api/fav | 移除收藏 |
| POST /api/alert | 添加价格提醒 |
| DELETE /api/alert | 移除价格提醒 |
| POST /api/pref | 设置偏好 |
| GET /api/history/{item_id} | 获取价格历史数据 |
| WebSocket /ws/chat | 流式对话 |
| WebSocket /ws/notifications | 实时价格提醒推送 |

#### 5.3 异步适配
- **market.py**: 添加 `fetch_orders_async()` 使用 `asyncio.to_thread()`
- **llm.py**: 添加 `stream_ollama_chat()` 流式生成
- **price_history.py**: 启用 WAL 模式解决并发写入

#### 5.4 Monitor 推送适配
- **monitor.py**: 已支持 `on_alert` 回调
- **app.py**: WebSocket 广播通知

#### 5.5 启动入口
- `start_web.py` — Python 启动脚本
- `start_web.bat` — Windows 一键启动
- `main.py` — 新增选项 5：启动 Web 界面

#### 5.6 测试
- `tests/test_web_api.py` — 7 个测试用例
- 验证所有端点和 WebSocket 连接

---

### Phase 6: 前端界面

**目标**: 创建现代化 Web UI，暗色主题，Warframe 游戏风格。

#### 6.1 技术选择
- 纯 HTML + CSS + JavaScript（无需 Node.js 构建工具）
- Chart.js 用于价格趋势图
- FastAPI StaticFiles 托管静态文件

#### 6.2 页面布局
**三栏单页应用**：

**左侧边栏**：
- 收藏列表（实时价格 + 涨跌标记）
- 价格提醒列表（状态指示灯）
- 快捷操作按钮

**中间主区域**：
- 对话窗口（聊天气泡样式）
- 输入框 + 发送按钮
- 快捷提问按钮（"充沛多少钱"、"扫描关注"等）

**右侧面板**：
- 物品详情卡片（卖价/收价/价差）
- 价格趋势折线图（Chart.js）
- 卖家/买家排行表格

#### 6.3 视觉设计
- 暗色主题（贴合 Warframe 游戏风格）
- 配色：深灰背景 + 金色/蓝色强调色
- 响应式布局，支持窄屏（手机浏览器）

#### 6.4 交互细节
- LLM 回复流式显示（逐字打出效果）
- API 请求时显示加载动画
- 价格提醒触发时浏览器通知（Notification API）
- 私聊命令点击即复制

---

### Phase 7: 体验优化

**目标**: 提升用户体验，添加智能功能。

#### 7.1 智能搜索建议
- **API**: `GET /api/suggest?q=<query>` — 实时返回匹配的物品名列表
- **前端**: 输入框下拉补全，300ms 防抖
- **数据源**: 从别名表 + 字典中搜索，最多返回 10 个结果

#### 7.2 错误处理优化
- 网络错误：显示友好提示而非 Python 异常
- LLM 超时：显示"模型响应较慢，已为你展示实时数据"
- 物品未找到：显示"未找到该物品，你是不是想找：xxx？"

#### 7.3 价格图表
- 使用 Chart.js 绘制价格趋势折线图
- 卖价线（红色）+ 收价线（绿色）
- 支持时间范围切换（24h/7d/30d）

#### 7.4 首次使用引导
- 新用户打开时显示欢迎弹窗
- 引导设置平台偏好（PC/PS/Xbox/Switch）
- localStorage 记录访问状态，避免重复显示

#### 7.5 快捷操作
- **键盘快捷键**: Enter 发送、Esc 关闭面板
- **快捷按钮**: 充沛价格、扫描关注、查看记忆
- **点击建议**: 搜索建议点击自动填充输入框

---

### Phase 8: 进阶功能

**目标**: 添加高级功能，优化性能。

#### 8.1 多物品对比
- **API**: `POST /api/compare` — 接收物品名称列表，返回对比结果
- **前端**: "对比物品"按钮，弹窗输入物品名称
- **功能**: 最多对比 3 个物品，并排显示卖价、收价、价差

#### 8.2 API 请求优化
- **内存缓存**: TTL 60秒，重复查询直接返回缓存
  - 缓存结构: `_cache[item_id] = (orders_data, timestamp)`
  - 效果: 响应时间从 ~500ms 降至 <1ms
- **请求限速**: 每秒最多 3 次请求（0.34秒间隔）
  - 防止被 warframe.market 封禁
  - 自动 sleep 控制请求频率

#### 8.3 导出与分享
- 查价结果导出为图片（截图分享到游戏群/Discord）
- 每日报告在 Web 页面内直接展示

#### 8.4 系统托盘通知（可选）
- 使用 plyer 库发送 Windows 系统通知
- 价格提醒触发时弹出桌面通知，即使浏览器最小化也能看到

---

## 关键文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `warframe_agent/web/__init__.py` | Web 模块初始化 |
| 新建 | `warframe_agent/web/app.py` | FastAPI 应用 + 所有端点 |
| 新建 | `warframe_agent/web/static/index.html` | 主页面 |
| 新建 | `warframe_agent/web/static/css/style.css` | 暗色主题样式 |
| 新建 | `warframe_agent/web/static/js/app.js` | API 调用和初始化 |
| 新建 | `warframe_agent/web/static/js/chat.js` | 对话功能 |
| 新建 | `warframe_agent/web/static/js/chart.js` | 价格图表 |
| 新建 | `warframe_agent/web/static/js/sidebar.js` | 侧边栏 |
| 新建 | `start_web.py` | Web 启动入口 |
| 新建 | `start_web.bat` | 一键启动脚本 |
| 新建 | `tests/test_web_api.py` | Web API 测试 |
| 修改 | `warframe_agent/market.py` | 添加缓存和限速 |
| 修改 | `warframe_agent/llm.py` | 添加流式输出 |
| 修改 | `warframe_agent/price_history.py` | 启用 WAL 模式 |
| 修改 | `warframe_agent/monitor.py` | WebSocket 推送支持 |
| 修改 | `main.py` | 新增 Web 启动选项 |
| 修改 | `requirements.txt` | 添加 Web 依赖 |

---

## 验证清单

每个 Phase 完成后的验证步骤：

1. **全量测试通过**
   ```bash
   python -m unittest discover -s tests -v
   ```

2. **Phase 5 验证**: curl 测试所有 API 端点 + WebSocket 连接

3. **Phase 6 验证**: 浏览器打开 http://localhost:8000，测试完整对话流程

4. **Phase 7 验证**: 测试搜索建议、错误场景、图表渲染

5. **Phase 8 验证**: 测试并发请求、缓存命中、通知推送

---

## 最终成果

### 测试结果
- **102 个测试全部通过**（从 95 个增加到 102 个）
- 覆盖所有核心模块和 Web API

### 功能清单
1. ✅ 实时查价 — 查询 warframe.market 最新价格
2. ✅ 对话式交互 — 自然语言查询，LLM 工具路由
3. ✅ 收藏和提醒 — 关注物品，价格提醒推送
4. ✅ 价格历史 — SQLite 记录，Chart.js 可视化
5. ✅ 后台监控 — daemon 线程，WebSocket 实时推送
6. ✅ 智能搜索 — 输入建议，6 层 fallback 解析
7. ✅ 多物品对比 — 并排对比价格和价差
8. ✅ 性能优化 — 缓存 + 限速，保护 API

### 技术栈
- **后端**: Python 3.14, FastAPI, WebSocket, SQLite, Ollama (qwen3:8b)
- **前端**: 纯 HTML/CSS/JS, Chart.js
- **测试**: 102 个单元测试，完整覆盖

### 访问方式
- **Web 界面**: 启动 `start_web.bat` 或 `python start_web.py`，访问 http://127.0.0.1:8000
- **CLI 模式**: 运行 `python main.py`，选择菜单选项

---

## 使用示例

### Web 界面
1. 启动服务器：`start_web.bat`
2. 浏览器访问：http://127.0.0.1:8000
3. 首次访问显示欢迎弹窗，设置平台偏好
4. 输入物品名称，自动显示搜索建议
5. 点击"对比物品"按钮，输入多个物品名称进行对比

### 多物品对比
```
输入: 充沛, 川流不息, 活力

对比结果:
📦 充沛赋能
  卖价: 45p
  收价: 38p
  价差: 7p

📦 川流不息 Prime
  卖价: 29p
  收价: 25p
  价差: 4p
```

### 搜索建议
输入"充"时自动显示：
- 充沛赋能
- 充沛Prime
- 充能弹药转换器

---

## 性能指标

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 重复查询响应时间 | ~500ms | <1ms |
| API 请求频率 | 无限制 | 3次/秒 |
| 并发写入 | 可能锁死 | WAL 模式 |
| 测试用例数 | 95 个 | 102 个 |

---

## 后续优化方向

1. **导出功能** — 查价结果导出为图片
2. **每日报告** — Web 页面内直接展示
3. **系统托盘通知** — 桌面通知推送
4. **移动端优化** — 响应式布局改进
5. **多语言支持** — 中英文切换
