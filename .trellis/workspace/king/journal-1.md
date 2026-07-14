# Journal - king (Part 1)

> AI development session journal
> Started: 2026-07-04

---



## Session 1: Orbit login system and deployment progress snapshot

**Date**: 2026-07-04
**Task**: Orbit login system and deployment progress snapshot
**Branch**: `main`

### Summary

Captured current Orbit project progress after FastAPI/MySQL migration, custom folders, plans statistics, excerpts, PanSou integration, GitHub deployment, and Redis-backed dual-JWT auth rollout. Detailed snapshot saved in .trellis/workspace/king/orbit-progress-2026-07-04.md. Secrets intentionally omitted.

### Main Changes

# Orbit 当前开发进度快照

记录时间：2026-07-04  
项目路径：`/Users/king/Documents/code/a`  
线上地址：`http://123.56.29.242`

## 当前整体状态

Orbit 已经从最初的本地个人工作台推进到线上可访问版本，当前后端为 FastAPI，数据主要存储在 MySQL，登录态采用“双 JWT + Redis refresh token 状态”的方案。

当前已完成并上线的主要模块：

- 网站收藏与自定义收藏夹
- 收藏网站分类和移动收藏夹
- 日常计划/周常/月度计划
- 按日期统计每日计划完成情况
- 按计划维度查看统计
- Todo
- 书摘功能，并在主页问候语下随机展示
- PanSou 网盘搜索集成，并支持按不同网盘筛选
- MySQL 数据存储
- FastAPI 后端
- 账号注册/登录/退出
- 管理员账号
- 双 JWT 登录态
- Redis refresh token 存储与失效
- GitHub 托管
- 服务器部署

## 当前技术栈

### 后端

- Python FastAPI
- PyMySQL
- Redis Python client
- Uvicorn

关键文件：

- `backend/main.py`：API 路由、认证接口、业务接口保护
- `backend/auth.py`：密码哈希、JWT 签发/校验、Redis refresh token 状态管理
- `backend/database.py`：MySQL 初始化、旧 JSON 数据迁移
- `backend/repository.py`：业务数据 CRUD
- `backend/config.py`：环境变量配置

### 前端

- 原生 HTML/CSS/JavaScript
- Hash 路由：`#dashboard`、`#bookmarks`、`#plans`、`#todos`、`#excerpts`、`#netdisk`

关键文件：

- `public/index.html`
- `public/app.js`
- `public/styles.css`

### 存储和服务

- MySQL：业务数据和用户账号
- Redis：refresh token 的 jti 状态
- Nginx：反向代理线上 HTTP 入口
- systemd：管理 `orbit`、`redis`、`pansou`
- PanSou：独立服务，Orbit 通过 `PANSOU_BASE_URL=http://127.0.0.1:8888` 访问

## 登录系统当前设计

当前登录系统是“双 JWT + Redis”：

- `orbit_access`：短期 access token，HttpOnly Cookie，默认 15 分钟
- `orbit_refresh`：长期 refresh token，HttpOnly Cookie，默认 14 天
- Redis key：`orbit:refresh:<jti>`
- refresh token 每次续期都会轮换，旧 refresh token 立即失效
- logout 会删除 Redis 中当前 refresh token 的 key

前端逻辑：

- 访问 `/` 固定显示登录页
- 登录成功后跳转到 `/#dashboard`
- 访问工作台 hash 页面时，前端会请求 `/api/auth/me`
- access token 过期时，前端会调用 `/api/auth/refresh`
- refresh 成功则重试原请求
- refresh 失败则回到登录页

管理员账号：

- 用户名为 `admin`
- 密码已按用户要求在服务器更新
- 不在 Trellis 文档中保存明文密码

登录系统完整开发说明：

- `docs/auth-system.md`

## 线上部署状态

服务器：`123.56.29.242`

主要路径：

- Orbit 应用：`/opt/orbit`
- systemd 服务：`orbit`
- Redis 服务：`redis`
- PanSou 服务：`pansou`

当前服务状态最后一次验证：

- `orbit`：active
- `redis`：active
- Redis `dbsize`：退出测试后为 0
- 线上首页已加载新版前端脚本：`20260703-jwt-redis`

