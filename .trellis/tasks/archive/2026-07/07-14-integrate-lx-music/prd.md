# 接入 LX Music 服务

## Goal

在 Orbit 中提供一个可靠的音乐入口：`XCQ0607/lxserver` 保持独立部署和独立升级，但浏览器访问统一使用 Orbit 登录态。使用 `shawnstronger.cloud` 的 HTTPS 独立网关端口；已登录用户直接进入 LX，未登录用户先进入 Orbit 登录页，成功后自动返回 LX。

## Confirmed Facts

- Orbit 的生产入口由 Nginx 转发到 FastAPI，`shawnstronger.cloud` 和 `www.shawnstronger.cloud` 均解析到服务器并由 Let's Encrypt 证书提供 HTTPS。
- 音乐网关已从临时 IP 地址迁移为 `https://shawnstronger.cloud:9528/music`，底层 LX 容器仅监听服务器本机 `127.0.0.1:9527`。
- 用户先批准本地完成 Orbit 接入并将 LX 直接部署到现有服务器，随后明确授权把 Orbit 接入代码发布到同一服务器；代码仍不推送远程仓库。
- Orbit 已有登录后侧栏入口，普通用户和管理员通过现有权限集合控制功能可见性（`public/index.html:36-50`, `backend/auth.py:24-54`）。
- 过往 Hermes 集成确立了“外部服务保持独立、Orbit 只拥有入口和必要运维边界”的项目惯例；但 Hermes 的同端口代理模式不能直接复用到 LX，因为 LX 会占用多个根 `/api/*` 路由。
- `lxserver` v1.9.4 是 Node.js 服务，包含 Web 播放器、LX Music 同步 WebSocket、管理后台和 Subsonic API；官方支持 Docker 部署并默认监听 9527。
- `lxserver` 的播放器路径可配置，但浏览器 API 仍大量使用根 `/api/music/*`、`/api/user/*` 和 `/api/admin/*`；因此与 Orbit 共用同一监听端口会产生路由冲突和持续维护成本。
- Orbit 只保存密码哈希，登录后使用签名 Cookie；`lxserver` 则直接比较自己的用户密码，并用该密码派生 LX 客户端同步密钥。两边无法安全地从现有存储互相还原或复用密码。
- HTTP Cookie 按主机和路径匹配，不按端口隔离。同一域名的音乐网关端口会收到 Orbit Cookie，因此可以直接验证 Orbit 登录态，但必须在代理到 LX 前删除 Cookie 和认证头。
- 上游仍有反向代理登录、自定义根路径同步和 CPU 占用相关的开放问题；MVP 不依赖这些未稳定能力。
- v1.9.4 锁定的 `ws` 版本受 GHSA-96hv-2xvq-fx4p 影响。公网部署前必须使用已升级到 `ws >= 8.21.0` 的可复现镜像，并运行验证。
- `lxserver` 代码使用 Apache-2.0；音乐内容、第三方音源和平台使用条款不由该代码许可证覆盖。

## Requirements

