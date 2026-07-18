const dateKey = (date = new Date()) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const shiftDate = (key, amount) => { const date = new Date(`${key}T00:00:00`); date.setDate(date.getDate() + amount); return dateKey(date); };
const state = { user: null, authMode: 'login', bookmarks: [], todos: [], plans: [], folders: [], excerpts: [], featuredExcerptId: '', category: '全部', search: '', planDate: dateKey(), folderManaging: false, library: { books: [], filter: 'all', search: '', searchTimer: null, searchRequest: 0, loading: false, activeBookId: '', readers: null, reviews: null, reviewBookId: '', bookMode: 'upload', editBookId: '', readBookId: '', editReadId: '' }, admin: { users: [], roles: [], permissions: [], hermesChats: [], hermesChatActive: null, loading: false }, hermes: { loading: false, configured: false, installed: false, running: false, dashboardUrl: 'http://127.0.0.1:9119', dashboardPublicUrl: '/hermes-dashboard/', message: '', details: '' }, hermesChat: { loading: false, sending: false, stopping: false, stopped: false, controller: null, stream: null, conversations: [], activeId: '', active: null, error: '' }, netdisk: { keyword: '', loading: false, source: '', results: [], raw: null, error: '', selectedSource: '全部' }, integrations: { lxMusic: { enabled: false, publicUrl: '' } }, captcha: { pending: null, busy: false, mounted: false } };
let hermesGenerationPollTimer = 0;
let authReturnTarget = new URLSearchParams(location.search).get('next') === 'music' ? 'music' : '';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
const planTypeLabels = { daily: '日常', weekly: '周常', monthly: '月度' };
const netdiskSourceLabels = { baidu: '百度网盘', quark: '夸克网盘', aliyun: '阿里云盘', xunlei: '迅雷云盘', tianyi: '天翼云盘', uc: 'UC 网盘', mobile: '移动云盘', pikpak: 'PikPak', '123pan': '123 网盘', '115': '115 网盘' };
const hasPermission = (permission) => state.user?.permissions?.includes(permission);
const canManageAccess = () => hasPermission('users:manage') || hasPermission('roles:manage');
const canManageFolders = () => hasPermission('folders:manage');
const canReadLibrary = () => hasPermission('library:read');
const canUploadLibrary = () => hasPermission('library:upload');
const canManageLibrary = () => hasPermission('library:manage');
const canManageAgents = () => hasPermission('agents:manage');
const canUseHermesChat = () => hasPermission('hermes:chat');

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
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has('content-type')) headers.set('content-type', 'application/json');
  const response = await fetch(url, { ...options, headers });
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

function renderIntegrations() {
  const music = state.integrations?.lxMusic;
  const nav = $('#lx-music-nav');
  const publicUrl = music?.enabled ? String(music.publicUrl || '') : '';
  nav.hidden = !publicUrl;
  nav.href = publicUrl || '#';
}

async function loadIntegrations() {
  try {
    state.integrations = await request('/api/integrations');
  } catch {
    state.integrations = { lxMusic: { enabled: false, publicUrl: '' } };
  }
  renderIntegrations();
}

function returnToMusic() {
  if (authReturnTarget !== 'music') return false;
  authReturnTarget = '';
  const music = state.integrations?.lxMusic;
  const publicUrl = music?.enabled ? String(music.publicUrl || '') : '';
  history.replaceState(null, '', '/');
  if (!publicUrl) return false;
  location.replace(publicUrl);
  return true;
}

function resetToLoginRoute() {
  const route = authReturnTarget === 'music' ? '/?next=music' : '/';
  if (`${location.pathname}${location.search}` !== route || location.hash) history.replaceState(null, '', route);
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
  setTimeout(() => $(`#${mode}-form input`)?.focus(), 50);
}

function showApp() {
  $('#auth-screen').hidden = true;
  $('.app-shell').hidden = false;
  $('#user-chip').textContent = state.user ? `${state.user.username}${state.user.isAdmin ? ' · 管理员' : ''}` : '';
  $('#admin-nav').hidden = !canManageAccess();
  $('#library-nav').hidden = !canReadLibrary();
  $('#hermes-chat-nav').hidden = !canUseHermesChat();
  $('#hermes-nav').hidden = !canManageAgents();
  renderIntegrations();
}

async function authSubmit(path, form) {
  const mode = form.id === 'register-form' ? 'register' : 'login';
  showAuthCaptcha({ mode, path, payload: Object.fromEntries(new FormData(form)) });
}

async function finishAuthSubmit(playcaptchaToken) {
  const pending = state.captcha.pending;
  if (!pending || state.captcha.busy) return;
  state.captcha.busy = true;
  $('#auth-captcha-status').textContent = '验证成功，正在继续...';
  state.user = await request(pending.path, { method:'POST', body:JSON.stringify({ ...pending.payload, playcaptchaToken }) });
  closeAuthCaptcha();
  await loadIntegrations();
  if (returnToMusic()) return;
  showApp();
  location.hash = 'dashboard';
  showPage('dashboard');
  await load();
  toast(pending.mode === 'login' ? '欢迎回来' : '注册成功');
}

function showAuthCaptcha(pending) {
  state.captcha.pending = pending;
  state.captcha.busy = false;
  $('#auth-captcha-status').textContent = '';
  $('#auth-captcha-modal').hidden = false;
  mountAuthCaptcha();
  window.orbitPlayCaptcha?.reset('auth');
}

function closeAuthCaptcha() {
  $('#auth-captcha-modal').hidden = true;
  state.captcha.pending = null;
  state.captcha.busy = false;
}

function mountAuthCaptcha() {
  const element = $('[data-playcaptcha="auth"]');
  if (!element || !window.orbitPlayCaptcha || state.captcha.mounted) return;
  window.orbitPlayCaptcha.mount({
    element,
    mode: 'auth',
    onVerified: async () => {
      try {
        const result = await request('/api/auth/playcaptcha', { method:'POST' }, false);
        await finishAuthSubmit(result.token || '');
      } catch (error) {
        closeAuthCaptcha();
        window.orbitPlayCaptcha?.reset('auth');
        toast(error.message);
      }
    },
  });
  state.captcha.mounted = true;
}

async function load() {
  [state.bookmarks, state.todos, state.plans, state.folders, state.excerpts, state.library.books] = await Promise.all([
    ...['bookmarks','todos','plans','folders','excerpts'].map((type) => request(`/api/${type}`)),
    canReadLibrary() ? request('/api/library/books') : Promise.resolve([]),
  ]);
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

  if (!canManageFolders()) state.folderManaging = false;
  $('#bookmarks-filters')?.classList.toggle('managing', state.folderManaging);
  const manage = $('#folder-manage');
  if (manage) {
    manage.hidden = !canManageFolders();
    manage.textContent = state.folderManaging ? '完成管理' : '管理标签';
    manage.classList.toggle('active', state.folderManaging);
  }
  $('#category-filters').innerHTML = orderedFolders().map((folder) => state.folderManaging ? `<span class="folder-chip" draggable="true" data-folder-id="${folder.id}"><button class="filter ${state.category === folder.name ? 'active':''}" data-category="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</button><button class="folder-delete" data-delete="folders" data-id="${folder.id}" aria-label="删除收藏夹 ${escapeHtml(folder.name)}">×</button></span>` : `<button class="filter ${state.category === folder.name ? 'active':''}" data-category="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</button>`).join('');
  let visibleBookmarks = state.bookmarks.filter((b) => state.category === '全部' || b.category === state.category);
  if (state.search) visibleBookmarks = visibleBookmarks.filter((b) => `${b.title} ${b.url} ${b.note} ${b.category}`.toLowerCase().includes(state.search));
  visibleBookmarks.sort((a, b) => Number(b.favorite) - Number(a.favorite) || a.title.localeCompare(b.title, 'zh-CN'));
  $('#bookmarks-grid').innerHTML = visibleBookmarks.map(bookmarkHtml).join('') || empty('没有找到匹配的收藏');
  renderPlanStatistics();
  $('#todos-active').innerHTML = activeTodos.map(todoHtml).join('') || empty('现在没有待办');
  $('#todos-completed').innerHTML = doneTodos.map(todoHtml).join('') || empty('完成的事项会出现在这里');
  $('#active-count').textContent = `${activeTodos.length} 项`;
  renderLibrary();
  renderNetdisk();
  renderHermesChat();
  renderHermes();
  renderAdmin();
}

