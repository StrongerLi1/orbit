# 收口 HTTPS 与旧 HTTP 入口

## Goal

将 Orbit 的公开业务入口收口到 `https://shawnstronger.cloud`：HTTP 80 仅保留 ACME 验证与 HTTPS 跳转，`www` 和旧 IP 统一归一到裸域名，认证 Cookie 只允许经 HTTPS 发送，同时不破坏独立的 LX TLS 网关。

## Background

- `shawnstronger.cloud` 与 `www.shawnstronger.cloud` 已解析到 `123.56.29.242`，443 使用有效的 Let's Encrypt 证书，自动续期演练通过。
- 当前 Nginx 同一个 server block 同时监听 80/443，并在 HTTP 上直接代理 Orbit；旧 IP 也直接提供业务。
- `backend/auth.py:341-349` 当前设置认证 Cookie `secure=False`，即使浏览器最终使用 HTTPS，首次 HTTP 请求仍可能携带 Cookie。
- Android 1.0.2-debug 已改为 `https://shawnstronger.cloud`、禁止明文流量，且目前没有真实 Android 用户，因此无需保留旧 IP 客户端兼容窗口。
- LX 使用 `https://shawnstronger.cloud:9528/music`，证书、未登录跳转、登录放行和封锁路由均已验证；本任务不改变其独立端口架构。
- 用户确认 LX 侧栏与 `/api/integrations` 已部署上线；HTTPS 收口后必须把它们纳入生产回归验证。

## Requirements

- 保留公网 TCP 80，保证裸地址可达和 Certbot HTTP-01 验证；除 `/.well-known/acme-challenge/` 外不在 80 提供业务内容。
- `http://shawnstronger.cloud/*`、`http://www.shawnstronger.cloud/*` 与 `http://123.56.29.242/*` 使用保留方法和请求路径的永久跳转归一到 `https://shawnstronger.cloud/*`。
- `https://www.shawnstronger.cloud/*` 永久跳转到 `https://shawnstronger.cloud/*`；裸域名 443 继续代理 Orbit、`/api/ping` 和 `/v1/`。
- Orbit access/refresh Cookie 必须带 `Secure`、`HttpOnly`、`SameSite=Lax`。
- 在裸域名 HTTPS 响应上启用 HSTS，但不启用 preload；保留未来调整 max-age/includeSubDomains 的空间。
- 保持 `https://shawnstronger.cloud:9528/music` 行为、证书和认证隔离不变。
- 修改仓库部署模板与生产服务器实际配置；生产变更前必须备份，Nginx 校验失败时立即回滚。
- 不在本任务修改 LX 侧栏/API 集成逻辑，不开放或关闭额外端口，不修改 Android 功能。

## Acceptance Criteria

- [x] AC1: HTTP 裸域名、www 与 IP 的任意普通路径均返回 308，Location 保留路径并指向 HTTPS 裸域名。
- [x] AC2: ACME challenge 路径仍可由 80 提供，Certbot 续期 dry-run 成功。
- [x] AC3: HTTPS 裸域名首页和 `/api/ping` 返回 200，`www` HTTPS 返回到裸域名的永久跳转。
- [x] AC4: 登录响应的 access/refresh Cookie 均含 `Secure; HttpOnly; SameSite=Lax`，登录、鉴权、刷新和登出回归通过。
- [x] AC5: HTTPS 响应包含不带 preload 的 HSTS；HTTP 响应不提供业务内容。
- [x] AC6: LX 9528 未登录跳转、已登录 200、封锁路由 404 与证书验证继续通过。
- [x] AC7: `npm test`、Python compileall、前端语法检查、Nginx 配置检查全部通过；生产配置和认证代码有可用回滚备份。

## Out of Scope

- 关闭 TCP 80 或改用 DNS-01 证书验证。
- HSTS preload 提交。
- 修改或重新设计已上线的 `/api/integrations` 与 LX 侧栏入口。
- 下线 9528、合并 LX 到 443、修改 Android 功能或发布 APK。
