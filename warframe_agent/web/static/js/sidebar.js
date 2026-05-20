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
        if (!res.ok) return;
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

        // 使用 CountUp.js 动画显示价格
        if (typeof CountUp !== 'undefined' && price.sell !== null && prev && prev.sell !== null && prev.sell !== price.sell) {
            const counter = new CountUp(priceEl, price.sell, {
                suffix: 'p',
                duration: 0.6,
                useGrouping: false,
            });
            if (!counter.error) {
                counter.start();
            } else {
                priceEl.textContent = `${price.sell}p`;
            }
        } else {
            const sellText = price.sell !== null ? `${price.sell}p` : '-';
            priceEl.textContent = sellText;
        }

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
                // 价格更新闪烁效果
                div.classList.add('price-updated');
                setTimeout(() => div.classList.remove('price-updated'), 800);
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
        fetchFavoritesPrices();
        // 同时加载关注列表
        await loadWatchlist();
    } catch (err) {
        console.error('加载记忆失败:', err);
    }
}

// ===== 渲染收藏列表 =====

function renderFavorites(favorites) {
    const list = document.getElementById('favorites-list');
    if (!list) return;
    const header = list.previousElementSibling;
    list.textContent = '';

    if (!favorites || favorites.length === 0) {
        list.classList.add('collapsed');
        if (header) header.classList.add('collapsed');
        return;
    }

    list.classList.remove('collapsed');
    if (header) header.classList.remove('collapsed');

    favorites.forEach((fav, index) => {
        const div = document.createElement('div');
        div.className = 'list-item favorite-item stagger-item';
        div.style.animationDelay = `${index * 50}ms`;
        div.dataset.itemId = typeof fav === 'object' ? fav.item_id : '';

        const itemId = typeof fav === 'object' ? fav.item_id : '';
        const display = typeof fav === 'object' ? fav.display : fav;
        const displayText = typeof display === 'string' ? display : '';
        const parts = displayText.split(' / ');
        const displayName = parts[0] || displayText;
        const englishName = parts.length >= 3 ? parts[1] : '';
        const cached = currentPrices[itemId] || previousPrices[itemId];
        const priceText = cached && cached.sell !== null ? `${cached.sell}p` : '';

        const headerRow = document.createElement('div');
        headerRow.className = 'item-header';

        const nameSpan = document.createElement('span');
        nameSpan.className = 'item-name';
        nameSpan.textContent = displayName;

        const priceSpan = document.createElement('span');
        priceSpan.className = 'item-price';
        priceSpan.textContent = priceText;

        headerRow.append(nameSpan, priceSpan);
        div.appendChild(headerRow);

        if (englishName) {
            const subDiv = document.createElement('div');
            subDiv.className = 'item-sub';
            subDiv.textContent = englishName;
            div.appendChild(subDiv);
        }

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'item-actions';

        const queryButton = document.createElement('button');
        queryButton.type = 'button';
        queryButton.className = 'action-btn';
        queryButton.title = '查询价格';
        queryButton.appendChild(document.createElement('span')).textContent = '查价';
        queryButton.addEventListener('click', (event) => {
            event.stopPropagation();
            queryItemPrice(itemId);
        });

        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.className = 'action-btn danger';
        removeButton.title = '移除收藏';
        removeButton.appendChild(document.createElement('span')).textContent = '移除';
        removeButton.addEventListener('click', (event) => {
            event.stopPropagation();
            removeFavoriteItem(itemId);
        });

        actionsDiv.append(queryButton, removeButton);
        div.appendChild(actionsDiv);

        div.addEventListener('click', (event) => {
            if (!event.target.closest('.action-btn')) {
                queryItemPrice(itemId);
            }
        });

        list.appendChild(div);
    });
}

// ===== 渲染提醒列表 =====

const MAX_VISIBLE_ALERTS = 5;
let showAllAlerts = false;

function renderAlerts(alerts) {
    const list = document.getElementById('alerts-list');
    if (!list) return;
    const header = list.previousElementSibling;
    list.textContent = '';

    if (!alerts || alerts.length === 0) {
        list.classList.add('collapsed');
        if (header) header.classList.add('collapsed');
        return;
    }

    list.classList.remove('collapsed');
    if (header) header.classList.remove('collapsed');

    const visibleAlerts = showAllAlerts ? alerts : alerts.slice(0, MAX_VISIBLE_ALERTS);

    visibleAlerts.forEach((alert, index) => {
        const div = document.createElement('div');
        div.className = 'list-item alert-item stagger-item';
        div.style.animationDelay = `${index * 50}ms`;

        const directionIcon = alert.direction === 'below' ? '📉' : '📈';
        const directionText = alert.direction === 'below' ? '低于' : '高于';
        const alertItemId = alert.item_id || alert.item;
        const alertItemName = alert.item || alertItemId;

        const headerRow = document.createElement('div');
        headerRow.className = 'item-header';

        const nameSpan = document.createElement('span');
        nameSpan.className = 'item-name';
        nameSpan.textContent = alertItemName;

        const badgeSpan = document.createElement('span');
        badgeSpan.className = 'item-badge';
        if (alert.direction === 'below' || alert.direction === 'above') {
            badgeSpan.classList.add(alert.direction);
        }
        badgeSpan.textContent = directionIcon;

        headerRow.append(nameSpan, badgeSpan);
        div.appendChild(headerRow);

        const subDiv = document.createElement('div');
        subDiv.className = 'item-sub';
        subDiv.textContent = `${directionText} ${alert.price}p 时提醒${alert.note ? ` - ${alert.note}` : ''}`;
        div.appendChild(subDiv);

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'item-actions';

        const queryButton = document.createElement('button');
        queryButton.type = 'button';
        queryButton.className = 'action-btn';
        queryButton.title = '查询价格';
        queryButton.appendChild(document.createElement('span')).textContent = '查价';
        queryButton.addEventListener('click', () => queryItemPrice(alertItemId));

        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.className = 'action-btn danger';
        removeButton.title = '移除提醒';
        removeButton.appendChild(document.createElement('span')).textContent = '移除';
        removeButton.addEventListener('click', () => removeAlertItem(alertItemId, alert.direction, alert.price));

        actionsDiv.append(queryButton, removeButton);
        div.appendChild(actionsDiv);
        list.appendChild(div);
    });

    if (alerts.length > MAX_VISIBLE_ALERTS) {
        const toggleBtn = document.createElement('div');
        toggleBtn.className = 'list-toggle';

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'toggle-btn';
        button.textContent = showAllAlerts ? '收起' : `查看全部 (${alerts.length})`;
        button.addEventListener('click', toggleAlertsView);

        toggleBtn.appendChild(button);
        list.appendChild(toggleBtn);
    }
}

