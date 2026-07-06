import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings
from backend.main import _hermes_status, _rewrite_hermes_css, _rewrite_hermes_html, _rewrite_hermes_javascript


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
    finally:
        settings.hermes_dashboard_command = original_command
        settings.hermes_dashboard_url = original_url
        settings.hermes_dashboard_timeout = original_timeout


if __name__ == "__main__":
    main()
