/* ============================================
   Warframe Trading Agent - Chat Module
   Tenno 科技终端对话模块 v3.0
   ============================================ */

// ===== DOM 元素 =====
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const suggestionsDiv = document.getElementById('suggestions');

// ===== 状态变量 =====
let debounceTimer;
let isTyping = false;
let chatWs = null;
let currentStreamMsg = null;

// ===== Markdown 配置 =====
if (typeof marked !== 'undefined') {
    marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false
    });
}

function renderMarkdown(text) {
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        try {
            const html = marked.parse(text);
            return DOMPurify.sanitize(html);
        } catch (e) {
            return escapeHtml(text);
        }
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== 对话历史持久化 =====

const CHAT_HISTORY_KEY = 'warframe_chat_history';
const MAX_HISTORY = 50;

function saveChatHistory() {
    const messages = [];
    chatMessages.querySelectorAll('.message').forEach(msg => {
        const role = msg.classList.contains('user') ? 'user' :
                     msg.classList.contains('agent') ? 'agent' : 'system';
        const content = msg.querySelector('.message-content');
        if (content) {
            messages.push({ role, text: content.textContent || content.innerText });
        }
    });
    const recent = messages.slice(-MAX_HISTORY);
    try {
        localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(recent));
    } catch (e) {
        console.warn('保存对话历史失败:', e);
    }
}

function loadChatHistory() {
    try {
        const saved = localStorage.getItem(CHAT_HISTORY_KEY);
        if (!saved) return false;
        const messages = JSON.parse(saved);
        if (!messages || messages.length === 0) return false;

        const welcome = chatMessages.querySelector('.welcome-message');
        if (welcome) welcome.remove();

        messages.forEach(msg => {
            addChatMessage(msg.role, msg.text, false);
        });
        return true;
    } catch (e) {
        console.warn('加载对话历史失败:', e);
        return false;
    }
}