function toggleAlertsView() {
    showAllAlerts = !showAllAlerts;
    loadSidebar();
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

            const selectAllButton = document.createElement('button');
            selectAllButton.type = 'button';
            selectAllButton.className = 'batch-btn';
            selectAllButton.textContent = '全选';
            selectAllButton.addEventListener('click', batchSelectAll);

            const deleteButton = document.createElement('button');
            deleteButton.type = 'button';
            deleteButton.className = 'batch-btn danger';
            deleteButton.textContent = '删除选中';
            deleteButton.addEventListener('click', batchDelete);

            const cancelButton = document.createElement('button');
            cancelButton.type = 'button';
            cancelButton.className = 'batch-btn';
            cancelButton.textContent = '取消';
            cancelButton.addEventListener('click', toggleBatchMode);

            bar.append(selectAllButton, deleteButton, cancelButton);
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

function updateSidebarStatus(status, detail = '') {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    if (!statusDot || !statusText) return;

    statusDot.className = 'status-dot';
    statusText.title = detail || '';

    switch (status) {
        case 'online':
            statusDot.classList.add('online');
            statusText.textContent = '系统在线';
            break;
        case 'loading':
            statusDot.classList.add('loading');
            statusText.textContent = '状态检查中';
            break;
        case 'degraded':
            statusDot.classList.add('degraded');
            statusText.textContent = '部分服务异常';
            break;
        case 'error':
            statusDot.classList.add('error');
            statusText.textContent = '连接错误';
            break;
        default:
            statusDot.classList.add('loading');
            statusText.textContent = '状态检查中';
    }
}

// ===== 操作函数 =====

async function queryItemPrice(itemId) {
    if (!itemId) return;
    const input = window.chatInput || document.getElementById('chat-input');
    if (input) {
        input.value = itemId;
        input.focus();
    }
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

// ===== 交易历史功能 =====

async function loadTradeHistory() {
    const content = openDetailPanel('加载交易历史...');
    if (!content) return;

    try {
        const [tradesRes, statsRes] = await Promise.all([
            fetch('/api/trades?limit=20'),
            fetch('/api/trades/stats')
        ]);
        const tradesData = await tradesRes.json();
        const statsData = await statsRes.json();

        let html = `
            <div class="trade-history-container">
                <div class="trade-history-header">
                    <h3 class="trade-history-title">交易历史</h3>
                    <button class="detail-action-btn" onclick="showAddTradeModal()">
                        + 记录交易
                    </button>
                </div>
        `;

        // 统计信息
        if (statsData.total_trades > 0) {
            html += `
                <div class="trade-stats">
                    <div class="trade-stat-item">
                        <div class="trade-stat-label">总交易</div>
                        <div class="trade-stat-value">${statsData.total_trades}</div>
                    </div>
                    <div class="trade-stat-item">
                        <div class="trade-stat-label">买入</div>
                        <div class="trade-stat-value buy">${statsData.buy_count}</div>
                    </div>
                    <div class="trade-stat-item">
                        <div class="trade-stat-label">卖出</div>
                        <div class="trade-stat-value sell">${statsData.sell_count}</div>
                    </div>
                    <div class="trade-stat-item">
                        <div class="trade-stat-label">净收入</div>
                        <div class="trade-stat-value ${statsData.net_profit >= 0 ? 'positive' : 'negative'}">${statsData.net_profit}p</div>
                    </div>
                </div>
            `;
        }

        // 交易记录列表
        if (tradesData.trades && tradesData.trades.length > 0) {
            html += '<div class="trade-list">';
            tradesData.trades.forEach(trade => {
                const typeClass = trade.trade_type === 'buy' ? 'buy' : 'sell';
                const typeText = trade.trade_type === 'buy' ? '买入' : '卖出';
                const typeIcon = trade.trade_type === 'buy' ? '📥' : '📤';
                const date = new Date(trade.timestamp).toLocaleString('zh-CN');

                html += `
                    <div class="trade-item ${typeClass}">
                        <div class="trade-item-header">
                            <span class="trade-type-badge ${typeClass}">${typeIcon} ${typeText}</span>
                            <span class="trade-price">${trade.price}p</span>
                        </div>
                        <div class="trade-item-name">${escapeHtml(trade.item_name)}</div>
                        <div class="trade-item-details">
                            ${trade.player_name ? `<span class="trade-player">玩家: ${escapeHtml(trade.player_name)}</span>` : ''}
                            <span class="trade-date">${date}</span>
                        </div>
                        ${trade.notes ? `<div class="trade-notes">${escapeHtml(trade.notes)}</div>` : ''}
                        <div class="trade-item-actions">
                            <button class="action-btn danger" onclick="deleteTradeRecord(${trade.id})">删除</button>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        } else {
            html += `
                <div class="trade-empty">
                    <div class="empty-state-icon">📋</div>
                    <div class="empty-state-text">暂无交易记录</div>
                    <div class="empty-state-sub">点击上方按钮记录您的第一笔交易</div>
                </div>
            `;
        }

        html += '</div>';
        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = createChartError('加载交易历史失败');
    }
}

function showAddTradeModal() {
    // 使用简单的 prompt 方式
    const itemName = prompt('物品名称:');
    if (!itemName) return;

    const tradeType = prompt('交易类型 (buy/sell):');
    if (!tradeType || !['buy', 'sell'].includes(tradeType.toLowerCase())) {
        showToast('请输入 buy 或 sell', 'warning');
        return;
    }

    const priceStr = prompt('价格 (白金):');
    if (!priceStr) return;
    const price = parseInt(priceStr);
    if (isNaN(price) || price <= 0) {
        showToast('请输入有效的价格', 'warning');
        return;
    }

    const playerName = prompt('对方玩家名 (可选):') || '';
    const notes = prompt('备注 (可选):') || '';

    // 尝试解析物品ID
    fetch(`/api/resolve/${encodeURIComponent(itemName)}`)
        .then(res => res.json())
        .then(data => {
            const itemId = data.found ? data.item_id : itemName;
            return fetch('/api/trades', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    item_id: itemId,
                    item_name: itemName,
                    trade_type: tradeType.toLowerCase(),
                    price: price,
                    player_name: playerName,
                    notes: notes
                })
            });
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                showToast('交易记录已添加', 'success');
                loadTradeHistory(); // 刷新显示
            }
        })
        .catch(() => {
            showToast('添加交易记录失败', 'error');
        });
}

async function deleteTradeRecord(tradeId) {
    if (!confirm('确定要删除这条交易记录吗？')) return;

    try {
        const res = await fetch(`/api/trades/${tradeId}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('已删除交易记录', 'success');
            loadTradeHistory(); // 刷新显示
        }
    } catch (err) {
        showToast('删除失败', 'error');
    }
}

// 交易历史按钮事件
document.getElementById('trade-history-btn')?.addEventListener('click', () => {
    document.getElementById('more-menu')?.classList.remove('active');
    loadTradeHistory();
});

// ===== 每日报告 =====
document.getElementById('report-btn')?.addEventListener('click', async () => {
    document.getElementById('more-menu')?.classList.remove('active');
    const content = openDetailPanel('生成每日报告...');
    if (!content) return;

    try {
        const res = await fetch('/api/report');
        const data = await res.json();
        const report = data.report || '无报告数据';

        let html = `<div class="panel-title-row">
            <span class="panel-title-eyebrow">每日价格报告</span>
            <span class="badge badge-gold">${new Date().toLocaleDateString('zh-CN')}</span>
        </div>`;

        html += '<div class="card"><div class="card-body">';
        const lines = report.split('\n');
        lines.forEach(line => {
            if (line.startsWith('# ')) {
                html += `<h3 style="color:var(--gold-primary);margin-bottom:12px;font-size:16px;">${line.substring(2)}</h3>`;
            } else if (line.startsWith('- ')) {
                const parts = line.substring(2).split(':');
                const name = parts[0] || '';
                const details = parts.slice(1).join(':');
                html += `<div class="fissure-item">
                    <div><div class="fissure-node">${name}</div></div>
                    <span style="font-family:var(--font-mono);font-size:12px;color:var(--text-secondary)">${details}</span>
                </div>`;
            } else if (line.trim()) {
                html += `<p style="color:var(--text-secondary);font-size:13px;margin:4px 0;">${line}</p>`;
            }
        });
        html += '</div></div>';

        html += `<div style="margin-top:12px;display:flex;gap:8px;">
            <button class="btn-gradient" id="copy-report-btn">复制报告</button>
            <button class="btn-gradient btn-gradient-cyan" id="refresh-report-btn">刷新</button>
        </div>`;

        content.innerHTML = html;
        document.getElementById('copy-report-btn')?.addEventListener('click', () => {
            navigator.clipboard.writeText(report).then(() => showToast('已复制', 'success'));
        });
        document.getElementById('refresh-report-btn')?.addEventListener('click', () => {
            document.getElementById('report-btn')?.click();
        });
    } catch (err) {
        content.innerHTML = `<div class="empty-state"><div class="empty-icon">📊</div>
            <span class="empty-primary">报告生成失败</span><span class="empty-sub">${err.message}</span></div>`;
    }
});

// ===== 收藏夹仪表盘 =====

let dashboardMode = 'scatter';

async function loadFavoritesDashboard(mode) {
    if (mode) dashboardMode = mode;
    const content = openDetailPanel('加载收藏仪表盘...');
    if (!content) return;

    try {
        const [memoryRes, pricesRes] = await Promise.all([
            fetch('/api/memory'),
            fetch(`/api/favorites_prices?mode=${dashboardMode}`)
        ]);
        const memoryData = await memoryRes.json();
        const pricesData = await pricesRes.json();

        const favorites = memoryData.favorites || [];
        const prices = pricesData.items || [];

        if (favorites.length === 0) {
            content.innerHTML = `<div class="empty-state"><div class="empty-icon">⭐</div>
                <span class="empty-primary">收藏夹为空</span>
                <span class="empty-sub">在对话中输入 物品名 添加收藏，或使用 /fav add 物品名</span></div>`;
            return;
        }

        // 计算统计数据
        let totalSell = 0;
        let totalBuy = 0;
        let itemsWithPrices = 0;
        let priceChanges = { up: 0, down: 0, stable: 0 };

        // 加载上次价格缓存
        loadPriceCache();

        const priceMap = {};
        prices.forEach(item => {
            priceMap[item.item_id] = item;
            if (item.sell_price) {
                totalSell += item.sell_price;
                itemsWithPrices++;
            }
            if (item.buy_price) {
                totalBuy += item.buy_price;
            }

            // 检查价格变化
            const prev = previousPrices[item.item_id];
            if (prev && prev.sell !== null && item.sell_price !== null) {
                const diff = item.sell_price - prev.sell;
                if (diff > 0) priceChanges.up++;
                else if (diff < 0) priceChanges.down++;
                else priceChanges.stable++;
            } else {
                priceChanges.stable++;
            }
        });

        let html = `
            <div class="dashboard-container">
                <div class="dashboard-header">
                    <h3 class="dashboard-title">收藏夹仪表盘</h3>
                    <div class="dashboard-subtitle">收藏物品价格概览 · 点击物品查看详情</div>
                </div>
                <div class="mode-toggle-bar">
                    <button class="mode-toggle-btn ${dashboardMode === 'scatter' ? 'active' : ''}" onclick="loadFavoritesDashboard('scatter')">零散价格</button>
                    <button class="mode-toggle-btn ${dashboardMode === 'maxrank' ? 'active' : ''}" onclick="loadFavoritesDashboard('maxrank')">满级成本</button>
                </div>

                <div class="dashboard-summary">
                    <div class="dashboard-stat main">
                        <div class="dashboard-stat-label">${dashboardMode === 'maxrank' ? '总满级卖价' : '总卖出价值'}</div>
                        <div class="dashboard-stat-value">${totalSell}p</div>
                        <div style="font-size:11px;color:var(--text-tertiary)">${dashboardMode === 'maxrank' ? '全部收藏按满级最低卖价' : '全部收藏按最低卖价'}</div>
                    </div>
                    <div class="dashboard-stat">
                        <div class="dashboard-stat-label">${dashboardMode === 'maxrank' ? '总满级收价' : '总收购价值'}</div>
                        <div class="dashboard-stat-value" style="color:var(--blue-primary)">${totalBuy}p</div>
                        <div style="font-size:11px;color:var(--text-tertiary)">${dashboardMode === 'maxrank' ? '全部收藏按满级最高收价' : '全部收藏按最高收价'}</div>
                    </div>
                    <div class="dashboard-stat">
                        <div class="dashboard-stat-label">物品数</div>
                        <div class="dashboard-stat-value">${favorites.length}</div>
                    </div>
                </div>

                <div class="dashboard-changes">
                    <div class="change-title">价格变动</div>
                    <div class="change-bars">
                        <div class="change-bar up">
                            <span class="change-icon">▲</span>
                            <span class="change-count">${priceChanges.up}</span>
                            <span class="change-label">上涨</span>
                        </div>
                        <div class="change-bar stable">
                            <span class="change-icon">─</span>
                            <span class="change-count">${priceChanges.stable}</span>
                            <span class="change-label">持平</span>
                        </div>
                        <div class="change-bar down">
                            <span class="change-icon">▼</span>
                            <span class="change-count">${priceChanges.down}</span>
                            <span class="change-label">下跌</span>
                        </div>
                    </div>
                </div>

                <div class="dashboard-items-title">物品列表 <span style="font-size:11px;color:var(--text-tertiary);font-weight:normal">（点击查看详情）</span></div>
                <div class="dashboard-items">
        `;

        // 物品列表
        favorites.forEach((fav, index) => {
            const itemId = typeof fav === 'object' ? fav.item_id : '';
            const display = typeof fav === 'object' ? fav.display : fav;
            const price = priceMap[itemId];
            const prev = previousPrices[itemId];
            const isRanked = price && price.max_rank && price.max_rank > 0;

            let changeHtml = '';
            if (price && prev && prev.sell !== null && price.sell_price !== null) {
                const diff = price.sell_price - prev.sell;
                if (diff > 0) {
                    changeHtml = `<span class="item-change up">▲${diff}</span>`;
                } else if (diff < 0) {
                    changeHtml = `<span class="item-change down">▼${Math.abs(diff)}</span>`;
                }
            }

            const spread = price && price.sell_price && price.buy_price ? price.sell_price - price.buy_price : null;
            const spreadClass = spread !== null ? (spread > 20 ? 'high' : spread > 5 ? 'mid' : 'low') : '';

            const sellLabel = dashboardMode === 'maxrank' && isRanked ? '满级卖价' : '卖价';
            const buyLabel = dashboardMode === 'maxrank' && isRanked ? '满级收价' : '收价';

            html += `
                <div class="dashboard-item" style="animation-delay: ${index * 50}ms" onclick="queryItemPrice('${itemId}')">
                    <div class="dashboard-item-header">
                        <span class="dashboard-item-name">${display.split(' / ')[0]}</span>
                        <span class="dashboard-item-price">
                            ${price && price.sell_price ? price.sell_price + 'p' : '-'}
                            ${changeHtml}
                        </span>
                    </div>
                    <div class="dashboard-item-detail">
                        <span class="detail-label">${buyLabel}</span>
                        <span class="detail-value" style="color:var(--blue-primary)">${price && price.buy_price ? price.buy_price + 'p' : '-'}</span>
                        ${spread !== null ? `<span class="detail-spread ${spreadClass}">差 ${spread}p</span>` : ''}
                    </div>
                </div>
            `;
        });

        html += `
                </div>

                <div class="dashboard-actions">
                    <button class="btn-gradient" onclick="exportDashboardData()">导出数据</button>
                    <button class="btn-gradient btn-gradient-cyan" onclick="loadFavoritesDashboard()">刷新数据</button>
                </div>
            </div>
        `;

        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = createChartError('加载仪表盘失败: ' + err.message);
    }
}

function exportDashboardData() {
    // 导出收藏夹数据为文本
    const items = document.querySelectorAll('.dashboard-item');
    let text = 'Warframe 收藏夹概览\n';
    text += '==================\n\n';

    items.forEach(item => {
        const name = item.querySelector('.dashboard-item-name')?.textContent || '';
        const price = item.querySelector('.dashboard-item-price')?.textContent || '';
        text += `${name}: ${price}\n`;
    });

    navigator.clipboard.writeText(text).then(() => {
        showToast('已复制到剪贴板', 'success');
    }).catch(() => {
        showToast('复制失败', 'error');
    });
}

// 收藏仪表盘按钮事件
document.getElementById('dashboard-btn')?.addEventListener('click', () => {
    document.getElementById('more-menu')?.classList.remove('active');
    loadFavoritesDashboard();
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
        background: var(--bg-overlay);
        box-shadow: inset 3px 0 0 var(--gold-primary), var(--shadow-gold-sm);
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
        opacity: 1;
        transition: opacity 0.3s ease-out;
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

    /* 交易历史样式 */
    .trade-history-container {
        padding: 16px;
    }

    .trade-history-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(212, 167, 55, 0.2);
    }

    .trade-history-title {
        font-family: var(--font-display);
        font-size: 16px;
        color: var(--gold-primary);
        letter-spacing: 0.05em;
    }

    .trade-stats {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        margin-bottom: 16px;
    }

    .trade-stat-item {
        text-align: center;
        padding: 10px 8px;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 4px;
    }

    .trade-stat-label {
        font-size: 10px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }

    .trade-stat-value {
        font-family: var(--font-mono);
        font-size: 16px;
        font-weight: 700;
        color: var(--text-primary);
    }

    .trade-stat-value.buy {
        color: var(--green-success);
    }

    .trade-stat-value.sell {
        color: var(--red-error);
    }

    .trade-stat-value.positive {
        color: var(--green-success);
    }

    .trade-stat-value.negative {
        color: var(--red-error);
    }

    .trade-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .trade-item {
        padding: 12px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 6px;
        transition: all 0.3s ease-out;
    }

    .trade-item:hover {
        border-color: rgba(212, 167, 55, 0.3);
        transform: translateX(2px);
    }

    .trade-item.buy {
        border-left: 3px solid var(--green-success);
    }

    .trade-item.sell {
        border-left: 3px solid var(--red-error);
    }

    .trade-item-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }

    .trade-type-badge {
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 3px;
        letter-spacing: 0.05em;
    }

    .trade-type-badge.buy {
        background: rgba(74, 222, 128, 0.15);
        color: var(--green-success);
    }

    .trade-type-badge.sell {
        background: rgba(239, 68, 68, 0.15);
        color: var(--red-error);
    }

    .trade-price {
        font-family: var(--font-mono);
        font-size: 16px;
        font-weight: 700;
        color: var(--gold-primary);
    }

    .trade-item-name {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 6px;
    }

    .trade-item-details {
        display: flex;
        gap: 12px;
        font-size: 11px;
        color: var(--text-tertiary);
    }

    .trade-player, .trade-date {
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .trade-notes {
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        font-size: 12px;
        color: var(--text-secondary);
        font-style: italic;
    }

    .trade-item-actions {
        margin-top: 8px;
        opacity: 0;
        transition: opacity 0.2s ease-out;
    }

    .trade-item:hover .trade-item-actions {
        opacity: 1;
    }

    .trade-empty {
        padding: 40px 20px;
        text-align: center;
    }

    /* 套利检测样式 */
    .arbitrage-container {
        padding: 16px;
    }

    .arbitrage-header {
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(212, 167, 55, 0.2);
    }

    .arbitrage-title {
        font-family: var(--font-display);
        font-size: 16px;
        color: var(--gold-primary);
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }

    .arbitrage-subtitle {
        font-size: 12px;
        color: var(--text-tertiary);
    }

    .arbitrage-summary {
        display: flex;
        gap: 16px;
        margin-bottom: 16px;
        padding: 12px;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 6px;
    }

    .arbitrage-stat {
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 1;
    }

    .arbitrage-stat-label {
        font-size: 10px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }

    .arbitrage-stat-value {
        font-family: var(--font-mono);
        font-size: 18px;
        font-weight: 700;
        color: var(--gold-primary);
    }

    .arbitrage-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .arbitrage-item {
        padding: 14px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(212, 167, 55, 0.15);
        border-radius: 6px;
        animation: fadeInUp 0.4s ease-out backwards;
        transition: all 0.3s ease-out;
    }

    .arbitrage-item:hover {
        border-color: rgba(212, 167, 55, 0.4);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .arbitrage-item-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }

    .arbitrage-item-name {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
    }

    .arbitrage-profit {
        font-family: var(--font-mono);
        font-size: 16px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 4px;
    }

    .arbitrage-profit.high {
        background: rgba(74, 222, 128, 0.2);
        color: var(--green-success);
    }

    .arbitrage-profit.medium {
        background: rgba(212, 167, 55, 0.2);
        color: var(--gold-primary);
    }

    .arbitrage-profit.low {
        background: rgba(74, 158, 255, 0.2);
        color: var(--blue-primary);
    }

    .arbitrage-prices {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
        padding: 10px;
        background: rgba(0, 0, 0, 0.15);
        border-radius: 4px;
    }

    .arbitrage-price {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
    }

    .arbitrage-price .price-label {
        font-size: 10px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .arbitrage-price .price-value {
        font-family: var(--font-mono);
        font-size: 16px;
        font-weight: 700;
    }

    .arbitrage-price.buy .price-value {
        color: var(--green-success);
    }

    .arbitrage-price.sell .price-value {
        color: var(--red-error);
    }

    .arbitrage-price .price-player {
        font-size: 10px;
        color: var(--text-tertiary);
    }

    .arbitrage-arrow {
        font-size: 18px;
        color: var(--gold-primary);
    }

    .arbitrage-ducat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 10px;
        background: rgba(212, 167, 55, 0.05);
        border-radius: 4px;
        margin-bottom: 10px;
        font-size: 11px;
    }

    .arbitrage-ducat .ducat-info {
        color: var(--text-secondary);
    }

    .arbitrage-ducat .ducat-efficiency {
        font-family: var(--font-mono);
        color: var(--text-tertiary);
    }

    .arbitrage-ducat .ducat-efficiency.good {
        color: var(--green-success);
    }

    .arbitrage-actions {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }

    .arbitrage-empty {
        padding: 40px 20px;
        text-align: center;
    }

    .arbitrage-tips {
        margin-top: 20px;
        padding: 16px;
        background: rgba(74, 158, 255, 0.05);
        border: 1px solid rgba(74, 158, 255, 0.15);
        border-radius: 6px;
        text-align: left;
    }

    .arbitrage-tips .tip-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--blue-primary);
        margin-bottom: 8px;
    }

    .arbitrage-tips ul {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .arbitrage-tips li {
        font-size: 12px;
        color: var(--text-secondary);
        padding: 4px 0;
        padding-left: 16px;
        position: relative;
    }

    .arbitrage-tips li::before {
        content: '•';
        position: absolute;
        left: 0;
        color: var(--blue-primary);
    }

    /* 收藏夹仪表盘样式 */
    .dashboard-container {
        padding: 16px;
    }

    .dashboard-header {
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(212, 167, 55, 0.2);
    }

    .dashboard-title {
        font-family: var(--font-display);
        font-size: 16px;
        color: var(--gold-primary);
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }

    .dashboard-subtitle {
        font-size: 12px;
        color: var(--text-tertiary);
    }

    .dashboard-summary {
        display: grid;
        grid-template-columns: 2fr 1fr 1fr;
        gap: 10px;
        margin-bottom: 16px;
    }

    .dashboard-stat {
        text-align: center;
        padding: 14px 10px;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 6px;
    }

    .dashboard-stat.main {
        background: rgba(212, 167, 55, 0.1);
        border: 1px solid rgba(212, 167, 55, 0.2);
    }

    .dashboard-stat-label {
        font-size: 10px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }

    .dashboard-stat-value {
        font-family: var(--font-mono);
        font-size: 20px;
        font-weight: 700;
        color: var(--text-primary);
    }

    .dashboard-stat.main .dashboard-stat-value {
        color: var(--gold-primary);
        font-size: 24px;
    }

    .dashboard-changes {
        margin-bottom: 16px;
        padding: 14px;
        background: rgba(0, 0, 0, 0.15);
        border-radius: 6px;
    }

    .change-title {
        font-size: 11px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .change-bars {
        display: flex;
        gap: 8px;
    }

    .change-bar {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 10px 8px;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 4px;
    }

    .change-bar.up {
        border-top: 2px solid var(--green-success);
    }

    .change-bar.stable {
        border-top: 2px solid var(--text-tertiary);
    }

    .change-bar.down {
        border-top: 2px solid var(--red-error);
    }

    .change-icon {
        font-size: 14px;
        margin-bottom: 4px;
    }

    .change-bar.up .change-icon {
        color: var(--green-success);
    }

    .change-bar.stable .change-icon {
        color: var(--text-tertiary);
    }

    .change-bar.down .change-icon {
        color: var(--red-error);
    }

    .change-count {
        font-family: var(--font-mono);
        font-size: 18px;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 2px;
    }

    .change-label {
        font-size: 10px;
        color: var(--text-tertiary);
    }

    .dashboard-items-title {
        font-size: 11px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .dashboard-items {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-bottom: 16px;
        max-height: 300px;
        overflow-y: auto;
    }

    .dashboard-item {
        padding: 12px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.2s ease-out;
        animation: fadeInUp 0.3s ease-out backwards;
    }

    .dashboard-item:hover {
        background: var(--bg-overlay);
        border-color: rgba(212, 167, 55, 0.2);
        transform: translateX(2px);
        box-shadow: inset 3px 0 0 var(--gold-primary), var(--shadow-gold-sm);
    }

    .dashboard-item-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .dashboard-item-name {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-primary);
    }

    .dashboard-item-price {
        font-family: var(--font-mono);
        font-size: 14px;
        font-weight: 600;
        color: var(--gold-primary);
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .item-change {
        font-size: 10px;
        padding: 1px 4px;
        border-radius: 2px;
    }

    .item-change.up {
        background: rgba(74, 222, 128, 0.15);
        color: var(--green-success);
    }

    .item-change.down {
        background: rgba(239, 68, 68, 0.15);
        color: var(--red-error);
    }

    .dashboard-item-detail {
        display: flex;
        gap: 10px;
        margin-top: 6px;
        font-size: 11px;
        color: var(--text-tertiary);
    }

    .detail-label {
        color: var(--text-tertiary);
    }

    .detail-value {
        font-family: var(--font-mono);
        color: var(--text-secondary);
    }

    .detail-spread {
        font-family: var(--font-mono);
        color: var(--gold-primary);
    }

    .dashboard-actions {
        display: flex;
        gap: 8px;
    }

    /* 利润计算器样式 */
    .profit-calc-container {
        padding: 16px;
    }

    .profit-calc-title {
        font-family: var(--font-display);
        font-size: 16px;
        color: var(--gold-primary);
        letter-spacing: 0.05em;
        margin-bottom: 16px;
    }

    .profit-form-group {
        margin-bottom: 12px;
    }

    .profit-form-label {
        display: block;
        font-size: 11px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }

    .profit-material-row {
        display: flex;
        gap: 8px;
        margin-bottom: 8px;
        align-items: center;
    }

    .profit-material-input {
        flex: 1;
        padding: 6px 10px;
        background: rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        color: var(--text-primary);
        font-size: 12px;
    }

    .profit-material-input:focus {
        outline: none;
        border-color: rgba(212, 167, 55, 0.3);
    }

    .profit-material-input.short {
        width: 60px;
        flex: none;
    }

    .profit-result {
        margin-top: 16px;
        padding: 12px;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }

    .profit-result-row {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        font-size: 13px;
    }

    .profit-result-label {
        color: var(--text-secondary);
    }

    .profit-result-value {
        font-family: var(--font-mono);
        font-weight: 600;
    }

    .profit-result-value.positive {
        color: var(--green-success);
    }

    .profit-result-value.negative {
        color: var(--red-error);
    }

    .profit-recommendation {
        margin-top: 12px;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 12px;
        text-align: center;
    }

    .profit-recommendation.good {
        background: rgba(74, 222, 128, 0.1);
        border: 1px solid rgba(74, 222, 128, 0.2);
        color: var(--green-success);
    }

    .profit-recommendation.bad {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        color: var(--red-error);
    }

    /* 通知设置面板样式 */
    .notify-settings-container { padding: 16px; }
    .notify-settings-header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid rgba(212, 167, 55, 0.2); }
    .notify-settings-title { font-family: var(--font-display); font-size: 16px; color: var(--gold-primary); letter-spacing: 0.05em; margin-bottom: 4px; }
    .notify-settings-subtitle { font-size: 12px; color: var(--text-tertiary); }
    .notify-section { margin-bottom: 16px; }
    .notify-section-title { font-size: 11px; color: var(--text-tertiary); letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 10px; }
    .notify-option { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: rgba(0,0,0,0.2); border-radius: 4px; margin-bottom: 6px; }
    .notify-option-info { display: flex; flex-direction: column; gap: 2px; }
    .notify-option-label { font-size: 13px; color: var(--text-primary); font-weight: 600; }
    .notify-option-desc { font-size: 11px; color: var(--text-tertiary); }
    .notify-toggle { position: relative; display: inline-block; width: 40px; height: 22px; cursor: pointer; }
    .notify-toggle input { opacity: 0; width: 0; height: 0; }
    .notify-toggle-slider { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.1); border-radius: 11px; transition: 0.3s; }
    .notify-toggle-slider::before { content: ''; position: absolute; height: 16px; width: 16px; left: 3px; bottom: 3px; background: var(--text-tertiary); border-radius: 50%; transition: 0.3s; }
    .notify-toggle input:checked + .notify-toggle-slider { background: rgba(74, 222, 128, 0.3); }
    .notify-toggle input:checked + .notify-toggle-slider::before { transform: translateX(18px); background: var(--green-success); }
    .notify-frequency-options { display: flex; gap: 6px; }
    .notify-freq-btn { flex: 1; padding: 8px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; color: var(--text-tertiary); font-size: 12px; cursor: pointer; transition: all 0.2s; }
    .notify-freq-btn:hover { background: rgba(212, 167, 55, 0.1); border-color: rgba(212, 167, 55, 0.3); color: var(--gold-primary); }
    .notify-freq-btn.active { background: rgba(212, 167, 55, 0.15); border-color: var(--gold-primary); color: var(--gold-primary); }
    .notify-threshold-row { display: flex; align-items: center; gap: 12px; }
    .notify-range { flex: 1; accent-color: var(--gold-primary); height: 4px; }
    .notify-threshold-val { font-family: var(--font-mono); font-size: 14px; font-weight: 600; color: var(--gold-primary); min-width: 40px; }
    .notify-threshold-desc { font-size: 11px; color: var(--text-tertiary); margin-top: 6px; }
    .notify-actions { display: flex; gap: 8px; margin-top: 16px; }

    /* 模式切换按钮 */
    .mode-toggle-bar {
        display: flex;
        gap: 6px;
        margin-bottom: 12px;
    }
    .mode-toggle-btn {
        flex: 1;
        padding: 8px 12px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px;
        color: var(--text-tertiary);
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
    }
    .mode-toggle-btn:hover {
        background: rgba(212, 167, 55, 0.1);
        border-color: rgba(212, 167, 55, 0.3);
        color: var(--gold-primary);
    }
    .mode-toggle-btn.active {
        background: rgba(212, 167, 55, 0.15);
        border-color: var(--gold-primary);
        color: var(--gold-primary);
        font-weight: 600;
    }

    /* 购买方案迷你卡片 */
    .buy-plan-mini {
        margin-top: 6px;
        padding: 6px 8px;
        background: rgba(99, 102, 241, 0.08);
        border: 1px solid rgba(99, 102, 241, 0.15);
        border-radius: 6px;
        font-size: 11px;
    }
    .bp-mini-row {
        display: flex;
        justify-content: space-between;
        padding: 2px 0;
        color: var(--text-secondary);
    }
    .bp-mini-row span:last-child {
        color: var(--gold-primary);
        font-family: var(--font-mono);
    }
    .bp-more {
        color: var(--text-tertiary);
        font-style: italic;
    }
`;
document.head.appendChild(sidebarStyles);

// ===== 利润计算器 =====

function showProfitCalculator() {
    const content = openDetailPanel('加载利润计算器...');
    if (!content) return;

    content.innerHTML = `
        <div class="profit-calc-container">
            <div class="profit-calc-title">利润计算器</div>
            <div class="profit-form-group">
                <label class="profit-form-label">成品物品</label>
                <input type="text" class="profit-material-input" id="profit-item-input" placeholder="输入成品名称..." style="width:100%">
                <div id="profit-item-suggestions" style="display:none; position:absolute; z-index:10;"></div>
            </div>
            <div class="profit-form-group">
                <label class="profit-form-label">材料列表</label>
                <div id="profit-materials">
                    <div class="profit-material-row">
                        <input type="text" class="profit-material-input" placeholder="材料名称" data-type="name">
                        <input type="number" class="profit-material-input short" placeholder="数量" data-type="qty" value="1" min="1">
                        <input type="number" class="profit-material-input short" placeholder="单价" data-type="cost" min="0">
                        <button class="compare-remove-btn" onclick="this.parentElement.remove()">×</button>
                    </div>
                </div>
                <button class="compare-add-btn" onclick="addProfitMaterial()" style="margin-top:8px;">+ 添加材料</button>
            </div>
            <button class="form-btn primary" onclick="runProfitCalc()" style="width:100%; margin-top:12px;">计算利润</button>
            <div id="profit-result"></div>
        </div>
    `;

    // 绑定成品输入建议
    const itemInput = document.getElementById('profit-item-input');
    let debounce;
    itemInput.addEventListener('input', () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => showProfitItemSuggestions(itemInput), 300);
    });
}

async function showProfitItemSuggestions(input) {
    const query = input.value.trim();
    const sugDiv = document.getElementById('profit-item-suggestions');
    if (!sugDiv || query.length < 1) {
        if (sugDiv) sugDiv.style.display = 'none';
        return;
    }

    try {
        const res = await fetch(`/api/suggest?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (!data.suggestions || data.suggestions.length === 0) {
            sugDiv.style.display = 'none';
            return;
        }

        sugDiv.textContent = '';
        data.suggestions.forEach((suggestion) => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.textContent = suggestion;
            item.addEventListener('click', () => selectProfitItem(suggestion));
            sugDiv.appendChild(item);
        });
        sugDiv.style.display = 'block';
        sugDiv.style.cssText = 'display:block; position:absolute; background:var(--glass-bg); border:var(--glass-border); border-radius:8px; max-height:150px; overflow-y:auto; z-index:10; width:100%;';
    } catch (e) {
        sugDiv.style.display = 'none';
    }
}

function selectProfitItem(itemId) {
    document.getElementById('profit-item-input').value = itemId;
    document.getElementById('profit-item-suggestions').style.display = 'none';
}

function addProfitMaterial() {
    const container = document.getElementById('profit-materials');
    const row = document.createElement('div');
    row.className = 'profit-material-row';
    row.innerHTML = `
        <input type="text" class="profit-material-input" placeholder="材料名称" data-type="name">
        <input type="number" class="profit-material-input short" placeholder="数量" data-type="qty" value="1" min="1">
        <input type="number" class="profit-material-input short" placeholder="单价" data-type="cost" min="0">
        <button class="compare-remove-btn" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(row);
}

async function runProfitCalc() {
    const itemId = document.getElementById('profit-item-input').value.trim();
    if (!itemId) {
        showToast('请输入成品物品', 'warning');
        return;
    }

    const rows = document.querySelectorAll('#profit-materials .profit-material-row');
    const materials = [];
    rows.forEach(row => {
        const name = row.querySelector('[data-type="name"]').value.trim();
        const qty = parseInt(row.querySelector('[data-type="qty"]').value) || 1;
        const cost = parseInt(row.querySelector('[data-type="cost"]').value) || 0;
        if (name) {
            materials.push({ item_id: name, quantity: qty, unit_cost: cost });
        }
    });

    if (materials.length === 0) {
        showToast('请至少添加一种材料', 'warning');
        return;
    }

    const resultDiv = document.getElementById('profit-result');
    resultDiv.innerHTML = '<div class="loading"><div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div></div>';

    try {
        // 先解析物品ID
        const resolveRes = await fetch(`/api/resolve/${encodeURIComponent(itemId)}`);
        const resolveData = await resolveRes.json();
        const resolvedId = resolveData.found ? resolveData.item_id : itemId;

        // 解析材料ID
        const resolvedMaterials = [];
        for (const mat of materials) {
            const matRes = await fetch(`/api/resolve/${encodeURIComponent(mat.item_id)}`);
            const matData = await matRes.json();
            resolvedMaterials.push({
                item_id: matData.found ? matData.item_id : mat.item_id,
                quantity: mat.quantity,
                unit_cost: mat.unit_cost,
            });
        }

        const res = await fetch('/api/profit/calculate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ item_id: resolvedId, material_costs: resolvedMaterials })
        });
        const data = await res.json();

        if (data.error) {
            resultDiv.innerHTML = `<div class="profit-recommendation bad">计算失败: ${escapeHtml(data.error)}</div>`;
            return;
        }

        renderProfitResult(data, resultDiv);
    } catch (err) {
        resultDiv.innerHTML = `<div class="profit-recommendation bad">请求失败</div>`;
    }
}

function renderProfitResult(data, container) {
    const p = data.profit;
    const sellClass = p.sell_profit > 0 ? 'positive' : (p.sell_profit < 0 ? 'negative' : '');
    const buyClass = p.buy_profit > 0 ? 'positive' : (p.buy_profit < 0 ? 'negative' : '');

    let html = `
        <div class="profit-result">
            <div class="profit-result-row">
                <span class="profit-result-label">成品 (${escapeHtml(data.display)})</span>
                <span class="profit-result-value">卖 ${data.sell_price || '-'}p / 收 ${data.buy_price || '-'}p</span>
            </div>
            <div class="profit-result-row">
                <span class="profit-result-label">材料总成本</span>
                <span class="profit-result-value">${data.total_cost}p</span>
            </div>
            <div class="profit-result-row">
                <span class="profit-result-label">按卖价利润</span>
                <span class="profit-result-value ${sellClass}">${p.sell_profit !== null ? p.sell_profit + 'p (' + p.sell_margin + '%)' : '-'}</span>
            </div>
            <div class="profit-result-row">
                <span class="profit-result-label">按收价利润</span>
                <span class="profit-result-value ${buyClass}">${p.buy_profit !== null ? p.buy_profit + 'p (' + p.buy_margin + '%)' : '-'}</span>
            </div>
        </div>
    `;

    // 材料明细
    if (data.materials && data.materials.length > 0) {
        html += `<div style="margin-top:12px; font-size:11px; color:var(--text-tertiary);">材料明细:</div>`;
        data.materials.forEach(mat => {
            html += `<div class="profit-result-row" style="font-size:12px;">
                <span style="color:var(--text-secondary)">${escapeHtml(mat.display)} x${mat.quantity}</span>
                <span style="font-family:var(--font-mono)">${mat.total_cost}p</span>
            </div>`;
        });
    }

    // 推荐
    const isGood = p.sell_profit && p.sell_profit > 0;
    html += `<div class="profit-recommendation ${isGood ? 'good' : 'bad'}">
        ${isGood ? '✓ 制造盈利，建议制作' : '✗ 制造亏损，不建议制作'}
    </div>`;

    container.innerHTML = html;
}

// 绑定利润计算器按钮
document.getElementById('profit-calc-btn')?.addEventListener('click', () => {
    document.getElementById('more-menu')?.classList.remove('active');
    showProfitCalculator();
});

// ===== 通知设置面板 =====

const NOTIFY_SETTINGS_KEY = 'warframe_notify_settings';

function loadNotifySettings() {
    try {
        const saved = localStorage.getItem(NOTIFY_SETTINGS_KEY);
        if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { browserNotify: true, soundAlert: true, alertFrequency: 'realtime', priceChangeThreshold: 5 };
}

function saveNotifySettings(settings) {
    try {
        localStorage.setItem(NOTIFY_SETTINGS_KEY, JSON.stringify(settings));
    } catch (e) {}
}

function showNotificationSettings() {
    const content = openDetailPanel('通知设置');
    if (!content) return;

    const settings = loadNotifySettings();

    content.innerHTML = `
        <div class="notify-settings-container">
            <div class="notify-settings-header">
                <h3 class="notify-settings-title">通知设置</h3>
                <div class="notify-settings-subtitle">配置价格提醒和通知方式</div>
            </div>

            <div class="notify-section">
                <div class="notify-section-title">通知方式</div>
                <div class="notify-option">
                    <div class="notify-option-info">
                        <span class="notify-option-label">浏览器通知</span>
                        <span class="notify-option-desc">价格触发时弹出浏览器通知</span>
                    </div>
                    <label class="notify-toggle">
                        <input type="checkbox" id="notify-browser" ${settings.browserNotify ? 'checked' : ''}>
                        <span class="notify-toggle-slider"></span>
                    </label>
                </div>
                <div class="notify-option">
                    <div class="notify-option-info">
                        <span class="notify-option-label">声音提醒</span>
                        <span class="notify-option-desc">价格触发时播放提示音</span>
                    </div>
                    <label class="notify-toggle">
                        <input type="checkbox" id="notify-sound" ${settings.soundAlert ? 'checked' : ''}>
                        <span class="notify-toggle-slider"></span>
                    </label>
                </div>
            </div>

            <div class="notify-section">
                <div class="notify-section-title">检查频率</div>
                <div class="notify-frequency-options">
                    <button class="notify-freq-btn ${settings.alertFrequency === 'realtime' ? 'active' : ''}" data-freq="realtime">实时</button>
                    <button class="notify-freq-btn ${settings.alertFrequency === '5min' ? 'active' : ''}" data-freq="5min">5分钟</button>
                    <button class="notify-freq-btn ${settings.alertFrequency === '15min' ? 'active' : ''}" data-freq="15min">15分钟</button>
                    <button class="notify-freq-btn ${settings.alertFrequency === '30min' ? 'active' : ''}" data-freq="30min">30分钟</button>
                </div>
            </div>

            <div class="notify-section">
                <div class="notify-section-title">价格变动阈值</div>
                <div class="notify-threshold-row">
                    <input type="range" id="notify-threshold" min="1" max="50" value="${settings.priceChangeThreshold}" class="notify-range">
                    <span id="notify-threshold-value" class="notify-threshold-val">${settings.priceChangeThreshold}%</span>
                </div>
                <div class="notify-threshold-desc">价格变动超过此百分比时触发通知</div>
            </div>

            <div class="notify-actions">
                <button class="detail-action-btn" onclick="testNotification()">测试通知</button>
                <button class="detail-action-btn" onclick="saveNotifySettingsFromUI()">保存设置</button>
            </div>
        </div>
    `;

    // 绑定滑块事件
    const slider = document.getElementById('notify-threshold');
    const valSpan = document.getElementById('notify-threshold-value');
    if (slider && valSpan) {
        slider.addEventListener('input', () => {
            valSpan.textContent = slider.value + '%';
        });
    }

    // 绑定频率按钮
    document.querySelectorAll('.notify-freq-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.notify-freq-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

function saveNotifySettingsFromUI() {
    const settings = {
        browserNotify: document.getElementById('notify-browser')?.checked ?? true,
        soundAlert: document.getElementById('notify-sound')?.checked ?? true,
        alertFrequency: document.querySelector('.notify-freq-btn.active')?.dataset.freq || 'realtime',
        priceChangeThreshold: parseInt(document.getElementById('notify-threshold')?.value) || 5,
    };
    saveNotifySettings(settings);
    showToast('通知设置已保存', 'success');
}

function testNotification() {
    // 先播放测试声音
    playNotificationSound();

    if (Notification.permission === 'granted') {
        new Notification('Warframe 交易助手', { body: '测试通知成功！价格提醒将以此方式通知您。', icon: '/static/favicon.ico' });
        showToast('测试通知已发送（含声音）', 'success');
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(perm => {
            if (perm === 'granted') {
                new Notification('Warframe 交易助手', { body: '通知权限已开启！', icon: '/static/favicon.ico' });
                showToast('通知权限已开启', 'success');
            } else {
                showToast('通知权限被拒绝', 'warning');
            }
        });
    } else {
        showToast('通知权限已被禁止，请在浏览器设置中开启', 'error');
    }
}

// 绑定通知设置按钮
document.getElementById('notify-settings-btn')?.addEventListener('click', () => {
    document.getElementById('more-menu')?.classList.remove('active');
    showNotificationSettings();
});

// ===== 虚空裂隙追踪 =====

async function showFissureTracker() {
    const content = openDetailPanel('加载虚空裂隙...');
    if (!content) return;
    const ver = getPanelVersion();

    try {
        const res = await fetch('/api/fissures');
        if (getPanelVersion() !== ver) return;
        const data = await res.json();

        if (data.error) {
            content.innerHTML = createChartError(data.error);
            return;
        }

        const tierIcons = {
            'Lith': '🔹',
            'Meso': '🔸',
            'Neo': '🔶',
            'Axi': '🔷',
            'Requiem': '💀'
        };

        const tierNames = {
            'Lith': '古纪 (Lith)',
            'Meso': '前纪 (Meso)',
            'Neo': '中纪 (Neo)',
            'Axi': '后纪 (Axi)',
            'Requiem': '安魂 (Requiem)'
        };

        const isLive = data.source === 'live';
        let html = `
            <div class="profit-calc-container">
                <div class="profit-calc-title">虚空裂隙追踪</div>
                <div style="font-size:12px; color:var(--text-tertiary); margin-bottom:16px;">
                    ${isLive ? '当前活跃的虚空裂隙任务' : (data.message || '遗物掉落数据')}
                </div>
        `;

        let hasFissures = false;

        Object.entries(data.fissures).forEach(([tier, fissures]) => {
            if (fissures.length === 0) return;
            hasFissures = true;

            html += `
                <div style="margin-bottom:16px;">
                    <div style="font-size:13px; color:var(--gold-primary); margin-bottom:8px; font-weight:600;">
                        ${tierIcons[tier] || '◆'} ${tierNames[tier] || tier} (${fissures.length})
                    </div>
            `;

            fissures.forEach(f => {
                const rareDrops = (f.rare_drops || []).map(r =>
                    `<span style="color:var(--gold-primary);">${r.name} (${r.chance}%)</span>`
                ).join(', ');
                const uncommonDrops = (f.uncommon_drops || []).map(r =>
                    `<span style="color:var(--text-secondary);">${r.name} (${r.chance}%)</span>`
                ).join(', ');

                html += `
                    <div class="list-item" style="margin-bottom:6px; padding:8px 12px;">
                        <div class="item-header">
                            <span class="item-name" style="font-size:12px;">${f.node}</span>
                            ${f.missionType ? `<span class="item-badge" style="font-size:10px;">${f.missionType}</span>` : ''}
                        </div>
                        ${f.enemy ? `<div class="item-sub" style="font-size:11px;">${f.enemy}</div>` : ''}
                        ${rareDrops ? `<div style="font-size:11px; margin-top:4px;">稀有: ${rareDrops}</div>` : ''}
                        ${uncommonDrops ? `<div style="font-size:10px; color:var(--text-tertiary);">银: ${uncommonDrops}</div>` : ''}
                    </div>
                `;
            });

            html += `</div>`;
        });

        if (!hasFissures) {
            html += `
                <div class="empty-state" style="padding:32px 0;">
                    <div class="empty-state-icon">🔔</div>
                    <div class="empty-state-text">暂无裂隙数据</div>
                    <div class="empty-state-sub">请稍后再试</div>
                </div>
            `;
        }

        html += `</div>`;
        if (getPanelVersion() !== ver) return;
        content.innerHTML = html;
    } catch (err) {
        if (getPanelVersion() !== ver) return;
        content.innerHTML = createChartError('获取裂隙数据失败');
    }
}

// 绑定虚空裂隙按钮
document.getElementById('fissure-btn')?.addEventListener('click', () => {
    document.getElementById('more-menu')?.classList.remove('active');
    showFissureTracker();
});

// ===== 装备百科 =====

// 全局数据存储，避免 onclick 内嵌 JSON 被 HTML 解析破坏
const _wikiStore = { warframes: [], weapons: [], mods: [] };

async function showWikiWarframes(q) {
    const content = openDetailPanel('加载装备百科...');
    if (!content) return;

    try {
        const url = q ? `/api/wiki/warframes?q=${encodeURIComponent(q)}` : '/api/wiki/warframes';
        const res = await fetch(url);
        const data = await res.json();

        let html = `<div class="profit-calc-container">
            <div class="profit-calc-title">🛡️ 装备百科</div>
            <div class="wiki-search-row">
                <input type="text" id="wiki-warframe-search" class="wiki-search-input"
                    placeholder="搜索 Warframe..." value="${q || ''}" autocomplete="off">
                <button class="wiki-search-btn" onclick="showWikiWarframes(document.getElementById('wiki-warframe-search').value)">搜索</button>
            </div>
            <div class="wiki-tabs">
                <button class="wiki-tab active" onclick="showWikiWarframes(document.getElementById('wiki-warframe-search').value)">Warframe</button>
                <button class="wiki-tab" onclick="showWikiWeapons('primary','')">主武器</button>
                <button class="wiki-tab" onclick="showWikiWeapons('secondary','')">副武器</button>
                <button class="wiki-tab" onclick="showWikiWeapons('melee','')">近战武器</button>
            </div>
            <div class="wiki-count">共 ${data.total} 个结果</div>
            <div class="wiki-grid">`;

        _wikiStore.warframes = data.warframes;
        data.warframes.forEach((wf, i) => {
            const displayName = wf.nameZh ? `${wf.nameZh}（${wf.name}）` : wf.name;
            html += `<div class="wiki-card" onclick="showWikiWarframeDetail(${i})">
                <div class="wiki-card-name">${displayName}</div>
                <div class="wiki-card-stats">
                    <span class="wiki-stat">❤️ ${wf.health}</span>
                    <span class="wiki-stat">🛡️ ${wf.shield}</span>
                    <span class="wiki-stat">⚔️ ${wf.armor}</span>
                    <span class="wiki-stat">⚡ ${wf.power}</span>
                </div>
                <div class="wiki-card-sub">速度 ${wf.sprintSpeed} · 段位 ${wf.masteryReq}</div>
            </div>`;
        });

        html += `</div></div>`;
        content.innerHTML = html;

        const searchInput = document.getElementById('wiki-warframe-search');
        if (searchInput) {
            searchInput.addEventListener('keydown', e => {
                if (e.key === 'Enter') showWikiWarframes(searchInput.value);
            });
        }
    } catch (err) {
        content.innerHTML = createChartError('加载装备百科失败: ' + err.message);
    }
}

function showWikiWarframeDetail(idx) {
    const wf = _wikiStore.warframes[idx];
    if (!wf) return;
    const content = document.getElementById('detail-content');
    if (!content) return;

    const displayName = wf.nameZh ? `${wf.nameZh}（${wf.name}）` : wf.name;

    let html = `<div class="profit-calc-container">
        <div class="wiki-detail-back" onclick="showWikiWarframes('')">← 返回列表</div>
        <div class="profit-calc-title">${displayName}</div>
        <div class="wiki-detail-desc">${wf.description || ''}</div>
        ${wf.marketUrl ? `<a class="wiki-market-link" href="${wf.marketUrl}" target="_blank" rel="noopener">${wf.isPrime ? '在 warframe.market 查看蓝图交易 →' : '在 warframe.market 查看交易 →'}</a>` : ''}
        ${wf.components && wf.components.length > 0 ? `
        <div class="wiki-detail-section">
            <div class="wiki-detail-label">Prime 部件交易</div>
            <div class="wiki-detail-grid">
                ${wf.components.map(comp => {
                    const compUrl = wf.marketUrl ? wf.marketUrl.replace('_blueprint', '_' + comp.name.toLowerCase().replace(/\s+/g, '_')) : '';
                    return `<a class="wiki-comp-link" href="${compUrl}" target="_blank" rel="noopener">
                        <span class="wiki-comp-name">${comp.name}</span>
                        ${comp.ducats ? `<span class="wiki-comp-ducats">◆ ${comp.ducats}</span>` : ''}
                    </a>`;
                }).join('')}
            </div>
        </div>` : ''}

        <div class="wiki-detail-section">
            <div class="wiki-detail-label">基础属性</div>
            <div class="wiki-detail-grid">
                <div class="wiki-detail-stat"><span class="stat-label">生命</span><span class="stat-value">${wf.health}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">护盾</span><span class="stat-value">${wf.shield}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">护甲</span><span class="stat-value">${wf.armor}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">能量</span><span class="stat-value">${wf.power}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">冲刺速度</span><span class="stat-value">${wf.sprintSpeed}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">段位需求</span><span class="stat-value">${wf.masteryReq}</span></div>
            </div>
        </div>`;

    if (wf.passiveDescription) {
        html += `<div class="wiki-detail-section">
            <div class="wiki-detail-label">被动技能</div>
            <div class="wiki-detail-desc">${wf.passiveDescription}</div>
        </div>`;
    }

    if (wf.abilities && wf.abilities.length > 0) {
        html += `<div class="wiki-detail-section">
            <div class="wiki-detail-label">技能</div>`;
        wf.abilities.forEach((a, i) => {
            html += `<div class="wiki-ability">
                <div class="wiki-ability-name">${i + 1}. ${a.name}</div>
                <div class="wiki-ability-desc">${a.description || ''}</div>
            </div>`;
        });
        html += `</div>`;
    }

    html += `</div>`;
    content.innerHTML = html;
}

// ===== 武器百科 =====

async function showWikiWeapons(type, q) {
    const content = openDetailPanel('加载武器数据...');
    if (!content) return;

    try {
        let url = `/api/wiki/weapons?type=${type}`;
        if (q) url += `&q=${encodeURIComponent(q)}`;
        const res = await fetch(url);
        const data = await res.json();

        const typeNames = { primary: '主武器', secondary: '副武器', melee: '近战武器' };
        const typeName = typeNames[type] || type;

        let html = `<div class="profit-calc-container">
            <div class="profit-calc-title">🔫 ${typeName}</div>
            <div class="wiki-search-row">
                <input type="text" id="wiki-weapon-search" class="wiki-search-input"
                    placeholder="搜索武器..." value="${q || ''}" autocomplete="off">
                <button class="wiki-search-btn" onclick="showWikiWeapons('${type}',document.getElementById('wiki-weapon-search').value)">搜索</button>
            </div>
            <div class="wiki-tabs">
                <button class="wiki-tab ${type==='primary'?'active':''}" onclick="showWikiWeapons('primary','')">主武器</button>
                <button class="wiki-tab ${type==='secondary'?'active':''}" onclick="showWikiWeapons('secondary','')">副武器</button>
                <button class="wiki-tab ${type==='melee'?'active':''}" onclick="showWikiWeapons('melee','')">近战武器</button>
                <button class="wiki-tab" onclick="showWikiWarframes('')">Warframe</button>
            </div>
            <div class="wiki-count">共 ${data.total} 个结果</div>
            <div class="wiki-grid">`;

        _wikiStore.weapons = data.weapons;
        data.weapons.forEach((w, i) => {
            const critPct = w.criticalChance ? (w.criticalChance * 100).toFixed(0) + '%' : '-';
            const statusPct = w.procChance ? (w.procChance * 100).toFixed(0) + '%' : '-';
            const displayName = w.nameZh ? `${w.nameZh}（${w.name}）` : w.name;
            html += `<div class="wiki-card" onclick="showWikiWeaponDetail(${i})">
                <div class="wiki-card-name">${displayName}</div>
                <div class="wiki-card-stats">
                    <span class="wiki-stat">💥 ${w.totalDamage}</span>
                    <span class="wiki-stat">🎯 ${critPct}</span>
                    <span class="wiki-stat">⚡ ${statusPct}</span>
                </div>
                <div class="wiki-card-sub">射速 ${w.fireRate} · 段位 ${w.masteryReq}</div>
            </div>`;
        });

        html += `</div></div>`;
        content.innerHTML = html;

        const searchInput = document.getElementById('wiki-weapon-search');
        if (searchInput) {
            searchInput.addEventListener('keydown', e => {
                if (e.key === 'Enter') showWikiWeapons(type, searchInput.value);
            });
        }
    } catch (err) {
        content.innerHTML = createChartError('加载武器数据失败: ' + err.message);
    }
}

function showWikiWeaponDetail(idx) {
    const w = _wikiStore.weapons[idx];
    if (!w) return;
    const content = document.getElementById('detail-content');
    if (!content) return;

    const critPct = w.criticalChance ? (w.criticalChance * 100).toFixed(1) + '%' : '-';
    const critMul = w.criticalMultiplier ? w.criticalMultiplier + 'x' : '-';
    const statusPct = w.procChance ? (w.procChance * 100).toFixed(1) + '%' : '-';
    const displayName = w.nameZh ? `${w.nameZh}（${w.name}）` : w.name;

    let html = `<div class="profit-calc-container">
        <div class="wiki-detail-back" onclick="showWikiWeapons('${w.category}','')">← 返回列表</div>
        <div class="profit-calc-title">${displayName}</div>
        ${w.marketUrl ? `<a class="wiki-market-link" href="${w.marketUrl}" target="_blank" rel="noopener">${w.isPrime ? '在 warframe.market 查看蓝图交易 →' : '在 warframe.market 查看交易 →'}</a>` : ''}
        ${w.components && w.components.length > 0 ? `
        <div class="wiki-detail-section">
            <div class="wiki-detail-label">Prime 部件交易</div>
            <div class="wiki-detail-grid">
                ${w.components.map(comp => {
                    const compUrl = w.marketUrl ? w.marketUrl.replace('_blueprint', '_' + comp.name.toLowerCase().replace(/\s+/g, '_')) : '';
                    return `<a class="wiki-comp-link" href="${compUrl}" target="_blank" rel="noopener">
                        <span class="wiki-comp-name">${comp.name}</span>
                        ${comp.ducats ? `<span class="wiki-comp-ducats">◆ ${comp.ducats}</span>` : ''}
                    </a>`;
                }).join('')}
            </div>
        </div>` : ''}
        <div class="wiki-detail-desc">${w.description || ''}</div>

        <div class="wiki-detail-section">
            <div class="wiki-detail-label">战斗属性</div>
            <div class="wiki-detail-grid">
                <div class="wiki-detail-stat"><span class="stat-label">总伤害</span><span class="stat-value">${w.totalDamage}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">暴击率</span><span class="stat-value">${critPct}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">暴击倍率</span><span class="stat-value">${critMul}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">触发率</span><span class="stat-value">${statusPct}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">射速</span><span class="stat-value">${w.fireRate}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">弹匣</span><span class="stat-value">${w.magazineSize}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">装填</span><span class="stat-value">${w.reloadTime}s</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">精准</span><span class="stat-value">${w.accuracy || '-'}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">噪音</span><span class="stat-value">${w.noise || '-'}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">扳机</span><span class="stat-value">${w.trigger || '-'}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">段位需求</span><span class="stat-value">${w.masteryReq}</span></div>
            </div>
        </div>
    </div>`;
    content.innerHTML = html;
}

// ===== MOD 数据库 =====

async function showWikiMods(q, polarity, rarity) {
    const content = openDetailPanel('加载 MOD 数据...');
    if (!content) return;

    try {
        let url = '/api/wiki/mods?';
        if (q) url += `q=${encodeURIComponent(q)}&`;
        if (polarity) url += `polarity=${encodeURIComponent(polarity)}&`;
        if (rarity) url += `rarity=${encodeURIComponent(rarity)}&`;
        const res = await fetch(url);
        const data = await res.json();

        let html = `<div class="profit-calc-container">
            <div class="profit-calc-title">📖 MOD 数据库</div>
            <div class="wiki-search-row">
                <input type="text" id="wiki-mod-search" class="wiki-search-input"
                    placeholder="搜索 MOD..." value="${q || ''}" autocomplete="off">
                <button class="wiki-search-btn" onclick="searchWikiMods()">搜索</button>
            </div>
            <div class="wiki-filters">
                <select id="wiki-mod-polarity" onchange="searchWikiMods()">
                    <option value="">全部极性</option>
                    <option value="madurai" ${polarity==='madurai'?'selected':''}>Madurai (V)</option>
                    <option value="vazarin" ${polarity==='vazarin'?'selected':''}>Vazarin (D)</option>
                    <option value="naramon" ${polarity==='naramon'?'selected':''}>Naramon (横线)</option>
                    <option value="zenurik" ${polarity==='zenurik'?'selected':''}>Zenurik (—)</option>
                    <option value="penjaga" ${polarity==='penjaga'?'selected':''}>Penjaga (Y)</option>
                    <option value="umbra" ${polarity==='umbra'?'selected':''}>Umbra</option>
                </select>
                <select id="wiki-mod-rarity" onchange="searchWikiMods()">
                    <option value="">全部稀有度</option>
                    <option value="common" ${rarity==='common'?'selected':''}>Common</option>
                    <option value="uncommon" ${rarity==='uncommon'?'selected':''}>Uncommon</option>
                    <option value="rare" ${rarity==='rare'?'selected':''}>Rare</option>
                    <option value="legendary" ${rarity==='legendary'?'selected':''}>Legendary</option>
                    <option value="peculiar" ${rarity==='peculiar'?'selected':''}>Peculiar</option>
                </select>
            </div>
            <div class="wiki-count">共 ${data.total} 个结果（显示前 200）</div>
            <div class="wiki-grid">`;

        _wikiStore.mods = data.mods;
        data.mods.forEach((m, i) => {
            const polarityIcons = { madurai: 'V', vazarin: 'D', naramon: '—', zenurik: '—', penjaga: 'Y', umbra: '◆' };
            const rarityColors = { common: '#a0a0a0', uncommon: '#c9a227', rare: '#3f8ae0', legendary: '#e04040', peculiar: '#b060d0' };
            const polIcon = polarityIcons[m.polarity] || '?';
            const rarColor = rarityColors[(m.rarity || '').toLowerCase()] || '#888';
            const displayName = m.nameZh ? `${m.nameZh}（${m.name}）` : m.name;

            html += `<div class="wiki-card wiki-mod-card" onclick="showWikiModDetail(${i})">
                <div class="wiki-card-name">${displayName}</div>
                <div class="wiki-card-stats">
                    <span class="wiki-stat" style="color:${rarColor}">◆ ${m.rarity || '-'}</span>
                    <span class="wiki-stat">⊘ ${polIcon}</span>
                    <span class="wiki-stat">⚡ ${m.baseDrain}/${m.maxRank}</span>
                </div>
                <div class="wiki-card-sub">${m.type || ''}</div>
            </div>`;
        });

        html += `</div></div>`;
        content.innerHTML = html;

        const searchInput = document.getElementById('wiki-mod-search');
        if (searchInput) {
            searchInput.addEventListener('keydown', e => {
                if (e.key === 'Enter') searchWikiMods();
            });
        }
    } catch (err) {
        content.innerHTML = createChartError('加载 MOD 数据失败: ' + err.message);
    }
}

function searchWikiMods() {
    const q = document.getElementById('wiki-mod-search')?.value || '';
    const polarity = document.getElementById('wiki-mod-polarity')?.value || '';
    const rarity = document.getElementById('wiki-mod-rarity')?.value || '';
    showWikiMods(q, polarity, rarity);
}

function showWikiModDetail(idx) {
    const m = _wikiStore.mods[idx];
    if (!m) return;
    const content = document.getElementById('detail-content');
    if (!content) return;

    const rarityColors = { common: '#a0a0a0', uncommon: '#c9a227', rare: '#3f8ae0', legendary: '#e04040', peculiar: '#b060d0' };
    const rarColor = rarityColors[(m.rarity || '').toLowerCase()] || '#888';
    const displayName = m.nameZh ? `${m.nameZh}（${m.name}）` : m.name;

    let html = `<div class="profit-calc-container">
        <div class="wiki-detail-back" onclick="searchWikiMods()">← 返回列表</div>
        <div class="profit-calc-title">${displayName}</div>
        <div class="wiki-detail-desc">${m.description || ''}</div>
        ${m.marketUrl ? `<a class="wiki-market-link" href="${m.marketUrl}" target="_blank" rel="noopener">在 warframe.market 查看交易 →</a>` : ''}

        <div class="wiki-detail-section">
            <div class="wiki-detail-label">MOD 信息</div>
            <div class="wiki-detail-grid">
                <div class="wiki-detail-stat"><span class="stat-label">类型</span><span class="stat-value">${m.type || '-'}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">稀有度</span><span class="stat-value" style="color:${rarColor}">${m.rarity || '-'}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">极性</span><span class="stat-value">${m.polarity || '-'}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">容量消耗</span><span class="stat-value">${m.baseDrain}/${m.maxRank}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">兼容</span><span class="stat-value">${m.compatName || '通用'}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">强化 MOD</span><span class="stat-value">${m.isAugment ? '是' : '否'}</span></div>
                <div class="wiki-detail-stat"><span class="stat-label">可交易</span><span class="stat-value">${m.tradable ? '是' : '否'}</span></div>
            </div>
        </div>
    </div>`;
    content.innerHTML = html;
}

// ===== 遗物搜索 =====

async function showRelicSearch(q) {
    const content = openDetailPanel('搜索遗物...');
    if (!content) return;

    try {
        const url = q ? `/api/relic/search?q=${encodeURIComponent(q)}` : '/api/relic/search';
        const res = await fetch(url);
        const data = await res.json();

        let html = `<div class="profit-calc-container">
            <div class="profit-calc-title">🔮 遗物搜索</div>
            <div class="wiki-search-row">
                <input type="text" id="relic-search-input" class="wiki-search-input"
                    placeholder="输入物品名称（如：Nova Prime, Volt Prime Blueprint）..." value="${q || ''}" autocomplete="off">
                <button class="wiki-search-btn" onclick="showRelicSearch(document.getElementById('relic-search-input').value)">搜索</button>
            </div>`;

        if (!q) {
            html += `<div class="empty-state" style="padding:32px 0;">
                <div class="empty-state-icon">🔮</div>
                <div class="empty-state-text">输入物品名称搜索掉落遗物</div>
                <div class="empty-state-sub">例如：Nova Prime, Saryn Prime Blueprint, Akbolto Prime Barrel</div>
            </div>`;
        } else if (data.results.length === 0) {
            html += `<div class="empty-state" style="padding:32px 0;">
                <div class="empty-state-icon">❌</div>
                <div class="empty-state-text">未找到 "${q}" 相关的遗物</div>
                <div class="empty-state-sub">请尝试使用英文名称搜索</div>
            </div>`;
        } else {
            html += `<div class="wiki-count">找到 ${data.total} 个遗物掉落</div>`;

            const rarityColors = { Rare: '#e04040', Uncommon: '#c9a227', Common: '#a0a0a0' };
            const rarityIcons = { Rare: '🔴', Uncommon: '🟡', Common: '⚪' };

            data.results.forEach(r => {
                const color = rarityColors[r.rarity] || '#888';
                const icon = rarityIcons[r.rarity] || '⚪';
                const rarityDisplay = r.rarityZh || r.rarity;
                const vaultStatus = r.vaultStatus || '';
                const vaultClass = vaultStatus === '入库' ? 'vaulted' : 'active';
                const vaultLabel = vaultStatus === '入库' ? '🔒 入库' : '✅ 非入库';
                html += `<div class="relic-result-card">
                    <div class="relic-result-header">
                        <span class="relic-name">${r.relicName}</span>
                        <span class="relic-vault-badge ${vaultClass}">${vaultLabel}</span>
                        <span class="relic-state">${r.state}</span>
                    </div>
                    <div class="relic-result-body">
                        <span class="relic-item">${r.itemName}</span>
                        <span class="relic-rarity" style="color:${color}">${icon} ${rarityDisplay}</span>
                        <span class="relic-chance">${r.chance}%</span>
                    </div>
                </div>`;
            });
        }

        html += `</div>`;
        content.innerHTML = html;

        const searchInput = document.getElementById('relic-search-input');
        if (searchInput) {
            searchInput.addEventListener('keydown', e => {
                if (e.key === 'Enter') showRelicSearch(searchInput.value);
            });
            searchInput.focus();
        }
    } catch (err) {
        content.innerHTML = createChartError('搜索遗物失败: ' + err.message);
    }
}

// 绑定新功能菜单按钮
document.getElementById('wiki-warframes-btn')?.addEventListener('click', () => {
    document.getElementById('more-menu')?.classList.remove('active');
    showWikiWarframes('');
});

document.getElementById('wiki-mods-btn')?.addEventListener('click', () => {
    document.getElementById('more-menu')?.classList.remove('active');
    showWikiMods('', '', '');
});

document.getElementById('relic-search-btn')?.addEventListener('click', () => {
    document.getElementById('more-menu')?.classList.remove('active');
    showRelicSearch('');
});

function copyProvidedWhisperMessage(message) {
    if (!message) return '';
    navigator.clipboard.writeText(message).then(() => {
        showToast('已复制私聊消息', 'success');
    }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = message;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('已复制私聊消息', 'success');
    });
    return message;
}

function escapeHtmlAttr(text) {
    return escapeHtml(text).replace(/`/g, '&#96;');
}

