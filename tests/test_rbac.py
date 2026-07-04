import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.auth import PERMISSIONS, ROLES, public_user


def main() -> None:
    assert list(ROLES) == ["admin", "user"]
    assert set(ROLES["admin"]["permissions"]) == set(PERMISSIONS)
    assert ROLES["user"]["permissions"] == ("content:read", "content:write", "netdisk:search")

    user = public_user({
        "id": "u1",
        "username": "alice",
        "is_admin": 0,
        "roles": ["user"],
        "permissions": list(ROLES["user"]["permissions"]),
        "created_at": "2026-07-04T00:00:00Z",
        "last_login_at": "",
    })
    assert user["isAdmin"] is False
    assert user["roles"] == ["user"]
    assert "users:manage" not in user["permissions"]

    admin = public_user({
        "id": "u2",
        "username": "admin",
        "is_admin": 0,
        "roles": ["admin"],
        "permissions": list(ROLES["admin"]["permissions"]),
        "created_at": "2026-07-04T00:00:00Z",
        "last_login_at": "",
    })
    assert admin["isAdmin"] is True
    assert "users:manage" in admin["permissions"]


if __name__ == "__main__":
    main()
