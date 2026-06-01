/* ============================================
   Warframe Trading Agent - Chat Module
   Tenno 科技终端对话模块 v3.0
   ============================================ */

// ===== DOM 元素（用 var 保证全局作用域，onclick 内联处理器可访问） =====
var chatMessages = document.getElementById('chat-messages');
var chatInput = document.getElementById('chat-input');
var sendBtn = document.getElementById('send-btn');
var suggestionsDiv = document.getElementById('suggestions');
// 显式挂到 window，防止缓存旧版本（const）导致跨文件访问失败
window.chatInput = chatInput;

// ===== 状态变量 =====
let debounceTimer;
let isTyping = false;
let chatWs = null;
let currentStreamMsg = null;
let chatReconnectDelay = 1000;
let wsReconnectTimer = null;

// ===== Markdown 配置 =====
if (typeof marked !== 'undefined') {
    marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false
    });
}

function stripUnsafeInlineHtml(text) {
    return String(text || '')
        .replace(/<\s*(script|style|iframe|object|embed|img)\b[^>]*>/gi, '')
        .replace(/<\s*\/\s*(script|style|iframe|object|embed)\s*>/gi, '');
}

function safeChatRawText(text) {
    return stripUnsafeInlineHtml(text);
}

function renderMarkdown(text) {
    const safeText = safeChatRawText(text);
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        try {
            const html = marked.parse(safeText);
            return DOMPurify.sanitize(html, {
                FORBID_TAGS: ['img'],
                FORBID_ATTR: ['onerror', 'onload', 'onclick', 'data-xss']
            });
        } catch (e) {
            return escapeHtml(safeText);
        }
    }
    return escapeHtml(safeText).replace(/\n/g, '<br>');
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
            const raw = content.getAttribute('data-raw');
            messages.push({ role, text: raw || content.textContent || content.innerText });
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
        const safeText = safeChatRawText(text);
        content.setAttribute('data-raw', safeText);
        content.innerHTML = renderMarkdown(safeText);
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

        // 评分按钮
        const ratingDiv = document.createElement('div');
        ratingDiv.className = 'msg-rating';
        for (let i = 1; i <= 5; i++) {
            const star = document.createElement('button');
            star.className = 'rating-star';
            star.textContent = '★';
            star.dataset.value = i;
            star.onclick = () => {
                rateMessage(ratingDiv, i, text);
            };
            ratingDiv.appendChild(star);
        }
        actions.appendChild(ratingDiv);
    }

    return actions;
}

function extractItemIdFromText(text) {
    const match = text.match(/[\w]+_[\w]+/);
    return match ? match[0] : null;
}

// ===== 私聊命令检测与高亮 =====

function detectWhisperCommands(container) {
    const whisperPattern = /\/w\s+[\w]+\s+Hi!.*?(?:buy|sell).*/gi;
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const replacements = [];

    while (walker.nextNode()) {
        const node = walker.currentNode;
        const text = node.textContent || '';
        whisperPattern.lastIndex = 0;
        const matches = Array.from(text.matchAll(whisperPattern));
        if (matches.length > 0) {
            replacements.push({ node, matches });
        }
    }

    replacements.forEach(({ node, matches }) => {
        const fragment = document.createDocumentFragment();
        const text = node.textContent || '';
        let cursor = 0;

        matches.forEach(match => {
            const command = match[0];
            const index = match.index || 0;
            if (index > cursor) {
                fragment.appendChild(document.createTextNode(text.slice(cursor, index)));
            }
            fragment.appendChild(createWhisperCommand(command));
            cursor = index + command.length;
        });

        if (cursor < text.length) {
            fragment.appendChild(document.createTextNode(text.slice(cursor)));
        }

        node.parentNode.replaceChild(fragment, node);
    });
}