function copyTradePlanWhisperFromButton(btn) {
    return copyProvidedWhisperMessage(btn?.dataset?.whisper || '');
}

function safeWarframeMarketUrl(url) {
    const text = String(url || '').trim();
    if (text.startsWith('https://warframe.market/items/') || text.startsWith('https://warframe.market/profile/')) {
        return text;
    }
    return '';
}

function renderTradePlanStep(step, index) {
    const marketUrl = safeWarframeMarketUrl(step.market_url);
    const profileUrl = safeWarframeMarketUrl(step.profile_url);
    const whisper = String(step.whisper || '');
    const rankText = step.rank === null || step.rank === undefined ? '' : ` · R${escapeHtml(step.rank)}`;
    return `<div class="trade-plan-step">
        <div class="trade-plan-step-main">
            <span class="trade-plan-step-index">${index}</span>
            <span class="trade-plan-step-label">${escapeHtml(step.label || step.display_name || step.item_id || '-')}</span>
            <span class="trade-plan-step-player">${escapeHtml(step.player || '-')}</span>
            <span class="trade-plan-step-price">${escapeHtml(step.unit_price ?? '-')}p × ${escapeHtml(step.quantity ?? 1)} = ${escapeHtml(step.subtotal ?? '-')}p${rankText}</span>
        </div>
        <div class="trade-plan-step-actions">
            ${marketUrl ? `<a href="${escapeHtml(marketUrl)}" target="_blank" rel="noopener">市场 ↗</a>` : ''}
            ${profileUrl ? `<a href="${escapeHtml(profileUrl)}" target="_blank" rel="noopener">Profile ↗</a>` : ''}
            ${whisper ? `<button type="button" class="copy-whisper-btn" data-whisper="${escapeHtmlAttr(whisper)}" onclick="copyTradePlanWhisperFromButton(this)">复制私聊</button>` : ''}
        </div>
    </div>`;
}

