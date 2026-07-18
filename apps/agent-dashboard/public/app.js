const REFRESH_INTERVAL = 5000;

const $loading = document.getElementById('stateLoading');
const $error = document.getElementById('stateError');
const $errorMsg = document.getElementById('errorMessage');
const $empty = document.getElementById('stateEmpty');
const $dashboard = document.getElementById('dashboard');
const $countdown = document.getElementById('refreshCountdown');
const $lastUpdated = document.getElementById('lastUpdated');
const $sectionErrors = document.getElementById('sectionErrors');

let countdown = REFRESH_INTERVAL / 1000;
let timer = null;
let fetchTimer = null;
let requestSequence = 0;

function showState(state) {
  $loading.classList.add('hidden');
  $error.classList.add('hidden');
  $empty.classList.add('hidden');
  $dashboard.classList.add('hidden');
  if (state === 'loading') $loading.classList.remove('hidden');
  else if (state === 'error') $error.classList.remove('hidden');
  else if (state === 'empty') $empty.classList.remove('hidden');
  else if (state === 'dashboard') $dashboard.classList.remove('hidden');
}

function badgeClass(status) {
  const s = typeof status === 'string' ? status.toLowerCase() : '';
  if (s === 'completed') return 'badge-success';
  if (s === 'active' || s === 'in_progress') return 'badge-success';
  if (s === 'standby' || s === 'available' || s === 'planned') return 'badge-muted';
  if (s === 'failed' || s === 'cancelled' || s === 'error' || s === 'budget_exhausted' || s === 'permission_blocked') return 'badge-danger';
  if (s === 'blocked' || s === 'pending' || s === 'awaiting_user' || s === 'ready') return 'badge-warning';
  return 'badge-muted';
}

function milestoneDotClass(status) {
  const s = typeof status === 'string' ? status.toLowerCase() : '';
  if (s === 'completed') return 'completed';
  if (s === 'in_progress') return 'in_progress';
  return 'planned';
}

function renderProject(project) {
  if (!project) return '<p style="color:var(--text-muted)">项目数据不可用</p>';

  let html = '<table class="prop-table">';
  if (project.project) html += `<tr><th>项目名称</th><td>${esc(project.project)}</td></tr>`;
  if (project.phase) html += `<tr><th>当前阶段</th><td><span class="badge badge-info">${esc(project.phase)}</span></td></tr>`;
  if (project.summary) html += `<tr><th>摘要</th><td>${esc(project.summary)}</td></tr>`;
  if (project.updatedAt) html += `<tr><th>更新时间</th><td>${esc(project.updatedAt)}</td></tr>`;
  html += '</table>';

  if (project.milestones && Array.isArray(project.milestones)) {
    html += '<div style="margin-top:12px"><strong style="font-size:0.85rem">里程碑</strong>';
    html += '<ul class="milestone-list" style="margin-top:6px">';
    for (const m of project.milestones) {
      html += `<li class="milestone-item">
        <span class="milestone-dot ${milestoneDotClass(m.status)}"></span>
        <span>${esc(m.name || m.id)}</span>
        <span class="badge ${badgeClass(m.status)}" style="margin-left:auto">${esc(statusLabel(m.status))}</span>
      </li>`;
    }
    html += '</ul></div>';
  }

  return html;
}

