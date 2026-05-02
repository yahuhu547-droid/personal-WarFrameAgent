/* ============================================
   Warframe Trading Agent - Main Application
   Tenno 科技终端主逻辑 v3.0
   ============================================ */

const API_BASE = '';

// ===== API 调用函数 =====

async function fetchMemory() {
    const res = await fetch(`${API_BASE}/api/memory`);
    return await res.json();
}

async function sendChat(message) {
    const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    });
    return await res.json();
}

async function addFavorite(itemId) {
    const res = await fetch(`${API_BASE}/api/fav`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId })
    });
    return await res.json();
}

async function removeFavorite(itemId) {
    const res = await fetch(`${API_BASE}/api/fav`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId })
    });
    return await res.json();
}

async function addAlert(itemId, direction, price) {
    const res = await fetch(`${API_BASE}/api/alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, direction, price })
    });
    return await res.json();
}

async function removeAlertApi(itemId, direction, price) {
    const res = await fetch(`${API_BASE}/api/alert`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, direction, price })
    });
    return await res.json();
}

async function getHistory(itemId) {
    const res = await fetch(`${API_BASE}/api/history/${itemId}`);
    return await res.json();
}

async function compareItems(items) {
    const res = await fetch(`${API_BASE}/api/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(items)
    });
    return await res.json();
}

// ===== 通知系统 =====

function showNotification(message, type = 'info') {
    if (Notification.permission === 'granted') {
        new Notification('Warframe 交易提醒', {
            body: message,
            icon: '/static/images/icon.png'
        });
    }
    showToast(message, type);
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1100;
            display: flex;
            flex-direction: column;
            gap: 8px;
        `;
        document.body.appendChild(container);
    }

    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===== 主题切换 =====

function initTheme() {
    const saved = localStorage.getItem('warframe_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('warframe_theme', next);
    updateThemeIcon(next);
    showToast(`已切换为${next === 'dark' ? '暗色' : '亮色'}主题`, 'info');
}

function updateThemeIcon(theme) {
    const icon = document.querySelector('#theme-toggle .theme-icon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '🌙' : '☀️';
    }
}

// ===== WebSocket 连接（指数退避） =====

let wsReconnectDelay = 1000;
const WS_MAX_DELAY = 30000;

function setupWebSocket() {
    // 标签页不可见时不连接
    if (document.visibilityState === 'hidden') {
        document.addEventListener('visibilitychange', function onVis() {
            if (document.visibilityState === 'visible') {
                document.removeEventListener('visibilitychange', onVis);
                setupWebSocket();
            }
        });
        return;
    }

    try {
        const ws = new WebSocket(`ws://${location.host}/ws/notifications`);

        ws.onopen = () => {
            console.log('通知 WebSocket 已连接');
            wsReconnectDelay = 1000;
            updateSidebarStatus('online');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'alert') {
                const msg = `${data.item}: 当前 ${data.current_price}p (${data.direction} ${data.price}p)`;
                showNotification(msg, 'warning');
                addChatMessage('system', msg);
                loadSidebar();
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket 错误:', error);
            updateSidebarStatus('error');
        };

        ws.onclose = () => {
            console.log(`WebSocket 断开，${wsReconnectDelay / 1000}s 后重连`);
            setTimeout(() => {
                wsReconnectDelay = Math.min(wsReconnectDelay * 2, WS_MAX_DELAY);
                setupWebSocket();
            }, wsReconnectDelay);
        };
    } catch (error) {
        console.error('WebSocket 连接失败:', error);
        setTimeout(setupWebSocket, wsReconnectDelay);
    }
}

// ===== 首次访问引导 =====

function checkFirstVisit() {
    const visited = localStorage.getItem('warframe_visited');
    if (!visited) {
        showWelcomeModal();
    }
}

