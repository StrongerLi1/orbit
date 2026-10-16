import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException

import backend.kindle_mail as kindle_mail
import backend.main as main_module
from backend.config import settings


class FakeRequest:
    def __init__(self, payload=None):
        self.payload = payload or {}

    async def json(self):
        return self.payload


def assert_http(status: int, action) -> None:
    try:
        action()
        raise AssertionError(f"expected HTTP {status}")
    except HTTPException as error:
        assert error.status_code == status


def test_email_and_catalog_rules() -> None:
    assert kindle_mail.validate_kindle_email(" Reader@Kindle.com ") == "Reader@kindle.com"
    for invalid in ("", "reader@example.com", "reader @kindle.com", "@kindle.com"):
        assert_http(422, lambda value=invalid: kindle_mail.validate_kindle_email(value))

    original_limit = settings.kindle_max_attachment_mb
    settings.kindle_max_attachment_mb = 25
    try:
        assert kindle_mail.can_send_book({"fileFormat": "epub", "fileSize": 1024})
        assert kindle_mail.can_send_book({"file_format": "pdf", "file_size": 25 * 1024 * 1024})
        assert not kindle_mail.can_send_book({"fileFormat": "mobi", "fileSize": 1024})
        assert not kindle_mail.can_send_book({"fileFormat": "txt", "fileSize": 25 * 1024 * 1024 + 1})
    finally:
        settings.kindle_max_attachment_mb = original_limit


def test_rate_limit_and_admin_bypass() -> None:
    class Redis:
        def __init__(self, result):
            self.result = result
            self.calls = []

        def eval(self, *args):
            self.calls.append(args)
            return self.result

    allowed = Redis(0)
    kindle_mail.enforce_send_limit("u1", allowed)
    assert len(allowed.calls) == 1
    assert "orbit:kindle-send:user:u1" in allowed.calls[0]
    script = allowed.calls[0][0]
    assert script.index("user_count >=") < script.index("redis.call('INCR', KEYS[1])")
    assert script.index("global_count >=") < script.index("redis.call('INCR', KEYS[2])")
    assert_http(429, lambda: kindle_mail.enforce_send_limit("u1", Redis(1)))
    user_window = iter([0, 0, 0, 0, 0, 1])
    for _ in range(5):
        kindle_mail.enforce_send_limit("u1", Redis(next(user_window)))
    assert_http(429, lambda: kindle_mail.enforce_send_limit("u1", Redis(next(user_window))))
    global_window = iter([0] * 30 + [2])
    for index in range(30):
        kindle_mail.enforce_send_limit(f"u{index}", Redis(next(global_window)))
    assert_http(429, lambda: kindle_mail.enforce_send_limit("u31", Redis(next(global_window))))
    admin = Redis(1)
    kindle_mail.enforce_send_limit("admin", admin, is_admin=True)
    assert admin.calls == []

    class BrokenRedis:
        def eval(self, *_args):
            raise kindle_mail.redis.ConnectionError("redis offline")

    assert_http(503, lambda: kindle_mail.enforce_send_limit("u1", BrokenRedis()))


def test_smtp_message() -> None:
    original = {
        "host": settings.kindle_smtp_host,
        "port": settings.kindle_smtp_port,
        "username": settings.kindle_smtp_username,
        "password": settings.kindle_smtp_password,
        "sender": settings.kindle_smtp_from,
        "security": settings.kindle_smtp_security,
        "timeout": settings.kindle_smtp_timeout_seconds,
        "smtp": kindle_mail.smtplib.SMTP,
    }
    captured = {}

    class SMTP:
        def __init__(self, host, port, timeout):
            captured.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self):
            captured["tls"] = True

        def login(self, username, password):
            captured["login"] = (username, password)

        def send_message(self, message):
            captured["message"] = message

    try:
        settings.kindle_smtp_host = "smtp.example.com"
        settings.kindle_smtp_port = 587
        settings.kindle_smtp_username = "orbit"
        settings.kindle_smtp_password = "secret"
        settings.kindle_smtp_from = "books@example.com"
        settings.kindle_smtp_security = "starttls"
        settings.kindle_smtp_timeout_seconds = 9
        kindle_mail.smtplib.SMTP = SMTP
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "book.epub"
            path.write_bytes(b"epub-content")
            kindle_mail.send_book("reader@kindle.com", path, "book.epub", "书名\n不可注入", "epub")
        message = captured["message"]
        assert captured["tls"] is True
        assert captured["login"] == ("orbit", "secret")
        assert message["To"] == "reader@kindle.com"
        assert message["Subject"] == "书名 不可注入"
        assert message.iter_attachments().__next__().get_filename() == "book.epub"
        class TimeoutSMTP(SMTP):
            def send_message(self, _message):
                raise TimeoutError("timed out")

        kindle_mail.smtplib.SMTP = TimeoutSMTP
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "book.pdf"
            path.write_bytes(b"%PDF")
            try:
                kindle_mail.send_book("reader@kindle.com", path, "book.pdf", "书名", "pdf")
                raise AssertionError("timeout must fail")
            except kindle_mail.KindleDeliveryError:
                pass
    finally:
        settings.kindle_smtp_host = original["host"]
        settings.kindle_smtp_port = original["port"]
        settings.kindle_smtp_username = original["username"]
        settings.kindle_smtp_password = original["password"]
        settings.kindle_smtp_from = original["sender"]
        settings.kindle_smtp_security = original["security"]
        settings.kindle_smtp_timeout_seconds = original["timeout"]
        kindle_mail.smtplib.SMTP = original["smtp"]


