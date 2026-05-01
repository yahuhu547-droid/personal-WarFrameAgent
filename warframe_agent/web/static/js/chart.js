let priceChart = null;

async function showPriceChart(itemId) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');

    panel.classList.add('active');
    content.innerHTML = '<canvas id="price-chart"></canvas>';

    try {
        const data = await getHistory(itemId);
        renderChart(data);
    } catch (err) {
        content.innerHTML = `<p style="color: #ff6b6b;">加载失败: ${err.message}</p>`;
    }
}

function renderChart(data) {
    const ctx = document.getElementById('price-chart').getContext('2d');

    if (priceChart) {
        priceChart.destroy();
    }

    const labels = data.snapshots.map(s => new Date(s.timestamp).toLocaleDateString());
    const sellPrices = data.snapshots.map(s => s.sell_price);
    const buyPrices = data.snapshots.map(s => s.buy_price);

    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.reverse(),
            datasets: [
                {
                    label: '卖价',
                    data: sellPrices.reverse(),
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255, 107, 107, 0.1)',
                    tension: 0.3
                },
                {
                    label: '收价',
                    data: buyPrices.reverse(),
                    borderColor: '#51cf66',
                    backgroundColor: 'rgba(81, 207, 102, 0.1)',
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: '#e0e0e0' } }
            },
            scales: {
                x: { ticks: { color: '#e0e0e0' }, grid: { color: '#2a2f3f' } },
                y: { ticks: { color: '#e0e0e0' }, grid: { color: '#2a2f3f' } }
            }
        }
    });
}

document.getElementById('close-detail').addEventListener('click', () => {
    document.getElementById('detail-panel').classList.remove('active');
});