部署前备份记录：

- 登录系统 JWT/Redis 上线前备份：`/opt/orbit/data/mysql-backup-before-jwt-20260704-000536.sql`

## GitHub 状态

远程仓库：

- `https://github.com/StrongerLi1/orbit.git`

最近关键提交：

- `75f23d0 Add username password authentication`
- `fa94bd7 Redirect unauthenticated users to login`
- `9b6013b Use Redis backed JWT authentication`

当前本地未提交内容：

- Trellis 初始化文件
- `docs/auth-system.md` 登录系统开发文档
- README 中新增登录系统开发文档入口

## 最近一次已验证的登录链路

线上验证结果：

- 旧 admin 密码登录：401
- 新 admin 密码登录：成功
- `/api/auth/me`：成功返回 admin
- logout：成功
- Redis refresh key 已清空
- JWT secret 已在线上轮换，旧 access token 会失效

本地 JWT/Redis 开发验证结果：

- 未登录访问业务接口：401
- 登录后 Cookie 中存在 `orbit_access` 和 `orbit_refresh`
- refresh 成功
- refresh token 轮换后旧 refresh token 返回 401
- logout 后 Redis `dbsize` 归零
- logout 后 `/api/auth/me` 返回 401
- 浏览器访问 `/` 显示登录页
- 登录后进入 `/#dashboard`

## 当前注意事项

1. 不要把服务器密码、JWT_SECRET、数据库密码、admin 明文密码写入仓库或 Trellis 文档。
2. 当前 Cookie 的 `secure=False`，因为线上仍是 HTTP；后续如果启用 HTTPS，应改为 `secure=True`。
3. 当前用户系统只做登录保护，业务数据还没有按用户隔离；新增普通用户后看到的是同一套数据。
4. 如果要做多用户，需要给 bookmarks、todos、plans、folders、excerpts 等表增加 `user_id`。
5. Redis 挂掉会影响登录、注册、refresh、logout；已有 access token 在过期前仍能访问业务接口。
6. 管理员密码已在服务器数据库直接更新；如果本地要同步测试，需要本地数据库也更新或重新 seed。

## 适合继续推进的任务

优先级较高：

1. 增加“修改密码”功能。
2. 增加手机端更明显的当前账号/退出登录入口。
3. 实现多用户数据隔离。
4. 给 Cookie secure 增加基于环境变量的配置，方便未来 HTTPS。
5. 给登录系统补最小化自动化测试。

优先级中等：

1. 增加“退出所有设备”。
2. Redis refresh key 记录设备信息，支持查看登录设备。
3. 给管理员增加简单用户管理页面。
4. 把部署步骤整理成脚本。

## 已知用户偏好

- 用户希望先在本地跑通，再部署到线上。
- 用户倾向于功能直接可用，不希望只停在解释。
- 用户希望线上部署后也同步更新数据库和服务配置。
- 对登录页体验的期望：打开根路径 `/` 应该先看到登录页。


### Git Commits

| Hash | Message |
|------|---------|
| `75f23d0` | (see git log) |
| `fa94bd7` | (see git log) |
| `9b6013b` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: Store Orbit local secrets pointer

**Date**: 2026-07-04
**Task**: Store Orbit local secrets pointer
**Branch**: `main`

### Summary

Created a local-only Trellis secrets file at .trellis/workspace/king/secrets.local.md, added ignore rule in .trellis/.gitignore, and updated the progress snapshot with the file location. The journal entry intentionally does not include secret values.

### Main Changes

(Add details)

### Git Commits

(No commits - planning session)

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: Update Orbit progress after remembered login and local MySQL migration

**Date**: 2026-07-04
**Task**: Update Orbit progress after remembered login and local MySQL migration
**Branch**: `main`

### Summary

Updated Trellis progress snapshot after changing app entry to remember login via refresh token, deploying app.js?v=20260704-remember-login, migrating the temporary MySQL orbit database into the local Homebrew MySQL 3306 instance, resetting local MySQL root access, creating the local orbit project user, and cleaning temporary MySQL files. Secret values remain only in the ignored local secrets file.

### Main Changes

# Orbit 当前开发进度快照

