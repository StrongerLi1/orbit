const dateKey = (date = new Date()) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const shiftDate = (key, amount) => { const date = new Date(`${key}T00:00:00`); date.setDate(date.getDate() + amount); return dateKey(date); };
const state = { user: null, authMode: 'login', bookmarks: [], todos: [], plans: [], folders: [], excerpts: [], featuredExcerptId: '', category: '全部', search: '', planDate: dateKey(), admin: { users: [], roles: [], permissions: [], loading: false }, netdisk: { keyword: '', loading: false, source: '', results: [], raw: null, error: '', selectedSource: '全部' }, captcha: { login: '', register: '' } };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
const planTypeLabels = { daily: '日常', weekly: '周常', monthly: '月度' };
const netdiskSourceLabels = { baidu: '百度网盘', quark: '夸克网盘', aliyun: '阿里云盘', xunlei: '迅雷云盘', tianyi: '天翼云盘', uc: 'UC 网盘', mobile: '移动云盘', pikpak: 'PikPak', '123pan': '123 网盘', '115': '115 网盘' };
const hasPermission = (permission) => state.user?.permissions?.includes(permission);
const canManageAccess = () => hasPermission('users:manage') || hasPermission('roles:manage');

function isPlanActive(plan, date) { return date >= plan.startDate && (!plan.endDate || date <= plan.endDate); }
function plansForDate(date) { return state.plans.filter((plan) => isPlanActive(plan, date)); }
function periodKey(plan, date) {
  if (plan.frequencyType === 'monthly') return `month:${date.slice(0, 7)}`;
  if (plan.frequencyType === 'weekly') {
    const value = new Date(`${date}T00:00:00`);
    value.setDate(value.getDate() - ((value.getDay() + 6) % 7));
    return `week:${dateKey(value)}`;
  }
  return `day:${date}`;
}
function countInPeriod(plan, date) {
  const wanted = periodKey(plan, date);
  return Object.entries(plan.completions || {}).reduce((sum, [key, count]) => periodKey(plan, key) === wanted ? sum + Number(count) : sum, 0);
}
function periodLabel(plan) { return plan.frequencyType === 'weekly' ? '本周' : plan.frequencyType === 'monthly' ? '本月' : '今日'; }
function planProgress(plan, date) { return { done: countInPeriod(plan, date), target: Number(plan.targetCount) || 1 }; }
function planHistory(plan, until) {
  if (until < plan.startDate) return [];
  const last = plan.endDate && plan.endDate < until ? plan.endDate : until;
  const keys = new Set();
  for (let cursor = plan.startDate, guard = 0; cursor <= last && guard < 1500; cursor = shiftDate(cursor, 1), guard++) keys.add(periodKey(plan, cursor));
  return [...keys].map((key) => {
    const done = Object.entries(plan.completions || {}).reduce((sum, [date, count]) => periodKey(plan, date) === key ? sum + Number(count) : sum, 0);
    return { key, done, success: done >= plan.targetCount };
  });
}

async function request(url, options = {}, retry = true) {
  const response = await fetch(url, { headers: { 'content-type': 'application/json' }, ...options });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401 && retry && !url.startsWith('/api/auth/login') && !url.startsWith('/api/auth/register') && !url.startsWith('/api/auth/refresh') && !url.startsWith('/api/auth/logout')) {
    const refreshed = await refreshAuth();
    if (refreshed) return request(url, options, false);
  }
  if (response.status === 401) showAuth('login');
  if (!response.ok) throw new Error(result.error || '操作失败');
  return result;
}

async function refreshAuth() {
  const response = await fetch('/api/auth/refresh', { method:'POST', headers: { 'content-type': 'application/json' } });
  if (!response.ok) return false;
  state.user = await response.json();
  return true;
}

function resetToLoginRoute() {
  if (location.pathname !== '/' || location.hash) history.replaceState(null, '', '/');
}

function showAuth(mode = 'login') {
  state.authMode = mode;
  state.user = null;
  resetToLoginRoute();
  $('#auth-screen').hidden = false;
  $('.app-shell').hidden = true;
  $('#login-form').hidden = mode !== 'login';
  $('#register-form').hidden = mode !== 'register';
  $('#auth-title').textContent = mode === 'login' ? '登录你的空间' : '注册新账号';
  $('#auth-switch').textContent = mode === 'login' ? '还没有账号？注册一个' : '已有账号？返回登录';
  updateAuthCaptchaState(mode);
  setTimeout(() => $(`#${mode}-form input`)?.focus(), 50);
}

function showApp() {
  $('#auth-screen').hidden = true;
  $('.app-shell').hidden = false;
  $('#user-chip').textContent = state.user ? `${state.user.username}${state.user.isAdmin ? ' · 管理员' : ''}` : '';
  $('#admin-nav').hidden = !canManageAccess();
}