function libraryHue(value = '') {
  return [...String(value)].reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) % 360, 28);
}

function formatFileSize(bytes) {
  const size = Number(bytes) || 0;
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / 1024 / 1024).toFixed(size >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
}

function libraryBookHtml(book) {
  const initial = (book.title || '书').trim().slice(0, 1);
  const cover = book.hasCover ? `<img src="/api/library/books/${escapeHtml(book.id)}/cover" alt="${escapeHtml(book.title)} 封面" loading="lazy" onerror="this.remove()">` : '';
  const manage = canManageLibrary() ? `<button data-library-edit="${escapeHtml(book.id)}">编辑</button><button class="library-danger" data-library-delete="${escapeHtml(book.id)}">删除</button>` : '';
  return `<article class="library-card">
    <div class="library-cover" style="--cover-hue:${libraryHue(book.title)}">${cover}<span class="library-cover-placeholder">${escapeHtml(initial)}</span><span class="library-format">${escapeHtml(String(book.fileFormat || '').toUpperCase())}</span></div>
    <div class="library-card-body">
      <div class="library-card-title"><h3>${escapeHtml(book.title)}</h3><span class="library-read-status ${book.currentUserRead ? 'read' : ''}">${book.currentUserRead ? `已读 ${book.currentUserReadCount} 次` : '未读'}</span></div>
      <p class="library-author">${escapeHtml(book.author)}</p>
      <div class="library-stats">${book.readerCount} 人读过 · 共阅读 ${book.readCount} 次</div>
      <p class="library-uploaded">${formatFileSize(book.fileSize)} · ${escapeHtml(book.uploadedByName)} 上传</p>
      <div class="library-card-actions">
        <button class="library-record" data-library-record="${escapeHtml(book.id)}">记录阅读</button>
        <button data-library-readers="${escapeHtml(book.id)}">读者</button>
        <button data-library-reviews="${escapeHtml(book.id)}">书评</button>
        <a href="/api/library/books/${escapeHtml(book.id)}/download">下载</a>
        ${manage}
      </div>
    </div>
  </article>`;
}

function renderLibrary() {
  const grid = $('#library-grid');
  if (!grid) return;
  if (!canReadLibrary()) {
    grid.innerHTML = empty('没有访问共享图书馆的权限');
    return;
  }
  $$('#library-filters [data-library-filter]').forEach((button) => button.classList.toggle('active', button.dataset.libraryFilter === state.library.filter));
  const upload = $('[data-library-upload]', $('#library .page-title'));
  if (upload) upload.hidden = !canUploadLibrary();
  const books = state.library.books.filter((book) => state.library.filter === 'all' || (state.library.filter === 'read' ? book.currentUserRead : !book.currentUserRead));
  $('#library-count').textContent = `${books.length} / ${state.library.books.length} 本`;
  grid.innerHTML = state.library.loading ? empty('正在加载图书馆…') : books.map(libraryBookHtml).join('') || empty(state.library.books.length ? '这个分类还没有书' : state.library.search.trim() ? '没有找到匹配的图书' : '图书馆还是空的，上传第一本书吧');
}

async function loadLibrary() {
  if (!canReadLibrary()) return;
  const requestId = ++state.library.searchRequest;
  const query = state.library.search.trim();
  const params = new URLSearchParams();
  if (query) params.set('q', query);
  const queryString = params.toString();
  state.library.loading = true;
  renderLibrary();
  try {
    const books = await request(`/api/library/books${queryString ? `?${queryString}` : ''}`);
    if (requestId === state.library.searchRequest) state.library.books = books;
  } finally {
    if (requestId === state.library.searchRequest) {
      state.library.loading = false;
      renderLibrary();
    }
  }
}

function openLibraryBookModal(book = null) {
  const form = $('#library-book-form');
  form.reset();
  delete form.elements.title.dataset.autoValue;
  delete form.elements.author.dataset.autoValue;
  delete form.elements.title.dataset.manualValue;
  delete form.elements.author.dataset.manualValue;
  state.library.bookMode = book ? 'edit' : 'upload';
  state.library.editBookId = book?.id || '';
  $('#library-book-label').textContent = book ? 'ADMIN EDIT' : 'UPLOAD';
  $('#library-book-title').textContent = book ? '编辑书目信息' : '上传电子书';
  form.elements.title.value = book?.title || '';
  form.elements.author.value = book?.author || '';
  form.elements.title.required = Boolean(book);
  form.elements.author.required = Boolean(book);
  $('#library-file-hint').textContent = '选择文件后会从文件名预填；上传时还会读取 EPUB/PDF 元数据，可随时修改。支持格式最大 100 MB';
  $('#library-file-field').hidden = Boolean(book);
  form.elements.bookFile.required = !book;
  $('#library-remove-cover').hidden = !book?.hasCover;
  $('#library-book-modal').hidden = false;
  setTimeout(() => form.elements.title.focus(), 50);
}

function libraryMetadataFromFilename(filename = '') {
  const stem = filename.replace(/\.[^.]+$/, '').replace(/\s+/g, ' ').trim();
  if (!stem) return { title:'', author:'' };
  const quoted = stem.match(/^《(.+?)》(?:\s*[-—–]\s*|\s+)(.+)$/);
  if (quoted) return { title:quoted[1].trim(), author:quoted[2].trim() };
  const separated = stem.match(/^(.+?)\s+[-—–]\s+(.+)$/);
  if (separated) return { title:separated[1].trim(), author:separated[2].trim() };
  return { title:stem, author:'' };
}

function setLibraryAutoField(input, value) {
  if (input.dataset.manualValue !== 'true') input.value = value;
  input.dataset.autoValue = value;
}

function openLibraryReadModal(bookId, record = null) {
  state.library.readBookId = bookId;
  state.library.editReadId = record?.id || '';
  $('#library-read-title').textContent = record ? '修改阅读日期' : '记录一次阅读';
  const form = $('#library-read-form');
  form.elements.readDate.value = record?.readDate || dateKey();
  form.elements.review.value = '';
  form.elements.reviewAnonymous.checked = false;
  $('#library-read-review-field').hidden = Boolean(record);
  $('#library-readers-modal').hidden = true;
  $('#library-read-modal').hidden = false;
  setTimeout(() => form.elements.readDate.focus(), 50);
}

function renderLibraryReaders() {
  const container = $('#library-readers-content');
  const book = state.library.books.find((item) => item.id === state.library.activeBookId);
  $('#library-readers-title').textContent = book ? `《${book.title}》的阅读记录` : '阅读记录';
  const data = state.library.readers;
  if (!data) {
    container.innerHTML = empty('正在加载阅读记录…');
    return;
  }
  container.innerHTML = data.readers.map((reader) => `<section class="library-reader">
    <div class="library-reader-head"><strong>${escapeHtml(reader.username)}${reader.isCurrentUser ? ' · 我' : ''}</strong><span>${reader.reads.length} 次</span></div>
    <div class="library-read-list">${reader.reads.map((record) => `<div class="library-read-row"><time datetime="${escapeHtml(record.readDate)}">${escapeHtml(record.readDate)}</time>${reader.isCurrentUser ? `<div class="library-read-actions"><button data-library-read-edit="${escapeHtml(record.id)}" data-book-id="${escapeHtml(state.library.activeBookId)}">修改</button><button class="danger" data-library-read-delete="${escapeHtml(record.id)}" data-book-id="${escapeHtml(state.library.activeBookId)}">删除</button></div>` : ''}</div>`).join('')}</div>
  </section>`).join('') || empty('还没有人记录阅读');
}

async function openLibraryReaders(bookId) {
  state.library.activeBookId = bookId;
  state.library.readers = null;
  $('#library-readers-modal').hidden = false;
  renderLibraryReaders();
  try {
    state.library.readers = await request(`/api/library/books/${bookId}/reads`);
    renderLibraryReaders();
  } catch (error) {
    $('#library-readers-content').innerHTML = `<div class="empty status-error">${escapeHtml(error.message)}</div>`;
  }
}

