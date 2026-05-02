/* ============================================
   Warframe Trading Agent - Chart Module
   Tenno 科技终端图表模块 v3.0
   ============================================ */

// ===== 图表状态 =====
let priceChart = null;
let currentItemId = null;
let currentRange = 'all';

// ===== Warframe 配色 =====
const CHART_COLORS = {
    sell: {
        line: '#ef4444',
        fill: 'rgba(239, 68, 68, 0.1)',
        point: '#ef4444'
    },
    buy: {
        line: '#4ade80',
        fill: 'rgba(74, 222, 128, 0.1)',
        point: '#4ade80'
    },
    grid: 'rgba(255, 255, 255, 0.05)',
    text: 'rgba(255, 255, 255, 0.6)',
    tooltip: {
        bg: 'rgba(12, 16, 32, 0.95)',
        border: 'rgba(212, 167, 55, 0.3)',
        text: '#e0e0e0'
    }
};

// ===== 显示价格图表 =====

async function showPriceChart(itemId, range) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');

    currentItemId = itemId;
    if (range) currentRange = range;

    panel.classList.add('active');
    content.innerHTML = createChartLoading();

    try {
        const [detailData, historyData] = await Promise.all([
            getItemDetail(itemId),
            getHistoryWithRange(itemId, currentRange)
        ]);

        let html = '';

        // 物品详情卡片
        if (detailData && !detailData.error) {
            html += renderItemDetailCard(detailData);
        }

        // 时间范围选择器
        html += `
            <div class="chart-range-selector">
                <button class="range-btn ${currentRange === '24h' ? 'active' : ''}" onclick="showPriceChart('${itemId}', '24h')">24h</button>
                <button class="range-btn ${currentRange === '7d' ? 'active' : ''}" onclick="showPriceChart('${itemId}', '7d')">7天</button>
                <button class="range-btn ${currentRange === '30d' ? 'active' : ''}" onclick="showPriceChart('${itemId}', '30d')">30天</button>
                <button class="range-btn ${currentRange === 'all' ? 'active' : ''}" onclick="showPriceChart('${itemId}', 'all')">全部</button>
            </div>
        `;

        if (!historyData.snapshots || historyData.snapshots.length === 0) {
            html += createChartEmpty(itemId);
            content.innerHTML = html;
            return;
        }

        html += `
            <div class="chart-header">
                <div class="chart-subtitle">价格历史趋势</div>
            </div>
            <div class="chart-container">
                <canvas id="price-chart"></canvas>
            </div>
            <div class="chart-legend">
                <div class="legend-item">
                    <div class="legend-color sell"></div>
                    <span>卖价</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color buy"></div>
                    <span>收价</span>
                </div>
            </div>
            <div class="chart-stats">
                ${renderChartStats(historyData.snapshots)}
            </div>
        `;

        content.innerHTML = html;
        renderChartCanvas(historyData);
    } catch (err) {
        content.innerHTML = createChartError(err.message);
    }
}

async function getItemDetail(itemId) {
    try {
        const res = await fetch(`/api/item_detail/${itemId}`);
        return await res.json();
    } catch (e) {
        return null;
    }
}

async function getHistoryWithRange(itemId, range) {
    const res = await fetch(`/api/history/${itemId}?range=${range}`);
    return await res.json();
}

// ===== 物品详情卡片 =====