function renderTradePlanSection(title, steps) {
    const list = Array.isArray(steps) ? steps : [];
    if (!list.length) return '';
    return `<div class="trade-plan-section">
        <div class="trade-plan-section-title">${escapeHtml(title)}</div>
        ${list.map((step, index) => renderTradePlanStep(step, index + 1)).join('')}
    </div>`;
}

function renderTradePlanCard(plan) {
    if (!plan || typeof plan !== 'object') return '';
    const marketUrl = safeWarframeMarketUrl(plan.market_url || (plan.item_id ? `https://warframe.market/items/${plan.item_id}` : ''));
    return `<div class="trade-plan-card">
        <div class="trade-plan-summary">
            <span class="trade-plan-strategy">${escapeHtml(plan.display_strategy || plan.strategy || '交易计划')}</span>
            <span class="trade-plan-profit">+${escapeHtml(plan.profit ?? 0)}p</span>
            <span>成本 ${escapeHtml(plan.total_cost ?? 0)}p</span>
            <span>收入 ${escapeHtml(plan.total_revenue ?? 0)}p</span>
            <span>ROI ${escapeHtml(plan.roi_pct ?? 0)}%</span>
            ${plan.required_quantity ? `<span>数量 ${escapeHtml(plan.required_quantity)}</span>` : ''}
            ${marketUrl ? `<a href="${escapeHtml(marketUrl)}" target="_blank" rel="noopener">整套市场 ↗</a>` : ''}
        </div>
        ${renderTradePlanSection('你需要买入', plan.buy_steps)}
        ${renderTradePlanSection('你可以卖给', plan.sell_steps)}
    </div>`;
}

