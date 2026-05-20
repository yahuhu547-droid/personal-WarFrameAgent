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
    currentItemId = itemId;
    if (range) currentRange = range;

    const content = openDetailPanel();
    if (!content) return;

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
        const safeId = escapeJsString(itemId);
        html += `
            <div class="chart-range-selector">
                <button class="range-btn ${currentRange === '24h' ? 'active' : ''}" onclick="showPriceChart('${safeId}', '24h')">24h</button>
                <button class="range-btn ${currentRange === '7d' ? 'active' : ''}" onclick="showPriceChart('${safeId}', '7d')">7天</button>
                <button class="range-btn ${currentRange === '30d' ? 'active' : ''}" onclick="showPriceChart('${safeId}', '30d')">30天</button>
                <button class="range-btn ${currentRange === 'all' ? 'active' : ''}" onclick="showPriceChart('${safeId}', 'all')">全部</button>
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
window.showPriceChart = showPriceChart;

async function getItemDetail(itemId) {
    try {
        const res = await fetch(`/api/item_detail/${itemId}`);
        if (!res.ok) return null;
        return await res.json();
    } catch (e) {
        return null;
    }
}

async function getHistoryWithRange(itemId, range) {
    try {
        const res = await fetch(`/api/history/${itemId}?range=${range}`);
        if (!res.ok) return { snapshots: [] };
        return await res.json();
    } catch (e) {
        return { snapshots: [] };
    }
}

// ===== 物品详情卡片 =====

function renderItemDetailCard(data) {
    const spreadClass = data.spread > 0 ? 'positive' : (data.spread < 0 ? 'negative' : '');
    const spreadText = data.spread !== null && data.spread !== undefined ? `${data.spread}p` : '-';
    const trendClass = data.trend === 'up' ? 'trend-up' : data.trend === 'down' ? 'trend-down' : 'trend-stable';

    const safeDisplay = escapeHtml(data.display || data.item_id || '');
    const safeItemId = escapeHtml(data.item_id || '');
    const safeTrendDisplay = escapeHtml(data.trend_display || '');
    const safeItemTypeDisplay = escapeHtml(data.item_type_display || '');
    const jsDisplay = escapeJsString(data.display || data.item_id || '');
    const jsWhisperSell = escapeJsString(data.whisper_sell || '');
    const jsWhisperBuy = escapeJsString(data.whisper_buy || '');
    const jsItemId = escapeJsString(data.item_id || '');

    let card = `
        <div class="item-detail-card">
            <div class="item-detail-header">
                <h3 class="item-detail-name">${safeDisplay}</h3>
                ${data.trend_display ? `<span class="trend-badge ${trendClass}">${safeTrendDisplay}</span>` : ''}
                ${data.item_type ? `
                <div class="item-type-badge ${data.item_type}">
                    <span class="type-icon">${data.item_type === 'arcane' ? '⚡' : '🔧'}</span>
                    <span class="type-text">${safeItemTypeDisplay}</span>
                    <span class="type-rank">Rank ${data.max_rank}/${data.max_rank}</span>
                </div>
                ` : ''}
            </div>
            <div class="item-detail-prices">
                <div class="price-block sell">
                    <div class="price-label">最低卖价</div>
                    <div class="price-value">${data.sell_price !== null ? data.sell_price + 'p' : '暂无'}</div>
                    ${data.seller ? `<div class="price-player">${escapeHtml(data.seller.name)} (信誉 ${data.seller.reputation})
                        ${jsWhisperSell ? `<button class="copy-whisper-btn" onclick="copyProvidedWhisperMessage('${jsWhisperSell}')" title="复制私聊消息">📋 复制私聊</button>` : ''}
                    </div>` : ''}
                </div>
                <div class="price-block spread ${spreadClass}">
                    <div class="price-label">价差</div>
                    <div class="price-value">${spreadText}</div>
                </div>
                <div class="price-block buy">
                    <div class="price-label">最高收价</div>
                    <div class="price-value">${data.buy_price !== null ? data.buy_price + 'p' : '暂无'}</div>
                    ${data.buyer ? `<div class="price-player">${escapeHtml(data.buyer.name)} (信誉 ${data.buyer.reputation})</div>` : ''}
                </div>
            </div>
    `;

    // 增强信息：供需比 + 历史高低
    if (data.supply_count !== undefined || data.history_high !== undefined) {
        card += `<div class="item-enhanced-info">`;
        if (data.supply_count !== undefined) {
            const ratioText = data.supply_demand_ratio !== null ? data.supply_demand_ratio : '-';
            const ratioClass = data.supply_demand_ratio > 2 ? 'oversupply' : data.supply_demand_ratio < 0.5 ? 'high-demand' : 'balanced';
            card += `
                <div class="enhanced-row">
                    <span class="enhanced-label">供需比</span>
                    <span class="enhanced-value ${ratioClass}">${ratioText}</span>
                    <span class="enhanced-detail">卖 ${data.supply_count} / 收 ${data.demand_count}</span>
                </div>`;
        }
        if (data.history_high !== undefined) {
            card += `
                <div class="enhanced-row">
                    <span class="enhanced-label">历史范围</span>
                    <span class="enhanced-value">${data.history_low}p ~ ${data.history_high}p</span>
                    <span class="enhanced-detail">均值 ${data.history_avg}p</span>
                </div>`;
        }
        card += `</div>`;
    }

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
                        <span class="rank-value" style="color: ${rarityColor}">${safeItemTypeDisplay}</span>
                    </div>
                    <div class="rank-row">
                        <span class="rank-label">稀有度</span>
                        <span class="rank-value" style="color: ${rarityColor}">${escapeHtml(rarityText)}</span>
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

    if (data.rank0_sell_price !== undefined && data.rank0_sell_price !== null) {
        card += `<div class="item-detail-extra buy-plan-card">`;
        card += `<div class="buy-plan-title">赋能/Mod 价格对比</div>`;
        card += `<div class="buy-plan-entries">`;
        card += `<div class="buy-plan-entry"><span class="bp-seller">零散（rank 0）</span> <span class="bp-price">${data.rank0_sell_price}p</span></div>`;
        card += `<div class="buy-plan-entry"><span class="bp-seller">满级（rank ${data.max_rank}）</span> <span class="bp-price">${data.max_rank_sell_price || '-'}p</span></div>`;
        card += `</div>`;
        card += `</div>`;
    }

    card += `
            <div class="item-detail-actions">
                <button class="detail-action-btn" onclick="copyToClipboard('${jsWhisperSell}')">
                    复制购买私聊
                </button>
                <button class="detail-action-btn" onclick="copyToClipboard('${jsWhisperBuy}')">
                    复制出售私聊
                </button>
                <button class="detail-action-btn" onclick="addFavorite('${jsItemId}').then(() => { showToast('已收藏', 'success'); loadSidebar(); })">
                    收藏
                </button>
                <button class="detail-action-btn share-btn" onclick="shareItemCard('${jsItemId}', '${jsDisplay}', ${data.sell_price || 'null'}, ${data.buy_price || 'null'}, ${data.spread || 'null'})">
                    分享
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
        const sellMin = sellPrices.reduce((a, b) => a < b ? a : b);
        const sellMax = sellPrices.reduce((a, b) => a > b ? a : b);
        stats.push(`
            <div class="stat-item"><div class="stat-label">平均卖价</div><div class="stat-value">${avg}p</div></div>
            <div class="stat-item"><div class="stat-label">最低卖价</div><div class="stat-value min">${sellMin}p</div></div>
            <div class="stat-item"><div class="stat-label">最高卖价</div><div class="stat-value max">${sellMax}p</div></div>
        `);
    }

    if (buyPrices.length > 0) {
        const avg = Math.round(buyPrices.reduce((a, b) => a + b, 0) / buyPrices.length);
        const buyMin = buyPrices.reduce((a, b) => a < b ? a : b);
        const buyMax = buyPrices.reduce((a, b) => a > b ? a : b);
        stats.push(`
            <div class="stat-item"><div class="stat-label">平均收价</div><div class="stat-value">${avg}p</div></div>
            <div class="stat-item"><div class="stat-label">最低收价</div><div class="stat-value min">${buyMin}p</div></div>
            <div class="stat-item"><div class="stat-label">最高收价</div><div class="stat-value max">${buyMax}p</div></div>
        `);
    }

    return stats.length > 0 ? `<div class="stats-grid">${stats.join('')}</div>` : '';
}