function renderItemDetailCard(data) {
    const spreadClass = data.spread > 0 ? 'positive' : (data.spread < 0 ? 'negative' : '');
    const spreadText = data.spread !== null && data.spread !== undefined ? `${data.spread}p` : '-';

    let card = `
        <div class="item-detail-card">
            <div class="item-detail-header">
                <h3 class="item-detail-name">${data.display || data.item_id}</h3>
                ${data.item_type ? `
                <div class="item-type-badge ${data.item_type}">
                    <span class="type-icon">${data.item_type === 'arcane' ? '⚡' : '🔧'}</span>
                    <span class="type-text">${data.item_type_display}</span>
                    <span class="type-rank">Rank ${data.max_rank}/${data.max_rank}</span>
                </div>
                ` : ''}
            </div>
            <div class="item-detail-prices">
                <div class="price-block sell">
                    <div class="price-label">最低卖价</div>
                    <div class="price-value">${data.sell_price !== null ? data.sell_price + 'p' : '暂无'}</div>
                    ${data.seller ? `<div class="price-player">${data.seller.name} (信誉 ${data.seller.reputation})</div>` : ''}
                </div>
                <div class="price-block spread ${spreadClass}">
                    <div class="price-label">价差</div>
                    <div class="price-value">${spreadText}</div>
                </div>
                <div class="price-block buy">
                    <div class="price-label">最高收价</div>
                    <div class="price-value">${data.buy_price !== null ? data.buy_price + 'p' : '暂无'}</div>
                    ${data.buyer ? `<div class="price-player">${data.buyer.name} (信誉 ${data.buyer.reputation})</div>` : ''}
                </div>
            </div>
    `;

    // 物品类型和等级信息
    if (data.item_type) {
        const rarityColors = {
            'COMMON': '#a0a0a0',
            'UNCOMMON': '#e0e0e0',
            'RARE': '#ffd700',
            'LEGENDARY': '#ff8c00',
            'PRIME': '#00bfff'
        };
        const rarityColor = rarityColors[data.rarity] || '#a0a0a0';
        const rarityText = {
            'COMMON': '普通',
            'UNCOMMON': '罕见',
            'RARE': '稀有',
            'LEGENDARY': '传说',
            'PRIME': 'Prime'
        }[data.rarity] || data.rarity;

        card += `
            <div class="rank-info-section">
                <div class="rank-header">
                    <span class="rank-icon">📊</span>
                    <span class="rank-title">等级信息</span>
                </div>
                <div class="rank-details">
                    <div class="rank-row">
                        <span class="rank-label">类型</span>
                        <span class="rank-value" style="color: ${rarityColor}">${data.item_type_display}</span>
                    </div>
                    <div class="rank-row">
                        <span class="rank-label">稀有度</span>
                        <span class="rank-value" style="color: ${rarityColor}">${rarityText}</span>
                    </div>
                    <div class="rank-row">
                        <span class="rank-label">最大等级</span>
                        <span class="rank-value">${data.max_rank}/${data.max_rank}</span>
                    </div>
                    ${data.item_type === 'arcane' ? `
                    <div class="rank-note">
                        <span class="note-icon">💡</span>
                        <span class="note-text">赋能满级为 ${data.max_rank}/${data.max_rank}，需要 ${data.max_rank + 1} 个相同赋能融合</span>
                    </div>
                    ` : `
                    <div class="rank-note">
                        <span class="note-icon">💡</span>
                        <span class="note-text">Mod 满级为 ${data.max_rank}/${data.max_rank}，需要消耗内融核心升级</span>
                    </div>
                    `}
                </div>
            </div>
        `;
    }

    // 杜卡特信息
    if (data.ducat_value !== null && data.ducat_value !== undefined) {
        card += renderDucatInfo(data);
    }

    if (data.max_level_cost) {
        card += `<div class="item-detail-extra">满级估算: ${data.max_rank + 1 || 21} 个约 ${data.max_level_cost}p</div>`;
    }

    card += `
            <div class="item-detail-actions">
                <button class="detail-action-btn" onclick="copyToClipboard('${data.whisper_sell || ''}')">
                    复制购买私聊
                </button>
                <button class="detail-action-btn" onclick="copyToClipboard('${data.whisper_buy || ''}')">
                    复制出售私聊
                </button>
                <button class="detail-action-btn" onclick="addFavorite('${data.item_id}').then(() => { showToast('已收藏', 'success'); loadSidebar(); })">
                    收藏
                </button>
            </div>
        </div>
    `;

    return card;
}

function copyToClipboard(text) {
    if (!text) {
        showToast('无私聊命令可复制', 'warning');
        return;
    }
    navigator.clipboard.writeText(text).then(() => {
        showToast('已复制到剪贴板', 'success');
    }).catch(() => {
        showToast('复制失败', 'error');
    });
}