def test_send_route() -> None:
    original = {
        "require": main_module.require_permission,
        "book": main_module.get_book_storage,
        "configured": main_module.smtp_is_configured,
        "redis": main_module.kindle_redis_client,
        "limit": main_module.enforce_send_limit,
        "send": main_module.send_book,
        "storage": settings.library_storage_dir,
    }
    calls = []
    try:
        with tempfile.TemporaryDirectory() as directory:
            settings.library_storage_dir = Path(directory)
            (settings.library_storage_dir / "books").mkdir(parents=True)
            (settings.library_storage_dir / "books" / "b1.epub").write_bytes(b"book")
            main_module.require_permission = lambda _request, permission: {
                "id": "admin",
                "kindle_email": "reader@kindle.com",
                "roles": ["admin"],
                "permissions": [permission],
            }
            main_module.get_book_storage = lambda _book_id: {
                "id": "b1",
                "title": "书名",
                "file_format": "epub",
                "file_size": 4,
                "stored_filename": "b1.epub",
                "original_filename": "book.epub",
            }
            main_module.smtp_is_configured = lambda: True
            main_module.kindle_redis_client = lambda: object()
            main_module.enforce_send_limit = lambda user_id, _redis, is_admin: calls.append((user_id, is_admin))
            main_module.send_book = lambda *args: calls.append(args)
            assert main_module.library_send_to_kindle("b1", FakeRequest()) == {"status": "sent"}
            assert calls[0] == ("admin", True)
            assert calls[1][0] == "reader@kindle.com"

            main_module.smtp_is_configured = lambda: False
            before = len(calls)
            assert_http(503, lambda: main_module.library_send_to_kindle("b1", FakeRequest()))
            assert len(calls) == before
            main_module.smtp_is_configured = lambda: True

            def fail_send(*_args):
                raise kindle_mail.KindleDeliveryError("private smtp detail")

            main_module.send_book = fail_send
            assert_http(502, lambda: main_module.library_send_to_kindle("b1", FakeRequest()))
            assert calls[-1] == ("admin", True)

            main_module.get_book_storage = lambda _book_id: {"file_format": "azw3", "file_size": 4}
            before = len(calls)
            assert_http(415, lambda: main_module.library_send_to_kindle("b1", FakeRequest()))
            assert len(calls) == before
            main_module.get_book_storage = lambda _book_id: {
                "file_format": "pdf",
                "file_size": settings.kindle_max_attachment_mb * 1024 * 1024 + 1,
            }
            assert_http(413, lambda: main_module.library_send_to_kindle("b1", FakeRequest()))
            main_module.get_book_storage = lambda _book_id: {
                "file_format": "pdf",
                "file_size": 4,
                "stored_filename": "missing.pdf",
            }
            assert_http(404, lambda: main_module.library_send_to_kindle("b1", FakeRequest()))
            main_module.require_permission = lambda _request, _permission: {"id": "u1", "kindle_email": "", "roles": ["user"]}
            assert_http(409, lambda: main_module.library_send_to_kindle("b1", FakeRequest()))
    finally:
        main_module.require_permission = original["require"]
        main_module.get_book_storage = original["book"]
        main_module.smtp_is_configured = original["configured"]
        main_module.kindle_redis_client = original["redis"]
        main_module.enforce_send_limit = original["limit"]
        main_module.send_book = original["send"]
        settings.library_storage_dir = original["storage"]


def test_private_account_settings() -> None:
    original_require = main_module.require_user
    original_set = main_module.set_user_kindle_email
    updates = []
    user = {
        "id": "u1",
        "username": "reader",
        "kindle_email": "",
        "is_admin": 0,
        "is_banned": 0,
        "roles": ["user"],
        "permissions": ["library:read"],
        "created_at": "now",
        "last_login_at": "",
    }
    try:
        main_module.require_user = lambda _request: user
        main_module.set_user_kindle_email = lambda user_id, email: updates.append((user_id, email))
        saved = asyncio.run(main_module.account_kindle_update(FakeRequest({"email": "Reader@Kindle.com"})))
        assert saved["kindleEmail"] == "Reader@kindle.com"
        assert updates[-1] == ("u1", "Reader@kindle.com")
        cleared = main_module.account_kindle_delete(FakeRequest())
        assert cleared["kindleEmail"] == ""
        assert updates[-1] == ("u1", "")
        assert "kindleEmail" not in main_module.public_user({**user, "kindle_email": "secret@kindle.com"})
    finally:
        main_module.require_user = original_require
        main_module.set_user_kindle_email = original_set


def main() -> None:
    test_email_and_catalog_rules()
    test_rate_limit_and_admin_bypass()
    test_smtp_message()
    test_send_route()
    test_private_account_settings()


if __name__ == "__main__":
    main()
