/* ============================================
   Warframe Trading Agent - Sidebar Module
   Tenno 科技终端侧边栏模块 v3.0
   ============================================ */

// ===== 价格缓存（用于变动高亮） =====
const PRICE_CACHE_KEY = 'warframe_price_cache';
let previousPrices = {};
let currentPrices = {};

function loadPriceCache() {
    try {
        const saved = localStorage.getItem(PRICE_CACHE_KEY);
        if (saved) previousPrices = JSON.parse(saved);
    } catch (e) {}
}

function savePriceCache(prices) {
    try {
        localStorage.setItem(PRICE_CACHE_KEY, JSON.stringify(prices));
    } catch (e) {}
}

async function fetchFavoritesPrices() {
    try {
        const res = await fetch('/api/favorites_prices');
        const data = await res.json();
        const prices = {};
        data.items.forEach(item => {
            prices[item.item_id] = {
                sell: item.sell_price,
                buy: item.buy_price
            };
        });
        currentPrices = prices;
        updatePriceIndicators();
        savePriceCache(prices);
    } catch (e) {
        console.warn('获取收藏价格失败:', e);
    }
}

function updatePriceIndicators() {
    document.querySelectorAll('.favorite-item').forEach(div => {
        const itemId = div.dataset.itemId;
        if (!itemId || !currentPrices[itemId]) return;

        const price = currentPrices[itemId];
        const prev = previousPrices[itemId];
        const priceEl = div.querySelector('.item-price');
        if (!priceEl) return;

        const sellText = price.sell !== null ? `${price.sell}p` : '-';
        priceEl.textContent = sellText;

        // 移除旧的变化指示器
        const oldIndicator = div.querySelector('.price-change');
        if (oldIndicator) oldIndicator.remove();

        if (prev && prev.sell !== null && price.sell !== null) {
            const diff = price.sell - prev.sell;
            if (diff !== 0) {
                const indicator = document.createElement('span');
                indicator.className = `price-change ${diff > 0 ? 'up' : 'down'}`;
                indicator.textContent = diff > 0 ? `▲${diff}` : `▼${Math.abs(diff)}`;
                priceEl.appendChild(indicator);
            }
        }
    });
}

// ===== 加载侧边栏数据 =====

async function loadSidebar() {
    try {
        loadPriceCache();
        const memory = await fetchMemory();
        renderFavorites(memory.favorites);
        renderAlerts(memory.alerts);
        updateSidebarStatus('online');
        fetchFavoritesPrices();
    } catch (err) {
        console.error('加载记忆失败:', err);
        updateSidebarStatus('error');
    }
}

// ===== 渲染收藏列表 =====

function renderFavorites(favorites) {
    const list = document.getElementById('favorites-list');
    list.innerHTML = '';

    if (!favorites || favorites.length === 0) {
        list.innerHTML = createEmptyState('暂无收藏', '添加收藏的物品将显示在这里');
        return;
    }

    favorites.forEach((fav, index) => {
        const div = document.createElement('div');
        div.className = 'list-item favorite-item';
        div.style.animationDelay = `${index * 100}ms`;
        div.dataset.itemId = typeof fav === 'object' ? fav.item_id : '';

        // 兼容新旧格式：新格式为 {display, item_id} 对象，旧格式为字符串
        const itemId = typeof fav === 'object' ? fav.item_id : '';
        const display = typeof fav === 'object' ? fav.display : fav;

        // 解析显示名称
        const parts = display.split(' / ');
        const displayName = parts[0] || display;
        const englishName = parts.length >= 3 ? parts[1] : '';

        // 使用缓存的价格
        const cached = currentPrices[itemId] || previousPrices[itemId];
        const priceText = cached && cached.sell !== null ? `${cached.sell}p` : '';

        div.innerHTML = `
            <div class="item-header">
                <span class="item-name">${displayName}</span>
                <span class="item-price">${priceText}</span>
            </div>
            ${englishName ? `<div class="item-sub">${englishName}</div>` : ''}
            <div class="item-actions">
                <button class="action-btn" onclick="event.stopPropagation(); queryItemPrice('${itemId}')" title="查询价格">
                    <span>查价</span>
                </button>
                <button class="action-btn danger" onclick="event.stopPropagation(); removeFavoriteItem('${itemId}')" title="移除收藏">
                    <span>移除</span>
                </button>
            </div>
        `;

        // 点击查询价格
        div.addEventListener('click', (e) => {
            if (!e.target.closest('.action-btn')) {
                queryItemPrice(itemId);
            }
        });

        list.appendChild(div);
    });
}