window.copyTradePlanWhisperFromButton = copyTradePlanWhisperFromButton;
window.renderTradePlanCard = renderTradePlanCard;

// ===== 虚空裂隙面板 (借鉴 WarStonks) =====
async function showFissures() {
    document.getElementById('more-menu')?.classList.remove('active');
    const content = document.getElementById('detail-content');
    if (!content) return;
    content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>加载裂隙数据...</p></div>';
    document.getElementById('detail-panel')?.classList.add('active');

    try {
        const resp = await fetch('https://api.warframestat.us/pc/fissures');
        if (!resp.ok) throw new Error('API 请求失败');
        const fissures = await resp.json();

        // Group by tier
        const tiers = { Lith: [], Meso: [], Neo: [], Axi: [], Requiem: [] };
        fissures.filter(f => !f.expired).forEach(f => {
            const tier = f.tier || 'Unknown';
            if (!tiers[tier]) tiers[tier] = [];
            tiers[tier].push(f);
        });

        let html = `<div class="panel-title-row">
            <span class="panel-title-eyebrow">虚空裂隙</span>
            <span class="badge badge-blue">${fissures.filter(f => !f.expired).length} 活跃</span>
        </div>`;

        html += '<div class="fissures-container">';
        for (const [tier, items] of Object.entries(tiers)) {
            if (items.length === 0) continue;
            html += `<div class="fissure-tier-group">
                <div class="fissure-tier-label">${tier}</div>`;
            items.forEach(f => {
                const eta = f.eta || '';
                const isExpiring = eta.includes('m') && !eta.includes('h');
                // 从节点名提取遗物信息 (如 "Lith A1" -> tier=Lith, name=A1)
                const node = f.node || '';
                html += `<div class="fissure-item" onclick="showRelicDrops('${tier}', '${f.tierNum || ''}')" style="cursor:pointer" title="点击查看遗物掉落">
                    <div>
                        <div class="fissure-node">${node}</div>
                        <div class="fissure-mission">${f.missionType || ''} ${f.enemy || ''}</div>
                    </div>
                    <span class="fissure-countdown ${isExpiring ? 'expiring' : ''}">${eta}</span>
                </div>`;
            });
            html += '</div>';
        }
        html += '</div>';
        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = `<div class="panel-title-row"><span class="panel-title-eyebrow">虚空裂隙</span></div>
            <div class="empty-state"><div class="empty-icon">🔔</div>
            <span class="empty-primary">无法加载裂隙数据</span>
            <span class="empty-sub">${err.message}</span></div>`;
    }
}

// ===== 遗物掉落详情 =====
async function showRelicDrops(tier, relicName) {
    const content = document.getElementById('detail-content');
    if (!content) return;
    content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>加载遗物掉落...</p></div>';

    try {
        // 查询单个遗物的详细掉落数据
        const resp = await fetch(`/api/relic/drops/${tier}/${relicName}`);
        const data = await resp.json();

        if (data.error) {
            content.innerHTML = `<div class="empty-state"><div class="empty-icon">🔮</div>
                <span class="empty-primary">未找到遗物</span><span class="empty-sub">${escapeHtml(data.error)}</span></div>`;
            return;
        }

        let html = `<div class="panel-title-row">
            <span class="panel-title-eyebrow">遗物掉落</span>
            <span class="badge badge-gold">${escapeHtml(data.displayName || tier + ' ' + relicName)}</span>
            ${data.vaultStatus ? `<span class="badge ${data.vaultStatus === '已入库' ? 'badge-red' : 'badge-green'}">${escapeHtml(data.vaultStatus)}</span>` : ''}
            <button class="btn-gradient" style="margin-left:auto;padding:4px 12px;font-size:11px" onclick="showFissureTracker()">← 返回裂隙</button>
        </div>`;

        // 如果有分状态数据（新格式）
        if (data.rewardsByState) {
            const stateLabels = data.stateLabels || { Intact: '完好', Exceptional: '卓越', Flawless: '无瑕', Radiant: '光辉' };
            const states = data.states || Object.keys(data.rewardsByState);

            // 精炼等级选择器
            html += `<div class="mode-toggle" style="margin-bottom:12px">`;
            states.forEach((state, i) => {
                html += `<button class="mode-toggle-btn ${i === 0 ? 'active' : ''}" onclick="switchRelicState(this, '${state}')">${stateLabels[state] || state}</button>`;
            });
            html += `</div>`;

            // 每个精炼等级的内容
            states.forEach((state, i) => {
                const rewards = data.rewardsByState[state] || [];
                html += `<div class="relic-state-panel" id="relic-state-${state}" style="display:${i === 0 ? 'block' : 'none'}">`;

                // 按稀有度排序
                const sorted = [...rewards].sort((a, b) => {
                    const order = { 'Rare': 0, 'Uncommon': 1, 'Common': 2 };
                    return (order[a.rarity] || 3) - (order[b.rarity] || 3);
                });

                sorted.forEach(r => {
                    const rarityColors = {
                        'Rare': { bg: 'rgba(212, 167, 55, 0.15)', color: 'var(--gold-primary)', border: 'rgba(212, 167, 55, 0.3)' },
                        'Uncommon': { bg: 'rgba(148, 163, 184, 0.15)', color: '#94a3b8', border: 'rgba(148, 163, 184, 0.3)' },
                        'Common': { bg: 'rgba(180, 83, 9, 0.15)', color: '#b45309', border: 'rgba(180, 83, 9, 0.3)' },
                    };
                    const rc = rarityColors[r.rarity] || rarityColors['Common'];
                    const itemName = r.itemName || '';
                    const rarityKey = String(r.rarity || 'common').toLowerCase().replace(/[^a-z]/g, '') || 'common';

                    html += `<div class="fissure-item" onclick="queryItemPrice('${escapeJsString(itemName)}')" style="cursor:pointer" title="点击查询价格">
                        <div style="display:flex;align-items:center;gap:8px">
                            <span class="rarity-dot ${escapeHtml(rarityKey)}"></span>
                            <div>
                                <div class="fissure-node">${escapeHtml(itemName)}</div>
                                <div class="fissure-mission">${escapeHtml(r.rarityZh || r.rarity || '')}</div>
                            </div>
                        </div>
                        <span style="font-family:var(--font-mono);font-size:13px;font-weight:600;color:${rc.color};background:${rc.bg};padding:2px 8px;border-radius:12px;border:1px solid ${rc.border}">${escapeHtml(r.chance ?? '-')}%</span>
                    </div>`;
                });
                html += `</div>`;
            });
        } else {
            // 旧格式兼容
            const rewards = data.rewards || [];
            const sorted = [...rewards].sort((a, b) => {
                const order = { 'Rare': 0, 'Uncommon': 1, 'Common': 2 };
                return (order[a.rarity] || 3) - (order[b.rarity] || 3);
            });

            sorted.forEach(r => {
                const rarityColors = {
                    'Rare': { bg: 'rgba(212, 167, 55, 0.15)', color: 'var(--gold-primary)', border: 'rgba(212, 167, 55, 0.3)' },
                    'Uncommon': { bg: 'rgba(148, 163, 184, 0.15)', color: '#94a3b8', border: 'rgba(148, 163, 184, 0.3)' },
                    'Common': { bg: 'rgba(180, 83, 9, 0.15)', color: '#b45309', border: 'rgba(180, 83, 9, 0.3)' },
                };
                const rc = rarityColors[r.rarity] || rarityColors['Common'];
                const itemName = r.itemName || '';
                const rarityKey = String(r.rarity || 'common').toLowerCase().replace(/[^a-z]/g, '') || 'common';

                html += `<div class="fissure-item" onclick="queryItemPrice('${escapeJsString(itemName)}')" style="cursor:pointer" title="点击查询价格">
                    <div style="display:flex;align-items:center;gap:8px">
                        <span class="rarity-dot ${escapeHtml(rarityKey)}"></span>
                        <div>
                            <div class="fissure-node">${escapeHtml(itemName)}</div>
                            <div class="fissure-mission">${escapeHtml(r.rarityZh || r.rarity || '')}</div>
                        </div>
                    </div>
                    <span style="font-family:var(--font-mono);font-size:13px;font-weight:600;color:${rc.color};background:${rc.bg};padding:2px 8px;border-radius:12px;border:1px solid ${rc.border}">${escapeHtml(r.chance ?? '-')}%</span>
                </div>`;
            });
        }

        html += `<div style="margin-top:12px;padding:12px;background:rgba(0,0,0,0.2);border-radius:8px;font-size:12px;color:var(--text-tertiary)">
            <strong>精炼等级说明：</strong>
            <ul style="margin:8px 0 0 16px;list-style:disc">
                <li><strong>完好 (Intact)</strong> — 无需消耗，稀有掉率 2%</li>
                <li><strong>卓越 (Exceptional)</strong> — 消耗 25 虚空光体（Void Traces），稀有掉率 4%</li>
                <li><strong>无瑕 (Flawless)</strong> — 消耗 50 虚空光体（Void Traces），稀有掉率 6%</li>
                <li><strong>光辉 (Radiant)</strong> — 消耗 100 虚空光体（Void Traces），稀有掉率 10%</li>
            </ul>
            <p style="margin-top:8px"><strong>组队建议：</strong>泛刷多个奖励可分带不同遗物；定向刷某个稀有奖励时，建议 4 人同带对应光辉遗物。</p>
        </div>`;

        html += '<div id="relic-value-analysis" style="margin-top:12px"><div class="loading-spinner" style="padding:8px"><p style="font-size:12px;color:var(--text-tertiary)">加载价值分析...</p></div></div>';

        // 加载遗物来源
        html += '<div id="relic-sources" style="margin-top:12px"><div class="loading-spinner" style="padding:8px"><p style="font-size:12px;color:var(--text-tertiary)">加载掉落来源...</p></div></div>';

        content.innerHTML = html;

        // 异步加载来源和价值数据
        loadRelicValue(tier, relicName);
        loadRelicSources(data.displayName || `${tier} ${relicName}`);
    } catch (err) {
        content.innerHTML = `<div class="empty-state"><div class="empty-icon">🔮</div>
            <span class="empty-primary">加载失败</span><span class="empty-sub">${err.message}</span></div>`;
    }
}

