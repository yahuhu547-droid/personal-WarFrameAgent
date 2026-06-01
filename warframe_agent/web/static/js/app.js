/* ============================================
   Warframe Trading Agent - Main Application
   Tenno 科技终端主逻辑 v3.0
   ============================================ */

const API_BASE = '';
const FUTURE_CAPABILITY_ADMISSION = 'future_capability_admission';
const FUTURE_CAPABILITY_DEFAULT_MODE = 'design_required_before_runtime';

// HTML/JS 转义工具函数
function escapeJsString(str) {
    return String(str)
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '\\"')
        .replace(/</g, '\\x3c')
        .replace(/>/g, '\\x3e');
}

// ===== API 调用函数 =====

async function fetchMemory() {
    const res = await fetch(`${API_BASE}/api/memory`);
    if (!res.ok) return { error: `HTTP ${res.status}` };
    return await res.json();
}

async function sendChat(message) {
    const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    });
    let data = {};
    try {
        data = await res.json();
    } catch (e) {
        data = {};
    }
    if (!res.ok) {
        const detail = data.detail;
        const backendMessage = data.message;
        const backendError = data.error;
        const parts = [detail, backendMessage, backendError]
            .filter(value => value !== undefined && value !== null && String(value).trim() !== '')
            .map(value => String(value));
        const displayError = parts.length ? `HTTP ${res.status}: ${parts.join(' | ')}` : `HTTP ${res.status}`;
        return {
            ok: false,
            status: res.status,
            detail,
            message: backendMessage,
            error: backendError,
            display_error: displayError
        };
    }
    return { ok: true, ...data };
}

async function addFavorite(itemId) {
    const res = await fetch(`${API_BASE}/api/fav`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId })
    });
    if (!res.ok) return { error: `HTTP ${res.status}` };
    return await res.json();
}

async function removeFavorite(itemId) {
    const res = await fetch(`${API_BASE}/api/fav`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId })
    });
    if (!res.ok) return { error: `HTTP ${res.status}` };
    return await res.json();
}

async function addAlert(itemId, direction, price, note = '') {
    const res = await fetch(`${API_BASE}/api/alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, direction, price, note })
    });
    if (!res.ok) return { error: `HTTP ${res.status}` };
    return await res.json();
}

async function removeAlertApi(itemId, direction, price) {
    const res = await fetch(`${API_BASE}/api/alert`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, direction, price })
    });
    if (!res.ok) return { error: `HTTP ${res.status}` };
    return await res.json();
}

async function compareItems(items) {
    const res = await fetch(`${API_BASE}/api/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items })
    });
    if (!res.ok) return { error: `HTTP ${res.status}` };
    return await res.json();
}

// ===== 通知系统 =====

let _audioCtx = null;
function playNotificationSound() {
    try {
        const settings = JSON.parse(localStorage.getItem('warframe_notify_settings') || '{}');
        if (settings.soundAlert === false) return;
        if (!_audioCtx || _audioCtx.state === 'closed') {
            _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        const ctx = _audioCtx;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.1);
        osc.frequency.setValueAtTime(880, ctx.currentTime + 0.2);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.4);
    } catch (e) { /* Audio not supported */ }
}

function showNotification(message, type = 'info') {
    const settings = JSON.parse(localStorage.getItem('warframe_notify_settings') || '{}');
    if (settings.browserNotify !== false && Notification.permission === 'granted') {
        new Notification('Warframe 交易提醒', {
            body: message,
            icon: '/static/favicon.ico'
        });
    }
    playNotificationSound();
    showToast(message, type);
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = typeof message === 'string' ? message : JSON.stringify(message);

    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1100;
            display: flex;
            flex-direction: column;
            gap: 8px;
        `;
        document.body.appendChild(container);
    }

    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===== 主题切换 =====

function initTheme() {
    const saved = localStorage.getItem('warframe_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';

    // 添加主题切换过渡类
    document.documentElement.classList.add('theme-transitioning');
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.classList.add('theme-rotating');

    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('warframe_theme', next);
    updateThemeIcon(next);
    showToast(`已切换为${next === 'dark' ? '暗色' : '亮色'}主题`, 'info');

    // 移除过渡类
    setTimeout(() => {
        document.documentElement.classList.remove('theme-transitioning');
        if (btn) btn.classList.remove('theme-rotating');
    }, 500);
}

function updateThemeIcon(theme) {
    const icon = document.querySelector('#theme-toggle .theme-icon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '🌙' : '☀️';
    }
}

// ===== WebSocket 连接（指数退避） =====

let wsReconnectDelay = 1000;
let runtimeStatusState = 'loading';
let lastRuntimeStatusData = null;
const WS_MAX_DELAY = 30000;
const RUNTIME_STATUS_POLL_MS = 45000;

function runtimeStatusDetail(data) {
    if (!data || typeof data !== 'object') return '';
    const parts = [];
    if (data.scheduler) parts.push(`scheduler: ${data.scheduler.running ? 'running' : 'stopped'}`);
    if (data.feishu && data.feishu.enabled) parts.push(`feishu: ${data.feishu.managed_running ? 'running' : 'stopped'}`);
    if (data.daily_report) parts.push(`daily: ${data.daily_report.enabled ? data.daily_report.report_time : 'off'}`);
    return parts.join(' | ');
}

async function refreshRuntimeStatus() {
    try {
        updateSidebarStatus('loading', '正在检查运行态');
        const res = await fetch(`${API_BASE}/api/runtime/status`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        lastRuntimeStatusData = data;
        const status = data && data.status === 'degraded' ? 'degraded' : data && data.status === 'ok' ? 'online' : 'loading';
        runtimeStatusState = status;
        updateSidebarStatus(status, runtimeStatusDetail(data));
    } catch (error) {
        console.warn('运行态状态检查失败:', error);
        runtimeStatusState = 'error';
        lastRuntimeStatusData = { status: 'error', error: String(error && error.message ? error.message : error) };
        updateSidebarStatus('error', String(error && error.message ? error.message : error));
    }
}

async function showRuntimeStatusPanel() {
    const content = openDetailPanel('加载运行态详情...');
    if (!content) return;
    try {
        const res = await fetch(`${API_BASE}/api/runtime/status`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        lastRuntimeStatusData = data;
        content.innerHTML = renderRuntimeStatusPanel(data);
    } catch (error) {
        const message = String(error && error.message ? error.message : error);
        lastRuntimeStatusData = { status: 'error', error: message };
        content.innerHTML = renderRuntimeStatusPanel(lastRuntimeStatusData);
    }
}

function renderRuntimeStatusPanel(data) {
    const scheduler = data && data.scheduler ? data.scheduler : {};
    const jobs = Array.isArray(scheduler.jobs) ? scheduler.jobs : [];
    const background = data && data.background_tasks ? data.background_tasks : {};
    const tasks = Array.isArray(background.tasks) ? background.tasks : [];
    const recentToolCalls = data && data.recent_tool_calls ? data.recent_tool_calls : {};
    const toolCalls = Array.isArray(recentToolCalls.items) ? recentToolCalls.items : [];
    const agentTrace = data && data.agent_trace ? data.agent_trace : {};
    const agentPlan = agentTrace && agentTrace.plan ? agentTrace.plan : {};
    const feishu = data && data.feishu ? data.feishu : {};
    const wxpusher = data && data.wxpusher ? data.wxpusher : {};
    const daily = data && data.daily_report ? data.daily_report : {};
    const web = data && data.web ? data.web : {};
    const learningCompletion = data && data.learning_completion ? data.learning_completion : {};
    const safetyPolicy = data && data.safety_policy ? data.safety_policy : {};
    const toolRegistry = safetyPolicy && safetyPolicy.tool_registry ? safetyPolicy.tool_registry : {};
    const gatewayPolicy = safetyPolicy && safetyPolicy.gateway_policy ? safetyPolicy.gateway_policy : {};
    const pluginPolicy = safetyPolicy && safetyPolicy.plugin_policy ? safetyPolicy.plugin_policy : {};
    const futureCapabilityPolicy = safetyPolicy && safetyPolicy.future_capability_policy ? safetyPolicy.future_capability_policy : {};
    const opsHealth = data && data.ops_health ? data.ops_health : {};
    return `
        <div class="runtime-panel">
            <div class="panel-title-row">
                <div>
                    <span class="panel-title-eyebrow">运行态详情</span>
                    <div class="trading-memory-subtitle">Web、scheduler、推送与后台任务只读状态</div>
                </div>
                <span class="badge ${data && data.status === 'ok' ? 'badge-green' : data && data.status === 'degraded' ? 'badge-gold' : 'badge-red'}">${escapeHtml(data && data.status ? data.status : 'unknown')}</span>
            </div>
            ${data && data.error ? `<div class="card runtime-card"><div class="card-body"><div class="trading-memory-message">${escapeHtml(data.error)}</div></div></div>` : ''}
            <div class="runtime-grid">
                ${renderRuntimeSummaryCard('Web', [`uptime=${web.uptime_seconds ?? '-' }s`, `started=${web.started_at ?? '-'}`])}
                ${renderRuntimeSummaryCard('Scheduler', [`running=${Boolean(scheduler.running)}`, `jobs=${scheduler.total ?? jobs.length}`])}
                ${renderRuntimeSummaryCard('Feishu', [`enabled=${Boolean(feishu.enabled)}`, `running=${Boolean(feishu.managed_running)}`])}
                ${renderRuntimeSummaryCard('WxPusher', [`enabled=${Boolean(wxpusher.enabled)}`, `configured=${Boolean(wxpusher.configured)}`, `uids=${wxpusher.uid_count ?? 0}`])}
                ${renderRuntimeSummaryCard('Daily Report', [`enabled=${Boolean(daily.enabled)}`, `time=${daily.report_time || '-'}`])}
                ${renderRuntimeSummaryCard('Learning Completion', [`status=${learningCompletion.status || '-'}`, `acceptance=${learningCompletion.acceptance_status || '-'}`, `steps=${learningCompletion.completed_step_count ?? 0}`, `improvements=${Array.isArray(learningCompletion.improvement_steps) ? learningCompletion.improvement_steps.length : 0}`])}
                ${renderRuntimeSummaryCard('Safety Policy', [`mode=${safetyPolicy.default_mode || '-'}`, `version=${safetyPolicy.policy_version || '-'}`])}
                ${renderRuntimeSummaryCard('Tool Registry', [`tools=${toolRegistry.tool_count ?? 0}`, `schemas=${toolRegistry.exposed_schema_count ?? 0}`, `side_effect=${toolRegistry.side_effect_count ?? 0}`])}
                ${renderRuntimeSummaryCard('Gateway Policy', [`mode=${gatewayPolicy.default_mode || '-'}`, `blocked=${policyDecisionCount(gatewayPolicy, 'blocked_public_or_anonymous_inbound') + policyDecisionCount(gatewayPolicy, 'blocked_sensitive_action')}`])}
                ${renderRuntimeSummaryCard('Plugin Policy', [`mode=${pluginPolicy.default_mode || '-'}`, `blocked=${policyDecisionCount(pluginPolicy, 'blocked_high_risk_capability') + policyDecisionCount(pluginPolicy, 'blocked_unknown_capability')}`])}
                ${renderRuntimeSummaryCard('Future Capability Policy', [`mode=${futureCapabilityPolicy.default_mode || FUTURE_CAPABILITY_DEFAULT_MODE}`, `runtime=${Boolean(futureCapabilityPolicy.runtime_enablement_allowed)}`, `admission=${FUTURE_CAPABILITY_ADMISSION}`, `blocked=${policyDecisionCount(futureCapabilityPolicy, 'blocked_uncontrolled_runtime')}`])}
                ${renderRuntimeSummaryCard('Ops Health', [`ops_status=${opsHealth.status || '-'}`, `reason_count=${opsHealth.reason_count ?? 0}`])}
                ${renderRuntimeSummaryCard('Background Tasks', [`running=${background.running ?? 0}`, `error=${background.error ?? 0}`, `total=${background.total ?? tasks.length}`])}
                ${renderRuntimeSummaryCard('Agent Trace', [`present=${Boolean(agentTrace.present)}`, `status=${agentTrace.status || '-'}`, `iter=${agentTrace.iterations ?? 0}/${agentTrace.max_iterations ?? '-'}`, `duration=${agentTrace.duration_ms ?? '-'}ms`])}
                ${renderRuntimeSummaryCard('Agent Plan', [`present=${Boolean(agentPlan.present)}`, `plan_status=${agentPlan.status || '-'}`, `goal_present=${Boolean(agentPlan.goal_present)}`, `plan_steps=${agentPlan.step_count ?? 0}`])}
                ${renderRuntimeSummaryCard('最近工具调用', [`count=${recentToolCalls.count ?? toolCalls.length}`])}
            </div>
            <h3 class="runtime-section-title">Ops Health</h3>
            ${renderRuntimeOpsHealth(opsHealth)}
            <h3 class="runtime-section-title">Learning Completion</h3>
            ${renderRuntimeLearningCompletion(learningCompletion)}
            <h3 class="runtime-section-title">安全策略</h3>
            ${renderRuntimeSafetyPolicy(safetyPolicy)}
            <h3 class="runtime-section-title">Gateway Policy</h3>
            ${renderRuntimeGatewayPolicy(gatewayPolicy)}
            <h3 class="runtime-section-title">Plugin Policy</h3>
            ${renderRuntimePluginPolicy(pluginPolicy)}
            <h3 class="runtime-section-title">Future Capability Policy</h3>
            ${renderRuntimeFutureCapabilityPolicy(futureCapabilityPolicy)}
            <h3 class="runtime-section-title">工具安全分布</h3>
            ${renderRuntimeToolRegistrySummary(toolRegistry)}
            <h3 class="runtime-section-title">Scheduler Jobs</h3>
            <div class="trading-memory-list">${jobs.length ? jobs.map(renderRuntimeJob).join('') : renderRuntimeEmpty('暂无任务状态')}</div>
            <h3 class="runtime-section-title">后台任务</h3>
            <div class="trading-memory-list">${tasks.length ? tasks.map(renderRuntimeTask).join('') : renderRuntimeEmpty('暂无任务状态')}</div>
            <h3 class="runtime-section-title">Agent Trace</h3>
            ${renderRuntimeAgentTrace(agentTrace)}
            <h3 class="runtime-section-title">Agent Plan</h3>
            ${renderRuntimeAgentPlan(agentPlan)}
            <h3 class="runtime-section-title">最近工具调用</h3>
            <div class="trading-memory-list">${toolCalls.length ? toolCalls.map(renderRuntimeToolCall).join('') : renderRuntimeEmpty('暂无工具调用')}</div>
        </div>
    `;
}

function renderRuntimeSummaryCard(title, lines) {
    return `<div class="card runtime-card"><div class="card-body">
        <div class="trading-memory-name">${escapeHtml(title)}</div>
        <div class="trading-memory-meta">${(lines || []).map(line => escapeHtml(line)).join('<br>')}</div>
    </div></div>`;
}

function renderRuntimeOpsHealth(opsHealth) {
    if (!opsHealth || !opsHealth.status) {
        return `<div class="trading-memory-list">${renderRuntimeEmpty('No ops health snapshot')}</div>`;
    }
    const reasons = Array.isArray(opsHealth.reasons) ? opsHealth.reasons : [];
    const components = opsHealth.components || {};
    const reasonText = reasons.length ? reasons.map(formatRuntimeSafeText).join(', ') : 'none';
    const statusClass = opsHealth.status === 'degraded' ? 'badge-gold' : opsHealth.status === 'ok' ? 'badge-green' : 'badge-muted';
    return `<div class="trading-memory-list">
        <div class="card trading-memory-record"><div class="card-body">
            <div class="trading-memory-record-header">
                <div>
                    <div class="trading-memory-name">Ops Health</div>
                    <div class="trading-memory-meta">ops_status=${escapeHtml(opsHealth.status || '-')} | reason_count=${escapeHtml(opsHealth.reason_count ?? reasons.length)}</div>
                </div>
                <span class="badge ${statusClass}">${escapeHtml(opsHealth.status || '-')}</span>
            </div>
            <div class="trading-memory-message">${escapeHtml(reasonText)}</div>
        </div></div>
        ${Object.entries(components).map(([name, component]) => renderRuntimeOpsComponent(name, component || {})).join('')}
    </div>`;
}

function renderRuntimeOpsComponent(name, component) {
    const status = component.status || '-';
    const statusClass = status === 'degraded' ? 'badge-gold' : status === 'ok' ? 'badge-green' : 'badge-muted';
    const details = Object.entries(component || {})
        .filter(([key]) => key !== 'status' && !isRuntimeSensitiveKey(key))
        .map(([key, value]) => {
            const safeValue = formatRuntimeObjectValue(value);
            if (safeValue === null || safeValue === undefined || safeValue === '') return null;
            return `${key}=${safeValue}`;
        })
        .filter(Boolean)
        .join(' | ');
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(name)}</div>
                <div class="trading-memory-meta">${escapeHtml(details || '-')}</div>
            </div>
            <span class="badge ${statusClass}">${escapeHtml(status)}</span>
        </div>
    </div></div>`;
}

