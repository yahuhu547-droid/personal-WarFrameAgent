# Warframe Agent 升级计划：从 CLI 到 Web UI

## 项目概述

本文档详细记录了 Warframe 交易助手从纯 CLI 应用升级为具有专业级 Web UI 的完整过程，包括后端 API 开发、前端界面设计、UI 美化、性能优化等方面。

### 初始状态（Phase 0-4 完成，相关描述文件在当前文件夹下 README.md 里）
- 纯终端应用，只适合开发者自用
- 169 个测试全部通过
- 已实现功能：bug 修复、后台监控、价格历史、会话上下文、LLM 工具路由

### 升级目标
将项目从 CLI 工具升级为面向玩家的 Web 应用：
- ✅ 可视化界面（Web UI）— Tenno 科技终端风格
- ✅ 更好的交互体验（流式输出、加载状态、价格图表）
- ✅ 实时通知（价格提醒推送到浏览器）
- ✅ 更友好的错误处理和引导
- ✅ 专业级 UI 设计（响应式、动画、无障碍）

### 技术方案
- **后端**: FastAPI + WebSocket + SQLite
- **前端**: 纯 HTML/CSS/JavaScript + Chart.js
- **UI 设计**: Tenno 科技终端风格，CSS 变量系统
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

**目标**: 创建现代化 Web UI，采用 "Tenno 科技终端" 设计风格。

#### 6.1 技术选择
- 纯 HTML + CSS + JavaScript（无需 Node.js 构建工具）
- Chart.js 用于价格趋势图
- FastAPI StaticFiles 托管静态文件
- CSS 变量系统实现主题一致性
- 模块化 JavaScript 架构

#### 6.2 页面布局
**三栏单页应用**：

**左侧边栏**（300px）：
- 收藏列表（实时价格 + 涨跌标记）
- 价格提醒列表（状态指示灯）
- 快捷操作按钮
- 系统状态指示器
- 序列号装饰

**中间主区域**：
- 对话窗口（聊天气泡样式）
- 输入框 + 发送按钮
- 快捷提问按钮（"充沛多少钱"、"扫描关注"等）
- 欢迎消息

**右侧面板**（400px）：
- 物品详情卡片（卖价/收价/价差）
- 价格趋势折线图（Chart.js）
- 统计信息（平均/最低/最高价格）

#### 6.3 视觉设计 - Tenno 科技终端风格