async function authSubmit(path, form) {
  const mode = form.id === 'register-form' ? 'register' : 'login';
  if (!state.captcha[mode]) {
    toast('请先完成抓娃娃验证');
    return;
  }
  const payload = Object.fromEntries(new FormData(form));
  state.user = await request(path, { method:'POST', body:JSON.stringify({ ...payload, playcaptchaToken: state.captcha[mode] }) });
  showApp();
  location.hash = 'dashboard';
  showPage('dashboard');
  await load();
}

function updateAuthCaptchaState(mode) {
  const verified = Boolean(state.captcha[mode]);
  const button = $(`[data-auth-submit="${mode}"]`);
  const status = $(`[data-captcha-status="${mode}"]`);
  if (button) button.disabled = !verified;
  if (status) {
    status.textContent = verified ? '验证完成，可以继续。' : (mode === 'login' ? '完成抓娃娃验证后即可登录。' : '完成抓娃娃验证后即可注册。');
    status.classList.toggle('ready', verified);
  }
}

function resetAuthCaptcha(mode) {
  state.captcha[mode] = '';
  updateAuthCaptchaState(mode);
  window.orbitPlayCaptcha?.reset(mode);
}

function mountPlayCaptcha(mode) {
  const element = $(`[data-playcaptcha="${mode}"]`);
  if (!element || !window.orbitPlayCaptcha) return;
  window.orbitPlayCaptcha.mount({
    element,
    mode,
    onVerified: async () => {
      try {
        const result = await request('/api/auth/playcaptcha', { method:'POST', body:JSON.stringify({ mode }) }, false);
        state.captcha[mode] = result.token || '';
        updateAuthCaptchaState(mode);
      } catch (error) {
        resetAuthCaptcha(mode);
        toast(error.message);
      }
    },
  });
}

function mountPlayCaptchas() {
  mountPlayCaptcha('login');
  mountPlayCaptcha('register');
  updateAuthCaptchaState('login');
  updateAuthCaptchaState('register');
}

async function load() {
  [state.bookmarks, state.todos, state.plans, state.folders, state.excerpts] = await Promise.all(['bookmarks','todos','plans','folders','excerpts'].map((type) => request(`/api/${type}`)));
  if (!state.excerpts.some((excerpt) => excerpt.id === state.featuredExcerptId)) chooseFeaturedExcerpt();
  render();
}

function chooseFeaturedExcerpt() {
  if (!state.excerpts.length) { state.featuredExcerptId = ''; return; }
  const choices = state.excerpts.filter((excerpt) => excerpt.id !== state.featuredExcerptId);
  const pool = choices.length ? choices : state.excerpts;
  state.featuredExcerptId = pool[Math.floor(Math.random() * pool.length)].id;
}

function render() {
  const activeTodos = state.todos.filter((t) => !t.completed);
  const doneTodos = state.todos.filter((t) => t.completed);
  const todayPlans = plansForDate(dateKey());
  const donePlans = todayPlans.filter((plan) => { const progress = planProgress(plan, dateKey()); return progress.done >= progress.target; }).length;
  $('#stats').innerHTML = [
    ['◇', state.bookmarks.length, '个收藏网站'],
    ['✓', activeTodos.length, '项待办未完成'],
    ['◷', `${donePlans}/${todayPlans.length}`, '项今日计划']
  ].map(([icon,num,label]) => `<div class="stat"><span class="stat-icon">${icon}</span><div><strong>${num}</strong><small>${label}</small></div></div>`).join('');
  $('#dashboard-plans').innerHTML = todayPlans.slice().sort((a,b)=>a.time.localeCompare(b.time)).slice(0,4).map(planHtml).join('') || empty('今天还没有计划');
  $('#dashboard-todos').innerHTML = activeTodos.slice(0,4).map(todoHtml).join('') || empty('待办都完成啦');
  $('#dashboard-bookmarks').innerHTML = state.bookmarks.slice(0,4).map((b) => `<a class="mini-bookmark" href="${escapeHtml(b.url)}" target="_blank" rel="noreferrer"><span class="site-icon">${escapeHtml(b.title[0])}</span><span><strong>${escapeHtml(b.title)}</strong><small>${escapeHtml(host(b.url))}</small></span></a>`).join('') || empty('还没有收藏');
  const featured = state.excerpts.find((excerpt) => excerpt.id === state.featuredExcerptId);
  $('#featured-excerpt').innerHTML = featured ? `<blockquote>“${escapeHtml(featured.content)}”</blockquote><button class="excerpt-source" data-page-link="excerpts">— ${escapeHtml([featured.author, featured.source].filter(Boolean).join(' · ') || '未注明出处')}</button>` : `<button class="empty-excerpt" data-add="excerpts">＋ 留下一句今天想记住的话</button>`;
  $('#excerpt-count').textContent = `${state.excerpts.length} 条摘录`;
  $('#excerpts-grid').innerHTML = state.excerpts.slice().sort((a, b) => (b.excerptDate || b.createdAt).localeCompare(a.excerptDate || a.createdAt)).map(excerptHtml).join('') || empty('还没有摘录，先留下第一句话吧');

  const categoryOrder = ['AI 与智能体', '开发与学习', '科研与阅读', '校园与办公', '实用工具', 'Mac 软件', '网络与账号', '影音与游戏', '社区与生活', '其他收藏'];
  const categories = state.folders.map((folder) => folder.name).sort((a, b) => {
    const left = categoryOrder.indexOf(a), right = categoryOrder.indexOf(b);
    return (left < 0 ? 999 : left) - (right < 0 ? 999 : right) || a.localeCompare(b, 'zh-CN');
  });
  $('#category-filters').innerHTML = categories.map((c) => `<button class="filter ${state.category === c ? 'active':''}" data-category="${escapeHtml(c)}">${escapeHtml(c)}</button>`).join('');
  let visibleBookmarks = state.bookmarks.filter((b) => state.category === '全部' || b.category === state.category);
  if (state.search) visibleBookmarks = visibleBookmarks.filter((b) => `${b.title} ${b.url} ${b.note} ${b.category}`.toLowerCase().includes(state.search));
  visibleBookmarks.sort((a, b) => Number(b.favorite) - Number(a.favorite) || a.title.localeCompare(b.title, 'zh-CN'));
  $('#bookmarks-grid').innerHTML = visibleBookmarks.map(bookmarkHtml).join('') || empty('没有找到匹配的收藏');
  renderPlanStatistics();
  $('#todos-active').innerHTML = activeTodos.map(todoHtml).join('') || empty('现在没有待办');
  $('#todos-completed').innerHTML = doneTodos.map(todoHtml).join('') || empty('完成的事项会出现在这里');
  $('#active-count').textContent = `${activeTodos.length} 项`;
  renderNetdisk();
  renderAdmin();
}