function renderDucatInfo(data) {
    let html = `
        <div class="ducat-info">
            <div class="ducat-header">
                <span class="ducat-icon">◆</span>
                <span class="ducat-title">杜卡特分析</span>
            </div>
            <div class="ducat-details">
                <div class="ducat-value-row">
                    <span class="ducat-label">杜卡特价值</span>
                    <span class="ducat-amount">${data.ducat_value} ducats</span>
                </div>
    `;

    if (data.ducat_efficiency) {
        const eff = data.ducat_efficiency;
        const isGoodDeal = eff.recommendation === 'ducat';
        const recommendationClass = isGoodDeal ? 'recommend-ducat' : 'recommend-sell';
        const recommendationText = isGoodDeal ? '建议拆成杜卡特' : '建议直接卖白金';
        const reasonText = `每白金获得 ${eff.ducats_per_plat} 杜卡特`;

        html += `
                <div class="ducat-efficiency">
                    <div class="efficiency-row">
                        <span class="efficiency-label">杜卡特效率</span>
                        <span class="efficiency-value ${eff.ducats_per_plat >= 3 ? 'good' : 'normal'}">${eff.ducats_per_plat} ducats/p</span>
                    </div>
                    <div class="ducat-recommendation ${recommendationClass}">
                        <span class="recommend-icon">${isGoodDeal ? '✓' : '✗'}</span>
                        <span class="recommend-text">${recommendationText}</span>
                    </div>
                    <div class="ducat-reason">${reasonText}${eff.ducats_per_plat >= 3 ? ' (高于3:1阈值)' : ' (低于3:1阈值)'}</div>
                </div>
        `;
    }

    html += `
            </div>
        </div>
    `;

    return html;
}

// ===== 渲染图表 =====

