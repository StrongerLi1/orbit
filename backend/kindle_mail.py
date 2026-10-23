import re
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import redis
from fastapi import HTTPException

from .config import settings


KINDLE_FORMATS = {
    "epub": ("application", "epub+zip"),
    "pdf": ("application", "pdf"),
    "txt": ("text", "plain"),
}
KINDLE_EMAIL_RE = re.compile(r"^[^@\s]+@kindle\.com$", re.IGNORECASE)
KINDLE_USER_LIMIT = 5
KINDLE_GLOBAL_LIMIT = 30
KINDLE_RATE_WINDOW_SECONDS = 60 * 60


class KindleDeliveryError(Exception):
    CATEGORIES = {"timeout", "smtp", "network", "invalid"}

    def __init__(self, category: str):
        self.category = category if category in self.CATEGORIES else "unknown"
        super().__init__(self.category)


def _delivery_error_category(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, smtplib.SMTPException):
        return "smtp"
    if isinstance(error, OSError):
        return "network"
    return "invalid"


def validate_kindle_email(value: Any) -> str:
    email = str(value or "").strip()
    if len(email) > 320 or not KINDLE_EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=422, detail="请输入有效的 @kindle.com 邮箱")
    local, domain = email.rsplit("@", 1)
    return f"{local}@{domain.lower()}"


def smtp_is_configured() -> bool:
    credentials_valid = bool(settings.kindle_smtp_username) == bool(settings.kindle_smtp_password)
    return bool(
        settings.kindle_smtp_host
        and settings.kindle_smtp_from
        and credentials_valid
        and settings.kindle_smtp_security in {"starttls", "ssl", "none"}
    )


def kindle_settings_payload(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "kindleEmail": str(user.get("kindle_email") or ""),
        "senderEmail": settings.kindle_smtp_from,
        "enabled": smtp_is_configured(),
        "maxAttachmentMb": settings.kindle_max_attachment_mb,
    }


def can_send_book(book: dict[str, Any]) -> bool:
    return (
        str(book.get("fileFormat") or book.get("file_format") or "").lower() in KINDLE_FORMATS
        and int(book.get("fileSize") or book.get("file_size") or 0) <= settings.kindle_max_attachment_mb * 1024 * 1024
    )


def enforce_send_limit(user_id: str, redis_client, is_admin: bool = False) -> None:
    if is_admin:
        return
    script = """
    local user_count = tonumber(redis.call('GET', KEYS[1]) or '0')
    local global_count = tonumber(redis.call('GET', KEYS[2]) or '0')
    if user_count >= tonumber(ARGV[1]) then return 1 end
    if global_count >= tonumber(ARGV[2]) then return 2 end
    local next_user = redis.call('INCR', KEYS[1])
    if next_user == 1 then redis.call('EXPIRE', KEYS[1], ARGV[3]) end
    local next_global = redis.call('INCR', KEYS[2])
    if next_global == 1 then redis.call('EXPIRE', KEYS[2], ARGV[3]) end
    return 0
    """
    try:
        result = int(redis_client.eval(
            script,
            2,
            f"orbit:kindle-send:user:{user_id}",
            "orbit:kindle-send:global",
            KINDLE_USER_LIMIT,
            KINDLE_GLOBAL_LIMIT,
            KINDLE_RATE_WINDOW_SECONDS,
        ))
    except redis.RedisError as error:
        raise HTTPException(status_code=503, detail="发送频率服务暂时不可用，请稍后再试") from error
    if result in {1, 2}:
        raise HTTPException(status_code=429, detail="发送次数过多，请一小时后再试")


def kindle_redis_client():
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        decode_responses=True,
        socket_timeout=3,
    )


def send_book(to_email: str, path: Path, filename: str, title: str, file_format: str) -> None:
    if not smtp_is_configured():
        raise HTTPException(status_code=503, detail="Kindle 邮件发送服务尚未配置")
    maintype, subtype = KINDLE_FORMATS[file_format.lower()]
    try:
        message = EmailMessage()
        message["From"] = settings.kindle_smtp_from
        message["To"] = to_email
        message["Subject"] = " ".join(str(title).splitlines())[:300]
        message.set_content("此邮件由 Orbit 共享图书馆发送。")
        message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=filename)
        smtp_class = smtplib.SMTP_SSL if settings.kindle_smtp_security == "ssl" else smtplib.SMTP
        with smtp_class(
            settings.kindle_smtp_host,
            settings.kindle_smtp_port,
            timeout=settings.kindle_smtp_timeout_seconds,
        ) as client:
            if settings.kindle_smtp_security == "starttls":
                client.starttls()
            if settings.kindle_smtp_username:
                client.login(settings.kindle_smtp_username, settings.kindle_smtp_password)
            client.send_message(message)
    except (OSError, ValueError, smtplib.SMTPException) as error:
        raise KindleDeliveryError(_delivery_error_category(error)) from error