function renderRuntimeLearningCompletion(snapshot) {
    if (!snapshot || !snapshot.status) {
        return `<div class="trading-memory-list">${renderRuntimeEmpty('No learning completion snapshot')}</div>`;
    }
    const acceptance = snapshot.acceptance_snapshot || {};
    const details = [
        `status=${formatRuntimeSafeText(snapshot.status || '-')}`,
        `acceptance=${formatRuntimeSafeText(snapshot.acceptance_status || '-')}`,
        `legacy_complete=${Boolean(snapshot.legacy_non_voice_learning_complete)}`,
        `improvement_complete=${Boolean(snapshot.improvement_closure_complete)}`,
        `runtime_changed=${Boolean(snapshot.runtime_enablement_changed)}`,
        `completed_steps=${snapshot.completed_step_count ?? 0}`,
        `closure_step=${formatRuntimeSafeText(acceptance.latest_closure_step || '-')}`,
        `acceptance_record=${formatRuntimeSafeText(acceptance.acceptance_record_step || '-')}`,
    ];
    const steps = Array.isArray(snapshot.completed_steps) ? snapshot.completed_steps.slice(-6) : [];
    const checklist = Array.isArray(acceptance.checklist) ? acceptance.checklist.slice(0, 8) : [];
    const nextStage = Array.isArray(snapshot.next_stage_required) ? snapshot.next_stage_required.slice(0, 8) : [];
    return `<div class="trading-memory-list">
        ${renderRuntimePolicySummary('Learning Completion', details)}
        ${steps.length ? steps.map(step => renderRuntimeLearningCompletionItem(step, 'completed')).join('') : renderRuntimeEmpty('No completed steps')}
        ${checklist.length ? checklist.map(item => renderRuntimeLearningCompletionItem(`${item.id || '-'}:${item.status || '-'}`, 'acceptance')).join('') : ''}
        ${nextStage.length ? nextStage.map(step => renderRuntimeLearningCompletionItem(step, 'next-stage')).join('') : ''}
    </div>`;
}

function renderRuntimeLearningCompletionItem(name, label) {
    const badgeClass = label === 'completed' || label === 'acceptance' ? 'badge-green' : 'badge-gold';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(formatRuntimeSafeText(name || '-'))}</div>
                <div class="trading-memory-meta">learning_completion=${escapeHtml(label)}</div>
            </div>
            <span class="badge ${badgeClass}">${escapeHtml(label)}</span>
        </div>
    </div></div>`;
}

function renderRuntimeSafetyPolicy(policy) {
    const capabilities = policy && policy.capabilities ? policy.capabilities : {};
    const entries = Object.entries(capabilities);
    if (!entries.length) return renderRuntimeEmpty('暂无安全策略快照');
    return `<div class="trading-memory-list">${entries.map(([name, cap]) => renderRuntimeSafetyCapability(name, cap || {})).join('')}</div>`;
}

function renderRuntimeSafetyCapability(name, cap) {
    const available = Boolean(cap.available);
    const enabledText = Object.prototype.hasOwnProperty.call(cap, 'enabled') ? ` · enabled=${Boolean(cap.enabled)}` : '';
    const scopeText = cap.scope ? ` · ${escapeHtml(cap.scope)}` : '';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(name)}</div>
                <div class="trading-memory-meta">default=${escapeHtml(cap.default || '-')} · requires_explicit_enable=${escapeHtml(Boolean(cap.requires_explicit_enable))}${enabledText}${scopeText}</div>
            </div>
            <span class="badge ${available ? 'badge-green' : 'badge-muted'}">${available ? 'available' : 'disabled'}</span>
        </div>
    </div></div>`;
}

function renderRuntimeGatewayPolicy(policy) {
    if (!policy || !policy.default_mode) return renderRuntimeEmpty('No gateway policy snapshot');
    const details = [
        `default=${formatRuntimeSafeText(policy.default_mode || '-')}`,
        `auto_inbound=${Boolean(policy.automatic_inbound_execution_enabled)}`,
        `anonymous_inbound=${Boolean(policy.anonymous_inbound_enabled)}`,
        `outbound_config=${Boolean(policy.outbound_push_requires_configuration)}`,
        `decisions=${formatRuntimeDistribution(policy.decision_counts || {})}`,
    ];
    const matrix = Array.isArray(policy.gateway_matrix) ? policy.gateway_matrix.slice(0, 8) : [];
    return `<div class="trading-memory-list">
        ${renderRuntimePolicySummary('Gateway Policy', details)}
        ${matrix.length ? matrix.map(item => renderRuntimeGatewayPolicyItem(item || {})).join('') : renderRuntimeEmpty('No gateway matrix')}
    </div>`;
}

function renderRuntimePluginPolicy(policy) {
    if (!policy || !policy.default_mode) return renderRuntimeEmpty('No plugin policy snapshot');
    const details = [
        `default=${formatRuntimeSafeText(policy.default_mode || '-')}`,
        `plugin_runtime=${Boolean(policy.plugin_runtime_enabled)}`,
        `connector_runtime=${Boolean(policy.connector_runtime_enabled)}`,
        `auto_install=${Boolean(policy.automatic_tool_install_enabled)}`,
        `decisions=${formatRuntimeDistribution(policy.decision_counts || {})}`,
    ];
    const matrix = Array.isArray(policy.capability_matrix) ? policy.capability_matrix.slice(0, 8) : [];
    return `<div class="trading-memory-list">
        ${renderRuntimePolicySummary('Plugin Policy', details)}
        ${matrix.length ? matrix.map(item => renderRuntimePluginPolicyItem(item || {})).join('') : renderRuntimeEmpty('No plugin matrix')}
    </div>`;
}