function renderNetdisk() {
  const status = $('#netdisk-status');
  const filters = $('#netdisk-filters');
  const results = $('#netdisk-results');
  if (!status || !results) return;
  if (state.netdisk.loading) {
    status.innerHTML = '<span class="loading-dot"></span> 正在搜索…';
    if (filters) filters.innerHTML = '';
    results.innerHTML = '';
    return;
  }
  if (state.netdisk.error) {
    status.innerHTML = `<span class="status-error">搜索失败：</span>${escapeHtml(state.netdisk.error)}`;
    if (filters) filters.innerHTML = '';
    results.innerHTML = '';
    return;
  }
  if (!state.netdisk.keyword) {
    status.textContent = '输入关键词后开始搜索。';
    if (filters) filters.innerHTML = '';
    results.innerHTML = '';
    return;
  }
  const sourceCounts = state.netdisk.results.reduce((all, item) => {
    const source = item.source || '其他';
    all[source] = (all[source] || 0) + 1;
    return all;
  }, {});
  const sources = Object.entries(sourceCounts).sort((a, b) => b[1] - a[1] || netdiskSourceName(a[0]).localeCompare(netdiskSourceName(b[0]), 'zh-CN'));
  const selected = state.netdisk.selectedSource || '全部';
  const visible = selected === '全部' ? state.netdisk.results : state.netdisk.results.filter((item) => (item.source || '其他') === selected);
  status.textContent = `“${state.netdisk.keyword}” 找到 ${state.netdisk.results.length} 条结果${selected !== '全部' ? ` · 当前显示 ${visible.length} 条` : ''}${state.netdisk.source ? ` · 来源：${state.netdisk.source}` : ''}`;
  if (filters) {
    filters.innerHTML = state.netdisk.results.length ? [
      `<button class="netdisk-filter ${selected === '全部' ? 'active' : ''}" data-netdisk-source="全部">全部 <span>${state.netdisk.results.length}</span></button>`,
      ...sources.map(([source, count]) => `<button class="netdisk-filter ${selected === source ? 'active' : ''}" data-netdisk-source="${escapeHtml(source)}">${escapeHtml(netdiskSourceName(source))} <span>${count}</span></button>`)
    ].join('') : '';
  }
  results.innerHTML = visible.map(netdiskResultHtml).join('') || empty(selected === '全部' ? '没有搜到结果，换个关键词试试' : '这个网盘类型下没有结果');
}

async function loadAdmin() {
  if (!canManageAccess()) return;
  state.admin.loading = true;
  renderAdmin();
  try {
    const [users, roles, permissions] = await Promise.all([
      request('/api/admin/users'),
      request('/api/admin/roles'),
      request('/api/admin/permissions')
    ]);
    state.admin = { users, roles, permissions, loading: false };
  } catch (error) {
    state.admin.loading = false;
    toast(error.message);
  }
  renderAdmin();
}

