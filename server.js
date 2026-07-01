const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');

const PORT = Number(process.env.PORT) || 3000;
const PUBLIC_DIR = path.join(__dirname, 'public');
const DATA_DIR = path.join(__dirname, 'data');
const DB_FILE = path.join(DATA_DIR, 'db.json');
const localDate = (date = new Date()) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

const seed = {
  excerpts: [],
  folders: [
    { id: crypto.randomUUID(), name: '阅读', createdAt: new Date().toISOString() },
    { id: crypto.randomUUID(), name: '工具', createdAt: new Date().toISOString() },
    { id: crypto.randomUUID(), name: '灵感', createdAt: new Date().toISOString() }
  ],
  bookmarks: [
    { id: crypto.randomUUID(), title: 'Readwise Reader', url: 'https://readwise.io/read', category: '阅读', note: '稍后读与高亮整理', favorite: true, createdAt: new Date().toISOString() },
    { id: crypto.randomUUID(), title: 'Linear', url: 'https://linear.app', category: '工具', note: '简洁的项目管理', favorite: false, createdAt: new Date().toISOString() },
    { id: crypto.randomUUID(), title: 'Are.na', url: 'https://www.are.na', category: '灵感', note: '收集视觉与想法', favorite: true, createdAt: new Date().toISOString() }
  ],
  todos: [
    { id: crypto.randomUUID(), title: '整理本周收藏', priority: 'medium', dueDate: '', completed: false, createdAt: new Date().toISOString() },
    { id: crypto.randomUUID(), title: '完成个人工作台第一版', priority: 'high', dueDate: new Date().toISOString().slice(0, 10), completed: false, createdAt: new Date().toISOString() }
  ],
  plans: [
    { id: crypto.randomUUID(), title: '晨间阅读', frequencyType: 'daily', targetCount: 1, startDate: localDate(), endDate: '', completions: {}, time: '08:00', duration: 30, color: 'violet', createdAt: new Date().toISOString() },
    { id: crypto.randomUUID(), title: '专注工作', frequencyType: 'daily', targetCount: 1, startDate: localDate(), endDate: '', completions: {}, time: '09:30', duration: 90, color: 'orange', createdAt: new Date().toISOString() },
    { id: crypto.randomUUID(), title: '晚间复盘', frequencyType: 'daily', targetCount: 1, startDate: localDate(), endDate: '', completions: {}, time: '21:30', duration: 20, color: 'green', createdAt: new Date().toISOString() }
  ]
};

async function readDb() {
  await fs.mkdir(DATA_DIR, { recursive: true });
  try {
    const data = JSON.parse(await fs.readFile(DB_FILE, 'utf8'));
    let changed = false;
    if (!Array.isArray(data.folders)) {
      const names = [...new Set((data.bookmarks || []).map((item) => item.category).filter(Boolean))];
      data.folders = names.map((name) => ({ id: crypto.randomUUID(), name, createdAt: new Date().toISOString() }));
      changed = true;
    }
    if (!Array.isArray(data.excerpts)) { data.excerpts = []; changed = true; }
    for (const plan of data.plans || []) {
      if (!plan.frequencyType) {
        const originalDate = plan.date || localDate();
        plan.frequencyType = 'daily';
        plan.targetCount = 1;
        plan.startDate = originalDate;
        plan.endDate = '';
        plan.completions = plan.completed ? { [originalDate]: 1 } : {};
        changed = true;
      }
      if (!plan.completions || typeof plan.completions !== 'object' || Array.isArray(plan.completions)) {
        plan.completions = {};
        changed = true;
      }
    }
    if (changed) await writeDb(data);
    return data;
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    await writeDb(seed);
    return structuredClone(seed);
  }
}

async function writeDb(data) {
  await fs.mkdir(DATA_DIR, { recursive: true });
  const temp = `${DB_FILE}.tmp`;
  await fs.writeFile(temp, JSON.stringify(data, null, 2));
  await fs.rename(temp, DB_FILE);
}

function json(res, status, payload) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
}

async function body(req) {
  let raw = '';
  for await (const chunk of req) {
    raw += chunk;
    if (raw.length > 1_000_000) throw new Error('Payload too large');
  }
  return raw ? JSON.parse(raw) : {};
}

