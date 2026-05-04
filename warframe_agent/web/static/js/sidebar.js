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
document.getElementById('trade-history-btn')?.addEventListener('click', () => {
    toggleMoreMenu();
    loadTradeHistory();
});

// ===== 每日报告 =====
document.getElementById('report-btn')?.addEventListener('click', async () => {
    toggleMoreMenu();
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
            <button class="btn-gradient" onclick="navigator.clipboard.writeText(\`${report.replace(/`/g, '\\`')}\`).then(()=>showToast('已复制','success'))">复制报告</button>
            <button class="btn-gradient btn-gradient-cyan" onclick="document.getElementById('report-btn').click()">刷新</button>
        </div>`;

        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = `<div class="empty-state"><div class="empty-icon">📊</div>
            <span class="empty-primary">报告生成失败</span><span class="empty-sub">${err.message}</span></div>`;
    }
});

// ===== 套利检测功能 =====

async function loadArbitrageOpportunities() {
    const content = openDetailPanel('检测套利机会...');
    if (!content) return;

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
document.getElementById('arbitrage-btn')?.addEventListener('click', () => {
    toggleMoreMenu();
    loadArbitrageOpportunities();
});

// ===== 收藏夹仪表盘 =====

async function loadFavoritesDashboard() {
    const content = openDetailPanel('加载收藏仪表盘...');
    if (!content) return;

    try {
        const [memoryRes, pricesRes] = await Promise.all([
            fetch('/api/memory'),
            fetch('/api/favorites_prices')
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

                <div class="dashboard-summary">
                    <div class="dashboard-stat main">
                        <div class="dashboard-stat-label">总卖出价值</div>
                        <div class="dashboard-stat-value">${totalSell}p</div>
                        <div style="font-size:11px;color:var(--text-tertiary)">全部收藏按最低卖价</div>
                    </div>
                    <div class="dashboard-stat">
                        <div class="dashboard-stat-label">总收购价值</div>
                        <div class="dashboard-stat-value" style="color:var(--blue-primary)">${totalBuy}p</div>
                        <div style="font-size:11px;color:var(--text-tertiary)">全部收藏按最高收价</div>
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
                        <span class="detail-label">收价</span>
                        <span class="detail-value" style="color:var(--blue-primary)">${price && price.buy_price ? price.buy_price + 'p' : '-'}</span>
                        ${spread !== null ? `<span class="detail-spread ${spreadClass}">差 ${spread}p</span>` : ''}
                        <button class="copy-whisper-btn" onclick="event.stopPropagation();copyWhisperMessage('seller','${display.split(' / ')[0]}',${price?.sell_price || 0})" title="复制私聊" style="margin-left:auto">📋</button>
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
    toggleMoreMenu();
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

        sugDiv.innerHTML = data.suggestions.map(s =>
            `<div class="suggestion-item" onclick="selectProfitItem('${s}')">${s}</div>`
        ).join('');
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
            resultDiv.innerHTML = `<div class="profit-recommendation bad">计算失败: ${data.error}</div>`;
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
                <span class="profit-result-label">成品 (${data.display})</span>
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
                <span style="color:var(--text-secondary)">${mat.display} x${mat.quantity}</span>
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
    toggleMoreMenu();
    showProfitCalculator();
});

// ===== 价格异常检测 =====

async function showPriceAnomalies() {
    const content = openDetailPanel('检测价格异常...');
    if (!content) return;

    try {
        const res = await fetch('/api/price/anomalies?threshold=30');
        const data = await res.json();

        if (!data.anomalies || data.anomalies.length === 0) {
            content.innerHTML = `
                <div class="profit-calc-container">
                    <div class="profit-calc-title">价格异常提醒</div>
                    <div class="empty-state" style="padding:32px 0;">
                        <div class="empty-state-icon">📊</div>
                        <div class="empty-state-text">暂无价格异常</div>
                        <div class="empty-state-sub">当物品价格偏离均值超过30%时会在此显示</div>
                    </div>
                </div>
            `;
            return;
        }

        let html = `
            <div class="profit-calc-container">
                <div class="profit-calc-title">价格异常提醒</div>
                <div style="font-size:12px; color:var(--text-tertiary); margin-bottom:16px;">
                    检测到 ${data.total} 个价格异常（偏离阈值 ${data.threshold}%）
                </div>
        `;

        data.anomalies.forEach(item => {
            const isSpike = item.type === 'spike';
            const icon = isSpike ? '📈' : '📉';
            const colorClass = isSpike ? 'positive' : 'negative';
            const deviationSign = item.deviation > 0 ? '+' : '';

            html += `
                <div class="list-item" style="margin-bottom:8px; cursor:pointer;"
                    onclick="showPriceChart('${item.item_id}')">
                    <div class="item-header">
                        <span class="item-name">${icon} ${item.display}</span>
                        <span class="item-price">${item.current_price}p</span>
                    </div>
                    <div class="item-sub" style="display:flex; justify-content:space-between;">
                        <span>均值 ${item.avg_price}p</span>
                        <span class="${colorClass}" style="font-weight:600;">${deviationSign}${item.deviation}%</span>
                    </div>
                    <div class="item-sub">${item.type_display} | 基于 ${item.snapshots_count} 条历史数据</div>
                </div>
            `;
        });

        html += `</div>`;
        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = createChartError('检测价格异常失败');
    }
}

// 绑定价格异常按钮
document.getElementById('anomaly-btn')?.addEventListener('click', () => {
    toggleMoreMenu();
    showPriceAnomalies();
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
    if (Notification.permission === 'granted') {
        new Notification('Warframe 交易助手', { body: '测试通知成功！价格提醒将以此方式通知您。', icon: '/static/favicon.ico' });
        showToast('测试通知已发送', 'success');
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(perm => {
            if (perm === 'granted') {
                new Notification('Warframe 交易助手', { body: '通知权限已开启！' });
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
    toggleMoreMenu();
    showNotificationSettings();
});

// ===== 虚空裂隙追踪 =====

async function showFissureTracker() {
    const content = openDetailPanel('加载虚空裂隙...');
    if (!content) return;

    try {
        const res = await fetch('/api/fissures');
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
            'Meso': '中纪 (Meso)',
            'Neo': '前纪 (Neo)',
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
        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = createChartError('获取裂隙数据失败');
    }
}

// 绑定虚空裂隙按钮
document.getElementById('fissure-btn')?.addEventListener('click', () => {
    toggleMoreMenu();
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
    toggleMoreMenu();
    showWikiWarframes('');
});

document.getElementById('wiki-mods-btn')?.addEventListener('click', () => {
    toggleMoreMenu();
    showWikiMods('', '', '');
});

document.getElementById('relic-search-btn')?.addEventListener('click', () => {
    toggleMoreMenu();
    showRelicSearch('');
});

// ===== 复制私聊消息 (借鉴 WarStonks) =====
function copyWhisperMessage(sellerName, itemName, platinum) {
    const msg = `/w ${sellerName} Hi! I want to buy: ${itemName} for ${platinum} platinum. (warframe.market)`;
    navigator.clipboard.writeText(msg).then(() => {
        showToast('已复制私聊消息', 'success');
    }).catch(() => {
        // Fallback
        const ta = document.createElement('textarea');
        ta.value = msg;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('已复制私聊消息', 'success');
    });
    return msg;
}

// ===== 虚空裂隙面板 (借鉴 WarStonks) =====
async function showFissures() {
    toggleMoreMenu();
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
                <span class="empty-primary">未找到遗物</span><span class="empty-sub">${data.error}</span></div>`;
            return;
        }

        let html = `<div class="panel-title-row">
            <span class="panel-title-eyebrow">遗物掉落</span>
            <span class="badge badge-gold">${data.displayName || tier + ' ' + relicName}</span>
            ${data.vaultStatus ? `<span class="badge ${data.vaultStatus === '已入库' ? 'badge-red' : 'badge-green'}">${data.vaultStatus}</span>` : ''}
            <button class="btn-gradient" style="margin-left:auto;padding:4px 12px;font-size:11px" onclick="showFissures()">← 返回裂隙</button>
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

                    html += `<div class="fissure-item" onclick="queryItemPrice('${r.itemName}')" style="cursor:pointer" title="点击查询价格">
                        <div style="display:flex;align-items:center;gap:8px">
                            <span class="rarity-dot ${r.rarity?.toLowerCase() || 'common'}"></span>
                            <div>
                                <div class="fissure-node">${r.itemName}</div>
                                <div class="fissure-mission">${r.rarityZh || r.rarity}</div>
                            </div>
                        </div>
                        <span style="font-family:var(--font-mono);font-size:13px;font-weight:600;color:${rc.color};background:${rc.bg};padding:2px 8px;border-radius:12px;border:1px solid ${rc.border}">${r.chance}%</span>
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

                html += `<div class="fissure-item" onclick="queryItemPrice('${r.itemName}')" style="cursor:pointer" title="点击查询价格">
                    <div style="display:flex;align-items:center;gap:8px">
                        <span class="rarity-dot ${r.rarity?.toLowerCase() || 'common'}"></span>
                        <div>
                            <div class="fissure-node">${r.itemName}</div>
                            <div class="fissure-mission">${r.rarityZh || r.rarity}</div>
                        </div>
                    </div>
                    <span style="font-family:var(--font-mono);font-size:13px;font-weight:600;color:${rc.color};background:${rc.bg};padding:2px 8px;border-radius:12px;border:1px solid ${rc.border}">${r.chance}%</span>
                </div>`;
            });
        }

        html += `<div style="margin-top:12px;padding:12px;background:rgba(0,0,0,0.2);border-radius:8px;font-size:12px;color:var(--text-tertiary)">
            <strong>精炼等级说明：</strong>
            <ul style="margin:8px 0 0 16px;list-style:disc">
                <li><strong>完好 (Intact)</strong> — 无需消耗，稀有掉率 2%</li>
                <li><strong>卓越 (Exceptional)</strong> — 消耗 25 虚空之尘，稀有掉率 4%</li>
                <li><strong>无瑕 (Flawless)</strong> — 消耗 50 虚空之尘，稀有掉率 6%</li>
                <li><strong>光辉 (Radiant)</strong> — 消耗 100 虚空之尘，稀有掉率 10%</li>
            </ul>
            <p style="margin-top:8px"><strong>组队建议：</strong>4人组队每人开不同遗物，效率最高</p>
        </div>`;

        // 加载遗物来源
        html += '<div id="relic-sources" style="margin-top:12px"><div class="loading-spinner" style="padding:8px"><p style="font-size:12px;color:var(--text-tertiary)">加载掉落来源...</p></div></div>';

        content.innerHTML = html;

        // 异步加载来源数据
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