function renderLibraryReviews() {
  const container = $('#library-reviews-content');
  const book = state.library.books.find((item) => item.id === state.library.reviewBookId);
  $('#library-review-title').textContent = book ? `《${book.title}》的书评` : '书评';
  const reviews = state.library.reviews;
  if (!reviews) {
    container.innerHTML = empty('正在加载书评…');
    return;
  }
  container.innerHTML = reviews.map((review) => `<article class="library-review">
    <div class="library-review-head"><strong>${escapeHtml(review.username)}${review.canDelete && review.username === state.user?.username ? ' · 我' : ''}${review.isAnonymous && review.canToggleAnonymous ? ' · 匿名' : ''}</strong><time datetime="${escapeHtml(review.createdAt)}">${escapeHtml(review.createdAt)}</time></div>
    <p>${escapeHtml(review.content)}</p>
    <div class="library-review-actions">${review.canToggleAnonymous ? `<button class="library-review-toggle" data-library-review-toggle="${escapeHtml(review.id)}" data-library-review-anonymous="${review.isAnonymous ? 'true' : 'false'}">${review.isAnonymous ? '取消匿名' : '设为匿名'}</button>` : ''}${review.canDelete ? `<button class="library-review-delete" data-library-review-delete="${escapeHtml(review.id)}">删除</button>` : ''}</div>
  </article>`).join('') || empty('还没有书评，来留下第一条吧');
}

async function openLibraryReviews(bookId) {
  state.library.reviewBookId = bookId;
  state.library.reviews = null;
  $('#library-review-modal').hidden = false;
  renderLibraryReviews();
  try {
    state.library.reviews = await request(`/api/library/books/${bookId}/reviews`);
    renderLibraryReviews();
  } catch (error) {
    $('#library-reviews-content').innerHTML = `<div class="empty status-error">${escapeHtml(error.message)}</div>`;
  }
}

function closeLibraryModals() {
  $('#library-book-modal').hidden = true;
  $('#library-read-modal').hidden = true;
  $('#library-readers-modal').hidden = true;
  $('#library-review-modal').hidden = true;
  state.library.readers = null;
  state.library.reviews = null;
  state.library.reviewBookId = '';
}

function renderHermes() {
  const status = $('#hermes-status');
  const badge = $('#hermes-badge');
  const open = $('#hermes-open');
  if (!status || !badge || !open) return;
  const localUrl = state.hermes.dashboardUrl || 'http://127.0.0.1:9119';
  const url = state.hermes.dashboardPublicUrl || localUrl;
  const canOpen = canOpenHermesDashboard(url);
  open.href = url;
  open.textContent = canOpen ? '打开 Dashboard' : '服务器本机 Dashboard';
  open.classList.toggle('disabled', !state.hermes.running || !canOpen);
  if (state.hermes.loading) {
    badge.textContent = '检查中';
    badge.className = 'hermes-badge';
    status.innerHTML = '<div class="empty"><span class="loading-dot"></span> 正在检查 Hermes...</div>';
    return;
  }
  const tone = !state.hermes.installed || !state.hermes.configured ? 'missing' : state.hermes.running ? 'running' : 'stopped';
  badge.className = `hermes-badge ${tone}`;
  badge.textContent = tone === 'running' ? '运行中' : tone === 'missing' ? '不可用' : '未运行';
  status.innerHTML = `<dl class="hermes-grid">
    <div><dt>Dashboard</dt><dd>${escapeHtml(url)}</dd></div>
    <div><dt>Hermes CLI</dt><dd>${state.hermes.installed ? '已安装' : '未找到'}</dd></div>
    <div><dt>配置</dt><dd>${state.hermes.configured ? '已配置' : '缺失'}</dd></div>
    <div><dt>状态</dt><dd>${escapeHtml(state.hermes.message || '尚未检查')}</dd></div>
  </dl>${state.hermes.details ? `<p class="hermes-details">${escapeHtml(state.hermes.details)}</p>` : ''}`;
}

function hermesMessageHtml(message, userLabel = '你') {
  const user = message.role === 'user';
  const thinking = message.temporary && message.status === 'streaming' && !message.content;
  const content = thinking ? '<span class="loading-dot"></span> 正在思考' : escapeHtml(message.content);
  const interrupted = message.status === 'interrupted' ? '<small class="hermes-message-status">用户终止回答</small>' : '';
  return `<article class="hermes-message ${user ? 'user' : 'assistant'}"><div class="hermes-message-role">${user ? userLabel : 'Hermes'}</div><div class="hermes-message-content">${content}</div>${interrupted}</article>`;
}

function renderHermesChat() {
  const list = $('#hermes-chat-conversations');
  const room = $('#hermes-chat-room');
  const form = $('#hermes-chat-form');
  const input = $('#hermes-chat-input');
  if (!list || !room || !form || !input) return;
  if (!canUseHermesChat()) {
    list.innerHTML = empty('没有 Hermes 聊天权限');
    room.innerHTML = empty('没有 Hermes 聊天权限');
    form.hidden = true;
    return;
  }
  form.hidden = false;
  const button = form.querySelector('button');
  const finishing = Boolean(state.hermesChat.stream?.serverCompleted);
  input.disabled = state.hermesChat.sending || !state.hermesChat.active;
  button.disabled = !state.hermesChat.active || state.hermesChat.stopping || finishing;
  button.type = state.hermesChat.sending ? 'button' : 'submit';
  button.textContent = state.hermesChat.sending ? (finishing ? '正在显示…' : state.hermesChat.stopping ? '正在停止…' : '停止生成') : '发送';
  button.classList.toggle('primary', !state.hermesChat.sending);
  button.classList.toggle('secondary', state.hermesChat.sending);
  if (state.hermesChat.loading) {
    list.innerHTML = empty('正在加载会话…');
    room.innerHTML = '<div class="empty"><span class="loading-dot"></span> 正在加载 Hermes 聊天…</div>';
    return;
  }
  if (state.hermesChat.error) {
    room.innerHTML = `<div class="empty status-error">${escapeHtml(state.hermesChat.error)}</div>`;
  }
  list.innerHTML = state.hermesChat.conversations.map((conversation) => `<article class="hermes-chat-session ${conversation.id === state.hermesChat.activeId ? 'active' : ''}" data-hermes-chat-open="${escapeHtml(conversation.id)}"><div><strong>${escapeHtml(conversation.title)}</strong><small>${escapeHtml(conversation.updatedAt || conversation.createdAt)}</small></div><button class="delete" data-hermes-chat-delete="${escapeHtml(conversation.id)}" aria-label="删除会话">×</button></article>`).join('') || empty('还没有会话');
  const active = state.hermesChat.active;
  if (!active) {
    room.innerHTML = empty('新建一个对话后开始聊天');
    return;
  }
  const messages = active.messages || [];
  const stream = state.hermesChat.stream?.conversationId === active.id ? [{ role:'assistant', content:state.hermesChat.stream.content, status:state.hermesChat.stream.status, temporary:true }] : [];
  room.innerHTML = [...messages, ...stream].map((message) => hermesMessageHtml(message)).join('') || empty('这条会话还没有消息');
  room.scrollTop = room.scrollHeight;
}

function canOpenHermesDashboard(url) {
  try {
    if (url.startsWith('/')) return true;
    const dashboardHost = new URL(url).hostname;
    const pageHost = location.hostname;
    const loopback = new Set(['127.0.0.1', 'localhost', '::1']);
    return !loopback.has(dashboardHost) || loopback.has(pageHost);
  } catch {
    return false;
  }
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
    const [users, roles, permissions, hermesChats] = await Promise.all([
      request('/api/admin/users'),
      request('/api/admin/roles'),
      request('/api/admin/permissions'),
      request('/api/admin/hermes-chat/conversations')
    ]);
    state.admin = { ...state.admin, users, roles, permissions, hermesChats, loading: false };
  } catch (error) {
    state.admin.loading = false;
    toast(error.message);
  }
  renderAdmin();
}