// ===== 渲染提醒列表 =====

function renderAlerts(alerts) {
    const list = document.getElementById('alerts-list');
    list.innerHTML = '';

    if (!alerts || alerts.length === 0) {
        list.innerHTML = createEmptyState('暂无提醒', '设置价格提醒将显示在这里');
        return;
    }

    alerts.forEach((alert, index) => {
        const div = document.createElement('div');
        div.className = 'list-item alert-item';
        div.style.animationDelay = `${index * 100}ms`;

        const directionIcon = alert.direction === 'below' ? '📉' : '📈';
        const directionText = alert.direction === 'below' ? '低于' : '高于';
        const alertItemId = alert.item_id || alert.item;

        div.innerHTML = `
            <div class="item-header">
                <span class="item-name">${alert.item}</span>
                <span class="item-badge ${alert.direction}">${directionIcon}</span>
            </div>
            <div class="item-sub">${directionText} ${alert.price}p 时提醒</div>
            <div class="item-actions">
                <button class="action-btn" onclick="queryItemPrice('${alertItemId}')" title="查询价格">
                    <span>查价</span>
                </button>
                <button class="action-btn danger" onclick="removeAlertItem('${alertItemId}', '${alert.direction}', ${alert.price})" title="移除提醒">
                    <span>移除</span>
                </button>
            </div>
        `;

        list.appendChild(div);
    });
}

// ===== 创建空状态 =====

function createEmptyState(title, subtitle) {
    return `
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <div class="empty-state-text">${title}</div>
            <div class="empty-state-sub">${subtitle}</div>
        </div>
    `;
}

// ===== 批量操作 =====

let batchMode = false;

function toggleBatchMode() {
    batchMode = !batchMode;
    const btn = document.getElementById('batch-edit-btn');
    if (btn) btn.textContent = batchMode ? '✓' : '✏️';

    document.querySelectorAll('.favorite-item').forEach(item => {
        if (batchMode) {
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'batch-checkbox';
            item.prepend(checkbox);
            item.classList.add('batch-mode');
        } else {
            const checkbox = item.querySelector('.batch-checkbox');
            if (checkbox) checkbox.remove();
            item.classList.remove('batch-mode');
        }
    });

    // 批量模式下显示删除按钮
    const existingBar = document.querySelector('.batch-bar');
    if (batchMode) {
        if (!existingBar) {
            const bar = document.createElement('div');
            bar.className = 'batch-bar';
            bar.innerHTML = `
                <button class="batch-btn" onclick="batchSelectAll()">全选</button>
                <button class="batch-btn danger" onclick="batchDelete()">删除选中</button>
                <button class="batch-btn" onclick="toggleBatchMode()">取消</button>
            `;
            document.getElementById('favorites-list').after(bar);
        }
    } else {
        if (existingBar) existingBar.remove();
    }
}

function batchSelectAll() {
    document.querySelectorAll('.batch-checkbox').forEach(cb => {
        cb.checked = true;
    });
}