function clearChatHistory() {
    localStorage.removeItem(CHAT_HISTORY_KEY);
    chatMessages.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">⚡</div>
            <h3>Tenno，欢迎回来</h3>
            <p>输入物品名称或问题，开始交易查询</p>
        </div>
    `;
    showToast('对话已清空', 'success');
}

// ===== 消息管理 =====

function addChatMessage(role, text, animate = true) {
    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    if (!animate) msg.style.animation = 'none';

    const decoration = document.createElement('div');
    decoration.className = 'message-decoration';

    const content = document.createElement('div');
    content.className = 'message-content';

    if (role === 'agent') {
        content.innerHTML = renderMarkdown(text);
        detectWhisperCommands(content);
    } else {
        content.textContent = text;
    }

    // 消息操作菜单
    const actions = createMessageActions(role, text);
    msg.appendChild(decoration);
    msg.appendChild(content);
    msg.appendChild(actions);

    chatMessages.appendChild(msg);
    scrollToBottom();

    if (animate && role === 'agent') {
        typewriterEffect(content, text);
    }

    // 保存历史
    if (animate) {
        setTimeout(saveChatHistory, 100);
    }

    return msg;
}

function createMessageActions(role, text) {
    const actions = document.createElement('div');
    actions.className = 'message-actions';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'msg-action-btn';
    copyBtn.title = '复制';
    copyBtn.textContent = '📋';
    copyBtn.onclick = () => {
        navigator.clipboard.writeText(text).then(() => {
            showToast('已复制到剪贴板', 'success');
        }).catch(() => {
            showToast('复制失败', 'error');
        });
    };
    actions.appendChild(copyBtn);

    if (role === 'user') {
        const retryBtn = document.createElement('button');
        retryBtn.className = 'msg-action-btn';
        retryBtn.title = '重试';
        retryBtn.textContent = '🔄';
        retryBtn.onclick = () => {
            chatInput.value = text;
            handleSend();
        };
        actions.appendChild(retryBtn);
    }

    if (role === 'agent') {
        const favBtn = document.createElement('button');
        favBtn.className = 'msg-action-btn';
        favBtn.title = '收藏物品';
        favBtn.textContent = '⭐';
        favBtn.onclick = () => {
            const itemId = extractItemIdFromText(text);
            if (itemId) {
                addFavorite(itemId).then(() => {
                    showToast('已添加收藏', 'success');
                    loadSidebar();
                }).catch(() => showToast('添加收藏失败', 'error'));
            } else {
                showToast('未识别到物品ID', 'warning');
            }
        };
        actions.appendChild(favBtn);
    }

    return actions;
}

function extractItemIdFromText(text) {
    const match = text.match(/[\w]+_[\w]+/);
    return match ? match[0] : null;
}

// ===== 私聊命令检测与高亮 =====

function detectWhisperCommands(container) {
    const text = container.textContent;
    const whisperPattern = /\/w\s+[\w]+\s+Hi!.*?(?:buy|sell).*/gi;
    const matches = text.match(whisperPattern);
    if (!matches) return;

    let html = container.innerHTML;
    matches.forEach(match => {
        const escaped = match.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(escaped, 'g');
        html = html.replace(regex, `
            <div class="whisper-command">
                <div class="whisper-text">${match}</div>
                <button class="whisper-copy-btn" onclick="copyWhisper(this)">复制私聊</button>
            </div>
        `);
    });
    container.innerHTML = html;
}

function copyWhisper(btn) {
    const text = btn.parentElement.querySelector('.whisper-text').textContent;
    navigator.clipboard.writeText(text).then(() => {
        btn.textContent = '已复制 ✓';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = '复制私聊';
            btn.classList.remove('copied');
        }, 2000);
    });
}

// ===== 打字机效果 =====

function typewriterEffect(element, text) {
    if (isTyping) return;
    isTyping = true;
    element.innerHTML = '';
    let i = 0;
    const rendered = renderMarkdown(text);

    function type() {
        if (i < rendered.length) {
            const chunk = rendered.substring(0, i + 1);
            element.innerHTML = chunk;
            i++;
            setTimeout(type, 8);
        } else {
            element.innerHTML = rendered;
            detectWhisperCommands(element);
            isTyping = false;
        }
    }
    type();
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ===== WebSocket 流式对话 =====

function ensureChatWs() {
    if (chatWs && chatWs.readyState === WebSocket.OPEN) return chatWs;

    chatWs = new WebSocket(`ws://${location.host}/ws/chat`);

    chatWs.onopen = () => {
        console.log('Chat WebSocket 已连接');
    };

    chatWs.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.status === 'processing') {
            if (currentStreamMsg) {
                const loading = currentStreamMsg.querySelector('.loading');
                if (loading) loading.remove();
            }
            return;
        }

        if (data.token && currentStreamMsg) {
            const content = currentStreamMsg.querySelector('.message-content');
            if (content) {
                const current = content.getAttribute('data-raw') || '';
                const updated = current + data.token;
                content.setAttribute('data-raw', updated);
                content.innerHTML = renderMarkdown(updated);
            }
            scrollToBottom();
            return;
        }

        if (data.done && currentStreamMsg) {
            const content = currentStreamMsg.querySelector('.message-content');
            if (content) {
                // 检测物品未找到
                const query = currentStreamMsg.getAttribute('data-query') || '';
                if (isItemNotFoundResponse(data.reply) && query) {
                    currentStreamMsg.remove();
                    showItemNotFound(query);
                } else {
                    content.innerHTML = renderMarkdown(data.reply);
                    detectWhisperCommands(content);
                }
            }
            isTyping = false;
            currentStreamMsg = null;
            saveChatHistory();
            return;
        }

        if (data.reply && currentStreamMsg) {
            const content = currentStreamMsg.querySelector('.message-content');
            if (content) {
                const query = currentStreamMsg.getAttribute('data-query') || '';
                if (isItemNotFoundResponse(data.reply) && query) {
                    currentStreamMsg.remove();
                    showItemNotFound(query);
                } else {
                    content.innerHTML = renderMarkdown(data.reply);
                    detectWhisperCommands(content);
                }
            }
            isTyping = false;
            currentStreamMsg = null;
            saveChatHistory();
        }
    };

    chatWs.onclose = () => {
        console.log('Chat WebSocket 已断开');
        setTimeout(ensureChatWs, 3000);
    };

    chatWs.onerror = (err) => {
        console.error('Chat WebSocket 错误:', err);
    };

    return chatWs;
}

// ===== 发送消息 =====