async function loadHermes() {
  if (!canManageAgents()) return;
  state.hermes.loading = true;
  renderHermes();
  try {
    state.hermes = { ...state.hermes, ...await request('/api/agents/hermes/status'), loading: false };
  } catch (error) {
    state.hermes = { ...state.hermes, loading: false, running: false, message: error.message };
  }
  renderHermes();
}

function scheduleHermesGenerationPoll(conversationId, delay = 2000) {
  if (hermesGenerationPollTimer) clearTimeout(hermesGenerationPollTimer);
  hermesGenerationPollTimer = setTimeout(() => { void pollHermesGeneration(conversationId); }, delay);
}

function resumeHermesBackgroundGeneration(conversation) {
  if (!conversation?.generating) return false;
  const current = state.hermesChat.stream;
  if (current?.conversationId === conversation.id && state.hermesChat.sending) {
    current.conversation = conversation;
    return true;
  }
  state.hermesChat = {
    ...state.hermesChat,
    sending:true,
    stopping:false,
    stopped:false,
    controller:null,
    stream:{ conversationId:conversation.id, conversation, content:'', status:'streaming', background:true },
    error:'',
  };
  scheduleHermesGenerationPoll(conversation.id);
  return true;
}

async function pollHermesGeneration(conversationId) {
  hermesGenerationPollTimer = 0;
  if (!state.user || !canUseHermesChat() || state.hermesChat.stream?.conversationId !== conversationId) return;
  try {
    const conversation = await request(`/api/hermes-chat/conversations/${conversationId}`);
    if (conversation.generating) {
      state.hermesChat.stream.conversation = conversation;
      if (state.hermesChat.activeId === conversationId) state.hermesChat.active = conversation;
      renderHermesChat();
      scheduleHermesGenerationPoll(conversationId);
      return;
    }
    state.hermesChat = { ...state.hermesChat, sending:false, stopping:false, stopped:false, controller:null, stream:null, error:'' };
    state.hermesChat.conversations = [conversation, ...state.hermesChat.conversations.filter((item) => item.id !== conversationId)];
    if (state.hermesChat.activeId === conversationId) state.hermesChat.active = conversation;
    renderHermesChat();
  } catch {
    scheduleHermesGenerationPoll(conversationId, 3000);
  }
}

async function loadHermesChat() {
  if (!canUseHermesChat()) return;
  state.hermesChat.loading = true;
  state.hermesChat.error = '';
  renderHermesChat();
  try {
    const conversations = await request('/api/hermes-chat/conversations');
    const activeId = conversations.some((item) => item.id === state.hermesChat.activeId) ? state.hermesChat.activeId : conversations[0]?.id || '';
    const active = activeId ? await request(`/api/hermes-chat/conversations/${activeId}`) : null;
    state.hermesChat = { ...state.hermesChat, loading: false, conversations, activeId, active, error: '' };
    resumeHermesBackgroundGeneration(active);
  } catch (error) {
    state.hermesChat = { ...state.hermesChat, loading: false, error: error.message };
    toast(error.message);
  }
  renderHermesChat();
}

async function loadHermesChatConversation(id) {
  if (!canUseHermesChat() || !id) return;
  state.hermesChat.loading = true;
  state.hermesChat.activeId = id;
  renderHermesChat();
  try {
    const active = await request(`/api/hermes-chat/conversations/${id}`);
    if (state.hermesChat.activeId !== id) return;
    state.hermesChat = { ...state.hermesChat, loading: false, active, activeId: id, error: '' };
    resumeHermesBackgroundGeneration(active);
  } catch (error) {
    if (state.hermesChat.activeId !== id) return;
    state.hermesChat = { ...state.hermesChat, loading: false, error: error.message };
    toast(error.message);
  }
  renderHermesChat();
}

async function createHermesChatConversation() {
  if (!canUseHermesChat()) return;
  if (state.hermesChat.sending) { toast('请先停止或等待当前回答'); return; }
  try {
    const conversation = await request('/api/hermes-chat/conversations', { method:'POST', body:JSON.stringify({}) });
    state.hermesChat.conversations = [conversation, ...state.hermesChat.conversations];
    state.hermesChat.activeId = conversation.id;
    state.hermesChat.active = { ...conversation, messages: [] };
    renderHermesChat();
    $('#hermes-chat-input')?.focus();
  } catch (error) {
    toast(error.message);
  }
}

async function streamHermesChat(url, content, signal, onEvent, retry = true) {
  const response = await fetch(url, { method:'POST', headers:{ 'content-type':'application/json', accept:'text/event-stream' }, body:JSON.stringify({ content }), signal });
  if (response.status === 401 && retry && await refreshAuth()) return streamHermesChat(url, content, signal, onEvent, false);
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.error || 'Hermes 请求失败');
  }
  if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) throw new Error('Hermes 流式响应格式无效');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const consume = () => {
    while (true) {
      const boundary = buffer.match(/\r?\n\r?\n/);
      if (!boundary) return;
      const block = buffer.slice(0, boundary.index);
      buffer = buffer.slice(boundary.index + boundary[0].length);
      let event = 'message';
      const data = [];
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }
      if (data.length) onEvent(event, JSON.parse(data.join('\n')));
    }
  };
  while (true) {
    let packet;
    try {
      packet = await reader.read();
    } catch (error) {
      error.backgroundRecoverable = true;
      throw error;
    }
    const { value, done } = packet;
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    consume();
    if (done) break;
  }
}

function createHermesStreamPacer(conversationId) {
  const queue = [];
  const waiters = [];
  let frameId = 0;

  const finishWaiters = () => waiters.splice(0).forEach((resolve) => resolve());
  const schedule = () => {
    if (!frameId) frameId = requestAnimationFrame(tick);
  };
  const tick = () => {
    frameId = 0;
    const stream = state.hermesChat.stream;
    if (!stream || stream.conversationId !== conversationId) {
      queue.length = 0;
      finishWaiters();
      return;
    }
    const frameSize = Math.min(32, Math.max(1, Math.ceil(queue.length / 8)));
    stream.content += queue.splice(0, frameSize).join('');
    renderHermesChat();
    if (queue.length) schedule();
    else finishWaiters();
  };

  return {
    push(content) {
      for (const character of String(content || '')) queue.push(character);
      if (queue.length) schedule();
    },
    drain() {
      if (!queue.length && !frameId) return Promise.resolve();
      return new Promise((resolve) => waiters.push(resolve));
    },
    flush() {
      if (frameId) cancelAnimationFrame(frameId);
      frameId = 0;
      const stream = state.hermesChat.stream;
      if (stream?.conversationId === conversationId && queue.length) stream.content += queue.splice(0).join('');
      else queue.length = 0;
      finishWaiters();
      renderHermesChat();
    },
    cancel() {
      if (frameId) cancelAnimationFrame(frameId);
      frameId = 0;
      queue.length = 0;
      finishWaiters();
    },
  };
}

