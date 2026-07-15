import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import can_manage_excerpt, validate
from backend.repository import _excerpt_row


def main() -> None:
    owner = {"id": "u1", "permissions": ["content:read", "content:write"]}
    other = {"id": "u2", "permissions": ["content:read", "content:write"]}
    admin = {"id": "admin-id", "permissions": ["content:read", "content:write", "users:manage"]}

    assert can_manage_excerpt(owner, "u1")
    assert not can_manage_excerpt(other, "u1")
    assert can_manage_excerpt(admin, "u1")
    assert can_manage_excerpt(admin, None)

    row = {
        "id": "e1",
        "owner_user_id": "u1",
        "owner_name": "alice",
        "content": "一句话",
        "source": "书",
        "author": "作者",
        "excerpt_date": "2026-07-15",
        "note": "",
        "created_at": "2026-07-15T00:00:00Z",
    }
    assert _excerpt_row(row, "u1", False)["canManage"] is True
    assert _excerpt_row(row, "u2", False)["canManage"] is False
    assert _excerpt_row(row, "u2", True)["canManage"] is True
    assert _excerpt_row(row, "u2", False)["createdByName"] == "alice"

    clean = validate("excerpts", {
        "content": "一句话",
        "createdByName": "mallory",
        "owner_user_id": "mallory-id",
    })
    assert "createdByName" not in clean
    assert "owner_user_id" not in clean


if __name__ == "__main__":
    main()