async function handleSend() {
    const message = chatInput.value.trim();
    if (!message || isTyping) return;

    addChatMessage('user', message);
    chatInput.value = '';
    suggestionsDiv.classList.remove('active');

    // 创建流式消息容器
    const msg = document.createElement('div');
    msg.className = 'message agent';

    const decoration = document.createElement('div');
    decoration.className = 'message-decoration';

    const content = document.createElement('div');
    content.className = 'message-content';
    content.setAttribute('data-raw', '');
    content.innerHTML = '<div class="loading"><div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div></div>';

    const actions = createMessageActions('agent', '');
    msg.appendChild(decoration);
    msg.appendChild(content);
    msg.appendChild(actions);
    chatMessages.appendChild(msg);
    scrollToBottom();

    currentStreamMsg = msg;
    currentStreamMsg.setAttribute('data-query', message);
    isTyping = true;

    try {
        const ws = ensureChatWs();
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ message }));
        } else {
            // 回退到 REST
            setTimeout(async () => {
                try {
                    const data = await sendChat(message);
                    if (currentStreamMsg) {
                        const c = currentStreamMsg.querySelector('.message-content');
                        const q = currentStreamMsg.getAttribute('data-query') || '';
                        if (c) {
                            if (isItemNotFoundResponse(data.reply) && q) {
                                currentStreamMsg.remove();
                                showItemNotFound(q);
                            } else {
                                c.innerHTML = renderMarkdown(data.reply);
                                detectWhisperCommands(c);
                            }
                        }
                    }
                } catch (err) {
                    if (currentStreamMsg) {
                        const c = currentStreamMsg.querySelector('.message-content');
                        if (c) c.textContent = '错误: 无法连接到服务器';
                    }
                }
                isTyping = false;
                currentStreamMsg = null;
                saveChatHistory();
            }, 500);
        }
    } catch (err) {
        isTyping = false;
        currentStreamMsg = null;
        addChatMessage('system', '错误: 无法连接到服务器，请检查网络或重启服务');
    }
}

// ===== 物品未找到检测 =====

function isItemNotFoundResponse(text) {
    const patterns = ['没有找到', '未找到', '找不到', '无法找到', '未识别', '不认识'];
    return patterns.some(p => text.includes(p)) && text.includes('物品');
}

// ===== 搜索建议 =====

async function fetchSuggestions(query) {
    if (!query || query.length < 1) {
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
    if (!items || items.length === 0) {
        suggestionsDiv.classList.remove('active');
        return;
    }

    suggestionsDiv.innerHTML = '';

    items.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'suggestion-item';
        div.textContent = item;
        div.style.animationDelay = `${index * 50}ms`;

        div.addEventListener('click', () => {
            chatInput.value = item;
            suggestionsDiv.classList.remove('active');
            chatInput.focus();
        });

        suggestionsDiv.appendChild(div);
    });

    suggestionsDiv.classList.add('active');
}

// ===== 多物品对比 =====

async function handleCompare() {
    const items = prompt('输入要对比的物品名称（用逗号分隔）：');
    if (!items) return;

    const itemList = items.split(',').map(s => s.trim()).filter(s => s);
    if (itemList.length < 2) {
        addChatMessage('system', '请至少输入2个物品名称');
        return;
    }

    addChatMessage('user', `对比: ${itemList.join(', ')}`);

    const loadingMsg = createLoadingMessage();
    chatMessages.appendChild(loadingMsg);
    scrollToBottom();

    try {
        const data = await compareItems(itemList);
        chatMessages.removeChild(loadingMsg);

        let result = '**对比结果:**\n\n';
        data.items.forEach(item => {
            if (item.error) {
                result += `- ${item.name}: ${item.error}\n`;
            } else {
                result += `**${item.name}**\n`;
                result += `  - 卖价: ${formatPrice(item.sell_price)}\n`;
                result += `  - 收价: ${formatPrice(item.buy_price)}\n`;
                if (item.sell_price && item.buy_price) {
                    const spread = item.sell_price - item.buy_price;
                    result += `  - 价差: ${spread}p\n`;
                }
                result += '\n';
            }
        });

        addChatMessage('agent', result);
    } catch (err) {
        chatMessages.removeChild(loadingMsg);
        addChatMessage('system', '对比失败: ' + err.message);
    }
}

// ===== 批量查价 =====