async function sendHermesChatMessage(content) {
  const conversationId = state.hermesChat.activeId;
  if (!conversationId || state.hermesChat.sending) return;
  const controller = new AbortController();
  state.hermesChat = { ...state.hermesChat, sending:true, stopping:false, stopped:false, controller, stream:{ conversationId, conversation:state.hermesChat.active, content:'', status:'streaming' }, error:'' };
  const pacer = createHermesStreamPacer(conversationId);
  state.hermesChat.stream.pacer = pacer;
  renderHermesChat();
  let completion = null;
  let streamConversation = state.hermesChat.stream.conversation;
  try {
    await streamHermesChat(`/api/hermes-chat/conversations/${conversationId}/messages/stream`, content, controller.signal, (event, payload) => {
      const stream = state.hermesChat.stream;
      if (!stream || stream.conversationId !== conversationId) return;
      if (event === 'started') {
        const messages = [...(stream.conversation?.messages || []), payload.userMessage];
        stream.conversation = { ...payload.conversation, messages };
        streamConversation = stream.conversation;
        if (state.hermesChat.activeId === conversationId) state.hermesChat.active = stream.conversation;
      } else if (event === 'delta') {
        pacer.push(payload.content);
      } else if (event === 'completed') {
        completion = payload;
        state.hermesChat.stream.serverCompleted = true;
      } else if (event === 'error') {
        throw new Error(payload.detail || 'Hermes 运行失败');
      }
      renderHermesChat();
    });
    if (!completion) {
      const error = new Error('Hermes 流式连接意外结束');
      error.backgroundRecoverable = true;
      throw error;
    }
    await pacer.drain();
    const messages = [...(state.hermesChat.stream?.conversation?.messages || []), completion.message];
    streamConversation = { ...completion.conversation, messages };
    if (state.hermesChat.activeId === conversationId) state.hermesChat.active = streamConversation;
    state.hermesChat.stream = null;
  } catch (error) {
    if (state.hermesChat.stopped) {
      pacer.flush();
      const stream = state.hermesChat.stream;
      const partial = stream?.content || '';
      if (partial && stream?.conversation) {
        streamConversation = { ...stream.conversation, messages:[...(stream.conversation.messages || []), { role:'assistant', content:partial, status:'interrupted' }] };
        if (state.hermesChat.activeId === conversationId) state.hermesChat.active = streamConversation;
      }
      state.hermesChat.stream = null;
      state.hermesChat.error = '';
    } else if (error.backgroundRecoverable || error.name === 'TypeError') {
      pacer.flush();
      const stream = state.hermesChat.stream;
      if (stream) {
        stream.background = true;
        stream.pacer = null;
        stream.content = '';
        streamConversation = stream.conversation || streamConversation;
      }
      state.hermesChat = { ...state.hermesChat, sending:true, stopping:false, stopped:false, controller:null, error:'' };
      if (streamConversation) state.hermesChat.conversations = [streamConversation, ...state.hermesChat.conversations.filter((item) => item.id !== conversationId)];
      scheduleHermesGenerationPoll(conversationId, 500);
      renderHermesChat();
      return;
    } else {
      pacer.cancel();
      streamConversation = state.hermesChat.stream?.conversation || streamConversation;
      state.hermesChat.stream = null;
      state.hermesChat.error = error.message;
      toast(error.message);
    }
  }
  state.hermesChat = { ...state.hermesChat, sending:false, stopping:false, stopped:false, controller:null };
  if (streamConversation) state.hermesChat.conversations = [streamConversation, ...state.hermesChat.conversations.filter((item) => item.id !== conversationId)];
  renderHermesChat();
}

async function stopHermesChatMessage() {
  if (!state.hermesChat.sending) return;
  if (state.hermesChat.stream?.serverCompleted) return;
  const conversationId = state.hermesChat.stream?.conversationId;
  const controller = state.hermesChat.controller;
  if (!conversationId) return;
  state.hermesChat.stopped = true;
  state.hermesChat.stopping = true;
  state.hermesChat.stream?.pacer?.flush();
  renderHermesChat();
  try {
    await request(`/api/hermes-chat/conversations/${conversationId}/messages/stop`, { method:'POST', body:JSON.stringify({}) });
    if (controller) controller.abort();
    else scheduleHermesGenerationPoll(conversationId, 250);
  } catch (error) {
    state.hermesChat.stopped = false;
    state.hermesChat.stopping = false;
    toast(error.message);
    renderHermesChat();
  }
}

