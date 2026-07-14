# HTTPS 收口实施计划

1. 读取 backend/frontend 相关规范与现有测试，定位 Cookie 测试客户端和全部 Nginx 域名常量。
2. 修改 `backend/auth.py`，让认证 Cookie 带 `Secure`；只调整必要测试 origin/断言。
3. 重构 `deploy/nginx/orbit.conf`：80 ACME+308、443 apex 业务、443 www 308、HSTS；保持 9528 block 原样。
4. 运行本地验证：
   - `npm test`
   - `python3 -m compileall -q backend run.py tests`
   - `node --check public/app.js`
   - 以临时 Nginx 容器或生产 `nginx -t` 验证配置
5. 对比生产文件，备份后只部署 Nginx 收口和 Cookie Secure 两处，不覆盖或回退已上线的 LX 侧栏/API 代码。
6. reload/restart 后验证 HTTP 308、HTTPS 200、www 归一、Cookie 属性、认证生命周期、LX 9528 和证书。
7. 使用 `certbot renew --dry-run --no-random-sleep-on-renew` 验证续期；记录备份路径与回滚状态。

## Risk Files

- `backend/auth.py`：Cookie 属性会影响测试客户端与所有登录会话。
- `deploy/nginx/orbit.conf`：80/443 分离时不得遗漏 `/api/ping`、`/v1/`、WebSocket 头或上传限制。
- 生产 `/etc/nginx/conf.d/orbit.conf`：含 Certbot 管理行和已部署的 9528 TLS 网关。

## Review Gate

- [x] 用户确认没有 Android 用户，无需旧 IP 兼容。
- [x] 80 保留用于 ACME 与跳转，不关闭端口。
- [x] 不修改或回退已上线的 LX 侧栏/API 集成代码。
- [x] 不启用 HSTS preload。
- [x] 用户于 2026-07-14 批准本 PRD、设计与实施计划并要求开始实施。

## Validation Results

- Local `npm test`, Python compileall, JavaScript syntax, focused auth/LX tests, and `git diff --check`: passed.
- Public HTTP apex, www, IP, API path, and POST: 308 to canonical HTTPS with path/query preserved.
- HTTPS apex and `/api/ping`: 200 with `Strict-Transport-Security: max-age=31536000`; www: 308 to apex.
- Login and refresh: 200; access/refresh cookies include Secure, HttpOnly, and SameSite=Lax; `/api/auth/me`: 200.
- `/api/integrations`: enabled with `https://shawnstronger.cloud:9528/music`.
- LX: anonymous 302 to Orbit, authenticated final 200, blocked route 404, certificate valid.
- ACME path over port 80: 200; Certbot simulated renewal: success.
- Production Nginx and Orbit services: active; rollback backup: `/opt/orbit-backups/20260714-223657-close-http`.