document.getElementById('fissure-btn')?.addEventListener('click', () => showFissures());

// ===== 价格异常检测 (借鉴 WarStonks 套利扫描) =====
async function showPriceAnomalies() {
    toggleMoreMenu();
    const content = document.getElementById('detail-content');
    if (!content) return;
    content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>扫描价格异常...</p></div>';
    document.getElementById('detail-panel')?.classList.add('active');

    try {
        const resp = await fetch('/api/arbitrage');
        const data = await resp.json();
        const items = data.opportunities || [];

        let html = `<div class="panel-title-row">
            <span class="panel-title-eyebrow">价格异常</span>
            <span class="badge ${items.length > 0 ? 'badge-gold' : 'badge-muted'}">${items.length} 机会</span>
        </div>`;

        if (items.length === 0) {
            html += `<div class="empty-state"><div class="empty-icon">📊</div>
                <span class="empty-primary">暂无异常</span>
                <span class="empty-sub">当前市场未发现明显价格异常</span></div>`;
        } else {
            html += '<div class="card"><div class="card-body">';
            items.slice(0, 20).forEach(item => {
                const profitColor = item.profit > 0 ? 'var(--green-success)' : 'var(--red-error)';
                html += `<div class="fissure-item">
                    <div>
                        <div class="fissure-node">${item.item || 'Unknown'}</div>
                        <div class="fissure-mission">买 ${item.buy || 0}p → 卖 ${item.sell || 0}p</div>
                    </div>
                    <span style="color:${profitColor};font-weight:600;font-family:var(--font-mono)">+${item.profit || 0}p</span>
                </div>`;
            });
            html += '</div></div>';
        }
        content.innerHTML = html;
    } catch (err) {
        content.innerHTML = `<div class="empty-state"><div class="empty-icon">📊</div>
            <span class="empty-primary">扫描失败</span><span class="empty-sub">${err.message}</span></div>`;
    }
}

document.getElementById('anomaly-btn')?.addEventListener('click', () => showPriceAnomalies());
