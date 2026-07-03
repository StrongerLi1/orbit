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


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "isAdmin": bool(row["is_admin"]),
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
    return get_user_by_id(user_id)


def touch_login(user_id: str) -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET last_login_at = %s WHERE id = %s", (now_iso(), user_id))


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


def _refresh_key(jti: str) -> str:
    return f"orbit:refresh:{jti}"


def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def set_auth_cookies(response: Response, user: dict[str, Any]) -> None:
    access_seconds = settings.jwt_access_minutes * 60
    refresh_seconds = settings.jwt_refresh_days * 24 * 60 * 60
    refresh_jti = str(uuid.uuid4())
    base_payload = {
        "sub": user["id"],
        "username": user["username"],
        "isAdmin": bool(user["is_admin"]),
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
    set_auth_cookies(response, user)
    return user


def seed_admin_user() -> None:
    if not settings.admin_username or not settings.admin_password:
        return
    existing = get_user_by_username(settings.admin_username)
    if existing:
        with connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET is_admin = 1 WHERE id = %s", (existing["id"],))
        return
    create_user(settings.admin_username, settings.admin_password, is_admin=True)