function renderChartCanvas(data) {
    const ctx = document.getElementById('price-chart');
    if (!ctx) return;

    if (priceChart) {
        priceChart.destroy();
    }

    const labels = data.snapshots.map(s => formatDate(s.timestamp)).reverse();
    const sellPrices = data.snapshots.map(s => s.sell_price).reverse();
    const buyPrices = data.snapshots.map(s => s.buy_price).reverse();

    priceChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '卖价',
                    data: sellPrices,
                    borderColor: CHART_COLORS.sell.line,
                    backgroundColor: CHART_COLORS.sell.fill,
                    borderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    pointBackgroundColor: CHART_COLORS.sell.point,
                    tension: 0.4,
                    fill: true
                },
                {
                    label: '收价',
                    data: buyPrices,
                    borderColor: CHART_COLORS.buy.line,
                    backgroundColor: CHART_COLORS.buy.fill,
                    borderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    pointBackgroundColor: CHART_COLORS.buy.point,
                    tension: 0.4,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: CHART_COLORS.tooltip.bg,
                    borderColor: CHART_COLORS.tooltip.border,
                    borderWidth: 1,
                    titleColor: CHART_COLORS.tooltip.text,
                    bodyColor: CHART_COLORS.tooltip.text,
                    padding: 12,
                    titleFont: { family: "'Rajdhani', sans-serif", size: 14, weight: '600' },
                    bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}p`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: CHART_COLORS.grid, drawBorder: false },
                    ticks: {
                        color: CHART_COLORS.text,
                        font: { family: "'JetBrains Mono', monospace", size: 10 },
                        maxRotation: 45,
                        minRotation: 45
                    }
                },
                y: {
                    grid: { color: CHART_COLORS.grid, drawBorder: false },
                    ticks: {
                        color: CHART_COLORS.text,
                        font: { family: "'JetBrains Mono', monospace", size: 11 },
                        callback: (v) => v + 'p'
                    }
                }
            }
        }
    });
}

// ===== 渲染统计信息 =====

function renderChartStats(snapshots) {
    if (!snapshots || snapshots.length === 0) return '';

    const sellPrices = snapshots.map(s => s.sell_price).filter(p => p !== null);
    const buyPrices = snapshots.map(s => s.buy_price).filter(p => p !== null);
    const stats = [];

    if (sellPrices.length > 0) {
        const avg = Math.round(sellPrices.reduce((a, b) => a + b, 0) / sellPrices.length);
        stats.push(`
            <div class="stat-item"><div class="stat-label">平均卖价</div><div class="stat-value">${avg}p</div></div>
            <div class="stat-item"><div class="stat-label">最低卖价</div><div class="stat-value min">${Math.min(...sellPrices)}p</div></div>
            <div class="stat-item"><div class="stat-label">最高卖价</div><div class="stat-value max">${Math.max(...sellPrices)}p</div></div>
        `);
    }

    if (buyPrices.length > 0) {
        const avg = Math.round(buyPrices.reduce((a, b) => a + b, 0) / buyPrices.length);
        stats.push(`
            <div class="stat-item"><div class="stat-label">平均收价</div><div class="stat-value">${avg}p</div></div>
            <div class="stat-item"><div class="stat-label">最低收价</div><div class="stat-value min">${Math.min(...buyPrices)}p</div></div>
            <div class="stat-item"><div class="stat-label">最高收价</div><div class="stat-value max">${Math.max(...buyPrices)}p</div></div>
        `);
    }

    return stats.length > 0 ? `<div class="stats-grid">${stats.join('')}</div>` : '';
}

// ===== 状态模板 =====

function createChartLoading() {
    return `
        <div class="chart-loading">
            <div class="loading"><div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div></div>
            <div class="loading-text">加载价格数据...</div>
        </div>
    `;
}

function createChartEmpty(itemId) {
    return `
        <div class="chart-empty">
            <div class="empty-icon">📊</div>
            <div class="empty-title">暂无价格数据</div>
            <div class="empty-subtitle">查询 "${itemId}" 后将显示价格历史</div>
            <button class="empty-btn" onclick="queryItemPrice('${itemId}')"><span>立即查询</span></button>
        </div>
    `;
}

function createChartError(message) {
    return `
        <div class="chart-error">
            <div class="error-icon">⚠️</div>
            <div class="error-title">加载失败</div>
            <div class="error-message">${message}</div>
        </div>
    `;
}

// ===== 关闭面板 =====

document.getElementById('close-detail').addEventListener('click', () => {
    document.getElementById('detail-panel').classList.remove('active');
    if (priceChart) {
        priceChart.destroy();
        priceChart = null;
    }
});

// ===== 每日报告 =====

document.getElementById('report-btn')?.addEventListener('click', async () => {
    const content = document.getElementById('detail-content');
    const panel = document.getElementById('detail-panel');
    panel.classList.add('active');
    content.innerHTML = createChartLoading();

    try {
        const res = await fetch('/api/report');
        const data = await res.json();
        content.innerHTML = `
            <div class="report-container">
                <h3 class="report-title">每日价格报告</h3>
                <pre class="report-text">${escapeHtml(data.report)}</pre>
                <button class="detail-action-btn" id="copy-report-btn">
                    复制报告
                </button>
            </div>
        `;
        document.getElementById('copy-report-btn')?.addEventListener('click', () => {
            copyToClipboard(data.report);
        });
    } catch (err) {
        content.innerHTML = createChartError('加载报告失败');
    }
});

// ===== 样式注入 =====

const chartStyles = document.createElement('style');
chartStyles.textContent = `
    .item-detail-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(212, 167, 55, 0.2);
        border-radius: 6px;
        padding: 16px;
        margin-bottom: 16px;
        animation: fadeInUp 0.4s ease-out;
    }

    .item-detail-header {
        margin-bottom: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(212, 167, 55, 0.15);
    }

    .item-detail-name {
        font-family: var(--font-display);
        font-size: 16px;
        color: var(--gold-primary);
        letter-spacing: 0.05em;
    }

    .item-detail-prices {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        gap: 12px;
        margin-bottom: 12px;
    }

    .price-block {
        text-align: center;
        padding: 10px 8px;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 4px;
    }

    .price-label {
        font-size: 10px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }

    .price-value {
        font-family: var(--font-mono);
        font-size: 18px;
        font-weight: 700;
        color: var(--text-primary);
    }

    .price-block.sell .price-value { color: var(--red-error); }
    .price-block.buy .price-value { color: var(--green-success); }
    .price-block.spread .price-value { color: var(--gold-primary); }
    .price-block.spread.positive .price-value { color: var(--green-success); }
    .price-block.spread.negative .price-value { color: var(--red-error); }

    .price-player {
        font-size: 10px;
        color: var(--text-tertiary);
        margin-top: 4px;
    }

    .item-detail-extra {
        font-size: 12px;
        color: var(--text-secondary);
        padding: 8px 0;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 10px;
    }

    .item-detail-actions {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }

    .detail-action-btn {
        flex: 1;
        min-width: 80px;
        padding: 6px 10px;
        background: rgba(74, 158, 255, 0.1);
        border: 1px solid rgba(74, 158, 255, 0.25);
        border-radius: 3px;
        color: var(--blue-primary);
        font-size: 11px;
        cursor: pointer;
        transition: all 0.2s ease-out;
        letter-spacing: 0.03em;
    }

    .detail-action-btn:hover {
        background: rgba(74, 158, 255, 0.2);
        transform: translateY(-1px);
    }

    .chart-range-selector {
        display: flex;
        gap: 6px;
        margin-bottom: 16px;
    }

    .range-btn {
        flex: 1;
        padding: 6px 10px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 3px;
        color: var(--text-tertiary);
        font-family: var(--font-mono);
        font-size: 11px;
        cursor: pointer;
        transition: all 0.2s ease-out;
        letter-spacing: 0.05em;
    }

    .range-btn:hover {
        background: rgba(212, 167, 55, 0.1);
        border-color: rgba(212, 167, 55, 0.3);
        color: var(--gold-primary);
    }

    .range-btn.active {
        background: rgba(212, 167, 55, 0.15);
        border-color: var(--gold-primary);
        color: var(--gold-primary);
    }

    .chart-header { margin-bottom: 16px; }

    .chart-subtitle {
        font-size: 12px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
    }

    .chart-container { height: 220px; margin-bottom: 16px; position: relative; }

    .chart-legend { display: flex; gap: 20px; justify-content: center; margin-bottom: 16px; }

    .legend-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); }

    .legend-color { width: 12px; height: 12px; border-radius: 2px; }
    .legend-color.sell { background: var(--red-error); }
    .legend-color.buy { background: var(--green-success); }

    .chart-stats { border-top: 1px solid rgba(212, 167, 55, 0.2); padding-top: 12px; }

    .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }

    .stat-item {
        text-align: center;
        padding: 6px;
        background: rgba(255, 255, 255, 0.02);
        border-radius: 3px;
    }

    .stat-label { font-size: 9px; color: var(--text-tertiary); letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 2px; }
    .stat-value { font-family: var(--font-mono); font-size: 13px; font-weight: 600; color: var(--text-primary); }
    .stat-value.min { color: var(--green-success); }
    .stat-value.max { color: var(--red-error); }

    .chart-loading, .chart-empty, .chart-error {
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        padding: 40px 20px; text-align: center;
    }

    .loading-text { margin-top: 12px; font-size: 12px; color: var(--text-tertiary); }
    .empty-icon, .error-icon { font-size: 40px; margin-bottom: 12px; }
    .empty-title, .error-title { font-family: var(--font-display); font-size: 14px; color: var(--text-primary); margin-bottom: 6px; }
    .empty-subtitle, .error-message { font-size: 12px; color: var(--text-tertiary); margin-bottom: 12px; }

    .empty-btn {
        padding: 6px 14px; background: var(--gradient-gold); color: var(--bg-primary);
        border: none; border-radius: 3px; cursor: pointer;
        font-family: var(--font-display); font-size: 10px; font-weight: 600;
        letter-spacing: 0.05em; text-transform: uppercase; transition: all 0.3s ease-out;
    }
    .empty-btn:hover { transform: translateY(-2px); box-shadow: 0 0 15px rgba(212, 167, 55, 0.3); }

    .report-container { padding: 16px; }
    .report-title { font-family: var(--font-display); font-size: 16px; color: var(--gold-primary); margin-bottom: 12px; }
    .report-text {
        font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary);
        background: rgba(0, 0, 0, 0.2); padding: 12px; border-radius: 4px;
        white-space: pre-wrap; word-break: break-all; margin-bottom: 12px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }

    /* 杜卡特信息样式 */
    .ducat-info {
        background: rgba(212, 167, 55, 0.05);
        border: 1px solid rgba(212, 167, 55, 0.2);
        border-radius: 6px;
        padding: 12px;
        margin: 12px 0;
        animation: fadeInUp 0.4s ease-out;
    }

    .ducat-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(212, 167, 55, 0.15);
    }

    .ducat-icon {
        color: var(--gold-primary);
        font-size: 14px;
    }

    .ducat-title {
        font-family: var(--font-display);
        font-size: 13px;
        color: var(--gold-primary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .ducat-details {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .ducat-value-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .ducat-label {
        font-size: 12px;
        color: var(--text-secondary);
    }

    .ducat-amount {
        font-family: var(--font-mono);
        font-size: 14px;
        font-weight: 600;
        color: var(--gold-primary);
    }

    .ducat-efficiency {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 4px;
        padding: 10px;
        margin-top: 4px;
    }

    .efficiency-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }

    .efficiency-label {
        font-size: 11px;
        color: var(--text-tertiary);
        letter-spacing: 0.05em;
    }

    .efficiency-value {
        font-family: var(--font-mono);
        font-size: 13px;
        font-weight: 600;
    }

    .efficiency-value.good {
        color: var(--green-success);
    }

    .efficiency-value.normal {
        color: var(--text-secondary);
    }

    .ducat-recommendation {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        border-radius: 4px;
        margin-bottom: 6px;
    }

    .ducat-recommendation.recommend-ducat {
        background: rgba(74, 222, 128, 0.1);
        border: 1px solid rgba(74, 222, 128, 0.2);
    }

    .ducat-recommendation.recommend-sell {
        background: rgba(74, 158, 255, 0.1);
        border: 1px solid rgba(74, 158, 255, 0.2);
    }

    .recommend-icon {
        font-size: 14px;
        font-weight: bold;
    }

    .recommend-ducat .recommend-icon {
        color: var(--green-success);
    }

    .recommend-sell .recommend-icon {
        color: var(--blue-primary);
    }

    .recommend-text {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-primary);
    }

    .ducat-reason {
        font-size: 11px;
        color: var(--text-tertiary);
        padding-left: 22px;
    }

    /* 物品类型和等级信息样式 */
    .item-type-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 11px;
        margin-top: 6px;
        letter-spacing: 0.05em;
    }

    .item-type-badge.arcane {
        background: rgba(255, 140, 0, 0.15);
        border: 1px solid rgba(255, 140, 0, 0.3);
        color: #ff8c00;
    }

    .item-type-badge.mod {
        background: rgba(74, 158, 255, 0.15);
        border: 1px solid rgba(74, 158, 255, 0.3);
        color: var(--blue-primary);
    }

    .type-icon {
        font-size: 12px;
    }

    .type-text {
        font-weight: 600;
    }

    .type-rank {
        font-family: var(--font-mono);
        font-size: 10px;
        opacity: 0.8;
    }

    .rank-info-section {
        background: rgba(74, 158, 255, 0.05);
        border: 1px solid rgba(74, 158, 255, 0.2);
        border-radius: 6px;
        padding: 12px;
        margin: 12px 0;
        animation: fadeInUp 0.4s ease-out;
    }

    .rank-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(74, 158, 255, 0.15);
    }

    .rank-icon {
        color: var(--blue-primary);
        font-size: 14px;
    }

    .rank-title {
        font-family: var(--font-display);
        font-size: 13px;
        color: var(--blue-primary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .rank-details {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .rank-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .rank-label {
        font-size: 12px;
        color: var(--text-secondary);
    }

    .rank-value {
        font-family: var(--font-mono);
        font-size: 13px;
        font-weight: 600;
        color: var(--text-primary);
    }

    .rank-note {
        display: flex;
        align-items: flex-start;
        gap: 6px;
        padding: 8px 10px;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 4px;
        margin-top: 4px;
    }

    .note-icon {
        font-size: 12px;
        margin-top: 1px;
    }

    .note-text {
        font-size: 11px;
        color: var(--text-tertiary);
        line-height: 1.4;
    }
`;
document.head.appendChild(chartStyles);