function renderAdmin() {
  const users = $('#admin-users');
  const roles = $('#admin-roles');
  if (!users || !roles) return;
  if (!canManageAccess()) {
    users.innerHTML = empty('没有访问用户管理的权限');
    roles.innerHTML = '';
    return;
  }
  if (state.admin.loading) {
    users.innerHTML = empty('正在加载用户…');
    roles.innerHTML = empty('正在加载角色…');
    return;
  }
  users.innerHTML = state.admin.users.map((user) => {
    const isAdmin = user.isAdmin || user.roles.includes('admin');
    const status = user.isBanned ? '已封禁' : '正常';
    const checks = state.admin.roles.map((role) => `<label class="role-check"><input type="checkbox" data-user-role value="${escapeHtml(role.name)}" ${user.roles.includes(role.name) ? 'checked' : ''}>${escapeHtml(role.name)}</label>`).join('');
    const permissionText = user.permissions.map((permission) => rolePermissionLabel(permission)).join(' · ');
    const actions = isAdmin ? '' : `<div class="admin-actions"><button class="secondary" data-admin-ban="${user.isBanned ? 'false' : 'true'}">${user.isBanned ? '解封' : '封禁'}</button><button class="delete-account" data-admin-delete>删除</button></div>`;
    return `<article class="admin-user" data-role-user="${escapeHtml(user.id)}"><div><strong>${escapeHtml(user.username)}</strong><small>${escapeHtml(isAdmin ? '管理员' : '普通用户')} · ${escapeHtml(status)} · ${escapeHtml(user.lastLoginAt || '尚未登录')}</small><p>${escapeHtml(permissionText)}</p></div><div class="admin-controls"><div class="role-checks">${checks}</div>${actions}</div></article>`;
  }).join('') || empty('还没有用户');
  roles.innerHTML = state.admin.roles.map((role) => {
    const permissions = role.permissions.map((permission) => `<span>${escapeHtml(rolePermissionLabel(permission))}</span>`).join('');
    return `<article class="admin-role"><div><strong>${escapeHtml(role.name)}</strong><small>${escapeHtml(role.description)}</small></div><div class="permission-tags">${permissions}</div></article>`;
  }).join('') || empty('还没有角色');
}

function rolePermissionLabel(permission) {
  const found = state.admin.permissions.find((item) => item.name === permission);
  return found ? found.description : permission;
}

function renderPlanStatistics() {
  const selected = plansForDate(state.planDate);
  const executions = selected.reduce((sum, plan) => sum + Number(plan.completions?.[state.planDate] || 0), 0);
  const minutes = selected.reduce((sum, plan) => sum + Number(plan.completions?.[state.planDate] || 0) * Number(plan.duration), 0);
  const periodDone = selected.reduce((sum, plan) => sum + Math.min(countInPeriod(plan, state.planDate), plan.targetCount), 0);
  const periodTarget = selected.reduce((sum, plan) => sum + Number(plan.targetCount), 0);
  const rate = periodTarget ? Math.round(periodDone / periodTarget * 100) : 0;
  $('#plan-date').value = state.planDate;
  const selectedDate = new Date(`${state.planDate}T00:00:00`);
  $('#selected-date-title').textContent = new Intl.DateTimeFormat('zh-CN', { month:'long', day:'numeric', weekday:'short' }).format(selectedDate);
  $('#plan-metrics').innerHTML = [
    ['◷', selected.length, '项进行中计划'],
    ['✓', executions, '次当日打卡'],
    ['⌛', minutes, '分钟已投入'],
    ['↗', `${rate}%`, '当前周期进度']
  ].map(([icon, value, label]) => `<div class="plan-metric"><span>${icon}</span><div><strong>${value}</strong><small>${label}</small></div></div>`).join('');
  $('#plans-list').innerHTML = selected.slice().sort((a,b)=>a.time.localeCompare(b.time)).map(timelineHtml).join('') || empty('这一天没有进行中的计划');

  const days = Array.from({ length: 7 }, (_, index) => shiftDate(state.planDate, index - 6));
  const daily = days.map((key) => {
    const count = plansForDate(key).reduce((sum, plan) => sum + Number(plan.completions?.[key] || 0), 0);
    return { key, count };
  });
  const totalExecutions = daily.reduce((sum, day) => sum + day.count, 0);
  const maxCount = Math.max(1, ...daily.map((day) => day.count));
  $('#chart-average').textContent = `共 ${totalExecutions} 次`;
  $('#completion-chart').innerHTML = daily.map((day) => {
    const date = new Date(`${day.key}T00:00:00`);
    const label = new Intl.DateTimeFormat('zh-CN', { weekday:'short' }).format(date).replace('周', '');
    const height = day.count ? Math.max(Math.round(day.count / maxCount * 100), 8) : 3;
    return `<div class="chart-day" title="${day.key}：执行 ${day.count} 次"><span>${day.count || '—'}</span><div class="chart-track"><i style="height:${height}%" class="${day.key === state.planDate ? 'selected' : ''}"></i></div><small>${label}</small><em>${date.getDate()}</em></div>`;
  }).join('');

  $('#plan-performance').innerHTML = state.plans.slice().sort((a, b) => a.title.localeCompare(b.title, 'zh-CN')).map((plan) => {
    const history = planHistory(plan, state.planDate);
    const success = history.filter((period) => period.success).length;
    const historyRate = history.length ? Math.round(success / history.length * 100) : 0;
    const total = Object.values(plan.completions || {}).reduce((sum, count) => sum + Number(count), 0);
    const current = isPlanActive(plan, state.planDate) ? planProgress(plan, state.planDate) : { done: 0, target: plan.targetCount };
    const width = Math.min(100, Math.round(current.done / current.target * 100));
    return `<article class="performance-item"><div class="performance-main"><span class="plan-dot ${plan.color}"></span><div><div class="performance-title"><h3>${escapeHtml(plan.title)}</h3><span class="type-pill">${planTypeLabels[plan.frequencyType]}</span></div><p>${escapeHtml(plan.startDate)} — ${escapeHtml(plan.endDate || '长期')} · 每${plan.frequencyType === 'daily' ? '日' : plan.frequencyType === 'weekly' ? '周' : '月'} ${plan.targetCount} 次</p></div></div><div class="performance-number"><strong>${historyRate}%</strong><small>${success}/${history.length} 个周期达标</small></div><div class="performance-number"><strong>${total}</strong><small>累计执行</small></div><div class="performance-progress"><span><i style="width:${width}%"></i></span><small>${periodLabel(plan)} ${current.done}/${current.target}</small></div><button class="delete plan-delete" data-delete="plans" data-id="${plan.id}" aria-label="删除计划 ${escapeHtml(plan.title)}">×</button></article>`;
  }).join('') || empty('还没有可统计的计划');
}

