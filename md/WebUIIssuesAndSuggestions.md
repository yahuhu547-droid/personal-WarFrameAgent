# Web UI 功能问题与改进建议

**扫描时间**: 2026-05-15
**扫描方法**: Playwright 自动化 + 代码审查
**扫描范围**: 所有 Web UI 功能面板

---

## 一、核心发现

### 已完成功能（正常工作）

| 功能模块 | 状态 | 说明 |
|---------|------|------|
| 主页加载 | ✅ | 所有元素正确渲染 |
| 聊天发送 | ✅ | Mock WebSocket 正常 |
| 收藏列表 | ✅ | 加载正常 |
| 提醒列表 | ✅ | 加载正常 |
| API 端点 | ✅ | 60+ 个端点正常 |

### 发现的问题

| 问题 | 严重度 | 影响 |
|------|--------|------|
| 欢迎弹窗阻挡操作 | 🔴 高 | 首次访问无法使用 |
| favicon.ico 缺失 | 🟡 中 | 5个404控制台错误 |
| 移动端溢出 | 🟡 中 | 小屏幕体验差 |
| API 错误无提示 | 🟢 低 | 用户不知道请求失败 |

---

## 二、严重问题详情

### 问题 1: 欢迎模态弹窗阻挡所有交互 🔴

**文件位置**: `warframe_agent/web/static/index.html` 第 249-270 行

**问题现象**:
- 首次访问时弹窗覆盖整个页面
- 无法点击聊天输入框、侧边栏按钮等
- Playwright 测试显示 `<div id="welcome-modal" class="modal active">` 阻挡所有指针事件

**根因代码**:
```javascript
function checkFirstVisit() {
    const visited = localStorage.getItem('warframe_visited');
    if (!visited) {
        showWelcomeModal(); // 无条件显示弹窗
    }
}
```

**建议修复**:

```javascript
// 方案1: 添加跳过按钮
function showWelcomeModal() {
    // ... 现有逻辑 ...

    // 添加跳过选项
    const skipBtn = document.createElement('button');
    skipBtn.textContent = '跳过';
    skipBtn.className = 'skip-btn';
    skipBtn.onclick = () => closeModal();
    modal.querySelector('.modal-content').appendChild(skipBtn);
}

// 方案2: ESC 键关闭
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.getElementById('welcome-modal');
        if (modal.classList.contains('active')) {
            modal.classList.remove('active');
            localStorage.setItem('warframe_visited', 'true');
        }
    }
});

// 方案3: 10秒自动关闭
setTimeout(() => {
    const modal = document.getElementById('welcome-modal');
    if (modal.classList.contains('active')) {
        modal.classList.remove('active');
        localStorage.setItem('warframe_visited', 'true');
    }
}, 10000);
```

---

### 问题 2: favicon.ico 缺失 🟡

**文件位置**: `warframe_agent/web/static/index.html` 第 30 行

**问题代码**:
```html
<link rel="icon" type="image/x-icon" href="/static/favicon.ico">
```

**缺失文件**: `warframe_agent/web/static/favicon.ico`

**建议修复**:
1. 创建简单的 favicon.ico（可以是占位符）
2. 或使用 SVG 内联 favicon:
```html
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
```
3. 或删除该行引用

---

## 三、建议新增功能

### 高优先级功能

#### 1. 跳过欢迎弹窗选项
- **描述**: 添加"跳过"按钮或 ESC 键关闭弹窗
- **影响**: 提升首次访问体验
- **工时**: 2h

#### 2. 移动端抽屉式侧边栏
- **描述**: 小屏幕（<768px）使用滑动抽屉替代固定侧边栏
- **代码示例**:
```javascript
function initMobileSidebar() {
    if (window.innerWidth < 768) {
        document.getElementById('sidebar').classList.add('drawer');
        // 添加汉堡菜单按钮
    }
}
```
- **工时**: 4h

#### 3. API 错误 Toast 提示
- **描述**: 网络请求失败时显示错误提示
- **代码示例**:
```javascript
async function safeFetch(url, options) {
    try {
        const res = await fetch(url, options);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (err) {
        showToast('请求失败: ' + err.message, 'error');
        return null;
    }
}
```
- **工时**: 2h