function renderRuntimeFutureCapabilityPolicy(policy) {
    if (!policy || !policy.default_mode) return renderRuntimeEmpty('No future capability policy snapshot');
    const details = [
        `default=${formatRuntimeSafeText(policy.default_mode || '-')}`,
        `runtime_enablement_allowed=${Boolean(policy.runtime_enablement_allowed)}`,
        `automatic_enable=${Boolean(policy.automatic_enable_enabled)}`,
        `design_review=${Boolean(policy.design_review_required)}`,
        `human_confirmation=${Boolean(policy.human_confirmation_required_before_runtime)}`,
        `decisions=${formatRuntimeDistribution(policy.decision_counts || {})}`,
    ];
    const matrix = Array.isArray(policy.capability_matrix) ? policy.capability_matrix.slice(0, 8) : [];
    return `<div class="trading-memory-list">
        ${renderRuntimePolicySummary('Future Capability Policy', details)}
        ${matrix.length ? matrix.map(item => renderRuntimeFutureCapabilityPolicyItem(item || {})).join('') : renderRuntimeEmpty('No future capability matrix')}
    </div>`;
}

function renderRuntimePolicySummary(title, details) {
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(title)}</div>
                <div class="trading-memory-meta">${escapeHtml((details || []).join(' | '))}</div>
            </div>
            <span class="badge badge-green">read-only</span>
        </div>
    </div></div>`;
}

function renderRuntimeGatewayPolicyItem(item) {
    const decision = formatRuntimeSafeText(item.decision || '-');
    const badgeClass = String(decision).startsWith('blocked') ? 'badge-red' : decision === 'requires_existing_confirmation_flow' ? 'badge-gold' : 'badge-green';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(formatRuntimeSafeText(item.channel || '-'))}</div>
                <div class="trading-memory-meta">action=${escapeHtml(formatRuntimeSafeText(item.action || '-'))} | trust=${escapeHtml(formatRuntimeSafeText(item.trust_boundary || '-'))} | reason=${escapeHtml(formatRuntimeSafeText(item.reason || '-'))}</div>
            </div>
            <span class="badge ${badgeClass}">${escapeHtml(decision)}</span>
        </div>
    </div></div>`;
}

function renderRuntimeFutureCapabilityPolicyItem(item) {
    const decision = formatRuntimeSafeText(item.decision || '-');
    const badgeClass = String(decision).startsWith('blocked')
        ? 'badge-red'
        : decision === 'requires_new_stage_design' || decision === 'frozen_by_current_user_instruction'
            ? 'badge-gold'
            : 'badge-green';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(formatRuntimeSafeText(item.capability || '-'))}</div>
                <div class="trading-memory-meta">trust=${escapeHtml(formatRuntimeSafeText(item.trust_boundary || '-'))} | runtime_enabled=${escapeHtml(Boolean(item.runtime_enabled))} | approval=${escapeHtml(Boolean(item.requires_explicit_user_approval))} | reason=${escapeHtml(formatRuntimeSafeText(item.reason || '-'))}</div>
            </div>
            <span class="badge ${badgeClass}">${escapeHtml(decision)}</span>
        </div>
    </div></div>`;
}

function renderRuntimePluginPolicyItem(item) {
    const decision = formatRuntimeSafeText(item.decision || '-');
    const badgeClass = String(decision).startsWith('blocked') ? 'badge-red' : decision === 'requires_review' || decision === 'requires_explicit_enable' ? 'badge-gold' : 'badge-green';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(formatRuntimeSafeText(item.source || '-'))}</div>
                <div class="trading-memory-meta">capability=${escapeHtml(formatRuntimeSafeText(item.capability || '-'))} | trust=${escapeHtml(formatRuntimeSafeText(item.trust_boundary || '-'))} | reason=${escapeHtml(formatRuntimeSafeText(item.reason || '-'))}</div>
            </div>
            <span class="badge ${badgeClass}">${escapeHtml(decision)}</span>
        </div>
    </div></div>`;
}

function policyDecisionCount(policy, name) {
    const counts = policy && policy.decision_counts ? policy.decision_counts : {};
    const value = counts && Object.prototype.hasOwnProperty.call(counts, name) ? counts[name] : 0;
    return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function renderRuntimeToolRegistrySummary(summary) {
    if (!summary || !summary.tool_count) return renderRuntimeEmpty('暂无工具安全统计');
    const safetyLevels = summary.safety_levels || {};
    const skills = summary.skills || {};
    const contextPolicies = summary.context_policies || {};
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">ToolRegistry</div>
                <div class="trading-memory-meta">tools=${escapeHtml(summary.tool_count ?? 0)} · exposed_schema=${escapeHtml(summary.exposed_schema_count ?? 0)} · private_schema=${escapeHtml(summary.private_schema_count ?? 0)} · side_effect=${escapeHtml(summary.side_effect_count ?? 0)}</div>
            </div>
            <span class="badge badge-green">aggregate</span>
        </div>
        <div class="trading-memory-prices">
            <span>safety=${escapeHtml(formatRuntimeDistribution(safetyLevels))}</span>
            <span>skills=${escapeHtml(formatRuntimeDistribution(skills))}</span>
            <span>context=${escapeHtml(formatRuntimeDistribution(contextPolicies))}</span>
        </div>
    </div></div>`;
}

function formatRuntimeDistribution(value) {
    const entries = Object.entries(value || {});
    if (!entries.length) return '-';
    return entries.map(([name, count]) => `${name}:${count}`).join(', ');
}

function renderRuntimeJob(job) {
    const okClass = job.last_success === false ? 'badge-red' : job.running ? 'badge-gold' : 'badge-green';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(job.name || job.job_id || '-')}</div>
                <div class="trading-memory-meta">${escapeHtml(job.job_id || '-')} · ${escapeHtml(job.safety_level || '-')} · external_side_effect=${escapeHtml(Boolean(job.external_side_effect))}</div>
            </div>
            <span class="badge ${okClass}">${job.running ? 'running' : job.last_success === false ? 'failed' : 'ok'}</span>
        </div>
        <div class="trading-memory-prices">
            <span>enabled=${escapeHtml(Boolean(job.enabled))}</span>
            <span>duration=${escapeHtml(job.last_duration_ms ?? '-')}ms</span>
        </div>
        ${job.last_error_summary ? `<div class="trading-memory-message">${escapeHtml(job.last_error_summary)}</div>` : ''}
    </div></div>`;
}

function renderRuntimeTask(task) {
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(task.task_id || '-')}</div>
                <div class="trading-memory-meta">status=${escapeHtml(task.status || '-')} · age=${escapeHtml(task.age_seconds ?? '-')}s${task.goal_id ? ` · goal=${escapeHtml(task.goal_id)}` : ''}</div>
            </div>
            <span class="badge ${task.status === 'error' ? 'badge-red' : task.status === 'running' ? 'badge-gold' : 'badge-green'}">${escapeHtml(task.status || '-')}</span>
        </div>
        <div class="trading-memory-prices">
            <span>result_count=${escapeHtml(task.result_count ?? '-')}</span>
            <span>result_total=${escapeHtml(task.result_total ?? '-')}</span>
        </div>
        ${task.error_summary ? `<div class="trading-memory-message">${escapeHtml(task.error_summary)}</div>` : ''}
    </div></div>`;
}

function renderRuntimeToolCall(call) {
    const args = renderRuntimeObject(call.args_summary || {});
    const contexts = Array.isArray(call.contexts) && call.contexts.length ? ` · contexts=${escapeHtml(call.contexts.join(','))}` : '';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(call.tool_name || '-')}</div>
                <div class="trading-memory-meta">${escapeHtml(call.tool_timestamp || call.conversation_timestamp || '-')}${contexts}</div>
            </div>
            <span class="badge ${call.ok === false ? 'badge-red' : call.ok === true ? 'badge-green' : 'badge-muted'}">${call.ok === false ? 'failed' : call.ok === true ? 'ok' : 'unknown'}</span>
        </div>
        <div class="trading-memory-prices"><span>duration=${escapeHtml(call.duration_ms ?? '-')}ms</span></div>
        ${args ? `<div class="trading-memory-message">args: ${args}</div>` : ''}
        ${call.error_summary ? `<div class="trading-memory-meta">error: ${escapeHtml(call.error_summary)}</div>` : ''}
    </div></div>`;
}

function renderRuntimeAgentTrace(trace) {
    if (!trace || !trace.present) {
        return `<div class="trading-memory-list">${renderRuntimeEmpty('No agent trace yet')}</div>`;
    }
    const steps = Array.isArray(trace.steps) ? trace.steps : [];
    const answerPresent = Boolean(trace.final_answer_present);
    return `<div class="trading-memory-list">
        <div class="card trading-memory-record"><div class="card-body">
            <div class="trading-memory-record-header">
                <div>
                    <div class="trading-memory-name">Agent Trace</div>
                    <div class="trading-memory-meta">status=${escapeHtml(trace.status || '-')} | reason=${escapeHtml(formatRuntimeTraceReason(trace.termination_reason))} | iterations=${escapeHtml(trace.iterations ?? 0)} | max=${escapeHtml(trace.max_iterations ?? '-')} | steps=${escapeHtml(trace.step_count ?? steps.length)}</div>
                </div>
                <span class="badge ${answerPresent ? 'badge-green' : 'badge-muted'}">answer_present=${escapeHtml(answerPresent)}</span>
            </div>
            <div class="trading-memory-prices">
                <span>duration=${escapeHtml(trace.duration_ms ?? '-')}ms</span>
                <span>started=${escapeHtml(trace.started_at ?? '-')}</span>
                <span>ended=${escapeHtml(trace.ended_at ?? '-')}</span>
            </div>
        </div></div>
        ${steps.length ? steps.map(renderRuntimeAgentTraceStep).join('') : renderRuntimeEmpty('No tool steps')}
    </div>`;
}