function host(url) { try { return new URL(url).hostname.replace(/^www\./,''); } catch { return url; } }
function netdiskSourceName(source = '') { return netdiskSourceLabels[String(source).toLowerCase()] || source || '其他'; }
function folderOptions(selected = '') { return state.folders.map((folder) => `<option value="${escapeHtml(folder.name)}" ${folder.name === selected ? 'selected' : ''}>${escapeHtml(folder.name)}</option>`).join(''); }
function empty(text) { return `<div class="empty">${text}</div>`; }
function planHtml(p) { const progress = planProgress(p, dateKey()); const done = progress.done >= progress.target; return `<div class="plan-item"><span class="plan-time">${p.time}</span><span class="plan-dot ${p.color}"></span><span class="plan-name ${done?'todo-title done':''}">${escapeHtml(p.title)}</span><span class="duration">${periodLabel(p)} ${progress.done}/${progress.target}</span></div>`; }
function timelineHtml(p) { const progress = planProgress(p, state.planDate); const todayCount = Number(p.completions?.[state.planDate] || 0); const done = progress.done >= progress.target; return `<div class="timeline-item recurring"><span class="plan-time">${p.time}</span><span class="plan-dot ${p.color}"></span><div><div class="plan-title-line"><h3 class="${done?'todo-title done':''}">${escapeHtml(p.title)}</h3><span class="type-pill">${planTypeLabels[p.frequencyType]}</span></div><p>${periodLabel(p)} ${progress.done}/${progress.target} 次 · 每次 ${p.duration} 分钟${todayCount ? ` · 今天 ${todayCount} 次` : ''}</p></div><div class="count-stepper"><button data-plan-count="-1" data-id="${p.id}" aria-label="减少 ${escapeHtml(p.title)} 打卡" ${todayCount ? '' : 'disabled'}>−</button><strong>${todayCount}</strong><button data-plan-count="1" data-id="${p.id}" aria-label="完成一次 ${escapeHtml(p.title)}">＋</button></div></div>`; }
function todoHtml(t) { return `<div class="todo-item"><button class="check ${t.completed?'done':''}" data-toggle="todos" data-id="${t.id}">${t.completed?'✓':''}</button><span class="priority ${t.priority}"></span><span class="todo-title ${t.completed?'done':''}">${escapeHtml(t.title)}</span>${t.dueDate?`<span class="duration">${escapeHtml(t.dueDate)}</span>`:''}<button class="delete" data-delete="todos" data-id="${t.id}" aria-label="删除">×</button></div>`; }
function bookmarkHtml(b) { return `<article class="bookmark-card"><div class="bookmark-top"><span class="site-icon">${escapeHtml(b.title[0])}</span><div><a href="${escapeHtml(b.url)}" target="_blank" rel="noreferrer"><h3>${escapeHtml(b.title)}</h3></a><span class="domain">${escapeHtml(host(b.url))}</span></div></div><p>${escapeHtml(b.note || '暂无备注')}</p><div class="bookmark-foot"><label class="folder-picker" title="更换收藏夹"><span>▣</span><select data-move-bookmark="${b.id}" aria-label="移动 ${escapeHtml(b.title)}">${folderOptions(b.category)}</select></label><div><button class="favorite ${b.favorite?'on':''}" data-favorite="${b.id}">★</button><button class="delete" data-delete="bookmarks" data-id="${b.id}">×</button></div></div></article>`; }
function excerptHtml(excerpt) { const attribution = [excerpt.author, excerpt.source].filter(Boolean).join(' · '); return `<article class="excerpt-card"><span class="excerpt-mark">“</span><blockquote>${escapeHtml(excerpt.content)}</blockquote><div class="excerpt-meta"><div><strong>${escapeHtml(attribution || '未注明出处')}</strong><small>${escapeHtml(excerpt.excerptDate || '未填写日期')}</small></div><button class="delete" data-delete="excerpts" data-id="${excerpt.id}" aria-label="删除摘录">×</button></div>${excerpt.note ? `<p>${escapeHtml(excerpt.note)}</p>` : ''}</article>`; }
function netdiskResultHtml(item) { return `<article class="netdisk-card"><div><span class="label">${escapeHtml(netdiskSourceName(item.source) || 'NETDISK')}</span><h3><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a></h3>${item.description ? `<p>${escapeHtml(item.description)}</p>` : ''}<div class="netdisk-meta">${[item.size, item.time, host(item.url)].filter(Boolean).map((value) => `<span>${escapeHtml(value)}</span>`).join('')}</div></div><a class="open-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">打开 →</a></article>`; }