// ===== 状态模板 =====

// ===== 关闭面板（handler moved to app.js） =====

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
        position: relative;
        overflow: hidden;
    }

    .item-detail-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 2px;
        background: linear-gradient(90deg, var(--gold-primary), var(--blue-primary), var(--gold-primary));
        background-size: 200% 100%;
        animation: gradientFlow 4s ease infinite;
        opacity: 0.7;
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

    .price-block.sell .price-value { color: var(--red-error); text-shadow: 0 0 8px rgba(239, 68, 68, 0.4); }
    .price-block.buy .price-value { color: var(--green-success); text-shadow: 0 0 8px rgba(74, 222, 128, 0.4); }
    .price-block.spread .price-value { color: var(--gold-primary); text-shadow: 0 0 8px rgba(212, 167, 55, 0.4); }
    .price-block.spread.positive .price-value { color: var(--green-success); text-shadow: 0 0 8px rgba(74, 222, 128, 0.4); }
    .price-block.spread.negative .price-value { color: var(--red-error); text-shadow: 0 0 8px rgba(239, 68, 68, 0.4); }

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
        box-shadow: var(--glow-blue-ring);
    }

    .detail-action-btn.share-btn {
        background: rgba(212, 167, 55, 0.1);
        border-color: rgba(212, 167, 55, 0.25);
        color: var(--gold-primary);
    }

    .detail-action-btn.share-btn:hover {
        background: rgba(212, 167, 55, 0.2);
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
        box-shadow: var(--glow-gold-ring);
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

    /* 多物品对比样式 */
    .compare-container {
        padding: 16px;
    }

    .compare-header {
        margin-bottom: 16px;
    }

    .compare-title {
        font-family: var(--font-display);
        font-size: 16px;
        color: var(--gold-primary);
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }

    .compare-items-selector {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-bottom: 16px;
    }

    .compare-item-row {
        display: flex;
        gap: 8px;
        align-items: center;
    }

    .compare-item-input {
        flex: 1;
        padding: 8px 12px;
        background: rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        color: var(--text-primary);
        font-size: 13px;
        font-family: var(--font-body);
    }

    .compare-item-input:focus {
        outline: none;
        border-color: rgba(212, 167, 55, 0.3);
    }

    .compare-remove-btn {
        width: 28px;
        height: 28px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 6px;
        color: var(--red-error);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
    }

    .compare-remove-btn:hover {
        background: rgba(239, 68, 68, 0.2);
    }

    .compare-add-btn {
        padding: 8px 16px;
        background: rgba(74, 158, 255, 0.1);
        border: 1px solid rgba(74, 158, 255, 0.2);
        border-radius: 6px;
        color: var(--blue-primary);
        cursor: pointer;
        font-size: 12px;
        transition: all 0.2s;
    }

    .compare-add-btn:hover {
        background: rgba(74, 158, 255, 0.2);
    }

    .compare-actions {
        display: flex;
        gap: 8px;
        margin-bottom: 16px;
    }

    .compare-range-selector {
        display: flex;
        gap: 4px;
    }

    .compare-range-btn {
        padding: 4px 10px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 4px;
        color: var(--text-secondary);
        cursor: pointer;
        font-size: 11px;
        transition: all 0.2s;
    }

    .compare-range-btn.active {
        background: rgba(212, 167, 55, 0.15);
        border-color: rgba(212, 167, 55, 0.3);
        color: var(--gold-primary);
    }

    .compare-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 12px;
        padding: 8px;
        background: rgba(0, 0, 0, 0.15);
        border-radius: 6px;
    }

    .compare-legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        color: var(--text-secondary);
    }

    .compare-legend-color {
        width: 12px;
        height: 3px;
        border-radius: 2px;
    }

    .trend-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-family: var(--font-mono);
        font-size: 11px;
        font-weight: 600;
        margin-left: 8px;
        vertical-align: middle;
    }
    .trend-up { background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }
    .trend-down { background: rgba(74, 222, 128, 0.15); color: #4ade80; border: 1px solid rgba(74, 222, 128, 0.3); }
    .trend-stable { background: rgba(255, 255, 255, 0.05); color: var(--text-tertiary); border: 1px solid rgba(255, 255, 255, 0.1); }

    .item-enhanced-info {
        background: rgba(74, 158, 255, 0.04);
        border: 1px solid rgba(74, 158, 255, 0.12);
        border-radius: 4px;
        padding: 8px 10px;
        margin: 8px 0;
    }
    .enhanced-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 3px 0;
    }
    .enhanced-label {
        font-size: 11px;
        color: var(--text-tertiary);
        min-width: 50px;
    }
    .enhanced-value {
        font-family: var(--font-mono);
        font-size: 12px;
        font-weight: 600;
        color: var(--text-primary);
    }
    .enhanced-value.oversupply { color: var(--blue-primary); }
    .enhanced-value.high-demand { color: var(--red-error); }
    .enhanced-value.balanced { color: var(--text-secondary); }
    .enhanced-detail {
        font-size: 10px;
        color: var(--text-tertiary);
        margin-left: auto;
    }
