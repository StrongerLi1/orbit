import base64
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import redis
from fastapi import HTTPException, Request, Response

from .config import settings
from .database import connection, now_iso


ACCESS_COOKIE = "orbit_access"
REFRESH_COOKIE = "orbit_refresh"
OLD_SESSION_COOKIE = "orbit_session"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
PLAYCAPTCHA_TOKEN_SECONDS = 5 * 60

PERMISSIONS = {
    "content:read": "读取共享业务数据",
    "content:write": "新增、修改和删除共享业务数据",
    "netdisk:search": "使用网盘搜索",
    "folders:manage": "管理收藏夹标签",
    "library:read": "查看和下载共享图书馆内容",
    "library:upload": "上传共享图书馆书籍",
    "library:manage": "编辑和删除共享图书馆书籍",
    "hermes:chat": "使用 Hermes 聊天",
    "agents:manage": "管理本地智能体服务",
    "users:manage": "管理用户和用户角色",
    "roles:manage": "查看角色和权限",
}

ROLES = {
    "admin": {
        "description": "管理员，拥有全部权限",
        "permissions": tuple(PERMISSIONS.keys()),
    },
    "user": {
        "description": "普通用户，可使用共享业务功能",
        "permissions": (
            "content:read",
            "content:write",
            "netdisk:search",
            "library:read",
            "library:upload",
            "hermes:chat",
        ),
    },
}


def validate_credentials_input(username: str, password: str) -> tuple[str, str]:
    username = (username or "").strip()
    password = password or ""
    if not USERNAME_RE.fullmatch(username):
        raise HTTPException(status_code=422, detail="用户名只能包含字母、数字、下划线和短横线，长度 3-32 位")
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="密码至少需要 8 位")
    return username, password


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return "pbkdf2_sha256$260000$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_raw, digest_raw = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_raw.encode())
        expected = base64.urlsafe_b64decode(digest_raw.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _ordered(values: set[str], order: list[str] | tuple[str, ...]) -> list[str]:
    return [value for value in order if value in values]


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    roles, permissions = user_access(row)
    return {
        "id": row["id"],
        "username": row["username"],
        "isAdmin": "admin" in roles or bool(row["is_admin"]),
        "isBanned": bool(row.get("is_banned")),
        "roles": roles,
        "permissions": permissions,
        "createdAt": row["created_at"],
        "lastLoginAt": row.get("last_login_at") or "",
    }


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            return cursor.fetchone()


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cursor.fetchone()


def user_access(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    if isinstance(row.get("roles"), list) and isinstance(row.get("permissions"), list):
        return row["roles"], row["permissions"]

    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.name AS role_name, p.name AS permission_name
                FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                LEFT JOIN role_permissions rp ON rp.role_id = r.id
                LEFT JOIN permissions p ON p.id = rp.permission_id
                WHERE ur.user_id = %s
                """,
                (row["id"],),
            )
            rows = cursor.fetchall()

    roles = {item["role_name"] for item in rows if item.get("role_name")}
    permissions = {item["permission_name"] for item in rows if item.get("permission_name")}
    if bool(row.get("is_admin")):
        roles.add("admin")
        permissions.update(ROLES["admin"]["permissions"])
    if not roles:
        roles.add("user")
        permissions.update(ROLES["user"]["permissions"])
    return _ordered(roles, tuple(ROLES.keys())), _ordered(permissions, tuple(PERMISSIONS.keys()))


def attach_user_access(row: dict[str, Any]) -> dict[str, Any]:
    roles, permissions = user_access(row)
    return {**row, "roles": roles, "permissions": permissions}


def list_permissions() -> list[dict[str, str]]:
    return [{"name": name, "description": description} for name, description in PERMISSIONS.items()]


def list_roles() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": details["description"],
            "permissions": list(details["permissions"]),
        }
        for name, details in ROLES.items()
    ]


def list_users() -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
            return [public_user(user) for user in cursor.fetchall()]


def set_user_roles(user_id: str, roles: list[str]) -> dict[str, Any]:
    wanted = list(dict.fromkeys(str(role or "").strip() for role in roles))
    wanted = [role for role in wanted if role]
    if not wanted:
        raise HTTPException(status_code=422, detail="用户至少需要一个角色")
    unknown = [role for role in wanted if role not in ROLES]
    if unknown:
        raise HTTPException(status_code=422, detail="包含未知角色")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    current_roles, _ = user_access(user)
    if "admin" in current_roles and "admin" not in wanted and count_admin_users() <= 1:
        raise HTTPException(status_code=409, detail="不能移除最后一个管理员")
    if "admin" in wanted and bool(user.get("is_banned")):
        raise HTTPException(status_code=409, detail="请先解除封禁再设为管理员")

    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
            for role in wanted:
                cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", (user_id, role))
            cursor.execute("UPDATE users SET is_admin = %s WHERE id = %s", (1 if "admin" in wanted else 0, user_id))
    return public_user(get_user_by_id(user_id))


def _ensure_non_admin_target(user_id: str) -> dict[str, Any]:
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    roles, _ = user_access(user)
    if "admin" in roles or bool(user.get("is_admin")):
        raise HTTPException(status_code=409, detail="不能封禁或删除管理员账号")
    return user


def set_user_banned(user_id: str, banned: bool) -> dict[str, Any]:
    _ensure_non_admin_target(user_id)
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET is_banned = %s WHERE id = %s", (1 if banned else 0, user_id))
    return public_user(get_user_by_id(user_id))


def delete_user_account(user_id: str) -> dict[str, bool]:
    _ensure_non_admin_target(user_id)
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM book_reads WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    return {"ok": True}


def count_admin_users() -> int:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT u.id) AS count
                FROM users u
                LEFT JOIN user_roles ur ON ur.user_id = u.id AND ur.role_id = 'admin'
                WHERE u.is_admin = 1 OR ur.role_id IS NOT NULL
                """
            )
            return int(cursor.fetchone()["count"])


def create_user(username: str, password: str, is_admin: bool = False) -> dict[str, Any]:
    username, password = validate_credentials_input(username, password)
    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="这个用户名已经被注册")
    user_id = str(uuid.uuid4())
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, username, password_hash, is_admin, created_at, last_login_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, username, hash_password(password), 1 if is_admin else 0, now_iso(), ""),
            )
    set_user_roles(user_id, ["admin" if is_admin else "user"])
    return get_user_by_id(user_id)


