# HTTPS 收口设计

## Boundaries

- Nginx 80：仅 ACME challenge 与 308 跳转。
- Nginx 443 裸域名：现有 Orbit、`/api/ping`、`/v1/` 代理，加 HSTS。
- Nginx 443 www：仅 308 跳转到裸域名。
- Nginx 9528：保持现有 LX TLS/auth_request 网关不变。
- FastAPI：只把 access/refresh Cookie 的 `secure` 属性改为 true。

## Request Flow

```text
HTTP domain/www/IP -> Nginx :80 -> ACME file or 308 canonical HTTPS
HTTPS www          -> Nginx :443 -> 308 apex HTTPS
HTTPS apex         -> Nginx :443 -> Orbit/Freellmapi
HTTPS apex:9528    -> Orbit auth_request -> LX loopback :9527
```

## Compatibility

- 没有旧 Android 用户，允许立即停止 IP HTTP 业务代理。
- 308 保留方法和请求体，避免 API POST 被 301/302 转成 GET；客户端不应继续把 IP 当 API origin。
- Secure Cookie 会要求本地测试使用 HTTPS TestClient origin，但不改变 token 或 SameSite 合约。
- HSTS 先不 preload，避免不可逆浏览器策略；LX 同主机 9528 已具备 TLS。

## Deployment and Rollback

- 先备份 `/etc/nginx/conf.d/orbit.conf` 与 `/opt/orbit/backend/auth.py`。
- 仓库和服务器均做最小定点修改，不部署其他未上线代码。
- 服务器先 `nginx -t`，成功后 reload；认证代码重启后立即探测 HTTPS。
- 任一业务、登录或 LX 回归失败，恢复对应备份并 reload/restart。