function createWhisperCommand(text) {
    const wrapper = document.createElement('div');
    wrapper.className = 'whisper-command';

    const textDiv = document.createElement('div');
    textDiv.className = 'whisper-text';
    textDiv.textContent = text;

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'whisper-copy-btn';
    copyBtn.textContent = '复制私聊';
    copyBtn.addEventListener('click', () => copyWhisper(copyBtn));

    wrapper.append(textDiv, copyBtn);
    return wrapper;
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

// ===== 消息评分 =====

function rateMessage(ratingDiv, score, replyText) {
    const userMsg = ratingDiv.closest('.message')?.previousElementSibling;
    const userText = userMsg?.classList.contains('user')
        ? userMsg.querySelector('.message-content')?.textContent || ''
        : '';

    fetch('/api/rate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: userText,
            reply: replyText,
            rating: score,
            session_id: ''
        })
    }).then(() => {
        ratingDiv.classList.add('rated');
        ratingDiv.querySelectorAll('.rating-star').forEach(star => {
            const val = parseInt(star.dataset.value);
            star.classList.toggle('active', val <= score);
            star.disabled = true;
        });
        showToast(`已评分 ${score}/5`, 'success');
    }).catch(() => {
        showToast('评分失败', 'error');
    });
}

// ===== 打字机效果 =====

function typewriterEffect(element, text) {
    if (isTyping) return;
    isTyping = true;
    const rendered = renderMarkdown(text);
    element.innerHTML = rendered;
    detectWhisperCommands(element);
    isTyping = false;
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function scrollMessageIntoView(messageEl) {
    if (!messageEl) {
        scrollToBottom();
        return;
    }

    const containerRect = chatMessages.getBoundingClientRect();
    const messageRect = messageEl.getBoundingClientRect();
    const overshoot = messageRect.bottom - containerRect.bottom;

    if (overshoot > 0) {
        chatMessages.scrollTop += overshoot + 12;
    }
}

// ===== WebSocket 流式对话 =====

function getChatErrorMessage(data, fallback = '错误: 请求处理失败') {
    if (!data || typeof data !== 'object') return '';
    if (data.ok !== false && data.status !== 'error' && !data.error) return '';
    const message = data.display_error || data.message || data.detail || data.error || fallback;
    return String(message);
}

function renderCurrentStreamError(message) {
    if (!currentStreamMsg) return;
    const content = currentStreamMsg.querySelector('.message-content');
    if (content) {
        content.setAttribute('data-raw', safeChatRawText(message));
        content.textContent = message;
    }
    scrollMessageIntoView(currentStreamMsg);
    isTyping = false;
    currentStreamMsg = null;
    saveChatHistory();
}

function chatWsState(name, fallback) {
    return typeof WebSocket !== 'undefined' && typeof WebSocket[name] === 'number'
        ? WebSocket[name]
        : fallback;
}

function isChatWsOpen(ws) {
    return Boolean(ws && ws.readyState === chatWsState('OPEN', 1));
}

function isChatWsConnecting(ws) {
    return Boolean(ws && ws.readyState === chatWsState('CONNECTING', 0));
}

function isChatWsClosed(ws) {
    return Boolean(ws && ws.readyState === chatWsState('CLOSED', 3));
}

function ensureChatWs() {
    if (chatWs && (isChatWsOpen(chatWs) || isChatWsConnecting(chatWs))) return chatWs;

    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    chatWs = new WebSocket(`${wsProto}//${location.host}/ws/chat`);

    chatWs.onopen = () => {
        console.log('Chat WebSocket 已连接');
        chatReconnectDelay = 1000;
    };

    chatWs.onmessage = (event) => {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            console.warn('WebSocket 消息解析失败:', e);
            return;
        }

        const errorMessage = getChatErrorMessage(data);
        if (errorMessage) {
            renderCurrentStreamError(errorMessage);
            return;
        }

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
                const updated = safeChatRawText(current + data.token);
                content.setAttribute('data-raw', updated);
                content.innerHTML = renderMarkdown(updated);
            }
            scrollMessageIntoView(currentStreamMsg);
            return;
        }

        if (data.done && currentStreamMsg) {
            const content = currentStreamMsg.querySelector('.message-content');
            if (content) {
                // 检测物品未找到
                const query = currentStreamMsg.getAttribute('data-query') || '';
                const reply = typeof data.reply === 'string' ? data.reply : '';
                if (isItemNotFoundResponse(reply) && query) {
                    currentStreamMsg.remove();
                    showItemNotFound(query);
                } else {
                    const safeReply = safeChatRawText(reply);
                    content.setAttribute('data-raw', safeReply);
                    content.innerHTML = renderMarkdown(safeReply);
                    detectWhisperCommands(content);
                }
            }
            isTyping = false;
            currentStreamMsg = null;
            saveChatHistory();
            return;
        }

        const directReply = typeof data.reply === 'string' ? data.reply : '';
        if (directReply && currentStreamMsg) {
            const content = currentStreamMsg.querySelector('.message-content');
            if (content) {
                const query = currentStreamMsg.getAttribute('data-query') || '';
                if (isItemNotFoundResponse(directReply) && query) {
                    currentStreamMsg.remove();
                    showItemNotFound(query);
                } else {
                    const safeReply = safeChatRawText(directReply);
                    content.setAttribute('data-raw', safeReply);
                    content.innerHTML = renderMarkdown(safeReply);
                    detectWhisperCommands(content);
                }
            }
            isTyping = false;
            currentStreamMsg = null;
            saveChatHistory();
        }
    };

    chatWs.onclose = () => {
        isTyping = false;
        currentStreamMsg = null;
        console.log('Chat WebSocket 已断开，' + chatReconnectDelay + 'ms 后重连');
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = setTimeout(ensureChatWs, chatReconnectDelay);
        chatReconnectDelay = Math.min(chatReconnectDelay * 2, 30000);
    };

    chatWs.onerror = (err) => {
        console.error('Chat WebSocket 错误:', err);
    };

    return chatWs;
}

