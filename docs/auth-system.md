# 登录系统开发文档

本文记录 Orbit 当前登录系统的设计、核心流程、后端实现、前端交互、Redis 使用方式和部署注意事项。对应代码主要在：

- `backend/auth.py`：密码哈希、JWT 签发/校验、Redis refresh token 状态管理
- `backend/main.py`：认证 API、RBAC 管理 API 和业务 API 权限保护
- `backend/config.py`：JWT、Redis、管理员账号等环境变量
- `public/app.js`：登录页、自动续期、未登录回退逻辑和用户角色管理页

## 设计目标

登录系统解决三个问题：

1. 只有登录用户才能访问收藏、计划、待办、摘录、网盘搜索等业务接口。
2. 用户关闭浏览器后再次打开，可以在 refresh token 有效期内保持登录。
3. 退出登录后，服务端能让 refresh token 立即失效，而不是只依赖浏览器删除 Cookie。
4. 管理员可以通过固定 RBAC 角色控制用户访问和管理能力。

当前采用“双 JWT + Redis”的方案：

- access token：短期令牌，默认 15 分钟，用于访问业务接口。
- refresh token：长期令牌，默认 14 天，用于换取新的 access token。
- Redis：保存 refresh token 的 `jti`，用来判断 refresh token 是否仍然有效。

两个 token 都存放在 HttpOnly Cookie 中，前端 JavaScript 不能直接读取 token，减少 XSS 窃取 token 的风险。

## 数据存储

### MySQL

用户账号存储在 MySQL 的 `users` 表中，由 `backend/database.py` 在服务启动时自动创建：

```sql
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_admin TINYINT(1) NOT NULL DEFAULT 0,
    is_banned TINYINT(1) NOT NULL DEFAULT 0,
    created_at VARCHAR(40) NOT NULL,
    last_login_at VARCHAR(40) NOT NULL
)
```

密码不会明文保存。注册或创建管理员时，后端使用 PBKDF2-HMAC-SHA256 生成密码哈希：

- 随机盐：16 字节
- 迭代次数：260000
- 存储格式：`pbkdf2_sha256$260000$salt$digest`

RBAC 使用四张表，由 `backend/database.py` 在服务启动时自动创建：

```sql
CREATE TABLE IF NOT EXISTS roles (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS permissions (
    id VARCHAR(80) PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id VARCHAR(64) NOT NULL,
    permission_id VARCHAR(80) NOT NULL,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id VARCHAR(64) NOT NULL,
    role_id VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, role_id)
);
```

当前仍保留 `users.is_admin` 作为兼容字段。启动时会把 `is_admin = 1` 的旧用户映射到 `admin` 角色，并把没有角色的用户补成 `user` 角色。

### 默认角色和权限

当前版本使用固定角色，不开放自定义角色或权限矩阵编辑：

| 角色 | 权限 |
| --- | --- |
| `admin` | 全部权限 |
| `user` | `content:read`、`content:write`、`netdisk:search` |

权限定义：

| 权限 | 用途 |
| --- | --- |
| `content:read` | 读取业务数据 |
| `content:write` | 新增、修改、删除业务数据 |
| `netdisk:search` | 使用网盘搜索 |
| `users:manage` | 管理用户和用户角色 |
| `roles:manage` | 查看角色和权限 |

注意：本版本保留公开注册。收藏和收藏夹仍然共享；待办和计划严格按当前用户 UID 隔离，管理员也只能管理自己的记录；摘录对所有用户可读，但普通用户只能编辑或删除自己的摘录，管理员可以管理全部摘录。网盘搜索不保存业务归属。

### Redis

Redis 只保存 refresh token 的服务端状态，key 格式为：

```text
orbit:refresh:<jti>
```

value 是用户 ID，TTL 与 refresh token 有效期一致。

这样做的作用：

- refresh token 续期时，可以确认这个 token 没被服务端撤销。
- refresh token 轮换后，旧 token 的 Redis key 会被删除。
- 用户退出登录时，当前 refresh token 的 Redis key 会被删除。

## JWT 内容

### access token

access token 的 payload 包含：

```json
{
  "typ": "access",
  "sub": "用户 ID",
  "username": "用户名",
  "isAdmin": true,
  "roles": ["admin"],
  "permissions": ["content:read", "content:write", "netdisk:search", "users:manage", "roles:manage"],
  "iat": 生成时间戳,
  "exp": 过期时间戳
}
```

后端业务接口只接受 `typ=access` 的 token。

### refresh token

refresh token 的 payload 包含：

```json
{
  "typ": "refresh",
  "sub": "用户 ID",
  "username": "用户名",
  "isAdmin": true,
  "roles": ["admin"],
  "permissions": ["content:read", "content:write", "netdisk:search", "users:manage", "roles:manage"],
  "jti": "refresh token 唯一 ID",
  "iat": 生成时间戳,
  "exp": 过期时间戳
}
```