`;
document.head.appendChild(chartStyles);

// ===== 多物品价格对比 =====

const COMPARE_COLORS = [
    { line: '#4a9eff', fill: 'rgba(74, 158, 255, 0.1)' },
    { line: '#ef4444', fill: 'rgba(239, 68, 68, 0.1)' },
    { line: '#4ade80', fill: 'rgba(74, 222, 128, 0.1)' },
    { line: '#f59e0b', fill: 'rgba(245, 158, 11, 0.1)' },
    { line: '#a855f7', fill: 'rgba(168, 85, 247, 0.1)' },
];

let compareChart = null;
let compareItemIds = ['', ''];
let compareRange = '7d';

function showComparePanel() {
    openDetailPanel();
    renderCompareUI();
}

function getCompareItemIds() {
    return Array.isArray(window.compareItemIds) ? window.compareItemIds : compareItemIds;
}

function setCompareItemIds(items) {
    compareItemIds = items;
    window.compareItemIds = compareItemIds;
}

setCompareItemIds(compareItemIds);
window.renderCompareUI = renderCompareUI;

function renderCompareUI() {
    const content = document.getElementById('detail-content');
    if (!content) return;

    content.textContent = '';

    const container = document.createElement('div');
    container.className = 'compare-container';

    const header = document.createElement('div');
    header.className = 'compare-header';
    const title = document.createElement('div');
    title.className = 'compare-title';
    title.textContent = '价格走势对比';
    header.appendChild(title);

    const selector = document.createElement('div');
    selector.className = 'compare-items-selector';
    selector.id = 'compare-items-selector';
    const items = getCompareItemIds();

    items.forEach((item, index) => {
        const row = document.createElement('div');
        row.className = 'compare-item-row';

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'compare-item-input';
        input.placeholder = '输入物品名称...';
        input.value = item;
        input.dataset.index = String(index);
        let debounce;
        input.addEventListener('input', () => {
            onCompareInputChange(input, index);
            clearTimeout(debounce);
            debounce = setTimeout(() => showCompareSuggestions(input, index), 300);
        });

        const suggestions = document.createElement('div');
        suggestions.className = 'compare-suggestions';
        suggestions.id = `compare-suggestions-${index}`;
        suggestions.style.cssText = 'display:none; position:absolute;';

        row.append(input, suggestions);

        if (items.length > 2) {
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'compare-remove-btn';
            remove.textContent = '×';
            remove.addEventListener('click', () => removeCompareItem(index));
            row.appendChild(remove);
        }

        selector.appendChild(row);
    });

    if (items.length < 5) {
        const add = document.createElement('button');
        add.type = 'button';
        add.className = 'compare-add-btn';
        add.textContent = '+ 添加物品';
        add.addEventListener('click', addCompareItem);
        selector.appendChild(add);
    }

    const actions = document.createElement('div');
    actions.className = 'compare-actions';

    const ranges = document.createElement('div');
    ranges.className = 'compare-range-selector';
    [
        ['24h', '24h'],
        ['7d', '7天'],
        ['30d', '30天'],
    ].forEach(([value, label]) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `compare-range-btn ${compareRange === value ? 'active' : ''}`;
        btn.textContent = label;
        btn.addEventListener('click', () => setCompareRange(value));
        ranges.appendChild(btn);
    });

    const runBtn = document.createElement('button');
    runBtn.type = 'button';
    runBtn.className = 'form-btn primary';
    runBtn.style.cssText = 'flex:none; padding: 6px 16px;';
    runBtn.textContent = '对比';
    runBtn.addEventListener('click', runCompare);

    actions.append(ranges, runBtn);

    const chartArea = document.createElement('div');
    chartArea.id = 'compare-chart-area';

    container.append(header, selector, actions, chartArea);
    content.appendChild(container);
}

function addCompareItem() {
    const items = getCompareItemIds();
    if (items.length >= 5) return;
    items.push('');
    setCompareItemIds(items);
    renderCompareUI();
}

function removeCompareItem(index) {
    const items = getCompareItemIds();
    items.splice(index, 1);
    setCompareItemIds(items);
    renderCompareUI();
}

function setCompareRange(range) {
    compareRange = range;
    document.querySelectorAll('.compare-range-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent.includes(range === '24h' ? '24h' : range === '7d' ? '7天' : '30天'));
    });
}

let compareDebounce = null;
function onCompareInputChange(input, index) {
    const items = getCompareItemIds();
    items[index] = input.value;
    setCompareItemIds(items);
    clearTimeout(compareDebounce);
    compareDebounce = setTimeout(() => showCompareSuggestions(input, index), 300);
}

async function showCompareSuggestions(input, index) {
    const query = input.value.trim();
    const sugDiv = document.getElementById(`compare-suggestions-${index}`);
    if (!sugDiv || query.length < 1) {
        if (sugDiv) sugDiv.style.display = 'none';
        return;
    }

    try {
        const res = await fetch(`/api/suggest?q=${encodeURIComponent(query)}`);
        if (!res.ok) return;
        const data = await res.json();
        if (!data.suggestions || data.suggestions.length === 0) {
            sugDiv.style.display = 'none';
            return;
        }

        sugDiv.textContent = '';
        data.suggestions.forEach(suggestion => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.textContent = suggestion;
            item.addEventListener('click', () => selectCompareItem(index, suggestion));
            sugDiv.appendChild(item);
        });
        sugDiv.style.cssText = 'display:block; position:absolute; background:var(--glass-bg); border:var(--glass-border); border-radius:8px; max-height:150px; overflow-y:auto; z-index:10; width:100%;';
    } catch (e) {
        sugDiv.style.display = 'none';
    }
}

function selectCompareItem(index, itemId) {
    const items = getCompareItemIds();
    items[index] = itemId;
    setCompareItemIds(items);
    const input = document.querySelector(`.compare-item-input[data-index="${index}"]`);
    if (input) input.value = itemId;
    const sugDiv = document.getElementById(`compare-suggestions-${index}`);
    if (sugDiv) sugDiv.style.display = 'none';
}

async function runCompare() {
    const validItems = getCompareItemIds().filter(i => i.trim() !== '');
    if (validItems.length < 2) {
        showToast('请至少输入2个物品', 'warning');
        return;
    }

    const chartArea = document.getElementById('compare-chart-area');
    chartArea.innerHTML = createChartLoading();

    try {
        const res = await fetch('/api/history/compare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ item_ids: validItems, range: compareRange })
        });
        if (!res.ok) {
            chartArea.innerHTML = '<div class="chart-empty"><p>查询失败</p></div>';
            return;
        }
        const data = await res.json();

        if (!data.items || Object.keys(data.items).length === 0) {
            chartArea.innerHTML = '<div class="chart-empty"><p>无数据可对比</p></div>';
            return;
        }

        renderCompareChart(data);
    } catch (err) {
        chartArea.innerHTML = createChartError('对比请求失败');
    }
}

function renderCompareChart(data) {
    const chartArea = document.getElementById('compare-chart-area');
    if (!chartArea) return;

    chartArea.textContent = '';
    const chartContainer = document.createElement('div');
    chartContainer.className = 'chart-container';
    chartContainer.style.height = '300px';

    const canvas = document.createElement('canvas');
    canvas.id = 'compare-chart';
    chartContainer.appendChild(canvas);

    const legend = document.createElement('div');
    legend.className = 'compare-legend';
    legend.id = 'compare-legend';

    chartArea.append(chartContainer, legend);

    const ctx = document.getElementById('compare-chart');
    if (!ctx) return;

    if (compareChart) {
        compareChart.destroy();
    }

    const datasets = [];
    const legendItems = [];
    let colorIndex = 0;

    Object.entries(data.items).forEach(([itemId, itemData]) => {
        if (!itemData.snapshots || itemData.snapshots.length === 0) return;

        const color = COMPARE_COLORS[colorIndex % COMPARE_COLORS.length];
        const labels = itemData.snapshots.map(s => s.timestamp).reverse();
        const sellPrices = itemData.snapshots.map(s => s.sell_price).reverse();

        datasets.push({
            label: itemData.display || itemId,
            data: sellPrices,
            borderColor: color.line,
            backgroundColor: color.fill,
            borderWidth: 2,
            pointRadius: 2,
            pointHoverRadius: 4,
            tension: 0.4,
            fill: false
        });

        legendItems.push({ name: itemData.display || itemId, color: color.line });
        colorIndex++;
    });

    if (datasets.length === 0) {
        chartArea.innerHTML = '<div class="chart-empty"><p>所选物品无历史数据</p></div>';
        return;
    }

    // 使用第一个物品的时间戳作为标签
    const firstItem = Object.values(data.items).find(i => i.snapshots && i.snapshots.length > 0);
    const labels = firstItem ? firstItem.snapshots.map(s => formatDate(s.timestamp)).reverse() : [];

    compareChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: { labels, datasets },
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

    // 渲染图例
    const legendDiv = document.getElementById('compare-legend');
    if (legendDiv) {
        legendDiv.textContent = '';
        legendItems.forEach(item => {
            const row = document.createElement('div');
            row.className = 'compare-legend-item';

            const color = document.createElement('div');
            color.className = 'compare-legend-color';
            color.style.background = item.color;

            const name = document.createElement('span');
            name.textContent = item.name;

            row.append(color, name);
            legendDiv.appendChild(row);
        });
    }
}

// ===== 社交分享 - 生成价格卡片图片 =====

async function shareItemCard(itemId, displayName, sellPrice, buyPrice, spread) {
    try {
        const canvas = document.createElement('canvas');
        const W = 600, H = 320;
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');

        // 背景
        const grad = ctx.createLinearGradient(0, 0, W, H);
        grad.addColorStop(0, '#0c1020');
        grad.addColorStop(1, '#1a1040');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);

        // 边框
        ctx.strokeStyle = 'rgba(212, 167, 55, 0.4)';
        ctx.lineWidth = 2;
        roundRect(ctx, 4, 4, W - 8, H - 8, 16);
        ctx.stroke();

        // 顶部装饰线
        ctx.fillStyle = 'rgba(212, 167, 55, 0.6)';
        ctx.fillRect(40, 60, W - 80, 1);

        // 标题
        ctx.fillStyle = '#d4a737';
        ctx.font = 'bold 14px sans-serif';
        ctx.fillText('WARFRAME 交易助手', 40, 42);

        // 物品名
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 28px sans-serif';
        const name = displayName.length > 20 ? displayName.substring(0, 20) + '...' : displayName;
        ctx.fillText(name, 40, 105);

        // 价格区域
        const priceY = 150;
        // 卖价
        ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
        roundRect(ctx, 40, priceY, 150, 80, 10);
        ctx.fill();
        ctx.fillStyle = '#888';
        ctx.font = '12px sans-serif';
        ctx.fillText('最低卖价', 55, priceY + 25);
        ctx.fillStyle = '#ef4444';
        ctx.font = 'bold 24px sans-serif';
        ctx.fillText(sellPrice !== null ? sellPrice + 'p' : '暂无', 55, priceY + 58);

        // 收价
        ctx.fillStyle = 'rgba(74, 222, 128, 0.15)';
        roundRect(ctx, 210, priceY, 150, 80, 10);
        ctx.fill();
        ctx.fillStyle = '#888';
        ctx.font = '12px sans-serif';
        ctx.fillText('最高收价', 225, priceY + 25);
        ctx.fillStyle = '#4ade80';
        ctx.font = 'bold 24px sans-serif';
        ctx.fillText(buyPrice !== null ? buyPrice + 'p' : '暂无', 225, priceY + 58);

        // 价差
        ctx.fillStyle = 'rgba(74, 158, 255, 0.15)';
        roundRect(ctx, 380, priceY, 150, 80, 10);
        ctx.fill();
        ctx.fillStyle = '#888';
        ctx.font = '12px sans-serif';
        ctx.fillText('价差', 395, priceY + 25);
        ctx.fillStyle = '#4a9eff';
        ctx.font = 'bold 24px sans-serif';
        ctx.fillText(spread !== null ? spread + 'p' : '-', 395, priceY + 58);

        // 底部
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.fillRect(40, H - 60, W - 80, 1);
        ctx.fillStyle = '#666';
        ctx.font = '11px sans-serif';
        const now = new Date();
        ctx.fillText(`生成时间: ${now.toLocaleDateString('zh-CN')} ${now.toLocaleTimeString('zh-CN')}`, 40, H - 30);
        ctx.fillText('warframe.trade', W - 120, H - 30);

        // 尝试复制到剪贴板
        if (navigator.clipboard && window.ClipboardItem) {
            const blob = await new Promise(r => canvas.toBlob(r, 'image/png'));
            await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
            showToast('价格卡片已复制到剪贴板', 'success');
        } else {
            // 降级：下载图片
            const link = document.createElement('a');
            link.download = `warframe-${itemId}-price.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
            showToast('价格卡片已下载', 'success');
        }
    } catch (e) {
        showToast('分享失败: ' + e.message, 'error');
    }
}

function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}