function showWelcomeModal() {
    const modal = document.getElementById('welcome-modal');
    modal.classList.add('active');

    let selectedPlatform = 'pc';

    document.querySelectorAll('.platform-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.platform-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            selectedPlatform = btn.dataset.platform;
        });
    });

    document.getElementById('start-btn').addEventListener('click', async () => {
        try {
            await fetch(`${API_BASE}/api/pref`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: 'platform', value: selectedPlatform })
            });

            localStorage.setItem('warframe_visited', 'true');
            modal.classList.remove('active');

            addChatMessage('system', `欢迎使用 Warframe 交易助手！已设置平台为 ${selectedPlatform.toUpperCase()}。`);
            addChatMessage('agent', '你好，Tenno！我是你的交易助手。可以问我任何关于 Warframe 物品价格的问题。\n\n**快速开始：**\n- 直接输入物品名查询价格\n- 使用 `/fav add 物品名` 添加收藏\n- 使用 `/alert add 物品名 below 40` 设置提醒');
        } catch (error) {
            console.error('保存偏好失败:', error);
            showToast('保存偏好失败，请重试', 'error');
        }
    });
}

// ===== 初始化 =====

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    loadSidebar();
    setupWebSocket();
    checkFirstVisit();
    addLoadingAnimations();
    initSettings();
    initCommandPalette();
    initKeyboardShortcuts();
    initResizeHandles();

    // 主题切换按钮
    document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);

    // 设置按钮
    document.getElementById('settings-btn')?.addEventListener('click', () => {
        document.getElementById('settings-modal').classList.add('active');
    });
});

function addLoadingAnimations() {
    const elements = document.querySelectorAll('.sidebar, .chat-area, .detail-panel');
    elements.forEach((el, index) => {
        el.style.opacity = '0';
        el.style.animation = `fadeInUp 0.6s ease-out ${index * 0.1}s forwards`;
    });
}

// ===== 设置系统 =====

const SETTINGS_KEY = 'warframe_settings';
let appSettings = {
    browserNotify: true,
    soundEnabled: true,
    showPriceChange: true
};

function initSettings() {
    try {
        const saved = localStorage.getItem(SETTINGS_KEY);
        if (saved) Object.assign(appSettings, JSON.parse(saved));
    } catch (e) {}

    // 绑定设置控件
    const browserNotify = document.getElementById('setting-browser-notify');
    const soundEnabled = document.getElementById('setting-sound');
    const priceChange = document.getElementById('setting-price-change');

    if (browserNotify) {
        browserNotify.checked = appSettings.browserNotify;
        browserNotify.addEventListener('change', () => {
            appSettings.browserNotify = browserNotify.checked;
            saveSettings();
            if (appSettings.browserNotify && Notification.permission === 'default') {
                Notification.requestPermission();
            }
        });
    }

    if (soundEnabled) {
        soundEnabled.checked = appSettings.soundEnabled;
        soundEnabled.addEventListener('change', () => {
            appSettings.soundEnabled = soundEnabled.checked;
            saveSettings();
        });
    }

    if (priceChange) {
        priceChange.checked = appSettings.showPriceChange;
        priceChange.addEventListener('change', () => {
            appSettings.showPriceChange = priceChange.checked;
            saveSettings();
        });
    }
}

function saveSettings() {
    try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(appSettings));
    } catch (e) {}
}

// ===== 命令面板 =====

const COMMANDS = [
    { name: '充沛价格', action: () => { chatInput.value = '充沛多少钱'; handleSend(); } },
    { name: '扫描关注', action: () => { chatInput.value = '扫描关注'; handleSend(); } },
    { name: '查看记忆', action: () => { chatInput.value = '/memory'; handleSend(); } },
    { name: '对比物品', action: () => handleCompare() },
    { name: '每日报告', action: () => document.getElementById('report-btn')?.click() },
    { name: '切换主题', action: () => toggleTheme() },
    { name: '清空对话', action: () => clearChatHistory() },
    { name: '打开设置', action: () => document.getElementById('settings-modal')?.classList.add('active') },
    { name: '快捷键帮助', action: () => document.getElementById('shortcuts-modal')?.classList.add('active') },
    { name: '收藏物品', action: () => { chatInput.value = '/fav add '; chatInput.focus(); } },
    { name: '添加提醒', action: () => { chatInput.value = '/alert add '; chatInput.focus(); } },
    { name: '管理别名', action: () => { document.getElementById('alias-modal')?.classList.add('active'); loadAliases(); } },
];