function renderRuntimeAgentTraceStep(step) {
    const args = renderRuntimeObject(step.args_summary || {});
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(step.tool_name || '-')}</div>
                <div class="trading-memory-meta">iteration=${escapeHtml(step.iteration ?? '-')} | result_chars=${escapeHtml(step.result_chars ?? 0)}</div>
            </div>
            <span class="badge ${step.ok === false ? 'badge-red' : step.ok === true ? 'badge-green' : 'badge-muted'}">${step.ok === false ? 'failed' : step.ok === true ? 'ok' : 'unknown'}</span>
        </div>
        <div class="trading-memory-prices">
            <span>duration=${escapeHtml(step.duration_ms ?? '-')}ms</span>
            <span>has_result=${escapeHtml(Boolean(step.has_result))}</span>
            <span>error_present=${escapeHtml(Boolean(step.error_present))}</span>
        </div>
        ${args ? `<div class="trading-memory-message">args: ${args}</div>` : ''}
    </div></div>`;
}

function formatRuntimeTraceReason(reason) {
    if (!reason) return '-';
    const value = String(reason);
    if (value === 'final_answer') return 'answered';
    if (isRuntimeSensitiveText(value)) return '[REDACTED]';
    return value;
}

function formatRuntimeSafeText(value) {
    if (value === null || value === undefined || value === '') return '-';
    const text = String(value);
    return isRuntimeSensitiveText(text) ? '[REDACTED]' : text;
}

function renderRuntimeAgentPlan(plan) {
    if (!plan || !plan.present) {
        return `<div class="trading-memory-list">${renderRuntimeEmpty('No agent plan yet')}</div>`;
    }
    const steps = Array.isArray(plan.steps) ? plan.steps : [];
    const review = plan.review || {};
    const reviewLine = review.present
        ? `review_status=${formatRuntimeSafeText(review.status)} | verification=${formatRuntimeSafeText(review.verification_note)} | blocked=${formatRuntimeSafeText(review.blocked_reason)} | issues=${review.issue_count ?? 0} | sensitive_args=${review.sensitive_argument_count ?? 0}`
        : '';
    const statusClass = plan.status === 'failed'
        ? 'badge-red'
        : plan.status === 'completed'
            ? 'badge-green'
            : plan.status === 'running'
                ? 'badge-gold'
                : 'badge-muted';
    return `<div class="trading-memory-list">
        <div class="card trading-memory-record"><div class="card-body">
            <div class="trading-memory-record-header">
                <div>
                    <div class="trading-memory-name">Agent Plan</div>
                    <div class="trading-memory-meta">plan_status=${escapeHtml(plan.status || '-')} | iteration=${escapeHtml(plan.iteration ?? '-')} | goal_present=${escapeHtml(Boolean(plan.goal_present))} | plan_steps=${escapeHtml(plan.step_count ?? steps.length)}</div>
                </div>
                <span class="badge ${statusClass}">${escapeHtml(plan.status || '-')}</span>
            </div>
            ${plan.goal ? `<div class="trading-memory-message">goal: ${escapeHtml(plan.goal)}</div>` : ''}
            ${reviewLine ? `<div class="trading-memory-meta">${escapeHtml(reviewLine)}</div>` : ''}
        </div></div>
        ${steps.length ? steps.map(renderRuntimeAgentPlanStep).join('') : renderRuntimeEmpty('No plan steps')}
    </div>`;
}

function renderRuntimeAgentPlanStep(step) {
    const args = renderRuntimeObject(step.args_summary || {});
    const okLabel = step.ok === false ? 'failed' : step.ok === true ? 'ok' : (step.status || 'unknown');
    const verificationNote = formatRuntimeSafeText(step.verification_note);
    const blockedReason = formatRuntimeSafeText(step.blocked_reason);
    const reviewLine = step.verification_note || step.blocked_reason
        ? `verification=${verificationNote} | blocked=${blockedReason}`
        : '';
    return `<div class="card trading-memory-record"><div class="card-body">
        <div class="trading-memory-record-header">
            <div>
                <div class="trading-memory-name">${escapeHtml(step.index ?? '-')}. ${escapeHtml(step.tool_name || '-')}</div>
                <div class="trading-memory-meta">status=${escapeHtml(step.status || '-')} | purpose=${escapeHtml(step.purpose || '-')}</div>
            </div>
            <span class="badge ${step.ok === false ? 'badge-red' : step.ok === true ? 'badge-green' : 'badge-muted'}">${escapeHtml(okLabel)}</span>
        </div>
        <div class="trading-memory-prices">
            <span>duration=${escapeHtml(step.duration_ms ?? '-')}ms</span>
            <span>result_present=${escapeHtml(Boolean(step.result_present))}</span>
            <span>error_present=${escapeHtml(Boolean(step.error_present))}</span>
        </div>
        ${args ? `<div class="trading-memory-message">args: ${args}</div>` : ''}
        ${reviewLine ? `<div class="trading-memory-meta">${escapeHtml(reviewLine)}</div>` : ''}
    </div></div>`;
}

function renderRuntimeObject(value) {
    if (!value || typeof value !== 'object') return '';
    return Object.entries(value)
        .map(([key, item]) => {
            if (isRuntimeSensitiveKey(key)) return null;
            const safeValue = formatRuntimeObjectValue(item);
            if (safeValue === null || safeValue === undefined || safeValue === '') return null;
            return `${escapeHtml(key)}=${escapeHtml(safeValue)}`;
        })
        .filter(Boolean)
        .join(' · ');
}

function formatRuntimeObjectValue(item) {
    if (Array.isArray(item)) {
        const values = item.map(formatRuntimeObjectValue).filter(value => value !== null && value !== undefined && value !== '');
        return values.length ? values.join(',') : null;
    }
    if (item && typeof item === 'object') {
        const values = Object.entries(item)
            .map(([key, value]) => {
                if (isRuntimeSensitiveKey(key)) return null;
                const safeValue = formatRuntimeObjectValue(value);
                return safeValue ? `${key}:${safeValue}` : null;
            })
            .filter(Boolean);
        return values.length ? `{${values.join(',')}}` : null;
    }
    const text = String(item);
    return isRuntimeSensitiveText(text) ? '[REDACTED]' : text;
}

function isRuntimeSensitiveKey(key) {
    return /(token|secret|password|authorization|cookie|chat_id|app_secret|uid|profile|whisper|raw|result_summary|final_answer|account[_-]?id|api[_-]?key|handler|params|manifest|payload|credential|user[_-]?id|private[_-]?network|local[_-]?path)/i.test(String(key || ''));
}

function isRuntimeSensitiveText(text) {
    return /(bearer\s+[a-z0-9._-]+|\/w\s+|secret-token|app_secret|chat_id|uid_secret|at_secret|playersecret|errorseller|gatewayleak|account-123|api_key|raw_payload|raw_manifest|raw_plan|raw_config|credential|webhook_secret|connector_token|private_network_url|local_path|user_id|final answer)/i.test(String(text || ''));
}

function renderRuntimeEmpty(text) {
    return `<div class="empty-state"><div class="empty-state-icon">RT</div><div class="empty-state-text">${escapeHtml(text)}</div></div>`;
}

function startRuntimeStatusPolling() {
    refreshRuntimeStatus();
    setInterval(refreshRuntimeStatus, RUNTIME_STATUS_POLL_MS);
}

function appendTradePlanToMessage(messageEl, plan) {
    if (!messageEl || !plan || typeof window.renderTradePlanCard !== 'function') return;
    const content = messageEl.querySelector('.message-content');
    if (!content) return;
    content.insertAdjacentHTML('beforeend', window.renderTradePlanCard(plan));
}

function getProactivePushQualitySource(data) {
    const nested = data && typeof data.data === 'object' ? data.data : null;
    return nested || data || {};
}

function hasProactivePushQualityData(data) {
    const source = getProactivePushQualitySource(data);
    return [
        'push_quality_score',
        'push_quality_reviewed_count',
        'push_quality_good_rate',
        'push_quality_false_positive_rate'
    ].some(key => Object.prototype.hasOwnProperty.call(source, key));
}

function formatPushQualityRate(value) {
    const rate = Number(value);
    if (!Number.isFinite(rate)) return '-';
    return `${Math.round(rate * 100)}%`;
}

function getProactivePushQualityBadge(data) {
    if (!hasProactivePushQualityData(data)) return null;
    const source = getProactivePushQualitySource(data);
    const reviewed = Number(source.push_quality_reviewed_count || 0);
    const score = Number(source.push_quality_score || 0);
    if (reviewed <= 0) {
        return { label: '待复盘', className: 'badge-muted' };
    }
    if (score > 0) {
        return { label: '表现好', className: 'badge-green' };
    }
    if (score < 0) {
        return { label: '需谨慎', className: 'badge-red' };
    }
    return { label: '观察中', className: 'badge-gold' };
}

function renderProactivePushQualityBadge(data) {
    const badge = getProactivePushQualityBadge(data);
    if (!badge) return '';
    const source = getProactivePushQualitySource(data);
    const reviewed = Number(source.push_quality_reviewed_count || 0);
    const goodRate = formatPushQualityRate(source.push_quality_good_rate);
    const falsePositiveRate = formatPushQualityRate(source.push_quality_false_positive_rate);
    const chips = [
        `<span class="badge ${badge.className}">${escapeHtml(badge.label)}</span>`,
        `<span class="badge badge-muted">复盘 ${escapeHtml(reviewed)}</span>`,
        goodRate !== '-' ? `<span class="badge badge-muted">好评率 ${escapeHtml(goodRate)}</span>` : '',
        falsePositiveRate !== '-' ? `<span class="badge badge-muted">误报率 ${escapeHtml(falsePositiveRate)}</span>` : ''
    ].filter(Boolean).join('');
    return `<div class="trading-memory-chips proactive-push-quality">${chips}</div>`;
}

function appendProactivePushQualityToMessage(messageEl, data) {
    if (!messageEl) return;
    const content = messageEl.querySelector('.message-content');
    if (!content) return;
    const html = renderProactivePushQualityBadge(data);
    if (html) content.insertAdjacentHTML('beforeend', html);
}

function handleNotificationMessage(data) {
    if (data.type === 'alert') {
        const msg = `${data.item}: 当前 ${data.current_price}p (${data.direction} ${data.price}p)`;
        showNotification(msg, 'warning');
        addChatMessage('system', msg);
        loadSidebar();
    } else if (data.type === 'watch') {
        const freq = {'hourly': '每小时', 'daily': '每日', 'weekly': '每周'}[data.frequency] || data.frequency;
        const msg = `⏰ ${freq}关注推送: ${data.item_name} — ${data.price_info || '暂无价格'}`;
        showNotification(msg, 'info');
        addChatMessage('system', msg);
        queryItemPrice(data.item_id);
    } else if (data.type === 'enriched_analysis') {
        const typeMap = {'anomaly': '价格异常', 'opportunity': '套利机会', 'trend': '趋势分析'};
        const priorityIcon = data.priority === 1 ? '🔴' : data.priority === 2 ? '🟡' : '🔵';
        const label = typeMap[data.notification_type] || data.notification_type;
        const msg = `${priorityIcon} ${label}: ${data.item_display}\n${data.analysis}`;
        showNotification(msg, data.priority === 1 ? 'warning' : 'info');
        addChatMessage('agent', msg);
        loadSidebar();
    } else if (data.type === 'goal_opportunity') {
        const priorityIcon = data.priority === 1 ? '🔴' : '🟡';
        const msg = `${priorityIcon} 目标机会: ${data.message}`;
        showNotification(msg, data.priority === 1 ? 'warning' : 'info');
        addChatMessage('agent', msg);
    } else if (data.type === 'proactive_push') {
        const actionMap = {'buy now': '立即买入', 'sell now': '立即卖出', 'watch': '持续关注'};
        const typeMap = {'opportunity': '机会', 'warning': '警告', 'recommendation': '推荐'};
        const priorityIcon = data.priority === 1 ? '🔴' : '🟡';
        const label = typeMap[data.push_type] || data.push_type;
        const action = actionMap[data.action_suggestion] || data.action_suggestion;
        const msg = `${priorityIcon} [${label}] ${data.item_display}\n${data.message}\n建议: ${action}`;
        showNotification(msg, data.priority === 1 ? 'warning' : 'info');
        const messageEl = addChatMessage('agent', msg);
        appendProactivePushQualityToMessage(messageEl, data);
        appendTradePlanToMessage(messageEl, data.trade_plan || data.data?.trade_plan);
    }
}

window.renderProactivePushQualityBadge = renderProactivePushQualityBadge;
window.handleNotificationMessage = handleNotificationMessage;

function setupWebSocket() {
    // 标签页不可见时不连接
    if (document.visibilityState === 'hidden') {
        document.addEventListener('visibilitychange', function onVis() {
            if (document.visibilityState === 'visible') {
                document.removeEventListener('visibilitychange', onVis);
                setupWebSocket();
            }
        });
        return;
    }

    try {
        const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${wsProto}//${location.host}/ws/notifications`);

        ws.onopen = () => {
            console.log('通知 WebSocket 已连接');
            wsReconnectDelay = 1000;
            refreshRuntimeStatus();
        };

        ws.onmessage = (event) => {
            let data;
            try {
                data = JSON.parse(event.data);
            } catch (e) {
                console.warn('通知 WebSocket 消息解析失败:', e);
                return;
            }
            handleNotificationMessage(data);
        };

        ws.onerror = (error) => {
            console.error('WebSocket 错误:', error);
            updateSidebarStatus('error');
        };

        ws.onclose = () => {
            console.log(`WebSocket 断开，${wsReconnectDelay / 1000}s 后重连`);
            setTimeout(() => {
                wsReconnectDelay = Math.min(wsReconnectDelay * 2, WS_MAX_DELAY);
                setupWebSocket();
            }, wsReconnectDelay);
        };
    } catch (error) {
        console.error('WebSocket 连接失败:', error);
        setTimeout(setupWebSocket, wsReconnectDelay);
    }
}

