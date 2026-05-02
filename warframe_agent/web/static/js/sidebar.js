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
        // 同时加载关注列表
        await loadWatchlist();
    } catch (err) {
        console.error('加载记忆失败:', err);
        updateSidebarStatus('error');
    }
}

// ===== 渲染收藏列表 =====

function renderFavorites(favorites) {
    const list = document.getElementById('favorites-list');
    const header = list.previousElementSibling;
    list.innerHTML = '';

    if (!favorites || favorites.length === 0) {
        list.classList.add('collapsed');
        if (header) header.classList.add('collapsed');
        return;
    }

    list.classList.remove('collapsed');
    if (header) header.classList.remove('collapsed');

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

const MAX_VISIBLE_ALERTS = 5;
let showAllAlerts = false;

function renderAlerts(alerts) {
    const list = document.getElementById('alerts-list');
    const header = list.previousElementSibling;
    list.innerHTML = '';

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
            <div class="item-sub">${directionText} ${alert.price}p 时提醒${alert.note ? ` - ${alert.note}` : ''}</div>
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

function toggleAlertsView() {
    showAllAlerts = !showAllAlerts;
    loadSidebar();
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

// ===== 交易历史功能 =====

async function loadTradeHistory() {
    const content = document.getElementById('detail-content');
    const panel = document.getElementById('detail-panel');
    panel.classList.add('active');
    content.innerHTML = createChartLoading();

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
                        <div class="trade-item-name">${trade.item_name}</div>
                        <div class="trade-item-details">
                            ${trade.player_name ? `<span class="trade-player">玩家: ${trade.player_name}</span>` : ''}
                            <span class="trade-date">${date}</span>
                        </div>
                        ${trade.notes ? `<div class="trade-notes">${trade.notes}</div>` : ''}
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
document.getElementById('trade-history-btn')?.addEventListener('click', loadTradeHistory);

// ===== 套利检测功能 =====

async function loadArbitrageOpportunities() {
    const content = document.getElementById('detail-content');
    const panel = document.getElementById('detail-panel');
    panel.classList.add('active');
    content.innerHTML = createChartLoading();

    try {
        const res = await fetch('/api/arbitrage?min_profit=3');
        const data = await res.json();

        let html = `
            <div class="arbitrage-container">
                <div class="arbitrage-header">
                    <h3 class="arbitrage-title">套利机会</h3>
                    <div class="arbitrage-subtitle">低买高卖的盈利机会</div>
                </div>
        `;

        if (data.opportunities && data.opportunities.length > 0) {
            html += `
                <div class="arbitrage-summary">
                    <div class="arbitrage-stat">
                        <span class="arbitrage-stat-label">发现机会</span>
                        <span class="arbitrage-stat-value">${data.total}</span>
                    </div>
                    <div class="arbitrage-stat">
                        <span class="arbitrage-stat-label">最低利润</span>
                        <span class="arbitrage-stat-value">${data.min_profit_filter}p</span>
                    </div>
                </div>
            `;

            html += '<div class="arbitrage-list">';
            data.opportunities.forEach((opp, index) => {
                const profitClass = opp.profit >= 10 ? 'high' : (opp.profit >= 5 ? 'medium' : 'low');

                html += `
                    <div class="arbitrage-item" style="animation-delay: ${index * 50}ms">
                        <div class="arbitrage-item-header">
                            <span class="arbitrage-item-name">${opp.display}</span>
                            <span class="arbitrage-profit ${profitClass}">+${opp.profit}p</span>
                        </div>
                        <div class="arbitrage-prices">
                            <div class="arbitrage-price buy">
                                <span class="price-label">买入</span>
                                <span class="price-value">${opp.buy_price}p</span>
                                <span class="price-player">${opp.buyer}</span>
                            </div>
                            <div class="arbitrage-arrow">→</div>
                            <div class="arbitrage-price sell">
                                <span class="price-label">卖出</span>
                                <span class="price-value">${opp.sell_price}p</span>
                                <span class="price-player">${opp.seller}</span>
                            </div>
                        </div>
                        ${opp.ducat_value ? `
                            <div class="arbitrage-ducat">
                                <span class="ducat-info">杜卡特: ${opp.ducat_value}</span>
                                ${opp.ducat_efficiency ? `
                                    <span class="ducat-efficiency ${opp.ducat_efficiency.recommendation === 'ducat' ? 'good' : ''}">
                                        ${opp.ducat_efficiency.ducats_per_plat} ducats/p
                                    </span>
                                ` : ''}
                            </div>
                        ` : ''}
                        <div class="arbitrage-actions">
                            <button class="detail-action-btn" onclick="copyToClipboard('/w ${opp.buyer} Hi! I want to buy...')">
                                复制买入私聊
                            </button>
                            <button class="detail-action-btn" onclick="copyToClipboard('/w ${opp.seller} Hi! I want to sell...')">
                                复制卖出私聊
                            </button>
                            <button class="detail-action-btn" onclick="queryItemPrice('${opp.item_id}')">
                                查看详情
                            </button>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        } else {
            html += `
                <div class="arbitrage-empty">
                    <div class="empty-state-icon">💰</div>
                    <div class="empty-state-text">暂无套利机会</div>
                    <div class="empty-state-sub">收藏物品后，系统将自动检测套利机会</div>
                    <div class="arbitrage-tips">
                        <div class="tip-title">套利提示：</div>
                        <ul>
                            <li>收藏您感兴趣的物品</li>
                            <li>系统会自动检测买卖价差</li>
                            <li>利润 ≥ 3p 的机会会被标记</li>
                        </ul>
                    </div>
                </div>
            `;
        }

        html += '</div>';
        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = createChartError('加载套利数据失败');
    }
}

// 套利检测按钮事件
document.getElementById('arbitrage-btn')?.addEventListener('click', loadArbitrageOpportunities);

// ===== 收藏夹仪表盘 =====

async function loadFavoritesDashboard() {
    const content = document.getElementById('detail-content');
    const panel = document.getElementById('detail-panel');
    panel.classList.add('active');
    content.innerHTML = createChartLoading();

    try {
        const [memoryRes, pricesRes] = await Promise.all([
            fetch('/api/memory'),
            fetch('/api/favorites_prices')
        ]);
        const memoryData = await memoryRes.json();
        const pricesData = await pricesRes.json();

        const favorites = memoryData.favorites || [];
        const prices = pricesData.items || [];

        // 计算统计数据
        let totalValue = 0;
        let itemsWithPrices = 0;
        let priceChanges = { up: 0, down: 0, stable: 0 };

        // 加载上次价格缓存
        loadPriceCache();

        const priceMap = {};
        prices.forEach(item => {
            if (item.sell_price) {
                priceMap[item.item_id] = item;
                totalValue += item.sell_price;
                itemsWithPrices++;

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
            }
        });

        let html = `
            <div class="dashboard-container">
                <div class="dashboard-header">
                    <h3 class="dashboard-title">收藏夹仪表盘</h3>
                    <div class="dashboard-subtitle">收藏物品价格概览</div>
                </div>

                <div class="dashboard-summary">
                    <div class="dashboard-stat main">
                        <div class="dashboard-stat-label">总价值</div>
                        <div class="dashboard-stat-value">${totalValue}p</div>
                    </div>
                    <div class="dashboard-stat">
                        <div class="dashboard-stat-label">物品数</div>
                        <div class="dashboard-stat-value">${favorites.length}</div>
                    </div>
                    <div class="dashboard-stat">
                        <div class="dashboard-stat-label">有价格</div>
                        <div class="dashboard-stat-value">${itemsWithPrices}</div>
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

                <div class="dashboard-items-title">物品列表</div>
                <div class="dashboard-items">
        `;

        // 物品列表
        favorites.forEach((fav, index) => {
            const itemId = typeof fav === 'object' ? fav.item_id : '';
            const display = typeof fav === 'object' ? fav.display : fav;
            const price = priceMap[itemId];
            const prev = previousPrices[itemId];

            let changeHtml = '';
            if (price && prev && prev.sell !== null && price.sell_price !== null) {
                const diff = price.sell_price - prev.sell;
                if (diff > 0) {
                    changeHtml = `<span class="item-change up">▲${diff}</span>`;
                } else if (diff < 0) {
                    changeHtml = `<span class="item-change down">▼${Math.abs(diff)}</span>`;
                }
            }

            html += `
                <div class="dashboard-item" style="animation-delay: ${index * 50}ms" onclick="queryItemPrice('${itemId}')">
                    <div class="dashboard-item-header">
                        <span class="dashboard-item-name">${display.split(' / ')[0]}</span>
                        <span class="dashboard-item-price">
                            ${price && price.sell_price ? price.sell_price + 'p' : '-'}
                            ${changeHtml}
                        </span>
                    </div>
                    ${price && price.buy_price ? `
                        <div class="dashboard-item-detail">
                            <span class="detail-label">收价</span>
                            <span class="detail-value">${price.buy_price}p</span>
                            ${price.sell_price && price.buy_price ? `
                                <span class="detail-spread">差 ${price.sell_price - price.buy_price}p</span>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>
            `;
        });

        html += `
                </div>

                <div class="dashboard-actions">
                    <button class="detail-action-btn" onclick="exportDashboardData()">
                        导出数据
                    </button>
                    <button class="detail-action-btn" onclick="loadFavoritesDashboard()">
                        刷新数据
                    </button>
                </div>
            </div>
        `;

        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = createChartError('加载仪表盘失败');
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
document.getElementById('dashboard-btn')?.addEventListener('click', loadFavoritesDashboard);

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
        background: rgba(212, 167, 55, 0.05);
        border-color: rgba(212, 167, 55, 0.2);
        transform: translateX(2px);
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
`;
document.head.appendChild(sidebarStyles);