function initCommandPalette() {
    const modal = document.getElementById('command-modal');
    const input = document.getElementById('command-input');
    const list = document.getElementById('command-list');
    if (!modal || !input || !list) return;

    function filterCommands(query) {
        const q = query.toLowerCase();
        return COMMANDS.filter(cmd => cmd.name.toLowerCase().includes(q));
    }

    function renderCommands(commands) {
        list.innerHTML = commands.map((cmd, i) => `
            <div class="command-item ${i === 0 ? 'selected' : ''}" data-index="${i}">
                ${cmd.name}
            </div>
        `).join('');

        list.querySelectorAll('.command-item').forEach((el, i) => {
            el.addEventListener('click', () => {
                commands[i].action();
                modal.classList.remove('active');
                input.value = '';
            });
        });
    }

    input.addEventListener('input', () => {
        renderCommands(filterCommands(input.value));
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            modal.classList.remove('active');
            input.value = '';
        }
        if (e.key === 'Enter') {
            const selected = list.querySelector('.command-item.selected');
            if (selected) selected.click();
        }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            const items = list.querySelectorAll('.command-item');
            const current = list.querySelector('.command-item.selected');
            let idx = Array.from(items).indexOf(current);
            items.forEach(el => el.classList.remove('selected'));
            if (e.key === 'ArrowDown') idx = (idx + 1) % items.length;
            else idx = (idx - 1 + items.length) % items.length;
            items[idx]?.classList.add('selected');
            items[idx]?.scrollIntoView({ block: 'nearest' });
        }
    });

    // 点击遮罩关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
            input.value = '';
        }
    });

    renderCommands(COMMANDS);
}

// ===== 键盘快捷键 =====

function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+P: 命令面板
        if (e.ctrlKey && e.key === 'p') {
            e.preventDefault();
            const modal = document.getElementById('command-modal');
            const input = document.getElementById('command-input');
            if (modal) {
                modal.classList.add('active');
                setTimeout(() => input?.focus(), 100);
            }
            return;
        }

        // Ctrl+/: 快捷键帮助
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            document.getElementById('shortcuts-modal')?.classList.add('active');
            return;
        }

        // 数字键 1-4: 触发快捷按钮（输入框未聚焦时）
        if (!e.ctrlKey && !e.altKey && !e.shiftKey && document.activeElement !== chatInput) {
            const num = parseInt(e.key);
            if (num >= 1 && num <= 4) {
                const btns = document.querySelectorAll('.quick-btn');
                if (btns[num - 1]) btns[num - 1].click();
            }
        }
    });
}

// ===== 布局拖拽调整 =====

const LAYOUT_KEY = 'warframe_layout';

function initResizeHandles() {
    const sidebarHandle = document.getElementById('resize-sidebar');
    const detailHandle = document.getElementById('resize-detail');
    const sidebar = document.getElementById('sidebar');
    const detailPanel = document.getElementById('detail-panel');

    if (!sidebarHandle || !detailHandle || !sidebar || !detailPanel) return;

    // 恢复保存的宽度
    try {
        const saved = localStorage.getItem(LAYOUT_KEY);
        if (saved) {
            const layout = JSON.parse(saved);
            if (layout.sidebar) sidebar.style.width = layout.sidebar;
            if (layout.detail) detailPanel.style.width = layout.detail;
        }
    } catch (e) {}

    function startResize(handle, target, direction) {
        let startX, startWidth;

        function onMouseDown(e) {
            e.preventDefault();
            startX = e.clientX;
            startWidth = target.offsetWidth;
            handle.classList.add('active');
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        }

        function onMouseMove(e) {
            const dx = e.clientX - startX;
            const newWidth = direction === 'right' ? startWidth + dx : startWidth - dx;
            const clamped = Math.max(200, Math.min(500, newWidth));
            target.style.width = clamped + 'px';
        }

        function onMouseUp() {
            handle.classList.remove('active');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            saveLayout();
        }

        handle.addEventListener('mousedown', onMouseDown);
    }

    function saveLayout() {
        try {
            localStorage.setItem(LAYOUT_KEY, JSON.stringify({
                sidebar: sidebar.style.width,
                detail: detailPanel.style.width
            }));
        } catch (e) {}
    }

    startResize(sidebarHandle, sidebar, 'right');
    startResize(detailHandle, detailPanel, 'left');
}