// ===== 首次访问引导 =====

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
        try {
            await fetch(`${API_BASE}/api/pref`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: 'platform', value: selectedPlatform })
            });

            localStorage.setItem('warframe_visited', 'true');
            modal.classList.remove('active');

            addChatMessage('system', `欢迎使用 Warframe 交易助手！已设置平台为 ${selectedPlatform.toUpperCase()}。`);
            addChatMessage('agent', '你好，Tenno！我是你的交易助手。可以问我任何关于 Warframe 物品价格的问题。\n\n**快速开始：**\n- 直接输入物品名查询价格\n- 使用 `/fav add 物品名` 添加收藏\n- 使用 `/alert add 物品名 below 40` 设置提醒');
        } catch (error) {
            console.error('保存偏好失败:', error);
            showToast('保存偏好失败，请重试', 'error');
        }
    });
}

// ===== 粒子背景系统 =====

function initParticleBg() {
    const canvas = document.getElementById('particle-bg');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let particles = [];
    let animationId;
    let lastTime = 0;
    const fps = 30;
    const interval = 1000 / fps;

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    function createParticle() {
        return {
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            size: Math.random() * 1.5 + 0.5,
            speedX: (Math.random() - 0.5) * 0.3,
            speedY: (Math.random() - 0.5) * 0.3,
            opacity: Math.random() * 0.5 + 0.1,
            pulse: Math.random() * Math.PI * 2
        };
    }

    function init() {
        resize();
        particles = [];
        const count = Math.min(60, Math.floor((canvas.width * canvas.height) / 15000));
        for (let i = 0; i < count; i++) {
            particles.push(createParticle());
        }
    }

    function animate(currentTime) {
        animationId = requestAnimationFrame(animate);

        const delta = currentTime - lastTime;
        if (delta < interval) return;
        lastTime = currentTime - (delta % interval);

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        particles.forEach(p => {
            p.x += p.speedX;
            p.y += p.speedY;
            p.pulse += 0.02;

            if (p.x < 0) p.x = canvas.width;
            if (p.x > canvas.width) p.x = 0;
            if (p.y < 0) p.y = canvas.height;
            if (p.y > canvas.height) p.y = 0;

            const currentOpacity = p.opacity * (0.7 + 0.3 * Math.sin(p.pulse));

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(212, 167, 55, ${currentOpacity})`;
            ctx.fill();
        });
    }

    window.addEventListener('resize', () => {
        resize();
    });

    init();
    animate(0);
}

// ===== 初始化 =====

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initParticleBg();
    loadSidebar();
    startRuntimeStatusPolling();
    setupWebSocket();
    checkFirstVisit();
    addLoadingAnimations();
    initSettings();
    initCommandPalette();
    initKeyboardShortcuts();
    initResizeHandles();
    initMouseGradient();

    // 主题切换按钮
    document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);
    document.querySelector('.status-indicator')?.addEventListener('click', showRuntimeStatusPanel);

    // 设置按钮
    document.getElementById('settings-btn')?.addEventListener('click', () => {
        document.getElementById('more-menu')?.classList.remove('active');
        document.getElementById('settings-modal').classList.add('active');
    });
});

function addLoadingAnimations() {
    const elements = document.querySelectorAll('.sidebar, .chat-area, .detail-panel');
    elements.forEach((el, index) => {
        el.style.opacity = '0';
        el.style.animation = `fadeInUp 0.6s ease-out ${index * 0.1}s forwards`;
    });
}

// ===== 设置系统 =====

const SETTINGS_KEY = 'warframe_settings';
let appSettings = {
    browserNotify: true,
    soundEnabled: true,
    showPriceChange: true
};

function initSettings() {
    try {
        const saved = localStorage.getItem(SETTINGS_KEY);
        if (saved) Object.assign(appSettings, JSON.parse(saved));
    } catch (e) {}

    // 绑定设置控件
    const browserNotify = document.getElementById('setting-browser-notify');
    const soundEnabled = document.getElementById('setting-sound');
    const priceChange = document.getElementById('setting-price-change');

    if (browserNotify) {
        browserNotify.checked = appSettings.browserNotify;
        browserNotify.addEventListener('change', () => {
            appSettings.browserNotify = browserNotify.checked;
            saveSettings();
            if (appSettings.browserNotify && Notification.permission === 'default') {
                Notification.requestPermission();
            }
        });
    }

    if (soundEnabled) {
        soundEnabled.checked = appSettings.soundEnabled;
        soundEnabled.addEventListener('change', () => {
            appSettings.soundEnabled = soundEnabled.checked;
            saveSettings();
        });
    }

    if (priceChange) {
        priceChange.checked = appSettings.showPriceChange;
        priceChange.addEventListener('change', () => {
            appSettings.showPriceChange = priceChange.checked;
            saveSettings();
        });
    }

    // 微信推送设置
    initPushSettings();
    // 飞书机器人设置
    initFeishuSettings();
}

function saveSettings() {
    try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(appSettings));
    } catch (e) {}
}

// ===== 微信推送设置 =====

async function initPushSettings() {
    const wxToggle = document.getElementById('setting-wx-push');
    const setupDiv = document.getElementById('push-setup');
    const uidInput = document.getElementById('wxpusher-uid');
    const saveBtn = document.getElementById('wxpusher-save');
    const testBtn = document.getElementById('wxpusher-test');
    const qrArea = document.getElementById('push-qrcode-area');

    if (!wxToggle) return;

    // 加载当前配置
    try {
        const resp = await fetch('/api/push/config');
        const cfg = await resp.json();
        wxToggle.checked = cfg.enabled || false;
        if (uidInput && cfg.uids && cfg.uids.length > 0) {
            uidInput.value = cfg.uids[0];
        }
        const pa = document.getElementById('setting-push-alerts');
        const pw = document.getElementById('setting-push-watches');
        const pp = document.getElementById('setting-push-proactive');
        const pr = document.getElementById('setting-push-report');
        const pt = document.getElementById('setting-report-time');
        if (pa) pa.checked = cfg.push_alerts !== false;
        if (pw) pw.checked = cfg.push_watches !== false;
        if (pp) pp.checked = cfg.push_proactive !== false;
        if (pr) pr.checked = cfg.push_daily_report !== false;
        if (pt && cfg.report_time) pt.value = cfg.report_time;

        if (cfg.enabled && setupDiv) setupDiv.style.display = 'block';
    } catch (e) {}

    // 切换显示/隐藏
    wxToggle.addEventListener('change', async () => {
        if (setupDiv) setupDiv.style.display = wxToggle.checked ? 'block' : 'none';
        await savePushConfig({ enabled: wxToggle.checked });
    });

    // 保存 UID
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            const uid = uidInput.value.trim();
            if (!uid || !uid.startsWith('UID_')) {
                showToast('请输入有效的 UID（以 UID_ 开头）', 'warning');
                return;
            }
            await savePushConfig({ uids: [uid], enabled: true });
            showToast('UID 已保存', 'success');
        });
    }

    // 测试推送
    if (testBtn) {
        testBtn.addEventListener('click', async () => {
            try {
                const resp = await fetch('/api/push/test', { method: 'POST' });
                const data = await resp.json();
                if (data.status === 'ok') {
                    showToast('测试消息已发送，请检查微信', 'success');
                } else {
                    showToast(data.message || '发送失败', 'error');
                }
            } catch (e) {
                showToast('请求失败', 'error');
            }
        });
    }

    // 子开关变更
    for (const [id, key] of [
        ['setting-push-alerts', 'push_alerts'],
        ['setting-push-watches', 'push_watches'],
        ['setting-push-proactive', 'push_proactive'],
        ['setting-push-report', 'push_daily_report'],
    ]) {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', () => savePushConfig({ [key]: el.checked }));
        }
    }

    // 报告时间变更
    const ptEl = document.getElementById('setting-report-time');
    if (ptEl) {
        ptEl.addEventListener('change', () => savePushConfig({ report_time: ptEl.value }));
    }

    // 加载二维码
    if (qrArea) {
        try {
            const resp = await fetch('/api/push/qrcode');
            const data = await resp.json();
            if (data.status === 'ok' && typeof data.url === 'string' && data.url) {
                const img = document.createElement('img');
                img.src = data.url;
                img.alt = '扫码关注 WxPusher';
                qrArea.innerHTML = '';
                qrArea.appendChild(img);
            }
        } catch (e) {}
    }
}

async function savePushConfig(updates) {
    try {
        await fetch('/api/push/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        });
    } catch (e) {}
}

// ===== 飞书机器人设置 =====

async function initFeishuSettings() {
    const toggle = document.getElementById('setting-feishu-enabled');
    const setupDiv = document.getElementById('feishu-setup');
    const appIdInput = document.getElementById('feishu-app-id');
    const appSecretInput = document.getElementById('feishu-app-secret');
    const saveBtn = document.getElementById('feishu-save');
    const testBtn = document.getElementById('feishu-test');

    if (!toggle) return;

    // 加载配置
    try {
        const resp = await fetch('/api/feishu/config');
        const cfg = await resp.json();
        toggle.checked = cfg.enabled || false;
        if (appIdInput) appIdInput.value = cfg.app_id || '';
        if (cfg.enabled && setupDiv) setupDiv.style.display = 'block';
    } catch (e) {}

    // 切换显示
    toggle.addEventListener('change', async () => {
        if (setupDiv) setupDiv.style.display = toggle.checked ? 'block' : 'none';
        await saveFeishuConfig({ enabled: toggle.checked });
    });

    // 保存
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            const updates = {};
            if (appIdInput) updates.app_id = appIdInput.value.trim();
            if (appSecretInput && appSecretInput.value) updates.app_secret = appSecretInput.value.trim();
            updates.enabled = true;
            await saveFeishuConfig(updates);
            showToast('飞书配置已保存，正在连接...', 'success');
        });
    }

    // 测试
    if (testBtn) {
        testBtn.addEventListener('click', async () => {
            try {
                const resp = await fetch('/api/feishu/test', { method: 'POST' });
                const data = await resp.json();
                if (data.status === 'ok') {
                    showToast(data.message || '连接成功', 'success');
                } else {
                    showToast(data.message || '连接失败', 'error');
                }
            } catch (e) {
                showToast('请求失败', 'error');
            }
        });
    }
}

async function saveFeishuConfig(updates) {
    try {
        await fetch('/api/feishu/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        });
    } catch (e) {}
}

// ===== 命令面板 =====

const COMMANDS = [
    { name: '充沛价格', action: () => { chatInput.value = '充沛多少钱'; handleSend(); } },
    { name: '扫描关注', action: () => { chatInput.value = '扫描关注'; handleSend(); } },
    { name: '查看记忆', action: () => { chatInput.value = '/memory'; handleSend(); } },
    { name: '对比物品', action: () => handleCompare() },
    { name: '每日报告', action: () => document.getElementById('report-btn')?.click() },
    { name: '切换主题', action: () => toggleTheme() },
    { name: '清空对话', action: () => clearChatHistory() },
    { name: '打开设置', action: () => document.getElementById('settings-modal')?.classList.add('active') },
    { name: '快捷键帮助', action: () => document.getElementById('shortcuts-modal')?.classList.add('active') },
    { name: '收藏物品', action: () => { chatInput.value = '/fav add '; chatInput.focus(); } },
    { name: '添加提醒', action: () => { chatInput.value = '/alert add '; chatInput.focus(); } },
    { name: '管理别名', action: () => { document.getElementById('alias-modal')?.classList.add('active'); loadAliases(); } },
];

function initCommandPalette() {
    const modal = document.getElementById('command-modal');
    const input = document.getElementById('command-input');
    const list = document.getElementById('command-list');
    if (!modal || !input || !list) return;

    function filterCommands(query) {
        const q = query.toLowerCase();
        return COMMANDS.filter(cmd => cmd.name.toLowerCase().includes(q));
    }

    function renderCommands(commands) {
        list.textContent = '';
        commands.forEach((cmd, i) => {
            const item = document.createElement('div');
            item.className = `command-item ${i === 0 ? 'selected' : ''}`;
            item.dataset.index = String(i);
            item.textContent = cmd.name;
            item.addEventListener('click', () => {
                cmd.action();
                modal.classList.remove('active');
                input.value = '';
            });
            list.appendChild(item);
        });
    }

    input.addEventListener('input', () => {
        renderCommands(filterCommands(input.value));
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            modal.classList.remove('active');
            input.value = '';
        }
        if (e.key === 'Enter') {
            const selected = list.querySelector('.command-item.selected');
            if (selected) selected.click();
        }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            const items = list.querySelectorAll('.command-item');
            const current = list.querySelector('.command-item.selected');
            let idx = Array.from(items).indexOf(current);
            items.forEach(el => el.classList.remove('selected'));
            if (e.key === 'ArrowDown') idx = (idx + 1) % items.length;
            else idx = (idx - 1 + items.length) % items.length;
            items[idx]?.classList.add('selected');
            items[idx]?.scrollIntoView({ block: 'nearest' });
        }
    });

    // 点击遮罩关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
            input.value = '';
        }
    });

    renderCommands(COMMANDS);
}

// ===== 键盘快捷键 =====

function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+P: 命令面板
        if (e.ctrlKey && e.key === 'p') {
            e.preventDefault();
            const modal = document.getElementById('command-modal');
            const input = document.getElementById('command-input');
            if (modal) {
                modal.classList.add('active');
                setTimeout(() => input?.focus(), 100);
            }
            return;
        }

        // Ctrl+/: 快捷键帮助
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            document.getElementById('shortcuts-modal')?.classList.add('active');
            return;
        }

        // 数字键 1-4: 触发快捷按钮（输入框未聚焦时）
        if (!e.ctrlKey && !e.altKey && !e.shiftKey && document.activeElement !== chatInput) {
            const num = parseInt(e.key);
            if (num >= 1 && num <= 4) {
                const btns = document.querySelectorAll('.quick-btn');
                if (btns[num - 1]) btns[num - 1].click();
            }
        }
    });
}

// ===== 布局拖拽调整 =====

const LAYOUT_KEY = 'warframe_layout';

function initResizeHandles() {
    const sidebarHandle = document.getElementById('resize-sidebar');
    const detailHandle = document.getElementById('resize-detail');
    const sidebar = document.getElementById('sidebar');
    const detailPanel = document.getElementById('detail-panel');

    if (!sidebarHandle || !detailHandle || !sidebar || !detailPanel) return;

    // 恢复保存的宽度
    try {
        const saved = localStorage.getItem(LAYOUT_KEY);
        if (saved) {
            const layout = JSON.parse(saved);
            if (layout.sidebar) sidebar.style.width = layout.sidebar;
            if (layout.detail) detailPanel.style.width = layout.detail;
        }
    } catch (e) {}

    function startResize(handle, target, direction) {
        let startX, startWidth;

        function onMouseDown(e) {
            e.preventDefault();
            startX = e.clientX;
            startWidth = target.offsetWidth;
            handle.classList.add('active');
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        }

        function onMouseMove(e) {
            const dx = e.clientX - startX;
            const newWidth = direction === 'right' ? startWidth + dx : startWidth - dx;
            const clamped = Math.max(200, Math.min(500, newWidth));
            target.style.width = clamped + 'px';
        }

        function onMouseUp() {
            handle.classList.remove('active');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            saveLayout();
        }

        handle.addEventListener('mousedown', onMouseDown);
    }

    function saveLayout() {
        try {
            localStorage.setItem(LAYOUT_KEY, JSON.stringify({
                sidebar: sidebar.style.width,
                detail: detailPanel.style.width
            }));
        } catch (e) {}
    }

    startResize(sidebarHandle, sidebar, 'right');
    startResize(detailHandle, detailPanel, 'left');

    // 可折叠侧边栏 (借鉴 warframe-toolkit)
    const SIDEBAR_COLLAPSE_KEY = 'warframe_sidebar_collapsed';
    const sidebarHeader = sidebar.querySelector('.sidebar-header');
    if (sidebarHeader) {
        const collapseBtn = document.createElement('button');
        collapseBtn.className = 'sidebar-collapse-btn';
        collapseBtn.title = '折叠侧边栏';
        collapseBtn.textContent = '‹';
        sidebarHeader.appendChild(collapseBtn);

        // 恢复折叠状态
        try {
            if (localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === 'true') {
                sidebar.classList.add('collapsed');
                collapseBtn.textContent = '›';
            }
        } catch (e) {}

        collapseBtn.addEventListener('click', () => {
            const isCollapsed = sidebar.classList.toggle('collapsed');
            collapseBtn.textContent = isCollapsed ? '›' : '‹';
            try {
                localStorage.setItem(SIDEBAR_COLLAPSE_KEY, isCollapsed);
            } catch (e) {}
        });
    }
}

// ===== 鼠标跟随渐变（Stripe 风格） =====

function initMouseGradient() {
    const blob = document.querySelector('.mesh-blob-gold');
    if (!blob) return;

    let mouseX = 0, mouseY = 0;
    let currentX = 0, currentY = 0;
    const speed = 0.05;

    document.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 30;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 30;
    });

    function animate() {
        currentX += (mouseX - currentX) * speed;
        currentY += (mouseY - currentY) * speed;
        blob.style.transform = `translate(${currentX}px, ${currentY}px)`;
        requestAnimationFrame(animate);
    }

    animate();
}

// ===== 工具函数 =====

function formatPrice(price) {
    if (price === null || price === undefined) return '无';
    return `${price}p`;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ===== 样式注入 =====

const style = document.createElement('style');
style.textContent = `
    .toast {
        padding: 12px 20px;
        border-radius: 4px;
        font-family: var(--font-body);
        font-size: var(--text-sm);
        letter-spacing: var(--tracking-wide);
        transform: translateX(100%);
        opacity: 0;
        transition: all 0.4s var(--ease-spring);
        max-width: 300px;
    }

    .toast.show {
        transform: translateX(0);
        opacity: 1;
    }

    .toast-info {
        background: rgba(74, 158, 255, 0.2);
        border: 1px solid rgba(74, 158, 255, 0.3);
        color: var(--blue-primary);
    }

    .toast-success {
        background: rgba(74, 222, 128, 0.2);
        border: 1px solid rgba(74, 222, 128, 0.3);
        color: var(--green-success);
    }

    .toast-warning {
        background: rgba(245, 158, 11, 0.2);
        border: 1px solid rgba(245, 158, 11, 0.3);
        color: var(--orange-warning);
    }

    .toast-error {
        background: rgba(239, 68, 68, 0.2);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: var(--red-error);
    }

    .sidebar-actions {
        display: flex;
        gap: 6px;
        margin-bottom: 10px;
    }

    .sidebar-btn {
        flex: 1;
        padding: 6px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s ease-out;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .sidebar-btn:hover {
        background: rgba(212, 167, 55, 0.1);
        border-color: rgba(212, 167, 55, 0.3);
        transform: translateY(-1px);
    }

    [data-theme="light"] {
        --bg-primary: #f5f5f5;
        --bg-secondary: #ffffff;
        --bg-tertiary: #e8e8e8;
        --text-primary: #1a1a1a;
        --text-secondary: #4a4a4a;
        --text-tertiary: #888888;
        --gold-primary: #b8860b;
        --blue-primary: #2563eb;
    }

    [data-theme="light"] .sidebar {
        background: linear-gradient(180deg, #ffffff, #f8f8f8);
        border-right-color: rgba(184, 134, 11, 0.2);
    }

    [data-theme="light"] .chat-area {
        background: #f5f5f5;
    }

    [data-theme="light"] .message.user .message-content {
        background: rgba(37, 99, 235, 0.1);
        border-color: rgba(37, 99, 235, 0.2);
    }

    [data-theme="light"] .message.agent .message-content {
        background: rgba(0, 0, 0, 0.03);
        border-color: rgba(0, 0, 0, 0.08);
    }

    [data-theme="light"] .input-wrapper input {
        background: #ffffff;
        border-color: rgba(0, 0, 0, 0.15);
        color: #1a1a1a;
    }

    [data-theme="light"] .detail-panel {
        background: linear-gradient(180deg, #ffffff, #f8f8f8);
        border-left-color: rgba(184, 134, 11, 0.2);
    }

    [data-theme="light"] .list-item {
        background: rgba(0, 0, 0, 0.02);
        border-color: rgba(0, 0, 0, 0.06);
    }

    [data-theme="light"] .list-item:hover {
        background: rgba(184, 134, 11, 0.05);
    }

    /* 设置模态框 */
    .settings-modal-content,
    .shortcuts-modal-content {
        max-width: 400px;
    }

    .modal-close-btn {
        position: absolute;
        top: 12px;
        right: 16px;
        background: none;
        border: none;
        color: var(--text-tertiary);
        font-size: 24px;
        cursor: pointer;
        transition: color 0.2s;
        z-index: 10;
    }

    .modal-close-btn:hover {
        color: var(--gold-primary);
    }

    .settings-group {
        margin-bottom: 20px;
    }

    .settings-group h3 {
        font-family: var(--font-display);
        font-size: 12px;
        color: var(--gold-primary);
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 12px;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(212, 167, 55, 0.2);
    }

    .setting-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        cursor: pointer;
    }

    .setting-label {
        font-size: 14px;
        color: var(--text-secondary);
    }

    .setting-toggle {
        appearance: none;
        width: 40px;
        height: 22px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 11px;
        position: relative;
        cursor: pointer;
        transition: background 0.3s;
    }

    .setting-toggle::before {
        content: '';
        position: absolute;
        top: 3px;
        left: 3px;
        width: 16px;
        height: 16px;
        background: var(--text-tertiary);
        border-radius: 50%;
        transition: all 0.3s;
    }

    .setting-toggle:checked {
        background: rgba(74, 158, 255, 0.3);
    }

    .setting-toggle:checked::before {
        left: 21px;
        background: var(--blue-primary);
    }

    .push-setup {
        margin-top: 10px;
        padding: 10px;
        background: rgba(255,255,255,0.03);
        border-radius: 8px;
        border: 1px solid rgba(212,167,55,0.1);
    }
    .push-uid-row {
        display: flex;
        gap: 8px;
        margin-bottom: 8px;
    }
    .push-uid-row input {
        flex: 1;
        background: rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px;
        padding: 6px 10px;
        color: var(--text-primary);
        font-size: 13px;
        font-family: var(--font-mono);
    }
    .push-btn {
        background: rgba(74,158,255,0.2);
        border: 1px solid rgba(74,158,255,0.3);
        color: var(--blue-primary);
        padding: 6px 14px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        transition: all 0.2s;
    }
    .push-btn:hover { background: rgba(74,158,255,0.35); }
    .push-btn-secondary {
        background: rgba(255,255,255,0.05);
        border-color: rgba(255,255,255,0.15);
        color: var(--text-secondary);
    }
    .push-btn-secondary:hover { background: rgba(255,255,255,0.1); }
    .push-hint {
        font-size: 11px;
        color: var(--text-tertiary);
        margin: 6px 0;
        line-height: 1.5;
    }
    .push-qrcode-area {
        text-align: center;
        margin: 8px 0;
    }
    .push-qrcode-area img {
        max-width: 180px;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .push-report-time {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 0;
    }
    .push-report-time input[type="time"] {
        background: rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px;
        padding: 4px 8px;
        color: var(--text-primary);
        font-family: var(--font-mono);
    }

    /* 快捷键帮助 */
    .shortcuts-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .shortcut-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
    }

    .shortcut-item kbd {
        font-family: var(--font-mono);
        font-size: 11px;
        padding: 3px 8px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 3px;
        color: var(--gold-primary);
    }

    .shortcut-item span {
        font-size: 13px;
        color: var(--text-secondary);
    }

    /* 命令面板 */
    .command-modal-content {
        max-width: 500px;
        padding: 0;
        overflow: hidden;
    }

    #command-input {
        width: 100%;
        padding: 16px 20px;
        background: transparent;
        border: none;
        border-bottom: 1px solid rgba(212, 167, 55, 0.2);
        color: var(--text-primary);
        font-family: var(--font-body);
        font-size: 16px;
        outline: none;
    }

    #command-input::placeholder {
        color: var(--text-tertiary);
    }

    .command-list {
        max-height: 300px;
        overflow-y: auto;
    }

    .command-item {
        padding: 10px 20px;
        font-size: 14px;
        color: var(--text-secondary);
        cursor: pointer;
        transition: all 0.15s ease-out;
    }

    .command-item:hover,
    .command-item.selected {
        background: rgba(212, 167, 55, 0.1);
        color: var(--gold-primary);
    }

    /* 拖拽分割线 */
    .resize-handle {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 4px;
        cursor: col-resize;
        z-index: 10;
        transition: background 0.2s;
    }

    .resize-handle:hover {
        background: var(--gold-primary);
    }

    .resize-handle.active {
        background: var(--gold-primary);
    }

    /* 自定义快捷按钮 */
    .quick-btn.custom-quick-btn {
        position: relative;
    }

    .custom-quick-btn .remove-quick-btn {
        display: none;
        position: absolute;
        top: -4px;
        right: -4px;
        width: 16px;
        height: 16px;
        background: var(--red-error);
        border: none;
        border-radius: 50%;
        color: white;
        font-size: 10px;
        cursor: pointer;
        align-items: center;
        justify-content: center;
        line-height: 1;
    }

    .custom-quick-btn:hover .remove-quick-btn {
        display: flex;
    }

    .add-quick-btn {
        padding: 6px 12px;
        background: rgba(74, 222, 128, 0.1);
        border: 1px dashed rgba(74, 222, 128, 0.3);
        border-radius: 4px;
        color: var(--green-success);
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .add-quick-btn:hover {
        background: rgba(74, 222, 128, 0.2);
    }

    /* 别名管理模态框 */
    .alias-modal-content {
        max-width: 500px;
    }

    .alias-desc {
        font-size: 13px;
        color: var(--text-tertiary);
        margin-bottom: 16px;
    }

    .alias-add-section {
        margin-bottom: 16px;
    }

    .alias-add-row {
        margin-bottom: 8px;
    }

    .alias-add-row input,
    .alias-search-row input {
        width: 100%;
        padding: 8px 12px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        color: var(--text-primary);
        font-family: var(--font-body);
        font-size: 13px;
        outline: none;
        transition: border-color 0.2s;
        box-sizing: border-box;
    }

    .alias-add-row input:focus,
    .alias-search-row input:focus {
        border-color: var(--gold-primary);
    }

    .alias-add-row input::placeholder,
    .alias-search-row input::placeholder {
        color: var(--text-tertiary);
    }

    .alias-search-row {
        margin-bottom: 8px;
    }

    .alias-search-wrapper {
        position: relative;
    }

    .alias-search-results {
        display: none;
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: rgba(12, 15, 25, 0.98);
        border: 1px solid rgba(212, 167, 55, 0.2);
        border-top: none;
        border-radius: 0 0 4px 4px;
        max-height: 200px;
        overflow-y: auto;
        z-index: 100;
    }

    .alias-search-results.active {
        display: block;
    }

    .alias-search-item {
        padding: 8px 12px;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: background 0.15s;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }

    .alias-search-item:hover {
        background: rgba(212, 167, 55, 0.1);
    }

    .alias-search-item:last-child {
        border-bottom: none;
    }

    .alias-search-display {
        font-size: 13px;
        color: var(--text-primary);
    }

    .alias-search-id {
        font-family: var(--font-mono);
        font-size: 11px;
        color: var(--text-tertiary);
    }

    .alias-search-empty {
        padding: 12px;
        text-align: center;
        font-size: 13px;
        color: var(--text-tertiary);
    }

    .alias-selected {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        background: rgba(74, 222, 128, 0.08);
        border: 1px solid rgba(74, 222, 128, 0.2);
        border-radius: 4px;
        margin-bottom: 10px;
        font-size: 13px;
    }

    .alias-selected-label {
        color: var(--text-tertiary);
        font-size: 12px;
    }

    .alias-selected-name {
        color: var(--green-success);
        font-weight: 600;
    }

    .alias-selected-id {
        color: var(--text-tertiary);
        font-family: var(--font-mono);
        font-size: 11px;
    }

    .alias-clear-btn {
        margin-left: auto;
        width: 20px;
        height: 20px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 3px;
        color: var(--red-error);
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }

    .alias-clear-btn:hover {
        background: rgba(239, 68, 68, 0.2);
    }

    .alias-add-btn {
        width: 100%;
        padding: 8px 16px;
        background: rgba(74, 222, 128, 0.15);
        border: 1px solid rgba(74, 222, 128, 0.3);
        border-radius: 4px;
        color: var(--green-success);
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .alias-add-btn:hover:not(:disabled) {
        background: rgba(74, 222, 128, 0.25);
    }

    .alias-add-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }

    .alias-list {
        max-height: 300px;
        overflow-y: auto;
    }

    .alias-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 10px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 4px;
        margin-bottom: 6px;
        transition: all 0.2s;
    }

    .alias-item:hover {
        background: rgba(212, 167, 55, 0.05);
        border-color: rgba(212, 167, 55, 0.2);
    }

    .alias-info {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
    }

    .alias-name {
        color: var(--gold-primary);
        font-weight: 600;
    }

    .alias-arrow {
        color: var(--text-tertiary);
        font-size: 11px;
    }

    .alias-id {
        color: var(--text-secondary);
        font-family: var(--font-mono);
        font-size: 12px;
    }

    .alias-display {
        color: var(--text-secondary);
        font-size: 12px;
    }

    .alias-remove-btn {
        width: 22px;
        height: 22px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 3px;
        color: var(--red-error);
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }

    .alias-remove-btn:hover {
        background: rgba(239, 68, 68, 0.2);
    }

    .alias-empty {
        text-align: center;
        padding: 20px;
        color: var(--text-tertiary);
        font-size: 13px;
    }

    /* 物品未找到提示 */
    .not-found-hint {
        font-size: 14px;
        color: var(--orange-warning);
        margin-bottom: 8px;
    }

    .add-alias-hint {
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        font-size: 13px;
        color: var(--text-tertiary);
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .alias-link-btn {
        padding: 4px 12px;
        background: rgba(212, 167, 55, 0.1);
        border: 1px solid rgba(212, 167, 55, 0.3);
        border-radius: 12px;
        color: var(--gold-primary);
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .alias-link-btn:hover {
        background: rgba(212, 167, 55, 0.2);
        transform: translateY(-1px);
    }
`;
document.head.appendChild(style);

// 请求通知权限
if (Notification.permission === 'default') {
    Notification.requestPermission();
}

// ===== 公共面板操作 =====

let _panelVersion = 0;

function openDetailPanel(loadingText) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');
    if (!panel || !content) {
        console.error('[openDetailPanel] panel or content not found');
        return null;
    }
    _panelVersion++;
    panel.style.display = '';  // Clear any inline display override
    panel.scrollTop = 0;
    panel.classList.add('active');
    // 面板滑入动画
    panel.classList.add('panel-enter');
    setTimeout(() => panel.classList.remove('panel-enter'), 400);
    content.innerHTML = createChartLoading(loadingText || '加载中...');
    return content;
}

function getPanelVersion() {
    return _panelVersion;
}

function createChartLoading(text) {
    return `
        <div class="chart-loading">
            <div class="loading"><div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div></div>
            <div class="loading-text">${escapeHtml(text || '加载价格数据...')}</div>
        </div>
    `;
}

// ===== 关闭面板按钮 =====
function closeDetailPanel(e) {
    console.log('[ClosePanel] called', e && e.type);
    var panel = document.getElementById('detail-panel');
    console.log('[ClosePanel] panel:', panel, 'classes:', panel ? panel.className : 'N/A');
    if (panel) {
        panel.classList.remove('active');
        // Force hide as fallback
        panel.style.display = 'none';
        console.log('[ClosePanel] hidden, display:', panel.style.display);
    }
    if (typeof priceChart !== 'undefined' && priceChart) {
        priceChart.destroy();
        priceChart = null;
    }
}

// Document-level fallback: catch close button clicks via event delegation
document.addEventListener('click', function(e) {
    const btn = e.target.closest('#close-detail');
    if (btn) {
        console.log('[ClosePanel] delegated click');
        closeDetailPanel(e);
    }
});

function createChartEmpty(itemId) {
    const safeId = escapeJsString(itemId);
    return `
        <div class="chart-empty">
            <div class="empty-icon">📊</div>
            <div class="empty-title">暂无价格数据</div>
            <div class="empty-subtitle">查询 "${escapeHtml(itemId)}" 后将显示价格历史</div>
            <button class="empty-btn" onclick="queryItemPrice('${safeId}')"><span>立即查询</span></button>
        </div>
    `;
}

function createChartError(message) {
    return `
        <div class="chart-error">
            <div class="error-icon">⚠️</div>
            <div class="error-title">加载失败</div>
            <div class="error-message">${escapeHtml(message)}</div>
        </div>
    `;
}

// 公共状态样式
(function() {
    const s = document.createElement('style');
    s.textContent = `
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
    `;
    document.head.appendChild(s);
})();

// ===== 更多功能菜单 =====

function toggleMoreMenu() {
    const menu = document.getElementById('more-menu');
    if (menu) menu.classList.toggle('active');
}

function closeMoreMenu() {
    const menu = document.getElementById('more-menu');
    if (menu) menu.classList.remove('active');
}

// 点击其他地方关闭菜单
document.addEventListener('click', (e) => {
    const menu = document.getElementById('more-menu');
    const btn = document.getElementById('more-menu-btn');
    if (menu && !menu.contains(e.target) && (!btn || !btn.contains(e.target))) {
        menu.classList.remove('active');
    }
});

// 更多菜单按钮事件
document.getElementById('more-menu-btn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleMoreMenu();
});

// ===== 搜索建议（模态框用） =====

async function fetchSuggestionsForModal(query, suggestionsDiv, input) {
    if (!query || query.length < 1) {
        suggestionsDiv.classList.remove('active');
        return;
    }

    try {
        const res = await fetch(`/api/suggest?q=${encodeURIComponent(query)}`);
        const data = await res.json();

        if (!data.suggestions || data.suggestions.length === 0) {
            suggestionsDiv.classList.remove('active');
            return;
        }

        suggestionsDiv.innerHTML = '';
        data.suggestions.forEach(item => {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.textContent = item;
            div.addEventListener('click', () => {
                input.value = item;
                suggestionsDiv.classList.remove('active');
            });
            suggestionsDiv.appendChild(div);
        });

        suggestionsDiv.classList.add('active');
    } catch (err) {
        suggestionsDiv.classList.remove('active');
    }
}

// ===== 加载关注列表 =====

async function loadWatchlist() {
    const list = document.getElementById('watchlist');
    if (!list) return;

    try {
        const res = await fetch(`${API_BASE}/api/watchlist`);
        const data = await res.json();
        const watchlist = data.watchlist || [];
        const header = list.previousElementSibling;
        list.textContent = '';

        if (watchlist.length === 0) {
            list.classList.add('collapsed');
            if (header) header.classList.add('collapsed');
            return;
        }

        list.classList.remove('collapsed');
        if (header) header.classList.remove('collapsed');

        watchlist.forEach((watch, index) => {
            const div = document.createElement('div');
            div.className = 'list-item watch-item';
            div.style.animationDelay = `${index * 100}ms`;

            const frequencyText = {
                'daily': '每天',
                'hourly': '每小时',
                'weekly': '每周'
            }[watch.frequency] || watch.frequency;

            const contentText = {
                'top3_sellers': '前3卖家',
                'top3_buyers': '前3买家',
                'price_change': '价格变动',
                'all': '全部'
            }[watch.content] || watch.content;

            const headerRow = document.createElement('div');
            headerRow.className = 'item-header';

            const nameSpan = document.createElement('span');
            nameSpan.className = 'item-name';
            nameSpan.textContent = watch.item_name;

            const badgeSpan = document.createElement('span');
            badgeSpan.className = 'item-badge';
            badgeSpan.textContent = frequencyText;

            headerRow.append(nameSpan, badgeSpan);
            div.appendChild(headerRow);

            const subDiv = document.createElement('div');
            subDiv.className = 'item-sub';
            subDiv.textContent = `${watch.time} | ${contentText}`;
            div.appendChild(subDiv);

            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'item-actions';

            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.className = 'action-btn danger';
            removeButton.appendChild(document.createElement('span')).textContent = '移除';
            removeButton.addEventListener('click', (event) => {
                event.stopPropagation();
                removeWatchItem(watch.item_id);
            });

            actionsDiv.appendChild(removeButton);
            div.appendChild(actionsDiv);
            list.appendChild(div);
        });
    } catch (err) {
        console.error('加载关注列表失败:', err);
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-text">加载失败</div>
                <div class="empty-state-sub">请刷新页面重试</div>
            </div>
        `;
    }
}

async function removeWatchItem(itemId) {
    if (!confirm('确定要移除此关注吗？')) return;

    try {
        const res = await fetch(`${API_BASE}/api/watchlist/${itemId}`, {
            method: 'DELETE',
        });

        if (res.ok) {
            showToast('已移除关注', 'success');
            loadWatchlist();
        } else {
            showToast('移除失败', 'error');
        }
    } catch (err) {
        showToast('移除失败', 'error');
    }
}

// ===== 按钮事件绑定 =====

// 确保函数在全局作用域（HTML onclick 需要）
window.showAddFavoriteModal = function() {
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = 'add-favorite-modal';
    modal.innerHTML = `
        <div class="modal-content add-modal-content">
            <div class="modal-decoration-top"></div>
            <button class="modal-close-btn" onclick="document.getElementById('add-favorite-modal').remove()">&times;</button>
            <h2>添加收藏</h2>
            <div class="add-modal-form">
                <div class="form-group">
                    <label class="form-label">物品名称</label>
                    <input type="text" id="fav-item-input" class="form-input" placeholder="输入物品名称（如：充沛赋能）" autocomplete="off">
                    <div id="fav-suggestions" class="suggestions"></div>
                </div>
                <div class="form-actions">
                    <button class="form-btn secondary" onclick="document.getElementById('add-favorite-modal').remove()">取消</button>
                    <button class="form-btn primary" onclick="confirmAddFavorite()">添加</button>
                </div>
            </div>
            <div class="modal-decoration-bottom"></div>
        </div>
    `;
    document.body.appendChild(modal);

    const input = document.getElementById('fav-item-input');
    const suggestions = document.getElementById('fav-suggestions');
    let debounceTimer;

    input.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchSuggestionsForModal(e.target.value, suggestions, input);
        }, 300);
    });

    input.focus();
};

