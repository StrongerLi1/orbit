import asyncio
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException
from pymysql.err import IntegrityError

from backend import main, repository


class Cursor:
    def __init__(self, row=None, rows=()):
        self.row = row
        self.rows = rows
        self.calls = []
        self.rowcount = 1

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


@contextmanager
def connect(cursor):
    class Connection:
        def cursor(self):
            return cursor

    yield Connection()


class Request:
    def __init__(self, body):
        self.body = body

    async def json(self):
        return self.body


def rejects(status, action):
    try:
        action()
    except HTTPException as error:
        assert error.status_code == status
    else:
        raise AssertionError(f"expected HTTP {status}")


def run():
    assert main._todo_label_name({"name": " 工作 "}) == "工作"
    for name in (" ", "x" * 31, 3):
        rejects(422, lambda: main._todo_label_name({"name": name}))

    legacy = {"title": "旧待办", "priority": "medium", "dueDate": "", "completed": False}
    assert main.validate("todos", legacy)["labelId"] is None
    assert main.validate("todos", {**legacy, "labelId": "own-label"})["labelId"] == "own-label"
    rejects(422, lambda: main.validate("todos", {**legacy, "labelId": " "}))

    row = {"id": "own-label", "name": "工作", "created_at": "now"}
    cursor = Cursor(rows=[row])
    with patch.object(repository, "connection", lambda: connect(cursor)):
        assert repository.list_todo_labels("user-a") == [{"id": "own-label", "name": "工作", "createdAt": "now"}]
    assert "WHERE owner_user_id = %s" in cursor.calls[0][0]
    assert cursor.calls[0][1] == ("user-a",)

    cursor = Cursor(row=None)
    with patch.object(repository, "connection", lambda: connect(cursor)):
        assert repository.get_todo_label("other-label", "user-a") is None
    assert cursor.calls[0][1] == ("other-label", "user-a")

    cursor = Cursor()
    with patch.object(repository, "connection", lambda: connect(cursor)):
        assert repository.delete_todo_label("own-label", "user-a")
    assert cursor.calls[0][1] == ("own-label", "user-a")

    cursor = Cursor()
    with patch.object(repository, "connection", lambda: connect(cursor)), patch.object(repository, "get_item", return_value={"id": "todo-1"}):
        repository.create_item("todos", {**legacy, "labelId": "own-label"}, {"id": "user-a", "permissions": []})
    assert "label_id" in cursor.calls[0][0]
    assert cursor.calls[0][1][1:3] == ("user-a", "own-label")

    cursor = Cursor()
    with patch.object(repository, "connection", lambda: connect(cursor)), patch.object(repository, "get_item", return_value={"id": "todo-1"}):
        repository.update_item("todos", "todo-1", {**legacy, "labelId": None}, {"id": "user-a", "permissions": []})
    assert "label_id = %s" in cursor.calls[0][0]
    assert cursor.calls[0][1][-3:] == (None, "todo-1", "user-a")

    user = {"id": "user-a"}
    with patch.object(main, "require_permission", return_value=user), patch.object(main, "get_todo_label", return_value=None):
        rejects(422, lambda: asyncio.run(main.api_create("todos", Request({**legacy, "labelId": "other-label"}))))

    with patch.object(main, "require_permission", return_value=user), patch.object(main, "get_item", return_value={"id": "todo-1", **legacy, "labelId": "own-label"}), patch.object(main, "get_todo_label", return_value=None):
        rejects(422, lambda: asyncio.run(main.api_update("todos", "todo-1", Request({"labelId": "other-label"}))))

    with patch.object(main, "require_permission", return_value=user), patch.object(main, "get_item", return_value={"id": "todo-1", **legacy, "labelId": "own-label"}), patch.object(main, "update_item", return_value={"id": "todo-1", "labelId": None}) as update:
        assert asyncio.run(main.api_update("todos", "todo-1", Request({"labelId": None})))["labelId"] is None
        assert update.call_args.args[2]["labelId"] is None

    with patch.object(main, "require_permission", return_value=user), patch.object(main, "get_item", return_value={"id": "todo-1", **legacy, "labelId": "own-label"}), patch.object(main, "get_todo_label", return_value={"id": "own-label"}), patch.object(main, "update_item", return_value={"id": "todo-1", "labelId": "own-label"}) as update:
        asyncio.run(main.api_update("todos", "todo-1", Request({"completed": True})))
        assert update.call_args.args[2]["labelId"] == "own-label"

    with patch.object(main, "require_permission", return_value=user), patch.object(main, "get_todo_label", return_value={"id": "own-label"}), patch.object(main, "create_item", side_effect=IntegrityError(1452, "label deleted")):
        rejects(422, lambda: asyncio.run(main.api_create("todos", Request({**legacy, "labelId": "own-label"}))))

    with patch.object(main, "require_permission", return_value=user), patch.object(main, "create_todo_label", side_effect=IntegrityError(1062, "duplicate")):
        rejects(409, lambda: asyncio.run(main.todo_label_create(Request({"name": "工作"}))))

    with patch.object(main, "require_permission", return_value=user), patch.object(main, "get_todo_label", return_value=None), patch.object(main, "delete_todo_label", return_value=False):
        rejects(404, lambda: asyncio.run(main.todo_label_update("other-label", Request({"name": "新名称"}))))
        rejects(404, lambda: main.todo_label_delete("other-label", Request({})))


if __name__ == "__main__":
    run()
