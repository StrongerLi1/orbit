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
export LX_MUSIC_PUBLIC_URL=https://shawnstronger.cloud:9528/music
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

用户权限使用固定 RBAC 角色：`admin` 拥有全部权限，`user` 可以使用业务功能、网盘搜索和 Hermes 聊天。当前版本保留公开注册，新用户默认获得 `user` 角色；收藏和收藏夹仍是共享数据，待办、计划和 Hermes 聊天会话按用户隔离，摘录对所有用户可读但只有摘录人本人或管理员可以编辑、删除。Web 端的“写点什么”支持纯文本日记或短句，每篇可选仅自己可见/公开及实名/匿名；私密内容仅作者可读，管理员也不能在产品内访问。

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
- `GET/POST /api/writings`，`PATCH/DELETE /api/writings/:id`，Web 写作内容；返回公开内容和当前用户自己的私密内容
- `GET /api/netdisk/search?kw=关键词`，代理 PanSou 网盘搜索
- `GET /api/integrations`，返回当前登录用户可见的外部服务入口
- `GET /api/library/books?q=关键词`，按书名或作者搜索共享图书目录；`POST /api/library/books` 上传电子书
- `PATCH/DELETE /api/library/books/:id`，管理员编辑或删除共享书籍
- `GET /api/library/books/:id/download`，认证下载原始电子书
- `GET/POST /api/library/books/:id/reads`，查看或新增多次阅读记录
- `PATCH/DELETE /api/library/books/:id/reads/:readId`，用户修改或删除自己的阅读记录
- `GET/POST /api/library/books/:id/reviews`，查看或发布独立书评；已读未读用户均可发布，可选择匿名
- `PATCH /api/library/books/:id/reviews/:reviewId`，作者切换书评匿名状态；`DELETE` 用户删除自己的书评，管理员可删除全部书评
- `GET /api/agents/hermes/status`，`POST /api/agents/hermes/start`，`POST /api/agents/hermes/stop`，管理员管理本地 Hermes Agent dashboard
- `GET/POST /api/hermes-chat/conversations`，`GET/DELETE /api/hermes-chat/conversations/:id`，`POST /api/hermes-chat/conversations/:id/messages/stream`，`POST /api/hermes-chat/conversations/:id/messages/stop`，用户通过 SSE 使用 Orbit 自带 Hermes 聊天
- `POST /api/auth/register`，`POST /api/auth/login`，`POST /api/auth/refresh`，`POST /api/auth/logout`，`GET /api/auth/me`
- `GET /api/admin/users`，`PATCH /api/admin/users/:id/roles`，`PATCH /api/admin/users/:id/ban`，`DELETE /api/admin/users/:id`
- `GET /api/admin/roles`，`GET /api/admin/permissions`
- `GET /api/admin/hermes-chat/conversations`，`GET/DELETE /api/admin/hermes-chat/conversations/:id`，管理员查看和软删除 Hermes 聊天会话

## 网盘搜索

网盘搜索模块接入 [PanSou](https://github.com/fish2018/pansou) 的 `/api/search?kw=` 接口。推荐在服务器本机运行 PanSou 后端，并把 `PANSOU_BASE_URL` 指向 `http://127.0.0.1:8888`。

## 共享图书馆

登录用户可以上传 EPUB、PDF、MOBI、AZW3 和 UTF-8 TXT，浏览并下载共享书籍。上传时优先采用用户手写的书名、作者和封面，其次读取 EPUB/PDF/AZW3 内嵌元数据，最后从文件名回退；EPUB 和 AZW3 可提取 JPEG、PNG 或 WebP 内嵌封面，PDF 默认将完整第一页生成白底 JPEG 封面。所有用户都能记录多次阅读日期、查看读者历史并发布独立书评；摘录和书评都支持匿名展示，作者本人可看到真实用户名和匿名标识，其他普通用户看到“匿名用户”。只有评论作者可以删除和切换自己书评的匿名状态，管理员可以删除全部书评，阅读记录表单也支持可选书评和匿名发布。只有管理员可以编辑或删除共享书籍。电子书和封面保存在 `LIBRARY_STORAGE_DIR`，MySQL 只保存元数据。默认电子书上限为 100 MB，封面上限为 5 MB；Nginx 部署需要将 `client_max_body_size` 设置为大于 100 MB，例如 `110m`。存储目录不要放在 `public/` 下，并确保运行 Orbit 的系统用户拥有读写权限。

## LX Music

Orbit 只提供 LX Music 入口和登录网关，[lxserver](https://github.com/XCQ0607/lxserver) 保持独立进程、独立数据和独立升级。设置 `LX_MUSIC_PUBLIC_URL=https://shawnstronger.cloud:9528/music` 后，登录用户侧栏会出现“音乐”并在新标签页打开；未配置时入口隐藏。浏览器访问 9528 时，Nginx 使用同一域名下的 Orbit Cookie 调用 `/api/auth/me`，未登录则跳到固定的 `https://shawnstronger.cloud/?next=music`，登录后再返回音乐页。Orbit Cookie 和认证头在代理到 LX 前会被删除。

部署制品位于 [`deploy/lxserver/`](deploy/lxserver/)：镜像固定 lxserver v1.9.4 的提交 `0d653bf31b19635dd20299c5b341630b426c79f3`、源码包 SHA-256、Alpine 与 Node 22 基础镜像摘要，并在构建阶段将存在安全公告的 `ws 8.20.1` 升级为 `8.21.0`。先复制 `lxserver.env.example` 为不入库的 `lxserver.env`，生成强随机 `FRONTEND_PASSWORD`，创建 `data`、`logs` 并授予容器 UID 10001 写权限，然后使用 Compose，或在 Podman 服务器安装 `orbit-lxserver.service`。LX 只发布 `127.0.0.1:9527`，公网只开放 Nginx 9528；网关配置见 [`deploy/nginx/orbit.conf`](deploy/nginx/orbit.conf)。

Web 播放器和管理后台均通过 Orbit 登录网关；管理后台地址为 `https://shawnstronger.cloud:9528/_orbit_lx_admin/`，进入后仍需独立的 LX `FRONTEND_PASSWORD`。LX 客户端同步和 Subsonic 不开放。`data/` 内含缓存和下载音乐，`logs/` 保存日志，两者都应纳入备份；重建容器不能删除这两个目录。升级时必须先审查上游路由变化、更新固定提交和校验值、重新运行 `npm audit --omit=dev`，并复测管理入口、同步和 Subsonic 边界。回滚时清空 `LX_MUSIC_PUBLIC_URL` 隐藏入口、移除 9528 Nginx server block、停止 LX 服务，但保留数据目录。

Orbit 与 LX 网关均使用 `shawnstronger.cloud` 的 HTTPS 证书；续期时需确保 Nginx reload 后 443 和 9528 都加载新证书。LX 的 Apache-2.0 许可证不覆盖音乐内容、第三方音源或音乐平台条款，部署和使用者需要自行确认合规性。

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