window.showAlertModal = function() {
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = 'add-alert-modal';
    modal.innerHTML = `
        <div class="modal-content add-modal-content">
            <div class="modal-decoration-top"></div>
            <button class="modal-close-btn" onclick="document.getElementById('add-alert-modal').remove()">&times;</button>
            <h2>添加价格提醒</h2>
            <div class="add-modal-form">
                <div class="form-group">
                    <label class="form-label">物品名称</label>
                    <input type="text" id="alert-item-input" class="form-input" placeholder="输入物品名称" autocomplete="off">
                    <div id="alert-suggestions" class="suggestions"></div>
                </div>
                <div class="form-group">
                    <label class="form-label">提醒方向</label>
                    <select id="alert-direction" class="form-select">
                        <option value="below">低于目标价格时提醒</option>
                        <option value="above">高于目标价格时提醒</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">目标价格 (白金)</label>
                    <input type="number" id="alert-price" class="form-input" placeholder="输入价格" min="1">
                </div>
                <div class="form-group">
                    <label class="form-label">备注 (可选)</label>
                    <input type="text" id="alert-note" class="form-input" placeholder="添加备注信息">
                </div>
                <div class="form-actions">
                    <button class="form-btn secondary" onclick="document.getElementById('add-alert-modal').remove()">取消</button>
                    <button class="form-btn primary" onclick="confirmAddAlert()">添加提醒</button>
                </div>
            </div>
            <div class="modal-decoration-bottom"></div>
        </div>
    `;
    document.body.appendChild(modal);

    const input = document.getElementById('alert-item-input');
    const suggestions = document.getElementById('alert-suggestions');
    let debounceTimer;

    input.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchSuggestionsForModal(e.target.value, suggestions, input);
        }, 300);
    });

    input.focus();
};