async function batchDelete() {
    const checked = document.querySelectorAll('.batch-checkbox:checked');
    if (checked.length === 0) {
        showToast('请先选择要删除的物品', 'warning');
        return;
    }

    if (!confirm(`确定要删除选中的 ${checked.length} 个收藏吗？`)) return;

    const items = [];
    checked.forEach(cb => {
        const item = cb.closest('.favorite-item');
        if (item) items.push(item.dataset.itemId);
    });

    let success = 0;
    for (const itemId of items) {
        try {
            await removeFavorite(itemId);
            success++;
        } catch (e) {}
    }

    showToast(`已删除 ${success} 个收藏`, 'success');
    toggleBatchMode();
    loadSidebar();
}

document.getElementById('batch-edit-btn')?.addEventListener('click', toggleBatchMode);

// ===== 更新侧边栏状态 =====

function updateSidebarStatus(status) {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    if (!statusDot || !statusText) return;

    statusDot.className = 'status-dot';

    switch (status) {
        case 'online':
            statusDot.classList.add('online');
            statusText.textContent = '系统在线';
            break;
        case 'loading':
            statusDot.classList.add('loading');
            statusText.textContent = '加载中...';
            break;
        case 'error':
            statusDot.classList.add('error');
            statusText.textContent = '连接错误';
            break;
        default:
            statusText.textContent = '未知状态';
    }
}

// ===== 操作函数 =====

async function queryItemPrice(itemId) {
    if (!itemId) return;

    chatInput.value = itemId;
    handleSend();
}

async function removeFavoriteItem(itemId) {
    if (!itemId) return;

    if (!confirm(`确定要移除收藏 "${itemId}" 吗？`)) {
        return;
    }

    try {
        await removeFavorite(itemId);
        showToast('已移除收藏', 'success');
        loadSidebar(); // 重新加载
    } catch (err) {
        console.error('移除收藏失败:', err);
        showToast('移除收藏失败', 'error');
    }
}

async function removeAlertItem(itemId, direction, price) {
    if (!itemId) return;

    if (!confirm(`确定要移除提醒 "${itemId} ${direction} ${price}p" 吗？`)) {
        return;
    }

    try {
        await removeAlertApi(itemId, direction, price);
        showToast('已移除提醒', 'success');
        loadSidebar(); // 重新加载
    } catch (err) {
        console.error('移除提醒失败:', err);
        showToast('移除提醒失败', 'error');
    }
}

// ===== 定时刷新（标签页可见时才刷新） =====

setInterval(() => {
    if (document.visibilityState === 'visible') {
        loadSidebar();
    }
}, 5 * 60 * 1000);

// ===== 初始化 =====

// 页面加载完成后加载侧边栏
document.addEventListener('DOMContentLoaded', () => {
    // 延迟加载，避免阻塞页面渲染
    setTimeout(loadSidebar, 500);
});

// ===== 样式注入 =====

const sidebarStyles = document.createElement('style');
sidebarStyles.textContent = `
    .favorite-item,
    .alert-item {
        cursor: pointer;
        transition: all 0.3s ease-out;
    }

    .favorite-item:hover,
    .alert-item:hover {
        transform: translateX(4px);
        border-left-color: var(--gold-primary);
    }

    .item-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
    }

    .item-name {
        font-family: var(--font-body);
        font-weight: 600;
        color: var(--text-primary);
        font-size: 14px;
    }

    .item-badge {
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 3px;
        background: rgba(74, 158, 255, 0.2);
        color: var(--blue-primary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .item-badge.below {
        background: rgba(239, 68, 68, 0.2);
        color: var(--red-error);
    }

    .item-badge.above {
        background: rgba(74, 222, 128, 0.2);
        color: var(--green-success);
    }

    .item-price {
        font-family: var(--font-mono);
        font-size: 12px;
        color: var(--text-secondary);
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .price-change {
        font-size: 10px;
        padding: 1px 4px;
        border-radius: 2px;
        animation: priceFlash 0.6s ease-out;
    }

    .price-change.up {
        color: var(--green-success);
        background: rgba(74, 222, 128, 0.1);
    }

    .price-change.down {
        color: var(--red-error);
        background: rgba(239, 68, 68, 0.1);
    }

    @keyframes priceFlash {
        0% { opacity: 0; transform: scale(0.8); }
        50% { opacity: 1; transform: scale(1.2); }
        100% { opacity: 1; transform: scale(1); }
    }

    .item-sub {
        font-size: 12px;
        color: var(--text-tertiary);
        margin-bottom: 8px;
    }

    .item-actions {
        display: flex;
        gap: 8px;
        opacity: 0;
        transition: opacity 0.3s ease-out;
    }

    .list-item:hover .item-actions {
        opacity: 1;
    }

    .action-btn {
        padding: 4px 8px;
        background: rgba(74, 158, 255, 0.1);
        border: 1px solid rgba(74, 158, 255, 0.3);
        border-radius: 3px;
        color: var(--blue-primary);
        font-size: 11px;
        cursor: pointer;
        transition: all 0.2s ease-out;
        letter-spacing: 0.05em;
    }

    .action-btn:hover {
        background: rgba(74, 158, 255, 0.2);
        transform: translateY(-1px);
    }

    .action-btn.danger {
        background: rgba(239, 68, 68, 0.1);
        border-color: rgba(239, 68, 68, 0.3);
        color: var(--red-error);
    }

    .action-btn.danger:hover {
        background: rgba(239, 68, 68, 0.2);
    }

    .sidebar-footer {
        margin-top: auto;
        padding-top: 16px;
        border-top: 1px solid rgba(212, 167, 55, 0.2);
    }

    .serial-number {
        font-family: var(--font-mono);
        font-size: 10px;
        color: var(--text-tertiary);
        letter-spacing: 0.1em;
        margin-bottom: 8px;
    }

    .status-indicator {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--text-tertiary);
        transition: all 0.3s ease-out;
    }

    .status-dot.online {
        background: var(--green-success);
        box-shadow: 0 0 8px rgba(74, 222, 128, 0.5);
        animation: pulse 2s infinite;
    }

    .status-dot.loading {
        background: var(--orange-warning);
        animation: pulse 1s infinite;
    }

    .status-dot.error {
        background: var(--red-error);
        animation: pulse 0.5s infinite;
    }

    .status-text {
        font-size: 11px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
    }

    @keyframes pulse {
        0%, 100% {
            opacity: 1;
        }
        50% {
            opacity: 0.5;
        }
    }

    .sidebar-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .sidebar-edit-btn {
        background: none;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 3px;
        padding: 2px 6px;
        cursor: pointer;
        font-size: 12px;
        transition: all 0.2s;
    }

    .sidebar-edit-btn:hover {
        background: rgba(212, 167, 55, 0.1);
        border-color: rgba(212, 167, 55, 0.3);
    }

    .batch-checkbox {
        margin-right: 8px;
        accent-color: var(--gold-primary);
    }

    .list-item.batch-mode {
        padding-left: 8px;
    }

    .batch-bar {
        display: flex;
        gap: 8px;
        padding: 10px 0;
        margin-top: 8px;
        border-top: 1px solid rgba(212, 167, 55, 0.2);
    }

    .batch-btn {
        flex: 1;
        padding: 6px 10px;
        background: rgba(74, 158, 255, 0.1);
        border: 1px solid rgba(74, 158, 255, 0.3);
        border-radius: 3px;
        color: var(--blue-primary);
        font-size: 11px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .batch-btn:hover {
        background: rgba(74, 158, 255, 0.2);
    }

    .batch-btn.danger {
        background: rgba(239, 68, 68, 0.1);
        border-color: rgba(239, 68, 68, 0.3);
        color: var(--red-error);
    }

    .batch-btn.danger:hover {
        background: rgba(239, 68, 68, 0.2);
    }
`;
document.head.appendChild(sidebarStyles);