function renderAdmin() {
  const users = $('#admin-users');
  const roles = $('#admin-roles');
  const hermesChats = $('#admin-hermes-chats');
  const hermesDetail = $('#admin-hermes-chat-detail');
  if (!users || !roles) return;
  if (!canManageAccess()) {
    users.innerHTML = empty('没有访问用户管理的权限');
    roles.innerHTML = '';
    if (hermesChats) hermesChats.innerHTML = '';
    if (hermesDetail) hermesDetail.innerHTML = '';
    return;
  }
  if (state.admin.loading) {
    users.innerHTML = empty('正在加载用户…');
    roles.innerHTML = empty('正在加载角色…');
    if (hermesChats) hermesChats.innerHTML = empty('正在加载 Hermes 会话…');
    if (hermesDetail) hermesDetail.innerHTML = '';
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
  if (hermesChats) {
    hermesChats.innerHTML = state.admin.hermesChats.map((conversation) => `<article class="admin-hermes-chat ${state.admin.hermesChatActive?.id === conversation.id ? 'active' : ''}" data-admin-hermes-open="${escapeHtml(conversation.id)}"><div><strong>${escapeHtml(conversation.title)}</strong><small>${escapeHtml(conversation.username || conversation.userId)} · ${escapeHtml(conversation.updatedAt)}</small></div><button class="delete-account" data-admin-hermes-delete="${escapeHtml(conversation.id)}">删除</button></article>`).join('') || empty('还没有 Hermes 聊天记录');
  }
  if (hermesDetail) {
    const active = state.admin.hermesChatActive;
    const messages = active?.messages || [];
    hermesDetail.innerHTML = active ? `<div class="admin-hermes-title"><strong>${escapeHtml(active.title)}</strong><small>${escapeHtml(active.username || active.userId)} · ${escapeHtml(active.createdAt)}</small></div>${messages.map((message) => hermesMessageHtml(message, '用户')).join('') || empty('这条会话还没有消息')}` : empty('选择一条会话查看内容');
  }
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
function orderedFolders() { return state.folders.slice().sort((a, b) => Number(a.sortOrder || 0) - Number(b.sortOrder || 0) || String(b.createdAt || '').localeCompare(String(a.createdAt || '')) || a.name.localeCompare(b.name, 'zh-CN')); }
function folderOptions(selected = '') { return orderedFolders().map((folder) => `<option value="${escapeHtml(folder.name)}" ${folder.name === selected ? 'selected' : ''}>${escapeHtml(folder.name)}</option>`).join(''); }
function empty(text) { return `<div class="empty">${text}</div>`; }
function planHtml(p) { const progress = planProgress(p, dateKey()); const done = progress.done >= progress.target; return `<div class="plan-item"><span class="plan-time">${p.time}</span><span class="plan-dot ${p.color}"></span><span class="plan-name ${done?'todo-title done':''}">${escapeHtml(p.title)}</span><span class="duration">${periodLabel(p)} ${progress.done}/${progress.target}</span></div>`; }
function timelineHtml(p) { const progress = planProgress(p, state.planDate); const todayCount = Number(p.completions?.[state.planDate] || 0); const done = progress.done >= progress.target; return `<div class="timeline-item recurring"><span class="plan-time">${p.time}</span><span class="plan-dot ${p.color}"></span><div><div class="plan-title-line"><h3 class="${done?'todo-title done':''}">${escapeHtml(p.title)}</h3><span class="type-pill">${planTypeLabels[p.frequencyType]}</span></div><p>${periodLabel(p)} ${progress.done}/${progress.target} 次 · 每次 ${p.duration} 分钟${todayCount ? ` · 今天 ${todayCount} 次` : ''}</p></div><div class="count-stepper"><button data-plan-count="-1" data-id="${p.id}" aria-label="减少 ${escapeHtml(p.title)} 打卡" ${todayCount ? '' : 'disabled'}>−</button><strong>${todayCount}</strong><button data-plan-count="1" data-id="${p.id}" aria-label="完成一次 ${escapeHtml(p.title)}">＋</button></div></div>`; }
function todoHtml(t) { return `<div class="todo-item"><button class="check ${t.completed?'done':''}" data-toggle="todos" data-id="${t.id}">${t.completed?'✓':''}</button><span class="priority ${t.priority}"></span><span class="todo-title ${t.completed?'done':''}">${escapeHtml(t.title)}</span>${t.dueDate?`<span class="duration">${escapeHtml(t.dueDate)}</span>`:''}<button class="delete" data-delete="todos" data-id="${t.id}" aria-label="删除">×</button></div>`; }
function bookmarkHtml(b) { return `<article class="bookmark-card"><div class="bookmark-top"><span class="site-icon">${escapeHtml(b.title[0])}</span><div><a href="${escapeHtml(b.url)}" target="_blank" rel="noreferrer"><h3>${escapeHtml(b.title)}</h3></a><span class="domain">${escapeHtml(host(b.url))}</span></div></div><p>${escapeHtml(b.note || '暂无备注')}</p><div class="bookmark-foot"><label class="folder-picker" title="更换收藏夹"><span>▣</span><select data-move-bookmark="${b.id}" aria-label="移动 ${escapeHtml(b.title)}">${folderOptions(b.category)}</select></label><div><button class="favorite ${b.favorite?'on':''}" data-favorite="${b.id}">★</button><button class="delete" data-delete="bookmarks" data-id="${b.id}">×</button></div></div></article>`; }
function excerptHtml(excerpt) { const attribution = [excerpt.author, excerpt.source].filter(Boolean).join(' · '); const author = `${excerpt.createdByName || 'admin'}${excerpt.isAnonymous && excerpt.canToggleAnonymous ? ' · 匿名' : ''}`; const actions = excerpt.canManage ? `<div class="excerpt-actions"><button class="text-btn" data-edit="excerpts" data-id="${escapeHtml(excerpt.id)}">编辑</button><button class="delete" data-delete="excerpts" data-id="${escapeHtml(excerpt.id)}" aria-label="删除摘录">×</button></div>` : ''; return `<article class="excerpt-card"><span class="excerpt-mark">“</span><blockquote>${escapeHtml(excerpt.content)}</blockquote><div class="excerpt-meta"><div><strong>${escapeHtml(attribution || '未注明出处')}</strong><small>${escapeHtml(excerpt.excerptDate || '未填写日期')} · ${escapeHtml(author)} 摘录</small></div>${actions}</div>${excerpt.note ? `<p>${escapeHtml(excerpt.note)}</p>` : ''}</article>`; }
function netdiskResultHtml(item) { return `<article class="netdisk-card"><div><span class="label">${escapeHtml(netdiskSourceName(item.source) || 'NETDISK')}</span><h3><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a></h3>${item.description ? `<p>${escapeHtml(item.description)}</p>` : ''}<div class="netdisk-meta">${[item.size, item.time, host(item.url)].filter(Boolean).map((value) => `<span>${escapeHtml(value)}</span>`).join('')}</div></div><a class="open-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">打开 →</a></article>`; }

const forms = {
  bookmarks: { title:'添加网站', label:'NEW BOOKMARK', fields:() => `<div class="field"><label>名称</label><input name="title" required placeholder="例如：少数派"></div><div class="field"><label>网址</label><input name="url" type="url" required placeholder="https://"></div><div class="field"><label>收藏夹</label><select name="category" required>${folderOptions()}</select></div><div class="field"><label>备注</label><textarea name="note" placeholder="为什么收藏它？"></textarea></div>` },
  excerpts: { title:'添加摘录', label:'NEW EXCERPT', fields:(item = {}) => `<div class="field"><label>内容</label><textarea name="content" required maxlength="3000" placeholder="写下让你停顿的那句话…">${escapeHtml(item.content || '')}</textarea></div><div class="form-row"><div class="field"><label>作者 / 歌手</label><input name="author" value="${escapeHtml(item.author || '')}" placeholder="例如：加缪、陈奕迅"></div><div class="field"><label>出处</label><input name="source" value="${escapeHtml(item.source || '')}" placeholder="书名、歌名、电影或其他来源"></div></div><div class="field"><label>摘录日期</label><input name="excerptDate" type="date" value="${escapeHtml(item.excerptDate || dateKey())}"></div><div class="field"><label>备注（可选）</label><textarea name="note" maxlength="500" placeholder="当时的想法、页码或场景…">${escapeHtml(item.note || '')}</textarea></div><div class="field"><label class="checkbox-field"><input name="anonymous" type="checkbox" ${item.isAnonymous ? 'checked' : ''}> 匿名发布</label></div>` },
  folders: { title:'新建收藏夹', label:'NEW COLLECTION', fields:`<div class="field"><label>收藏夹名称</label><input name="name" required maxlength="30" placeholder="例如：旅行灵感"></div>` },
  todos: { title:'添加待办', label:'NEW TO-DO', fields:`<div class="field"><label>待办内容</label><input name="title" required placeholder="我准备完成…"></div><div class="form-row"><div class="field"><label>优先级</label><select name="priority"><option value="medium">普通</option><option value="high">重要</option><option value="low">低</option></select></div><div class="field"><label>截止日期</label><input name="dueDate" type="date"></div></div>` },
  plans: { title:'制定计划', label:'NEW PLAN', fields:() => `<div class="field"><label>计划名称</label><input name="title" required placeholder="例如：晨间阅读"></div><div class="form-row"><div class="field"><label>计划类型</label><select name="frequencyType"><option value="daily">日常计划</option><option value="weekly">周常计划</option><option value="monthly">月度计划</option></select></div><div class="field"><label>每周期目标次数</label><input name="targetCount" type="number" min="1" max="99" value="1" required></div></div><div class="form-row"><div class="field"><label>开始日期</label><input name="startDate" type="date" required value="${state.planDate}"></div><div class="field"><label>结束日期（可选）</label><input name="endDate" type="date"></div></div><div class="form-row"><div class="field"><label>提醒时间</label><input name="time" type="time" required value="09:00"></div><div class="field"><label>每次时长（分钟）</label><input name="duration" type="number" min="5" max="480" value="30"></div></div><div class="field"><label>标记颜色</label><select name="color"><option value="violet">紫色</option><option value="orange">橙色</option><option value="green">绿色</option><option value="blue">蓝色</option></select></div>` }
};

function openModal(type, item = null) {
  const config = forms[type];
  const editing = Boolean(item?.id);
  $('#modal-title').textContent = editing ? `编辑${type === 'excerpts' ? '摘录' : '项目'}` : config.title; $('#modal-label').textContent = editing ? 'EDIT EXCERPT' : config.label; $('#form-fields').innerHTML = typeof config.fields === 'function' ? config.fields(item || {}) : config.fields;
  $('#item-form').dataset.type = type; $('#item-form').dataset.id = item?.id || ''; $('#modal').hidden = false; $('#quick-menu').hidden = true;
  setTimeout(() => $('#item-form input')?.focus(), 50);
}
function closeModal() { $('#modal').hidden = true; $('#item-form').reset(); delete $('#item-form').dataset.id; }
function toast(message) { const el=$('#toast'); el.textContent=message; el.classList.add('show'); setTimeout(()=>el.classList.remove('show'),1800); }

document.addEventListener('click', async (event) => {
  const pageLink = event.target.closest('[data-page],[data-page-link]');
  if (pageLink) { const page=pageLink.dataset.page || pageLink.dataset.pageLink; location.hash=page; showPage(page); }
  const add = event.target.closest('[data-add]'); if (add) openModal(add.dataset.add);
  if (event.target.closest('#modal .close') || event.target === $('#modal')) closeModal();
  if (event.target.closest('#auth-captcha-modal .close') || event.target === $('#auth-captcha-modal')) closeAuthCaptcha();
  if (event.target.closest('[data-library-close]') || ['library-book-modal','library-read-modal','library-readers-modal','library-review-modal'].includes(event.target.id)) closeLibraryModals();
  if (event.target.closest('[data-library-upload]')) {
    if (!canUploadLibrary()) { toast('没有上传权限'); return; }
    $('#quick-menu').hidden = true;
    openLibraryBookModal();
    return;
  }
  const libraryFilter = event.target.closest('[data-library-filter]');
  if (libraryFilter) {
    state.library.filter = libraryFilter.dataset.libraryFilter;
    renderLibrary();
    return;
  }
  const libraryRecord = event.target.closest('[data-library-record]');
  if (libraryRecord) {
    openLibraryReadModal(libraryRecord.dataset.libraryRecord);
    return;
  }
  const libraryReaders = event.target.closest('[data-library-readers]');
  if (libraryReaders) {
    await openLibraryReaders(libraryReaders.dataset.libraryReaders);
    return;
  }
  const libraryReviews = event.target.closest('[data-library-reviews]');
  if (libraryReviews) {
    await openLibraryReviews(libraryReviews.dataset.libraryReviews);
    return;
  }
  const libraryEdit = event.target.closest('[data-library-edit]');
  if (libraryEdit) {
    const book = state.library.books.find((item) => item.id === libraryEdit.dataset.libraryEdit);
    if (!canManageLibrary() || !book) { toast('没有管理权限'); return; }
    openLibraryBookModal(book);
    return;
  }
  const libraryDelete = event.target.closest('[data-library-delete]');
  if (libraryDelete) {
    const book = state.library.books.find((item) => item.id === libraryDelete.dataset.libraryDelete);
    if (!canManageLibrary() || !book) { toast('没有管理权限'); return; }
    if (!confirm(`确定删除《${book.title}》吗？电子书、封面和全部阅读记录都会被删除。`)) return;
    try {
      await request(`/api/library/books/${book.id}`, { method:'DELETE' });
      closeLibraryModals();
      await loadLibrary();
      toast('书籍已删除');
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  const libraryReadEdit = event.target.closest('[data-library-read-edit]');
  if (libraryReadEdit) {
    const record = state.library.readers?.readers.flatMap((reader) => reader.reads).find((item) => item.id === libraryReadEdit.dataset.libraryReadEdit);
    if (record) openLibraryReadModal(libraryReadEdit.dataset.bookId, record);
    return;
  }
  const libraryReadDelete = event.target.closest('[data-library-read-delete]');
  if (libraryReadDelete) {
    if (!confirm('确定删除这条阅读记录吗？')) return;
    try {
      await request(`/api/library/books/${libraryReadDelete.dataset.bookId}/reads/${libraryReadDelete.dataset.libraryReadDelete}`, { method:'DELETE' });
      await loadLibrary();
      await openLibraryReaders(libraryReadDelete.dataset.bookId);
      toast('阅读记录已删除');
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  const libraryReviewToggle = event.target.closest('[data-library-review-toggle]');
  if (libraryReviewToggle) {
    try {
      await request(`/api/library/books/${state.library.reviewBookId}/reviews/${libraryReviewToggle.dataset.libraryReviewToggle}`, {
        method:'PATCH',
        body:JSON.stringify({ anonymous: libraryReviewToggle.dataset.libraryReviewAnonymous !== 'true' }),
      });
      await openLibraryReviews(state.library.reviewBookId);
      toast(libraryReviewToggle.dataset.libraryReviewAnonymous === 'true' ? '已取消匿名' : '已设为匿名');
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  const libraryReviewDelete = event.target.closest('[data-library-review-delete]');
  if (libraryReviewDelete) {
    if (!confirm('确定删除这条书评吗？')) return;
    try {
      await request(`/api/library/books/${state.library.reviewBookId}/reviews/${libraryReviewDelete.dataset.libraryReviewDelete}`, { method:'DELETE' });
      await openLibraryReviews(state.library.reviewBookId);
      toast('书评已删除');
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  const edit = event.target.closest('[data-edit]');
  if (edit) {
    const item = state[edit.dataset.edit]?.find((entry) => entry.id === edit.dataset.id);
    if (!item?.canManage) { toast('没有编辑权限'); return; }
    openModal(edit.dataset.edit, item);
    return;
  }
  const category = event.target.closest('[data-category]'); if (category) { state.category=category.dataset.category; render(); }
  if (event.target.closest('[data-folder-manage]')) { state.folderManaging = !state.folderManaging; render(); }
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
  if (del) {
    if (del.dataset.delete === 'folders') {
      const folder = state.folders.find((item) => item.id === del.dataset.id);
      if (!confirm(`确定删除收藏夹「${folder?.name || ''}」吗？`)) return;
      if (state.category === folder?.name) state.category = '全部';
    }
    await mutate(()=>request(`/api/${del.dataset.delete}/${del.dataset.id}`,{method:'DELETE'}),'已删除');
  }
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
  if (event.target.closest('[data-hermes-chat-new]')) {
    await createHermesChatConversation();
    return;
  }
  const hermesChatDelete = event.target.closest('[data-hermes-chat-delete]');
  if (hermesChatDelete) {
    if (state.hermesChat.sending) { toast('请先停止或等待当前回答'); return; }
    const id = hermesChatDelete.dataset.hermesChatDelete;
    const conversation = state.hermesChat.conversations.find((item) => item.id === id);
    if (!confirm(`确定删除会话「${conversation?.title || ''}」吗？`)) return;
    try {
      await request(`/api/hermes-chat/conversations/${id}`, { method:'DELETE' });
      state.hermesChat.conversations = state.hermesChat.conversations.filter((item) => item.id !== id);
      if (state.hermesChat.activeId === id) {
        state.hermesChat.activeId = state.hermesChat.conversations[0]?.id || '';
        state.hermesChat.active = null;
        if (state.hermesChat.activeId) await loadHermesChatConversation(state.hermesChat.activeId);
      }
      renderHermesChat();
      toast('会话已删除');
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  const hermesChatOpen = event.target.closest('[data-hermes-chat-open]');
  if (hermesChatOpen) {
    await loadHermesChatConversation(hermesChatOpen.dataset.hermesChatOpen);
    return;
  }
  const adminHermesDelete = event.target.closest('[data-admin-hermes-delete]');
  if (adminHermesDelete) {
    const id = adminHermesDelete.dataset.adminHermesDelete;
    const conversation = state.admin.hermesChats.find((item) => item.id === id);
    if (!confirm(`确定删除「${conversation?.username || ''}」的会话「${conversation?.title || ''}」吗？`)) return;
    try {
      await request(`/api/admin/hermes-chat/conversations/${id}`, { method:'DELETE' });
      state.admin.hermesChats = state.admin.hermesChats.filter((item) => item.id !== id);
      if (state.admin.hermesChatActive?.id === id) state.admin.hermesChatActive = null;
      renderAdmin();
      toast('会话已删除');
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  const adminHermesOpen = event.target.closest('[data-admin-hermes-open]');
  if (adminHermesOpen) {
    try {
      state.admin.hermesChatActive = await request(`/api/admin/hermes-chat/conversations/${adminHermesOpen.dataset.adminHermesOpen}`);
      renderAdmin();
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  const hermesAction = event.target.closest('[data-hermes-action]');
  if (hermesAction) {
    const action = hermesAction.dataset.hermesAction;
    if (action === 'refresh') await loadHermes();
    if (action === 'start' || action === 'stop') {
      state.hermes.loading = true;
      renderHermes();
      try {
        state.hermes = { ...state.hermes, ...await request(`/api/agents/hermes/${action}`, { method:'POST' }), loading: false };
        toast(action === 'start' ? 'Hermes 启动命令已发送' : 'Hermes 停止命令已发送');
      } catch (error) {
        state.hermes = { ...state.hermes, loading: false, running: false, message: error.message };
        toast(error.message);
      }
      renderHermes();
    }
  }
  if (event.target.closest('.mobile-menu')) $('.sidebar').classList.toggle('open');
  const shift = event.target.closest('[data-shift-date]'); if (shift) { state.planDate = shiftDate(state.planDate, Number(shift.dataset.shiftDate)); render(); }
  if (event.target.closest('[data-plan-today]')) { state.planDate = dateKey(); render(); }
  if (event.target.closest('#shuffle-excerpt')) { chooseFeaturedExcerpt(); render(); toast('换了一句'); }
});

$('#item-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const form = event.currentTarget; const type=form.dataset.type; const itemId=form.dataset.id; const payload=Object.fromEntries(new FormData(form));
  if (type === 'excerpts') payload.anonymous = Boolean(form.elements.anonymous.checked);
  if (payload.duration) payload.duration=Number(payload.duration);
  if (payload.targetCount) payload.targetCount=Number(payload.targetCount);
  const editing = Boolean(itemId);
  await mutate(()=>request(`/api/${type}${editing ? `/${itemId}` : ''}`,{method:editing ? 'PATCH' : 'POST',body:JSON.stringify(payload)}), editing ? '已更新' : '已添加'); closeModal();
});
$('#library-book-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('[type="submit"]');
  const data = new FormData(form);
  const editing = state.library.bookMode === 'edit';
  if (editing) data.delete('bookFile');
  if (!editing) {
    ['title', 'author'].forEach((name) => {
      const input = form.elements[name];
      if (input.dataset.manualValue !== 'true') data.set(name, '');
    });
  }
  button.disabled = true;
  button.textContent = editing ? '正在保存…' : '正在上传…';
  try {
    const path = editing ? `/api/library/books/${state.library.editBookId}` : '/api/library/books';
    await request(path, { method:editing ? 'PATCH' : 'POST', body:data });
    closeLibraryModals();
    await loadLibrary();
    toast(editing ? '书目信息已更新' : '电子书已上传');
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = '保存';
  }
});
$('#library-read-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('[type="submit"]');
  const readDate = form.elements.readDate.value;
  const bookId = state.library.readBookId;
  const readId = state.library.editReadId;
  const returnToReaders = Boolean(state.library.readers);
  const review = readId ? '' : form.elements.review.value.trim();
  button.disabled = true;
  try {
    const path = readId ? `/api/library/books/${bookId}/reads/${readId}` : `/api/library/books/${bookId}/reads`;
    await request(path, { method:readId ? 'PATCH' : 'POST', body:JSON.stringify({ readDate, review, reviewAnonymous: readId ? false : form.elements.reviewAnonymous.checked }) });
    $('#library-read-modal').hidden = true;
    await loadLibrary();
    if (returnToReaders) await openLibraryReaders(bookId);
    toast(readId ? '阅读日期已更新' : '已记录这次阅读');
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
});
$('#library-review-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('[type="submit"]');
  const content = form.elements.content.value.trim();
  if (!content) return;
  button.disabled = true;
  try {
    await request(`/api/library/books/${state.library.reviewBookId}/reviews`, { method:'POST', body:JSON.stringify({ content, anonymous: form.elements.anonymous.checked }) });
    form.reset();
    await openLibraryReviews(state.library.reviewBookId);
    toast('书评已发布');
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
});
document.addEventListener('input', (event) => {
  const librarySearch = event.target.closest('#library-search');
  if (librarySearch) {
    state.library.search = librarySearch.value;
    clearTimeout(state.library.searchTimer);
    state.library.searchTimer = setTimeout(() => { void loadLibrary(); }, 250);
    return;
  }
  const metadataInput = event.target.closest('#library-book-form [name="title"], #library-book-form [name="author"]');
  if (metadataInput && state.library.bookMode === 'upload') metadataInput.dataset.manualValue = 'true';
});
document.addEventListener('change', async (event) => {
  const libraryFile = event.target.closest('#library-book-form [name="bookFile"]');
  if (libraryFile) {
    const file = libraryFile.files?.[0];
    const metadata = libraryMetadataFromFilename(file?.name || '');
    const form = $('#library-book-form');
    setLibraryAutoField(form.elements.title, metadata.title);
    setLibraryAutoField(form.elements.author, metadata.author);
    $('#library-file-hint').textContent = file
      ? '已从文件名预填。你可以直接修改；未修改的值会在上传时优先使用文件内元数据。'
      : '选择文件后会从文件名预填；上传时还会读取 EPUB/PDF 元数据，可随时修改。支持格式最大 100 MB';
    return;
  }
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
let draggedFolderId = '';
document.addEventListener('dragstart', (event) => {
  const chip = event.target.closest('.folder-chip');
  if (!state.folderManaging || !chip || event.target.closest('[data-delete]')) return;
  draggedFolderId = chip.dataset.folderId;
  chip.classList.add('dragging');
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', draggedFolderId);
});
document.addEventListener('dragover', (event) => {
  const chip = event.target.closest('.folder-chip');
  if (!state.folderManaging || !chip || !draggedFolderId) return;
  event.preventDefault();
  chip.classList.add('drag-over');
});
document.addEventListener('dragleave', (event) => {
  event.target.closest('.folder-chip')?.classList.remove('drag-over');
});
document.addEventListener('drop', async (event) => {
  const chip = event.target.closest('.folder-chip');
  if (!state.folderManaging || !chip || !draggedFolderId) return;
  event.preventDefault();
  const targetId = chip.dataset.folderId;
  $$('.folder-chip').forEach((item) => item.classList.remove('drag-over', 'dragging'));
  await saveFolderOrder(draggedFolderId, targetId);
  draggedFolderId = '';
});
document.addEventListener('dragend', () => {
  draggedFolderId = '';
  $$('.folder-chip').forEach((item) => item.classList.remove('drag-over', 'dragging'));
});
$('#clear-completed').addEventListener('click', async () => { await Promise.all(state.todos.filter((t)=>t.completed).map((t)=>request(`/api/todos/${t.id}`,{method:'DELETE'}))); await load(); toast('已清空'); });
$('#global-search').addEventListener('input', (e) => { state.search=e.target.value.trim().toLowerCase(); if(state.search){showPage('bookmarks');location.hash='bookmarks'} render(); });
$('#plan-date').addEventListener('change', (event) => { if (event.target.value) { state.planDate = event.target.value; render(); } });
$('#auth-switch').addEventListener('click', () => showAuth(state.authMode === 'login' ? 'register' : 'login'));
$('#login-form').addEventListener('submit', async (event) => { event.preventDefault(); await authSubmit('/api/auth/login', event.currentTarget); });
$('#register-form').addEventListener('submit', async (event) => { event.preventDefault(); await authSubmit('/api/auth/register', event.currentTarget); });
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
$('#hermes-chat-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = $('#hermes-chat-input');
  const content = input.value.trim();
  if (!content) return;
  input.value = '';
  await sendHermesChatMessage(content);
});
$('#hermes-chat-form button').addEventListener('click', (event) => {
  if (!state.hermesChat.sending) return;
  event.preventDefault();
  void stopHermesChatMessage();
});
document.addEventListener('keydown', (e) => { if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();$('#global-search').focus()} if(e.key==='Escape'){closeModal();closeAuthCaptcha();closeLibraryModals();} });
window.addEventListener('hashchange',()=> state.user ? showPage(location.hash.slice(1)||'dashboard') : showAuth('login'));
async function mutate(action,message){try{await action();await load();toast(message)}catch(e){toast(e.message)}}
async function saveFolderOrder(draggedId, targetId) {
  if (!draggedId || !targetId || draggedId === targetId) return;
  const folders = orderedFolders();
  const from = folders.findIndex((folder) => folder.id === draggedId);
  const to = folders.findIndex((folder) => folder.id === targetId);
  if (from < 0 || to < 0) return;
  const [moved] = folders.splice(from, 1);
  folders.splice(to, 0, moved);
  state.folders = folders.map((folder, index) => ({ ...folder, sortOrder: index }));
  render();
  try {
    await Promise.all(state.folders.map((folder, index) => request(`/api/folders/${folder.id}`, { method:'PATCH', body:JSON.stringify({ sortOrder:index }) })));
    await load();
    toast('收藏夹顺序已更新');
  } catch (error) {
    await load();
    toast(error.message);
  }
}
function showPage(id){if(!state.user){showAuth('login');return}if(!$('#'+id))id='dashboard';if(id==='admin'&&!canManageAccess()){id='dashboard';toast('没有访问用户管理的权限')}if(id==='library'&&!canReadLibrary()){id='dashboard';toast('没有访问共享图书馆的权限')}if(id==='hermes-chat'&&!canUseHermesChat()){id='dashboard';toast('没有 Hermes 聊天权限')}if(id==='hermes'&&!canManageAgents()){id='dashboard';toast('没有访问智能体管理的权限')}$$('.page').forEach((p)=>p.classList.toggle('active',p.id===id));$$('.nav-link').forEach((a)=>a.classList.toggle('active',a.dataset.page===id));$('.sidebar').classList.remove('open');if(id==='admin')loadAdmin();if(id==='library'&&!state.library.books.length)loadLibrary();if(id==='hermes-chat')loadHermesChat();if(id==='hermes')loadHermes();}

async function boot() {
  const now=new Date(); $('#today-chip').textContent=new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric',weekday:'long'}).format(now); $('#greeting').textContent=`${now.getHours()<12?'早上':now.getHours()<18?'下午':'晚上'}好，欢迎回来`;
  try {
    state.user = await request('/api/auth/me');
    await loadIntegrations();
    if (returnToMusic()) return;
    showApp();
    const page = location.hash.slice(1) || 'dashboard';
    if (!location.hash) location.hash = page;
    showPage(page);
    await load();
  } catch {
    showAuth('login');
  }
}
if (window.orbitPlayCaptcha) mountAuthCaptcha();
else window.addEventListener('orbit:playcaptcha-ready', mountAuthCaptcha, { once: true });
boot();