后端 refresh 接口只接受 `typ=refresh` 的 token，并且会检查 Redis 中是否存在对应 `jti`。

## Cookie 设计

当前使用两个 Cookie：

| Cookie | 用途 | 默认有效期 | HttpOnly |
| --- | --- | --- | --- |
| `orbit_access` | 访问业务 API | 15 分钟 | 是 |
| `orbit_refresh` | 刷新 access token | 14 天 | 是 |

Cookie 配置：

- `httponly=True`
- `samesite="lax"`
- `secure=False`
- `path="/"`

说明：当前线上是 HTTP 访问，所以 `secure=False`。如果后续切换 HTTPS，应改为 `secure=True`。

## 后端接口

### `POST /api/auth/register`

注册新用户。

流程：

1. 校验用户名和密码。
2. 判断用户名是否已存在。
3. 写入 `users` 表。
4. 给新用户分配默认 `user` 角色。
5. 签发 access token 和 refresh token。
6. 将 refresh token 的 `jti` 写入 Redis。
7. 设置 `orbit_access` 和 `orbit_refresh` Cookie。
8. 返回公开用户信息。

用户名规则：

- 3-32 位
- 只允许字母、数字、下划线、短横线

密码规则：

- 至少 8 位

### `POST /api/auth/login`

用户名密码登录。

流程：

1. 校验用户名和密码格式。
2. 从 MySQL 查询用户。
3. 使用 PBKDF2 校验密码。
4. 拒绝已封禁用户。
5. 更新 `last_login_at`。
6. 签发 access token 和 refresh token。
7. 写入 Redis refresh key。
8. 设置 Cookie 并返回用户信息。

### `GET /api/auth/me`

获取当前登录用户。

流程：

1. 读取 `orbit_access` Cookie。
2. 校验 JWT 签名、类型和过期时间。
3. 根据 `sub` 查询 MySQL 用户。
4. 拒绝已封禁用户。
5. 返回公开用户信息。

如果 access token 不存在、过期或无效，返回 401。

公开用户信息现在包含兼容字段和 RBAC 字段：

```json
{
  "id": "用户 ID",
  "username": "admin",
  "isAdmin": true,
  "isBanned": false,
  "roles": ["admin"],
  "permissions": ["content:read", "content:write", "netdisk:search", "users:manage", "roles:manage"],
  "createdAt": "创建时间",
  "lastLoginAt": "最后登录时间"
}
```

### `POST /api/auth/refresh`

刷新登录态。

流程：

1. 读取 `orbit_refresh` Cookie。
2. 校验 JWT 签名、类型和过期时间。
3. 获取 refresh token 中的 `jti` 和用户 ID。
4. 检查 Redis 中 `orbit:refresh:<jti>` 是否存在且 value 等于用户 ID。
5. 拒绝已封禁用户。
6. 删除旧 refresh key。
7. 重新签发一组新的 access token 和 refresh token。
8. 将新的 refresh `jti` 写入 Redis。
9. 更新 Cookie。

这个流程叫 refresh token rotation：每次刷新都会让旧 refresh token 失效。

### `POST /api/auth/logout`

退出登录。

流程：

1. 读取当前 `orbit_refresh` Cookie。
2. 从 refresh token 中解析 `jti`。
3. 删除 Redis 中对应的 refresh key。
4. 删除 `orbit_access`、`orbit_refresh` 和旧版 `orbit_session` Cookie。
5. 返回 `{ "ok": true }`。

## 业务接口保护

后端登录检查由 `require_user(request)` 完成，权限检查由 `require_permission(request, permission)` 完成。`require_user` 会拒绝已封禁用户，因此已有 access token 的封禁用户也无法继续访问业务接口。业务 API 不直接检查角色名，只检查权限：

| API | 权限 |
| --- | --- |
| `GET /api/bookmarks` 等业务读取接口 | `content:read` |
| `POST/PATCH/DELETE /api/bookmarks` 等业务写入接口 | `content:write` |
| `GET /api/netdisk/search` | `netdisk:search` |

业务数据范围由 repository/API 归属校验决定：

- `GET/POST /api/bookmarks`
- `GET/POST /api/plans`
- `GET/POST /api/todos`
- `GET/POST /api/folders`
- `GET/POST /api/excerpts`
- `GET /api/netdisk/search`
- 对应的 `PATCH`、`DELETE`

收藏、收藏夹和摘录保持共享读取；待办和计划按认证用户 UID 严格隔离，管理员也不能读取或修改他人的记录。摘录响应包含 `createdByName` 和 `canManage`，普通用户只能修改自己的摘录，管理员可以管理全部摘录。客户端传入的归属字段不会生效。

