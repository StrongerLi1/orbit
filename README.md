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
export LIBRARY_STORAGE_DIR=/path/to/private/orbit-library
export LIBRARY_MAX_FILE_MB=100
export LIBRARY_MAX_COVER_MB=5
export HERMES_DASHBOARD_URL=http://127.0.0.1:9119
export HERMES_DASHBOARD_PUBLIC_PATH=/hermes-dashboard
export HERMES_STREAM_COMMAND="/path/to/hermes-agent/venv/bin/python -m backend.hermes_stream_bridge"
export HERMES_STREAM_POOL_SIZE=2
export HERMES_STREAM_POOL_WAIT_TIMEOUT=5
export HERMES_CHAT_TIMEOUT=1800
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

用户权限使用固定 RBAC 角色：`admin` 拥有全部权限，`user` 可以使用共享业务功能、网盘搜索和 Hermes 聊天。当前版本保留公开注册，新用户默认获得 `user` 角色；业务数据仍然是共享数据，Hermes 聊天会话按用户隔离保存。

登录系统的完整设计和开发说明见 [`docs/auth-system.md`](docs/auth-system.md)。RBAC 的设计原理和授权逻辑见 [`docs/rbac-design.md`](docs/rbac-design.md)。

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
- `GET/POST /api/library/books`，共享图书目录与电子书上传
- `PATCH/DELETE /api/library/books/:id`，管理员编辑或删除共享书籍
- `GET /api/library/books/:id/download`，认证下载原始电子书
- `GET/POST /api/library/books/:id/reads`，查看或新增多次阅读记录
- `PATCH/DELETE /api/library/books/:id/reads/:readId`，用户修改或删除自己的阅读记录
- `GET /api/agents/hermes/status`，`POST /api/agents/hermes/start`，`POST /api/agents/hermes/stop`，管理员管理本地 Hermes Agent dashboard
- `GET/POST /api/hermes-chat/conversations`，`GET/DELETE /api/hermes-chat/conversations/:id`，`POST /api/hermes-chat/conversations/:id/messages/stream`，`POST /api/hermes-chat/conversations/:id/messages/stop`，用户通过 SSE 使用 Orbit 自带 Hermes 聊天
- `POST /api/auth/register`，`POST /api/auth/login`，`POST /api/auth/refresh`，`POST /api/auth/logout`，`GET /api/auth/me`
- `GET /api/admin/users`，`PATCH /api/admin/users/:id/roles`，`PATCH /api/admin/users/:id/ban`，`DELETE /api/admin/users/:id`
- `GET /api/admin/roles`，`GET /api/admin/permissions`
- `GET /api/admin/hermes-chat/conversations`，`GET/DELETE /api/admin/hermes-chat/conversations/:id`，管理员查看和软删除 Hermes 聊天会话

## 网盘搜索

网盘搜索模块接入 [PanSou](https://github.com/fish2018/pansou) 的 `/api/search?kw=` 接口。推荐在服务器本机运行 PanSou 后端，并把 `PANSOU_BASE_URL` 指向 `http://127.0.0.1:8888`。

## 共享图书馆

登录用户可以上传 EPUB、PDF、MOBI、AZW3 和 UTF-8 TXT，浏览并下载共享书籍。上传时优先采用用户手写的书名、作者和封面，其次读取 EPUB/PDF 内嵌元数据，最后从文件名回退；EPUB 还可提取内嵌封面。所有用户都能记录多次阅读日期并查看读者历史；只有管理员可以编辑或删除共享书籍。电子书和封面保存在 `LIBRARY_STORAGE_DIR`，MySQL 只保存元数据。默认电子书上限为 100 MB，封面上限为 5 MB；Nginx 部署需要将 `client_max_body_size` 设置为大于 100 MB，例如 `110m`。存储目录不要放在 `public/` 下，并确保运行 Orbit 的系统用户拥有读写权限。

## Hermes Agent

管理员可以在 Orbit 中查看并管理服务器本机 [Hermes Agent](https://github.com/NousResearch/hermes-agent) dashboard。Orbit 负责启动、停止、状态检查，并通过管理员登录态保护的代理入口打开 dashboard；模型和密钥仍在 Hermes 自己的配置内管理。

默认使用 `HERMES_DASHBOARD_URL=http://127.0.0.1:9119` 和 `HERMES_DASHBOARD_PUBLIC_PATH=/hermes-dashboard`，启动命令为 `hermes dashboard --host 127.0.0.1 --port 9119 --no-open`。聊天页由 Orbit 自己渲染，后端通过 `HERMES_STREAM_COMMAND` 在 Hermes 的 Python 运行时中启动私有 worker 池，把 Hermes `run_conversation` 的真实文本增量转换为 SSE，并为每个 Orbit 会话复用 Hermes Agent 和 session id。`HERMES_STREAM_COMMAND` 应指向安装 Hermes 的虚拟环境 Python，例如 `/path/to/hermes-agent/venv/bin/python -m backend.hermes_stream_bridge`；Orbit 会自动追加 `--worker`。如果本机还没安装 Hermes，先按 Hermes 官方安装方式安装并完成配置。

流式聊天使用 `POST` + `text/event-stream`；Nginx 等反向代理需要关闭响应缓冲。用户可以停止生成，已生成的部分会以 `interrupted` 状态保存并显示“用户终止回答”。被动断线（例如手机浏览器切后台后连接被系统回收）不会停止 Hermes，Orbit 会在服务器后台继续消费并持久化最终回复；主动 Stop 使用独立 API 才会终止 worker。页面恢复或刷新后会根据会话的 `generating` 状态显示“正在思考”，每 2 秒检查一次，Hermes 完成落库后自动替换成最终回复。同一用户同时只允许一个生成任务。`HERMES_STREAM_POOL_SIZE` 默认为 2（范围 1–8），worker 最多缓存 16 个 Orbit 会话；正常完成后复用，主动停止、30 分钟超时或协议异常时销毁并补充 worker。池满时最多等待 `HERMES_STREAM_POOL_WAIT_TIMEOUT` 秒，默认 5 秒。`HERMES_CHAT_TIMEOUT=1800` 设置回答总时限为 30 分钟。

生产环境中 Orbit 通过 systemd 运行时，可以把 Hermes 绑定到服务器本机端口，并让管理员通过 Orbit 的 `/hermes-dashboard/` 代理入口访问。当前服务器使用的 drop-in 形态如下：

```ini
[Service]
Environment=HERMES_DASHBOARD_URL=http://127.0.0.1:9119
Environment="HERMES_DASHBOARD_COMMAND=env HOME=/opt/orbit HERMES_HOME=/opt/orbit/.hermes /usr/local/bin/hermes dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build"
Environment="HERMES_DASHBOARD_STOP_COMMAND=env HOME=/opt/orbit HERMES_HOME=/opt/orbit/.hermes /usr/local/bin/hermes dashboard --stop"
Environment=HERMES_DASHBOARD_TIMEOUT=5
Environment="HERMES_STREAM_COMMAND=env HOME=/opt/orbit HERMES_HOME=/opt/orbit/.hermes /usr/local/lib/hermes-agent/venv/bin/python -m backend.hermes_stream_bridge"
Environment=HERMES_STREAM_POOL_SIZE=2
Environment=HERMES_STREAM_POOL_WAIT_TIMEOUT=5
Environment=HERMES_CHAT_TIMEOUT=1800
```

## 后续适合扩展

用户登录与多设备同步、标签和全文搜索、重复计划、番茄钟、Markdown 笔记、数据导入导出、PWA 与提醒。