function renderTasks(tasks) {
  if (!tasks || tasks.length === 0) return '<p style="color:var(--text-muted)">暂无任务数据</p>';

  let html = '';
  for (const t of tasks) {
    if (t._error) {
      html += `<div class="corrupt-notice">${t._file ? esc(t._file) + ': ' : ''}数据损坏 — ${esc(t._message || '')}</div>`;
      continue;
    }
    const displayName = t.title || humanizeTaskId(t.id) || t._file || '未知任务';
    const primaryStatus = t.runtime?.status || t.approval?.status || t.lifecycle;
    html += `<div class="task-item">
      <div class="task-heading">
        <h3>${esc(displayName)}</h3>
        ${t.id ? `<span class="task-id" title="稳定任务编号">${esc(t.id)}</span>` : ''}
      </div>
      ${primaryStatus ? `<p class="task-status">当前状态: <span class="badge ${badgeClass(primaryStatus)}">${esc(statusLabel(primaryStatus))}</span></p>` : ''}
      ${t.runtime?.owner ? `<p>当前负责人: ${esc(t.runtime.owner)}</p>` : t.executor ? `<p>执行者: ${esc(t.executor)}</p>` : ''}
      <details class="technical-details">
        <summary>技术详情</summary>
        ${t.kind ? `<p>记录类型: ${esc(kindLabel(t.kind))}</p>` : ''}
        ${t.lifecycle ? `<p>合同生命周期: ${esc(statusLabel(t.lifecycle))}</p>` : ''}
        ${t.riskLevel ? `<p>风险等级: ${esc(t.riskLevel)}</p>` : ''}
        ${t.authority ? `<p>执行权限: ${esc(authorityLabel(t.authority))}</p>` : ''}
        <p>复杂度: ${esc(complexityLabel(t.complexity))}</p>
        ${t.model ? `<p>执行模型: ${esc(t.model)}</p>` : ''}
        ${t.modelPolicy ? `<p>模型策略: v${esc(t.modelPolicy.version)}${t.modelPolicy.defaultApplied ? '（默认 Flash）' : ''}</p>` : ''}
        ${t.approval?.status ? `<p>审批状态: ${esc(statusLabel(t.approval.status))}</p>` : ''}
        ${t.requestedBy ? `<p>请求者: ${esc(t.requestedBy)}</p>` : ''}
        ${renderRuntime(t.runtime, true)}
        ${renderBudget(t.budget, t.runtime?.usage)}
        <p>结果回执: ${t.result?.available ? `已生成（${esc(formatNumber(t.result.sizeBytes))} bytes）` : '尚未生成'}</p>
      </details>
    </div>`;
  }
  return html || '<p style="color:var(--text-muted)">无有效任务</p>';
}

function renderRuntime(runtime, detailsOnly = false) {
  if (!runtime) return detailsOnly ? '<p>运行状态: 尚未创建</p>' : '';
  return `<div class="task-detail">
    <p>运行状态: <span class="badge ${badgeClass(runtime.status)}">${esc(statusLabel(runtime.status || 'UNKNOWN'))}</span></p>
    ${runtime.updatedAt ? `<p>运行态更新: ${esc(runtime.updatedAt)}</p>` : ''}
    ${runtime.budgetReason ? `<p class="text-danger">停止原因: ${esc(runtime.budgetReason)}</p>` : ''}
    ${runtime.verification ? `<p>验证: ${runtime.verification.ok ? '通过' : '未通过'}</p>` : ''}
  </div>`;
}

function statusLabel(value) {
  const labels = {
    ACTIVE: '进行中', APPROVED: '已批准', COMPLETED: '已完成', COMPLETE: '已完成',
    PLANNED: '计划中', READY: '可以开始', RUNNING: '正在执行', VERIFYING: '正在验证',
    AWAITING_USER: '等待你的决定', AWAITING_CODEX_REVIEW: '等待 Codex 复核',
    READY_FOR_NEXT_CONTRACT: '可以起草下一任务', BLOCKED: '受阻', INTERRUPTED: '已中断',
    FAILED: '失败', CANCELLED: '已取消', BUDGET_EXHAUSTED: '预算已用尽',
    PERMISSION_BLOCKED: '等待权限', VERIFICATION_FAILED: '验证未通过'
  };
  return labels[String(value).toUpperCase()] || String(value).replaceAll('_', ' ');
}

function kindLabel(value) {
  return ({ contract: '已批准任务', draft: '任务草案', 'runtime-only': '仅运行记录' })[value] || value;
}

function authorityLabel(value) {
  return ({ CODEX_ONLY: '仅 Codex', DELEGATABLE: '可委派给 OpenCode' })[value] || value;
}

function complexityLabel(value) {
  return ({ LOW: '低', MEDIUM: '中', HIGH: '高' })[value] || '旧任务 / 未声明';
}

function humanizeTaskId(value) {
  return value ? `任务 ${value}` : '';
}

function renderBudget(budget, usage) {
  if (!budget && !usage) return '';
  return `<div class="budget-grid">
    <strong>预算 / 已用</strong>
    <span>输入 ${esc(formatNumber(usage?.inputTokens))} / ${esc(formatNumber(budget?.maxInputTokens))}</span>
    <span>输出 ${esc(formatNumber(usage?.outputTokens))} / ${esc(formatNumber(budget?.maxOutputTokens))}</span>
    <span>成本 ${esc(formatCost(usage?.cost))} / ${esc(formatCost(budget?.maxCost))} ${esc(budget?.currency || 'USD')}</span>
  </div>`;
}