const forms = {
  bookmarks: { title:'添加网站', label:'NEW BOOKMARK', fields:() => `<div class="field"><label>名称</label><input name="title" required placeholder="例如：少数派"></div><div class="field"><label>网址</label><input name="url" type="url" required placeholder="https://"></div><div class="field"><label>收藏夹</label><select name="category" required>${folderOptions()}</select></div><div class="field"><label>备注</label><textarea name="note" placeholder="为什么收藏它？"></textarea></div>` },
  excerpts: { title:'添加摘录', label:'NEW EXCERPT', fields:() => `<div class="field"><label>内容</label><textarea name="content" required maxlength="3000" placeholder="写下让你停顿的那句话…"></textarea></div><div class="form-row"><div class="field"><label>作者 / 歌手</label><input name="author" placeholder="例如：加缪、陈奕迅"></div><div class="field"><label>出处</label><input name="source" placeholder="书名、歌名、电影或其他来源"></div></div><div class="field"><label>摘录日期</label><input name="excerptDate" type="date" value="${dateKey()}"></div><div class="field"><label>备注（可选）</label><textarea name="note" maxlength="500" placeholder="当时的想法、页码或场景…"></textarea></div>` },
  folders: { title:'新建收藏夹', label:'NEW COLLECTION', fields:`<div class="field"><label>收藏夹名称</label><input name="name" required maxlength="30" placeholder="例如：旅行灵感"></div>` },
  todos: { title:'添加待办', label:'NEW TO-DO', fields:`<div class="field"><label>待办内容</label><input name="title" required placeholder="我准备完成…"></div><div class="form-row"><div class="field"><label>优先级</label><select name="priority"><option value="medium">普通</option><option value="high">重要</option><option value="low">低</option></select></div><div class="field"><label>截止日期</label><input name="dueDate" type="date"></div></div>` },
  plans: { title:'制定计划', label:'NEW PLAN', fields:() => `<div class="field"><label>计划名称</label><input name="title" required placeholder="例如：晨间阅读"></div><div class="form-row"><div class="field"><label>计划类型</label><select name="frequencyType"><option value="daily">日常计划</option><option value="weekly">周常计划</option><option value="monthly">月度计划</option></select></div><div class="field"><label>每周期目标次数</label><input name="targetCount" type="number" min="1" max="99" value="1" required></div></div><div class="form-row"><div class="field"><label>开始日期</label><input name="startDate" type="date" required value="${state.planDate}"></div><div class="field"><label>结束日期（可选）</label><input name="endDate" type="date"></div></div><div class="form-row"><div class="field"><label>提醒时间</label><input name="time" type="time" required value="09:00"></div><div class="field"><label>每次时长（分钟）</label><input name="duration" type="number" min="5" max="480" value="30"></div></div><div class="field"><label>标记颜色</label><select name="color"><option value="violet">紫色</option><option value="orange">橙色</option><option value="green">绿色</option><option value="blue">蓝色</option></select></div>` }
};