async function handleBatchQuery() {
    const input = prompt('输入要查询的物品名称（每行一个或用逗号分隔）：');
    if (!input) return;

    // 支持逗号、换行、空格分隔
    const items = input.split(/[,\n\r]+/).map(s => s.trim()).filter(s => s.length > 0);

    if (items.length === 0) {
        addChatMessage('system', '请输入至少一个物品名称');
        return;
    }

    if (items.length === 1) {
        // 单个物品直接查询
        chatInput.value = items[0];
        handleSend();
        return;
    }

    addChatMessage('user', `批量查价: ${items.join(', ')}`);

    const loadingMsg = createLoadingMessage();
    chatMessages.appendChild(loadingMsg);
    scrollToBottom();

    try {
        const res = await fetch('/api/batch_query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(items)
        });
        const data = await res.json();
        chatMessages.removeChild(loadingMsg);

        let result = `**批量查价结果** (共 ${data.total} 个，成功 ${data.success} 个)\n\n`;

        data.items.forEach(item => {
            if (item.error) {
                result += `❌ **${item.name}**: ${item.error}\n\n`;
            } else {
                result += `📦 **${item.name}**\n`;
                result += `   卖价: ${item.sell_price !== null ? item.sell_price + 'p' : '暂无'}`;
                if (item.seller) result += ` (${item.seller})`;
                result += `\n`;
                result += `   收价: ${item.buy_price !== null ? item.buy_price + 'p' : '暂无'}`;
                if (item.buyer) result += ` (${item.buyer})`;
                result += `\n`;

                if (item.spread !== undefined && item.spread !== null) {
                    result += `   价差: ${item.spread}p\n`;
                }

                // 杜卡特信息
                if (item.ducat_value) {
                    result += `   杜卡特: ${item.ducat_value} ducats`;
                    if (item.ducat_efficiency) {
                        const eff = item.ducat_efficiency;
                        result += ` (${eff.ducats_per_plat} ducats/p)`;
                        if (eff.recommendation === 'ducat') {
                            result += ` → 建议拆杜卡特`;
                        }
                    }
                    result += `\n`;
                }

                result += `\n`;
            }
        });

        addChatMessage('agent', result);
    } catch (err) {
        chatMessages.removeChild(loadingMsg);
        addChatMessage('system', '批量查价失败: ' + err.message);
    }
}

// ===== 扫描关注 =====

async function handleScanWatchlist() {
    // 获取当前关注列表
    try {
        const res = await fetch(`${API_BASE}/api/watchlist`);
        const data = await res.json();
        const watchlist = data.watchlist || [];

        if (watchlist.length === 0) {
            // 如果没有关注项，提示用户添加
            const input = prompt('当前没有关注的物品，请输入要关注的物品名称（每行一个或用逗号分隔）：');
            if (!input) return;

            const items = input.split(/[,\n\r]+/).map(s => s.trim()).filter(s => s.length > 0);
            if (items.length === 0) return;

            // 添加到关注列表
            for (const itemName of items) {
                try {
                    // 解析物品ID
                    const resolveRes = await fetch(`/api/resolve/${encodeURIComponent(itemName)}`);
                    const resolveData = await resolveRes.json();
                    const itemId = resolveData.found ? resolveData.item_id : itemName;

                    await fetch(`${API_BASE}/api/watchlist`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            item_id: itemId,
                            item_name: itemName,
                            frequency: 'daily',
                            time: '09:00',
                            content: 'top3_buyers'
                        })
                    });
                } catch (e) {
                    console.error('添加关注失败:', itemName, e);
                }
            }

            showToast(`已添加 ${items.length} 个关注物品`, 'success');
            loadWatchlist();
            return;
        }

        // 如果有关注项，显示选择界面
        const itemNames = watchlist.map(w => w.item_name).join(', ');
        const input = prompt(`当前关注物品：${itemNames}\n\n输入要扫描的物品名称（留空扫描全部）：`);

        let itemsToScan;
        if (!input || input.trim() === '') {
            // 扫描全部
            itemsToScan = watchlist.map(w => w.item_id);
        } else {
            // 扫描指定物品
            const requested = input.split(/[,\n\r]+/).map(s => s.trim()).filter(s => s.length > 0);
            itemsToScan = requested.map(name => {
                const found = watchlist.find(w =>
                    w.item_name.toLowerCase().includes(name.toLowerCase()) ||
                    w.item_id.toLowerCase().includes(name.toLowerCase())
                );
                return found ? found.item_id : name;
            });
        }

        if (itemsToScan.length === 0) {
            addChatMessage('system', '没有找到要扫描的物品');
            return;
        }

        // 发送扫描请求
        addChatMessage('user', `扫描关注: ${itemsToScan.length} 个物品`);

        const loadingMsg = createLoadingMessage();
        chatMessages.appendChild(loadingMsg);
        scrollToBottom();

        try {
            const batchRes = await fetch('/api/batch_query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(itemsToScan)
            });
            const batchData = await batchRes.json();
            chatMessages.removeChild(loadingMsg);

            let result = `**关注扫描结果** (共 ${batchData.total} 个)\n\n`;

            batchData.items.forEach(item => {
                if (item.error) {
                    result += `❌ **${item.name}**: ${item.error}\n\n`;
                } else {
                    result += `📦 **${item.name}**\n`;
                    result += `   卖价: ${item.sell_price !== null ? item.sell_price + 'p' : '暂无'}`;
                    if (item.seller) result += ` (${item.seller})`;
                    result += `\n`;
                    result += `   收价: ${item.buy_price !== null ? item.buy_price + 'p' : '暂无'}`;
                    if (item.buyer) result += ` (${item.buyer})`;
                    result += `\n`;

                    if (item.spread !== undefined && item.spread !== null) {
                        result += `   价差: ${item.spread}p\n`;
                    }

                    result += `\n`;
                }
            });

            addChatMessage('agent', result);
        } catch (err) {
            chatMessages.removeChild(loadingMsg);
            addChatMessage('system', '扫描失败: ' + err.message);
        }
    } catch (err) {
        addChatMessage('system', '获取关注列表失败: ' + err.message);
    }
}

