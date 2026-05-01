const API_BASE = '';

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
    await fetch(`${API_BASE}/api/fav`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId })
    });
}

async function removeFavorite(itemId) {
    await fetch(`${API_BASE}/api/fav`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId })
    });
}

async function addAlert(itemId, direction, price) {
    await fetch(`${API_BASE}/api/alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, direction, price })
    });
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

function showNotification(message) {
    if (Notification.permission === 'granted') {
        new Notification('Warframe 交易提醒', { body: message });
    }
}

if (Notification.permission === 'default') {
    Notification.requestPermission();
}

document.addEventListener('DOMContentLoaded', () => {
    loadSidebar();
    setupWebSocket();
    checkFirstVisit();
});

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
        await fetch(`${API_BASE}/api/pref`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: 'platform', value: selectedPlatform })
        });
        localStorage.setItem('warframe_visited', 'true');
        modal.classList.remove('active');
        addChatMessage('system', `已设置平台为 ${selectedPlatform.toUpperCase()}，开始使用吧！`);
    });
}

function setupWebSocket() {
    const ws = new WebSocket(`ws://${location.host}/ws/notifications`);
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'alert') {
            const msg = `${data.item}: 当前 ${data.current_price}p (${data.direction} ${data.price}p)`;
            showNotification(msg);
            addChatMessage('system', msg);
        }
    };
}