**色彩方案**：
- **主色调**：深空黑 (#070a14) + Tenno 金 (#d4a737) + 能量蓝 (#4a9eff)
- **辅助色**：成功绿 (#4ade80)、警告橙 (#f59e0b)、错误红 (#ef4444)
- **渐变效果**：金色渐变、蓝色渐变、背景渐变

**字体设计**：
- **标题字体**：Orbitron - 未来感强，适合标题
- **正文字体**：Rajdhani - 科技感，适合正文
- **数据字体**：JetBrains Mono - 清晰易读，适合价格数据

**视觉效果**：
- **扫描线效果**：模拟终端扫描线
- **光效边框**：金色/蓝色发光边框
- **几何装饰**：Warframe 风格的角落装饰
- **背景纹理**：暗纹背景增加层次感

#### 6.4 交互细节

**动画效果**：
- **页面加载**：元素逐个出现动画
- **消息动画**：用户/Agent 消息从不同方向滑入
- **价格动画**：价格上涨/下跌时的闪烁效果
- **按钮动画**：悬停时的光效扫过
- **模态动画**：弹窗缩放+淡入效果

**交互反馈**：
- **搜索建议**：输入时实时下拉补全
- **键盘快捷键**：Enter 发送、Esc 关闭、Ctrl+K 聚焦
- **Toast 通知**：页面内通知系统
- **加载状态**：Warframe 风格的点状加载
- **错误提示**：友好的错误状态显示

**响应式设计**：
- **移动端**：< 640px（单栏布局）
- **平板端**：640px - 1024px（侧边栏收缩）
- **桌面端**：> 1024px（完整三栏布局）
- **大屏幕**：> 1440px（扩大面板）
- **触摸设备**：增大点击区域，优化触摸反馈

#### 6.5 无障碍设计
- **高对比度模式**：支持高对比度显示
- **减少动画模式**：尊重用户动画偏好
- **焦点样式**：清晰的焦点指示
- **键盘导航**：完整的键盘操作支持
- **屏幕阅读器**：语义化 HTML 结构

---

### UI 设计详解：Tenno 科技终端风格

#### 设计理念

**核心概念**：将 Warframe 交易助手打造成一个 **Tenno 科技终端**，让用户感觉自己在使用一套来自 Warframe 世界的高科技交易系统。

**设计风格**：
- **主风格**：未来科幻工业风 + 军事终端感
- **参考元素**：
  - Warframe 游戏 UI 的金色/橙色强调色
  - Corpus 财团的高科技感
  - Tenno 盔甲的几何线条
  - 星际战舰的控制台界面

#### CSS 架构

```
variables.css   - CSS 变量定义（颜色、字体、间距、动画等）
animations.css  - 动画关键帧（淡入、滑入、脉冲、扫描线等）
style.css       - 主样式（Tenno 科技终端风格）
responsive.css  - 响应式设计（移动端/平板/桌面/大屏/超大屏）
```

#### 色彩系统

**主色调**：
- **深空黑**：#070a14 - 主背景色
- **Tenno 金**：#d4a737 - 主强调色，用于标题、重要元素
- **能量蓝**：#4a9eff - 交互元素，用于按钮、链接

**辅助色**：
- **成功绿**：#4ade80 - 价格上涨、成功状态
- **警告橙**：#f59e0b - 提醒、警告状态
- **错误红**：#ef4444 - 价格下跌、错误状态

**渐变效果**：
- **金色渐变**：linear-gradient(135deg, #d4a737, #b8860b)
- **蓝色渐变**：linear-gradient(135deg, #4a9eff, #2563eb)
- **背景渐变**：linear-gradient(180deg, #070a14, #0c1020, #070a14)

#### 字体系统

**字体选择**：
- **Orbitron** - 未来感标题字体，适合标题和重要元素
- **Rajdhani** - 科技感正文字体，适合正文和标签
- **JetBrains Mono** - 等宽数据字体，适合价格数据和代码

**字体层次**：
- **标题**：Orbitron, 16-24px, 大写，金色
- **正文**：Rajdhani, 14-16px, 灰色
- **数据**：JetBrains Mono, 12-14px, 亮色
- **标签**：Rajdhani, 12px, 大写，次级灰色

#### 视觉效果

**扫描线效果**：
```css
.scanlines::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.1) 2px,
    rgba(0, 0, 0, 0.1) 4px
  );
  pointer-events: none;
  z-index: 10;
}
```

**光效边框**：
```css
.glow-border {
  border: 1px solid rgba(212, 167, 55, 0.3);
  box-shadow:
    0 0 10px rgba(212, 167, 55, 0.1),
    inset 0 0 10px rgba(212, 167, 55, 0.05);
}
```

**几何装饰**：
```css
.deco-corner::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 20px;
  height: 20px;
  border-left: 2px solid #d4a737;
  border-top: 2px solid #d4a737;
}
```

#### 动画系统

**基础动画**：
- **fadeInUp** - 淡入上移
- **fadeInLeft** - 淡入左移
- **fadeInRight** - 淡入右移
- **fadeInScale** - 淡入缩放

**特效动画**：
- **pulseGlow** - 脉冲光效
- **scanline** - 扫描线效果
- **spin** - 旋转
- **blink** - 闪烁

**价格动画**：
- **priceUp** - 价格上涨（绿色闪烁）
- **priceDown** - 价格下跌（红色闪烁）
- **priceFlash** - 价格闪烁

**消息动画**：
- **messageInUser** - 用户消息从右侧滑入
- **messageInAgent** - Agent 消息从左侧滑入
- **messageInSystem** - 系统消息淡入

#### 交互设计

**搜索建议下拉**：
- **背景**：深色半透明
- **边框**：金色发光边框
- **选中项**：蓝色高亮
- **动画**：从上往下滑入

**模态弹窗**：
- **背景**：模糊 + 暗色遮罩
- **弹窗**：带几何装饰的卡片
- **动画**：缩放 + 淡入
- **关闭按钮**：X 图标 + 旋转动画

**加载状态**：
- **加载动画**：Warframe 风格的旋转图标
- **骨架屏**：带闪烁效果的占位符
- **进度条**：金色渐变进度条

#### 响应式设计

**断点设计**：
- **移动端**：< 640px（单栏布局）
- **平板端**：640px - 1024px（侧边栏收缩）
- **桌面端**：> 1024px（完整三栏布局）
- **大屏幕**：> 1440px（扩大面板）
- **超大屏幕**：> 1920px（居中显示）

**适配优化**：
- **触摸设备**：增大点击区域，优化触摸反馈
- **安全区域**：适配刘海屏等异形屏
- **滚动条**：自定义滚动条样式
- **打印样式**：支持页面打印

#### 无障碍设计

**可访问性**：
- **高对比度模式**：支持高对比度显示
- **减少动画模式**：尊重用户动画偏好
- **焦点样式**：清晰的焦点指示
- **键盘导航**：完整的键盘操作支持
- **屏幕阅读器**：语义化 HTML 结构

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

### 后端文件
| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `warframe_agent/web/__init__.py` | Web 模块初始化 |
| 新建 | `warframe_agent/web/app.py` | FastAPI 应用 + 所有端点 |
| 修改 | `warframe_agent/market.py` | 添加缓存和限速 |
| 修改 | `warframe_agent/llm.py` | 添加流式输出 |
| 修改 | `warframe_agent/price_history.py` | 启用 WAL 模式 |
| 修改 | `warframe_agent/monitor.py` | WebSocket 推送支持 |

### 前端文件
| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `warframe_agent/web/static/index.html` | 主页面（Tenno 科技终端风格） |
| 新建 | `warframe_agent/web/static/css/variables.css` | CSS 变量定义（颜色、字体、间距） |
| 新建 | `warframe_agent/web/static/css/animations.css` | 动画定义（淡入、滑入、脉冲等） |
| 新建 | `warframe_agent/web/static/css/style.css` | 主样式（Tenno 科技终端风格） |
| 新建 | `warframe_agent/web/static/css/responsive.css` | 响应式设计（移动端/平板/桌面） |
| 新建 | `warframe_agent/web/static/js/app.js` | 主应用逻辑、API 调用、通知系统 |
| 新建 | `warframe_agent/web/static/js/chat.js` | 对话功能、消息管理、打字机效果 |
| 新建 | `warframe_agent/web/static/js/sidebar.js` | 侧边栏功能、收藏/提醒管理 |
| 新建 | `warframe_agent/web/static/js/chart.js` | 价格图表、统计信息 |

### 启动和测试文件
| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `start_web.py` | Web 启动入口 |
| 新建 | `start_web.bat` | 一键启动脚本 |
| 新建 | `tests/test_web_api.py` | Web API 测试（7 个用例） |
| 修改 | `main.py` | 新增 Web 启动选项 |
| 修改 | `requirements.txt` | 添加 Web 依赖 |

### 文档文件
| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `docs/ui_design_plan.md` | UI 设计计划文档 |
| 新建 | `docs/ui_implementation_report.md` | UI 实现报告 |
| 新建 | `docs/ui_design_summary.md` | UI 设计总结 |
| 新建 | `docs/ui_preview.html` | UI 预览页面 |
| 更新 | `README.md` | 更新项目文档 |

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
9. ✅ Tenno 科技终端 UI — 专业级前端设计

### 技术栈
- **后端**: Python 3.14, FastAPI, WebSocket, SQLite, Ollama (qwen3:8b)
- **前端**: 纯 HTML/CSS/JS, Chart.js, CSS 变量系统
- **UI 设计**: Tenno 科技终端风格，响应式设计，丰富动画效果
- **测试**: 102 个单元测试，完整覆盖

### UI 设计亮点

**视觉设计**：
- **色彩方案**：深空黑 + Tenno 金 + 能量蓝，完美契合 Warframe 游戏风格
- **字体设计**：Orbitron (标题) + Rajdhani (正文) + JetBrains Mono (数据)
- **视觉效果**：扫描线、光效边框、几何装饰、背景纹理

**交互设计**：
- **动画效果**：消息滑入、价格闪烁、按钮光效、模态弹窗动画
- **搜索建议**：实时下拉补全，300ms 防抖
- **键盘快捷键**：Enter 发送、Esc 关闭、Ctrl+K 聚焦
- **Toast 通知**：页面内通知系统

**响应式设计**：
- 支持移动端、平板端、桌面端、大屏幕
- 触摸设备优化
- 安全区域适配（刘海屏）

**无障碍设计**：
- 高对比度模式
- 减少动画模式
- 焦点样式优化
- 键盘导航支持

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

### 后端性能
| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 重复查询响应时间 | ~500ms | <1ms |
| API 请求频率 | 无限制 | 3次/秒 |
| 并发写入 | 可能锁死 | WAL 模式 |
| 测试用例数 | 95 个 | 169 个 |

### 前端性能
| 指标 | 说明 |
|------|------|
| 页面加载 | 使用 CSS 变量，减少重复代码 |
| 动画性能 | 使用 CSS 动画，GPU 加速 |
| 响应式设计 | 支持 5 种断点（移动端/平板/桌面/大屏/超大屏） |
| 浏览器兼容 | Chrome 90+, Firefox 88+, Safari 14+, Edge 90+ |

---

## 后续优化方向

### 短期优化（1-2周）
1. **导出功能** — 查价结果导出为图片
2. **每日报告** — Web 页面内直接展示
3. **系统托盘通知** — 桌面通知推送
4. **音效支持** — 添加操作音效

### 中期优化（1-2月）
5. **主题切换** — 支持亮色/暗色主题
6. **图表增强** — 添加更多图表类型和交互
7. **离线支持** — Service Worker 缓存
8. **多语言支持** — 中英文切换

### 长期优化（3-6月）
9. **PWA 支持** — 可安装的 Web 应用
10. **自定义主题** — 用户自定义颜色方案
11. **高级动画** — 更丰富的动画效果
12. **性能监控** — 前端性能监控和优化

## 相关文档

- [UI 设计计划](docs/ui_design_plan.md) — 详细的设计理念和规范
- [UI 实现报告](docs/ui_implementation_report.md) — 实现的功能和技术细节
- [UI 设计总结](docs/ui_design_summary.md) — 完整的设计总结
- [UI 预览](docs/ui_preview.html) — 在线预览设计效果
- [升级计划](docs/upgrade_plan.md) — Phase 5-8 的完整升级计划

## UI 设计资源

### 字体资源
- [Orbitron](https://fonts.google.com/specimen/Orbitron) - 未来感标题字体
- [Rajdhani](https://fonts.google.com/specimen/Rajdhani) - 科技感正文字体
- [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) - 等宽数据字体

### 色彩参考
- **Tenno 金**：#d4a737 - Warframe 标志性颜色
- **能量蓝**：#4a9eff - Corpus 财团风格
- **深空黑**：#070a14 - 星际背景色

### 设计灵感
- Warframe 游戏 UI 设计
- Corpus 财团高科技界面
- Tenno 盔甲几何线条
- 星际战舰控制台界面

### 技术参考
- CSS 变量系统
- CSS 动画关键帧
- 响应式设计断点
- 无障碍设计规范

## 浏览器兼容性

### 支持的浏览器
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

### 使用的现代 CSS 特性
- CSS 变量
- Flexbox
- Grid
- CSS 动画
- 媒体查询
- backdrop-filter
- @supports

## 开发规范

### CSS 命名规范
- 类名：kebab-case
- 变量：camelCase
- 常量：UPPER_SNAKE_CASE

### 文件组织
```
/static/css/
  ├── variables.css    # CSS 变量定义
  ├── animations.css   # 动画定义
  ├── style.css        # 主样式
  └── responsive.css   # 响应式设计
```

### 注释规范
- 每个组件前添加注释
- 颜色值添加说明
- 动画效果添加描述

## 设计验证清单

### 可用性测试
- [ ] 文字清晰易读
- [ ] 操作反馈及时
- [ ] 颜色对比度达标
- [ ] 动画不卡顿

### 性能测试
- [ ] 页面加载时间 < 2s
- [ ] 动画帧率 > 60fps
- [ ] 内存占用合理
- [ ] 移动端流畅

### 兼容性测试
- [ ] Chrome 浏览器正常
- [ ] Firefox 浏览器正常
- [ ] Safari 浏览器正常
- [ ] Edge 浏览器正常
- [ ] 移动端浏览器正常

### 无障碍测试
- [ ] 高对比度模式正常
- [ ] 减少动画模式正常
- [ ] 键盘导航正常
- [ ] 屏幕阅读器正常

---

## 项目总结

### 升级成果

通过 Phase 5-8 的完整升级，Warframe 交易助手已经从一个纯 CLI 工具成功转型为具有专业级 Web UI 的现代化应用：

**后端能力**：
- ✅ FastAPI REST API（35+ 个端点）
- ✅ WebSocket 实时通信（2 个端点）
- ✅ 异步适配和性能优化
- ✅ 缓存和限速机制
- ✅ 169 个单元测试覆盖

**前端设计**：
- ✅ Tenno 科技终端风格 UI
- ✅ CSS 变量系统（一致性）
- ✅ 丰富动画效果（15+ 种动画）
- ✅ 响应式设计（5 种断点）
- ✅ 无障碍设计支持

**用户体验**：
- ✅ 智能搜索建议
- ✅ 首次使用引导
- ✅ 多物品对比
- ✅ 实时通知推送
- ✅ 键盘快捷键支持

### 技术亮点

1. **CSS 变量系统**：使用 CSS 变量实现主题一致性，便于维护和扩展
2. **动画性能优化**：使用 CSS 动画而非 JavaScript，GPU 加速
3. **响应式设计**：支持从移动端到超大屏幕的完整适配
4. **无障碍设计**：支持高对比度、减少动画模式、键盘导航
5. **模块化架构**：CSS 和 JavaScript 模块化，便于维护

### 设计价值

**视觉独特性**：
- 具有强烈的 Warframe 游戏风格
- Tenno 科技终端设计概念
- 独特的色彩和字体方案

**交互流畅性**：
- 丰富的动画和过渡效果
- 即时的交互反馈
- 直观的操作流程

**信息清晰性**：
- 层次分明的视觉设计
- 清晰的信息架构
- 易于阅读的数据展示

**体验沉浸感**：
- 让用户感觉自己在使用 Tenno 科技终端
- 沉浸式的游戏风格界面
- 流畅的操作体验

### 项目价值

1. **技术价值**：展示了完整的 Web 应用开发流程，包括后端 API、前端设计、性能优化
2. **设计价值**：提供了 Warframe 风格 UI 设计的完整方案，可复用到其他项目
3. **用户价值**：为 Warframe 玩家提供了专业、美观、易用的交易工具
4. **学习价值**：包含了 CSS 变量、动画、响应式设计等现代前端技术的最佳实践

### 未来展望

> 以下为 Phase 9-12 升级计划，聚焦 Web Agent 的用户操作体验提升。

---

## Phase 9: 对话体验增强

**目标**: 让对话更流畅、信息更易获取、交互更自然。

### 9.1 流式对话输出

**现状**: 前端使用 `POST /api/chat` 同步请求，用户需等待完整回复才能看到内容。
**方案**: 改用已有的 `/ws/chat` WebSocket 端点，实现逐字流式输出。

| 项目 | 说明 |
|------|------|
| 前端 | `chat.js` 改用 WebSocket 发送消息，实时接收 token 流 |
| 后端 | `app.py` 的 `/ws/chat` 调用 `stream_ollama_chat()` 逐 token 推送 |
| 体验 | 用户看到打字机实时输出，而非等待数秒后一次性显示 |

**关键实现**:
- 前端维护一个 WebSocket 连接复用（聊天用），与通知 WebSocket 分开
- 每个 token 通过 `ws.send_json({"token": "..."})` 推送
- 结束时发送 `{"done": true, "reply": "完整文本"}` 信号
- 超时处理：15 秒无响应显示"模型响应较慢，已为你展示实时数据"

### 9.2 对话历史持久化

**现状**: 刷新页面后对话记录全部丢失。
**方案**: 使用 `localStorage` 保存最近 50 条对话。

| 项目 | 说明 |
|------|------|
| 存储 | `localStorage.setItem('chat_history', JSON.stringify(messages))` |
| 恢复 | 页面加载时读取并渲染历史消息 |
| 清理 | 超过 50 条自动淘汰最早的；提供"清空对话"按钮 |
| 容量 | localStorage 约 5MB，50 条消息绰绰有余 |

### 9.3 Agent 回复 Markdown 渲染

**现状**: Agent 回复以纯文本显示，价格表格、加粗等格式丢失。
**方案**: 引入轻量 Markdown 渲染库（`marked.js`，~40KB），将回复渲染为 HTML。

| 项目 | 说明 |
|------|------|
| 支持语法 | 标题、加粗、列表、表格、代码块、链接 |
| 安全 | 使用 DOMPurify 防止 XSS |
| 降级 | 渲染失败时回退到纯文本显示 |
| 样式 | 表格使用 Tenno 科技终端风格（金色表头、深色背景） |

### 9.4 消息操作菜单

**现状**: 对话消息无法复制、重试或进一步操作。
**方案**: 每条消息悬停时显示操作按钮。

| 操作 | 功能 |
|------|------|
| 复制 | 一键复制消息文本到剪贴板 |
| 重试 | 重新发送该条用户消息（Agent 重新回答） |
| 收藏 | 如果回复包含物品价格，快捷添加到收藏 |
| 提醒 | 如果回复包含物品价格，快捷设置价格提醒 |

### 9.5 物品未找到引导

**现状**: 用户输入不存在的物品名时，Agent 回复较生硬。
**方案**: 后端检测物品解析失败时，返回候选建议列表。

| 项目 | 说明 |
|------|------|
| 后端 | `chat.py` 解析失败时调用 RAG 搜索，返回 top-3 候选 |
| 前端 | 渲染为可点击的建议按钮："你是不是想找：XX、YY、ZZ？" |
| 交互 | 点击候选直接发送查询，无需重新输入 |

---

## Phase 10: 数据展示与可视化

**目标**: 让价格数据更直观、可操作、可分享。

### 10.1 物品详情卡片

**现状**: 右侧详情面板只有价格图表，缺少物品基本信息。
**方案**: 在图表上方添加物品详情卡片。

```
┌─────────────────────────────┐
│  充沛赋能                    │
│  Arcane Energize            │
│  ─────────────────────────  │
│  卖价    收价    价差         │
│  45p     38p     7p         │
│  🟢 Player1  🔴 Player2     │
│  ─────────────────────────  │
│  [收藏]  [设提醒]  [游戏私聊] │
└─────────────────────────────┘
```

| 元素 | 说明 |
|------|------|
| 物品名称 | 中文名 + 英文名 |
| 价格信息 | 最低卖价、最高收价、价差（带颜色标记） |
| 交易对象 | 卖家/买家游戏名 + 声望等级 |
| 快捷操作 | 收藏、设提醒、复制游戏私聊命令 |
| 满级估算 | arcane 类物品显示 21 个满级总花费 |

### 10.2 图表时间范围切换

**现状**: 图表只显示最近 50 条快照，无法选择时间范围。
**方案**: 添加时间范围选择器。

| 范围 | 说明 |
|------|------|
| 24h | 最近 24 小时，按小时聚合 |
| 7d | 最近 7 天，按天聚合 |
| 30d | 最近 30 天，按天聚合 |

**前端**: 图表上方添加三个切换按钮，样式使用 Tenno 科技终端风格。
**后端**: `GET /api/history/{item_id}?range=24h|7d|30d`，支持时间范围参数。

### 10.3 每日价格报告

**现状**: 每日报告只输出到 `reports/` 目录的文本文件。
**方案**: 在 Web 页面内直接展示每日报告。

| 项目 | 说明 |
|------|------|
| API | `GET /api/report` 返回今日报告数据（JSON） |
| 入口 | 侧边栏底部"每日报告"按钮，或快捷按钮 |
| 展示 | 模态弹窗内显示表格：物品名、昨日价、今日价、涨跌幅 |
| 导出 | 支持一键复制报告文本，粘贴到游戏群/Discord |

### 10.4 价格变动高亮

**现状**: 侧边栏收藏列表只显示静态物品名。
**方案**: 刷新时与上次数据对比，价格变动用动画高亮。

| 变动 | 视觉效果 |
|------|------|
| 上涨 | 绿色闪烁 + 向上箭头 `▲` |
| 下跌 | 红色闪烁 + 向下箭头 `▼` |
| 持平 | 无特殊效果 |

**实现**: 侧边栏刷新时对比 localStorage 中的上次价格快照。

---

## Phase 11: 个性化与设置

**目标**: 让用户可以根据自己的习惯定制界面。

### 11.1 主题切换

**现状**: `variables.css` 已定义 `[data-theme="light"]` 变量但未启用。
**方案**: 在侧边栏底部添加主题切换按钮。

| 主题 | 说明 |
|------|------|
| 暗色（默认） | 当前的 Tenno 科技终端深空黑风格 |
| 亮色 | 浅色背景 + 深色文字，适合白天使用 |

**实现**:
- `document.documentElement.setAttribute('data-theme', theme)`
- `localStorage.setItem('theme', theme)` 持久化
- 切换时添加过渡动画（0.3s ease-out）

### 11.2 通知设置面板

**现状**: 只有浏览器原生通知权限弹窗，无细粒度控制。
**方案**: 添加通知设置面板。

| 设置项 | 说明 |
|------|------|
| 浏览器通知 | 开关控制 |
| 通知音效 | 开关控制 + 音效选择（3 种） |
| 提醒阈值 | 价格提醒触发后的冷却时间（避免重复推送） |
| 静默时段 | 设置免打扰时间段 |

**入口**: 侧边栏底部齿轮图标 → 弹出设置模态框。

### 11.3 自定义快捷操作

**现状**: 快捷按钮固定为 4 个（充沛价格、扫描关注、查看记忆、对比物品）。
**方案**: 允许用户自定义快捷按钮。

| 功能 | 说明 |
|------|------|
| 添加 | 点击 "+" 按钮，输入按钮名称和对应消息 |
| 编辑 | 长按/右键编辑已有按钮 |
| 删除 | 拖拽删除或点击 X |
| 存储 | `localStorage` 保存自定义配置 |
| 预设 | 保留系统默认按钮，用户可在此基础上增删 |

### 11.4 布局偏好

**现状**: 三栏布局宽度固定，无法调整。
**方案**: 允许用户拖拽调整面板宽度。

| 设置 | 说明 |
|------|------|
| 侧边栏宽度 | 200px - 400px，拖拽分割线调整 |
| 详情面板宽度 | 300px - 500px，拖拽分割线调整 |
| 侧边栏位置 | 左侧（默认）/ 右侧 |
| 自动收起 | 移动端自动收起侧边栏（已有） |

---

## Phase 12: 效率工具与细节打磨

**目标**: 为高频用户提升操作效率，打磨交互细节。

### 12.1 命令面板

**方案**: `Ctrl+P` 打开命令面板（类似 VS Code），快速执行任意操作。

| 命令 | 功能 |
|------|------|
| `> 物品名` | 直接查询价格 |
| `/fav 物品名` | 添加收藏 |
| `/alert 物品名 below 40` | 添加提醒 |
| `/scan` | 扫描关注列表 |
| `/report` | 查看每日报告 |
| `/theme` | 切换主题 |
| `/clear` | 清空对话 |
| `/export` | 导出当前数据 |

**交互**: 输入框实时过滤命令列表，Enter 执行，Esc 关闭。

### 12.2 WebSocket 连接优化

**现状**: 断线后固定 5 秒重连，无退避策略；标签页不可见时仍持续请求。
**方案**:

| 优化项 | 说明 |
|------|------|
| 指数退避 | 重连间隔：1s → 2s → 4s → 8s → 30s（上限） |
| 状态指示 | 断线时状态指示器显示"重连中..."，带倒计时 |
| 标签页感知 | 使用 `document.visibilityState`，不可见时暂停自动刷新 |
| 心跳检测 | 每 30 秒发送 ping，60 秒无响应判定断线 |

### 12.3 键盘快捷键扩展

**现状**: 只有 Enter/Esc/Ctrl+K 三个快捷键。
**方案**: 扩展快捷键体系。

| 快捷键 | 功能 |
|------|------|
| `Ctrl+P` | 打开命令面板 |
| `Ctrl+/` | 显示快捷键帮助 |
| `Ctrl+Shift+F` | 聚焦收藏列表搜索 |
| `Ctrl+Shift+A` | 聚焦提醒列表搜索 |
| `1-4` | 在输入框未聚焦时触发快捷按钮 |
| `Tab` | 在搜索建议中切换选中项 |

### 12.4 批量操作

**现状**: 收藏和提醒只能逐个操作。
**方案**: 支持批量管理。

| 操作 | 说明 |
|------|------|
| 多选模式 | 侧边栏长按或点击"编辑"进入多选 |
| 批量删除 | 勾选多个收藏/提醒，一键删除 |
| 批量导出 | 导出收藏列表为文本/JSON |
| 全选/取消 | 快速全选或取消选择 |

### 12.5 游戏内私聊命令增强

**现状**: Agent 回复中包含 `/w 玩家名 ...` 格式的私聊命令，但无法直接操作。
**方案**: 检测回复中的私聊命令，渲染为可交互元素。

| 功能 | 说明 |
|------|------|
| 高亮显示 | 私聊命令渲染为带边框的代码块 |
| 一键复制 | 点击命令自动复制到剪贴板 |
| Toast 提示 | 复制成功后显示"已复制，粘贴到游戏聊天即可" |
| 批量复制 | 多个卖家时支持"复制全部" |

---

## Phase 13: 自定义物品别名系统

**目标**: 允许用户自定义物品别名，用自己熟悉的叫法查询物品价格。

### 13.1 需求背景

Warframe 物品名称复杂，玩家常用简称交流（如"充沛"指"充沛赋能/Arcane Energize"）。Agent 内置别名有限，用户第一次用简称查询失败后，需要一种方式让 Agent "记住"这个叫法。

### 13.2 后端实现

**文件**: `warframe_agent/web/app.py`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/aliases` | GET | 获取所有自定义别名列表（含 display 名称） |
| `/api/aliases` | POST | 添加自定义别名（name → item_id） |
| `/api/aliases` | DELETE | 删除自定义别名 |
| `/api/resolve/{name}` | GET | 解析物品名，失败时返回候选建议 |
| `/api/search_items?q=xxx` | GET | 模糊搜索物品名称，返回候选列表（含 item_id 和 display 名） |

**数据存储**: `data/custom_aliases.json`，格式为 `{"别名": "item_id"}`。

**注入机制**: 启动时和添加/删除别名后，调用 `inject_custom_aliases()` 将自定义别名注入到 `ItemResolver.aliases` 字典中，使 Agent 的解析链自动识别。

```python
def inject_custom_aliases() -> None:
    aliases = load_custom_aliases()
    for name, item_id in aliases.items():
        key = normalize_lookup_key(name)
        if key and item_id:
            chat_agent.resolver.aliases[key] = normalize_market_id(item_id)
```

### 13.3 前端实现

**别名管理面板**（模态框）：
- 入口：侧边栏 🏷️ 按钮 / 命令面板 "管理别名"
- 别名输入框：用户输入自己的叫法（如"充沛"）
- 物品搜索框：输入游戏内物品名称，实时搜索候选列表（调用 `/api/search_items`）
- 候选列表：显示物品中文名 + item_id，点击选中
- 确认区域：显示已选物品，可取消重选
- 确认绑定按钮：未选物品时禁用
- 列表：显示所有已绑定别名（别名 → 物品显示名），每条有删除按钮
- 预填充：从未找到引导点击"添加自定义别名"时，自动填入用户输入的名称

**物品未找到引导**（增强版）：
- 当 Agent 回复包含"没有找到/未找到"等关键词时，自动触发 `showItemNotFound(query)`
- 显示候选建议（从 `/api/resolve` 获取相似物品）
- 提示"如果是你熟悉的叫法，可以 [添加自定义别名]"
- 点击后打开别名管理面板，名称预填充

**命令面板集成**：
- 新增"管理别名"命令，`Ctrl+P` 输入"别名"即可快速打开

### 13.4 交互流程

```
用户输入 "充沛多少钱"
    ↓
Agent 解析失败，回复 "没有找到匹配的物品"
    ↓
前端检测到未找到关键词
    ↓
调用 /api/resolve/充沛，获取候选建议
    ↓
显示：未找到「充沛」
      你是不是想找：[arcane_energize]
      如果是你熟悉的叫法，可以 [添加自定义别名]
    ↓
用户点击 [添加自定义别名]
    ↓
打开别名管理面板，名称预填 "充沛"
用户在搜索框输入 "Arcane Energize" 或 "充沛赋能"
    ↓
前端调用 /api/search_items?q=Arcane+Energize
返回候选列表：[{display: "充沛赋能 / Arcane Energize", item_id: "arcane_energize"}]
    ↓
用户点击候选项，确认绑定
    ↓
POST /api/aliases {name: "充沛", item_id: "arcane_energize"}
注入到 resolver
    ↓
下次用户输入 "充沛"，Agent 直接识别为 arcane_energize
```

### 13.5 关键文件变更

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/app.py` | 别名 CRUD 端点、resolve 端点、search_items 搜索端点、启动注入 |
| 修改 | `warframe_agent/web/static/index.html` | 别名管理模态框 HTML、侧边栏按钮 |
| 修改 | `warframe_agent/web/static/js/chat.js` | 物品未找到检测、别名管理交互 |
| 修改 | `warframe_agent/web/static/js/app.js` | 别名 CSS 样式、命令面板集成 |
| 新增 | `data/custom_aliases.json` | 自定义别名持久化存储 |

---

## Phase 9-12 实施优先级

| 优先级 | Phase | 功能 | 理由 |
|--------|-------|------|------|
| P0 | 9.1 | 流式对话输出 | 核心体验，等待感最影响用户体验 |
| P0 | 9.5 | 物品未找到引导 | 减少用户挫败感 |
| P0 | 10.1 | 物品详情卡片 | 右侧面板空缺，信息展示不完整 |
| P1 | 9.2 | 对话历史持久化 | 刷新丢记录是常见痛点 |
| P1 | 9.3 | Markdown 渲染 | Agent 回复格式丢失影响可读性 |
| P1 | 10.2 | 图表时间范围 | 价格趋势分析的核心需求 |
| P1 | 11.1 | 主题切换 | 代码已就绪，工作量小收益大 |
| P2 | 9.4 | 消息操作菜单 | 提升操作效率 |
| P2 | 10.3 | 每日报告展示 | 复用已有后端逻辑 |
| P2 | 10.4 | 价格变动高亮 | 视觉增强 |
| P2 | 12.5 | 私聊命令增强 | 交易场景核心操作 |
| P3 | 11.2 | 通知设置面板 | 进阶用户需求 |
| P3 | 11.3 | 自定义快捷操作 | 个性化需求 |
| P3 | 12.1 | 命令面板 | 效率工具 |
| P3 | 12.2 | WebSocket 优化 | 稳定性提升 |
| P3 | 12.3 | 快捷键扩展 | 效率工具 |
| P3 | 12.4 | 批量操作 | 管理效率 |
| P3 | 11.4 | 布局偏好 | 个性化需求 |
| P1 | 13 | 自定义物品别名系统 | 解决简称查询失败的核心痛点 |

---

## 关键文件变更清单（Phase 9-12）

### 后端文件
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/app.py` | 流式 WebSocket、报告 API、历史范围参数、别名 CRUD、resolve 端点 |
| 修改 | `warframe_agent/chat.py` | 物品未找到时返回候选建议 |
| 修改 | `warframe_agent/price_history.py` | 支持时间范围查询聚合 |

### 前端文件
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/static/index.html` | 新增命令面板、设置面板、详情卡片 HTML |
| 修改 | `warframe_agent/web/static/js/app.js` | 主题切换、通知设置、命令面板 |
| 修改 | `warframe_agent/web/static/js/chat.js` | 流式输出、Markdown 渲染、消息操作 |
| 修改 | `warframe_agent/web/static/js/sidebar.js` | 批量操作、价格变动高亮 |
| 修改 | `warframe_agent/web/static/js/chart.js` | 时间范围切换、详情卡片渲染 |
| 新增 | `warframe_agent/web/static/js/markdown.js` | Markdown 渲染封装 |
| 新增 | `warframe_agent/web/static/js/command-palette.js` | 命令面板逻辑 |
| 修改 | `warframe_agent/web/static/css/style.css` | 新组件样式 |
| 修改 | `warframe_agent/web/static/css/variables.css` | 完善亮色主题变量 |

### 新增依赖
| 包 | 大小 | 用途 |
|------|------|------|
| marked.js (CDN) | ~40KB | Markdown 渲染 |
| DOMPurify (CDN) | ~15KB | HTML 净化防 XSS |
| howler.js (CDN) | ~10KB | 通知音效播放 |

---

## Phase 14: 交易效率工具（已实现）

**目标**: 为玩家提供更高效的交易决策和管理工具。

**实现日期**: 2026-05-02

### 14.1 杜卡特计算器 ✅

**功能**: 在物品详情卡片中显示杜卡特价值和效率分析，帮助玩家判断拆成杜卡特还是直接卖白金更划算。

**后端实现**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/ducats/{item_id}` | GET | 获取物品的杜卡特价值和效率分析 |
| `/api/ducats/batch` | POST | 批量获取物品的杜卡特价值 |

**核心函数**:
```python
def get_ducat_value(item_id: str) -> int | None:
    """获取物品的杜卡特价值"""
    # 静态映射 + 模式推断
    # Prime 部件: 45 ducats
    # 赋能 (Arcane): 100 ducats

def calculate_ducat_efficiency(platinum_price: int, ducat_value: int) -> dict:
    """计算杜卡特效率（每白金获得的杜卡特数）"""
    # 效率 ≥ 3: 建议拆成杜卡特
    # 效率 < 3: 建议直接卖白金
```

**前端显示**:
```
┌─────────────────────────────────────┐
│  ◆ 杜卡特分析                       │
│  ─────────────────────────────────  │
│  杜卡特价值        45 ducats        │
│  ─────────────────────────────────  │
│  杜卡特效率        3.0 ducats/p     │
│  ✓ 建议拆成杜卡特                   │
│  每白金获得 3.0 杜卡特 (高于3:1阈值) │
└─────────────────────────────────────┘
```

**判断逻辑**:
- 每白金 ≥ 3 杜卡特: 建议拆成杜卡特（绿色提示）
- 每白金 < 3 杜卡特: 建议直接卖白金（蓝色提示）

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/app.py` | 杜卡特计算函数、API 端点 |
| 修改 | `warframe_agent/web/static/js/chart.js` | 杜卡特信息渲染、CSS 样式 |
| 新增 | `data/ducat_values.json` | 杜卡特静态映射数据 |

---

### 14.2 批量查价 ✅

**功能**: 一次性查询多个物品价格，支持逗号或换行分隔，适合整理库存时使用。

**后端实现**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/batch_query` | POST | 批量查询物品价格（最多 10 个） |

**返回数据**:
```json
{
  "items": [
    {
      "name": "充沛赋能",
      "item_id": "arcane_energize",
      "sell_price": 45,
      "buy_price": 38,
      "seller": "Player1",
      "buyer": "Player2",
      "spread": 7,
      "ducat_value": 100,
      "ducat_efficiency": { "ducats_per_plat": 2.22, "recommendation": "sell" }
    }
  ],
  "total": 3,
  "success": 3
}
```

**前端交互**:
- 侧边栏新增"批量查价"快捷按钮
- 弹窗输入框支持多行输入（逗号、换行、空格分隔）
- 结果以 Markdown 格式显示，包含价格、卖家/买家、杜卡特信息

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/app.py` | batch_query 端点 |
| 修改 | `warframe_agent/web/static/js/chat.js` | handleBatchQuery 函数 |
| 修改 | `warframe_agent/web/static/index.html` | 批量查价按钮 |

---

### 14.3 交易历史记录 ✅

**功能**: 记录玩家实际完成的交易，用于统计和回溯。

**后端实现**:

**新增文件**: `warframe_agent/trade_history.py`

```python
@dataclass(frozen=True)
class TradeRecord:
    id: int
    item_id: str
    item_name: str
    trade_type: str  # "buy" or "sell"
    price: int
    player_name: str
    timestamp: str
    notes: str

class TradeHistoryDB:
    def add_trade(...) -> int
    def get_recent_trades(limit) -> list[TradeRecord]
    def get_trades_by_item(item_id) -> list[TradeRecord]
    def get_trade_stats() -> dict
    def delete_trade(trade_id) -> bool
```

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/trades` | GET | 获取最近的交易记录 |
| `/api/trades` | POST | 添加交易记录 |
| `/api/trades/{trade_id}` | DELETE | 删除交易记录 |
| `/api/trades/stats` | GET | 获取交易统计信息 |
| `/api/trades/item/{item_id}` | GET | 获取指定物品的交易记录 |

**前端显示**:
```
┌─────────────────────────────────────┐
│  交易历史                    [+ 记录] │
│  ─────────────────────────────────  │
│  总交易  买入  卖出  净收入           │
│    12     5     7    +156p          │
│  ─────────────────────────────────  │
│  📤 卖出  充沛赋能    45p           │
│     玩家: Player1  2026-05-01      │
│  ─────────────────────────────────  │
│  📥 买入  川流不息    28p           │
│     玩家: Player2  2026-04-28      │
└─────────────────────────────────────┘
```

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 新增 | `warframe_agent/trade_history.py` | 交易历史数据库模块 |
| 修改 | `warframe_agent/web/app.py` | 交易历史 API 端点 |
| 修改 | `warframe_agent/web/static/index.html` | 交易历史按钮 |
| 修改 | `warframe_agent/web/static/js/sidebar.js` | 交易历史前端逻辑、CSS 样式 |

---

### 14.4 套利检测 ✅

**功能**: 自动检测收藏物品的低买高卖机会，帮助玩家发现盈利机会。

**后端实现**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/arbitrage` | GET | 检测套利机会（支持 min_profit 参数） |
| `/api/arbitrage/scan` | GET | 从 watchlist 扫描套利机会 |

**判断逻辑**:
- 计算每个物品的最低卖价和最高收价
- 利润 = 最低卖价 - 最高收价
- 利润 ≥ 3p 的机会会被标记

**前端显示**:
```
┌─────────────────────────────────────┐
│  套利机会                           │
│  低买高卖的盈利机会                  │
│  ─────────────────────────────────  │
│  发现机会: 5    最低利润: 3p        │
│  ─────────────────────────────────  │
│  充沛赋能                    +7p    │
│  买入 38p (Player2) → 卖出 45p     │
│  杜卡特: 100 (2.22 ducats/p)       │
│  [复制买入私聊] [复制卖出私聊]      │
└─────────────────────────────────────┘
```

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/app.py` | 套利检测 API 端点 |
| 修改 | `warframe_agent/web/static/index.html` | 套利检测按钮 |
| 修改 | `warframe_agent/web/static/js/sidebar.js` | 套利检测前端逻辑、CSS 样式 |

---

### 14.5 收藏夹仪表盘 ✅

**功能**: 将所有收藏物品的价格变化汇总到一个仪表盘，提供总览视角。

**后端实现**:
- 复用 `/api/memory` 和 `/api/favorites_prices` 端点

**前端显示**:
```
┌─────────────────────────────────────┐
│  收藏夹仪表盘                       │
│  收藏物品价格概览                    │
│  ─────────────────────────────────  │
│  总价值      物品数    有价格        │
│  1,234p       12        10         │
│  ─────────────────────────────────  │
│  价格变动                           │
│  ▲ 上涨  ─ 持平  ▼ 下跌            │
│    3       5        2              │
│  ─────────────────────────────────  │
│  物品列表                           │
│  充沛赋能              45p ▲3      │
│  川流不息              29p ▼1      │
│  活力赋能              52p         │
│  ─────────────────────────────────  │
│  [导出数据] [刷新数据]              │
└─────────────────────────────────────┘
```

**功能特性**:
- 显示收藏物品总价值
- 统计价格变动（上涨/持平/下跌）
- 物品列表带价格变化指示器
- 支持一键导出数据

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/static/index.html` | 仪表盘按钮 |
| 修改 | `warframe_agent/web/static/js/sidebar.js` | 仪表盘前端逻辑、CSS 样式 |

---

### 14.6 私聊快捷复制增强 ✅

**功能**: 优化私聊命令的复制体验，确保一键复制功能正常工作。

**实现细节**:
- 物品详情卡片中的私聊按钮使用 `copyToClipboard()` 函数
- 私聊命令自动检测和高亮显示
- 复制成功后显示 Toast 提示

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/static/js/chart.js` | 优化 copyToClipboard 函数 |

---

### Phase 14 实施总结

| 功能 | 状态 | 后端 | 前端 | 数据 |
|------|------|------|------|------|
| 杜卡特计算器 | ✅ | 2 个端点 | 详情卡片增强 | 静态映射 |
| 批量查价 | ✅ | 1 个端点 | 快捷按钮 + 弹窗 | - |
| 交易历史 | ✅ | 5 个端点 | 侧边栏面板 | SQLite 新表 |
| 套利检测 | ✅ | 2 个端点 | 侧边栏面板 | - |
| 收藏仪表盘 | ✅ | 复用现有 | 侧边栏面板 | - |
| 私聊复制 | ✅ | 无改动 | 函数优化 | - |

**测试结果**: 102 个测试全部通过

**新增文件**:
- `warframe_agent/trade_history.py` - 交易历史数据库模块
- `data/ducat_values.json` - 杜卡特静态映射数据

**修改文件**:
- `warframe_agent/web/app.py` - 新增 10 个 API 端点
- `warframe_agent/web/static/index.html` - 新增 4 个侧边栏按钮
- `warframe_agent/web/static/js/chart.js` - 杜卡特信息渲染
- `warframe_agent/web/static/js/chat.js` - 批量查价功能
- `warframe_agent/web/static/js/sidebar.js` - 交易历史、套利、仪表盘

---

## Phase 15: 交互体验优化与 Bug 修复

**目标**: 修复关键 Bug，优化侧边栏布局，增强物品信息展示。

**实现日期**: 2026-05-02

### 15.1 修复收藏和提醒移除功能 ✅

**问题**: 收藏列表和价格提醒的移除功能无效，弹窗显示后点击确定无反应。

**根因**: `app.py` 中调用的 AgentMemory 方法名不匹配：
- `memory.remove_favorite()` → 应为 `memory.without_favorite_item()`
- `memory.add_alert()` → 应为 `memory.with_price_alert()`
- `memory.remove_alert()` → 应为 `memory.without_price_alert()`

**修复**:
```python
# 修复前（错误）
memory = memory.remove_favorite(request.item_id)
memory = memory.add_alert(alert)
memory = memory.remove_alert(alert)

# 修复后（正确）
memory = memory.without_favorite_item(request.item_id)
memory = memory.with_price_alert(request.item_id, request.direction, request.price)
memory = memory.without_price_alert(request.item_id, request.direction, request.price)
```

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/app.py` | 修复 3 个方法调用 |

---

### 15.2 侧边栏布局重新设计 ✅

**问题**: 侧边栏底部按钮过多（8个），显得拥挤。

**方案**: 将功能整合为 3 个主按钮 + 弹出菜单。

**新布局**:
```
┌─────────────────────────────┐
│  收藏列表            [✏️] [+] │
│  ─────────────────────────  │
│  收藏物品列表...              │
│  ─────────────────────────  │
│  价格提醒               [+]  │
│  ─────────────────────────  │
│  提醒列表...                 │
│  ─────────────────────────  │
│  定时关注               [+]  │
│  ─────────────────────────  │
│  关注列表...                 │
│  ─────────────────────────  │
│  [🌙] [☰] [⚙️]             │
│  ● 系统在线                  │
└─────────────────────────────┘
```

**更多功能菜单**（点击 ☰ 展开）:
- 📊 每日报告
- 📋 交易历史
- 💰 套利检测
- 📈 收藏仪表盘
- 🏷️ 自定义别名
- 🗑️ 清空对话

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/static/index.html` | 重构侧边栏 HTML、添加更多功能菜单 |
| 修改 | `warframe_agent/web/static/css/style.css` | 侧边栏按钮、菜单样式 |
| 修改 | `warframe_agent/web/static/js/app.js` | 菜单切换、模态框函数 |

---

### 15.3 自定义价格提醒（带备注）✅

**功能**: 用户可以自定义设置价格提醒，并添加备注信息。

**API 更新**:
```python
class AlertRequest(BaseModel):
    item_id: str
    direction: str
    price: int
    note: str = ""  # 新增备注字段
```

**前端交互**:
```
┌─────────────────────────────┐
│  添加价格提醒                 │
│  ─────────────────────────  │
│  物品名称                    │
│  [输入物品名称           ▼]  │
│  ─────────────────────────  │
│  提醒方向                    │
│  [低于目标价格时提醒      ▼]  │
│  ─────────────────────────  │
│  目标价格 (白金)              │
│  [输入价格              ]    │
│  ─────────────────────────  │
│  备注 (可选)                  │
│  [添加备注信息           ]    │
│  ─────────────────────────  │
│  [取消]  [添加提醒]           │
└─────────────────────────────┘
```

**侧边栏显示**:
```
┌─────────────────────────────┐
│  充沛赋能              📉    │
│  低于 45p 时提醒 - 充沛低于45提醒 │
│  [查价] [移除]               │
└─────────────────────────────┘
```

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/app.py` | AlertRequest 添加 note 字段 |
| 修改 | `warframe_agent/web/static/js/app.js` | addAlert 支持 note 参数 |
| 修改 | `warframe_agent/web/static/js/sidebar.js` | 显示备注信息 |

---

### 15.4 优化提醒列表显示 ✅

**问题**: 自定义价格提醒过多时影响观感。

**方案**: 添加"展开/收起"功能，默认显示 5 个提醒。

**实现**:
```javascript
const MAX_VISIBLE_ALERTS = 5;
let showAllAlerts = false;

function renderAlerts(alerts) {
    // 默认显示前 5 个
    const visibleAlerts = showAllAlerts ? alerts : alerts.slice(0, MAX_VISIBLE_ALERTS);

    // 渲染列表...

    // 添加展开/收起按钮
    if (alerts.length > MAX_VISIBLE_ALERTS) {
        const toggleBtn = document.createElement('div');
        toggleBtn.className = 'list-toggle';
        toggleBtn.innerHTML = `
            <button class="toggle-btn" onclick="toggleAlertsView()">
                ${showAllAlerts ? '收起' : `查看全部 (${alerts.length})`}
            </button>
        `;
        list.appendChild(toggleBtn);
    }
}
```

**CSS 样式**:
```css
.list-toggle {
    display: flex;
    justify-content: center;
    padding: 8px 0;
}

.toggle-btn {
    padding: 4px 12px;
    background: rgba(212, 167, 55, 0.1);
    border: 1px solid rgba(212, 167, 55, 0.2);
    border-radius: 3px;
    color: var(--gold-primary);
    font-size: 11px;
    cursor: pointer;
}
```

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/static/js/sidebar.js` | 添加展开/收起逻辑 |
| 修改 | `warframe_agent/web/static/css/style.css` | 添加 toggle 按钮样式 |

---

### 15.5 自定义关注与定时推送 ✅

**功能**: 用户可以添加自己想要长期关注的物品，支持自定义定时推送。

**数据模型**:
```python
@dataclass(frozen=True)
class WatchItem:
    item_id: str
    item_name: str
    frequency: str = "daily"  # daily, hourly, weekly
    time: str = "09:00"
    content: str = "top3_buyers"  # top3_sellers, top3_buyers, price_change, all
```

**API 端点**:
| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/watchlist` | GET | 获取关注列表 |
| `/api/watchlist` | POST | 添加关注项 |
| `/api/watchlist/{item_id}` | DELETE | 移除关注项 |

**前端交互**:
```
┌─────────────────────────────┐
│  添加定时关注                 │
│  ─────────────────────────  │
│  物品名称                    │
│  [输入物品名称           ▼]  │
│  ─────────────────────────  │
│  关注频率                    │
│  [每天                   ▼]  │
│  ─────────────────────────  │
│  推送时间                    │
│  [09:00                ]    │
│  ─────────────────────────  │
│  关注内容                    │
│  [前3个最高买家          ▼]  │
│  ─────────────────────────  │
│  [取消]  [添加关注]           │
└─────────────────────────────┘
```

**侧边栏显示**:
```
┌─────────────────────────────┐
│  充沛赋能              每天  │
│  09:00 | 前3买家              │
│  [移除]                      │
└─────────────────────────────┘
```

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/memory.py` | 添加 WatchItem 类、watchlist 字段 |
| 修改 | `warframe_agent/web/app.py` | watchlist API 端点 |
| 修改 | `warframe_agent/web/static/js/app.js` | 改用服务器端 API |
| 修改 | `tests/test_web_api.py` | 更新测试用例 |
| 修改 | `tests/test_chat_memory_integration.py` | 更新测试用例 |

---

### 15.6 赋能/Mod 等级显示 ✅

**功能**: 在物品详情卡片中显示赋能和 Mod 的等级信息。

**物品类型检测**:
```python
def get_item_type_info(item_id: str) -> dict | None:
    """获取物品类型和最大等级信息"""
    # 检查是否是赋能 (Arcane) - max_rank = 5
    # 检查是否是 Mod - max_rank = 10
```

**前端显示**:
```
┌─────────────────────────────┐
│  充沛赋能                    │
│  ⚡ 赋能  Rank 5/5           │
│  ─────────────────────────  │
│  卖价    收价    价差         │
│  45p     38p     7p         │
│  ─────────────────────────  │
│  📊 等级信息                  │
│  ─────────────────────────  │
│  类型        赋能             │
│  稀有度      传说             │
│  最大等级    5/5              │
│  ─────────────────────────  │
│  💡 赋能满级为 5/5，需要 6    │
│     个相同赋能融合            │
└─────────────────────────────┘
```

**Mod 显示**:
```
┌─────────────────────────────┐
│  活力                        │
│  🔧 Mod  Rank 10/10         │
│  ─────────────────────────  │
│  📊 等级信息                  │
│  ─────────────────────────  │
│  类型        Mod              │
│  稀有度      普通             │
│  最大等级    10/10            │
│  ─────────────────────────  │
│  💡 Mod 满级为 10/10，需要   │
│     消耗内融核心升级          │
└─────────────────────────────┘
```

**API 返回数据**:
```json
{
    "item_id": "arcane_energize",
    "item_type": "arcane",
    "item_type_display": "赋能",
    "max_rank": 5,
    "rarity": "LEGENDARY"
}
```

**关键文件变更**:
| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframe_agent/web/app.py` | get_item_type_info 函数、API 返回 |
| 修改 | `warframe_agent/web/static/js/chart.js` | 等级信息渲染、CSS 样式 |

---

### Phase 15 实施总结

| 功能 | 状态 | 后端 | 前端 | 说明 |
|------|------|------|------|------|
| 修复移除功能 | ✅ | 方法名修复 | - | 关键 Bug |
| 侧边栏重构 | ✅ | - | HTML/CSS/JS | 布局优化 |
| 价格提醒备注 | ✅ | note 字段 | 模态框 | 功能增强 |
| 提醒列表优化 | ✅ | - | 展开/收起 | 观感优化 |
| 自定义关注 | ✅ | watchlist API | 服务器端存储 | 新功能 |
| 等级显示 | ✅ | 类型检测 | 详情卡片 | 信息增强 |

**测试结果**: 102 个测试全部通过

**新增文件**:
- 无

**修改文件**:
- `warframe_agent/memory.py` - 添加 WatchItem 类
- `warframe_agent/web/app.py` - watchlist API、等级检测、Bug 修复
- `warframe_agent/web/static/index.html` - 侧边栏重构
- `warframe_agent/web/static/css/style.css` - 新增样式
- `warframe_agent/web/static/js/app.js` - 服务器端 watchlist
- `warframe_agent/web/static/js/sidebar.js` - 展开/收起、备注显示
- `warframe_agent/web/static/js/chart.js` - 等级信息渲染
- `tests/test_web_api.py` - 更新测试
- `tests/test_chat_memory_integration.py` - 更新测试

---

---

### Phase 16 — Bug 修复与数据源重构

**日期**: 2026-05-02
**重点**: 修复更多功能菜单点击失效、虚空裂隙加载失败、收藏删除后重启恢复等关键 Bug

#### 1. 菜单点击失效修复

**问题**: 更多功能菜单中除自定义别名外，所有功能点击无响应。

**根因**: `openDetailPanel`、`createChartLoading`、`createChartError`、`createChartEmpty` 四个核心函数定义在 `chart.js`（最后加载的脚本）。如果 `chart.js` 有任何运行时错误，这些函数不存在，导致所有功能失效。

**修复方案**: 将四个函数及关联 CSS 迁移到 `app.js`（最先加载）。

| 操作 | 文件 | 变更 |
|------|------|------|
| 新增 | `js/app.js` | `openDetailPanel()`、`createChartLoading()`、`createChartEmpty()`、`createChartError()` + CSS 注入 |
| 移除 | `js/chart.js` | 删除重复定义 |
| 修改 | `js/sidebar.js` | 所有菜单处理器添加 `toggleMoreMenu()` 调用 |
| 修改 | `js/chart.js` | report 按钮添加 try-catch |
| 修改 | `js/chat.js` | alias/clear-chat 添加 `toggleMoreMenu()` |

#### 2. 虚空裂隙 API 重写

**问题**: `https://api.warframestat.us/pc/fissures` 被 Cloudflare 拦截。

**修复**: 改用本地 `data/relics_drop_data.json`（来自 WFCD/warframe-drop-data 仓库，3014 条遗物数据），按 tier 分组并显示稀有/非常规掉落物及掉落概率。

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `web/app.py` | `/api/fissures` 端点重写 |
| 修改 | `js/sidebar.js` | 前端适配新数据格式（rare_drops/uncommon_drops 数组） |
| 新增 | `data/relics_drop_data.json` | 3014 条遗物掉落表 |
| 新增 | `data/relics_list.json` | 690 个遗物名称（从 warframetools Flutter 项目提取） |

#### 3. 其他 Bug 修复

| Bug | 文件 | 修复 |
|-----|------|------|
| `config is not defined` | `web/app.py` | 添加 `from .. import config` |
| 收藏删除后重启恢复 | `web/app.py` | 添加 `NoCacheAPIMiddleware` 禁止 API 缓存 |
| 全局错误未捕获 | `index.html` | 添加 `window.onerror` + `unhandledrejection` 处理器 |
| 价格异常逻辑 | `web/app.py` | 仅检查收藏列表中的物品 |

#### 4. GitHub 项目参考

| 仓库 | 用途 |
|------|------|
| `githubProduct/warframe-drop-data/` | 遗物掉落表数据源 |
| `githubProduct/warframe-items/` | 物品综合数据参考 |

**测试结果**: 102 个测试全部通过

---

### Phase 17 — 新增数据浏览功能

**日期**: 2026-05-02
**重点**: 基于 warframe-items 本地数据新增 3 个百科类功能

#### 1. 装备百科（Warframe / 武器浏览器）

浏览所有 Warframe 和武器的基础属性、技能信息。

- **Warframe 浏览**: 118 个战甲，显示生命/护盾/护甲/能量/冲刺速度/段位需求/被动/技能
- **武器浏览**: 主武器(193)、副武器、近战武器，显示总伤害/暴击率/暴击倍率/触发率/射速/弹匣/装填
- **搜索过滤**: 支持名称搜索
- **详情页面**: 点击卡片展开完整属性

| 操作 | 文件 | 变更 |
|------|------|------|
| 新增 | `web/app.py` | `GET /api/wiki/warframes`, `GET /api/wiki/weapons` |
| 修改 | `js/sidebar.js` | `showWikiWarframes()`, `showWikiWeapons()`, 详情函数 |
| 修改 | `css/style.css` | wiki-card, wiki-grid, wiki-detail 样式 |
| 修改 | `index.html` | 菜单按钮 |

#### 2. MOD 数据库

搜索和过滤 1801 个 MOD，支持按极性、稀有度、类型过滤。

- **搜索**: 名称模糊搜索
- **过滤器**: 极性(Madurai/Vazarin/Naramon/Zenurik/Penjaga/Umbra)、稀有度(Common/Uncommon/Rare/Legendary/Peculiar)
- **详情页**: 显示类型、极性、容量消耗、兼容性、是否强化MOD、是否可交易

| 操作 | 文件 | 变更 |
|------|------|------|
| 新增 | `web/app.py` | `GET /api/wiki/mods` |
| 修改 | `js/sidebar.js` | `showWikiMods()`, `searchWikiMods()`, `showWikiModDetail()` |

#### 3. 遗物搜索

根据物品名称搜索掉落该物品的所有遗物，显示稀有度和掉落概率。

- **数据源**: `data/relics_drop_data.json`（3014 条遗物数据）
- **搜索**: 物品名称模糊匹配
- **排序**: 按稀有度（Rare > Uncommon > Common）+ 遗物名称
- **显示**: 遗物名称、物品名、稀有度、掉落概率

| 操作 | 文件 | 变更 |
|------|------|------|
| 新增 | `web/app.py` | `GET /api/relic/search` |
| 修改 | `js/sidebar.js` | `showRelicSearch()` |
| 修改 | `index.html` | 遗物搜索菜单按钮 |

#### 4. 菜单优化

将价格异常和虚空裂隙从动态插入改为静态 HTML 按钮，减少 JS 运行时依赖。

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `index.html` | 添加 fissure-btn, anomaly-btn 静态按钮 |
| 修改 | `js/sidebar.js` | 移除动态 createElement，改用事件绑定 |

**测试结果**: 102 个测试全部通过

---

### Phase 18 — 中文化与 warframe.market 链接

**日期**: 2026-05-02
**重点**: 全面中文化 + 交易跳转链接

#### 1. 遗物搜索中文化

- Tier 名称：Lith→古纪、Meso→前纪、Neo→中纪、Axi→后纪、Requiem→安魂
- 稀有度：Rare→稀有、Uncommon→非常规、Common→常规

#### 2. MOD/装备中文名

- 从 `data/export/ExportWarframes_zh.json`、`ExportWeapons_zh.json`、`ExportUpgrades_zh.json` 加载中文名映射
- 列表和详情页显示格式：`中文名（English Name）`
- 支持中文名搜索过滤

#### 3. warframe.market 交易链接

- 所有物品详情页添加 "在 warframe.market 查看交易 →" 链接
- URL 格式：`https://warframe.market/items/{url_name}`

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `web/app.py` | 新增 `_load_zh_names()`、`_market_url()`，三个 wiki 端点添加 `nameZh`/`marketUrl` 字段，遗物端点添加中文 tier 和稀有度 |
| 修改 | `js/sidebar.js` | 列表/详情显示中文名，添加市场链接 |
| 修改 | `css/style.css` | `.wiki-market-link` 样式 |

**测试结果**: 102 个测试全部通过

### Phase 19 — 详情面板关闭按钮修复

**日期**: 2026-05-03
**重点**: 修复详情面板关闭按钮点击无响应的 Bug

#### 问题

详情面板（装备百科、MOD 数据库、遗物搜索等）打开后，右上角关闭按钮点击无响应。

#### 根因

1. **DOM 层级问题**: `#detail-content` 在 DOM 中位于关闭按钮之后，渲染的内容覆盖了绝对定位的按钮
2. **事件绑定位置**: 关闭按钮 handler 定义在 `chart.js`（最后加载），若 chart.js 有运行时错误则 handler 不会绑定

#### 修复方案

**HTML 结构重构**:
```
旧: aside > button.close-btn + div.panel-header + div#detail-content
新: aside > div.detail-panel-header(button.close-btn + div.panel-header) + div.detail-panel-body#detail-content
```

- 关闭按钮移入固定头部区域，与滚动内容物理分离
- 面板改为 `display: flex; flex-direction: column`，头部 `flex-shrink: 0`，内容区 `flex: 1; overflow-y: auto`

**事件绑定迁移**: 关闭按钮 handler 从 `chart.js` 迁移到 `app.js`（最先加载），确保始终可用

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `index.html` | 详情面板结构重构，关闭按钮移入 `.detail-panel-header` |
| 修改 | `css/style.css` | 面板改为 flex 布局，关闭按钮改为 flex 子元素，新增 `.panel-header h2` 样式 |
| 修改 | `css/responsive.css` | 移动端/平板 padding 改为作用于子元素 |
| 修改 | `js/app.js` | 新增 `close-detail` 按钮事件监听 |
| 修改 | `js/chart.js` | 移除 `close-detail` 事件监听（已迁移至 app.js） |

**文档版本**：v3.8
**最后更新**：2026-05-03
**维护者**：Claude (Frontend Design Specialist)

### Phase 20 — Prime 物品 Market 链接优化

**日期**: 2026-05-03
**重点**: Prime 战甲/武器的 market 链接指向蓝图，新增部件交易列表

#### 背景

在 warframe.market 上，Prime 战甲和武器只能以部件形式交易（Blueprint、Chassis、Neuroptics、Systems 等），不能直接交易成品。原有实现用物品名直接生成链接（如 `rhino_prime`），该链接在 market 上不存在。

#### 改动内容

**1. 新增 `_market_url_prime_blueprint()` 函数**

为 Prime 物品生成蓝图链接：`Mirage Prime` → `https://warframe.market/items/mirage_prime_blueprint`

**2. 新增 `_extract_components()` 函数**

从 Prime 物品的 `components` 数组提取可交易部件（过滤掉 Orokin Cell 等资源），返回部件名称、可交易状态、杜卡特值。

**3. 战甲/武器端点改造**

- Prime 物品：`marketUrl` 指向蓝图页面，新增 `components` 字段（含 Blueprint、Chassis、Neuroptics、Systems 等）
- 非 Prime 物品：行为不变，`components` 为空数组
- 武器端点新增 `isPrime` 字段

**4. 前端详情页**

- Prime 物品显示"在 warframe.market 查看蓝图交易 →"
- 新增"Prime 部件交易"区块，每个部件可点击跳转 market 对应页面
- 部件显示杜卡特值（◆ 标记）
- 部件链接逻辑：`marketUrl.replace('_blueprint', '_{component_name}')`

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `web/app.py` | 新增 `_market_url_prime_blueprint()`、`_extract_components()`，战甲/武器端点增加 `components` 字段和 Prime 蓝图链接 |
| 修改 | `js/sidebar.js` | `showWikiWarframeDetail()`、`showWikiWeaponDetail()` 增加部件交易列表渲染 |
| 修改 | `css/style.css` | 新增 `.wiki-comp-link`、`.wiki-comp-name`、`.wiki-comp-ducats` 样式 |

**示例**:

| 物品 | marketUrl | 部件数 |
|------|-----------|--------|
| Mirage Prime | `.../mirage_prime_blueprint` | 4 (Blueprint/Chassis/Neuroptics/Systems) |
| Acceltra Prime | `.../acceltra_prime_blueprint` | 4 (Blueprint/Barrel/Receiver/Stock) |
| Rhino | `.../rhino` | 0（非 Prime，无变化） |

**文档版本**：v3.9
**最后更新**：2026-05-03
**维护者**：Claude (Frontend Design Specialist)

---

## 个人智能体升级（Phase 21-25）

> 以下 5 个阶段将项目从"领域专用智能助手"升级为真正的"个人智能体"，补齐多轮对话、行为学习、主动智能、语义理解、推理规划五大能力。

---

### Phase 21 — 多轮对话

**日期**: 2026-05-03
**目标**: session history 传入 LLM，支持上下文连贯的多轮对话

#### 改动内容

**1. config.py** — 新增对话窗口配置
- `CONTEXT_WINDOW = 6` — LLM 上下文中包含的最近对话轮数
- `MAX_HISTORY_MESSAGES = 20` — session 存储的消息硬上限

**2. session.py** — 新增 `to_messages()` 方法
将 `history` 列表转为 Ollama messages 格式 `[{"role": "user"/"assistant", "content": ...}]`，支持 limit 参数截取最近 N 轮。

**3. llm.py** — 新增 `chat_with_ollama()` 函数
调用 `ollama.chat(messages=...)` 多轮对话 API，替代原有的 `ollama.generate(prompt)` 单轮调用。

**4. chat.py** — 核心重构
- 新增 `build_system_prompt()` — 构建 system 消息（persona + 记忆 + 告警）
- 新增 `build_chat_messages()` — 构建完整 messages 数组（system + history + user）
- `ChatAgent._call_llm_messages()` — 优先使用 `chat_with_ollama()`，注入 `model_call` 时回退到旧方式
- `answer()` 改用 messages 格式调用 LLM

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `config.py` | 新增 CONTEXT_WINDOW、MAX_HISTORY_MESSAGES |
| 修改 | `session.py` | 新增 to_messages() |
| 修改 | `llm.py` | 新增 chat_with_ollama() |
| 修改 | `chat.py` | build_system_prompt()、build_chat_messages()、_call_llm_messages() |
| 新增 | `tests/test_multiturn.py` | 9 个测试用例 |

**测试结果**: 111 个测试全部通过

---

### Phase 22 — 行为学习（用户画像）

**日期**: 2026-05-03
**目标**: 分析 common_questions 构建用户画像，注入 LLM 上下文实现个性化回答

#### 改动内容

**1. memory.py** — 新增 `UserProfile` 数据类

```python
@dataclass(frozen=True)
class UserProfile:
    preferred_trade_type: str    # buy, sell, neutral
    queried_items: dict[str, int]  # 物品查询频次
    favorite_categories: list[str]  # 偏好分类：arcane/prime_set/prime_part/mod
    total_queries: int
```

- `from_questions(questions)` — 纯关键词频率分析，无需 ML
- 分析逻辑：BUY_KEYWORDS/SELL_KEYWORDS 统计偏好，CATEGORY_KEYWORDS 识别分类

**2. AgentMemory 扩展**
- 新增 `user_profile` 字段
- `analyze_and_update_profile()` — 根据 common_questions 重新分析画像
- `load()`/`to_dict()` 支持画像序列化

**3. chat.py 集成**
- `_remember_common_question()` 每 5 个问题触发画像分析
- `_memory_prompt()` 注入画像摘要：`用户画像: 偏好购买，偏好分类: arcane，累计查询 12 次`
- `_render_memory_summary()` 显示画像信息

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `memory.py` | 新增 UserProfile、关键词常量、analyze_and_update_profile() |
| 修改 | `chat.py` | 画像分析触发、画像注入 LLM 上下文 |
| 修改 | `tests/test_memory.py` | 7 个新测试用例 |

**测试结果**: 118 个测试全部通过

---

### Phase 23 — 主动智能（趋势监控）

**日期**: 2026-05-03
**目标**: 使用 price_history 趋势数据检测异常波动，Agent 主动给出建议

#### 改动内容

**1. config.py** — 新增监控阈值
- `TREND_THRESHOLD_PERCENT = 15` — 趋势变化百分比阈值
- `ANOMALY_THRESHOLD_PERCENT = 30` — 异常变化百分比阈值（触发建议）
- `PROACTIVE_SUGGESTION_LIMIT = 5` — 注入 LLM 的建议条数

**2. price_history.py** — 新增趋势分析方法
- `rolling_average(item_id, window)` — 计算滚动均价
- `detect_anomaly(item_id, threshold_pct)` — 检测价格异常波动，返回 `{direction, deviation_pct, current, average}`

**3. memory.py** — 新增 `ProactiveSuggestion` 数据类

```python
@dataclass(frozen=True)
class ProactiveSuggestion:
    item_id: str
    suggestion_type: str  # anomaly, trend, opportunity
    priority: int         # 1=critical, 2=important, 3=info
    message: str
    timestamp: str
```

- `AgentMemory.with_suggestion()` — 追加建议（保留最近 20 条）

**4. monitor.py** — 增强扫描逻辑
- `PriceMonitor.__init__()` 新增 `price_db` 参数
- `scan_once()` 新增：WatchItem 扫描、价格记录、异常检测、建议生成
- `_run()` 扫描后自动持久化建议到 memory

**5. main.py** — 将 `price_db` 注入 `PriceMonitor`

**6. chat.py** — 建议注入
- `_memory_prompt()` 注入最近 5 条智能建议到 LLM 上下文
- `_render_memory_summary()` 显示最近建议

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `config.py` | 新增 TREND/ANOMALY 阈值、SUGGESTION_LIMIT |
| 修改 | `price_history.py` | rolling_average()、detect_anomaly() |
| 修改 | `memory.py` | ProactiveSuggestion、with_suggestion() |
| 修改 | `monitor.py` | price_db 参数、WatchItem 扫描、异常检测 |
| 修改 | `main.py` | 注入 price_db |
| 修改 | `chat.py` | 建议注入 LLM 上下文和 /memory 命令 |
| 修改 | `tests/test_price_history.py` | 6 个新测试用例 |
| 修改 | `tests/test_monitor.py` | 2 个新测试用例 |

**测试结果**: 126 个测试全部通过

---

### Phase 24 — 语义 RAG（向量搜索）

**日期**: 2026-05-03
**目标**: 用 embedding 替代字符 n-gram，实现语义匹配（如"回蓝的赋能"→ arcane_energize）

#### 改动内容

**1. config.py** — 新增 embedding 配置
- `EMBEDDING_MODEL = "nomic-embed-text"` — Ollama embedding 模型
- `EMBEDDING_CACHE_PATH = data/rag_embeddings.npz` — 预计算缓存
- `EMBEDDING_ENABLED = True` — 开关

**2. rag.py** — 新增 `SemanticRAG` 类

```python
class SemanticRAG:
    def __init__(self, cache_path)
    def is_available(self) -> bool
    def search(self, query, limit) -> list[RagResult]
```

- 加载预计算的 embedding 缓存（item_ids + texts + embeddings 矩阵）
- 查询时 embed query → cosine similarity → top-k
- 无缓存时自动回退到 n-gram

新增 `smart_search_rag()` 函数：先语义搜索，无结果时回退 n-gram。

**3. tools/build_embeddings.py** — 离线预计算脚本
- 读取 `data/rag_items.jsonl`
- 调用 `ollama.embeddings(model=EMBEDDING_MODEL)` 逐条计算
- 保存为 `data/rag_embeddings.npz`（numpy 压缩格式）

**4. chat.py** — `_default_rag_search` 改用 `smart_search_rag()`

**5. requirements.txt** — 新增 `numpy>=1.24.0`

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `config.py` | EMBEDDING_MODEL、EMBEDDING_CACHE_PATH、EMBEDDING_ENABLED |
| 修改 | `rag.py` | SemanticRAG 类、_embed_text()、_cosine_similarity()、smart_search_rag() |
| 新增 | `tools/build_embeddings.py` | 离线 embedding 预计算脚本 |
| 修改 | `chat.py` | _default_rag_search 改用 smart_search_rag |
| 修改 | `requirements.txt` | numpy>=1.24.0 |
| 修改 | `tests/test_rag.py` | 6 个新测试用例 |

**测试结果**: 132 个测试全部通过

---

### Phase 25 — 推理规划（ReAct 循环）

**日期**: 2026-05-03
**目标**: 多步任务分解，支持链式工具调用（如"我有50p买什么赋能倒卖最赚"→ 查询多个赋能价格 → 对比 → 推荐）

#### 改动内容

**1. config.py** — 新增推理配置
- `MAX_TOOL_ITERATIONS = 3` — ReAct 循环最大轮数
- `REACT_MODEL = "qwen3:8b"` — 推理模型

**2. tool_router.py** — 新增 Ollama 原生工具格式

`TOOL_SCHEMAS` — 6 个工具的 JSON Schema 定义（Ollama function calling 格式）：
- query_price / query_set / query_missing_parts / scan_favorites / set_alert / price_trend

`react_loop()` 函数：
```
messages → LLM → tool_calls? → 执行 → 结果回传 → LLM → ... → 最终回答
```
- 支持多步推理（最多 3 轮）
- `_extract_tool_calls()` 解析 JSON 和数组格式的工具调用
- 旧 `parse_tool_call()` + `build_router_prompt()` 保留为回退

**3. chat.py** — 路由重构
- `_try_router()` 改为：先 `_try_react_loop()`，失败回退 `_try_router_legacy()`
- `_react_model_call()` — 支持注入 router_call 或 model_call
- `_execute_tool_call()` 新增 `query_missing_parts` handler
- `_query_missing_parts()` — 计算补齐 Prime 套装还需多少钱

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `config.py` | MAX_TOOL_ITERATIONS、REACT_MODEL |
| 修改 | `tool_router.py` | TOOL_SCHEMAS、react_loop()、_extract_tool_calls() |
| 修改 | `chat.py` | _try_react_loop()、_react_model_call()、_try_router_legacy()、query_missing_parts |
| 修改 | `tests/test_session_context.py` | 更新断言适配新路由行为 |
| 新增 | `tests/test_router.py` | 13 个测试用例 |

**测试结果**: 145 个测试全部通过

---

### 个人智能体升级总结

| Phase | 名称 | 核心能力 | 新增测试 |
|-------|------|----------|----------|
| 21 | 多轮对话 | session → messages API，上下文连贯 | +9 |
| 22 | 行为学习 | UserProfile 关键词画像，个性化回答 | +7 |
| 23 | 主动智能 | 异常检测 + ProactiveSuggestion，主动建议 | +8 |
| 24 | 语义 RAG | SemanticRAG embedding 余弦相似度搜索 | +6 |
| 25 | ReAct 循环 | react_loop 多步推理 + 原生工具调用 | +13 |

**测试**: 102 → 145（+43 新测试）→ 169（+24 新测试）

**新增配置**:

| 配置项 | 值 | 用途 |
|--------|-----|------|
| CONTEXT_WINDOW | 6 | 多轮对话上下文轮数 |
| MAX_HISTORY_MESSAGES | 20 | session 消息硬上限 |
| TREND_THRESHOLD_PERCENT | 15 | 趋势变化阈值 |
| ANOMALY_THRESHOLD_PERCENT | 30 | 异常检测阈值 |
| PROACTIVE_SUGGESTION_LIMIT | 5 | 注入 LLM 的建议条数 |
| EMBEDDING_MODEL | nomic-embed-text | 语义搜索模型 |
| EMBEDDING_ENABLED | True | 启用语义搜索 |
| MAX_TOOL_ITERATIONS | 3 | ReAct 最大循环轮数 |
| REACT_MODEL | qwen3:8b | 推理模型 |

**新增文件**:

| 文件 | 用途 |
|------|------|
| `tools/build_embeddings.py` | 离线 embedding 预计算脚本 |
| `tests/test_multiturn.py` | 多轮对话测试 |
| `tests/test_router.py` | ReAct 循环测试 |

**修改文件**:

| 文件 | 变更 |
|------|------|
| `config.py` | 新增 9 个配置项 |
| `session.py` | to_messages() |
| `llm.py` | chat_with_ollama() |
| `chat.py` | build_system_prompt()、build_chat_messages()、_call_llm_messages()、_try_react_loop()、_query_missing_parts()、画像分析、建议注入 |
| `memory.py` | UserProfile、ProactiveSuggestion、analyze_and_update_profile()、with_suggestion() |
| `price_history.py` | rolling_average()、detect_anomaly() |
| `monitor.py` | price_db 参数、WatchItem 扫描、异常检测 |
| `tool_router.py` | TOOL_SCHEMAS、react_loop() |
| `rag.py` | SemanticRAG、smart_search_rag() |
| `main.py` | 注入 price_db 到 PriceMonitor |
| `requirements.txt` | numpy>=1.24.0 |
| `tests/test_memory.py` | +7 测试 |
| `tests/test_price_history.py` | +6 测试 |
| `tests/test_monitor.py` | +2 测试 |
| `tests/test_rag.py` | +6 测试 |
| `tests/test_session_context.py` | 更新断言 |

**文档版本**：v4.0
**最后更新**：2026-05-03
**维护者**：Claude (Full-Stack Agent Developer)

---

### Phase 26 — 遗物来源查询与 Bug 修复

**日期**: 2026-05-04
**重点**: 虚空遗物掉落来源查询、前端 Bug 修复、代码质量改进

#### 1. 遗物来源查询

**功能**: 在虚空裂缝面板中点击遗物，显示该遗物的掉落来源（星球、任务节点、轮次、掉落概率）和精炼等级切换。

**数据来源**: 从 `githubProduct/warframe-drop-data/data/missionRewards.json` 处理提取，生成 `data/relic_sources.json`（62 个遗物，每个含多个掉落来源）。

**后端实现**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/relic/sources/{relic_name}` | GET | 获取遗物的掉落来源（星球+节点+轮次+概率） |
| `/api/relic/drops/{tier}/{relic_name}` | GET | 获取遗物详细掉落表（4 种精炼等级） |

**前端实现**:
- `loadRelicSources()` — 获取来源数据，按星球分组显示
- `switchRelicState()` — 精炼等级切换（完整/卓越/无瑕/光辉）
- 遗物详情面板：掉落表 + 来源列表双 Tab 切换

| 操作 | 文件 | 变更 |
|------|------|------|
| 新增 | `data/relic_sources.json` | 62 个遗物的掉落来源数据 |
| 新增 | `data/relics_detailed/` | 758 个遗物详细掉落 JSON |
| 修改 | `web/app.py` | 新增 2 个 API 端点 |
| 修改 | `js/sidebar.js` | 遗物来源展示 + 精炼等级切换 |

#### 2. showPriceChart 未定义修复

**问题**: 点击裂隙追踪面板中的任务项，控制台报 `showPriceChart is not defined`。

**根因**: `showPriceChart` 定义在 `chart.js`（最后加载的脚本），inline onclick handler 无法保证找到该函数。

**修复**:
- `chart.js`: 添加 `window.showPriceChart = showPriceChart;` 显式暴露到全局
- `sidebar.js`: 移除 `showFissureTracker()` 中裂隙任务项的错误 onclick（裂隙任务不是市场物品）

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `js/chart.js` | 添加 window.showPriceChart 全局暴露 |
| 修改 | `js/sidebar.js` | 移除裂隙任务的错误 onclick |

#### 3. FastAPI lifespan 迁移

**变更**: 将 deprecated `@app.on_event("startup")` / `@app.on_event("shutdown")` 迁移到 `lifespan` 上下文管理器。

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    inject_custom_aliases()
    setup_monitor()
    yield
    monitor.stop()

app = FastAPI(title="Warframe Trading Agent API", lifespan=lifespan)
```

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `web/app.py` | on_event → lifespan 模式 |

#### 4. requirements.txt 补全

**问题**: 缺少 `playwright`、`httpx`、`pydantic` 依赖声明。

**修复**: 添加 `httpx>=0.28.0`、`pydantic>=2.0.0`、`playwright>=1.40.0`。

**测试结果**: 145 个测试全部通过

---

### Phase 27 — 全面代码审查与修复

**目标**: 对整个项目进行全面审查，发现并修复 21 个问题（HIGH 3 / MEDIUM 10 / LOW 8）。

#### 1. HIGH 优先级修复

| 问题 | 文件 | 修复 |
|------|------|------|
| `toggleMoreMenu` 空指针 | `app.js` | 添加 null 检查 |
| chat.js DOM 引用安全性 | `chat.js` | 验证 script 在 `</body>` 前加载，DOM 已就绪 |
| `setup_monitor` 异常时 lifespan | `app.py` | 添加 try/except 保护 shutdown |

#### 2. MEDIUM 优先级修复

| 问题 | 文件 | 修复 |
|------|------|------|
| 重复 report-btn 绑定 | `chart.js` | 移除 chart.js 中的重复绑定 |
| `showPriceAnomalies` 重复定义 | `sidebar.js` | 移除第一个死代码定义 |
| `renderFavorites`/`renderAlerts` 空指针 | `sidebar.js` | 添加 null 检查 |
| XSS: inline onclick 注入 | `chart.js`, `sidebar.js` | 使用 `JSON.stringify()` 转义 |
| 死代码 `_ducat_cache` | `app.py` | 删除未使用的变量 |
| 未使用的 `getHistory` | `app.js` | 删除 |
| 未使用的 `createEmptyState` | `sidebar.js` | 删除 |
| `getHistoryWithRange` 缺 try/catch | `chart.js` | 添加异常处理 |
| report copy 模板注入 | `sidebar.js` | 改用 addEventListener |

#### 3. LOW 优先级修复

| 问题 | 文件 | 修复 |
|------|------|------|
| `asyncio.get_event_loop()` 已废弃 | `app.py` | 改为 `asyncio.get_running_loop()` |
| `get_item_type_info` 重复读文件 | `app.py` | 添加 `_export_file_cache` 文件级缓存 |
| `ws_connections` 迭代安全 | `app.py` | 迭代前拷贝列表 |
| Pydantic 请求模型缺失 | `app.py` | 添加 `ItemListRequest`、`AliasRequest`、`AliasDeleteRequest` |

#### 4. Pydantic 请求模型

为以下端点添加类型化请求模型：
- `/api/compare` — `ItemListRequest`（items 列表，限制 3 个）
- `/api/batch_query` — `ItemListRequest`（items 列表，限制 10 个）
- `/api/ducats/batch` — `ItemListRequest`（items 列表，限制 10 个）
- `/api/aliases` POST — `AliasRequest`（name + item_id）
- `/api/aliases` DELETE — `AliasDeleteRequest`（name）

#### 5. 测试补充

新增 24 个测试：
- `tests/test_trade_history.py`（10 个）— TradeHistoryDB 完整覆盖
- `tests/test_web_api.py` 新增（14 个）— watchlist、trades、suggest、aliases API

| 指标 | 修改前 | 修改后 |
|------|--------|--------|
| 测试用例数 | 145 | 169 |

**测试结果**: 169 个测试全部通过

---

### Phase 28 — 同步文件 I/O 阻塞事件循环修复（M10）

**目标**: 消除 async 端点中的同步文件 I/O，避免阻塞事件循环。

#### 问题分析

经审查发现 `app.py` 中有 **35+ 处同步文件 I/O 调用**分布在 **25 个 async 端点**中：

| 类别 | 数量 | 说明 |
|------|------|------|
| AgentMemory.load()/save() | 14 端点，~22 次 | 最频繁，每次请求读写磁盘 |
| 大文件直接读取 | 5 端点 | relics_drop_data.json（数百 KB）等 |
| 缓存辅助函数 | 6 端点 | 首次加载大文件，后续缓存命中 |
| 别名文件 | 3 端点 | custom_aliases.json |

#### 修复方案

**策略 1: 启动预热** — 在 `lifespan` 中用 `asyncio.gather` + `asyncio.to_thread` 并行预热所有缓存：
- `_load_export_file()` — ExportRelicArcane_en.json, ExportUpgrades_en.json
- `_load_wiki_json()` — Warframes.json, Weapons.json, Mods.json
- `_load_zh_names()` — Warframes, Weapons, Upgrades
- `_preload_relic_drop_data()` — relics_drop_data.json（新增模块级缓存）
- `_load_relic_vault_status()` — relic_vault_status.json
- `_load_relic_sources()` — relic_sources.json（新增模块级缓存）

**策略 2: 模块级缓存** — 为 `relics_drop_data.json` 和 `relic_sources.json` 添加 `_relic_drop_data_cache` / `_relic_sources_cache`，在 lifespan 中预热，端点直接从缓存读取。

**策略 3: asyncio.to_thread 包装** — 创建 `_load_memory_async()` / `_save_memory_async()` 替换 14 个端点中的 `AgentMemory.load()` / `memory.save()`。

**策略 4: asyncio.to_thread 包装** — 对 `/api/fissures/relics`、`/api/relic/drops` 详细 JSON、`/api/aliases` 的 `load_custom_aliases()` / `save_custom_aliases()` 使用 `asyncio.to_thread()`。

#### 修改的端点（21 个）

| 端点 | 策略 |
|------|------|
| GET /api/memory, POST/DELETE /api/fav, POST/DELETE /api/alert, GET/POST/DELETE /api/watchlist, POST /api/pref, GET /api/price/anomalies, GET /api/favorites_prices, GET /api/report, GET /api/arbitrage | 策略 3: async memory |
| GET /api/fissures, GET /api/relic/search, GET /api/relic/drops (fallback) | 策略 2: 模块级缓存 |
| GET /api/fissures/relics, GET /api/relic/drops (detailed) | 策略 4: to_thread |
| GET /api/relic/sources | 策略 2: 模块级缓存 |
| GET/POST/DELETE /api/aliases | 策略 4: to_thread |
| lifespan | 策略 1: 预热 |

| 指标 | 修改前 | 修改后 |
|------|--------|--------|
| 同步 I/O 调用点 | 35+ | 0（全部异步化） |

**测试结果**: 169 个测试全部通过

---

### Phase 29 — UI 动画增强与功能借鉴

**目标**: 借鉴 GitHub 和大厂网页的动画效果，在已有 Tenno 科技终端风格基础上增强视觉体验。

#### 1. 纯 CSS 增强（零依赖）

| 效果 | 文件 | 说明 |
|------|------|------|
| CRT 扫描线叠加层 | `animations.css` | 经典终端扫描线效果，body 添加 `scanlines` 类 |
| 角落括号装饰 | `animations.css` + `style.css` | 模态框添加金色角落边框装饰 |
| 增强文字辉光 | `style.css` | 标题 "Warframe 交易助手" 添加多层金色 text-shadow |
| 全息微光效果 | `animations.css` + `style.css` | 侧边栏标题栏添加流动渐变微光背景 |
| Glitch 效果 | `animations.css` | 用于错误状态或数据更新时的视觉提示 |
| 主题切换过渡 | `animations.css` + `app.js` | `theme-transitioning` 类实现全元素平滑颜色过渡 |
| 主题按钮旋转 | `animations.css` + `app.js` | 切换主题时图标 360° 旋转动画 |

#### 2. JavaScript 微交互（零依赖）

| 效果 | 文件 | 说明 |
|------|------|------|
| 列表交错入场 | `sidebar.js` | 收藏/提醒列表每项延迟 50ms 依次滑入（`stagger-item` 类） |
| 价格更新闪烁 | `sidebar.js` | 价格变化时列表项金色闪烁提示（`price-updated` 类） |
| 面板滑入增强 | `app.js` | 详情面板打开时添加 `panel-enter` 滑入动画 |

#### 3. CDN 库集成

| 库 | 大小 | 用途 |
|------|------|------|
| CountUp.js v2.10.0 | ~2KB | 价格数字平滑计数动画，价格变化时从旧值滚动到新值 |

**修改文件**:
- `web/static/css/animations.css` — 新增 11 个 keyframe 动画和工具类
- `web/static/css/style.css` — 应用辉光、括号、微光效果到组件
- `web/static/index.html` — 添加 `scanlines` 类、CountUp.js CDN
- `web/static/js/sidebar.js` — 交错入场、价格动画、CountUp 集成
- `web/static/js/app.js` — 主题切换过渡、面板滑入动画

**测试结果**: 169 个测试全部通过

**文档版本**：v4.4
**最后更新**：2026-05-04

---

### Phase 30 — GitHub 借鉴：三大交易效率工具

**日期**: 2026-05-04
**重点**: 从 GitHub Warframe 交易项目中借鉴 3 个高价值功能，提升交易决策效率

#### 背景

使用 Playwright 自动化搜索 GitHub 上的 Warframe trading 相关项目，分析并借鉴了以下 3 个功能：
- **Mod Flipper** — 借鉴自 warframe-market 相关项目的 Mod 翻转分析
- **Set Profit Analyzer** — 借鉴自套装利润对比的思路
- **Investment Advisor** — 借鉴自 ROI 投资回报分析模式

#### 1. Mod 翻转分析器

**功能**: 分析低买 R0 Mod → 内融升级满级 → 高价卖出的翻转利润，按"每千内融利润"排序。

**核心逻辑**:
- R0 买入成本 = 最低卖价（`best_sellers(orders, rank_filter=0)`）
- 满级卖出收入 = 最高收价（`best_buyers(orders, rank_filter=max_rank)`）
- 翻转利润 = 满级收价 - R0 卖价
- 每千内融利润 = 翻转利润 / (内融消耗 / 1000)
- Value Score = 每千内融利润 × log₂(48h成交量 + 1)

**内融消耗表**:

| 等级 | 所需内融 |
|------|----------|
| R3 | 320 |
| R5 | 1,280 |
| R10 | 20,470 |

**后端实现**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/mod_flipper` | GET | 扫描 Mod 翻转机会（参数: min_profit, limit） |

**核心函数**:
```python
def analyze_mod_flip(item_id, max_rank, rarity, order_fetcher) -> ModFlipResult | None
def scan_all_mod_flips(items, order_fetcher, min_profit=5, limit=20) -> list[ModFlipResult]
```

**前端显示**:
```
┌─────────────────────────────────────┐
│  Mod 翻转                    8 机会 │
│  ─────────────────────────────────  │
│  1. Primed Flow              +45p  │
│     买 R0: 10p  卖满级: 55p        │
│     内融: 20.5k  每千内融: 2.2p    │
│     48h量: 15  🟢 low              │
│  ─────────────────────────────────  │
│  2. Vitality                 +28p  │
│     买 R0: 5p   卖满级: 33p        │
│     内融: 1.3k   每千内融: 21.5p   │
│     48h量: 32  🟢 low              │
└─────────────────────────────────────┘
```

**新增文件**:
| 文件 | 说明 |
|------|------|
| `warframe_agent/mod_flipper.py` | Mod 翻转核心逻辑 |
| `tests/test_mod_flipper.py` | 10 个测试用例 |

---

#### 2. 套装利润分析器

**功能**: 对比 Prime 套装整套买 vs 拆件买的价格差异，推荐最优策略。

**两种策略**:
- **买部件→卖套装**: 各部件最低卖价总和 vs 套装最高收价
- **买套装→卖部件**: 套装最低卖价 vs 各部件最高收价总和

**后端实现**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/set_profit` | GET | 扫描套装利润机会（参数: min_profit, limit） |

**核心函数**:
```python
def analyze_set_profit(group: PrimeGroup, order_fetcher) -> SetProfitResult | None
def scan_all_set_profits(items, order_fetcher, min_profit=5, limit=20) -> list[SetProfitResult]
```

**前端显示**:
```
┌─────────────────────────────────────┐
│  套装利润                   5 套装  │
│  ─────────────────────────────────  │
│  1. Rhino Prime             +15p  │
│     策略: 买部件→卖套装             │
│     套装价: 70p  部件总和: 55p     │
│     48h量: 23                      │
│  ─────────────────────────────────  │
│  2. Nova Prime              +50p  │
│     策略: 买套装→卖部件             │
│     套装价: 30p  部件总和: 80p     │
│     48h量: 12                      │
└─────────────────────────────────────┘
```

**新增文件**:
| 文件 | 说明 |
|------|------|
| `warframe_agent/set_profit.py` | 套装利润分析核心逻辑 |
| `tests/test_set_profit.py` | 5 个测试用例 |

---

#### 3. 投资顾问

**功能**: 按预算扫描所有物品翻转机会，按 ROI% 排序并显示风险等级。

**风险评估逻辑**:
- **低风险**: 日成交量 ≥ 5 且 供需比 < 3
- **中风险**: 日成交量 ≥ 2 或 供需比 < 5
- **高风险**: 其他情况

**后端实现**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/investment` | GET | 扫描投资机会（参数: budget, min_roi, limit） |

**核心函数**:
```python
def analyze_investment(item_id, orders, filters) -> InvestmentOpportunity | None
def scan_investments(items, order_fetcher, filters) -> list[InvestmentOpportunity]
```

**前端显示**:
```
┌─────────────────────────────────────┐
│  投资顾问                  7 机会  │
│  ─────────────────────────────────  │
│  1. Arcane Energize         66.7% │
│     买: 30p  卖: 50p  利润: +20p  │
│     供/需: 2/2  日量: 5  🟢 low   │
│  ─────────────────────────────────  │
│  2. Primed Continuity       42.9% │
│     买: 35p  卖: 50p  利润: +15p  │
│     供/需: 3/5  日量: 3  🟡 med   │
└─────────────────────────────────────┘
```

**新增文件**:
| 文件 | 说明 |
|------|------|
| `warframe_agent/investment.py` | 投资顾问核心逻辑 |
| `tests/test_investment.py` | 9 个测试用例 |

---

#### 4. 工具路由集成

三个新功能均已注册为 ReAct 工具，支持自然语言调用：

**工具定义**（tool_router.py）:
```python
{"name": "mod_flipper", "description": "扫描 Mod 翻转机会..."}
{"name": "set_profit", "description": "扫描 Prime 套装利润..."}
{"name": "investment_advisor", "description": "按预算扫描投资机会..."}
```

**对话处理器**（chat.py）:
- `mod_flipper` → 调用 `scan_all_mod_flips()`，格式化排名列表
- `set_profit` → 调用 `scan_all_set_profits()`，显示策略和利润
- `investment_advisor` → 调用 `scan_investments()`，显示风险图标

**前端入口**（index.html + sidebar.js）:
- 侧边栏"更多功能"菜单新增 3 个按钮
- 点击后调用对应 API，渲染到详情面板

---

#### 5. 测试修复

**问题**: 测试 mock 订单格式与 `_to_market_orders()` 不匹配。

**根因**: `_to_market_orders()` 期望嵌套的 `user` 对象：
```python
# 期望格式
{"order_type": "sell", "platinum": 10, "user": {"ingame_name": "seller", "status": "ingame", "reputation": 5}, "rank": 0}
# 测试原格式（错误）
{"order_type": "sell", "platinum": 10, "user_name": "seller", "status": "ingame", "reputation": 5, "mod_rank": 0}
```

**修复**: 更新 3 个测试文件中的 mock 订单格式，23 个新测试全部通过。

---

#### Phase 30 实施总结

| 功能 | 模块 | 测试 | API 端点 | 前端 |
|------|------|------|----------|------|
| Mod 翻转 | `mod_flipper.py` | 10 | `/api/mod_flipper` | 侧边栏面板 |
| 套装利润 | `set_profit.py` | 5 | `/api/set_profit` | 侧边栏面板 |
| 投资顾问 | `investment.py` | 9 | `/api/investment` | 侧边栏面板 |

**修改文件**:
| 文件 | 变更 |
|------|------|
| `warframe_agent/tool_router.py` | 新增 3 个工具 schema |
| `warframe_agent/chat.py` | 新增 3 个工具处理器 |
| `warframe_agent/web/app.py` | 新增 3 个 API 端点 + `_load_items_full()` 辅助函数 |
| `warframe_agent/web/static/index.html` | 新增 3 个菜单按钮 |
| `warframe_agent/web/static/js/sidebar.js` | 新增 `loadModFlipper()`、`loadSetProfit()`、`loadInvestmentAdvisor()` |

**新增文件**:
| 文件 | 说明 |
|------|------|
| `warframe_agent/mod_flipper.py` | Mod 翻转核心逻辑 |
| `warframe_agent/set_profit.py` | 套装利润分析 |
| `warframe_agent/investment.py` | 投资顾问 |
| `tests/test_mod_flipper.py` | 10 个测试 |
| `tests/test_set_profit.py` | 5 个测试 |
| `tests/test_investment.py` | 9 个测试 |
| `scripts/browse_github.py` | Playwright GitHub 调研脚本 |
| `scripts/explore_repos.py` | 仓库探索脚本 |
| `scripts/read_source.py` | 源码阅读脚本 |

**测试结果**: 211 个测试全部通过（新增 24 个）

---

### Phase 31 — 投资顾问重设计 + Mod 翻转优化

**日期**: 2026-05-04
**重点**: 将投资顾问从通用价差扫描重构为 Prime 套装套利顾问，优化 Mod 翻转显示

#### 1. Mod 翻转优化

**问题**: 前端字段名不匹配导致显示 "undefinedp"，买/卖价格相同。

**修复**:
- API 端点新增 `min_roi_pct` 参数（默认 100%），只显示 ROI ≥ 100% 的 Mod
- 响应新增 `roi_pct` 和 `is_prime` 字段
- 前端修正字段名：`item.flip_profit`、`item.r0_buy_price`、`item.r10_sell_price`
- 新增分页（5 个/页）、PRIME 徽标、ROI 颜色编码
- 显示名只取中文名（`split(' / ')[0]`）

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `web/app.py` | `/api/mod_flipper` 新增 `min_roi_pct` 参数，返回 `roi_pct`/`is_prime` |
| 修改 | `js/sidebar.js` | `loadModFlipper` 重写：正确字段名 + 分页 + PRIME 徽标 |

#### 2. warframes.py PARTS 字典补全

**问题**: 42 个 Prime 部件因后缀不在 PARTS 字典中被 `build_prime_groups()` 静默丢弃。

**修复**: 新增 18 个部件后缀：

| 后缀 | 中文标签 | 典型物品 |
|------|---------|---------|
| hilt | 剑柄 | Nikana Prime |
| guard | 护手 | Silva & Aegis Prime |
| gauntlet | 护臂 | Ankyros Prime, Tekko Prime |
| carapace | 外壳 | Carrier Prime |
| cerebrum | 中枢 | Carrier Prime |
| boot | 靴甲 | Kogake Prime |
| head | 头部 | Fragor Prime |
| blades | 双刃 | Venka Prime |
| pouch | 囊袋 | Hikou Prime |
| stars | 星镖 | Hikou Prime |
| band | 项圈 | Kavasa Prime |
| buckle | 扣环 | Kavasa Prime |
| ornament | 饰物 | Bo Prime, Tipedo Prime |
| chain | 锁链 | Ninkondi Prime |
| bag | 袋囊 | — |
| wing | 翼片 | — |

| 操作 | 文件 | 变更 |
|------|------|------|
| 修改 | `warframes.py` | PARTS 字典新增 18 个后缀 |

#### 3. 投资顾问重设计

**设计理念**: 原投资顾问与 Mod 翻转功能重叠（都是"遍历物品找价差"）。重新设计为 **Prime 套装套利顾问**：
- **Mod 翻转** = 单品策略：买 R0 → 内融升级 → 卖满级
- **投资顾问** = 组合策略：用有限预算，在多个 Prime 套装间分配资金，最大化总利润

**核心逻辑**:

```python
# 策略 A: 散买部件 → 整套卖出
profit_a = set_sell_price - sum(parts_buy_prices)

# 策略 B: 整套买入 → 散卖部件
profit_b = sum(parts_sell_prices) - set_buy_price

# 选择更优策略
sets_affordable = budget // buy_cost
total_profit = sets_affordable * profit_per_set
```

**关键优化 — 并发获取价格**:
```python
def _fetch_prices_parallel(item_ids, order_fetcher, max_workers=5):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(order_fetcher, iid): iid for iid in item_ids}
        # 5 个部件并发获取，而非串行等待
```

**数据结构**:
```python
@dataclass(frozen=True)
class PrimeInvestment:
    base_id: str
    display_name: str
    strategy: str           # "buy_parts_sell_set" 或 "buy_set_sell_parts"
    buy_cost: int           # 买入总成本
    sell_price: int         # 卖出收入
    profit_per_set: int     # 每套利润
    roi_pct: float          # ROI%
    sets_affordable: int    # 预算内可买几套
    total_profit: int       # 可买套数 × 每套利润
    volume_48h: int | None
    risk_level: str
    part_details: list[dict]
    set_item_id: str
```

**API 端点**:

| 端点 | 参数 | 功能 |
|------|------|------|
| `/api/investment` | budget=500, min_roi_pct=10, limit=30 | Prime 套装套利扫描 |

**响应示例**:
```json
{
  "results": [{
    "base_id": "atlas_prime",
    "display_name": "Atlas Prime 一套",
    "strategy": "buy_set_sell_parts",
    "buy_cost": 65,
    "sell_price": 306,
    "profit_per_set": 241,
    "roi_pct": 370.8,
    "sets_affordable": 7,
    "total_profit": 1687,
    "part_details": [
      {"name": "蓝图", "buy": 2, "sell": 2},
      {"name": "机体", "buy": 7, "sell": 0},
      {"name": "头部神经光元", "buy": 44, "sell": 301},
      {"name": "系统", "buy": 5, "sell": 3}
    ]
  }],
  "budget": 500
}
```

**前端功能**:
- 预算输入框（默认 500p）+ 扫描按钮
- 分页显示（5 个/页）
- ROI 颜色编码：≥100% 绿色，≥50% 黄色，<50% 橙色
- 策略标签："散买→整卖" 或 "整买→散卖"
- 部件价格明细（可折叠）
- warframe.market 查看链接
- 总利润汇总："预算 500p · 全部执行可赚 +3534p"

| 操作 | 文件 | 变更 |
|------|------|------|
| 重写 | `warframe_agent/investment.py` | PrimeInvestment 数据结构、并发价格获取、套装套利分析 |
| 修改 | `web/app.py` | `/api/investment` 端点重写 |
| 重写 | `js/sidebar.js` | `loadInvestmentAdvisor` 重写 |
| 重写 | `tests/test_investment.py` | 10 个测试用例 |

#### 4. 三大功能定位

| 功能 | 利润来源 | 输入 | 输出 |
|------|---------|------|------|
| Mod 翻转 | 内融升级差价 | 无 | Mod 列表按利润排序 |
| 套装利润 | 套装 vs 部件价差 | 无 | 套装列表按利润排序 |
| **投资顾问** | 套装套利 + 预算分配 | **预算白金数** | **可执行的投资组合** |

**新增文件**:
| 文件 | 说明 |
|------|------|
| `tests/test_investment.py` | 10 个测试（重写） |

**修改文件**:
| 文件 | 变更 |
|------|------|
| `warframes.py` | PARTS 字典 +18 后缀 |
| `warframe_agent/investment.py` | 完全重写 |
| `web/app.py` | `/api/investment` + `/api/mod_flipper` 更新 |
| `js/sidebar.js` | `loadModFlipper` + `loadInvestmentAdvisor` 重写 |
| `tests/test_investment.py` | 重写为 Prime 套装测试 |

**测试结果**: 10 个投资顾问测试全部通过

**文档版本**：v4.6
**最后更新**：2026-05-04

---

### Phase 32 — Agent 架构升级：从工具平台到决策智能体

**日期**: 2026-05-05
**核心目标**: 在现有工具平台上加 4 层决策架构，让 Agent 拥有自主目标、执行计划、主动行为和反馈学习。

#### 1. 架构分析

**升级前**: 带工具的聊天机器人 — 用户问才答，每次交互独立，没有目标、没有主动性、没有学习。

**升级目标**: 4 层决策架构：

| 层级 | 功能 | 对应模块 |
|------|------|---------|
| 目标引擎 | 创建/管理/追踪目标 | `goals.py` |
| 执行计划 | 按目标生成扫描步骤 | `goals.py` → `plan_for_goal()` |
| 主动行为 | 监控循环自动执行目标 | `monitor.py` Phase 4 |
| 反馈学习 | 根据交易结果调整评分 | `goals.py` → `calculate_opportunity_score()` |

#### 2. 目标引擎 — `goals.py`（新文件）

**数据结构**:

```python
@dataclass(frozen=True)
class AgentGoal:
    goal_id: str              # UUID 前 12 位
    goal_type: str            # maximize_profit / flip_mod / build_set / find_bargain
    description: str          # 人类可读描述
    target: str               # prime_sets / mod / all
    criteria: dict            # {"budget": 500, "min_roi": 50}
    status: str               # active / achieved / abandoned
    created_at: str           # ISO 时间戳
    results: list[dict]       # 执行记录

@dataclass(frozen=True)
class ExecutionStep:
    step_id: str
    goal_id: str
    action: str               # scan_mod_flip / scan_set_profit / scan_investment / rank_results
    params: dict
    status: str               # pending / running / done / failed
    result: dict | None

@dataclass(frozen=True)
class TradeOutcome:
    outcome_id: str
    goal_id: str
    action: str               # bought / sold / skipped
    item_id: str
    price: int
    expected_profit: int
    actual_profit: int
    user_feedback: str        # good / bad / ignored
    timestamp: str
```

**核心函数**:

| 函数 | 功能 |
|------|------|
| `create_goal(goal_type, description, target, criteria)` | 创建目标，生成 UUID |
| `plan_for_goal(goal)` | 按类型生成执行步骤（4 种目标类型 × 不同步骤组合） |
| `execute_plan(plan, items, order_fetcher)` | 按顺序执行步骤，调用三大扫描函数，收集去重结果 |
| `calculate_opportunity_score(opportunity, trade_outcomes)` | 基于反馈历史调整 ROI 评分 |
| `record_trade_outcome(goal_id, action, item_id, price, ...)` | 记录交易结果 |

**目标类型 → 执行计划映射**:

| 目标类型 | 步骤 |
|---------|------|
| `maximize_profit` | scan_mod_flip → scan_set_profit → scan_investment → rank_results |
| `flip_mod` | scan_mod_flip |
| `build_set` | scan_investment |
| `find_bargain` | scan_investment → scan_mod_flip |

**反馈学习逻辑**:
```python
# 统计同类 source 的反馈
good_rate = good_count / total_count
if good_rate > 0.7:
    score *= 1.2   # 正反馈 +20%
elif good_rate < 0.3:
    score *= 0.7   # 负反馈 -30%
```

#### 3. Memory 扩展 — `memory.py`

**新增字段**:
```python
@dataclass(frozen=True)
class AgentMemory:
    # ... 原有字段 ...
    active_goals: list[AgentGoal] = field(default_factory=list)
    trade_outcomes: list[TradeOutcome] = field(default_factory=list)
```

**新增不可变方法**:

| 方法 | 功能 |
|------|------|
| `with_goal(goal)` | 添加目标 |
| `without_goal(goal_id)` | 移除目标 |
| `with_goal_result(goal_id, result)` | 追加执行结果 |
| `active_goals_list()` | 返回 status=="active" 的目标 |
| `with_trade_outcome(outcome)` | 追加交易结果 |

序列化/反序列化完整支持 JSON 持久化。

#### 4. 监控器扩展 — `monitor.py`

**Phase 4: 目标驱动扫描**（在 `scan_once()` 中新增）:

```python
# Phase 4: 目标驱动扫描
for goal in memory.active_goals_list():
    items = self._load_items()
    plan = plan_for_goal(goal)
    goal_results = execute_plan(plan, items, self.order_fetcher)
    for r in goal_results:
        if r.get("profit", 0) > 0:
            result.suggestions.append(ProactiveSuggestion(
                item_id=r["item_id"],
                suggestion_type="goal_opportunity",
                priority=1 if r["roi_pct"] > 100 else 2,
                message=f"目标「{goal.description}」发现机会: {r['item_name']} +{r['profit']}p",
            ))
```

**新增回调**: `on_goal_opportunity` — 目标机会发现时推送到前端 WebSocket。

#### 5. API 端点 — `app.py`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/goals` | GET | 获取所有目标 |
| `/api/goals` | POST | 创建新目标 |
| `/api/goals/{goal_id}` | DELETE | 放弃目标 |
| `/api/goals/{goal_id}/execute` | POST | 手动触发目标执行 |
| `/api/goals/{goal_id}/outcome` | POST | 记录交易结果 |
| `/api/goals/summary` | GET | 目标执行摘要 |

**WebSocket 新增通知类型**: `goal_opportunity` — 目标驱动的机会推送。

#### 6. 前端 — 目标面板 `sidebar.js`

**功能**:
- "+ 创建新目标" 按钮 → 弹窗（目标类型、描述、预算、最低 ROI）
- 目标列表分页（5 个/页）
- 每个目标显示：类型标签、状态、最近发现（可折叠）
- "执行" / "放弃" 按钮
- 底部摘要统计：活跃目标数、交易数、采纳率、预期利润

#### 7. 测试

**新增**: `tests/test_goals.py` — 17 个测试用例

| 测试 | 验证 |
|------|------|
| test_create_goal_basic | 目标创建、UUID 生成、默认值 |
| test_plan_for_maximize_profit | 4 步计划生成 |
| test_plan_for_flip_mod | 1 步计划生成 |
| test_plan_for_build_set | 1 步计划生成 |
| test_plan_for_find_bargain | 2 步计划生成 |
| test_execute_plan_empty | 空结果处理 |
| test_opportunity_score_* | 反馈加权（无/好/坏/中性） |
| test_record_trade_outcome | 交易结果记录 |
| test_goal_memory_persistence | JSON 持久化 |
| test_active_goals_list | 活跃目标过滤 |

**全部测试**: 229 passed

#### 8. 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `warframe_agent/goals.py` | 目标引擎核心 |
| 修改 | `warframe_agent/memory.py` | AgentMemory 扩展 |
| 修改 | `warframe_agent/monitor.py` | Phase 4 目标驱动扫描 |
| 修改 | `warframe_agent/web/app.py` | 6 个 API 端点 + WebSocket |
| 修改 | `web/static/index.html` | 目标引擎菜单按钮 |
| 修改 | `web/static/js/sidebar.js` | 目标面板前端 |
| 新增 | `tests/test_goals.py` | 17 个测试 |
| 修改 | `tests/test_mod_flipper.py` | 修复 roi_pct/is_prime 缺失 |

**文档版本**：v5.0
**最后更新**：2026-05-05

---

### Phase 33: Agent 深层智能 — 4 层自主决策能力 (v6.0)

**目标**: 从"被动执行模板"升级为具备自主思考能力的智能 Agent。

Phase 32 完成了基础架构（目标引擎 + 执行计划 + 监控集成 + 反馈学习），但系统仍然是被动的——目标由用户手动生成，计划是固定的 if-else 模板，不会从数据中学习。Phase 33 引入 4 层深层智能。

#### 架构概览

```
Layer 4: 主动推送 ← 综合所有数据，LLM 生成带推理的推送
Layer 3: 模式学习 ← 从交易历史中发现规律
Layer 2: 动态执行规划 ← ReAct 风格，根据中间结果调整
Layer 1: LLM 目标生成 ← 监控器自主分析市场创建目标
```

实现顺序: L3 → L1 → L2 → L4（因为 L1/L2/L4 的 prompt 都需要注入已学模式）

---

#### Layer 3: 模式学习 — `warframe_agent/patterns.py`

从交易历史和价格历史中提取规律，用 LLM 发现模式，写入记忆。

**数据结构**:
```python
@dataclass(frozen=True)
class LearnedPattern:
    pattern_id: str
    category: str       # "time" / "item" / "strategy"
    description: str    # "Mod翻转周末ROI更高"
    confidence: float   # 0.0-1.0
    data_points: int
    discovered_at: str
    last_validated: str
```

**核心函数**:

| 函数 | 功能 |
|------|------|
| `extract_time_patterns(trade_db, price_db)` | 按星期/小时聚合交易数据 |
| `extract_item_patterns(trade_db, price_db)` | 单品交易频率和价格稳定性 |
| `extract_strategy_patterns(trade_outcomes)` | 策略成功率对比 |
| `discover_patterns(trade_db, price_db, trade_outcomes, llm_caller)` | 主入口：数据提取 → LLM 分析 → 模式列表 |
| `build_pattern_discovery_prompt(...)` | 构建模式发现 prompt |
| `parse_patterns(response)` | 解析 LLM JSON 输出 |

**memory.py 修改**: `AgentMemory` 新增 `learned_patterns: list[dict]` 字段 + `with_patterns()` 方法（去重 + 按 confidence 排序）

**config.py 新增**: `PATTERN_DISCOVERY_INTERVAL = 12`（每 12 次扫描 ≈ 1 小时）

---

#### Layer 1: LLM 驱动目标生成 — `warframe_agent/goals.py` 扩展

监控器自动分析市场数据，用 LLM 生成目标（不需要用户创建）。

**数据结构**:
```python
@dataclass
class MarketContext:
    top_mod_flips: list[dict]       # scanner top 5
    top_set_profits: list[dict]
    top_investments: list[dict]
    anomalies: list[dict]
    active_goals: list[AgentGoal]
    trade_outcomes: list[TradeOutcome]
    user_profile: UserProfile | None
    learned_patterns: list[dict]
```

**核心函数**:

| 函数 | 功能 |
|------|------|
| `generate_goals_from_market(context, llm_caller)` | LLM 分析市场 → 1-3 个目标 |
| `_build_goal_generation_prompt(context)` | 构建 prompt（含市场数据 + 已有目标 + 用户偏好 + 已学模式） |
| `_parse_generated_goals(response, existing_goals)` | 解析 LLM JSON，去重，加 `[自动]` 前缀 |

**目标类型**: `maximize_profit` / `flip_mod` / `build_set` / `find_bargain`

**config.py 新增**: `GOAL_GENERATION_INTERVAL = 6`（每 6 周期 ≈ 30 分钟）

---

#### Layer 2: 动态执行规划（ReAct 风格）— `warframe_agent/goals.py` 扩展

执行目标时不再用固定模板，而是根据中间结果动态调整下一步。

**核心函数**:

| 函数 | 功能 |
|------|------|
| `execute_goal_dynamic(goal, items, order_fetcher, llm_caller, ...)` | ReAct 风格主循环 |
| `_build_next_step_prompt(goal, results, history, iteration, max_iter)` | 让 LLM 决定下一步 |
| `_parse_next_step(response)` | 解析 LLM 选择的 action + params |
| `_execute_single_step(action, items, order_fetcher, params)` | 执行单步扫描器 |

**执行循环**:
1. 第一步：根据 goal_type 选扫描器
2. 每步完成后，构建 summary prompt 让 LLM 决定下一步
3. LLM 可选：`scan_mod_flip` / `scan_set_profit` / `scan_investment` / `stop`
4. LLM 可调整参数（降低 min_roi_pct、改变 budget 等）
5. 超时 120s 或达到 max_iterations 则停止

**降级策略**: `llm_caller` 为 None 或 LLM 调用失败 → 回退到静态 `plan_for_goal` + `execute_plan`

**config.py 新增**:
- `DYNAMIC_PLAN_MAX_ITERATIONS = 3`
- `DYNAMIC_PLAN_TIMEOUT_SECONDS = 120`

---

#### Layer 4: 主动推送 — `warframe_agent/monitor.py` 扩展

综合所有数据生成带推理的推送消息，尊重用户偏好。

**数据结构**:
```python
@dataclass(frozen=True)
class ProactivePush:
    item_id: str
    item_display: str
    push_type: str       # "opportunity" / "warning" / "recommendation"
    priority: int        # 1=critical, 2=important
    message: str         # LLM 生成的推理
    action_suggestion: str  # "buy now" / "sell now" / "watch"
    data: dict
```

**核心逻辑**:
- `_run_proactive_push(scan_result)` → 筛选 priority ≤ 2 的建议
- 用户偏好过滤：mod 类机会对只关注 prime_set 的用户降级
- LLM 生成推送消息（含"为什么推荐" + 操作建议 + 风险提示）
- LLM 失败时用原始消息降级推送

**app.py 新增**:
- `broadcast_proactive_push(push)` — WebSocket 广播
- `on_proactive_push` 回调 → `setup_monitor()` 注册
- `GET /api/patterns` — 查看已学模式

**前端**: `app.js` WebSocket 处理 `proactive_push` 和 `goal_opportunity` 通知类型

---

#### monitor.py 集成

**PriceMonitor 新增**:
- `on_proactive_push` 回调参数
- `_goal_planner_caller()` — 适配 `execute_goal_dynamic` 的 LLM 接口
- `_run_proactive_push()` — Layer 4 主逻辑
- Phase 4 改用 `execute_goal_dynamic()` 替代静态 `plan_for_goal()`
- 周期调用：模式发现（每 12 周期）、目标生成（每 6 周期）

**扫描周期 `_run()` 流程**:
```
scan_once() → 机会检测 → LLM 分析增强 → 主动推送 → 保存建议
→ 周期性模式发现 → 周期性目标生成 → sleep 5min
```

---

#### 测试

| 测试文件 | 用例数 | 覆盖 |
|----------|--------|------|
| `tests/test_patterns.py` | 14 | 时间/物品/策略模式提取、prompt 构建、JSON 解析、discover_patterns 集成 |
| `tests/test_goal_generation.py` | 10 | MarketContext、prompt 构建、目标解析/去重、LLM 集成/降级 |
| `tests/test_dynamic_plan.py` | 9 | prompt 构建、step 解析、单步执行、fallback、超时 |
| `tests/test_proactive_push.py` | 7 | ProactivePush 创建、LLM 推送/降级、用户偏好过滤 |

**全部测试**: 274 passed（229 原有 + 45 新增）

---

#### 关键设计决策

1. **所有 LLM 调用用 `chat_with_ollama`（同步）**: 监控器是 daemon 线程，不能用 async
2. **优雅降级**: 每个 LLM 调用都有 fallback，失败不影响现有功能
3. **资源限制**: 自动目标 ≤ 3 个，模式发现每小时 1 次，动态执行超时 120s，推送仅 priority 1-2
4. **不可变数据**: 所有新结构用 frozen dataclass，AgentMemory 用 replace() 模式
5. **模式注入**: 已学模式注入到所有 LLM prompt 中，让 Agent 有"经验"

---

#### 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `warframe_agent/patterns.py` | 模式学习核心（224 行） |
| 修改 | `warframe_agent/memory.py` | `learned_patterns` 字段 + `with_patterns()` |
| 修改 | `warframe_agent/goals.py` | MarketContext + 目标生成 + 动态执行 |
| 修改 | `warframe_agent/monitor.py` | 4 层集成 + 回调 + 周期调度 |
| 修改 | `warframe_agent/config.py` | 4 个新常量 |
| 修改 | `warframe_agent/web/app.py` | `/api/patterns` + proactive_push 广播 |
| 修改 | `web/static/js/app.js` | WebSocket 通知处理 |
| 新增 | `tests/test_patterns.py` | 14 个测试 |
| 新增 | `tests/test_goal_generation.py` | 10 个测试 |
| 新增 | `tests/test_dynamic_plan.py` | 9 个测试 |
| 新增 | `tests/test_proactive_push.py` | 7 个测试 |

**文档版本**：v6.0
**最后更新**：2026-05-05

---

### Phase 34: 架构重构 — 从 LLM 驱动到规则引擎 + 知识库 (v7.0)

Phase 33 完成了 4 层深层智能，但存在根本问题：**监控器每 5 分钟扫描周期塞了 4-5 次 LLM 调用**，既慢又不稳定。Phase 34 将监控器从 LLM 依赖中解放出来，改为 100% 规则驱动。LLM 只保留给聊天层。

#### 核心变更

**5 个 LLM 调用点 → 纯规则驱动**:

| # | 原 LLM 调用 | 替代方案 | 位置 |
|---|------------|----------|------|
| 1 | `_run` LLM enrichment | 删除（模板已在异常检测中生成） | `monitor._run` |
| 2 | `_run_proactive_push` | `generate_proactive_message()` 模板 | `rules.py` |
| 3 | `_run_pattern_discovery` | `knowledge.update_from_scan()` | `knowledge.py` |
| 4 | `_run_goal_generation` | `generate_auto_goals()` 规则 | `rules.py` |
| 5 | `execute_goal_dynamic` | `plan_for_goal()` + `execute_plan()` | `goals.py` |

#### Phase 1: 知识库 + 规则引擎

**新增 `warframe_agent/knowledge.py`**:
- `ItemKnowledge` — 物品级市场智能（滚动均价、波动率、趋势、扫描计数、事件上下文）
- `CategoryHealth` — 品类健康度（机会数、平均 ROI、趋势）
- `MarketKnowledge` — 知识库核心：
  - `update_from_scan()` — 增量更新，用 `price_db` 计算统计量
  - `get_item_stats()` / `get_category_health()` / `get_market_summary()`
  - `update_event_context()` — 游戏事件上下文注入
  - `save()` / `load()` — 持久化到 `data/knowledge_base.json`

**新增 `warframe_agent/rules.py`**:
- `MarketState` — 市场状态快照（波动率、趋势、活跃度、品类表现）
- `ProactivePush` — 推送消息结构（从 monitor.py 迁移）
- `evaluate_market_state()` — 纯计算评估市场，无网络、无 LLM
- `generate_auto_goals()` — 4 条规则自动生成目标：
  - mod 平均 ROI > 100% → `flip_mod`
  - prime_set 机会 > 5 → `build_set`
  - prime_set 平均 ROI > 30% → `find_bargain`
  - 有异常 + 市场下行 → 保守 `maximize_profit`
  - 最多 3 个自动目标，按 `(goal_type, target)` 去重
- `generate_proactive_message()` — 模板化推送：
  - 异常 → `"⚠️ {item} 价格{方向}！{recommendation}"`
  - 机会 → `"💰 {item} 利润{profit}p"`
  - recommendation 由 `_anomaly_recommendation()` 规则决定
- `decide_next_step()` — 决策树替代 LLM 动态规划

#### Phase 2: 监控器重构

**重构 `warframe_agent/monitor.py`**:
- `__init__` 移除 `llm_analyzer`，新增 `knowledge: MarketKnowledge` + `event_tracker: EventTracker`
- `_run_proactive_push()` — 改用 `generate_proactive_message()`
- `_run_goal_generation()` — 改用 `evaluate_market_state()` + `generate_auto_goals()`
- `_run_pattern_discovery()` → `_run_knowledge_update()` — 改用 `knowledge.update_from_scan()`
- Phase 4 改回 `plan_for_goal()` + `execute_plan()`
- 删除 `_goal_planner_caller()`、`build_anomaly_analysis_prompt()`
- `_run()` 扫描周期从 LLM 依赖变为纯规则：
  ```
  scan_once() → 机会检测 → 规则推送 → 保存建议
  → 知识库更新(每3周期) → 目标生成(每6周期) → sleep 5min
  ```

**重构 `warframe_agent/web/app.py`**:
- `setup_monitor()` 移除 `llm_analyzer`，改用 `MarketKnowledge.load()`

#### Phase 3: 游戏事件感知

**新增 `warframe_agent/events.py`**:
- `GameEvent` — 事件结构（类型、影响物品、时间、影响方向、描述）
- `EventTracker` — 事件追踪器：
  - `fetch_world_state()` — 从 `api.warframestat.us/pc` 获取
  - `parse_events()` — 解析 Baro、警报、入侵、虚空风暴
  - `get_active_events()` — 带 30 分钟缓存
  - `get_event_impact()` — 检查物品是否受事件影响
  - `save_cache()` / `load_cache()` — 持久化缓存
  - 容错：API 失败返回旧缓存

**集成**:
- `monitor._run_knowledge_update()` — 每次知识更新时刷新事件并注入知识库
- `chat.py` — 新增 `query_events` 工具处理
- `tool_router.py` — 新增 `query_events` schema
- `app.py` — `GET /api/events` 端点

#### Phase 4: 用户目标分解

**扩展 `warframe_agent/goals.py`**:
- `GoalProgress` — 目标进度追踪（目标量、当前量、剩余、步骤完成数）
- `decompose_platinum_goal()` — 运行 3 个扫描器 → 按利润降序 → 贪心选取直到达标
- `track_goal_progress()` — 按 goal_id 过滤交易结果，累加实际利润
- `plan_for_goal()` 新增 `earn_platinum` 目标类型

**新增 API 端点**:
- `POST /api/goals/earn` — 创建攒白金目标 + 返回分解步骤
- `GET /api/goals/{goal_id}/progress` — 获取目标进度

#### 测试

| 测试文件 | 用例数 | 覆盖 |
|----------|--------|------|
| `tests/test_knowledge.py` | 17 | 分类、ItemKnowledge、CategoryHealth、MarketKnowledge CRUD、save/load |
| `tests/test_rules.py` | 21 | MarketState、evaluate_market_state、generate_auto_goals(7场景)、proactive_message(4场景)、decide_next_step(7场景) |
| `tests/test_events.py` | 12 | GameEvent、_classify_event、parse_events、get_event_impact、缓存、容错 |
| `tests/test_goal_decompose.py` | 7 | GoalProgress、decompose_platinum_goal、track_goal_progress、earn_platinum 计划 |
| `tests/test_enriched_monitor.py` | 8 | 机会检测、知识库集成、predict_trend |
| `tests/test_proactive_push.py` | 5 | ProactivePush 创建、规则推送 |

**全部测试**: 328 passed（309 原有 - 3 删除 + 19 新增）

---

#### 关键设计决策

1. **零 LLM 依赖的监控器**: 扫描周期 < 10s，不依赖 Ollama 进程
2. **知识库增量积累**: `knowledge.update_from_scan()` 用 `price_db` 计算派生统计，不重建
3. **模板化推送**: 异常/机会消息由规则模板生成，不调用 LLM
4. **游戏事件缓存**: 30 分钟 TTL，API 失败返回旧缓存，不崩溃
5. **贪心目标分解**: 运行全部扫描器后按利润降序选取，简单高效
6. **不可变数据**: 所有新结构用 frozen dataclass，保持一致性

---

#### 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `warframe_agent/knowledge.py` | 结构化知识库（233 行） |
| 新增 | `warframe_agent/rules.py` | 规则引擎（256 行） |
| 新增 | `warframe_agent/events.py` | 游戏事件追踪（210 行） |
| 修改 | `warframe_agent/monitor.py` | 删除 5 个 LLM 调用点，改用规则引擎 |
| 修改 | `warframe_agent/goals.py` | 新增 GoalProgress + decompose_platinum_goal + earn_platinum |
| 修改 | `warframe_agent/config.py` | 新增 6 个常量 |
| 修改 | `warframe_agent/chat.py` | 新增 query_events 工具处理 |
| 修改 | `warframe_agent/tool_router.py` | 新增 query_events schema |
| 修改 | `warframe_agent/web/app.py` | setup_monitor 重构 + 3 个新端点 |
| 新增 | `tests/test_knowledge.py` | 17 个测试 |
| 新增 | `tests/test_rules.py` | 21 个测试 |
| 新增 | `tests/test_events.py` | 12 个测试 |
| 新增 | `tests/test_goal_decompose.py` | 7 个测试 |
| 修改 | `tests/test_enriched_monitor.py` | 移除 LLM 测试，改用规则引擎 |
| 修改 | `tests/test_proactive_push.py` | 移除 LLM 测试，改用规则引擎 |

**文档版本**：v7.0
**最后更新**：2026-05-05

---

### Phase 35: 自适应智能体 — 反馈闭环 + 动态阈值 + 上下文增强

> **目标**: 从"有记忆的反应工具"进化为"从经验中学习的自适应智能体"。
> **核心突破**: 构建 4 个闭环，让智能体越用越聪明。

#### 背景问题

Phase 34 完成了架构重构（LLM → 规则引擎 + 知识库），系统运行稳定，328 测试全通过。但深入审计发现：

| 问题 | 表现 | 影响 |
|------|------|------|
| 反馈未消费 | `trade_outcomes` 记录了每笔交易结果，但规则引擎从不读取 | 无法从历史学习 |
| 静态阈值 | `ROI>100%`、`volatility>50` 全部硬编码 | 不同市场环境下一刀切 |
| 上下文贫乏 | 聊天层看不到知识库、事件、交易历史 | LLM 回答缺乏深度 |
| 事件无影响 | 游戏事件已追踪，但不影响价格预测或推送 | 错过 Baro/Prime Access 窗口 |

#### Phase A: 反馈闭环

**新增 `warframe_agent/feedback.py`** — 从 trade_outcomes 提炼策略信号：

```python
@dataclass(frozen=True)
class StrategyFeedback:
    strategy: str              # "mod_flip" / "set_build" / "bargain_hunt"
    win_rate: float            # 0.0 ~ 1.0
    avg_profit: float          # 平均利润
    avg_roi: float             # 平均 ROI
    sample_size: int           # 样本数
    confidence: str            # "high" / "medium" / "low"
    recommended: bool          # 是否推荐继续
    last_updated: str

@dataclass(frozen=True)
class ItemFeedback:
    item_id: str
    times_traded: int
    total_profit: float
    avg_profit: float
    win_rate: float
    best_strategy: str
    last_traded: str
```

**类 `FeedbackAnalyzer`**:
- `analyze_strategies(trade_outcomes) -> list[StrategyFeedback]` — 按策略分组计算胜率/利润/ROI
- `analyze_items(trade_outcomes) -> list[ItemFeedback]` — 按物品分组找最佳策略
- `get_strategy_ranking(trade_outcomes) -> list[str]` — 按 recommended + avg_profit 排序
- `get_feedback_for(strategy, outcomes) -> StrategyFeedback | None` — 单策略查询

**置信度规则**: sample_size < 3 → "low", < 10 → "medium", ≥ 10 → "high"
**推荐条件**: win_rate > 0.5 AND avg_profit > 5

**集成到 `rules.py`**:
- `generate_auto_goals()` — 新增 `trade_outcomes` 参数，检查 `_is_strategy_blocked()` 跳过表现差的策略
- `decide_next_step()` — 新增提前终止：win_rate < 20% 且 sample ≥ 3 → 换策略

#### Phase B: 自适应阈值

**新增 `AdaptiveThresholds`** — 根据市场状态动态计算阈值：

```python
@dataclass(frozen=True)
class AdaptiveThresholds:
    roi_good: float        # 市场平均 ROI × 1.2
    roi_excellent: float   # 市场平均 ROI × 2.0
    volatility_high: float # 市场平均波动率 × 1.5
    min_profit: float      # 市场平均利润 × 0.8

def compute_thresholds(knowledge: MarketKnowledge) -> AdaptiveThresholds:
    summary = knowledge.get_market_summary()
    avg_roi = summary.get("avg_roi", 30)
    avg_vol = summary.get("avg_volatility", 30)
    avg_profit = summary.get("avg_profit", 10)
    return AdaptiveThresholds(
        roi_good=max(20, avg_roi * 1.2),
        roi_excellent=max(50, avg_roi * 2.0),
        volatility_high=max(30, avg_vol * 1.5),
        min_profit=max(3, avg_profit * 0.8),
    )
```

**效果**: 高 ROI 市场 → 阈值自动提高（不推荐平庸机会）；低 ROI 市场 → 阈值降低（不错过好机会）

**`config.py` 变更**:
- `VOLATILITY_HIGH_THRESHOLD` → `DEFAULT_VOLATILITY_HIGH = 50`
- `VOLATILITY_LOW_THRESHOLD` → `DEFAULT_VOLATILITY_LOW = 20`
- 新增 `DEFAULT_ROI_THRESHOLD = 30`、`DEFAULT_MIN_PROFIT = 5`

#### Phase C: 聊天上下文增强

**新增 `build_system_context()`** — 注入丰富上下文到 LLM system prompt：

```python
def build_system_context(knowledge, event_tracker, trade_db, memory) -> str:
    # 1. 市场概况: trend_direction, volatility_index, best_category
    # 2. 热门物品: mod/prime_set 的 top_items
    # 3. 游戏事件: Baro/Prime Access/警报
    # 4. 交易统计: 近期胜率, 盈利笔数
    # 5. 交易结果: 最近 5 笔详情
```

**集成**:
- `chat.py` — `ChatAgent.__init__` 新增 `knowledge` + `event_tracker` 参数
- `answer()` / `answer_stream()` — 自动调用 `build_system_context()` 注入上下文
- `app.py` — `setup_monitor()` 中 `chat_agent.knowledge = monitor.knowledge`

#### Phase D: 事件驱动智能

**`knowledge.py` 增强**:
- `update_from_scan()` — 新增 `events` 参数，构建 item→event 映射，注入 `event_context`
- `predict_with_events(item_id, events)` — 正面事件 + stable → "rising"，负面 + stable → "falling"

**`monitor.py` 增强**:
- `_run_knowledge_update()` — 将 `event_tracker.refresh()` 结果传入 `update_from_scan(events=events)`
- 不再单独调用 `update_event_context()`

**`rules.py` 增强**:
- `generate_proactive_message()` — 推送消息附加事件上下文（如"Baro 即将到来可能导致进一步下跌"）

#### 测试

| 测试文件 | 新增 | 覆盖 |
|----------|------|------|
| `tests/test_feedback.py` | 16 | analyze_strategies(8), analyze_items(3), get_strategy_ranking(2), get_feedback_for(3) |
| `tests/test_rules.py` | +7 | feedback blocked/not blocked, switch strategy, compute_thresholds, auto_goals_use_adaptive |
| `tests/test_knowledge.py` | +6 | predict_with_events(5), update_from_scan_with_events(1) |
| `tests/test_chat.py` | +4 | build_system_context: empty, knowledge, trade_history, trade_outcomes |

**全部测试**: 361 passed（328 + 33 新增）

#### 关键设计决策

1. **反馈闭环**: trade_outcomes → FeedbackAnalyzer → 策略过滤 → 不推荐历史表现差的策略
2. **自适应阈值**: 知识库数据驱动阈值，无需手动调参
3. **上下文注入**: LLM 获得市场概况 + 事件 + 交易历史，回答更精准
4. **事件增强预测**: 游戏事件直接影响价格趋势预测
5. **不可变数据**: 所有新结构用 frozen dataclass + replace() 模式

---

#### 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `warframe_agent/feedback.py` | 反馈分析器（~150 行） |
| 修改 | `warframe_agent/rules.py` | 反馈过滤 + 自适应阈值 |
| 修改 | `warframe_agent/monitor.py` | 注入 feedback + events |
| 修改 | `warframe_agent/chat.py` | build_system_context + 上下文注入 |
| 修改 | `warframe_agent/knowledge.py` | 事件增强预测 |
| 修改 | `warframe_agent/config.py` | 重命名阈值常量 |
| 修改 | `warframe_agent/web/app.py` | chat_agent 绑定 knowledge |
| 新增 | `tests/test_feedback.py` | 16 个测试 |
| 修改 | `tests/test_rules.py` | +7 个测试 |
| 修改 | `tests/test_knowledge.py` | +6 个测试 |
| 修改 | `tests/test_chat.py` | +4 个测试 |

**文档版本**：v8.0
**最后更新**：2026-05-05

---

### Phase 36: 移动端推送与飞书机器人集成 (v9.0)

**日期**: 2026-05-06
**重点**: WxPusher 微信推送 + 飞书机器人双向对话，实现手机端与智能体交互

#### 背景

Web UI 功能完善后，用户希望在手机上也能接收通知和与智能体对话。采用两步方案：
1. **WxPusher** — 免费微信推送服务，实现价格提醒/每日报告推送到微信
2. **飞书机器人** — 通过飞书 App 实现手机端双向对话

---

#### 1. WxPusher 微信推送

**功能**: 价格提醒、关注通知、主动建议、每日报告推送到微信。

**数据模型** — `warframe_agent/push.py`:

```python
@dataclass
class PushConfig:
    enabled: bool = False
    app_token: str = ""          # WxPusher 应用 Token
    uids: list[str] = field(default_factory=list)  # 接收者 UID 列表
    push_alerts: bool = True     # 推送价格提醒
    push_watches: bool = True    # 推送关注通知
    push_proactive: bool = True  # 推送主动建议
    push_daily_report: bool = True  # 每日报告
    report_time: str = "09:00"   # 报告时间

class WxPusher:
    API_URL = "https://wxpusher.zjiecode.com/api/send/message"

    def send(self, title, content, content_type=3) -> bool
    def send_text(self, title, text) -> bool
    def send_markdown(self, title, md) -> bool

# 格式化函数（带私聊命令）
def format_buyers_with_whisper(item_name, market_id, buyers) -> str
def format_sellers_with_whisper(item_name, market_id, sellers) -> str
def should_send_daily_report(config) -> bool
```

**推送触发点** — `app.py`:

| 触发场景 | 函数 | 推送类型 |
|----------|------|----------|
| 价格提醒触发 | `broadcast_alert()` | 价格提醒 |
| 关注扫描完成 | `broadcast_watch()` | 关注通知 |
| 主动建议生成 | `broadcast_proactive_push()` | 主动建议 |
| 每日报告时间 | `monitor._check_daily_report()` | 每日报告 |

**每日报告** — `monitor.py`:
- 在 `_run()` 扫描循环中检查时间窗口（±6 分钟）
- 获取收藏物品当前价格（top 3 买家 + top 3 卖家）
- 使用 `format_buyers_with_whisper()` / `format_sellers_with_whisper()` 生成报告
- 报告自动包含 `/w 玩家名 Hi! I want to buy/sell: ...` 私聊命令
- 纯文本格式发送（微信显示效果优于 Markdown 表格）
- 通过 WxPusher + 飞书双通道推送（`on_daily_report` 回调）

**私聊命令格式化** — `push.py`:
```python
def format_buyers_with_whisper(item_name, market_id, buyers) -> str
def format_sellers_with_whisper(item_name, market_id, sellers) -> str
```
- 每个买家/卖家附带游戏内 `/w` 私聊命令，可直接复制粘贴
- 支持 `MarketOrder` 对象和字典两种格式

**API 端点**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/push/config` | GET | 获取推送配置（隐藏 token） |
| `POST /api/push/config` | POST | 更新推送配置 |
| `POST /api/push/test` | POST | 测试推送 |
| `GET /api/push/qrcode` | GET | 获取 WxPusher 关注二维码 |
| `POST /api/push/callback` | POST | WxPusher 事件回调 |

**前端设置** — 设置模态框新增"微信推送"区域：
- 启用开关
- UID 输入框 + 保存/测试按钮
- 子开关：价格提醒/关注通知/主动建议/每日报告
- 报告时间选择
- 关注二维码显示

---

#### 2. 飞书机器人（WebSocket 长连接模式）

**功能**: 在飞书中与智能体双向对话，无需公网 IP。

**技术方案**: 飞书 SDK WebSocket 长连接模式
- 使用 `lark_oapi` SDK 的 `lark.ws.Client` 建立 WebSocket 连接
- 通过 `subprocess.Popen` 运行独立子进程（避免与 FastAPI 事件循环冲突）
- 子进程收到消息后调用本地 `http://127.0.0.1:8000/api/chat` 获取智能体回复
- 通过飞书消息 API 回复用户

**数据模型** — `warframe_agent/feishu.py`:

```python
@dataclass
class FeishuConfig:
    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""

class FeishuBot:
    def __init__(self, cfg: FeishuConfig, on_message=None)
    def start(self) -> None    # 启动 WebSocket 子进程
    def stop(self) -> None     # 停止子进程
    def reply(self, message_id, text) -> bool
    def send(self, chat_id, text) -> bool
```

**子进程架构**:

```
主进程 (FastAPI)
  ├── Web 服务器 (uvicorn)
  └── FeishuBot.start()
        └── subprocess.Popen (独立 Python 进程)
              ├── lark.ws.Client (WebSocket 长连接)
              ├── EventDispatcherHandler (消息事件处理)
              └── 调用 /api/chat 获取回复 → 飞书 API 回复
```

**消息处理流程**:

```
飞书用户发消息
    ↓
飞书服务器 → WebSocket 推送
    ↓
子进程 on_message() 接收
    ↓
提取文本（去掉 @机器人 前缀）
    ↓
POST http://127.0.0.1:8000/api/chat
    ↓
ChatAgent.answer() 处理
    ↓
飞书 ReplyMessageRequest 回复
```

**关键实现细节**:

1. **回复 API**: 使用 `ReplyMessageRequest` + `ReplyMessageRequestBody`（不是 `CreateMessageRequest`）
2. **客户端复用**: 子进程内全局 `_client` 单例，避免每次回复重新创建
3. **日志输出**: stdout/stderr 重定向到 `data/feishu_worker.log`，便于调试
4. **自动重连**: SDK 内置 `auto_reconnect=True`，断线自动重连

**API 端点**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `GET /api/feishu/config` | GET | 获取飞书配置（隐藏 secret） |
| `POST /api/feishu/config` | POST | 更新飞书配置（自动重启子进程） |
| `POST /api/feishu/test` | POST | 测试连接状态 |

**前端设置** — 设置模态框新增"飞书机器人"区域：
- 启用开关
- App ID 输入框
- App Secret 输入框
- 保存/测试连接按钮

**飞书开发者后台配置**:
1. 创建企业自建应用
2. 添加"机器人"能力
3. 权限管理 → 开通 `im:message`、`im:message.create_v1`、`im:message.receive_v1`
4. 事件订阅 → 添加 `im.message.receive_v1`，勾选"使用长连接接收事件"
5. 创建版本并发布

---

#### 3. 配置存储

| 文件 | 格式 | 说明 |
|------|------|------|
| `data/push_config.json` | JSON | WxPusher 推送配置 |
| `data/feishu_config.json` | JSON | 飞书机器人配置 |

`config.py` 新增:
```python
PUSH_CONFIG_PATH = DATA_DIR / "push_config.json"
FEISHU_CONFIG_PATH = DATA_DIR / "feishu_config.json"
```

---

#### 4. 测试

| 测试文件 | 用例数 | 覆盖 |
|----------|--------|------|
| `tests/test_push.py` | 21 | PushConfig 存取、WxPusher 发送/错误/截断、should_send_daily_report |
| `tests/test_feishu.py` | 6 | FeishuConfig 存取、FeishuBot 可用状态、回调、stop |

---

#### 5. 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `warframe_agent/push.py` | WxPusher 推送模块 + `format_buyers_with_whisper()` / `format_sellers_with_whisper()` 格式化函数 |
| 新增 | `warframe_agent/feishu.py` | 飞书机器人模块（WebSocket + 子进程） |
| 修改 | `warframe_agent/config.py` | 新增 PUSH_CONFIG_PATH、FEISHU_CONFIG_PATH |
| 修改 | `warframe_agent/web/app.py` | 推送/飞书 API 端点、广播集成、`on_daily_report` 回调、lifespan |
| 修改 | `warframe_agent/monitor.py` | 每日报告：私聊命令 + 纯文本格式 + 双通道推送（WxPusher + 飞书） |
| 修改 | `warframe_agent/web/static/index.html` | WxPusher/飞书设置 UI |
| 修改 | `warframe_agent/web/static/js/app.js` | 推送/飞书设置交互 |
| 新增 | `tests/test_push.py` | 21 个测试 |
| 新增 | `tests/test_feishu.py` | 6 个测试 |

---

#### 6. 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 飞书消息已读但无回复 | 事件订阅未添加 `im.message.receive_v1` | 开发者后台添加事件 |
| 飞书回复失败: field validation failed | 使用了 `CreateMessageRequest` 而非 `ReplyMessageRequest` | 改用 `ReplyMessageRequest` |
| 飞书 WebSocket 事件不触发 | 事件订阅后未重新发布版本 | 创建新版本并发布 |
| WxPusher UID 收不到消息 | 未关注 WxPusher 公众号 | 扫码重新关注 |
| Ollama 超时导致飞书无回复 | 模型卡住或加载中 | 重启 Ollama (`ollama serve`) |
| 子进程事件循环冲突 | `lark.ws.Client.start()` 与 FastAPI 事件循环冲突 | 使用 `subprocess.Popen` 隔离 |

---

#### 7. 三大通信渠道总结

| 渠道 | 方向 | 协议 | 用途 |
|------|------|------|------|
| **Web UI** | 双向 | HTTP + WebSocket | 浏览器完整交互 |
| **WxPusher** | 单向（推送） | HTTPS | 微信通知推送 |
| **飞书机器人** | 双向 | WebSocket 长连接 | 手机端对话 |

**文档版本**：v9.1
**最后更新**：2026-05-07

---

### Phase 37: 智能体增强 — 不换模型，从 Prompt/知识/上下文/自检 四维度提升 (v10.0)

**日期**: 2026-05-10
**核心目标**: 在不升级本地模型（qwen3:8b）的前提下，通过 Prompt 工程、游戏知识注入、上下文智能组装、自检机制、反馈注入五个维度提升智能体回答质量。

#### 背景

本地 Ollama qwen3:8b 模型受硬件限制无法升级。瓶颈不在模型大小，而在：
- **Prompt 质量差**：硬编码 4 行指令，无 few-shot、无 CoT 引导
- **游戏知识未利用**：Export 数据（Mod 效果、战甲技能）完全未注入 LLM
- **上下文组装粗糙**：历史对话按时间截取、记忆平铺无优先级
- **无自检机制**：LLM 编造价格、遗漏私聊命令时无人纠正

改进思路：**让 8B 模型在更好的输入下工作**。

---

#### Phase 1: Prompt 工程优化

**目标**: 通过 CoT 引导 + Few-shot 示例 + 结构化模板，直接提升 LLM 输出质量。

**1.1 重写 `build_system_prompt()`**

| 项目 | 说明 |
|------|------|
| 行为准则 | 不编造价格、提供私聊命令、数据不足时说明 |
| CoT 回答策略 | 价格查询 4 步、投资类 4 步 |
| Few-shot 示例 | 价格查询 + 套装比较，教模型输出格式 |
| 结构化分段 | `## 角色` / `## 回答策略` / `## 示例` / `## 用户画像` / `## 市场智能` |

**1.2 重写 ReAct system prompt**

从 2 句话扩展为 10 条决策规则（每个工具一条触发条件），加注意事项（中文别名映射、多物品用 plan、不确定时走 general_chat）。

**1.3 重写 `_memory_prompt()`**

按优先级分层：触发的提醒 > 用户偏好 > 相关建议 > 高置信度已学模式。只注入与当前查询物品相关的建议。

---

#### Phase 2: 游戏知识深度注入

**目标**: 让 LLM 能引用具体游戏数据（Mod 效果、战甲技能、遗物封存状态）。

**2.1 新增 `warframe_agent/game_data.py`**

`GameDataStore` 类，懒加载以下数据：

| 数据源 | 内容 |
|--------|------|
| `ExportUpgrades_zh.json` | Mod 效果描述、满级属性、稀有度 |
| `ExportRelicArcane_zh.json` | 赋能效果、满级属性 |
| `ExportWarframes_zh.json` | 战甲技能描述、基础属性 |
| `ducat_values.json` | 杜卡特值 |
| `relic_vault_status.json` | 遗物封存状态 |
| `relic_sources.json` | 遗物获取途径 |

关键方法：
- `get_mod_info(name) -> str | None` — 返回 Mod/Arcane 效果文本
- `get_warframe_info(name) -> str | None` — 返回战甲技能文本
- `get_ducat_value(item_id) -> int | None`
- `is_vaulted(relic_name) -> bool | None`

**2.2 上下文注入**

- `ChatAgent.__init__` 新增 `self.game_data = GameDataStore()`
- `build_system_context()` 新增 `game_data` 和 `current_item_ids` 参数
- 新增 `_build_item_knowledge_block()` — 为当前查询物品构建详细知识块（知识库统计 + Mod 效果 + 杜卡特值）
- `answer()` / `answer_stream()` 传递 `game_data` 和 `current_item_ids`

---

#### Phase 3: 上下文智能组装

**目标**: 让注入 LLM 的信息更精准，减少干扰。

**3.1 历史对话按相关性排序**

`session.py` 的 `to_messages()` 新增 `current_query` 参数：
- 有 query 时：按关键词重叠评分 + 时间衰减排序，取 top-N
- 无 query 时：回退到原有时间截取

`_relevance_score()` — 简单子串匹配评分（不依赖 embedding，零开销）

**3.2 结构化 `build_system_context()`**

按层拼接：
1. `[物品情报: xxx]` — 当前查询物品的详细知识
2. `[市场概况]` — 趋势、跟踪物品数
3. `[游戏事件]` — 最多 3 条
4. `[交易统计]` — 胜率、累计利润
5. `[策略表现]` — 样本 >= 3 时注入

---

#### Phase 4: Self-Reflection 机制

**目标**: 用规则化自检捕获 LLM 的严重错误，不增加额外 LLM 调用。

**`_self_check()` 函数** — LLM 返回后调用：

| 检查项 | 规则 |
|--------|------|
| 价格编造检测 | 回答中出现的 `Np` 价格必须在 contexts 中存在（允许 ±5 范围） |
| 私聊命令检测 | 有推荐卖家/买家时必须包含 `/w ` |
| 回答截断检测 | 长度 < 20 字符则追加警告 |

发现问题时追加 `[注意] ...` 后缀，不重新生成。

**调用点**: `answer()` 和 `answer_stream()` 中 LLM 返回成功后。

---

#### Phase 5: 反馈与模式注入

**目标**: 让 LLM 利用积累的交易经验和规律。

**5.1 策略反馈注入**

`build_system_context()` 新增策略表现摘要：
- 调用 `FeedbackAnalyzer.analyze_strategies()` 生成
- sample_size >= 3 才显示
- 格式：`[策略表现] Mod翻转: 胜率=80%, 平均利润=15p, 样本=5`

**5.2 已学模式注入**

`_memory_prompt()` 注入 `memory.learned_patterns` 中 confidence >= 0.7 的模式，最多 3 条。

---

#### 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `warframe_agent/game_data.py` | 游戏知识查询模块（202 行） |
| 修改 | `warframe_agent/chat.py` | build_system_prompt + _memory_prompt + build_system_context 重写，game_data 注入，_self_check |
| 修改 | `warframe_agent/tool_router.py` | ReAct system prompt 重写（10 条规则） |
| 修改 | `warframe_agent/session.py` | to_messages() 相关性排序 + _relevance_score() |
| 修改 | `tests/test_chat.py` | 断言适配新格式 |
| 修改 | `tests/test_chat_alias_priority.py` | 断言适配新 prompt |
| 修改 | `tests/test_chat_memory_integration.py` | 断言适配新记忆格式 |
| 修改 | `tests/test_phase35_e2e.py` | 断言适配新上下文格式 |

**全部测试**: 409 passed

---

### Phase 38: 混合模型架构 — 本地 + 云端智能路由 (v11.0)

**日期**: 2026-05-11
**核心目标**: 接入外部云端模型（gpt-5.5），实现简单查询走本地、复杂推理走云端的智能路由。

#### 背景

本地 qwen3:8b 模型在复杂分析（多物品对比、投资策略、趋势推理）上能力不足。引入外部云端模型作为"大脑升级"，但保留本地模型处理简单查询以节省成本。

#### 模型路由策略

| 路由模式 | 说明 |
|----------|------|
| `auto`（默认） | 根据查询复杂度自动选择：简单 → 本地，复杂 → 云端 |
| `local` | 强制使用本地 qwen3:8b |
| `cloud` | 强制使用云端 gpt-5.5 |

**复杂度评估规则** (`estimate_complexity()`)：
- 长度 > 50 字符: +1
- 包含对比/分析关键词（对比、比较、划算、推荐、分析、投资等）: +2
- 包含投资/策略关键词（预算、ROI、翻转、利润等）: +2
- 多物品名（>2 个）: +1 per extra
- 阈值 >= 3 自动切换云端

#### 新增功能

**1. 统一 LLM 接口** (`warframe_agent/llm.py`)

| 函数 | 说明 |
|------|------|
| `chat_with_model(messages, model)` | 统一同步调用，支持 `model="local"\|"cloud"\|None(自动)` |
| `stream_chat_model(messages, model)` | 统一流式调用 |
| `_cloud_chat_sync(messages)` | 云端同步调用（OpenAI 兼容 API） |
| `_cloud_chat_stream(messages)` | 云端流式调用 |
| `estimate_complexity(message)` | 查询复杂度评估 |
| `should_use_cloud(message)` | 是否应使用云端模型 |

**2. 配置** (`warframe_agent/config.py`)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `CLOUD_API_BASE` | `https://gpt-agent.cc/v1` | 云端 API 地址 |
| `CLOUD_API_KEY` | 环境变量 | API 密钥 |
| `CLOUD_MODEL` | `gpt-5.5` | 云端模型名 |
| `MODEL_ROUTING` | `auto` | 路由策略 |
| `COMPLEXITY_THRESHOLD` | 3 | 复杂度阈值 |

**3. ChatAgent 集成**

- `_call_llm_messages()` 改用 `chat_with_model()` 自动路由
- `answer_stream()` 改用 `stream_chat_model()` 流式路由
- 云端调用失败时自动回退到本地模型

**4. 安全**

- API 密钥通过环境变量注入，`.env` 文件已加入 `.gitignore`
- 云端调用超时 60s（同步）/ 120s（流式）

#### 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `warframe_agent/config.py` | 新增云端模型配置（6 个配置项） |
| 修改 | `warframe_agent/llm.py` | 新增云端调用、复杂度评估、统一接口（~120 行） |
| 修改 | `warframe_agent/chat.py` | _call_llm_messages 和 stream 改用统一接口 |
| 新增 | `.env` | API 密钥（不入 git） |
| 修改 | `.gitignore` | 新增 .env |

**全部测试**: 409 passed

---

### Phase 39: 从领域助手到个人智能体 — 目标/扫描/深度分析/自学习 (v12.0)

**日期**: 2026-05-11
**核心目标**: 实施 P2-P5，让智能体具备自主目标管理、主动机会发现、深度分析、自学习闭环能力。

#### P2: 自主目标管理

**新增功能**：

| 功能 | 说明 |
|------|------|
| `/goal` | 查看当前所有活跃目标和进度 |
| `/goal set 描述` | 创建新交易目标（如"一周内赚500p"） |
| `/goal done ID` | 标记目标完成，自动生成复盘报告 |
| `/goal drop ID` | 放弃目标 |
| `/goal review ID` | 查看目标复盘（胜率、利润、最佳/最差交易） |
| `/goal rm ID` | 删除目标 |

**`GoalTracker` 类** (`warframe_agent/goals.py`)：
- 持久化存储到 `data/goals.json`
- 自动从 `trade_outcomes` 计算进度
- 生成复盘报告（胜率、累计利润、最佳/最差交易）

#### P3: 主动机会发现

**新增 `warframe_agent/scanner.py`**：

`OpportunityScanner` 类，检测以下异常：

| 检测类型 | 规则 | 严重程度 |
|----------|------|----------|
| 高价差 | 价差 > 30% | high/medium |
| 低挂单 | 卖价 < 均价 70% | high |
| 趋势反转 | 从下跌转上涨 + 高波动 | medium |
| 价格暴跌 | 当前价 < 7日均价 60% | high |

- `scan_item()` — 扫描单个物品
- `scan_batch()` — 批量扫描，按严重程度排序
- `format_opportunities()` — 格式化推送文本
- `generate_opportunity_push_text()` — WxPusher 推送文本

#### P4: 深度分析能力

**新增 `deep_analysis` 工具**：

- 用户说"深度分析XX"或"详细分析XX"时触发
- 收集多维度数据：当前价格、知识库统计、游戏数据、价格历史
- 调用云端 gpt-5.5 模型进行分析
- 输出 5 个维度：价格评估、趋势判断、风险评估、投资建议、操作建议
- 云端失败时自动回退本地模型

**工具路由** (`tool_router.py`)：
- `TOOL_SCHEMAS` 新增 `deep_analysis` schema
- `TOOLS` 新增 `deep_analysis` 条目

#### P5: 自学习闭环

**扩展 `warframe_agent/feedback.py`**：

| 函数 | 说明 |
|------|------|
| `discover_patterns()` | 用云端 LLM 从交易数据中发现新规律 |
| `update_pattern_confidence()` | 根据最新交易结果更新已有规律置信度 |
| `run_self_learning_cycle()` | 一轮完整闭环：发现新规律 + 更新置信度 |

**置信度机制**：
- 连续成功（胜率 > 70%）→ 提升置信度 +0.05
- 连续失败（胜率 < 30%）→ 降级置信度 -0.1
- 置信度 < 0.2 → 自动删除（不再注入 LLM）

**监控集成** (`warframe_agent/monitor.py`)：
- 每 `PATTERN_DISCOVERY_INTERVAL`（12）次扫描触发一轮自学习
- 使用云端模型分析，新规律自动存入 `memory.learned_patterns`

#### 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `warframe_agent/goals.py` | 新增 GoalTracker 类（持久化 + 复盘 + 进度追踪） |
| 修改 | `warframe_agent/chat.py` | 新增 /goal 命令 + deep_analysis 工具 + _deep_analysis 方法 |
| 新增 | `warframe_agent/scanner.py` | OpportunityScanner（价格异常检测） |
| 修改 | `warframe_agent/tool_router.py` | 新增 deep_analysis 工具 |
| 修改 | `warframe_agent/feedback.py` | 新增自学习闭环（模式提取 + 置信度更新） |
| 修改 | `warframe_agent/monitor.py` | 集成自学习周期 |

**全部测试**: 409 passed

---

### Phase 31: 虚空裂缝订阅 + Baro 购买推荐 + ReAct 修复

**日期**: 2026-05-11
**目标**: 新增事件订阅推送能力，修复 ReAct 工具调用链路。

#### 31.1 虚空裂缝订阅

**数据层** (`memory.py`)：
- 新增 `FissureAlert` dataclass（`node_pattern`, `mission_type`, `tier`, `hard`, `note`）
- `AgentMemory` 新增 `fissure_alerts` 字段 + `with_fissure_alert()` / `without_fissure_alert()` 方法

**解析层** (`events.py`)：
- 新增 `VoidFissure` dataclass（结构化数据：node, mission_type, tier, hard, activation, expiry）
- 新增 `parse_fissures(world_state)` 方法，从 `ActiveMissions` 数组解析
- 修复 MongoDB 日期格式 `{$date: {$numberLong: ...}}` 的解析
- `EventTracker` 存储 `_world_state`，新增 `get_active_fissures()` 方法

**命令层** (`chat.py`)：
- 新增 `/fissure add [过滤条件]` — 支持中文节点/任务类型/等级/钢铁模式
- `/fissure remove [序号]` / `/fissure list`
- 中文映射表：`_TIER_CHINESE`, `_MISSION_CHINESE`, `_NODE_CHINESE`

**监控层** (`monitor.py`)：
- `PriceMonitor._run()` 中新增 `_check_fissure_alerts()`
- 匹配逻辑：`FissureAlert.matches_fissure()` 子串匹配 + 精确匹配
- 去重：`_fissure_notified: dict[str, float]`，key = `(node, mission_type, tier, expiry)`
- 回调：`on_fissure(notification)` 推送到飞书/WebSocket

#### 31.2 Baro 购买推荐

**解析层** (`events.py`)：
- 修复 `VoidTraders`（复数，数组）vs `VoidTrader`（单数）兼容
- 解析 `PrimePrice`（杜卡特）和 `Price`（现金）字段
- 新增 `BaroItem` dataclass（`item_type`, `market_id`, `ducat_cost`, `credit_cost`）
- `GameEvent` 新增 `baro_items: list[BaroItem]` 字段
- 新增 `_build_item_type_map()` 映射 Baro ItemType → market_id

**分析器** (`baro.py`，新建)：
- `BaroRecommendation` dataclass
- `analyze_baro_inventory(baro_event)` — 推荐规则：`market_plat_price > ducat_cost / 3` → 值得买
- `format_baro_report()` — 格式化推送文本

**监控层** (`monitor.py`)：
- `_check_baro_recommendation()` — 检测 Baro 活跃时自动分析
- 去重：`_baro_recommendation_sent: str | None`（按 `start_time` 去重）

#### 31.3 ReAct 工具调用修复（3 个 Bug）

**Bug 1: `_react_model_call` 不传 tools 参数**
- `chat.py` 的 `_react_model_call` 调用 `chat_with_ollama`，后者不传 `tools=TOOL_SCHEMAS`
- 修复：改为调用 `tool_router._default_model_call`，该函数传递完整的工具 schema

**Bug 2: Ollama 原生 tool_calls 被丢弃**
- `_default_model_call` 只返回 `message.content`，Ollama 返回的 `message.tool_calls` 被丢弃
- 修复：将 `tool_calls` 序列化为 JSON 追加到 content 末尾，供 `_extract_tool_calls` 解析

**Bug 3: 交易查询被物品匹配拦截**
- "有什么 Mod 可以翻转赚钱" 中的 "Mod" 被 `_contexts_for_message` 匹配为物品，绕过路由器
- 修复：新增 `_is_trading_tool_query()` 关键词检测（翻转/投资/套装利润等），与 `_is_event_query` 同级处理
- 路由失败时返回提示而非 fallthrough 到物品匹配

#### 31.4 事件查询去污染

**问题**：查询"有没有钢铁的虚空裂缝歼灭"时，`_contexts_for_message("虚空")` 匹配到 `baro_void_signal`、`corpus_void_key` 等交易物品，导致回复中混入私聊命令。

**修复**：
- 新增 `_EVENT_KEYWORDS` 集合 + `_is_event_query()` 函数
- 事件类查询在 `answer()` 入口直接走路由器，跳过物品匹配
- `query_events` 工具新增 `type` 参数过滤（`void_fissure` / `baro_visit` / `invasion` / `void_storm`）
- ReAct 系统 prompt 增加约束：`query_events 结果只展示事件信息，不要混入交易数据`

#### 31.5 飞书去重

**问题**：多个飞书 worker 子进程同时运行，导致消息无限循环。

**修复** (`feishu.py`)：
- `start()` 方法新增 `_kill_old_workers()` 调用
- 通过 `wmic` 查找含 `lark_oapi` + `P2ImMessageReceiveV1` 的进程并杀掉

#### 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `warframe_agent/memory.py` | 新增 FissureAlert + 裂缝订阅 CRUD |
| 修改 | `warframe_agent/events.py` | VoidFissure + BaroItem + parse_fissures + Baro 修复 |
| 新增 | `warframe_agent/baro.py` | Baro 购买推荐分析器 |
| 修改 | `warframe_agent/chat.py` | /fissure 命令 + _is_trading_tool_query + _is_event_query + 修复 investment_advisor 导入 |
| 修改 | `warframe_agent/tool_router.py` | 修复 _default_model_call 保留 tool_calls + query_events type 参数 |
| 修改 | `warframe_agent/monitor.py` | 裂缝检查 + Baro 推荐 + 回调 |
| 修改 | `warframe_agent/feishu.py` | _kill_old_workers 去重 |
| 修改 | `warframe_agent/web/app.py` | on_fissure / on_baro_recommendation 回调接线 |
| 修改 | `md/FeishuUserGuide.md` | 新增裂缝订阅 + Baro 购买推荐文档 |

**全部测试**: 409 passed

---

### Phase 32: Agent 能力补全 — 5 阶段系统性升级 (v14.0)

按计划分 5 个阶段系统性补全 Agent 缺失能力，每阶段独立可交付。

#### Phase 1: API 缓存优化

**目标**：交易工具响应时间从 120s+ 降到 10s 以内。

| 文件 | 变更 |
|------|------|
| `config.py` | 新增 `ORDER_CACHE_TTL=60`, `STATS_CACHE_TTL=300`, `CACHE_MAX_SIZE=200` |
| `market.py` | `fetch_item_statistics` 新增 LRU 缓存（300s TTL）|
| `mod_flipper.py` | `scan_all_mod_flips` 并行化（`ThreadPoolExecutor(max_workers=8)`）|
| `set_profit.py` | `scan_all_set_profits` 并行化（`ThreadPoolExecutor(max_workers=6)`）|

**效果**：`set_profit` 冷启动 38.8s → 热缓存 0.0s

#### Phase 2: 交易记录自动追踪

**目标**：用户说"我刚买了充沛 80p"自动记录，支持盈亏统计。

| 文件 | 变更 |
|------|------|
| `trade_intent.py` | 新增 `detect_completed_trade()` + 已完成交易关键词 |
| `chat.py` | `/trade list/stats/add/undo` 命令 + `_auto_record_trade()` 自动检测 |

#### Phase 3: 遗物查询 + 裂缝智能推荐

**目标**：用户问"哪里掉犀牛 Prime 蓝图"能回答，并关联当前裂缝。

| 文件 | 变更 |
|------|------|
| `relics.py`（新建）| `RelicDB` 遗物掉落数据库，加载 ExportRelicArcane_en.json，构建 part→relic 索引 |
| `chat.py` | `/relic` 命令（部件查找 + 遗物查找 + 裂缝关联）|
| `events.py` | `get_vault_status()` + `get_vaulted_item_ids()` |

**关键修复**：原始数据同一遗物有 4 条记录（不同精炼等级），通过 `seen_relics` 去重。

#### Phase 4: 主动推送增强 + 价格预测

| 文件 | 变更 |
|------|------|
| `monitor.py` | `_check_price_spikes()` 3h 内涨跌>20% 预警 + `_check_event_driven_push()` Vault/PA 推送 |
| `price_history.py` | `predict_trend()` 增强：R² 置信度 + 价格区间 + 事件修正因子 |
| `strategies.py`（新建）| 3 个预设策略（低风险赋能翻转/中风险 Prime 拆件/高风险 Vault 投机）|
| `chat.py` | 趋势查询确定性回答 + `/strategy` 命令 |

#### Phase 5: 多物品对比 + 飞书卡片 + 错误处理

| 文件 | 变更 |
|------|------|
| `trade_intent.py` | `detect_compare_query()` 对比查询检测 |
| `chat.py` | `_render_comparison_table()` 多物品对比表格 + `/vault` 命令 |
| `feishu.py` | `send_card()` + `reply_card()` + `build_price_card()` 飞书卡片消息 |
| `set_profit.py` | silent exceptions → `logger.debug()` |
| `mod_flipper.py` | 同上 |
| `investment.py` | 同上 |
| `monitor.py` | 修复 `import time` 缺失 |

#### 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `warframe_agent/config.py` | 缓存 TTL 常量 |
| 修改 | `warframe_agent/market.py` | fetch_item_statistics 缓存 |
| 修改 | `warframe_agent/mod_flipper.py` | 并行化 + 日志 |
| 修改 | `warframe_agent/set_profit.py` | 并行化 + 日志 |
| 修改 | `warframe_agent/trade_intent.py` | 已完成交易 + 趋势 + 对比检测 |
| 修改 | `warframe_agent/chat.py` | /trade /relic /strategy /vault + 趋势预测 + 对比表格 |
| 修改 | `warframe_agent/price_history.py` | predict_trend 增强 |
| 修改 | `warframe_agent/monitor.py` | 价格突变 + 事件推送 + import time 修复 |
| 修改 | `warframe_agent/events.py` | Vault 解析 + get_vault_status |
| 修改 | `warframe_agent/investment.py` | 日志 |
| 修改 | `warframe_agent/feishu.py` | 卡片消息 + ReplyMessageRequest 导入 |
| 新增 | `warframe_agent/relics.py` | 遗物掉落数据库 |
| 新增 | `warframe_agent/strategies.py` | 交易策略模板 |
| 新增 | `tests/test_relics.py` | 遗物模块测试（30 个）|

**全部测试**: 439 passed（+30 新增）

---

### Phase 33: 多模型协作 — 降低 API 封禁风险 (v15.0)

**背景**：三大扫描工具每次全量扫描产生 ~350 次 warframe.market API 调用，8 线程并发 + 无锁速率限制器 = 实际请求率可能突破 3 req/s 上限，长期运行存在 IP 封禁风险。

**核心思路**：利用云端 LLM 的"世界知识"做智能预筛选，大幅减少实际 API 调用量。

#### Phase 1: 速率限制器修复

| 文件 | 变更 |
|------|------|
| `market.py` | `threading.Lock()` 保护全局时间戳 + 随机抖动 `0.34 + random(0, 0.1)` + HTTP 429 指数退避（最大 30s）|
| `tests/test_market_client.py` | mock Response 添加 `status_code = 200` |

#### Phase 2: 多模型智能预筛选

| 文件 | 变更 |
|------|------|
| `scout.py`（新建）| Scout 预筛选模块：三模型并行分工 |
| `config.py` | `SCOUT_MODELS` 模型分配 + `SCOUT_CACHE_TTL=600` + `SCOUT_MAX_CANDIDATES` |
| `mod_flipper.py` | `scan_all_mod_flips` 新增 `scout_fn` 参数 |
| `set_profit.py` | `scan_all_set_profits` 新增 `scout_fn` 参数 |
| `investment.py` | `scan_prime_investments` 新增 `scout_fn` 参数 |
| `chat.py` | 三处扫描调用点传入对应 scout 函数 |
| `goals.py` | 9 处扫描调用点传入 scout 函数 |
| `web/app.py` | 3 个 API endpoint 传入 scout 函数 |
| `tests/test_scout.py`（新建）| 23 个测试：JSON 解析、摘要构建、缓存、模型路由 |

**模型分配**：
| 扫描类型 | 云端模型 | 原始候选 | 预筛选后 | API 调用减少 |
|---|---|---|---|---|
| Mod 翻转 | kimi-k2.6 | 40 | 10 | 80 → 20 |
| 套装利润 | glm-5.1 | 15 | 5 | 90 → 30 |
| 投资顾问 | gpt-5.5 | 30 | 8 | 180 → 48 |
| **合计** | | | | **350 → ~98**（-72%）|

#### Phase 3: SQLite 持久化缓存

| 文件 | 变更 |
|------|------|
| `market.py` | `data/price_cache.db` SQLite 持久化 + `warm_persistent_cache()` 启动预热 + `_persistent_get/set` 二级缓存 |

**效果**：跨会话共享缓存，重启不丢失。内存缓存 → SQLite 缓存 → API 调用，三级回退。

#### Phase 4: 推理增强

| 文件 | 变更 |
|------|------|
| `scout.py` | `get_event_context()` 事件感知（Baro/Vault/PA）+ `get_user_preferences()` 用户偏好注入 + `get_price_trends()` 价格趋势 + `record_scout_feedback()` 反馈追踪 |

**关键修复**：
- `_detect_base_id` 中 COMMON_WARFRAME_ALIASES 分支添加价格查询关键词检测（"一套"/"多少钱"等），修复 "毒妈一套多少钱" 返回 None
- `_summarize_orders` 添加离线最低价兜底，修复无在线卖家时显示"暂无"

**全部测试**: 462 passed（+23 新增）

**文档版本**：v14.0
**最后更新**：2026-05-11