- 将 LX Music 作为独立容器服务部署，不把其源代码、依赖或进程嵌入 Orbit FastAPI。
- 使用同一域名上的独立 TLS Nginx 监听端口承载 LX 页面和根 `/api/*`，不让 LX 路由进入 Orbit 的 443 端口路由树。
- Orbit 登录后的侧栏向所有已登录用户显示“音乐”入口，指向配置的公共 LX URL。
- “音乐”入口在新标签页打开，避免离开 Orbit 或返回工作台时中断 LX 播放。
- LX 入口 URL 通过环境变量配置；未配置时入口隐藏，避免部署不完整时出现死链接。
- 浏览器访问音乐端口时必须先通过 Nginx `auth_request` 调用 Orbit：有效 Orbit Cookie 直接放行；无效或缺失时跳转 Orbit 登录页，登录成功后安全返回原音乐地址。
- 返回地址必须限定为当前 Orbit 域名和已配置的音乐端口，不得接受任意外部 URL，不得在 URL 中携带 Orbit access/refresh token。
- Nginx 在把请求转发给 `lxserver` 前必须删除 `Cookie`、`Authorization` 和内部身份头，第三方服务进程不得收到 Orbit 凭据。
- 网关每次请求都使用现有 Orbit 登录态并查询当前用户状态；Orbit 退出登录后 Cookie 被清除，封禁或删除用户后校验立即失败。
- LX Web 播放器关闭自身的全局播放器密码，由 Orbit SSO 网关承担浏览器入口认证。
- Web 播放器和 LX 管理后台通过 Orbit 登录网关开放；管理后台还必须校验独立的 LX 强随机管理密码。LX 桌面/手机客户端同步入口和 Subsonic 接口仍不开放，不创建或同步 LX 原生用户。
- LX 配置、升级和维护通过服务器环境变量及容器操作完成；管理密码仍必须使用强随机值，防止遗漏的管理 API 被猜中。
- 不得为了复用密码而让 Orbit 保存、记录或转发用户明文密码。
- 提供可复现的容器构建/编排配置，持久化 LX 的 `data`、`logs`、`cache` 和 `music` 目录。
- 基础镜像或构建必须固定版本，不使用不可追踪的 `latest` 作为生产来源。
- 示例配置必须启用公开用户限制、关闭遥测，并限制容器 CPU/内存。
- Nginx 配置必须支持 LX Web 播放器的页面、根 API 和长连接，同时保持 Orbit 现有 80 端口路由行为不变。
- 更新 `.env.example` 和 README，说明 IP/端口访问、SSO 边界、数据目录、安全设置和后续迁移到域名的方式。
- 添加最小自动验证，覆盖入口在配置存在/缺失时的行为、认证网关和安全返回地址；完整 `npm test` 必须继续通过。
- 本地完成并验证 Orbit 接入代码和部署制品，不在本机运行 LX 服务。
- 在现有服务器部署 LX 容器、Nginx 9528 网关并完成远程健康检查；部署前保留可回滚配置，失败时不得影响 Orbit 80 端口。
- 不推送代码；服务器发布仅包含 LX 接入所需的 Orbit 增量，不得夹带同一工作区的图书馆、Android 或其他未完成改动。

## Acceptance Criteria

- [x] 配置 `LX_MUSIC_PUBLIC_URL` 后，所有登录用户可从 Orbit 侧栏打开 LX Web 播放器；未配置时不显示入口。
- [x] “音乐”入口使用新标签页并设置安全的 opener 隔离。
- [x] 已登录 Orbit 的浏览器进入音乐端口时无需再次输入密码；未登录浏览器被带到 Orbit 登录页，登录成功后自动返回原音乐地址。
- [x] SSO 流程不在 URL 暴露 Orbit token，并拒绝外部返回地址和开放重定向。
- [x] 音乐端口请求只有在 Orbit 会话有效且用户仍有效时才转发到 LX；Orbit Cookie、Authorization 和内部身份头不泄露给 LX 进程。
- [x] Orbit 退出登录后 LX 请求立即失败；封禁或删除用户后其全部 LX 请求立即失败。
- [x] LX 原生同步和 Subsonic 不通过音乐端口开放；管理页面必须同时经过 Orbit 会话和 LX 独立管理密码。
- [x] LX 服务使用独立监听端口，Orbit 80/443 端口的 `/api/*`、认证和现有功能不被 LX 路由接管。
- [x] 容器构建使用固定上游版本，并将生产 `ws` 依赖升级到不受 GHSA-96hv-2xvq-fx4p 影响的版本。
- [x] LX 数据、日志、缓存和音乐目录位于持久卷中，容器重建不会删除用户数据。
- [x] 示例生产配置没有默认管理密码、无限资源或默认遥测等不安全设置。
- [x] Nginx 示例完整转发 LX Web 页面、播放器 API 和长连接，并保留必要的客户端地址/协议头。
- [x] README 明确 HTTPS 与证书续期、独立部署边界、升级方式、备份目录、版权边界和上线前检查。
- [x] `npm test` 与新增的最小验证通过，本机没有运行 LX 服务。
- [x] 服务器 LX 容器和 9528 网关已部署并通过未登录跳转、登录放行、凭据隔离、路由封锁和 Orbit 80/443 端口回归检查。
- [x] 未推送代码；Orbit LX 接入增量已发布到服务器并通过登录回跳验证。

## Out of Scope

- Orbit 与 LX 共享密码、自动同步密码或把 Orbit Cookie 交给 LX 进程。
- LX 桌面/手机客户端歌单同步、Subsonic 客户端接入和独立同步密码。
- Orbit 管理员角色自动映射；当前管理后台使用 Orbit 会话加独立 LX 管理密码，不自动映射角色。
- 将 LX 页面嵌入 Orbit DOM、iframe 或 Android WebView。
- 在 Orbit 后端实现 LX 音乐搜索、播放、缓存或 Subsonic 协议。
- 修改上游同步协议或长期维护一个功能分叉。
- 自动创建 DNS、申请新域名证书或推送代码。