`require_user` 只认 access token，不会直接使用 refresh token 访问业务数据。access token 过期时，前端负责先调用 refresh 接口，再重试原请求。

## RBAC 管理接口

RBAC 管理接口只允许拥有对应权限的管理员访问：

| API | 权限 | 说明 |
| --- | --- | --- |
| `GET /api/admin/users` | `users:manage` | 查看用户及其角色/权限 |
| `PATCH /api/admin/users/{user_id}/roles` | `users:manage` | 修改用户角色，body 为 `{"roles":["admin"]}` 或 `{"roles":["user"]}` |
| `PATCH /api/admin/users/{user_id}/ban` | `users:manage` | 封禁或解封非管理员用户，body 为 `{"banned":true}` 或 `{"banned":false}` |
| `DELETE /api/admin/users/{user_id}` | `users:manage` | 硬删除非管理员用户，并清理其角色、阅读记录、待办和计划 |
| `GET /api/admin/roles` | `roles:manage` | 查看固定角色 |
| `GET /api/admin/permissions` | `roles:manage` | 查看固定权限 |

后端会拒绝：

- 未知角色。
- 空角色列表。
- 移除系统中最后一个管理员。
- 将已封禁用户提升为管理员。
- 封禁、解封或删除管理员账号。

角色变更会同步更新 `users.is_admin`，用于兼容旧逻辑和迁移记录。
封禁是简单的永久开关，不记录原因或到期时间；删除是硬删除，删除后相同用户名可以重新注册。

## 前端逻辑

前端登录逻辑集中在 `public/app.js`。

### 根路径行为

访问 `/` 时，前端固定显示登录页：

```js
if (!location.hash) { showAuth('login'); return; }
```

登录成功后，前端跳转到：

```text
/#dashboard
```

这样做是为了让“主页”明确等于登录页，而不是用户有 Cookie 时自动进入工作台。

### 未登录拦截

如果用户访问 `/#plans`、`/#bookmarks` 等页面：

1. 前端启动时调用 `/api/auth/me`。
2. 如果成功，显示对应页面。
3. 如果返回 401，显示登录页，并把路由回退到 `/`。

### 自动续期

前端的 `request` 方法会处理 401：

1. 普通业务请求返回 401。
2. 前端自动调用 `POST /api/auth/refresh`。
3. 如果 refresh 成功，重试原请求。
4. 如果 refresh 失败，显示登录页。

登录、注册、refresh、logout 这几个接口不会触发递归 refresh，避免死循环。

### 退出登录

点击“退出”时：

1. 前端调用 `POST /api/auth/logout`。
2. 后端删除 Redis refresh key 和 Cookie。
3. 前端显示登录页。

### 用户管理页

管理员登录后，侧边栏会显示“用户管理”。该页面会调用：

- `/api/admin/users`
- `/api/admin/roles`
- `/api/admin/permissions`
- `/api/admin/users/{user_id}/ban`
- `/api/admin/users/{user_id}`

页面支持给用户分配固定 `admin` / `user` 角色，也支持封禁、解封和删除非管理员账号。删除账号前会使用浏览器原生确认框进行二次确认。页面不支持创建新角色或编辑权限矩阵。普通用户不会看到入口；如果直接访问 `/#admin`，前端会回到概览页，后端仍会对 admin API 返回 403。

## 环境变量

本地和线上需要这些登录相关配置：

```bash
JWT_SECRET=change-me-to-a-long-random-string
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=14
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me-admin-password
```

说明：

- `JWT_SECRET`：JWT 签名密钥，线上必须使用强随机值。
- `JWT_ACCESS_MINUTES`：access token 有效期。
- `JWT_REFRESH_DAYS`：refresh token 有效期。
- `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB`：Redis 连接配置。
- `REDIS_PASSWORD`：Redis 密码，当前线上 Redis 只监听本机，所以可以为空。
- `ADMIN_USERNAME` / `ADMIN_PASSWORD`：启动时自动创建或修正管理员账号。

`SESSION_SECRET` 是旧版 Cookie session 留下的配置，现在 `JWT_SECRET` 优先；如果没有设置 `JWT_SECRET`，会回退使用 `SESSION_SECRET`。

## 管理员账号初始化

服务启动时会先调用 `seed_rbac_defaults()`，再调用 `seed_admin_user()`：

1. 创建固定权限和固定角色。
2. 写入固定角色和权限的映射。
3. 把 `is_admin = 1` 的旧用户加入 `admin` 角色。
4. 把没有角色的用户加入 `user` 角色。
5. 如果没有配置 `ADMIN_USERNAME` 或 `ADMIN_PASSWORD`，跳过管理员 seed。
6. 如果管理员用户名已存在，把该用户的 `is_admin` 修正为 `1`，并设置为 `admin` 角色。
7. 如果不存在，则创建管理员用户并设置为 `admin` 角色。