// ===== 工具函数 =====

function formatPrice(price) {
    if (price === null || price === undefined) return '无';
    return `${price}p`;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ===== 样式注入 =====

const style = document.createElement('style');
style.textContent = `
    .toast {
        padding: 12px 20px;
        border-radius: 4px;
        font-family: var(--font-body);
        font-size: var(--text-sm);
        letter-spacing: var(--tracking-wide);
        transform: translateX(100%);
        opacity: 0;
        transition: all 0.3s ease-out;
        max-width: 300px;
    }

    .toast.show {
        transform: translateX(0);
        opacity: 1;
    }

    .toast-info {
        background: rgba(74, 158, 255, 0.2);
        border: 1px solid rgba(74, 158, 255, 0.3);
        color: var(--blue-primary);
    }

    .toast-success {
        background: rgba(74, 222, 128, 0.2);
        border: 1px solid rgba(74, 222, 128, 0.3);
        color: var(--green-success);
    }

    .toast-warning {
        background: rgba(245, 158, 11, 0.2);
        border: 1px solid rgba(245, 158, 11, 0.3);
        color: var(--orange-warning);
    }

    .toast-error {
        background: rgba(239, 68, 68, 0.2);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: var(--red-error);
    }

    .sidebar-actions {
        display: flex;
        gap: 6px;
        margin-bottom: 10px;
    }

    .sidebar-btn {
        flex: 1;
        padding: 6px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s ease-out;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .sidebar-btn:hover {
        background: rgba(212, 167, 55, 0.1);
        border-color: rgba(212, 167, 55, 0.3);
        transform: translateY(-1px);
    }

    [data-theme="light"] {
        --bg-primary: #f5f5f5;
        --bg-secondary: #ffffff;
        --bg-tertiary: #e8e8e8;
        --text-primary: #1a1a1a;
        --text-secondary: #4a4a4a;
        --text-tertiary: #888888;
        --gold-primary: #b8860b;
        --blue-primary: #2563eb;
    }

    [data-theme="light"] .sidebar {
        background: linear-gradient(180deg, #ffffff, #f8f8f8);
        border-right-color: rgba(184, 134, 11, 0.2);
    }

    [data-theme="light"] .chat-area {
        background: #f5f5f5;
    }

    [data-theme="light"] .message.user .message-content {
        background: rgba(37, 99, 235, 0.1);
        border-color: rgba(37, 99, 235, 0.2);
    }

    [data-theme="light"] .message.agent .message-content {
        background: rgba(0, 0, 0, 0.03);
        border-color: rgba(0, 0, 0, 0.08);
    }

    [data-theme="light"] .input-wrapper input {
        background: #ffffff;
        border-color: rgba(0, 0, 0, 0.15);
        color: #1a1a1a;
    }

    [data-theme="light"] .detail-panel {
        background: linear-gradient(180deg, #ffffff, #f8f8f8);
        border-left-color: rgba(184, 134, 11, 0.2);
    }

    [data-theme="light"] .list-item {
        background: rgba(0, 0, 0, 0.02);
        border-color: rgba(0, 0, 0, 0.06);
    }

    [data-theme="light"] .list-item:hover {
        background: rgba(184, 134, 11, 0.05);
    }

    /* 设置模态框 */
    .settings-modal-content,
    .shortcuts-modal-content {
        max-width: 400px;
    }

    .modal-close-btn {
        position: absolute;
        top: 12px;
        right: 16px;
        background: none;
        border: none;
        color: var(--text-tertiary);
        font-size: 24px;
        cursor: pointer;
        transition: color 0.2s;
        z-index: 10;
    }

    .modal-close-btn:hover {
        color: var(--gold-primary);
    }

    .settings-group {
        margin-bottom: 20px;
    }

    .settings-group h3 {
        font-family: var(--font-display);
        font-size: 12px;
        color: var(--gold-primary);
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 12px;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(212, 167, 55, 0.2);
    }

    .setting-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        cursor: pointer;
    }

    .setting-label {
        font-size: 14px;
        color: var(--text-secondary);
    }

    .setting-toggle {
        appearance: none;
        width: 40px;
        height: 22px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 11px;
        position: relative;
        cursor: pointer;
        transition: background 0.3s;
    }

    .setting-toggle::before {
        content: '';
        position: absolute;
        top: 3px;
        left: 3px;
        width: 16px;
        height: 16px;
        background: var(--text-tertiary);
        border-radius: 50%;
        transition: all 0.3s;
    }

    .setting-toggle:checked {
        background: rgba(74, 158, 255, 0.3);
    }

    .setting-toggle:checked::before {
        left: 21px;
        background: var(--blue-primary);
    }

    /* 快捷键帮助 */
    .shortcuts-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .shortcut-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
    }

    .shortcut-item kbd {
        font-family: var(--font-mono);
        font-size: 11px;
        padding: 3px 8px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 3px;
        color: var(--gold-primary);
    }

    .shortcut-item span {
        font-size: 13px;
        color: var(--text-secondary);
    }

    /* 命令面板 */
    .command-modal-content {
        max-width: 500px;
        padding: 0;
        overflow: hidden;
    }

    #command-input {
        width: 100%;
        padding: 16px 20px;
        background: transparent;
        border: none;
        border-bottom: 1px solid rgba(212, 167, 55, 0.2);
        color: var(--text-primary);
        font-family: var(--font-body);
        font-size: 16px;
        outline: none;
    }

    #command-input::placeholder {
        color: var(--text-tertiary);
    }

    .command-list {
        max-height: 300px;
        overflow-y: auto;
    }

    .command-item {
        padding: 10px 20px;
        font-size: 14px;
        color: var(--text-secondary);
        cursor: pointer;
        transition: all 0.15s ease-out;
    }

    .command-item:hover,
    .command-item.selected {
        background: rgba(212, 167, 55, 0.1);
        color: var(--gold-primary);
    }

    /* 拖拽分割线 */
    .resize-handle {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 4px;
        cursor: col-resize;
        z-index: 10;
        transition: background 0.2s;
    }

    .resize-handle:hover {
        background: var(--gold-primary);
    }

    .resize-handle.active {
        background: var(--gold-primary);
    }

    /* 自定义快捷按钮 */
    .quick-btn.custom-quick-btn {
        position: relative;
    }

    .custom-quick-btn .remove-quick-btn {
        display: none;
        position: absolute;
        top: -4px;
        right: -4px;
        width: 16px;
        height: 16px;
        background: var(--red-error);
        border: none;
        border-radius: 50%;
        color: white;
        font-size: 10px;
        cursor: pointer;
        align-items: center;
        justify-content: center;
        line-height: 1;
    }

    .custom-quick-btn:hover .remove-quick-btn {
        display: flex;
    }

    .add-quick-btn {
        padding: 6px 12px;
        background: rgba(74, 222, 128, 0.1);
        border: 1px dashed rgba(74, 222, 128, 0.3);
        border-radius: 4px;
        color: var(--green-success);
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .add-quick-btn:hover {
        background: rgba(74, 222, 128, 0.2);
    }

    /* 别名管理模态框 */
    .alias-modal-content {
        max-width: 500px;
    }

    .alias-desc {
        font-size: 13px;
        color: var(--text-tertiary);
        margin-bottom: 16px;
    }

    .alias-add-section {
        margin-bottom: 16px;
    }

    .alias-add-row {
        margin-bottom: 8px;
    }

    .alias-add-row input,
    .alias-search-row input {
        width: 100%;
        padding: 8px 12px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        color: var(--text-primary);
        font-family: var(--font-body);
        font-size: 13px;
        outline: none;
        transition: border-color 0.2s;
        box-sizing: border-box;
    }

    .alias-add-row input:focus,
    .alias-search-row input:focus {
        border-color: var(--gold-primary);
    }

    .alias-add-row input::placeholder,
    .alias-search-row input::placeholder {
        color: var(--text-tertiary);
    }

    .alias-search-row {
        margin-bottom: 8px;
    }

    .alias-search-wrapper {
        position: relative;
    }

    .alias-search-results {
        display: none;
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: rgba(12, 15, 25, 0.98);
        border: 1px solid rgba(212, 167, 55, 0.2);
        border-top: none;
        border-radius: 0 0 4px 4px;
        max-height: 200px;
        overflow-y: auto;
        z-index: 100;
    }

    .alias-search-results.active {
        display: block;
    }

    .alias-search-item {
        padding: 8px 12px;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: background 0.15s;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }

    .alias-search-item:hover {
        background: rgba(212, 167, 55, 0.1);
    }

    .alias-search-item:last-child {
        border-bottom: none;
    }

    .alias-search-display {
        font-size: 13px;
        color: var(--text-primary);
    }

    .alias-search-id {
        font-family: var(--font-mono);
        font-size: 11px;
        color: var(--text-tertiary);
    }

    .alias-search-empty {
        padding: 12px;
        text-align: center;
        font-size: 13px;
        color: var(--text-tertiary);
    }

    .alias-selected {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        background: rgba(74, 222, 128, 0.08);
        border: 1px solid rgba(74, 222, 128, 0.2);
        border-radius: 4px;
        margin-bottom: 10px;
        font-size: 13px;
    }

    .alias-selected-label {
        color: var(--text-tertiary);
        font-size: 12px;
    }

    .alias-selected-name {
        color: var(--green-success);
        font-weight: 600;
    }

    .alias-selected-id {
        color: var(--text-tertiary);
        font-family: var(--font-mono);
        font-size: 11px;
    }

    .alias-clear-btn {
        margin-left: auto;
        width: 20px;
        height: 20px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 3px;
        color: var(--red-error);
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }

    .alias-clear-btn:hover {
        background: rgba(239, 68, 68, 0.2);
    }

    .alias-add-btn {
        width: 100%;
        padding: 8px 16px;
        background: rgba(74, 222, 128, 0.15);
        border: 1px solid rgba(74, 222, 128, 0.3);
        border-radius: 4px;
        color: var(--green-success);
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .alias-add-btn:hover:not(:disabled) {
        background: rgba(74, 222, 128, 0.25);
    }

    .alias-add-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }

    .alias-list {
        max-height: 300px;
        overflow-y: auto;
    }

    .alias-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 10px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 4px;
        margin-bottom: 6px;
        transition: all 0.2s;
    }

    .alias-item:hover {
        background: rgba(212, 167, 55, 0.05);
        border-color: rgba(212, 167, 55, 0.2);
    }

    .alias-info {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
    }

    .alias-name {
        color: var(--gold-primary);
        font-weight: 600;
    }

    .alias-arrow {
        color: var(--text-tertiary);
        font-size: 11px;
    }

    .alias-id {
        color: var(--text-secondary);
        font-family: var(--font-mono);
        font-size: 12px;
    }

    .alias-display {
        color: var(--text-secondary);
        font-size: 12px;
    }

    .alias-remove-btn {
        width: 22px;
        height: 22px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 3px;
        color: var(--red-error);
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }

    .alias-remove-btn:hover {
        background: rgba(239, 68, 68, 0.2);
    }

    .alias-empty {
        text-align: center;
        padding: 20px;
        color: var(--text-tertiary);
        font-size: 13px;
    }

    /* 物品未找到提示 */
    .not-found-hint {
        font-size: 14px;
        color: var(--orange-warning);
        margin-bottom: 8px;
    }

    .add-alias-hint {
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        font-size: 13px;
        color: var(--text-tertiary);
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .alias-link-btn {
        padding: 4px 12px;
        background: rgba(212, 167, 55, 0.1);
        border: 1px solid rgba(212, 167, 55, 0.3);
        border-radius: 12px;
        color: var(--gold-primary);
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .alias-link-btn:hover {
        background: rgba(212, 167, 55, 0.2);
        transform: translateY(-1px);
    }
`;
document.head.appendChild(style);

// 请求通知权限
if (Notification.permission === 'default') {
    Notification.requestPermission();
}