function openModal(type) {
  const config = forms[type];
  $('#modal-title').textContent = config.title; $('#modal-label').textContent = config.label; $('#form-fields').innerHTML = typeof config.fields === 'function' ? config.fields() : config.fields;
  $('#item-form').dataset.type = type; $('#modal').hidden = false; $('#quick-menu').hidden = true;
  setTimeout(() => $('#item-form input')?.focus(), 50);
}
function closeModal() { $('#modal').hidden = true; $('#item-form').reset(); }
function toast(message) { const el=$('#toast'); el.textContent=message; el.classList.add('show'); setTimeout(()=>el.classList.remove('show'),1800); }

document.addEventListener('click', async (event) => {
  const pageLink = event.target.closest('[data-page],[data-page-link]');
  if (pageLink) { const page=pageLink.dataset.page || pageLink.dataset.pageLink; location.hash=page; showPage(page); }
  const add = event.target.closest('[data-add]'); if (add) openModal(add.dataset.add);
  if (event.target.closest('.close') || event.target === $('#modal')) closeModal();
  const category = event.target.closest('[data-category]'); if (category) { state.category=category.dataset.category; render(); }
  const toggle = event.target.closest('[data-toggle]');
  if (toggle) { const type=toggle.dataset.toggle; const item=state[type].find((x)=>x.id===toggle.dataset.id); await mutate(()=>request(`/api/${type}/${item.id}`,{method:'PATCH',body:JSON.stringify({completed:!item.completed})}),'已更新'); }
  const planCount = event.target.closest('[data-plan-count]');
  if (planCount) {
    const item = state.plans.find((plan) => plan.id === planCount.dataset.id);
    const completions = { ...(item.completions || {}) };
    const next = Math.max(0, Number(completions[state.planDate] || 0) + Number(planCount.dataset.planCount));
    if (next) completions[state.planDate] = next; else delete completions[state.planDate];
    await mutate(() => request(`/api/plans/${item.id}`, { method:'PATCH', body:JSON.stringify({ completions }) }), next ? '打卡成功' : '已撤销一次');
  }
  const del = event.target.closest('[data-delete]');
  if (del) await mutate(()=>request(`/api/${del.dataset.delete}/${del.dataset.id}`,{method:'DELETE'}),'已删除');
  const adminBan = event.target.closest('[data-admin-ban]');
  if (adminBan) {
    const row = adminBan.closest('[data-role-user]');
    const banned = adminBan.dataset.adminBan === 'true';
    try {
      const updated = await request(`/api/admin/users/${row.dataset.roleUser}/ban`, { method:'PATCH', body:JSON.stringify({ banned }) });
      state.admin.users = state.admin.users.map((user) => user.id === updated.id ? updated : user);
      renderAdmin();
      toast(banned ? '账号已封禁' : '账号已解封');
    } catch (error) {
      await loadAdmin();
      toast(error.message);
    }
    return;
  }
  const adminDelete = event.target.closest('[data-admin-delete]');
  if (adminDelete) {
    const row = adminDelete.closest('[data-role-user]');
    const user = state.admin.users.find((item) => item.id === row.dataset.roleUser);
    if (!confirm(`确定删除账号「${user?.username || ''}」吗？此操作不可恢复。`)) return;
    try {
      await request(`/api/admin/users/${row.dataset.roleUser}`, { method:'DELETE' });
      await loadAdmin();
      toast('账号已删除');
    } catch (error) {
      await loadAdmin();
      toast(error.message);
    }
    return;
  }
  const fav = event.target.closest('[data-favorite]');
  if (fav) { const item=state.bookmarks.find((x)=>x.id===fav.dataset.favorite); await mutate(()=>request(`/api/bookmarks/${item.id}`,{method:'PATCH',body:JSON.stringify({favorite:!item.favorite})}),'已更新'); }
  if (event.target.closest('[data-action="quick-add"]')) { const rect=event.target.closest('button').getBoundingClientRect(); const menu=$('#quick-menu'); menu.style.top=`${rect.bottom+8}px`; menu.style.left=`${Math.min(rect.left,innerWidth-180)}px`; menu.hidden=!menu.hidden; }
  const netdiskSource = event.target.closest('[data-netdisk-source]');
  if (netdiskSource) { state.netdisk.selectedSource = netdiskSource.dataset.netdiskSource; renderNetdisk(); }
  if (event.target.closest('.mobile-menu')) $('.sidebar').classList.toggle('open');
  const shift = event.target.closest('[data-shift-date]'); if (shift) { state.planDate = shiftDate(state.planDate, Number(shift.dataset.shiftDate)); render(); }
  if (event.target.closest('[data-plan-today]')) { state.planDate = dateKey(); render(); }
  if (event.target.closest('#shuffle-excerpt')) { chooseFeaturedExcerpt(); render(); toast('换了一句'); }
});