function waitForChatWsOpen(ws, timeoutMs = 300) {
    return new Promise(resolve => {
        const started = Date.now();
        const check = () => {
            if (!ws || isChatWsOpen(ws)) {
                resolve(isChatWsOpen(ws));
                return;
            }
            if (isChatWsClosed(ws) || Date.now() - started >= timeoutMs) {
                resolve(false);
                return;
            }
            setTimeout(check, 10);
        };
        check();
    });
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
        if (isChatWsConnecting(ws)) {
            await waitForChatWsOpen(ws);
        }
        if (isChatWsOpen(ws)) {
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
                            const errorMessage = getChatErrorMessage(data);
                            const reply = typeof data.reply === 'string' ? data.reply : '';
                            if (errorMessage) {
                                c.setAttribute('data-raw', safeChatRawText(errorMessage));
                                c.textContent = errorMessage;
                            } else if (isItemNotFoundResponse(reply) && q) {
                                currentStreamMsg.remove();
                                showItemNotFound(q);
                            } else {
                                const safeReply = safeChatRawText(reply);
                                c.setAttribute('data-raw', safeReply);
                                c.innerHTML = renderMarkdown(safeReply);
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
window.handleSend = handleSend;

// ===== 物品未找到检测 =====

function isItemNotFoundResponse(text) {
    if (typeof text !== 'string') return false;
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
            body: JSON.stringify({ items })
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
                body: JSON.stringify({ items: itemsToScan })
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
            showComparePanel();
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
document.getElementById('clear-chat-btn')?.addEventListener('click', () => {
    toggleMoreMenu();
    clearChatHistory();
});

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

    const nameSpan = document.createElement('span');
    nameSpan.textContent = name;
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'remove-quick-btn';
    removeBtn.title = '移除';
    removeBtn.textContent = '×';
    btn.append(nameSpan, removeBtn);

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

    list.textContent = '';
    if (aliases.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'alias-empty';
        empty.textContent = '暂无自定义别名';
        list.appendChild(empty);
        return;
    }

    aliases.forEach(alias => {
        const item = document.createElement('div');
        item.className = 'alias-item';

        const info = document.createElement('div');
        info.className = 'alias-info';

        const name = document.createElement('span');
        name.className = 'alias-name';
        name.textContent = alias.name;

        const arrow = document.createElement('span');
        arrow.className = 'alias-arrow';
        arrow.textContent = '→';

        const display = document.createElement('span');
        display.className = 'alias-display';
        display.textContent = alias.display || alias.item_id || '';

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'alias-remove-btn';
        remove.textContent = '×';
        remove.addEventListener('click', () => removeAlias(alias.name));

        info.append(name, arrow, display);
        item.append(info, remove);
        list.appendChild(item);
    });
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

        resultsDiv.textContent = '';
        if (!data.items || data.items.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'alias-search-empty';
            empty.textContent = '未找到匹配物品';
            resultsDiv.appendChild(empty);
            resultsDiv.classList.add('active');
            return;
        }

        data.items.forEach(item => {
            const el = document.createElement('div');
            el.className = 'alias-search-item';
            el.dataset.itemId = item.item_id || '';
            el.dataset.display = item.display || '';

            const display = document.createElement('span');
            display.className = 'alias-search-display';
            display.textContent = item.display || '';

            const id = document.createElement('span');
            id.className = 'alias-search-id';
            id.textContent = item.item_id || '';

            el.append(display, id);
            el.addEventListener('click', () => {
                selectAliasItem(el.dataset.itemId, el.dataset.display);
                resultsDiv.classList.remove('active');
            });
            resultsDiv.appendChild(el);
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
    toggleMoreMenu();
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

    const renderHint = (suggestions = []) => {
        content.textContent = '';

        const hint = document.createElement('div');
        hint.className = 'not-found-hint';
        hint.textContent = `未找到「${query}」`;
        content.appendChild(hint);

        if (suggestions.length > 0) {
            const title = document.createElement('div');
            title.className = 'suggestions-hint';
            title.textContent = '你是不是想找：';

            const buttons = document.createElement('div');
            buttons.className = 'suggestion-buttons';
            suggestions.forEach(suggestion => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'suggestion-btn';
                btn.textContent = suggestion.name || suggestion.item_id || '';
                btn.addEventListener('click', () => queryItemPrice(suggestion.item_id));
                buttons.appendChild(btn);
            });
            content.append(title, buttons);
        }

        const aliasHint = document.createElement('div');
        aliasHint.className = 'add-alias-hint';
        const aliasText = document.createElement('span');
        aliasText.textContent = '如果是你熟悉的叫法，可以';
        const aliasBtn = document.createElement('button');
        aliasBtn.type = 'button';
        aliasBtn.className = 'alias-link-btn';
        aliasBtn.textContent = '添加自定义别名';
        aliasBtn.addEventListener('click', () => openAliasModal(query));
        aliasHint.append(aliasText, aliasBtn);
        content.appendChild(aliasHint);
    };

    // 先尝试搜索候选
    fetch(`/api/resolve/${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => renderHint(data.suggestions || []))
        .catch(() => renderHint());

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
        box-shadow: var(--glow-gold-ring);
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
        position: relative;
        overflow: hidden;
    }

    .whisper-command::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 2px;
        background: linear-gradient(90deg, var(--blue-primary), var(--gold-primary), var(--blue-primary));
        background-size: 200% 100%;
        animation: gradientFlow 4s ease infinite;
        opacity: 0.6;
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

    .msg-rating {
        display: flex;
        gap: 2px;
        margin-top: 4px;
    }

    .msg-rating.rated {
        pointer-events: none;
    }

    .rating-star {
        background: none;
        border: none;
        cursor: pointer;
        font-size: 14px;
        color: rgba(255, 255, 255, 0.2);
        padding: 1px 2px;
        transition: color 0.15s, transform 0.15s;
        line-height: 1;
    }

    .rating-star:hover {
        color: var(--gold-primary);
        transform: scale(1.2);
    }

    .rating-star.active {
        color: var(--gold-primary);
    }

    .msg-rating.rated .rating-star:not(.active) {
        color: rgba(255, 255, 255, 0.1);
    }
`;
document.head.appendChild(chatStyles);
