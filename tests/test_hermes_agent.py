import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from types import SimpleNamespace

from backend.config import settings
import backend.main as main_module
from backend.main import (
    _hermes_chat_title,
    _hermes_status,
    _parse_hermes_chat_session_id,
    _rewrite_hermes_css,
    _rewrite_hermes_html,
    _rewrite_hermes_javascript,
    _run_hermes_chat,
)


def main() -> None:
    original_command = settings.hermes_dashboard_command
    original_url = settings.hermes_dashboard_url
    original_timeout = settings.hermes_dashboard_timeout
    try:
        settings.hermes_dashboard_command = "orbit-hermes-missing-binary dashboard --no-open"
        settings.hermes_dashboard_url = "http://127.0.0.1:9"
        settings.hermes_dashboard_timeout = 0.1
        status = _hermes_status()
        assert status["configured"] is True
        assert status["installed"] is False
        assert status["running"] is False
        assert status["dashboardPublicUrl"] == "/hermes-dashboard/"
        assert "not installed" in status["message"]
        html = _rewrite_hermes_html(b'<head><script src="/assets/app.js"></script><link href="/favicon.ico">')
        assert b'window.__HERMES_BASE_PATH__ = "/hermes-dashboard"' in html
        assert b'src="/hermes-dashboard/assets/app.js?v=orbit-hermes-proxy-20260707"' in html
        assert b'href="/hermes-dashboard/favicon.ico"' in html
        original_html = _rewrite_hermes_html(b'<head><script>window.__HERMES_BASE_PATH__="";</script>')
        assert b'window.__HERMES_BASE_PATH__="/hermes-dashboard"' in original_html
        script = _rewrite_hermes_javascript(b"let base=window.__HERMES_BASE_PATH__??``;")
        assert script == b'let base="/hermes-dashboard";'
        css = _rewrite_hermes_css(b"@font-face{src:url(/assets/font.woff2)}")
        assert css == b"@font-face{src:url(/hermes-dashboard/assets/font.woff2)}"
        assert _parse_hermes_chat_session_id("info\nsession_id: abc-123\n") == "abc-123"
        assert _parse_hermes_chat_session_id("no session") == ""
        assert _hermes_chat_title("  hello   Hermes  ") == "hello Hermes"
        assert _hermes_chat_title("a" * 31) == ("a" * 30) + "…"
        original_chat_command = settings.hermes_chat_command
        original_chat_timeout = settings.hermes_chat_timeout
        original_status = main_module._hermes_status
        original_available = main_module._command_available
        original_run = main_module.subprocess.run
        captured = {}
        try:
            settings.hermes_chat_command = "hermes chat -Q -q"
            settings.hermes_chat_timeout = 1
            main_module._hermes_status = lambda: {"running": True}
            main_module._command_available = lambda parts: True

            def fake_run(command, **kwargs):
                captured["command"] = command
                captured["kwargs"] = kwargs
                return SimpleNamespace(returncode=0, stdout="hello back\n", stderr="session_id: next-session\n")

            main_module.subprocess.run = fake_run
            reply = _run_hermes_chat("hi", "old-session")
            assert reply == {"content": "hello back", "hermesSessionId": "next-session"}
            assert captured["command"] == ["hermes", "chat", "-Q", "-q", "--resume", "old-session", "hi"]
            assert captured["kwargs"]["stdin"] == main_module.subprocess.DEVNULL
            assert captured["kwargs"]["timeout"] == 1
        finally:
            settings.hermes_chat_command = original_chat_command
            settings.hermes_chat_timeout = original_chat_timeout
            main_module._hermes_status = original_status
            main_module._command_available = original_available
            main_module.subprocess.run = original_run
    finally:
        settings.hermes_dashboard_command = original_command
        settings.hermes_dashboard_url = original_url
        settings.hermes_dashboard_timeout = original_timeout


if __name__ == "__main__":
    main()