$('#item-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const type=event.currentTarget.dataset.type; const payload=Object.fromEntries(new FormData(event.currentTarget));
  if (payload.duration) payload.duration=Number(payload.duration);
  if (payload.targetCount) payload.targetCount=Number(payload.targetCount);
  await mutate(()=>request(`/api/${type}`,{method:'POST',body:JSON.stringify(payload)}),'已添加'); closeModal();
});
document.addEventListener('change', async (event) => {
  const roleInput = event.target.closest('[data-user-role]');
  if (roleInput) {
    const row = roleInput.closest('[data-role-user]');
    const roles = $$('[data-user-role]', row).filter((input) => input.checked).map((input) => input.value);
    try {
      const updated = await request(`/api/admin/users/${row.dataset.roleUser}/roles`, { method:'PATCH', body:JSON.stringify({ roles }) });
      state.admin.users = state.admin.users.map((user) => user.id === updated.id ? updated : user);
      if (state.user?.id === updated.id) {
        state.user = await request('/api/auth/me');
        showApp();
      }
      renderAdmin();
      toast('角色已更新');
    } catch (error) {
      await loadAdmin();
      toast(error.message);
    }
    return;
  }
  const picker = event.target.closest('[data-move-bookmark]');
  if (!picker) return;
  await mutate(() => request(`/api/bookmarks/${picker.dataset.moveBookmark}`, { method:'PATCH', body:JSON.stringify({ category:picker.value }) }), `已移动到「${picker.value}」`);
});
$('#clear-completed').addEventListener('click', async () => { await Promise.all(state.todos.filter((t)=>t.completed).map((t)=>request(`/api/todos/${t.id}`,{method:'DELETE'}))); await load(); toast('已清空'); });
$('#global-search').addEventListener('input', (e) => { state.search=e.target.value.trim().toLowerCase(); if(state.search){showPage('bookmarks');location.hash='bookmarks'} render(); });
$('#plan-date').addEventListener('change', (event) => { if (event.target.value) { state.planDate = event.target.value; render(); } });
$('#auth-switch').addEventListener('click', () => showAuth(state.authMode === 'login' ? 'register' : 'login'));
$('#login-form').addEventListener('submit', async (event) => { event.preventDefault(); try { await authSubmit('/api/auth/login', event.currentTarget); toast('欢迎回来'); } catch (e) { resetAuthCaptcha('login'); toast(e.message); } });
$('#register-form').addEventListener('submit', async (event) => { event.preventDefault(); try { await authSubmit('/api/auth/register', event.currentTarget); toast('注册成功'); } catch (e) { resetAuthCaptcha('register'); toast(e.message); } });
$('#logout-btn').addEventListener('click', async () => { await request('/api/auth/logout', { method:'POST' }).catch(() => null); showAuth('login'); toast('已退出'); });
$('#netdisk-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const keyword = $('#netdisk-keyword').value.trim();
  if (!keyword) return;
  state.netdisk = { keyword, loading: true, source: '', results: [], raw: null, error: '', selectedSource: '全部' };
  renderNetdisk();
  try {
    const payload = await request(`/api/netdisk/search?kw=${encodeURIComponent(keyword)}`);
    state.netdisk = { keyword: payload.keyword || keyword, loading: false, source: payload.source || '', results: payload.results || [], raw: payload.raw || null, error: '', selectedSource: '全部' };
  } catch (error) {
    state.netdisk = { keyword, loading: false, source: '', results: [], raw: null, error: error.message, selectedSource: '全部' };
  }
  renderNetdisk();
});
document.addEventListener('keydown', (e) => { if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();$('#global-search').focus()} if(e.key==='Escape')closeModal(); });
window.addEventListener('hashchange',()=> state.user ? showPage(location.hash.slice(1)||'dashboard') : showAuth('login'));
async function mutate(action,message){try{await action();await load();toast(message)}catch(e){toast(e.message)}}
function showPage(id){if(!state.user){showAuth('login');return}if(!$('#'+id))id='dashboard';if(id==='admin'&&!canManageAccess()){id='dashboard';toast('没有访问用户管理的权限')}$$('.page').forEach((p)=>p.classList.toggle('active',p.id===id));$$('.nav-link').forEach((a)=>a.classList.toggle('active',a.dataset.page===id));$('.sidebar').classList.remove('open');if(id==='admin')loadAdmin();}

async function boot() {
  const now=new Date(); $('#today-chip').textContent=new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric',weekday:'long'}).format(now); $('#greeting').textContent=`${now.getHours()<12?'早上':now.getHours()<18?'下午':'晚上'}好，欢迎回来`;
  try {
    state.user = await request('/api/auth/me');
    showApp();
    const page = location.hash.slice(1) || 'dashboard';
    if (!location.hash) location.hash = page;
    showPage(page);
    await load();
  } catch {
    showAuth('login');
  }
}
if (window.orbitPlayCaptcha) mountPlayCaptchas();
else window.addEventListener('orbit:playcaptcha-ready', mountPlayCaptchas, { once: true });
boot();