function createLoadingMessage() {
    const msg = document.createElement('div');
    msg.className = 'message agent loading-message';
    const loading = document.createElement('div');
    loading.className = 'loading';
    loading.innerHTML = `
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
    `;
    msg.appendChild(loading);
    return msg;
}

// ===== 事件监听 =====

sendBtn.addEventListener('click', handleSend);

chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});

chatInput.addEventListener('input', (e) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        fetchSuggestions(e.target.value);
    }, 300);
});

document.addEventListener('click', (e) => {
    if (!e.target.closest('.input-wrapper')) {
        suggestionsDiv.classList.remove('active');
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        suggestionsDiv.classList.remove('active');
        document.getElementById('detail-panel').classList.remove('active');
    }
    if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        chatInput.focus();
    }
});

// 快捷按钮
document.querySelectorAll('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        if (btn.id === 'compare-btn') {
            handleCompare();
        } else if (btn.id === 'batch-query-btn') {
            handleBatchQuery();
        } else if (btn.id === 'scan-watch-btn') {
            handleScanWatchlist();
        } else {
            chatInput.value = btn.dataset.msg;
            handleSend();
        }
    });
});

// 清空对话按钮
document.getElementById('clear-chat-btn')?.addEventListener('click', clearChatHistory);

// ===== 自定义快捷操作 =====

const CUSTOM_QUICK_KEY = 'warframe_custom_quick';

function loadCustomQuickActions() {
    try {
        const saved = localStorage.getItem(CUSTOM_QUICK_KEY);
        if (!saved) return;
        const actions = JSON.parse(saved);
        const container = document.getElementById('quick-actions');
        const addBtn = document.getElementById('add-quick-btn');
        if (!container || !addBtn) return;

        actions.forEach(action => {
            const btn = createCustomQuickBtn(action.name, action.msg);
            container.insertBefore(btn, addBtn);
        });
    } catch (e) {}
}

function createCustomQuickBtn(name, msg) {
    const btn = document.createElement('button');
    btn.className = 'quick-btn custom-quick-btn';
    btn.dataset.msg = msg;
    btn.innerHTML = `<span>${name}</span><button class="remove-quick-btn" title="移除">&times;</button>`;

    btn.addEventListener('click', (e) => {
        if (e.target.classList.contains('remove-quick-btn')) {
            btn.remove();
            saveCustomQuickActions();
            return;
        }
        chatInput.value = msg;
        handleSend();
    });

    return btn;
}

