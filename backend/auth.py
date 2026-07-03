import base64
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, Response

from .config import settings
from .database import connection, now_iso


COOKIE_NAME = "orbit_session"
SESSION_DAYS = 14
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


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode())


def sign_session(user: dict[str, Any]) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    payload = {
        "id": user["id"],
        "username": user["username"],
        "isAdmin": bool(user["is_admin"]),
        "exp": int(expires_at.timestamp()),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(signature)}"


def read_session(token: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
        expected = _b64(hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_unb64(body))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            return None
        return payload
    except Exception:
        return None


def set_session_cookie(response: Response, user: dict[str, Any]) -> None:
    response.set_cookie(
        COOKIE_NAME,
        sign_session(user),
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def require_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME, "")
    session = read_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="请先登录")
    user = get_user_by_id(str(session.get("id", "")))
    if not user:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
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