// 切换精炼等级显示
function switchRelicState(btn, state) {
    // 更新按钮状态
    btn.parentElement.querySelectorAll('.mode-toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // 切换显示
    document.querySelectorAll('.relic-state-panel').forEach(p => p.style.display = 'none');
    const panel = document.getElementById(`relic-state-${state}`);
    if (panel) panel.style.display = 'block';
}

async function loadRelicValue(tier, relicName) {
    const container = document.getElementById('relic-value-analysis');
    if (!container) return;

    try {
        const resp = await fetch(`/api/relic/value/${encodeURIComponent(tier)}/${encodeURIComponent(relicName)}`);
        const data = await resp.json();
        if (!resp.ok || data.error) {
            container.innerHTML = `<div style="padding:12px;background:rgba(0,0,0,0.2);border-radius:8px;font-size:12px;color:var(--text-tertiary)">
                <strong>价值分析：</strong>${escapeHtml(data.error || '暂不可用')}
            </div>`;
            return;
        }

        const rewards = data.rewards || [];
        const topPlat = data.topPlatinumReward;
        const topDucat = data.topDucatEfficiencyReward;
        let html = `<div style="padding:12px;background:rgba(0,0,0,0.2);border-radius:8px;font-size:12px">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px">
                <strong style="color:var(--gold-primary)">价值分析</strong>
                <span class="badge badge-green">EV ${escapeHtml((data.expectedPlatinum ?? 0).toFixed ? data.expectedPlatinum.toFixed(2) : data.expectedPlatinum)}p</span>
                <span class="badge badge-gold">${escapeHtml((data.expectedDucats ?? 0).toFixed ? data.expectedDucats.toFixed(2) : data.expectedDucats)} 杜卡德</span>
            </div>
            <div style="color:var(--text-secondary);margin-bottom:8px">${escapeHtml(data.summaryRecommendation || '')}</div>`;

        rewards.forEach(r => {
            const isTopPlat = r.marketId && r.marketId === topPlat;
            const isTopDucat = r.marketId && r.marketId === topDucat;
            const flags = [isTopPlat ? '最佳白金' : '', isTopDucat ? '最佳杜卡德' : ''].filter(Boolean).join(' · ');
            const warnings = (r.warnings || []).map(w => escapeHtml(w)).join('；');
            html += `<div class="fissure-item" style="cursor:default">
                <div style="min-width:0">
                    <div class="fissure-node">${escapeHtml(r.itemName || r.marketId || '-')}</div>
                    <div class="fissure-mission">${escapeHtml(r.rarity || '-')} · 掉率 ${escapeHtml(((r.dropRate || 0) * 100).toFixed(1))}%${flags ? ` · ${escapeHtml(flags)}` : ''}</div>
                    ${warnings ? `<div class="fissure-mission">${warnings}</div>` : ''}
                </div>
                <div style="text-align:right;font-family:var(--font-mono);font-size:12px;color:var(--text-secondary)">
                    <div>${r.valuationPrice == null ? '估值未知' : `${escapeHtml(r.valuationPrice)}p`}</div>
                    <div>${r.ducatValue == null ? '杜卡德未知' : `${escapeHtml(r.ducatValue)}D`}${r.ducatsPerPlat == null ? '' : ` · ${escapeHtml(r.ducatsPerPlat)}D/p`}</div>
                </div>
            </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<div style="padding:12px;background:rgba(0,0,0,0.2);border-radius:8px;font-size:12px;color:var(--text-tertiary)">
            <strong>价值分析：</strong>${escapeHtml(err.message || '加载失败')}
        </div>`;
    }
}

// 加载遗物来源
async function loadRelicSources(relicDisplayName) {
    const container = document.getElementById('relic-sources');
    if (!container) return;

    try {
        // 提取遗物名 (如 "古纪 A1" -> "Lith A1")
        const tierMap = { '古纪': 'Lith', '前纪': 'Meso', '中纪': 'Neo', '后纪': 'Axi', '安魂': 'Requiem' };
        let relicName = relicDisplayName;
        for (const [zh, en] of Object.entries(tierMap)) {
            if (relicDisplayName.startsWith(zh)) {
                relicName = relicDisplayName.replace(zh, en).trim();
                break;
            }
        }

        const resp = await fetch(`/api/relic/sources/${encodeURIComponent(relicName)}`);
        const data = await resp.json();
        const sources = data.sources || [];

        if (sources.length === 0) {
            container.innerHTML = `<div style="padding:12px;background:rgba(0,0,0,0.2);border-radius:8px;font-size:12px;color:var(--text-tertiary)">
                <strong>掉落来源：</strong>该遗物已入库或无当前掉落来源
            </div>`;
            return;
        }

        // 按星球分组
        const byPlanet = {};
        sources.forEach(s => {
            const key = s.planetZh || s.planet;
            if (!byPlanet[key]) byPlanet[key] = [];
            byPlanet[key].push(s);
        });

        let html = `<div style="padding:12px;background:rgba(0,0,0,0.2);border-radius:8px;font-size:12px">
            <strong style="color:var(--gold-primary)">掉落来源</strong>
            <span style="color:var(--text-tertiary);margin-left:8px">共 ${sources.length} 个任务</span>
            <div style="margin-top:8px;max-height:300px;overflow-y:auto">`;

        for (const [planet, items] of Object.entries(byPlanet)) {
            html += `<div style="margin-bottom:8px">
                <div style="color:var(--blue-primary);font-weight:600;font-size:11px;text-transform:uppercase;margin-bottom:4px">${planet}</div>`;

            // 去重显示
            const seen = new Set();
            items.forEach(s => {
                const key = `${s.location}_${s.rotation}`;
                if (seen.has(key)) return;
                seen.add(key);

                const rotLabel = s.rotation !== '-' ? `轮次 ${s.rotation}` : '无轮次';
                const chanceColor = s.chance >= 10 ? 'var(--green-success)' : s.chance >= 5 ? 'var(--gold-primary)' : 'var(--text-tertiary)';

                html += `<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.03)">
                    <span>${s.location} <span style="color:var(--text-tertiary)">(${rotLabel})</span></span>
                    <span style="font-family:var(--font-mono);color:${chanceColor};font-weight:600">${s.chance}%</span>
                </div>`;
            });
            html += '</div>';
        }

        html += '</div></div>';
        container.innerHTML = html;

    } catch (err) {
        container.innerHTML = `<div style="padding:12px;background:rgba(0,0,0,0.2);border-radius:8px;font-size:12px;color:var(--text-tertiary)">
            <strong>掉落来源：</strong>加载失败 - ${err.message}
        </div>`;
    }
}

// ===== 价格异常检测 (借鉴 WarStonks 套利扫描) =====
async function showPriceAnomalies() {
    document.getElementById('more-menu')?.classList.remove('active');
    const content = openDetailPanel('扫描价格异常...');
    if (!content) return;
    const ver = getPanelVersion();

    try {
        const resp = await fetch('/api/price/anomalies');
        if (getPanelVersion() !== ver) return;
        if (!resp.ok) {
            const error = await resp.json().catch(() => ({}));
            throw new Error(error.detail || error.error || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        const items = data.anomalies || [];

        let html = `<div class="panel-title-row">
            <span class="panel-title-eyebrow">价格异常</span>
            <span class="badge ${items.length > 0 ? 'badge-gold' : 'badge-muted'}">${items.length} 异常</span>
        </div>`;

        if (items.length === 0) {
            html += `<div class="empty-state"><div class="empty-icon">📊</div>
                <span class="empty-primary">暂无异常</span>
                <span class="empty-sub">当前关注物品未发现明显价格异常</span></div>`;
        } else {
            html += '<div class="card"><div class="card-body">';
            items.slice(0, 20).forEach(item => {
                const deviation = Number(item.deviation || 0);
                const anomalyType = item.type || (deviation >= 0 ? 'spike' : 'drop');
                const color = anomalyType === 'spike' ? 'var(--green-success)' : 'var(--red-error)';
                const sign = deviation >= 0 ? '+' : '';
                html += `<div class="fissure-item">
                    <div>
                        <div class="fissure-node">${item.display || item.item_id || 'Unknown'}</div>
                        <div class="fissure-mission">当前 ${item.current_price ?? '-'}p / 均价 ${item.avg_price ?? '-'}p</div>
                    </div>
                    <span style="color:${color};font-weight:600;font-family:var(--font-mono)">${item.type_display || ''} ${sign}${deviation.toFixed(1)}%</span>
                </div>`;
            });
            html += '</div></div>';
        }
        if (getPanelVersion() !== ver) return;
        content.innerHTML = html;
    } catch (err) {
        if (getPanelVersion() !== ver) return;
        content.innerHTML = `<div class="empty-state"><div class="empty-icon">📊</div>
            <span class="empty-primary">扫描失败</span><span class="empty-sub">${err.message}</span></div>`;
    }
}

document.getElementById('anomaly-btn')?.addEventListener('click', () => showPriceAnomalies());

// ===== 长期交易记忆观察面板 =====
const TRADING_MEMORY_TABS = {
    'market-snapshots': {
        label: '市场快照',
        endpoint: '/api/trading-memory/market-snapshots',
        responseKey: 'market_snapshots',
        typeParam: 'source',
        typeLabel: '来源',
        placeholder: 'price_monitor.scan'
    },
    'recommendations': {
        label: '推荐记录',
        endpoint: '/api/trading-memory/recommendations',
        responseKey: 'recommendations',
        typeParam: 'recommendation_type',
        typeLabel: '推荐类型',
        placeholder: 'baro'
    },
    'push-history': {
        label: '推送历史',
        endpoint: '/api/trading-memory/push-history',
        responseKey: 'push_history',
        typeParam: 'push_type',
        typeLabel: '推送类型',
        placeholder: 'opportunity'
    },
    'recall-trace': {
        label: '召回 Trace',
        endpoint: '/api/memory/recall',
        responseKey: 'items',
        typeParam: 'intent',
        typeLabel: '意图',
        placeholder: 'price_check'
    }
};

let tradingMemoryActiveTab = 'market-snapshots';
let tradingMemoryRequestSeq = 0;

function showTradingMemoryPanel(tab = 'market-snapshots') {
    document.getElementById('more-menu')?.classList.remove('active');
    tradingMemoryActiveTab = TRADING_MEMORY_TABS[tab] ? tab : 'market-snapshots';
    const content = openDetailPanel('加载长期交易记忆...');
    if (!content) return;
    renderTradingMemoryShell(content, tradingMemoryActiveTab);
    fetchTradingMemoryTab(tradingMemoryActiveTab);
}

function renderTradingMemoryShell(content, activeTab) {
    const config = TRADING_MEMORY_TABS[activeTab];
    content.innerHTML = `
        <div class="trading-memory-panel">
            <div class="panel-title-row">
                <div>
                    <span class="panel-title-eyebrow">长期交易记忆</span>
                    <div class="trading-memory-subtitle">只读观察 market snapshots、recommendations、push history 与 recall trace</div>
                </div>
                <span id="trading-memory-count" class="badge badge-muted">${escapeHtml(config.label)} · 加载中</span>
            </div>
            <div class="mode-toggle trading-memory-tabs">
                ${Object.entries(TRADING_MEMORY_TABS).map(([key, tabConfig]) => `
                    <button class="mode-toggle-btn ${key === activeTab ? 'active' : ''}" id="trading-memory-tab-${key}" data-tab="${key}" type="button">
                        ${escapeHtml(tabConfig.label)}
                    </button>
                `).join('')}
            </div>
            <div class="wiki-filters trading-memory-filters">
                ${activeTab === 'recall-trace' ? '<input id="memory-recall-query-filter" class="wiki-search-input" type="text" placeholder="query" autocomplete="off">' : ''}
                <input id="${activeTab === 'recall-trace' ? 'memory-recall-item-filter' : 'trading-memory-item-filter'}" class="wiki-search-input" type="text" placeholder="item_name" autocomplete="off">
                <input id="trading-memory-type-filter" class="wiki-search-input" type="text" placeholder="${escapeHtml(config.typeLabel)}：${escapeHtml(config.placeholder)}" autocomplete="off">
                ${activeTab !== 'recall-trace' ? `<select id="trading-memory-since-filter" aria-label="时间范围">
                    <option value="all">全部</option>
                    <option value="24h">24h</option>
                    <option value="7d">7d</option>
                    <option value="30d">30d</option>
                </select>` : ''}
                <select id="trading-memory-limit-filter" aria-label="数量">
                    ${activeTab === 'recall-trace' ? `
                    <option value="5">5</option>
                    <option value="10">10</option>
                    <option value="20" selected>20</option>` : `
                    <option value="25">25</option>
                    <option value="50">50</option>
                    <option value="100" selected>100</option>`}
                </select>
                <button id="trading-memory-refresh-btn" class="detail-action-btn" type="button">刷新</button>
            </div>
            <div id="trading-memory-results" class="trading-memory-list">
                <div class="loading-spinner"><div class="spinner"></div><p>加载${escapeHtml(config.label)}...</p></div>
            </div>
        </div>
    `;
    bindTradingMemoryControls(content);
}

function bindTradingMemoryControls(content) {
    content.querySelectorAll('.trading-memory-tabs [data-tab]').forEach(button => {
        button.addEventListener('click', () => {
            const tab = button.dataset.tab;
            if (!TRADING_MEMORY_TABS[tab] || tab === tradingMemoryActiveTab) return;
            tradingMemoryActiveTab = tab;
            const nextContent = document.getElementById('detail-content');
            if (!nextContent) return;
            renderTradingMemoryShell(nextContent, tradingMemoryActiveTab);
            fetchTradingMemoryTab(tradingMemoryActiveTab);
        });
    });
    content.querySelector('#trading-memory-refresh-btn')?.addEventListener('click', () => {
        fetchTradingMemoryTab(tradingMemoryActiveTab);
    });
    content.querySelectorAll('#trading-memory-item-filter, #memory-recall-query-filter, #memory-recall-item-filter, #trading-memory-type-filter').forEach(input => {
        input.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                fetchTradingMemoryTab(tradingMemoryActiveTab);
            }
        });
    });
}

async function fetchTradingMemoryTab(tab) {
    const config = TRADING_MEMORY_TABS[tab];
    if (!config) return;
    const results = document.getElementById('trading-memory-results');
    const countBadge = document.getElementById('trading-memory-count');
    if (!results) return;
    const panelVersion = getPanelVersion();
    const requestSeq = ++tradingMemoryRequestSeq;
    results.innerHTML = `<div class="loading-spinner"><div class="spinner"></div><p>加载${escapeHtml(config.label)}...</p></div>`;
    if (countBadge) {
        countBadge.className = 'badge badge-muted';
        countBadge.textContent = `${config.label} · 加载中`;
    }
    try {
        const response = await fetch(buildTradingMemoryUrl(tab, getTradingMemoryFilters(tab)));
        if (getPanelVersion() !== panelVersion || requestSeq !== tradingMemoryRequestSeq) return;
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || error.error || `HTTP ${response.status}`);
        }
        const data = await response.json();
        if (getPanelVersion() !== panelVersion || requestSeq !== tradingMemoryRequestSeq) return;
        const records = Array.isArray(data[config.responseKey]) ? data[config.responseKey] : [];
        const count = Number.isFinite(Number(data.count)) ? Number(data.count) : records.length;
        if (countBadge) {
            countBadge.className = `badge ${count > 0 ? 'badge-gold' : 'badge-muted'}`;
            countBadge.textContent = `${config.label} · ${count} 条`;
        }
        if (tab === 'market-snapshots') {
            results.innerHTML = renderMarketSnapshots(records);
        } else if (tab === 'recommendations') {
            results.innerHTML = renderRecommendations(records);
        } else if (tab === 'push-history') {
            results.innerHTML = renderPushHistory(records);
        } else {
            results.innerHTML = renderRecallTrace(records, data.query_summary || {}, data.score_breakdown || {});
        }
    } catch (err) {
        if (getPanelVersion() !== panelVersion || requestSeq !== tradingMemoryRequestSeq) return;
        results.innerHTML = renderTradingMemoryError(`加载${config.label}失败`, err.message);
        if (countBadge) {
            countBadge.className = 'badge badge-red';
            countBadge.textContent = `${config.label} · 错误`;
        }
    }
}

function getTradingMemoryFilters(tab) {
    const itemName = (tab === 'recall-trace'
        ? document.getElementById('memory-recall-item-filter')?.value.trim()
        : document.getElementById('trading-memory-item-filter')?.value.trim()) || '';
    const typeValue = document.getElementById('trading-memory-type-filter')?.value.trim() || '';
    const sinceValue = document.getElementById('trading-memory-since-filter')?.value || 'all';
    const limitValue = document.getElementById('trading-memory-limit-filter')?.value || (tab === 'recall-trace' ? '20' : '100');
    const filters = { limit: tab === 'recall-trace' ? Math.min(Number(limitValue) || 20, 20) : limitValue };
    if (tab === 'recall-trace') {
        const query = document.getElementById('memory-recall-query-filter')?.value.trim() || '';
        filters.query = query;
        if (itemName) filters.item_name = itemName;
        if (typeValue) filters.intent = typeValue;
        return filters;
    }
    if (itemName) filters.item_name = itemName;
    if (typeValue && TRADING_MEMORY_TABS[tab]) filters[TRADING_MEMORY_TABS[tab].typeParam] = typeValue;
    const since = tradingMemorySinceIso(sinceValue);
    if (since) filters.since = since;
    return filters;
}

function buildTradingMemoryUrl(tab, filters) {
    const config = TRADING_MEMORY_TABS[tab];
    const params = new URLSearchParams();
    Object.entries(filters || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== null && String(value).trim() !== '') {
            params.set(key, String(value));
        }
    });
    const query = params.toString();
    return query ? `${config.endpoint}?${query}` : config.endpoint;
}

function tradingMemorySinceIso(value) {
    const now = new Date();
    const hours = { '24h': 24, '7d': 24 * 7, '30d': 24 * 30 }[value];
    if (!hours) return '';
    return new Date(now.getTime() - hours * 60 * 60 * 1000).toISOString();
}

function formatTradingMemoryDate(timestamp) {
    if (!timestamp) return '-';
    try {
        return formatDate(timestamp);
    } catch (_) {
        return String(timestamp);
    }
}

function renderMarketSnapshots(records) {
    if (!records.length) return renderTradingMemoryEmpty('暂无市场快照', 'PriceMonitor 写入 market snapshot 后会显示在这里');
    return records.map(record => `
        <div class="card trading-memory-record">
            <div class="card-body">
                <div class="trading-memory-record-header">
                    <div>
                        <div class="trading-memory-name">${escapeHtml(record.item_name || record.item_id || '-')}</div>
                        <div class="trading-memory-meta">${escapeHtml(record.source || '-')} · ${escapeHtml(formatTradingMemoryDate(record.timestamp))}</div>
                    </div>
                    <span class="badge badge-blue">市场快照</span>
                </div>
                <div class="trading-memory-prices">
                    <span>卖 ${renderPlatinum(record.sell_price)}</span>
                    <span>买 ${renderPlatinum(record.buy_price)}</span>
                    <span>价差 ${renderPlatinum(record.spread)}</span>
                </div>
            </div>
        </div>
    `).join('');
}

function renderRecommendations(records) {
    if (!records.length) return renderTradingMemoryEmpty('暂无推荐记录', 'Baro 或机会推荐写入后会显示在这里');
    return records.map(record => `
        <div class="card trading-memory-record">
            <div class="card-body">
                <div class="trading-memory-record-header">
                    <div>
                        <div class="trading-memory-name">${escapeHtml(record.display_name || record.item_name || record.market_id || '-')}</div>
                        <div class="trading-memory-meta">${escapeHtml(record.recommendation_type || '-')} · ${escapeHtml(formatTradingMemoryDate(record.timestamp))}</div>
                    </div>
                    <span class="badge badge-gold">${escapeHtml(record.source || record.event_type || '推荐')}</span>
                </div>
                ${record.reason ? `<div class="trading-memory-message">${escapeHtml(record.reason)}</div>` : ''}
                ${record.event_description ? `<div class="trading-memory-meta">事件：${escapeHtml(record.event_description)}</div>` : ''}
                <div class="trading-memory-prices">
                    <span>最高买 ${renderPlatinum(record.best_buy_price)}</span>
                    <span>最低卖 ${renderPlatinum(record.best_sell_price)}</span>
                    ${record.ducat_cost !== null && record.ducat_cost !== undefined ? `<span>${escapeHtml(record.ducat_cost)} 杜卡德</span>` : ''}
                    ${record.credit_cost !== null && record.credit_cost !== undefined ? `<span>${escapeHtml(record.credit_cost)} 星币</span>` : ''}
                    ${record.rank !== null && record.rank !== undefined ? `<span>等级 ${escapeHtml(record.rank)} / ${escapeHtml(record.max_rank ?? '-')}</span>` : ''}
                </div>
            </div>
        </div>
    `).join('');
}

