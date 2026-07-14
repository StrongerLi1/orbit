import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.main as main_module
from backend.config import settings


def main() -> None:
    original_require = main_module.require_user
    original_url = settings.lx_music_public_url
    calls = []
    try:
        main_module.require_user = lambda request: calls.append(request) or {"id": "u1"}

        settings.lx_music_public_url = ""
        assert main_module.integrations("request") == {
            "lxMusic": {"enabled": False, "publicUrl": ""},
        }

        settings.lx_music_public_url = "https://shawnstronger.cloud:9528/music"
        assert main_module.integrations("request") == {
            "lxMusic": {
                "enabled": True,
                "publicUrl": "https://shawnstronger.cloud:9528/music",
            },
        }
        assert calls == ["request", "request"]
    finally:
        main_module.require_user = original_require
        settings.lx_music_public_url = original_url

    root = Path(__file__).resolve().parent.parent
    app_source = (root / "public" / "app.js").read_text(encoding="utf-8")
    html = (root / "public" / "index.html").read_text(encoding="utf-8")
    nginx = (root / "deploy" / "nginx" / "orbit.conf").read_text(encoding="utf-8")
    dockerfile = (root / "deploy" / "lxserver" / "Dockerfile").read_text(encoding="utf-8")
    assert "get('next') === 'music'" in app_source
    assert "location.replace(publicUrl)" in app_source
    assert "authReturnTarget === 'music' ? '/?next=music' : '/'" in app_source
    assert 'id="lx-music-nav"' in html
    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert "auth_request /_orbit_lx_auth;" in nginx
    assert "return 302 https://shawnstronger.cloud/?next=music;" in nginx
    assert "return 308 https://shawnstronger.cloud$request_uri;" in nginx
    assert 'add_header Strict-Transport-Security "max-age=31536000" always;' in nginx
    assert "listen 9528 ssl;" in nginx
    for header in ("Cookie", "Authorization", "X-User-Token", "X-Orbit-User"):
        assert f'proxy_set_header {header} "";' in nginx
    assert "proxy_set_header X-Frontend-Auth $http_x_frontend_auth;" in nginx
    assert "location ^~ /_orbit_lx_admin" not in nginx
    assert "0d653bf31b19635dd20299c5b341630b426c79f3" in dockerfile
    assert "ws@8.21.0" in dockerfile


if __name__ == "__main__":
    main()