记录时间：2026-07-04  
项目路径：`/Users/king/Documents/code/a`  
线上地址：`http://123.56.29.242`

## 当前整体状态

Orbit 已经从最初的本地个人工作台推进到线上可访问版本，当前后端为 FastAPI，数据主要存储在 MySQL，登录态采用“双 JWT + Redis refresh token 状态”的方案。

当前已完成并上线的主要模块：

- 网站收藏与自定义收藏夹
- 收藏网站分类和移动收藏夹
- 日常计划/周常/月度计划
- 按日期统计每日计划完成情况
- 按计划维度查看统计
- Todo
- 书摘功能，并在主页问候语下随机展示
- PanSou 网盘搜索集成，并支持按不同网盘筛选
- MySQL 数据存储
- FastAPI 后端
- 账号注册/登录/退出
- 管理员账号
- 双 JWT 登录态
- Redis refresh token 存储与失效
- GitHub 托管
- 服务器部署

## 当前技术栈

### 后端

- Python FastAPI
- PyMySQL
- Redis Python client
- Uvicorn

关键文件：

- `backend/main.py`：API 路由、认证接口、业务接口保护
- `backend/auth.py`：密码哈希、JWT 签发/校验、Redis refresh token 状态管理
- `backend/database.py`：MySQL 初始化、旧 JSON 数据迁移
- `backend/repository.py`：业务数据 CRUD
- `backend/config.py`：环境变量配置

### 前端

- 原生 HTML/CSS/JavaScript
- Hash 路由：`#dashboard`、`#bookmarks`、`#plans`、`#todos`、`#excerpts`、`#netdisk`

关键文件：

- `public/index.html`
- `public/app.js`
- `public/styles.css`

### 存储和服务

- MySQL：业务数据和用户账号
- Redis：refresh token 的 jti 状态
- Nginx：反向代理线上 HTTP 入口
- systemd：管理 `orbit`、`redis`、`pansou`
- PanSou：独立服务，Orbit 通过 `PANSOU_BASE_URL=http://127.0.0.1:8888` 访问

## 登录系统当前设计

当前登录系统是“双 JWT + Redis”：

- `orbit_access`：短期 access token，HttpOnly Cookie，默认 15 分钟
- `orbit_refresh`：长期 refresh token，HttpOnly Cookie，默认 14 天
- Redis key：`orbit:refresh:<jti>`
- refresh token 每次续期都会轮换，旧 refresh token 立即失效
- logout 会删除 Redis 中当前 refresh token 的 key

前端逻辑：

- 访问 `/` 时先尝试恢复登录态，refresh token 有效则自动进入 `/#dashboard`
- 登录态无效或用户已退出时才显示登录页
- 登录成功后跳转到 `/#dashboard`
- 访问工作台 hash 页面时，前端会请求 `/api/auth/me`
- access token 过期时，前端会调用 `/api/auth/refresh`
- refresh 成功则重试原请求
- refresh 失败则回到登录页

管理员账号：

- 用户名为 `admin`
- 密码已按用户要求在服务器更新
- 不在 Trellis 文档中保存明文密码

登录系统完整开发说明：

- `docs/auth-system.md`

## 线上部署状态

服务器：`123.56.29.242`

主要路径：

- Orbit 应用：`/opt/orbit`
- systemd 服务：`orbit`
- Redis 服务：`redis`
- PanSou 服务：`pansou`

当前服务状态最后一次验证：

- `orbit`：active
- `redis`：active
- Redis `dbsize`：退出测试后为 0
- 线上首页已加载新版前端脚本：`20260704-remember-login`

部署前备份记录：

- 登录系统 JWT/Redis 上线前备份：`/opt/orbit/data/mysql-backup-before-jwt-20260704-000536.sql`

## GitHub 状态

远程仓库：

- `https://github.com/StrongerLi1/orbit.git`

最近关键提交：

- `75f23d0 Add username password authentication`
- `fa94bd7 Redirect unauthenticated users to login`
- `9b6013b Use Redis backed JWT authentication`
- `3d01e04 Add RBAC user management`
- `414b5ca Remember login on app entry`

当前本地未提交内容：