注意：如果管理员用户已存在，当前逻辑不会覆盖密码。后续如果需要修改密码，可以新增“修改密码”接口，或写一次性管理脚本。

## 本地开发启动

本地需要同时启动：

- MySQL
- Redis
- FastAPI

示例：

```bash
redis-server --port 6379
```

```bash
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=orbit
export MYSQL_PASSWORD=orbit_password
export MYSQL_DATABASE=orbit
export REDIS_HOST=127.0.0.1
export REDIS_PORT=6379
export JWT_SECRET=local-dev-secret
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=change-me-admin-password
npm start
```

## 线上部署状态

服务器上 Redis 作为 systemd 服务运行：

```bash
systemctl status redis
```

Orbit 服务依赖 MySQL 和 Redis：

```ini
After=network.target mysqld.service redis.service
Requires=mysqld.service redis.service
```

Redis 当前配置为：

- 监听：`127.0.0.1:6379`
- protected mode：开启

检查 Redis：

```bash
redis-cli -h 127.0.0.1 -p 6379 ping
```

查看 refresh token 数量：

```bash
redis-cli dbsize
```

## 验证用例

改动登录系统后，至少跑这些检查：

```bash
# 1. 未登录访问业务接口，应返回 401
curl -i http://127.0.0.1:3000/api/bookmarks

# 2. 登录，应返回用户信息并设置 orbit_access / orbit_refresh
curl -c /tmp/orbit.cookie \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"你的密码"}' \
  http://127.0.0.1:3000/api/auth/login

# 3. 登录后访问当前用户
curl -b /tmp/orbit.cookie http://127.0.0.1:3000/api/auth/me

# 4. 管理员访问 RBAC 用户列表，应成功
curl -b /tmp/orbit.cookie http://127.0.0.1:3000/api/admin/users

# 5. 管理员查看固定角色，应成功
curl -b /tmp/orbit.cookie http://127.0.0.1:3000/api/admin/roles

# 6. refresh，应成功，并轮换 refresh token
curl -b /tmp/orbit.cookie -c /tmp/orbit.cookie \
  -X POST http://127.0.0.1:3000/api/auth/refresh

# 7. logout，应删除 Redis 中对应 refresh key
curl -b /tmp/orbit.cookie -c /tmp/orbit.cookie \
  -X POST http://127.0.0.1:3000/api/auth/logout
```

预期：

- 未登录业务接口返回 401。
- 登录后 Cookie 中有 `orbit_access` 和 `orbit_refresh`。
- `/api/auth/me` 返回 `roles`、`permissions` 和 `isBanned`。
- 普通用户访问 `/api/admin/users` 返回 403。
- 已封禁用户无法登录、refresh 或继续访问受保护业务接口。
- refresh 后旧 refresh token 不能再使用。
- logout 后访问 `/api/auth/me` 返回 401。
- logout 后 Redis 中对应 refresh key 被删除。

## 常见问题

### 为什么打开 `/` 还是登录页，即使已经登录？

这是当前设计：根路径 `/` 固定作为登录页。登录后进入 `/#dashboard`。如果用户直接打开根路径，不自动跳工作台。

### 为什么 access token 过期后没有掉线？

因为前端会自动调用 `/api/auth/refresh`。只要 refresh token 还有效，并且 Redis 中对应 `jti` 存在，就会自动续期。

### 为什么退出后必须清 Redis？

JWT 本身是无状态的，如果只删除浏览器 Cookie，已经泄露或复制出去的 refresh token 仍可能在有效期内使用。Redis 保存 refresh token 状态后，退出登录可以删除对应 `jti`，让 refresh token 立即失效。

### Redis 挂了会怎样？

登录、注册、refresh、logout 会受影响，因为这些流程需要写入或读取 Redis。已有 access token 在过期前仍能访问业务接口，因为业务接口只校验 access token，不访问 Redis。

### 为什么不用 localStorage？

localStorage 容易被 XSS 读取。当前使用 HttpOnly Cookie，前端脚本不能直接读 token，安全边界更好。

## 后续可扩展点

- 增加修改密码功能。
- 增加“退出所有设备”，删除该用户所有 refresh key。
- Redis key 中增加设备信息，支持查看登录设备列表。
- 切换 HTTPS 后，将 Cookie 的 `secure` 改为 `True`。
- 如产品需要，继续为收藏和收藏夹设计多用户数据隔离。
- 如确实需要，再开放自定义角色创建和权限矩阵编辑。
