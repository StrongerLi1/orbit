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
export SESSION_SECRET=change-me-to-a-long-random-string
export JWT_SECRET=change-me-to-a-long-random-string
export REDIS_HOST=127.0.0.1
export REDIS_PORT=6379
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=change-me-admin-password
```

4. 启动：

```bash
npm start
```

打开 <http://localhost:3000>。开发时可运行 `npm run dev` 获得自动重启。

## 数据

首次启动会自动创建 MySQL 表；如果 MySQL 为空且存在 `data/db.json`，会自动从旧 JSON 文件迁移一次。迁移完成后，新增、完成和删除操作都会写入 MySQL。

登录态使用双 JWT：短期 access token 放 HttpOnly Cookie，长期 refresh token 放 HttpOnly Cookie，并在 Redis 中保存 refresh token 的 jti，用于续期和退出登录时失效。

用户权限使用固定 RBAC 角色：`admin` 拥有全部权限，`user` 可以使用共享业务功能和网盘搜索。当前版本保留公开注册，新用户默认获得 `user` 角色；业务数据仍然是共享数据，尚未按用户隔离。

登录系统的完整设计和开发说明见 [`docs/auth-system.md`](docs/auth-system.md)。

如果配置了 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`，启动时会自动创建或修正管理员账户。

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
- `POST /api/auth/register`，`POST /api/auth/login`，`POST /api/auth/refresh`，`POST /api/auth/logout`，`GET /api/auth/me`
- `GET /api/admin/users`，`PATCH /api/admin/users/:id/roles`，`PATCH /api/admin/users/:id/ban`，`DELETE /api/admin/users/:id`
- `GET /api/admin/roles`，`GET /api/admin/permissions`

## 网盘搜索

网盘搜索模块接入 [PanSou](https://github.com/fish2018/pansou) 的 `/api/search?kw=` 接口。推荐在服务器本机运行 PanSou 后端，并把 `PANSOU_BASE_URL` 指向 `http://127.0.0.1:8888`。

## 后续适合扩展

用户登录与多设备同步、标签和全文搜索、重复计划、番茄钟、Markdown 笔记、数据导入导出、PWA 与提醒。
