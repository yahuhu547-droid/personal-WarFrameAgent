async function loadSidebar() {
    try {
        const memory = await fetchMemory();
        renderFavorites(memory.favorites);
        renderAlerts(memory.alerts);
    } catch (err) {
        console.error('加载记忆失败:', err);
    }
}

function renderFavorites(favorites) {
    const list = document.getElementById('favorites-list');
    list.innerHTML = '';
    if (favorites.length === 0) {
        list.innerHTML = '<div style="color: #666;">暂无收藏</div>';
        return;
    }
    favorites.forEach(item => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.textContent = item;
        list.appendChild(div);
    });
}

function renderAlerts(alerts) {
    const list = document.getElementById('alerts-list');
    list.innerHTML = '';
    if (alerts.length === 0) {
        list.innerHTML = '<div style="color: #666;">暂无提醒</div>';
        return;
    }
    alerts.forEach(alert => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.textContent = `${alert.item} ${alert.direction} ${alert.price}p`;
        list.appendChild(div);
    });
}