function renderAgents(agents) {
  const list = agents && Array.isArray(agents.agents) ? agents.agents : [];
  if (list.length === 0) return '<p style="color:var(--text-muted)">暂无 Agent 数据</p>';

  let html = '';
  for (const a of list) {
    html += `<div class="agent-item">
      <h3>${esc(a.name || a.id)}</h3>
      ${a.role ? `<p>角色: ${esc(a.role)}</p>` : ''}
      ${a.status ? `<p>状态: <span class="badge ${badgeClass(a.status)}">${esc(statusLabel(a.status))}</span></p>` : ''}
    </div>`;
  }
  return html;
}

function renderEnv(envGate) {
  let html = '';
  if (envGate) {
    html += '<table class="prop-table">';
    const keys = Object.keys(envGate);
    for (const key of keys) {
      const val = envGate[key];
      if (typeof val === 'object' && val !== null) {
        html += `<tr><th>${esc(key)}</th><td><pre style="font-size:0.75rem;color:var(--text-muted);margin:0">${esc(JSON.stringify(val, null, 2))}</pre></td></tr>`;
      } else {
        html += `<tr><th>${esc(key)}</th><td>${esc(String(val))}</td></tr>`;
      }
    }
    html += '</table>';
  } else {
    html += '<p style="color:var(--text-muted)">环境门禁数据不可用</p>';
  }
  return html;
}

function renderErrors(errors) {
  if (!errors || errors.length === 0) {
    $sectionErrors.style.display = 'none';
    return;
  }
  $sectionErrors.style.display = '';
  const body = document.getElementById('errorsBody');
  body.innerHTML = errors.map((e) => `<div class="corrupt-notice">${esc(e?.source || 'unknown')}: ${esc(e?.code || String(e))}${e?.file ? ` (${esc(e.file)})` : ''}</div>`).join('');
}

function esc(str) {
  if (str === null || str === undefined) return '';
  if (typeof str !== 'string') str = String(str);
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return str.replace(/[&<>"']/g, (c) => map[c]);
}

function formatNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('zh-CN') : '—';
}

function formatCost(value) {
  return typeof value === 'number' && Number.isFinite(value) ? `$${value.toFixed(4)}` : '—';
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    return data;
  } catch (e) {
    throw e;
  }
}

function renderDashboard(data) {
  document.getElementById('projectBody').innerHTML = renderProject(data.project);
  document.getElementById('tasksBody').innerHTML = renderTasks(data.tasks);
  document.getElementById('agentsBody').innerHTML = renderAgents(data.agents);
  document.getElementById('envBody').innerHTML = renderEnv(data.environmentGate);
  $lastUpdated.textContent = '最后更新: ' + (data.lastUpdated || '未知');
  renderErrors(data.errors);

  const hasContent = data.project || (data.tasks && data.tasks.length > 0) ||
    (data.agents && data.agents.agents && data.agents.agents.length > 0);
  if (hasContent) {
    showState('dashboard');
  } else {
    showState('empty');
  }
}

async function refresh(showLoading = false) {
  const sequence = ++requestSequence;
  if (showLoading) showState('loading');
  try {
    const data = await fetchStatus();
    if (sequence !== requestSequence) return;
    renderDashboard(data);
  } catch (e) {
    if (sequence !== requestSequence) return;
    $errorMsg.textContent = '请求失败: ' + e.message;
    showState('error');
  } finally {
    if (sequence === requestSequence) scheduleNext();
  }
}

function resetCountdown() {
  countdown = REFRESH_INTERVAL / 1000;
  $countdown.textContent = `${countdown}s 后刷新`;
}

function startTimers() {
  clearInterval(timer);
  clearTimeout(fetchTimer);
  resetCountdown();
  timer = setInterval(() => {
    countdown = Math.max(0, countdown - 1);
    $countdown.textContent = `${countdown}s 后刷新`;
  }, 1000);
}

function scheduleNext() {
  clearTimeout(fetchTimer);
  startTimers();
  fetchTimer = setTimeout(() => refresh(false), REFRESH_INTERVAL);
}

document.getElementById('btnRefresh').addEventListener('click', () => {
  clearTimeout(fetchTimer);
  refresh(false);
});

document.getElementById('btnErrorRetry').addEventListener('click', () => {
  clearTimeout(fetchTimer);
  refresh(true);
});

refresh(true);