def touch_login(user_id: str) -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET last_login_at = %s WHERE id = %s", (now_iso(), user_id))


def ensure_user_active(user: dict[str, Any]) -> None:
    if bool(user.get("is_banned")):
        raise HTTPException(status_code=401, detail="账号已被封禁，请联系管理员")


def _redis() -> redis.Redis:
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        decode_responses=True,
        socket_timeout=3,
    )


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode())


def _jwt_encode(payload: dict[str, Any], ttl_seconds: int) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    body = {
        **payload,
        "iat": now,
        "exp": int((datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join([
        _b64(json.dumps(header, separators=(",", ":")).encode()),
        _b64(json.dumps(body, separators=(",", ":")).encode()),
    ])
    signature = hmac.new(settings.jwt_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


def _jwt_decode(token: str, token_type: str) -> dict[str, Any]:
    try:
        header_raw, payload_raw, signature = token.split(".", 2)
        signing_input = f"{header_raw}.{payload_raw}"
        expected = _b64(hmac.new(settings.jwt_secret.encode(), signing_input.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        payload = json.loads(_unb64(payload_raw))
        if payload.get("typ") != token_type:
            raise ValueError("bad token type")
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
        return payload
    except Exception as error:
        raise HTTPException(status_code=401, detail="请先登录") from error


def issue_playcaptcha_token() -> str:
    return _jwt_encode({"typ": "playcaptcha", "jti": str(uuid.uuid4())}, PLAYCAPTCHA_TOKEN_SECONDS)


def require_playcaptcha_token(token: str) -> None:
    if not token:
        raise HTTPException(status_code=422, detail="请先完成抓娃娃验证")
    try:
        _jwt_decode(token, "playcaptcha")
    except HTTPException as error:
        raise HTTPException(status_code=422, detail="抓娃娃验证已过期，请重新完成验证") from error


def _refresh_key(jti: str) -> str:
    return f"orbit:refresh:{jti}"


def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )


def set_auth_cookies(response: Response, user: dict[str, Any]) -> None:
    access_seconds = settings.jwt_access_minutes * 60
    refresh_seconds = settings.jwt_refresh_days * 24 * 60 * 60
    refresh_jti = str(uuid.uuid4())
    public = public_user(user)
    base_payload = {
        "sub": user["id"],
        "username": user["username"],
        "isAdmin": public["isAdmin"],
        "roles": public["roles"],
        "permissions": public["permissions"],
    }
    access_token = _jwt_encode({**base_payload, "typ": "access"}, access_seconds)
    refresh_token = _jwt_encode({**base_payload, "typ": "refresh", "jti": refresh_jti}, refresh_seconds)
    _redis().setex(_refresh_key(refresh_jti), refresh_seconds, user["id"])
    _set_cookie(response, ACCESS_COOKIE, access_token, access_seconds)
    _set_cookie(response, REFRESH_COOKIE, refresh_token, refresh_seconds)
    response.delete_cookie(OLD_SESSION_COOKIE, path="/")


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
    response.delete_cookie(OLD_SESSION_COOKIE, path="/")


def revoke_refresh_token(token: str) -> None:
    if not token:
        return
    try:
        payload = _jwt_decode(token, "refresh")
        _redis().delete(_refresh_key(str(payload.get("jti", ""))))
    except HTTPException:
        return


def require_user(request: Request) -> dict[str, Any]:
    payload = _jwt_decode(request.cookies.get(ACCESS_COOKIE, ""), "access")
    user = get_user_by_id(str(payload.get("sub", "")))
    if not user:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
    ensure_user_active(user)
    return attach_user_access(user)


def require_permission(request: Request, permission: str) -> dict[str, Any]:
    user = require_user(request)
    if permission not in user["permissions"]:
        raise HTTPException(status_code=403, detail="没有权限执行此操作")
    return user


def refresh_user(request: Request, response: Response) -> dict[str, Any]:
    token = request.cookies.get(REFRESH_COOKIE, "")
    payload = _jwt_decode(token, "refresh")
    jti = str(payload.get("jti", ""))
    user_id = str(payload.get("sub", ""))
    if _redis().get(_refresh_key(jti)) != user_id:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
    _redis().delete(_refresh_key(jti))
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
    ensure_user_active(user)
    set_auth_cookies(response, user)
    return user


def seed_admin_user() -> None:
    if not settings.admin_username or not settings.admin_password:
        return
    existing = get_user_by_username(settings.admin_username)
    if existing:
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET is_admin = 1, is_banned = 0 WHERE id = %s", (existing["id"],))
        set_user_roles(existing["id"], ["admin"])
        return
    create_user(settings.admin_username, settings.admin_password, is_admin=True)


def seed_rbac_defaults() -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            for name, description in PERMISSIONS.items():
                cursor.execute(
                    "INSERT INTO permissions (id, name, description) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE name = VALUES(name), description = VALUES(description)",
                    (name, name, description),
                )
            for name, details in ROLES.items():
                cursor.execute(
                    "INSERT INTO roles (id, name, description) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE name = VALUES(name), description = VALUES(description)",
                    (name, name, details["description"]),
                )
                cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (name,))
                for permission in details["permissions"]:
                    cursor.execute(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
                        (name, permission),
                    )
            cursor.execute(
                "INSERT IGNORE INTO user_roles (user_id, role_id) "
                "SELECT id, 'admin' FROM users WHERE is_admin = 1"
            )
            cursor.execute(
                """
                INSERT IGNORE INTO user_roles (user_id, role_id)
                SELECT u.id, 'user'
                FROM users u
                LEFT JOIN user_roles ur ON ur.user_id = u.id
                WHERE ur.user_id IS NULL
                """
            )