window.showAddWatchModal = function() {
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = 'add-watch-modal';
    modal.innerHTML = `
        <div class="modal-content add-modal-content">
            <div class="modal-decoration-top"></div>
            <button class="modal-close-btn" onclick="document.getElementById('add-watch-modal').remove()">&times;</button>
            <h2>添加定时关注</h2>
            <div class="add-modal-form">
                <div class="form-group">
                    <label class="form-label">物品名称</label>
                    <input type="text" id="watch-item-input" class="form-input" placeholder="输入物品名称" autocomplete="off">
                    <div id="watch-suggestions" class="suggestions"></div>
                </div>
                <div class="form-group">
                    <label class="form-label">关注频率</label>
                    <select id="watch-frequency" class="form-select">
                        <option value="daily">每天</option>
                        <option value="hourly">每小时</option>
                        <option value="weekly">每周</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">推送时间</label>
                    <input type="time" id="watch-time" class="form-input" value="09:00">
                </div>
                <div class="form-group">
                    <label class="form-label">关注内容</label>
                    <select id="watch-content" class="form-select">
                        <option value="top3_sellers">前3个最低卖家</option>
                        <option value="top3_buyers">前3个最高买家</option>
                        <option value="price_change">价格变动</option>
                        <option value="all">全部信息</option>
                    </select>
                </div>
                <div class="form-actions">
                    <button class="form-btn secondary" onclick="document.getElementById('add-watch-modal').remove()">取消</button>
                    <button class="form-btn primary" onclick="confirmAddWatch()">添加关注</button>
                </div>
            </div>
            <div class="modal-decoration-bottom"></div>
        </div>
    `;
    document.body.appendChild(modal);

    const input = document.getElementById('watch-item-input');
    const suggestions = document.getElementById('watch-suggestions');
    let debounceTimer;

    input.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchSuggestionsForModal(e.target.value, suggestions, input);
        }, 300);
    });

    input.focus();
};