#### 4. 价格变动闪烁动画
- **描述**: 价格变化时添加闪烁效果提示用户
- **工时**: 1h

---

### 中优先级功能

#### 5. 加载骨架屏
- **描述**: API 加载时显示占位符，而非空白
- **工时**: 3h

#### 6. 聊天历史自动保存
- **描述**: 限制 localStorage 存储量，避免无限增长
- **代码**:
```javascript
const MAX_HISTORY = 50;
function saveChatHistory() {
    const messages = getCurrentMessages();
    const trimmed = messages.slice(-MAX_HISTORY);
    localStorage.setItem('chat_history', JSON.stringify(trimmed));
}
```
- **工时**: 1h

#### 7. 离线模式
- **描述**: 网络断开时显示缓存数据
- **工时**: 6h

#### 8. 深色/浅色主题自动切换
- **描述**: 根据系统偏好自动选择主题
- **代码**:
```javascript
function initTheme() {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.body.classList.toggle('dark', prefersDark);
}
```
- **工时**: 1h

---

### 低优先级功能

| 功能 | 说明 | 工时 |
|------|------|------|
| 手势滑动支持 | 移动端滑动手势 | 2h |
| 通知权限引导 | 首次访问引导开启通知 | 1h |
| 快捷键提示 | 显示常用快捷键 | 1h |
| PWA 支持 | 可安装为桌面应用 | 8h |
| 搜索历史 | 保存搜索记录 | 2h |

---

## 四、现有测试覆盖

| 测试文件 | 测试数 | 通过 | 覆盖功能 |
|---------|--------|------|---------|
| `tests/test_web_ui_playwright.py` | 2 | ✅ | XSS防护、聊天、更多菜单 |
| `tests/test_web_api.py` | 7 | ? | API端点 |

**注意**: 现有测试在测试前设置了 `localStorage.setItem('warframe_visited', 'true')`，所以能通过。需要补充首次访问场景的测试。

---

## 五、功能优先级矩阵

| 功能 | 优先级 | 工时 | 影响用户 |
|------|--------|------|---------|
| 跳过欢迎弹窗 | 🔴 高 | 2h | 首次用户 |
| 修复 favicon | 🟡 中 | 0.5h | 所有用户 |
| 移动端抽屉 | 🟡 中 | 4h | 移动用户 |
| API 错误提示 | 🟡 中 | 2h | 所有用户 |
| 加载骨架屏 | 🟢 低 | 3h | 所有用户 |
| 离线模式 | 🟢 低 | 6h | 断网用户 |

---

## 六、建议实施计划

### 第一周（16h）
1. 添加欢迎弹窗跳过按钮（2h）
2. 修复 favicon 缺失（0.5h）
3. 添加 ESC 键关闭弹窗（0.5h）
4. 移动端抽屉式侧边栏（4h）
5. API 错误 Toast 提示（2h）
6. 价格变动闪烁动画（1h）

### 第二周（10h）
7. 加载骨架屏（3h）
8. 聊天历史自动清理（1h）
9. 深色/浅色主题自动切换（1h）
10. 通知权限引导（1h）

### 第三周及以后（16h+）
11. 离线模式支持（6h）
12. PWA 支持（8h）
13. 手势滑动支持（2h）

---

## 七、关键文件参考

| 文件 | 说明 |
|------|------|
| `warframe_agent/web/static/index.html` | 欢迎弹窗位置（第249-270行） |
| `warframe_agent/web/static/js/app.js` | 弹窗控制逻辑（第281-320行） |
| `warframe_agent/web/static/css/responsive.css` | 响应式样式 |
| `warframe_agent/web/static/js/sidebar.js` | 侧边栏逻辑 |
| `warframe_agent/web/static/js/chat.js` | 聊天功能 |
| `tests/test_web_ui_playwright.py` | Playwright 测试 |

---

## 八、截图记录

| 文件 | 说明 |
|------|------|
| `md/test_screenshots/01_homepage.png` | 桌面端主页 |
| `md/test_screenshots/05_mobile_view.png` | 移动端（375px宽） |

---

**报告生成时间**: 2026-05-15 14:25