- Trellis 初始化文件
- `docs/auth-system.md` 登录系统开发文档
- README 中新增登录系统开发文档入口
- Trellis workspace 进度记录和本地私密文件忽略配置

## 最近一次已验证的登录链路

线上验证结果：

- 旧 admin 密码登录：401
- 新 admin 密码登录：成功
- `/api/auth/me`：成功返回 admin
- logout：成功
- Redis refresh key 已清空
- JWT secret 已在线上轮换，旧 access token 会失效

本地 JWT/Redis 开发验证结果：

- 未登录访问业务接口：401
- 登录后 Cookie 中存在 `orbit_access` 和 `orbit_refresh`
- refresh 成功
- refresh token 轮换后旧 refresh token 返回 401
- logout 后 Redis `dbsize` 归零
- logout 后 `/api/auth/me` 返回 401
- 浏览器访问 `/` 显示登录页
- 登录后进入 `/#dashboard`

最近一次前端体验调整：

- 用户希望手机浏览器关闭后再打开，如果 refresh token 仍有效，不需要重新输入密码。
- 已移除根路径 `/` 强制显示登录页的逻辑。
- 现在打开 `/` 会先请求 `/api/auth/me`，必要时自动 `/api/auth/refresh`。
- 恢复成功后自动进入 `/#dashboard`。
- 恢复失败或点击退出后才显示登录页。

本机 MySQL 状态：

- Homebrew MySQL 已恢复正常运行在 `127.0.0.1:3306`。
- 已将临时 MySQL `orbit` 库迁移到本机正式 MySQL。
- 正式库当前数据量：bookmarks 73、folders 10、todos 2、plans 3、excerpts 0、users 1。
- 已创建本机项目账号，具体账号密码保存在本地私密文件 `.trellis/workspace/king/secrets.local.md`。
- 临时 MySQL 3307 已停止，相关 `/tmp/orbit-*` 临时目录和迁移 dump 已清理。

## 当前注意事项

1. 不要把服务器密码、JWT_SECRET、数据库密码、admin 明文密码写入仓库或 Trellis 文档。
2. 当前 Cookie 的 `secure=False`，因为线上仍是 HTTP；后续如果启用 HTTPS，应改为 `secure=True`。
3. 当前用户系统只做登录保护，业务数据还没有按用户隔离；新增普通用户后看到的是同一套数据。
4. 如果要做多用户，需要给 bookmarks、todos、plans、folders、excerpts 等表增加 `user_id`。
5. Redis 挂掉会影响登录、注册、refresh、logout；已有 access token 在过期前仍能访问业务接口。
6. 管理员密码已在服务器数据库直接更新；如果本地要同步测试，需要本地数据库也更新或重新 seed。

本机如需查看明文密钥，见 `.trellis/workspace/king/secrets.local.md`。该文件已被 `.trellis/.gitignore` 忽略，不应提交。

## 适合继续推进的任务

优先级较高：

1. 增加“修改密码”功能。
2. 增加手机端更明显的当前账号/退出登录入口。
3. 实现多用户数据隔离。
4. 给 Cookie secure 增加基于环境变量的配置，方便未来 HTTPS。
5. 给登录系统补最小化自动化测试。

优先级中等：

1. 增加“退出所有设备”。
2. Redis refresh key 记录设备信息，支持查看登录设备。
3. 给管理员增加简单用户管理页面。
4. 把部署步骤整理成脚本。

## 已知用户偏好

- 用户希望先在本地跑通，再部署到线上。
- 用户倾向于功能直接可用，不希望只停在解释。
- 用户希望线上部署后也同步更新数据库和服务配置。
- 对登录体验的最新期望：如果浏览器仍有有效 refresh token，打开根路径 `/` 应自动恢复登录并进入主页；点击退出后才需要重新输密码。


### Git Commits

| Hash | Message |
|------|---------|
| `414b5ca` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: Verify local RBAC MySQL migration

**Date**: 2026-07-04
**Task**: Verify local RBAC MySQL migration
**Branch**: `main`

### Summary

Updated local MySQL schema with RBAC tables and verified local RBAC API behavior after the database became available.

### Main Changes

Local MySQL RBAC verification completed after the local `orbit` database became available.