// 确认添加函数
window.confirmAddFavorite = async function() {
    const input = document.getElementById('fav-item-input');
    const itemName = input.value.trim();
    if (!itemName) {
        showToast('请输入物品名称', 'warning');
        return;
    }

    try {
        const res = await fetch(`/api/resolve/${encodeURIComponent(itemName)}`);
        const data = await res.json();

        let itemId;
        if (data.found) {
            itemId = data.item_id;
        } else {
            itemId = itemName;
        }

        await addFavorite(itemId);
        showToast(`已添加收藏: ${itemName}`, 'success');
        document.getElementById('add-favorite-modal').remove();
        loadSidebar();
    } catch (err) {
        showToast('添加收藏失败', 'error');
    }
};

window.confirmAddAlert = async function() {
    const itemInput = document.getElementById('alert-item-input');
    const directionSelect = document.getElementById('alert-direction');
    const priceInput = document.getElementById('alert-price');
    const noteInput = document.getElementById('alert-note');

    const itemName = itemInput.value.trim();
    const direction = directionSelect.value;
    const price = parseInt(priceInput.value);
    const note = noteInput.value.trim();

    if (!itemName) {
        showToast('请输入物品名称', 'warning');
        return;
    }

    if (!price || price <= 0) {
        showToast('请输入有效的价格', 'warning');
        return;
    }

    try {
        const res = await fetch(`/api/resolve/${encodeURIComponent(itemName)}`);
        const data = await res.json();

        let itemId;
        if (data.found) {
            itemId = data.item_id;
        } else {
            itemId = itemName;
        }

        await addAlert(itemId, direction, price, note);
        showToast(`已添加提醒: ${itemName} ${direction === 'below' ? '低于' : '高于'} ${price}p`, 'success');
        document.getElementById('add-alert-modal').remove();
        loadSidebar();
    } catch (err) {
        showToast('添加提醒失败', 'error');
    }
};

window.confirmAddWatch = async function() {
    const itemInput = document.getElementById('watch-item-input');
    const frequencySelect = document.getElementById('watch-frequency');
    const timeInput = document.getElementById('watch-time');
    const contentSelect = document.getElementById('watch-content');

    const itemName = itemInput.value.trim();
    const frequency = frequencySelect.value;
    const time = timeInput.value;
    const content = contentSelect.value;

    if (!itemName) {
        showToast('请输入物品名称', 'warning');
        return;
    }

    try {
        const res = await fetch(`/api/resolve/${encodeURIComponent(itemName)}`);
        const data = await res.json();

        let itemId;
        if (data.found) {
            itemId = data.item_id;
        } else {
            itemId = itemName;
        }

        const response = await fetch(`${API_BASE}/api/watchlist`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                item_id: itemId,
                item_name: itemName,
                frequency: frequency,
                time: time,
                content: content,
            })
        });

        if (response.ok) {
            showToast(`已添加关注: ${itemName}`, 'success');
            document.getElementById('add-watch-modal').remove();
            loadSidebar();
        } else {
            showToast('添加关注失败', 'error');
        }
    } catch (err) {
        showToast('添加关注失败', 'error');
    }
};

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(loadWatchlist, 600);
});
