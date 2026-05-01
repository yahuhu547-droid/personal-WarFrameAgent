const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const suggestionsDiv = document.getElementById('suggestions');

let debounceTimer;

function addChatMessage(role, text) {
    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    msg.textContent = text;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function handleSend() {
    const message = chatInput.value.trim();
    if (!message) return;

    addChatMessage('user', message);
    chatInput.value = '';
    suggestionsDiv.classList.remove('active');

    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'message agent';
    loadingMsg.innerHTML = '<span class="loading"></span>';
    chatMessages.appendChild(loadingMsg);

    try {
        const data = await sendChat(message);
        chatMessages.removeChild(loadingMsg);
        addChatMessage('agent', data.reply);
    } catch (err) {
        chatMessages.removeChild(loadingMsg);
        addChatMessage('agent', '错误: 无法连接到服务器，请检查网络或重启服务');
    }
}

async function fetchSuggestions(query) {
    if (!query) {
        suggestionsDiv.classList.remove('active');
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/suggest?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        showSuggestions(data.suggestions);
    } catch (err) {
        console.error('获取建议失败:', err);
    }
}

function showSuggestions(items) {
    if (items.length === 0) {
        suggestionsDiv.classList.remove('active');
        return;
    }
    suggestionsDiv.innerHTML = items.map(item =>
        `<div class="suggestion-item">${item}</div>`
    ).join('');
    suggestionsDiv.classList.add('active');

    document.querySelectorAll('.suggestion-item').forEach(el => {
        el.addEventListener('click', () => {
            chatInput.value = el.textContent;
            suggestionsDiv.classList.remove('active');
            chatInput.focus();
        });
    });
}

chatInput.addEventListener('input', (e) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        fetchSuggestions(e.target.value);
    }, 300);
});

sendBtn.addEventListener('click', handleSend);

chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSend();
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        suggestionsDiv.classList.remove('active');
        document.getElementById('detail-panel').classList.remove('active');
    }
});

document.querySelectorAll('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        chatInput.value = btn.dataset.msg;
        handleSend();
    });
});

document.getElementById('compare-btn').addEventListener('click', async () => {
    const items = prompt('输入要对比的物品名称（用逗号分隔）：');
    if (!items) return;

    const itemList = items.split(',').map(s => s.trim()).filter(s => s);
    if (itemList.length < 2) {
        addChatMessage('system', '请至少输入2个物品名称');
        return;
    }

    addChatMessage('user', `对比: ${itemList.join(', ')}`);

    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'message agent';
    loadingMsg.innerHTML = '<span class="loading"></span>';
    chatMessages.appendChild(loadingMsg);

    try {
        const data = await compareItems(itemList);
        chatMessages.removeChild(loadingMsg);

        let result = '对比结果:\n\n';
        data.items.forEach(item => {
            if (item.error) {
                result += `❌ ${item.name}: ${item.error}\n`;
            } else {
                result += `📦 ${item.name}\n`;
                result += `  卖价: ${item.sell_price || '无'}p\n`;
                result += `  收价: ${item.buy_price || '无'}p\n`;
                if (item.sell_price && item.buy_price) {
                    result += `  价差: ${item.sell_price - item.buy_price}p\n`;
                }
                result += '\n';
            }
        });

        addChatMessage('agent', result);
    } catch (err) {
        chatMessages.removeChild(loadingMsg);
        addChatMessage('agent', '对比失败: ' + err.message);
    }
});