function renderPushHistory(records) {
    if (!records.length) return renderTradingMemoryEmpty('暂无推送历史', '主动推送或事件推送写入后会显示在这里');
    return records.map(record => {
        const affected = Array.isArray(record.items_affected) ? record.items_affected : [];
        return `
            <div class="card trading-memory-record">
                <div class="card-body">
                    <div class="trading-memory-record-header">
                        <div>
                            <div class="trading-memory-name">${escapeHtml(record.item_display || record.item_name || record.item_id || '-')}</div>
                            <div class="trading-memory-meta">${escapeHtml(record.push_type || '-')} · ${escapeHtml(record.source || '-')} · ${escapeHtml(formatTradingMemoryDate(record.timestamp))}</div>
                        </div>
                        <span class="badge badge-green">优先级 ${escapeHtml(record.priority ?? '-')}</span>
                    </div>
                    ${record.message ? `<div class="trading-memory-message">${escapeHtml(record.message)}</div>` : ''}
                    ${record.action_suggestion ? `<div class="trading-memory-meta">建议：${escapeHtml(record.action_suggestion)}</div>` : ''}
                    ${record.event_description ? `<div class="trading-memory-meta">事件：${escapeHtml(record.event_description)}</div>` : ''}
                    ${affected.length ? `<div class="trading-memory-chips">${affected.map(item => `<span class="badge badge-muted">${escapeHtml(item)}</span>`).join('')}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function renderRecallTrace(records, querySummary, scoreBreakdown) {
    if (!records.length) return renderTradingMemoryEmpty('暂无召回 Trace', '有交易记忆后可在这里解释召回原因');
    const summary = querySummary || {};
    const header = `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-name">查询摘要</div>
        <div class="trading-memory-meta">item=${escapeHtml(summary.item_name || '-')} · intent=${escapeHtml(summary.intent || '-')} · max_score=${escapeHtml(scoreBreakdown.max_score ?? '-')}</div>
    </div></div>`;
    return header + records.map(record => {
        const facts = renderRecallKeyValues(record.summary || {});
        const trace = renderRecallKeyValues(record.trace || {});
        return `<div class="card trading-memory-record">
            <div class="card-body">
                <div class="trading-memory-record-header">
                    <div>
                        <div class="trading-memory-name">${escapeHtml(record.item_name || '-')}</div>
                        <div class="trading-memory-meta">${escapeHtml(record.source || '-')} #${escapeHtml(record.record_id ?? '-')} · ${escapeHtml(formatTradingMemoryDate(record.timestamp))}</div>
                    </div>
                    <span class="badge badge-blue">score ${escapeHtml(record.score ?? '-')}</span>
                </div>
                <div class="trading-memory-prices">
                    <span>relevance=${escapeHtml(record.relevance ?? '-')}</span>
                    <span>recency=${escapeHtml(record.recency ?? '-')}</span>
                    <span>salience=${escapeHtml(record.salience ?? '-')}</span>
                </div>
                <div class="trading-memory-message">facts: ${facts}</div>
                <div class="trading-memory-meta">trace: ${trace}</div>
            </div>
        </div>`;
    }).join('');
}

function renderRecallKeyValues(value) {
    if (!value || typeof value !== 'object') return '-';
    return Object.entries(value).map(([key, item]) => `${escapeHtml(key)}=${escapeHtml(Array.isArray(item) ? item.join(',') : item)}`).join(' · ');
}

function renderPlatinum(value) {
    return value === null || value === undefined || value === '' ? '-' : `${escapeHtml(value)}p`;
}

function renderTradingMemoryEmpty(title, subtitle) {
    return `<div class="empty-state">
        <div class="empty-state-icon">TM</div>
        <div class="empty-state-text">${escapeHtml(title)}</div>
        <div class="empty-state-sub">${escapeHtml(subtitle || '')}</div>
    </div>`;
}

function renderTradingMemoryError(title, detail) {
    return `<div class="empty-state">
        <div class="empty-state-icon">!</div>
        <div class="empty-state-text">${escapeHtml(title)}</div>
        <div class="empty-state-sub">${escapeHtml(detail || '请稍后重试')}</div>
    </div>`;
}

document.getElementById('trading-memory-btn')?.addEventListener('click', () => showTradingMemoryPanel());

// ===== 工具观测面板 =====
async function showToolObservabilityPanel() {
    document.getElementById('more-menu')?.classList.remove('active');
    const content = openDetailPanel('加载工具观测...');
    if (!content) return;
    content.innerHTML = `
        <div class="tool-observability-panel">
            <div class="panel-title-row">
                <div>
                    <span class="panel-title-eyebrow">工具观测</span>
                    <div class="trading-memory-subtitle">只读查看最近工具调用和统计摘要</div>
                </div>
                <span id="tool-observability-count" class="badge badge-muted">加载中</span>
            </div>
            <div class="wiki-filters trading-memory-filters">
                <input id="tool-observability-name-filter" class="wiki-search-input" type="text" placeholder="tool_name" autocomplete="off">
                <select id="tool-observability-ok-filter" aria-label="调用状态">
                    <option value="all">全部</option>
                    <option value="true">成功</option>
                    <option value="false">失败</option>
                </select>
                <select id="tool-observability-limit-filter" aria-label="数量">
                    <option value="25">25</option>
                    <option value="50" selected>50</option>
                    <option value="100">100</option>
                </select>
                <button id="tool-observability-refresh-btn" class="detail-action-btn" type="button">刷新</button>
            </div>
            <div id="tool-observability-stats" class="trading-memory-list"></div>
            <div class="trading-memory-section-title">调用历史</div>
            <div id="tool-observability-history" class="trading-memory-list">
                <div class="loading-spinner"><div class="spinner"></div><p>加载工具调用...</p></div>
            </div>
        </div>
    `;
    content.querySelector('#tool-observability-refresh-btn')?.addEventListener('click', fetchToolObservability);
    content.querySelector('#tool-observability-name-filter')?.addEventListener('keydown', event => {
        if (event.key === 'Enter') fetchToolObservability();
    });
    await fetchToolObservability();
}

async function fetchToolObservability() {
    const name = document.getElementById('tool-observability-name-filter')?.value.trim() || '';
    const ok = document.getElementById('tool-observability-ok-filter')?.value || 'all';
    const limit = document.getElementById('tool-observability-limit-filter')?.value || '50';
    const params = new URLSearchParams({ limit });
    if (name) params.set('tool_name', name);
    if (ok !== 'all') params.set('ok', ok);
    const statsParams = new URLSearchParams({ limit });
    if (name) statsParams.set('tool_name', name);
    const countBadge = document.getElementById('tool-observability-count');
    const statsEl = document.getElementById('tool-observability-stats');
    const historyEl = document.getElementById('tool-observability-history');
    if (!statsEl || !historyEl) return;
    try {
        const [historyRes, statsRes] = await Promise.all([
            fetch(`/api/tool-calls/history?${params.toString()}`),
            fetch(`/api/tool-calls/stats?${statsParams.toString()}`),
        ]);
        if (!historyRes.ok) throw new Error(`history HTTP ${historyRes.status}`);
        if (!statsRes.ok) throw new Error(`stats HTTP ${statsRes.status}`);
        const history = await historyRes.json();
        const stats = await statsRes.json();
        const items = Array.isArray(history.items) ? history.items : [];
        if (countBadge) {
            countBadge.className = `badge ${items.length ? 'badge-gold' : 'badge-muted'}`;
            countBadge.textContent = `${items.length} 条`;
        }
        statsEl.innerHTML = renderToolObservabilityStats(stats);
        historyEl.innerHTML = renderToolObservabilityHistory(items);
    } catch (error) {
        if (countBadge) {
            countBadge.className = 'badge badge-red';
            countBadge.textContent = '错误';
        }
        statsEl.innerHTML = '';
        historyEl.innerHTML = renderTradingMemoryError('加载工具观测失败', error.message);
    }
}

function renderToolObservabilityStats(stats) {
    const top = Array.isArray(stats.top_tools) ? stats.top_tools : [];
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">统计摘要</div>
                <div class="trading-memory-meta">total=${escapeHtml(stats.total_calls ?? 0)} · success=${escapeHtml(stats.success_count ?? 0)} · failure=${escapeHtml(stats.failure_count ?? 0)}</div>
            </div>
            <span class="badge badge-blue">成功率 ${escapeHtml(stats.success_rate ?? 0)}</span>
        </div>
        <div class="trading-memory-prices">
            <span>avg=${escapeHtml(stats.duration_ms?.avg ?? '-')}ms</span>
            <span>min=${escapeHtml(stats.duration_ms?.min ?? '-')}ms</span>
            <span>max=${escapeHtml(stats.duration_ms?.max ?? '-')}ms</span>
        </div>
        ${top.length ? `<div class="trading-memory-chips">${top.map(item => `<span class="badge badge-muted">${escapeHtml(item.tool_name)} · ${escapeHtml(item.total_calls)}</span>`).join('')}</div>` : ''}
    </div></div>`;
}

function renderToolObservabilityHistory(items) {
    if (!items.length) return renderTradingMemoryEmpty('暂无工具调用', '有工具调用日志后会显示在这里');
    return items.map(item => `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(item.tool_name || '-')}</div>
                <div class="trading-memory-meta">${escapeHtml(item.tool_timestamp || item.conversation_timestamp || '-')}</div>
            </div>
            <span class="badge ${item.ok === false ? 'badge-red' : item.ok === true ? 'badge-green' : 'badge-muted'}">${item.ok === false ? 'failed' : item.ok === true ? 'ok' : 'unknown'}</span>
        </div>
        <div class="trading-memory-prices"><span>duration=${escapeHtml(item.duration_ms ?? '-')}ms</span></div>
        <div class="trading-memory-message">args: ${renderRecallKeyValues(item.args_summary || {})}</div>
        ${item.error_summary ? `<div class="trading-memory-meta">error: ${escapeHtml(item.error_summary)}</div>` : ''}
    </div></div>`).join('');
}

document.getElementById('tool-observability-btn')?.addEventListener('click', () => showToolObservabilityPanel());

// ===== 通用扫描轮询 =====
async function _pollScan(url, content, onDone, onError) {
    const ver = getPanelVersion();
    try {
        const resp = await fetch(url);
        if (getPanelVersion() !== ver) return;
        if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${resp.status}`); }
        const data = await resp.json();

        if (data.status === 'done') {
            if (getPanelVersion() !== ver) return;
            onDone(data);
            return;
        }

        const taskId = data.task_id;
        if (!taskId) throw new Error('未获取到任务ID');

        let attempts = 0;
        const maxAttempts = 150;
        while (attempts < maxAttempts) {
            await new Promise(r => setTimeout(r, 2000));
            attempts++;
            if (getPanelVersion() !== ver) return;
            const sr = await fetch(`/api/scan_status/${taskId}`);
            if (!sr.ok) break;
            const sd = await sr.json();
            if (sd.status === 'done') { if (getPanelVersion() !== ver) return; onDone(sd); return; }
            if (sd.status === 'error') throw new Error(sd.error || '扫描异常');
            if (content && attempts % 5 === 0) {
                const sub = content.querySelector('.empty-sub');
                if (sub) sub.textContent = `扫描中${'.'.repeat((attempts % 3) + 1)} (${attempts * 2}s)`;
            }
        }
        throw new Error('扫描超时');
    } catch (err) {
        if (getPanelVersion() !== ver) return;
        if (onError) onError(err);
        else if (content) {
            content.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div>
                <span class="empty-primary">扫描失败</span><span class="empty-sub">${err.message}</span></div>`;
        }
    }
}

// ===== Mod 翻转分析 =====
let _modFlipData = [];
let _modFlipPage = 0;
const _MOD_FLIP_PAGE_SIZE = 5;

function renderModFlipPage(content) {
    const items = _modFlipData;
    const totalPages = Math.ceil(items.length / _MOD_FLIP_PAGE_SIZE);
    const start = _modFlipPage * _MOD_FLIP_PAGE_SIZE;
    const pageItems = items.slice(start, start + _MOD_FLIP_PAGE_SIZE);

    let html = `<div class="panel-title-row">
        <span class="panel-title-eyebrow">Mod 翻转 (100%+ ROI)</span>
        <span class="badge ${items.length > 0 ? 'badge-gold' : 'badge-muted'}">${items.length} 机会</span>
    </div>`;

    if (items.length === 0) {
        html += `<div class="empty-state"><div class="empty-icon">🔄</div>
            <span class="empty-primary">暂无翻转机会</span>
            <span class="empty-sub">当前市场未发现 100%+ ROI 的 Mod</span></div>`;
    } else {
        html += '<div class="card"><div class="card-body">';
        pageItems.forEach((item, idx) => {
            const globalIdx = start + idx + 1;
            const primeBadge = item.is_prime ? '<span style="background:linear-gradient(135deg,#c9a32e,#f0d060);color:#1a1a2e;padding:1px 6px;border-radius:4px;font-size:0.7em;font-weight:700;margin-left:6px;">PRIME</span>' : '';
            const roiColor = item.roi_pct >= 200 ? '#00ff88' : item.roi_pct >= 150 ? '#88ff00' : '#ffcc00';
            const shortName = (item.display_name || item.item_id).split(' / ')[0];
            html += `<div class="fissure-item" style="flex-direction:column;align-items:flex-start;gap:4px;">
                <div style="display:flex;justify-content:space-between;width:100%;align-items:center;">
                    <div class="fissure-node">${globalIdx}. ${shortName}${primeBadge}</div>
                    <span style="color:${roiColor};font-weight:700;font-family:var(--font-mono);font-size:1.05em;">ROI ${item.roi_pct}%</span>
                </div>
                <div style="display:flex;gap:10px;font-size:0.8em;color:var(--text-secondary);flex-wrap:wrap;align-items:center;">
                    <span style="color:var(--green-success);font-weight:600;">+${item.flip_profit}p</span>
                    <span>买 R0: ${item.r0_buy_price}p</span>
                    <span>卖 R${item.max_rank}: ${item.r10_sell_price}p</span>
                    <span>内融: ${(item.endo_cost / 1000).toFixed(1)}k</span>
                    <span>每千内融: ${item.plat_per_1k_endo}p</span>
                    <span>48h量: ${item.volume_48h ?? '?'}</span>
                    ${item.market_url ? `<a href="${escapeHtml(item.market_url)}" target="_blank" rel="noopener" style="color:var(--accent-color);text-decoration:none;">市场 ↗</a>` : ''}
                </div>
                ${item.trade_plan ? renderTradePlanCard(item.trade_plan) : ((item.r0_seller || item.max_rank_buyer) ? `<div style="font-size:0.75em;color:var(--text-secondary);display:flex;gap:10px;flex-wrap:wrap;">
                    ${item.r0_seller ? `<span>买入卖家: ${escapeHtml(item.r0_seller.player)} ${item.r0_seller.price}p</span>` : ''}
                    ${item.max_rank_buyer ? `<span>满级买家: ${escapeHtml(item.max_rank_buyer.player)} ${item.max_rank_buyer.price}p</span>` : ''}
                </div>` : '')}
            </div>`;
        });
        html += '</div></div>';

        // Pagination controls
        if (totalPages > 1) {
            html += `<div style="display:flex;justify-content:center;align-items:center;gap:12px;margin-top:12px;">
                <button onclick="modFlipPrevPage()" ${_modFlipPage === 0 ? 'disabled' : ''} style="padding:6px 16px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;cursor:${_modFlipPage === 0 ? 'not-allowed' : 'pointer'};opacity:${_modFlipPage === 0 ? 0.4 : 1};">上一页</button>
                <span style="color:var(--text-muted);font-size:0.85em;">${_modFlipPage + 1} / ${totalPages}</span>
                <button onclick="modFlipNextPage()" ${_modFlipPage >= totalPages - 1 ? 'disabled' : ''} style="padding:6px 16px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;cursor:${_modFlipPage >= totalPages - 1 ? 'not-allowed' : 'pointer'};opacity:${_modFlipPage >= totalPages - 1 ? 0.4 : 1};">下一页</button>
            </div>`;
        }
    }
    content.innerHTML = html;
}

function modFlipPrevPage() {
    if (_modFlipPage > 0) { _modFlipPage--; renderModFlipPage(document.getElementById('detail-content')); }
}
function modFlipNextPage() {
    const totalPages = Math.ceil(_modFlipData.length / _MOD_FLIP_PAGE_SIZE);
    if (_modFlipPage < totalPages - 1) { _modFlipPage++; renderModFlipPage(document.getElementById('detail-content')); }
}

async function loadModFlipper() {
    document.getElementById('more-menu')?.classList.remove('active');
    const content = openDetailPanel('扫描 Mod 翻转机会...<br><small style="color:var(--text-muted)">首次扫描可能需要 1-2 分钟</small>');
    if (!content) return;

    await _pollScan('/api/mod_flipper?min_profit=1&min_roi_pct=100&limit=50', content, (data) => {
        _modFlipData = data.results || [];
        _modFlipPage = 0;
        renderModFlipPage(content);
    });
}

document.getElementById('mod-flip-btn')?.addEventListener('click', () => loadModFlipper());

// ===== 套装利润分析 =====
async function loadSetProfit(minProfit = 3) {
    document.getElementById('more-menu')?.classList.remove('active');
    const content = openDetailPanel('扫描套装利润...<br><small style="color:var(--text-muted)">首次扫描可能需要 2-3 分钟</small>');
    if (!content) return;

    await _pollScan(`/api/set_profit?min_profit=${minProfit}&limit=20`, content, (data) => {
        const items = data.results || [];

        let html = `<div class="panel-title-row">
            <span class="panel-title-eyebrow">套装利润</span>
            <span class="badge ${items.length > 0 ? 'badge-gold' : 'badge-muted'}">${items.length} 套装</span>
        </div>`;

        if (items.length === 0) {
            html += `<div class="empty-state"><div class="empty-icon">📦</div>
                <span class="empty-primary">暂无利润机会</span>
                <span class="empty-sub">当前市场未发现符合条件的套装</span></div>`;
        } else {
            html += '<div class="card"><div class="card-body">';
            items.forEach((item, idx) => {
                const profitColor = item.best_profit > 0 ? 'var(--green-success)' : 'var(--red-error)';
                html += `<div class="fissure-item" style="flex-direction:column;align-items:flex-start;gap:4px;">
                    <div style="display:flex;justify-content:space-between;width:100%;align-items:center;">
                        <div class="fissure-node">${idx + 1}. ${item.display_name || item.base_id}</div>
                        <span style="color:${profitColor};font-weight:700;font-family:var(--font-mono);font-size:1.1em;">+${item.best_profit}p</span>
                    </div>
                    <div style="display:flex;gap:12px;font-size:0.8em;color:var(--text-secondary);flex-wrap:wrap;">
                        <span>策略: ${escapeHtml(item.best_strategy || item.trade_plan?.display_strategy || '-')}</span>
                        <span>成本: ${item.best_cost ?? '-'}p</span>
                        <span>收入: ${item.best_revenue ?? '-'}p</span>
                        <span>ROI: ${escapeHtml(item.roi_pct ?? 0)}%</span>
                        <span>机会分: ${escapeHtml(item.opportunity_score ?? 0)}</span>
                        <span>流动性: ${escapeHtml(item.liquidity_score ?? 0)}</span>
                        <span>风险: ${escapeHtml(item.risk_level || '-')}</span>
                        <span>48h量: ${item.volume_48h ?? '?'}</span>
                        ${item.market_url ? `<a href="${escapeHtml(item.market_url)}" target="_blank" rel="noopener" style="color:var(--accent-color);text-decoration:none;">整套市场 ↗</a>` : ''}
                    </div>
                    ${item.trade_plan ? renderTradePlanCard(item.trade_plan) : `${(item.set_seller || item.set_buyer) ? `<div style="font-size:0.75em;color:var(--text-secondary);display:flex;gap:10px;flex-wrap:wrap;">
                        ${item.set_seller ? `<span>整套卖家: ${escapeHtml(item.set_seller.player)} ${item.set_seller.price}p</span>` : ''}
                        ${item.set_buyer ? `<span>整套买家: ${escapeHtml(item.set_buyer.player)} ${item.set_buyer.price}p</span>` : ''}
                    </div>` : ''}
                    ${item.part_details && item.part_details.length ? `<div style="font-size:0.75em;color:var(--text-secondary);display:flex;gap:8px;flex-wrap:wrap;">
                        ${item.part_details.map(part => `<a href="${escapeHtml(part.market_url)}" target="_blank" rel="noopener" style="color:var(--accent-color);text-decoration:none;">${escapeHtml(part.name)} ↗</a>`).join('')}
                    </div>` : ''}`}
                </div>`;
            });
            html += '</div></div>';
        }
        content.innerHTML = html;
    });
}

document.getElementById('set-profit-btn')?.addEventListener('click', () => loadSetProfit());

// ===== 投资顾问 =====
let _investData = [];
let _investPage = 0;
const _INVEST_PAGE_SIZE = 5;

function renderInvestPage(content) {
    const items = _investData;
    const totalPages = Math.ceil(items.length / _INVEST_PAGE_SIZE);
    const start = _investPage * _INVEST_PAGE_SIZE;
    const pageItems = items.slice(start, start + _INVEST_PAGE_SIZE);

    let html = `<div class="panel-title-row">
        <span class="panel-title-eyebrow">Prime 套装投资顾问</span>
        <span class="badge ${items.length > 0 ? 'badge-gold' : 'badge-muted'}">${items.length} 套装</span>
    </div>`;

    // 预算输入
    html += `<div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap;">
        <label style="font-size:0.85em;color:var(--text-secondary);">预算:</label>
        <input id="invest-budget" type="number" value="${_investBudget || 500}" min="10" step="50"
            style="width:80px;padding:4px 8px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;font-size:0.85em;">
        <span style="font-size:0.85em;color:var(--text-secondary);">p</span>
        <button onclick="reloadInvestment()" style="padding:4px 12px;border:1px solid var(--accent-color);background:var(--accent-color);color:#fff;border-radius:6px;cursor:pointer;font-size:0.85em;">扫描</button>
    </div>`;

    if (items.length === 0) {
        html += `<div class="empty-state"><div class="empty-icon">💎</div>
            <span class="empty-primary">暂无投资机会</span>
            <span class="empty-sub">当前市场未发现符合条件的 Prime 套装</span></div>`;
    } else {
        // 总利润汇总
        const totalProfit = items.reduce((s, i) => s + i.total_profit, 0);
        html += `<div style="background:var(--bg-tertiary);border-radius:8px;padding:8px 12px;margin-bottom:10px;font-size:0.85em;color:var(--text-secondary);">
            预算 <span style="color:var(--text-primary);font-weight:600;">${_investBudget || 500}p</span> ·
            全部执行可赚 <span style="color:var(--green-success);font-weight:700;">+${totalProfit}p</span>
        </div>`;

        html += '<div class="card"><div class="card-body">';
        pageItems.forEach((item, idx) => {
            const globalIdx = start + idx + 1;
            const roiColor = item.roi_pct >= 100 ? '#00ff88' : item.roi_pct >= 50 ? '#ffcc00' : '#ff9900';
            const riskColor = item.risk_level === 'low' ? 'var(--green-success)' :
                item.risk_level === 'medium' ? 'var(--orange-warning)' : 'var(--red-error)';
            const riskIcon = item.risk_level === 'low' ? '🟢' :
                item.risk_level === 'medium' ? '🟡' : '🔴';
            const strategyLabel = item.strategy === 'buy_parts_sell_set' ? '散买→整卖' : '整买→散卖';
            const marketUrl = `https://warframe.market/items/${item.set_item_id}`;

            html += `<div class="fissure-item" style="flex-direction:column;align-items:flex-start;gap:4px;">
                <div style="display:flex;justify-content:space-between;width:100%;align-items:center;">
                    <div class="fissure-node">${globalIdx}. ${item.display_name}</div>
                    <span style="color:${roiColor};font-weight:700;font-family:var(--font-mono);font-size:1.05em;">ROI ${item.roi_pct}%</span>
                </div>
                <div style="display:flex;gap:8px;font-size:0.8em;color:var(--text-secondary);flex-wrap:wrap;align-items:center;">
                    <span style="background:var(--bg-tertiary);padding:1px 6px;border-radius:4px;font-size:0.85em;">${strategyLabel}</span>
                    <span style="color:var(--green-success);font-weight:600;">+${item.profit_per_set}p/套</span>
                    <span>成本: ${item.buy_cost}p</span>
                    <span>可买: ${item.sets_affordable}套</span>
                    <span style="color:var(--green-success);font-weight:600;">总赚: +${item.total_profit}p</span>
                    <span>48h量: ${item.volume_48h ?? '?'}</span>
                    <span style="color:${riskColor}">${riskIcon} ${item.risk_level}</span>
                </div>`;

            if (item.trade_plan) {
                html += renderTradePlanCard(item.trade_plan);
            }

            // 部件明细（可折叠）
            if (item.part_details && item.part_details.length > 0) {
                const detailId = `invest-parts-${globalIdx}`;
                html += `<div style="width:100%;margin-top:2px;">
                    <button onclick="toggleInvestParts('${detailId}')" style="background:none;border:none;color:var(--accent-color);cursor:pointer;font-size:0.75em;padding:0;">
                        ▶ 部件明细
                    </button>
                    <div id="${detailId}" style="display:none;margin-top:4px;padding:6px 8px;background:var(--bg-tertiary);border-radius:6px;font-size:0.75em;">
                        <div style="display:grid;grid-template-columns:1fr auto auto;gap:2px 12px;">`;
                item.part_details.forEach(p => {
                    html += `<span style="color:var(--text-secondary);">${p.name}</span>
                        <span>买 ${p.buy}p</span>
                        <span>卖 ${p.sell}p</span>`;
                });
                html += `</div>
                        <div style="margin-top:6px;">
                            <a href="${marketUrl}" target="_blank" rel="noopener" style="color:var(--accent-color);text-decoration:none;font-size:0.9em;">
                                在 warframe.market 查看 ↗
                            </a>
                        </div>
                    </div>
                </div>`;
            }

            html += `</div>`;
        });
        html += '</div></div>';

        // 分页控件
        if (totalPages > 1) {
            html += `<div style="display:flex;justify-content:center;align-items:center;gap:12px;margin-top:12px;">
                <button onclick="investPrevPage()" ${_investPage === 0 ? 'disabled' : ''} style="padding:6px 16px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;cursor:${_investPage === 0 ? 'not-allowed' : 'pointer'};opacity:${_investPage === 0 ? 0.4 : 1};">上一页</button>
                <span style="color:var(--text-muted);font-size:0.85em;">${_investPage + 1} / ${totalPages}</span>
                <button onclick="investNextPage()" ${_investPage >= totalPages - 1 ? 'disabled' : ''} style="padding:6px 16px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;cursor:${_investPage >= totalPages - 1 ? 'not-allowed' : 'pointer'};opacity:${_investPage >= totalPages - 1 ? 0.4 : 1};">下一页</button>
            </div>`;
        }
    }
    content.innerHTML = html;
}