Validation performed:
- Ran `initialize_database()` successfully with local MySQL and Redis.
- Confirmed local tables: `roles`, `permissions`, `role_permissions`, `user_roles`.
- Confirmed default data: 2 roles and 5 permissions.
- Confirmed `admin` user is mapped to the `admin` role.
- Started local FastAPI service on port 3000.
- Verified unauthenticated `/api/admin/users` returns 401.
- Created a temporary admin user for validation because the existing local admin password was not overwritten by seed logic.
- Verified temporary admin login returns `roles` and `permissions`, and can access `/api/admin/users` and `/api/admin/roles`.
- Verified temporary ordinary user gets `user`, can read `/api/bookmarks`, and gets 403 for `/api/admin/users`.
- Cleaned up temporary validation users.
- Re-ran `npm test` successfully.

Important note:
- Existing local admin password was not overwritten by `ADMIN_PASSWORD`; this is expected by current seed behavior and matches `docs/auth-system.md`.


### Git Commits

| Hash | Message |
|------|---------|
| `3d01e04` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: Admin account controls

**Date**: 2026-07-04
**Task**: Admin account controls
**Branch**: `main`

### Summary

Implemented admin-managed non-admin account ban, unban, and hard-delete controls with backend enforcement, UI actions, docs, tests, and RBAC spec updates.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `6e9c8b0` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 6: Hermes Agent dashboard management

**Date**: 2026-07-07
**Task**: Hermes Agent dashboard management
**Branch**: `main`

### Summary

Added admin-only Hermes Agent management in Orbit, including start/stop/status APIs, a protected /hermes-dashboard proxy, frontend controls, production deployment notes, and tests; deployed and pushed to origin/main.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `ade70d0` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 7: Hermes chat resilient streaming

**Date**: 2026-07-11
**Task**: Hermes chat resilient streaming
**Branch**: `main`

### Summary

Implemented and deployed genuine SSE streaming, sticky Hermes worker reuse, explicit Stop, passive-disconnect background completion, 30-minute timeout, and frontend recovery polling; pushed product code to origin/main.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `44888be` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 8: Hermes Chat Page

**Date**: 2026-07-11
**Task**: Hermes Chat Page
**Branch**: `main`

### Summary

Implemented, fixed, deployed, and verified Orbit-native Hermes chat with user-owned conversations, admin visibility, resume handling, and resilient streaming.

### Main Changes

- Added Orbit-native Hermes chat permissions, database tables, backend APIs, frontend chat UI, and admin chat inspection/deletion.
- Deployed directly to `/opt/orbit` because production is not pulled from GitHub.
- Fixed Hermes resume command argument ordering so `--resume` is inserted before `-q <prompt>`.
- Added resilient streaming support in commit `44888be` and verified production service health.
- Validation included `npm test`, frontend JS syntax check, production compile/tests, service restart, DB table/role checks, and live Hermes resume verification.


### Git Commits

| Hash | Message |
|------|---------|
| `aafa7bb` | (see git log) |
| `b01e38e` | (see git log) |
| `44888be` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 9: Shared ebook library

**Date**: 2026-07-14
**Task**: Shared ebook library
**Branch**: `main`

### Summary

Implemented and deployed a shared ebook library with per-user reading history, admin catalog management, filename and EPUB/PDF metadata extraction, and embedded EPUB cover support.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `96644ae` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 10: Integrate and deploy LX Music

**Date**: 2026-07-14
**Task**: Integrate and deploy LX Music
**Branch**: `main`

### Summary

Integrated LX Music behind Orbit SSO, migrated the gateway to the HTTPS domain, deployed Orbit and LX to the server, validated authentication and route isolation, then committed and pushed the scoped product changes.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `3d83d35` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 11: 收口 HTTPS 并推送 Android

**Date**: 2026-07-14
**Task**: 收口 HTTPS 并推送 Android
**Branch**: `main`

### Summary

新增并验证 Android 客户端；将 HTTP、www 和旧 IP 308 归一到 HTTPS 裸域名，启用 Secure Cookie 与非 preload HSTS；生产部署、LX/证书续期回归和 origin/main 推送均通过。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `c1455fd` | (see git log) |
| `337b19a` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete
