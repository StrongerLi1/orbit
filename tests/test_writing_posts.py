import asyncio
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.main as main_module
import backend.repository as repository
from fastapi import HTTPException


class FakeCursor:
    def __init__(self, row=None, rows=None, rowcount=1):
        self.row = row
        self.rows = rows or []
        self.rowcount = rowcount
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def fake_connection(cursor):
    @contextmanager
    def connect():
        yield FakeConnection(cursor)

    return connect


class FakeRequest:
    def __init__(self, data=None):
        self.data = data or {}

    async def json(self):
        return self.data


def main() -> None:
    paths = [route.path for route in main_module.app.routes]
    assert paths.index("/api/writings") < paths.index("/api/{collection}")
    assert paths.index("/api/writings/{post_id}") < paths.index("/api/{collection}/{item_id}")

    row = {
        "id": "w1", "owner_user_id": "u1", "owner_name": "alice", "visibility": "public",
        "is_anonymous": 1, "content": "只是一段话", "created_at": "2026-07-19T00:00:00Z",
        "updated_at": "2026-07-19T00:00:00Z",
    }
    owner_view = repository._writing_post_row(row, "u1")
    assert owner_view["createdByName"] == "alice"
    assert owner_view["isOwn"] and owner_view["canManage"]
    other_view = repository._writing_post_row(row, "u2")
    assert other_view["createdByName"] == "匿名用户"
    assert not other_view["isOwn"] and not other_view["canManage"]

    original_connection = repository.connection
    try:
        cursor = FakeCursor(rows=[row])
        repository.connection = fake_connection(cursor)
        assert repository.list_writing_posts("u2")[0]["id"] == "w1"
        assert "visibility = 'public' OR owner_user_id = %s" in cursor.calls[0][0]
        assert cursor.calls[0][1] == ("u2",)

        cursor = FakeCursor(rowcount=0)
        repository.connection = fake_connection(cursor)
        assert repository.update_writing_post("w1", {"content": "新内容", "visibility": "private", "anonymous": False}, "u2") is None
        assert "WHERE id = %s AND owner_user_id = %s" in cursor.calls[0][0]
        assert cursor.calls[0][1][-2:] == ("w1", "u2")

        cursor = FakeCursor(rowcount=0)
        repository.connection = fake_connection(cursor)
        assert not repository.delete_writing_post("w1", "u2")
        assert cursor.calls[0][1] == ("w1", "u2")
    finally:
        repository.connection = original_connection

    valid = main_module.validate("writings", {"content": "  今天很好  ", "visibility": "private", "anonymous": True, "owner_user_id": "forged"})
    assert valid == {"content": "今天很好", "visibility": "private", "anonymous": True}
    for invalid in ({"content": "", "visibility": "private", "anonymous": False}, {"content": "x", "visibility": "friends", "anonymous": False}, {"content": "x", "visibility": "public", "anonymous": "true"}):
        try:
            main_module.validate("writings", invalid)
            raise AssertionError("invalid writing payload must fail")
        except HTTPException as error:
            assert error.status_code == 422

    original_permission = main_module.require_permission
    original_list = main_module.list_writing_posts
    original_get = main_module.get_writing_post_for_owner
    try:
        admin = {"id": "admin", "permissions": ["content:read", "content:write", "users:manage"]}
        checked = []
        main_module.require_permission = lambda _request, _permission: admin
        main_module.list_writing_posts = lambda user_id: checked.append(user_id) or []
        assert main_module.writing_list(FakeRequest()) == []
        assert checked == ["admin"]

        main_module.get_writing_post_for_owner = lambda post_id, user_id: checked.append((post_id, user_id)) or None
        try:
            asyncio.run(main_module.writing_update("private-post", FakeRequest({"content": "偷看", "visibility": "public", "anonymous": False})))
            raise AssertionError("admin must not update another user's writing")
        except HTTPException as error:
            assert error.status_code == 404
        assert checked[-1] == ("private-post", "admin")
    finally:
        main_module.require_permission = original_permission
        main_module.list_writing_posts = original_list
        main_module.get_writing_post_for_owner = original_get


if __name__ == "__main__":
    main()