function toggleInvestParts(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const btn = el.previousElementSibling;
    if (el.style.display === 'none') {
        el.style.display = 'block';
        if (btn) btn.textContent = '▼ 部件明细';
    } else {
        el.style.display = 'none';
        if (btn) btn.textContent = '▶ 部件明细';
    }
}

function investPrevPage() {
    if (_investPage > 0) { _investPage--; renderInvestPage(document.getElementById('detail-content')); }
}
function investNextPage() {
    const totalPages = Math.ceil(_investData.length / _INVEST_PAGE_SIZE);
    if (_investPage < totalPages - 1) { _investPage++; renderInvestPage(document.getElementById('detail-content')); }
}

let _investBudget = 500;

async function reloadInvestment() {
    const input = document.getElementById('invest-budget');
    if (input) _investBudget = parseInt(input.value) || 500;
    await loadInvestmentAdvisor(_investBudget);
}

async function loadInvestmentAdvisor(budget = 500) {
    document.getElementById('more-menu')?.classList.remove('active');
    _investBudget = budget;
    const content = openDetailPanel('扫描 Prime 套装投资机会...<br><small style="color:var(--text-muted)">首次扫描可能需要 2-3 分钟</small>');
    if (!content) return;

    await _pollScan(`/api/investment?budget=${budget}&min_roi_pct=10&limit=30`, content, (data) => {
        _investData = data.results || [];
        _investPage = 0;
        renderInvestPage(content);
    });
}

document.getElementById('investment-btn')?.addEventListener('click', () => loadInvestmentAdvisor());

// ===== 目标引擎 =====
let _goalsData = [];
let _goalsPage = 0;
const _GOAL_PAGE_SIZE = 5;

function renderGoalPage(content) {
    const items = _goalsData;
    const totalPages = Math.ceil(items.length / _GOAL_PAGE_SIZE);
    const start = _goalsPage * _GOAL_PAGE_SIZE;
    const pageItems = items.slice(start, start + _GOAL_PAGE_SIZE);

    let html = `<div class="panel-title-row">
        <span class="panel-title-eyebrow">Agent 目标引擎</span>
        <span class="badge ${items.length > 0 ? 'badge-gold' : 'badge-muted'}">${items.length} 目标</span>
    </div>`;

    // 创建目标按钮
    html += `<div style="margin-bottom:12px;">
        <button onclick="showCreateGoalModal()" style="padding:6px 16px;border:1px solid var(--accent-color);background:var(--accent-color);color:#fff;border-radius:6px;cursor:pointer;font-size:0.85em;width:100%;">+ 创建新目标</button>
    </div>`;

    if (items.length === 0) {
        html += `<div class="empty-state"><div class="empty-icon">🎯</div>
            <span class="empty-primary">暂无活跃目标</span>
            <span class="empty-sub">创建目标让 Agent 帮你自动寻找交易机会</span></div>`;
    } else {
        html += '<div class="card"><div class="card-body">';
        pageItems.forEach((goal, idx) => {
            const globalIdx = start + idx + 1;
            const statusColor = goal.status === 'active' ? 'var(--green-success)' :
                goal.status === 'achieved' ? 'var(--accent-color)' : 'var(--red-error)';
            const statusLabel = goal.status === 'active' ? '进行中' :
                goal.status === 'achieved' ? '已达成' : '已放弃';
            const typeLabel = {
                'maximize_profit': '最大化利润',
                'flip_mod': 'Mod 翻转',
                'build_set': '凑套装',
                'find_bargain': '找便宜货',
                'earn_platinum': '攒白金'
            }[goal.goal_type] || goal.goal_type;

            html += `<div class="fissure-item" style="flex-direction:column;align-items:flex-start;gap:6px;">
                <div style="display:flex;justify-content:space-between;width:100%;align-items:center;">
                    <div class="fissure-node">${globalIdx}. ${goal.description}</div>
                    <span style="color:${statusColor};font-size:0.8em;font-weight:600;">${statusLabel}</span>
                </div>
                <div style="display:flex;gap:8px;font-size:0.8em;color:var(--text-secondary);flex-wrap:wrap;align-items:center;">
                    <span style="background:var(--bg-tertiary);padding:1px 6px;border-radius:4px;">${typeLabel}</span>
                    <span>目标: ${goal.target}</span>
                    <span>结果: ${goal.result_count} 条</span>
                </div>`;

            // 最近结果
            if (goal.results && goal.results.length > 0) {
                html += `<div style="width:100%;margin-top:2px;">
                    <button onclick="toggleGoalResults('goal-results-${goal.goal_id}')" style="background:none;border:none;color:var(--accent-color);cursor:pointer;font-size:0.75em;padding:0;">
                        ▶ 最近发现
                    </button>
                    <div id="goal-results-${goal.goal_id}" style="display:none;margin-top:4px;padding:6px 8px;background:var(--bg-tertiary);border-radius:6px;font-size:0.75em;">`;
                goal.results.forEach(r => {
                    html += `<div style="display:flex;justify-content:space-between;padding:2px 0;">
                        <span>${r.item_name || r.item_id}</span>
                        <span style="color:var(--green-success);">+${r.profit}p (ROI ${r.roi_pct}%)</span>
                    </div>`;
                });
                html += `</div></div>`;
            }

            // 操作按钮
            if (goal.status === 'active') {
                html += `<div style="display:flex;gap:6px;width:100%;margin-top:4px;">
                    <button onclick="executeGoal('${goal.goal_id}')" style="flex:1;padding:4px 8px;border:1px solid var(--accent-color);background:var(--accent-color);color:#fff;border-radius:6px;cursor:pointer;font-size:0.8em;">执行</button>
                    <button onclick="abandonGoal('${goal.goal_id}')" style="flex:1;padding:4px 8px;border:1px solid var(--red-error);background:transparent;color:var(--red-error);border-radius:6px;cursor:pointer;font-size:0.8em;">放弃</button>
                </div>`;
            }

            html += `</div>`;
        });
        html += '</div></div>';

        // 分页
        if (totalPages > 1) {
            html += `<div style="display:flex;justify-content:center;align-items:center;gap:12px;margin-top:12px;">
                <button onclick="goalPrevPage()" ${_goalsPage === 0 ? 'disabled' : ''} style="padding:6px 16px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;cursor:${_goalsPage === 0 ? 'not-allowed' : 'pointer'};opacity:${_goalsPage === 0 ? 0.4 : 1};">上一页</button>
                <span style="color:var(--text-muted);font-size:0.85em;">${_goalsPage + 1} / ${totalPages}</span>
                <button onclick="goalNextPage()" ${_goalsPage >= totalPages - 1 ? 'disabled' : ''} style="padding:6px 16px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;cursor:${_goalsPage >= totalPages - 1 ? 'not-allowed' : 'pointer'};opacity:${_goalsPage >= totalPages - 1 ? 0.4 : 1};">下一页</button>
            </div>`;
        }
    }

    // 摘要统计
    html += `<div id="goal-summary" style="margin-top:12px;padding:8px 12px;background:var(--bg-tertiary);border-radius:8px;font-size:0.8em;color:var(--text-secondary);">
        加载中...
    </div>`;

    content.innerHTML = html;
    loadGoalSummary();
}

function toggleGoalResults(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const btn = el.previousElementSibling;
    if (el.style.display === 'none') {
        el.style.display = 'block';
        if (btn) btn.textContent = '▼ 最近发现';
    } else {
        el.style.display = 'none';
        if (btn) btn.textContent = '▶ 最近发现';
    }
}

function goalPrevPage() {
    if (_goalsPage > 0) { _goalsPage--; renderGoalPage(document.getElementById('detail-content')); }
}
function goalNextPage() {
    const totalPages = Math.ceil(_goalsData.length / _GOAL_PAGE_SIZE);
    if (_goalsPage < totalPages - 1) { _goalsPage++; renderGoalPage(document.getElementById('detail-content')); }
}

async function loadGoalSummary() {
    try {
        const resp = await fetch('/api/goals/summary');
        const data = await resp.json();
        const el = document.getElementById('goal-summary');
        if (el) {
            el.innerHTML = `活跃: <b>${data.active_goals}</b> · 交易: <b>${data.total_outcomes}</b> · 采纳率: <b>${data.adoption_rate}%</b> · 预期利润: <b>${data.total_expected_profit}p</b>`;
        }
    } catch (e) {}
}

async function loadGoalDashboard() {
    const content = openDetailPanel('加载目标列表...');
    if (!content) return;

    try {
        const resp = await fetch('/api/goals');
        const data = await resp.json();
        _goalsData = data.goals || [];
        _goalsPage = 0;
        renderGoalPage(content);
    } catch (err) {
        content.innerHTML = `<div class="empty-state"><div class="empty-icon">🎯</div>
            <span class="empty-primary">加载失败</span><span class="empty-sub">${err.message}</span></div>`;
    }
}

function showCreateGoalModal() {
    const content = document.getElementById('detail-content');
    if (!content) return;

    content.innerHTML = `<div class="panel-title-row">
        <span class="panel-title-eyebrow">创建新目标</span>
    </div>
    <div style="display:flex;flex-direction:column;gap:12px;padding:8px 0;">
        <div>
            <label style="font-size:0.85em;color:var(--text-secondary);display:block;margin-bottom:4px;">目标类型</label>
            <select id="goal-type" onchange="toggleGoalTypeFields(this.value)" style="width:100%;padding:6px 8px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;">
                <option value="maximize_profit">最大化利润（全扫描）</option>
                <option value="flip_mod">Mod 翻转</option>
                <option value="build_set">凑套装</option>
                <option value="find_bargain">找便宜货</option>
                <option value="earn_platinum">攒白金</option>
            </select>
        </div>
        <div>
            <label style="font-size:0.85em;color:var(--text-secondary);display:block;margin-bottom:4px;">目标描述</label>
            <input id="goal-desc" type="text" placeholder="例如：找到 ROI 100%+ 的 Mod 翻转机会" style="width:100%;padding:6px 8px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;">
        </div>
        <div>
            <label style="font-size:0.85em;color:var(--text-secondary);display:block;margin-bottom:4px;">预算 (p)</label>
            <input id="goal-budget" type="number" value="500" min="10" step="50" style="width:100%;padding:6px 8px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;">
        </div>
        <div id="goal-target-amount-row" style="display:none;">
            <label style="font-size:0.85em;color:var(--text-secondary);display:block;margin-bottom:4px;">目标白金 (p)</label>
            <input id="goal-target-amount" type="number" value="100" min="10" step="10" style="width:100%;padding:6px 8px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;">
        </div>
        <div id="goal-roi-row">
            <label style="font-size:0.85em;color:var(--text-secondary);display:block;margin-bottom:4px;">最低 ROI %</label>
            <input id="goal-roi" type="number" value="50" min="0" step="10" style="width:100%;padding:6px 8px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;">
        </div>
        <div style="display:flex;gap:8px;">
            <button onclick="submitCreateGoal()" style="flex:1;padding:8px;border:1px solid var(--accent-color);background:var(--accent-color);color:#fff;border-radius:6px;cursor:pointer;font-weight:600;">创建</button>
            <button onclick="loadGoalDashboard()" style="flex:1;padding:8px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-primary);border-radius:6px;cursor:pointer;">取消</button>
        </div>
    </div>`;
}

function toggleGoalTypeFields(goalType) {
    const targetRow = document.getElementById('goal-target-amount-row');
    const roiRow = document.getElementById('goal-roi-row');
    if (targetRow) targetRow.style.display = goalType === 'earn_platinum' ? 'block' : 'none';
    if (roiRow) roiRow.style.display = goalType === 'earn_platinum' ? 'none' : 'block';
}

async function submitCreateGoal() {
    const goalType = document.getElementById('goal-type')?.value || 'maximize_profit';
    const desc = document.getElementById('goal-desc')?.value || '';
    const budget = parseInt(document.getElementById('goal-budget')?.value) || 500;
    const roi = parseInt(document.getElementById('goal-roi')?.value) || 50;
    const targetAmount = parseInt(document.getElementById('goal-target-amount')?.value) || 100;

    if (!desc.trim()) {
        alert('请输入目标描述');
        return;
    }

    try {
        if (goalType === 'earn_platinum') {
            const resp = await fetch('/api/goals/earn', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({target_amount: targetAmount, budget})
            });
            const data = await resp.json();
            if (data.goal_id) {
                loadGoalDashboard();
            }
        } else {
            const resp = await fetch('/api/goals', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    goal_type: goalType,
                    description: desc.trim(),
                    target: goalType === 'flip_mod' ? 'mod' : goalType === 'build_set' ? 'prime_sets' : 'all',
                    criteria: {budget, min_roi: roi}
                })
            });
            const data = await resp.json();
            if (data.status === 'ok') {
                loadGoalDashboard();
            }
        }
    } catch (err) {
        alert('创建失败: ' + err.message);
    }
}

async function executeGoal(goalId) {
    const content = document.getElementById('detail-content');
    const ver = getPanelVersion();
    if (content) {
        content.innerHTML = `<div class="empty-state"><div class="empty-icon">⏳</div>
            <span class="empty-primary">正在执行目标...</span>
            <span class="empty-sub">扫描中，通常需要 1-4 分钟</span></div>`;
    }

    try {
        const resp = await fetch(`/api/goals/${goalId}/execute`, {method: 'POST'});
        if (getPanelVersion() !== ver) return;
        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP ${resp.status}`);
        }
        const {task_id} = await resp.json();

        let attempts = 0;
        const maxAttempts = 150;
        while (attempts < maxAttempts) {
            await new Promise(r => setTimeout(r, 2000));
            attempts++;
            if (getPanelVersion() !== ver) return;
            const statusResp = await fetch(`/api/goals/execute_status/${task_id}`);
            if (!statusResp.ok) break;
            const status = await statusResp.json();

            if (status.status === 'done') {
                if (getPanelVersion() !== ver) return;
                const goalsResp = await fetch('/api/goals');
                const goalsData = await goalsResp.json();
                _goalsData = goalsData.goals || [];
                _goalsPage = 0;
                if (content) renderGoalPage(content);
                return;
            }
            if (status.status === 'error') {
                throw new Error(status.error || '执行异常');
            }
            if (content && attempts % 5 === 0) {
                const dots = '.'.repeat((attempts % 3) + 1);
                const sub = content.querySelector('.empty-sub');
                if (sub) sub.textContent = `扫描中${dots} (${attempts * 2}s)`;
            }
        }
        throw new Error('执行超时');
    } catch (err) {
        if (getPanelVersion() !== ver) return;
        if (content) {
            content.innerHTML = `<div class="empty-state"><div class="empty-icon">❌</div>
                <span class="empty-primary">执行失败</span><span class="empty-sub">${err.message}</span></div>`;
        }
    }
}

async function abandonGoal(goalId) {
    if (!confirm('确定放弃这个目标？')) return;
    try {
        await fetch(`/api/goals/${goalId}`, {method: 'DELETE'});
        loadGoalDashboard();
    } catch (err) {
        alert('操作失败: ' + err.message);
    }
}

document.getElementById('goal-btn')?.addEventListener('click', () => { document.getElementById('more-menu')?.classList.remove('active'); loadGoalDashboard(); });
