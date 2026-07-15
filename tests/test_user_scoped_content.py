import asyncio
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.database as database
import backend.repository as repository
import backend.auth as auth
import backend.main as main_module
from fastapi import HTTPException


validate = main_module.validate


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []
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


class FakeRequest:
    async def json(self):
        return {}


def fake_connection(cursor):
    @contextmanager
    def connect():
        yield FakeConnection(cursor)

    return connect


def main() -> None:
    assert repository.USER_SCOPED_COLLECTIONS == {"todos", "plans"}
    for collection in repository.USER_SCOPED_COLLECTIONS:
        try:
            repository._required_owner_id(collection, "")
            raise AssertionError("missing owner must fail closed")
        except ValueError:
            pass

    original_connection = repository.connection
    original_get_item = repository.get_item
    original_database_connection = database.connection
    original_auth_connection = auth.connection
    original_ensure_non_admin_target = auth._ensure_non_admin_target
    try:
        todo_row = {
            "id": "todo-1", "title": "私有待办", "priority": "high", "due_date": "",
            "completed": 0, "created_at": "2026-07-15T00:00:00Z",
        }
        cursor = FakeCursor(rows=[todo_row])
        repository.connection = fake_connection(cursor)
        assert repository.list_items("todos", "user-a")[0]["id"] == "todo-1"
        assert "WHERE owner_user_id = %s" in cursor.calls[0][0]
        assert cursor.calls[0][1] == ("user-a",)

        cursor = FakeCursor()
        repository.connection = fake_connection(cursor)
        repository.get_item = lambda collection, item_id, *_args: {"id": item_id}
        repository.create_item(
            "todos",
            {"title": "新待办", "priority": "medium", "dueDate": "", "completed": False},
            {"id": "user-a", "permissions": []},
        )
        assert "owner_user_id" in cursor.calls[0][0]
        assert cursor.calls[0][1][1] == "user-a"

        cursor = FakeCursor()
        repository.connection = fake_connection(cursor)
        repository.update_item(
            "todos", "todo-1",
            {"title": "已更新", "priority": "high", "dueDate": "", "completed": True},
            {"id": "user-a", "permissions": []},
        )
        assert "WHERE id = %s AND owner_user_id = %s" in cursor.calls[0][0]
        assert cursor.calls[0][1][-2:] == ("todo-1", "user-a")

        cursor = FakeCursor()
        repository.connection = fake_connection(cursor)
        repository.delete_item("plans", "plan-1", {"id": "user-a", "permissions": ["users:manage"]})
        assert "WHERE id = %s AND owner_user_id = %s" in cursor.calls[0][0]
        assert cursor.calls[0][1] == ("plan-1", "user-a")

        cursor = FakeCursor(row={"id": "admin-id", "username": "admin"})
        database.connection = fake_connection(cursor)
        database.backfill_legacy_owners()
        updates = [call for call in cursor.calls if call[0].startswith("UPDATE")]
        assert [f"`{table}`" in updates[index][0] for index, table in enumerate(("todos", "plans", "excerpts"))] == [True, True, True]
        assert all(params == ("admin-id",) for _, params in updates)

        cursor = FakeCursor()
        auth.connection = fake_connection(cursor)
        auth._ensure_non_admin_target = lambda _user_id: {"id": "user-a"}
        auth.delete_user_account("user-a")
        deleted_tables = [call[0].split()[2] for call in cursor.calls]
        assert "todos" in deleted_tables
        assert "plans" in deleted_tables
        assert deleted_tables[-1] == "users"
        assert all(params == ("user-a",) for _, params in cursor.calls)
    finally:
        repository.connection = original_connection
        repository.get_item = original_get_item
        database.connection = original_database_connection
        auth.connection = original_auth_connection
        auth._ensure_non_admin_target = original_ensure_non_admin_target

    todo = validate("todos", {"title": "待办", "owner_user_id": "forged"})
    plan = validate("plans", {
        "title": "计划", "startDate": "2026-07-15", "time": "09:00",
        "owner_user_id": "forged",
    })
    assert "owner_user_id" not in todo
    assert "owner_user_id" not in plan

    original_require_permission = main_module.require_permission
    original_main_get_item = main_module.get_item
    try:
        checked = []
        main_module.require_permission = lambda _request, _permission: {"id": "user-a", "permissions": []}
        main_module.get_item = lambda collection, item_id, user_id, is_admin: checked.append(
            (collection, item_id, user_id, is_admin)
        )
        try:
            asyncio.run(main_module.api_update("todos", "other-user-id", FakeRequest()))
            raise AssertionError("cross-user record must look missing")
        except HTTPException as error:
            assert error.status_code == 404
        assert checked == [("todos", "other-user-id", "user-a", False)]
    finally:
        main_module.require_permission = original_require_permission
        main_module.get_item = original_main_get_item


if __name__ == "__main__":
    main()