function saveCustomQuickActions() {
    const actions = [];
    document.querySelectorAll('.custom-quick-btn').forEach(btn => {
        actions.push({
            name: btn.querySelector('span').textContent,
            msg: btn.dataset.msg
        });
    });
    try {
        localStorage.setItem(CUSTOM_QUICK_KEY, JSON.stringify(actions));
    } catch (e) {}
}

document.getElementById('add-quick-btn')?.addEventListener('click', () => {
    const name = prompt('快捷按钮名称：');
    if (!name) return;
    const msg = prompt('对应的消息内容：');
    if (!msg) return;

    const container = document.getElementById('quick-actions');
    const addBtn = document.getElementById('add-quick-btn');
    const btn = createCustomQuickBtn(name, msg);
    container.insertBefore(btn, addBtn);
    saveCustomQuickActions();
    showToast('已添加快捷按钮', 'success');
});

// 初始化加载自定义快捷操作
document.addEventListener('DOMContentLoaded', loadCustomQuickActions);

// ===== 自定义别名管理 =====

let aliasSelectedItemId = null;
let aliasSearchTimer = null;

async function loadAliases() {
    try {
        const res = await fetch('/api/aliases');
        const data = await res.json();
        renderAliasList(data.aliases || []);
    } catch (e) {
        console.error('加载别名失败:', e);
    }
}

function renderAliasList(aliases) {
    const list = document.getElementById('alias-list');
    if (!list) return;

    if (aliases.length === 0) {
        list.innerHTML = '<div class="alias-empty">暂无自定义别名</div>';
        return;
    }

    list.innerHTML = aliases.map(a => `
        <div class="alias-item">
            <div class="alias-info">
                <span class="alias-name">${a.name}</span>
                <span class="alias-arrow">→</span>
                <span class="alias-display">${a.display || a.item_id}</span>
            </div>
            <button class="alias-remove-btn" onclick="removeAlias('${a.name.replace(/'/g, "\\'")}')">&times;</button>
        </div>
    `).join('');
}

async function searchItemsForAlias(query) {
    const resultsDiv = document.getElementById('alias-search-results');
    if (!resultsDiv) return;

    if (!query || query.length < 1) {
        resultsDiv.classList.remove('active');
        resultsDiv.innerHTML = '';
        return;
    }

    try {
        const res = await fetch(`/api/search_items?q=${encodeURIComponent(query)}`);
        const data = await res.json();

        if (!data.items || data.items.length === 0) {
            resultsDiv.innerHTML = '<div class="alias-search-empty">未找到匹配物品</div>';
            resultsDiv.classList.add('active');
            return;
        }

        resultsDiv.innerHTML = data.items.map(item => `
            <div class="alias-search-item" data-item-id="${item.item_id}" data-display="${escapeHtml(item.display)}">
                <span class="alias-search-display">${item.display}</span>
                <span class="alias-search-id">${item.item_id}</span>
            </div>
        `).join('');

        resultsDiv.querySelectorAll('.alias-search-item').forEach(el => {
            el.addEventListener('click', () => {
                selectAliasItem(el.dataset.itemId, el.dataset.display);
                resultsDiv.classList.remove('active');
            });
        });

        resultsDiv.classList.add('active');
    } catch (e) {
        resultsDiv.classList.remove('active');
    }
}

function selectAliasItem(itemId, display) {
    aliasSelectedItemId = itemId;
    const selectedDiv = document.getElementById('alias-selected');
    const nameSpan = document.getElementById('alias-selected-name');
    const idSpan = document.getElementById('alias-selected-id');
    const searchInput = document.getElementById('alias-search-input');
    const addBtn = document.getElementById('alias-add-btn');

    if (selectedDiv) selectedDiv.style.display = 'flex';
    if (nameSpan) nameSpan.textContent = display;
    if (idSpan) idSpan.textContent = `(${itemId})`;
    if (searchInput) searchInput.value = display;
    if (addBtn) addBtn.disabled = false;
}

function clearAliasSelection() {
    aliasSelectedItemId = null;
    const selectedDiv = document.getElementById('alias-selected');
    const searchInput = document.getElementById('alias-search-input');
    const addBtn = document.getElementById('alias-add-btn');

    if (selectedDiv) selectedDiv.style.display = 'none';
    if (searchInput) searchInput.value = '';
    if (addBtn) addBtn.disabled = true;
}

