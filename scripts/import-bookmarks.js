const fs = require('node:fs');

const source = process.argv[2];
const dryRun = process.argv.includes('--dry-run');
const apiArg = process.argv.find((arg) => arg.startsWith('--api='));
const apiBase = (apiArg ? apiArg.slice('--api='.length) : process.env.ORBIT_API || 'http://127.0.0.1:3000').replace(/\/$/, '');
if (!source) {
  console.error('用法: node scripts/import-bookmarks.js <bookmarks.html> [--dry-run] [--api=http://127.0.0.1:3000]');
  process.exit(1);
}

const html = fs.readFileSync(source, 'utf8');

function decode(value) {
  return value
    .replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)))
    .replace(/&#x([\da-f]+);/gi, (_, code) => String.fromCodePoint(parseInt(code, 16)));
}

function tidyTitle(raw, url) {
  let title = decode(raw).replace(/[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]/g, '').replace(/\s+/g, ' ').trim();
  title = title
    .replace(/^GitHub - /, '').replace(/ · GitHub$/, '')
    .replace(/ \| OpenAI$/, '').replace(/ - 知乎$/, '')
    .replace(/\s*\|\s*二哥的Java进阶之路$/, '')
    .replace(/^哔哩哔哩 \(゜-゜\)つロ 干杯~-bilibili$/, '哔哩哔哩')
    .replace(/^力扣 \(LeetCode\).*$/, '力扣 LeetCode')
    .replace(/^易转换 - .*/, '易转换')
    .replace(/^茶杯狐 Cupfox.*/, '茶杯狐 Cupfox')
    .replace(/^Google Gemini$/, 'Gemini');
  if (!title || title.length > 90) {
    try { title = new URL(url).hostname.replace(/^www\./, ''); } catch { title = '未命名网站'; }
  }
  return title;
}

function categoryFor(title, url, folders) {
  const text = `${title} ${url} ${folders.join(' ')}`.toLowerCase();
  const domain = (() => { try { return new URL(url).hostname; } catch { return ''; } })();

  if (/chatgpt|openai|gemini|qianwen|千问|llava|pandawiki|智能体|大模型|ai岗位/.test(text)) return 'AI 与智能体';
  if (/codetop|leetcode|力扣|javabetter|tobebetter|cnblogs|github\.com|mysql|计算机网络|面试|订单超时|yuque\.com/.test(text)) return '开发与学习';
  if (/overleaf|scholar|z-library|singlelogin|90tsg|ccfddl|论文|latex|图书馆/.test(text)) return '科研与阅读';
  if (/bupt|北京邮电|teams\.microsoft|feishu\.cn|飞书云文档/.test(text)) return '校园与办公';
  if (/bilibili|cupfox|switch|gamer520|seemac.*yxfl|appstorrent.*games|千禧梦|寂静岭|seerxin|电影|游戏|影视/.test(text)) return '影音与游戏';
  if (/macwk|machz|macclub|cmacked|macked|mac78|xmac|macenjoy|mac618|5v13|photolab|lensflare|mac软件|mac资源/.test(text)) return 'Mac 软件';
  if (/easeconvert|tboxn|chongbuluo|extfans|aconvert|snapany|iiilab|colostar|homebrew|brew\.sh|klakk|文件转换|视频解析|下载方法/.test(text)) return '实用工具';
  if (/机场|clash|freeair|1yunti|sms-activate|buptnet|网络|apple id/.test(text)) return '网络与账号';
  if (/xiaohongshu|500px|zhihu|bccfxs|sohu|ldxp|链动小铺/.test(text)) return '社区与生活';
  if (domain) return '其他收藏';
  return '待整理';
}

const foldersByIndent = new Map();
const imported = [];
for (const line of html.split(/\r?\n/)) {
  const indent = line.match(/^\s*/)[0].length;
  const folder = line.match(/<DT><H3[^>]*>(.*?)<\/H3>/i);
  if (folder) {
    for (const key of foldersByIndent.keys()) if (key >= indent) foldersByIndent.delete(key);
    foldersByIndent.set(indent, decode(folder[1]).trim());
    continue;
  }
  const bookmark = line.match(/<DT><A\s+HREF="([^"]+)"[^>]*>(.*?)<\/A>/i);
  if (!bookmark) continue;
  const url = decode(bookmark[1]);
  if (!/^https?:\/\//i.test(url)) continue;
  const folders = [...foldersByIndent.entries()].filter(([level]) => level < indent).sort(([a], [b]) => a - b).map(([, name]) => name);
  const title = tidyTitle(bookmark[2], url);
  imported.push({
    title, url,
    category: categoryFor(title, url, folders),
    note: folders.length ? `原书签：${folders.join(' / ')}` : '从浏览器书签导入',
    favorite: false
  });
}

function canonical(url) {
  try {
    const parsed = new URL(url);
    parsed.hash = '';
    for (const key of [...parsed.searchParams.keys()]) if (/^utm_/i.test(key)) parsed.searchParams.delete(key);
    return parsed.toString().replace(/\/$/, '');
  } catch { return url; }
}

async function api(pathname, options = {}) {
  const response = await fetch(`${apiBase}${pathname}`, {
    ...options,
    headers: { 'content-type': 'application/json', ...(options.headers || {}) }
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `请求失败：${response.status}`);
  return payload;
}

async function main() {
  const [bookmarks, folders] = await Promise.all([api('/api/bookmarks'), api('/api/folders')]);
  const existing = new Set(bookmarks.map((item) => canonical(item.url)));
  const unique = imported.filter((item) => {
    const key = canonical(item.url);
    if (existing.has(key)) return false;
    existing.add(key);
    return true;
  });
  const counts = unique.reduce((all, item) => ({ ...all, [item.category]: (all[item.category] || 0) + 1 }), {});
  console.log(JSON.stringify({ api: apiBase, found: imported.length, added: unique.length, existing: bookmarks.length, categories: counts }, null, 2));
  if (dryRun) return;

  const folderNames = new Set(folders.map((folder) => folder.name));
  for (const name of [...new Set(unique.map((item) => item.category))]) {
    if (!folderNames.has(name)) {
      await api('/api/folders', { method: 'POST', body: JSON.stringify({ name }) });
      folderNames.add(name);
    }
  }
  for (const bookmark of unique) {
    await api('/api/bookmarks', { method: 'POST', body: JSON.stringify(bookmark) });
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