function validate(type, input) {
  const item = { ...input };
  delete item.id;
  delete item.createdAt;
  if (type === 'folders') {
    if (!String(item.name || '').trim()) throw new Error('收藏夹名称不能为空');
    return { name: String(item.name).trim().slice(0, 30) };
  }
  if (type === 'excerpts') {
    if (!String(item.content || '').trim()) throw new Error('摘录内容不能为空');
    item.content = String(item.content).trim().slice(0, 3000);
    item.source = String(item.source || '').trim().slice(0, 200);
    item.author = String(item.author || '').trim().slice(0, 100);
    item.excerptDate = String(item.excerptDate || '');
    item.note = String(item.note || '').trim().slice(0, 500);
    if (item.excerptDate && !/^\d{4}-\d{2}-\d{2}$/.test(item.excerptDate)) throw new Error('请输入有效日期');
    return item;
  }
  if (!String(item.title || '').trim()) throw new Error('标题不能为空');
  item.title = item.title.trim();
  if (type === 'bookmarks') {
    try { item.url = new URL(item.url).toString(); } catch { throw new Error('请输入有效的网址'); }
    item.category = String(item.category || '未分类').trim();
    item.note = String(item.note || '').trim();
    item.favorite = Boolean(item.favorite);
  }
  if (type === 'todos') {
    item.priority = ['low', 'medium', 'high'].includes(item.priority) ? item.priority : 'medium';
    item.dueDate = String(item.dueDate || '');
    item.completed = Boolean(item.completed);
  }
  if (type === 'plans') {
    item.frequencyType = ['daily', 'weekly', 'monthly'].includes(item.frequencyType) ? item.frequencyType : 'daily';
    item.targetCount = Math.max(1, Math.min(99, Math.round(Number(item.targetCount) || 1)));
    item.startDate = String(item.startDate || item.date || '');
    item.endDate = String(item.endDate || '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(item.startDate)) throw new Error('请选择开始日期');
    if (item.endDate && !/^\d{4}-\d{2}-\d{2}$/.test(item.endDate)) throw new Error('请输入有效结束日期');
    if (item.endDate && item.endDate < item.startDate) throw new Error('结束日期不能早于开始日期');
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(item.time || '')) throw new Error('请输入有效时间');
    item.duration = Math.max(5, Math.min(480, Number(item.duration) || 30));
    item.color = ['violet', 'orange', 'green', 'blue'].includes(item.color) ? item.color : 'violet';
    const completions = item.completions && typeof item.completions === 'object' && !Array.isArray(item.completions) ? item.completions : {};
    item.completions = Object.fromEntries(Object.entries(completions)
      .filter(([date]) => /^\d{4}-\d{2}-\d{2}$/.test(date))
      .map(([date, count]) => [date, Math.max(0, Math.min(99, Math.round(Number(count) || 0)))])
      .filter(([, count]) => count > 0));
  }
  return item;
}

async function api(req, res, pathname) {
  const parts = pathname.split('/').filter(Boolean);
  const type = parts[1];
  const id = parts[2];
  if (!['bookmarks', 'todos', 'plans', 'folders', 'excerpts'].includes(type)) return json(res, 404, { error: 'Not found' });
  const db = await readDb();

  if (req.method === 'GET' && !id) return json(res, 200, db[type]);
  if (req.method === 'POST' && !id) {
    const valid = validate(type, await body(req));
    if (type === 'folders' && db.folders.some((folder) => folder.name.toLowerCase() === valid.name.toLowerCase())) {
      return json(res, 409, { error: '这个收藏夹已经存在' });
    }
    const item = { id: crypto.randomUUID(), ...valid, createdAt: new Date().toISOString() };
    db[type].unshift(item);
    await writeDb(db);
    return json(res, 201, item);
  }
  const index = db[type].findIndex((item) => item.id === id);
  if (index < 0) return json(res, 404, { error: '记录不存在' });
  if (req.method === 'PATCH') {
    db[type][index] = { ...db[type][index], ...validate(type, { ...db[type][index], ...await body(req) }) };
    await writeDb(db);
    return json(res, 200, db[type][index]);
  }
  if (req.method === 'DELETE') {
    if (type === 'folders' && db.bookmarks.some((bookmark) => bookmark.category === db.folders[index].name)) {
      return json(res, 409, { error: '请先移动收藏夹内的网站' });
    }
    const [removed] = db[type].splice(index, 1);
    await writeDb(db);
    return json(res, 200, removed);
  }
  return json(res, 405, { error: 'Method not allowed' });
}

async function staticFile(req, res, pathname) {
  const requested = pathname === '/' ? 'index.html' : pathname.slice(1);
  const file = path.normalize(path.join(PUBLIC_DIR, requested));
  if (!file.startsWith(PUBLIC_DIR)) return json(res, 403, { error: 'Forbidden' });
  const ext = path.extname(file);
  const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml' }[ext] || 'application/octet-stream';
  try {
    const content = await fs.readFile(file);
    res.writeHead(200, { 'content-type': mime, 'cache-control': 'no-cache' });
    res.end(content);
  } catch (error) {
    if (error.code === 'ENOENT') return json(res, 404, { error: 'Not found' });
    throw error;
  }
}

const server = http.createServer(async (req, res) => {
  try {
    const { pathname } = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    if (pathname.startsWith('/api/')) return await api(req, res, pathname);
    return await staticFile(req, res, pathname);
  } catch (error) {
    console.error(error);
    return json(res, error instanceof SyntaxError ? 400 : 422, { error: error.message || '服务器错误' });
  }
});

server.listen(PORT, () => console.log(`Orbit is running at http://localhost:${PORT}`));

module.exports = { server, validate };