async function addAlias(name, itemId) {
    if (!name || !itemId) {
        showToast('请填写别名并选择物品', 'warning');
        return;
    }
    try {
        const res = await fetch('/api/aliases', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, item_id: itemId })
        });
        if (res.ok) {
            showToast(`已绑定: ${name} → ${itemId}`, 'success');
            loadAliases();
            clearAliasSelection();
            const nameInput = document.getElementById('alias-name-input');
            if (nameInput) nameInput.value = '';
        } else {
            showToast('添加失败', 'error');
        }
    } catch (e) {
        showToast('添加失败', 'error');
    }
}

async function removeAlias(name) {
    try {
        await fetch('/api/aliases', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        showToast('已删除别名', 'success');
        loadAliases();
    } catch (e) {
        showToast('删除失败', 'error');
    }
}

// 初始化别名面板
document.getElementById('alias-btn')?.addEventListener('click', () => {
    document.getElementById('alias-modal').classList.add('active');
    loadAliases();
});

document.getElementById('alias-search-input')?.addEventListener('input', (e) => {
    clearTimeout(aliasSearchTimer);
    aliasSearchTimer = setTimeout(() => {
        searchItemsForAlias(e.target.value.trim());
    }, 300);
});

document.getElementById('alias-search-input')?.addEventListener('focus', (e) => {
    if (e.target.value.trim().length >= 1) {
        searchItemsForAlias(e.target.value.trim());
    }
});

document.addEventListener('click', (e) => {
    if (!e.target.closest('.alias-search-wrapper')) {
        document.getElementById('alias-search-results')?.classList.remove('active');
    }
});

document.getElementById('alias-clear-btn')?.addEventListener('click', clearAliasSelection);

document.getElementById('alias-add-btn')?.addEventListener('click', () => {
    const nameInput = document.getElementById('alias-name-input');
    addAlias(nameInput.value.trim(), aliasSelectedItemId);
});

// ===== 物品未找到引导（增强版） =====

function showItemNotFound(query) {
    const msg = document.createElement('div');
    msg.className = 'message system';

    const decoration = document.createElement('div');
    decoration.className = 'message-decoration';

    const content = document.createElement('div');
    content.className = 'message-content';

    // 先尝试搜索候选
    fetch(`/api/resolve/${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => {
            let html = `<div class="not-found-hint">未找到「${escapeHtml(query)}」</div>`;

            if (data.suggestions && data.suggestions.length > 0) {
                html += '<div class="suggestions-hint">你是不是想找：</div>';
                html += '<div class="suggestion-buttons">';
                data.suggestions.forEach(s => {
                    html += `<button class="suggestion-btn" onclick="queryItemPrice('${s.item_id}')">${escapeHtml(s.name)}</button>`;
                });
                html += '</div>';
            }

            html += `
                <div class="add-alias-hint">
                    <span>如果是你熟悉的叫法，可以</span>
                    <button class="alias-link-btn" onclick="openAliasModal('${escapeHtml(query)}')">添加自定义别名</button>
                </div>
            `;

            content.innerHTML = html;
        })
        .catch(() => {
            content.innerHTML = `
                <div class="not-found-hint">未找到「${escapeHtml(query)}」</div>
                <div class="add-alias-hint">
                    <span>如果是你熟悉的叫法，可以</span>
                    <button class="alias-link-btn" onclick="openAliasModal('${escapeHtml(query)}')">添加自定义别名</button>
                </div>
            `;
        });

    msg.appendChild(decoration);
    msg.appendChild(content);
    chatMessages.appendChild(msg);
    scrollToBottom();
}

function openAliasModal(prefillName) {
    const modal = document.getElementById('alias-modal');
    const nameInput = document.getElementById('alias-name-input');
    if (modal) modal.classList.add('active');
    if (nameInput && prefillName) nameInput.value = prefillName;
    clearAliasSelection();
    loadAliases();
}

// ===== 初始化 =====

function removeWelcomeMessage() {
    const welcome = chatMessages.querySelector('.welcome-message');
    if (welcome && chatMessages.children.length > 1) {
        welcome.style.animation = 'fadeOut 0.3s ease-out forwards';
        setTimeout(() => welcome.remove(), 300);
    }
}

const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.addedNodes.length > 0) {
            removeWelcomeMessage();
        }
    });
});

observer.observe(chatMessages, { childList: true });

// 初始化 WebSocket
document.addEventListener('DOMContentLoaded', () => {
    ensureChatWs();
    loadChatHistory();
});

// ===== 样式注入 =====

const chatStyles = document.createElement('style');
chatStyles.textContent = `
    .message {
        position: relative;
    }

    .message:hover .message-actions {
        opacity: 1;
    }

    .message-actions {
        position: absolute;
        top: 4px;
        right: 8px;
        display: flex;
        gap: 4px;
        opacity: 0;
        transition: opacity 0.2s ease-out;
    }

    .message.user .message-actions {
        right: auto;
        left: 8px;
    }

    .msg-action-btn {
        width: 24px;
        height: 24px;
        border: 1px solid rgba(212, 167, 55, 0.2);
        background: rgba(7, 10, 20, 0.8);
        border-radius: 3px;
        cursor: pointer;
        font-size: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease-out;
    }

    .msg-action-btn:hover {
        background: rgba(212, 167, 55, 0.2);
        border-color: var(--gold-primary);
        transform: scale(1.1);
    }

    .whisper-command {
        margin-top: 8px;
        padding: 8px 12px;
        background: rgba(74, 158, 255, 0.08);
        border: 1px solid rgba(74, 158, 255, 0.2);
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
    }

    .whisper-text {
        font-family: var(--font-mono);
        font-size: 11px;
        color: var(--blue-primary);
        word-break: break-all;
        flex: 1;
    }

    .whisper-copy-btn {
        padding: 4px 10px;
        background: rgba(74, 158, 255, 0.15);
        border: 1px solid rgba(74, 158, 255, 0.3);
        border-radius: 3px;
        color: var(--blue-primary);
        font-size: 10px;
        cursor: pointer;
        white-space: nowrap;
        transition: all 0.2s ease-out;
        letter-spacing: 0.05em;
    }

    .whisper-copy-btn:hover {
        background: rgba(74, 158, 255, 0.25);
    }

    .whisper-copy-btn.copied {
        background: rgba(74, 222, 128, 0.15);
        border-color: rgba(74, 222, 128, 0.3);
        color: var(--green-success);
    }

    .suggestions-hint {
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 8px;
    }

    .suggestion-buttons {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }

    .suggestion-btn {
        padding: 4px 12px;
        background: rgba(74, 158, 255, 0.1);
        border: 1px solid rgba(74, 158, 255, 0.3);
        border-radius: 12px;
        color: var(--blue-primary);
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s ease-out;
    }

    .suggestion-btn:hover {
        background: rgba(74, 158, 255, 0.2);
        transform: translateY(-1px);
    }

    .message-content table {
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0;
        font-size: 12px;
    }

    .message-content th {
        background: rgba(212, 167, 55, 0.15);
        color: var(--gold-primary);
        padding: 6px 10px;
        text-align: left;
        font-family: var(--font-body);
        font-weight: 600;
        letter-spacing: 0.05em;
        border-bottom: 1px solid rgba(212, 167, 55, 0.3);
    }

    .message-content td {
        padding: 5px 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        color: var(--text-secondary);
    }

    .message-content code {
        background: rgba(74, 158, 255, 0.1);
        padding: 1px 5px;
        border-radius: 3px;
        font-family: var(--font-mono);
        font-size: 12px;
        color: var(--blue-primary);
    }

    .message-content pre {
        background: rgba(0, 0, 0, 0.3);
        padding: 10px 14px;
        border-radius: 4px;
        overflow-x: auto;
        margin: 8px 0;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }

    .message-content pre code {
        background: none;
        padding: 0;
        color: var(--text-primary);
    }

    .message-content strong {
        color: var(--gold-primary);
        font-weight: 600;
    }

    .message-content ul, .message-content ol {
        padding-left: 20px;
        margin: 4px 0;
    }

    .message-content li {
        margin: 2px 0;
    }

    .message-content a {
        color: var(--blue-primary);
        text-decoration: underline;
        text-underline-offset: 2px;
    }
`;
document.head.appendChild(chatStyles);
