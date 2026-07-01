# Orbit 个人工作台

一个轻量、私密的个人信息中心，用来管理网站收藏、日常计划、Todo 和书摘。

## 启动

后端已经迁移为 Python FastAPI，数据存储在 MySQL。

1. 安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

2. 准备 MySQL 数据库用户，例如：

```sql
CREATE USER 'orbit'@'localhost' IDENTIFIED BY 'orbit_password';
GRANT ALL PRIVILEGES ON orbit.* TO 'orbit'@'localhost';
FLUSH PRIVILEGES;
```

3. 配置环境变量，可参考 `.env.example`：

```bash
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=orbit
export MYSQL_PASSWORD=orbit_password
export MYSQL_DATABASE=orbit
export PANSOU_BASE_URL=http://127.0.0.1:8888
```

4. 启动：

```bash
npm start
```

打开 <http://localhost:3000>。开发时可运行 `npm run dev` 获得自动重启。

## 数据

首次启动会自动创建 MySQL 表；如果 MySQL 为空且存在 `data/db.json`，会自动从旧 JSON 文件迁移一次。迁移完成后，新增、完成和删除操作都会写入 MySQL。

可以直接导入 Chrome、Edge 等浏览器导出的 Netscape 书签 HTML，脚本会清理标题、自动分类并按 URL 去重：

```bash
node scripts/import-bookmarks.js /path/to/bookmarks.html
```

## API

- `GET/POST /api/bookmarks`，`PATCH/DELETE /api/bookmarks/:id`
- `GET/POST /api/plans`，`PATCH/DELETE /api/plans/:id`
- `GET/POST /api/todos`，`PATCH/DELETE /api/todos/:id`
- `GET/POST /api/folders`，`PATCH/DELETE /api/folders/:id`
- `GET/POST /api/excerpts`，`PATCH/DELETE /api/excerpts/:id`
- `GET /api/netdisk/search?kw=关键词`，代理 PanSou 网盘搜索

## 网盘搜索

网盘搜索模块接入 [PanSou](https://github.com/fish2018/pansou) 的 `/api/search?kw=` 接口。推荐在服务器本机运行 PanSou 后端，并把 `PANSOU_BASE_URL` 指向 `http://127.0.0.1:8888`。

## 后续适合扩展

用户登录与多设备同步、标签和全文搜索、重复计划、番茄钟、Markdown 笔记、数据导入导出、PWA 与提醒。
