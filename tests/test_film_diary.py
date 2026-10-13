import asyncio
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.auth as auth
import backend.main as main_module
import backend.repository as repository
from fastapi import HTTPException


class FakeCursor:
    def __init__(self, row=None, rows=None, fetchall_results=None, rowcount=1):
        self.row = row
        self.rows = rows or []
        self.fetchall_results = list(fetchall_results or [])
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
        return self.fetchall_results.pop(0) if self.fetchall_results else self.rows


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def fake_connections(*cursors):
    pending = list(cursors)

    @contextmanager
    def connect():
        yield FakeConnection(pending.pop(0))

    return connect


class FakeRequest:
    def __init__(self, data=None):
        self.data = {} if data is None else data

    async def json(self):
        return self.data


def expect_422(action) -> None:
    try:
        action()
        raise AssertionError("invalid film diary payload must fail")
    except HTTPException as error:
        assert error.status_code == 422


def main() -> None:
    paths = [route.path for route in main_module.app.routes]
    assert paths.index("/api/film-rolls") < paths.index("/api/{collection}")
    assert paths.index("/api/film-rolls/{roll_id}") < paths.index("/api/{collection}/{item_id}")
    assert paths.index("/api/film-rolls/{roll_id}/exposures/{exposure_id}") < paths.index("/api/{collection}/{item_id}")

    roll = main_module.validate_film_roll({
        "filmStock": " Kodak Gold 200 ", "iso": 200, "camera": " Nikon FM2 ",
        "status": "active", "owner_user_id": "forged",
    })
    assert roll == {"filmStock": "Kodak Gold 200", "iso": 200, "camera": "Nikon FM2", "status": "active"}
    expect_422(lambda: main_module.validate_film_roll({"filmStock": "", "camera": "FM2"}))
    expect_422(lambda: main_module.validate_film_roll({"filmStock": "Gold", "camera": "FM2", "iso": True}))
    expect_422(lambda: main_module.validate_film_roll({"filmStock": "Gold", "camera": "FM2", "status": "developed"}))
    expect_422(lambda: main_module.validate_film_roll({"filmStock": "Gold", "camera": "FM2", "status": []}))
    expect_422(lambda: main_module.validate_film_roll({"filmStock": "x" * 161, "camera": "FM2"}))
    expect_422(lambda: main_module.validate_film_roll([]))

    exposure = main_module.validate_film_exposure({
        "frameNumber": 1,
        "takenAt": "2026-10-12T10:30:00+08:00",
        "location": " 上海 ",
        "thoughts": " 光很好 ",
        "lens": "50mm",
        "aperture": "f/5.6",
        "shutterSpeed": "1/250s",
        "owner_user_id": "forged",
    })
    assert exposure["takenAt"] == "2026-10-12T02:30:00Z"
    assert exposure["location"] == "上海"
    assert "owner_user_id" not in exposure
    expect_422(lambda: main_module.validate_film_exposure({"frameNumber": -1, "takenAt": "2026-10-12T10:30:00Z"}))
    expect_422(lambda: main_module.validate_film_exposure({"frameNumber": 1, "takenAt": "2026-10-12T10:30"}))
    expect_422(lambda: main_module.validate_film_exposure({"frameNumber": 1, "takenAt": "bad"}))
    expect_422(lambda: main_module.validate_film_exposure([]))

    roll_row = {
        "id": "r1", "owner_user_id": "u1", "film_stock": "Gold 200", "iso": 200,
        "camera": "FM2", "status": "active", "created_at": "2026-10-12T00:00:00Z",
        "updated_at": "2026-10-12T00:00:00Z",
    }
    exposure_rows = [
        {
            "id": "e1", "roll_id": "r1", "frame_number": 1, "taken_at": "2026-10-12T02:30:00Z",
            "location": "上海", "thoughts": "光很好", "lens": "50mm", "aperture": "f/5.6",
            "shutter_speed": "1/250s", "created_at": "2026-10-12T02:31:00Z", "updated_at": "2026-10-12T02:31:00Z",
        },
        {
            "id": "e2", "roll_id": "r1", "frame_number": 1, "taken_at": "2026-10-12T02:32:00Z",
            "location": "", "thoughts": "双重曝光", "lens": "", "aperture": "", "shutter_speed": "",
            "created_at": "2026-10-12T02:33:00Z", "updated_at": "2026-10-12T02:33:00Z",
        },
    ]
    original_repository_connection = repository.connection
    try:
        cursor = FakeCursor(fetchall_results=[[roll_row], exposure_rows])
        repository.connection = fake_connections(cursor)
        listed = repository.list_film_rolls("u1")
        assert [item["frameNumber"] for item in listed[0]["exposures"]] == [1, 1]
        assert listed[0]["filmStock"] == "Gold 200"
        assert "owner_user_id = %s" in cursor.calls[0][0]
        assert "CASE status WHEN 'active'" in cursor.calls[0][0]
        assert "INNER JOIN film_rolls" in cursor.calls[1][0]
        assert all(params == ("u1",) for _, params in cursor.calls)

        owner_lookup = FakeCursor(row=roll_row, rows=[])
        delete_cursor = FakeCursor(rowcount=1)
        repository.connection = fake_connections(owner_lookup, delete_cursor)
        assert repository.delete_film_roll("r1", "u1")
        assert delete_cursor.calls[0] == ("DELETE FROM film_exposures WHERE roll_id = %s", ("r1",))
        assert "owner_user_id = %s" in delete_cursor.calls[1][0]

        update_cursor = FakeCursor(rowcount=0)
        missing_cursor = FakeCursor(row=None)
        repository.connection = fake_connections(update_cursor, missing_cursor)
        assert repository.update_film_exposure("e1", "r1", exposure, "u2") is None
        assert "e.roll_id = %s AND r.owner_user_id = %s" in update_cursor.calls[0][0]
        assert update_cursor.calls[0][1][-3:] == ("e1", "r1", "u2")
    finally:
        repository.connection = original_repository_connection

    original_permission = main_module.require_permission
    original_get_roll = main_module.get_film_roll_for_owner
    try:
        main_module.require_permission = lambda _request, _permission: {"id": "admin", "permissions": ["content:write", "users:manage"]}
        main_module.get_film_roll_for_owner = lambda _roll_id, _user_id: None
        try:
            asyncio.run(main_module.film_roll_update("another-users-roll", FakeRequest({"status": "finished"})))
            raise AssertionError("admin must not update another user's film roll")
        except HTTPException as error:
            assert error.status_code == 404
        main_module.get_film_roll_for_owner = lambda _roll_id, _user_id: repository._film_roll_row(roll_row)
        try:
            asyncio.run(main_module.film_roll_update("r1", FakeRequest([])))
            raise AssertionError("non-object patch payload must fail")
        except HTTPException as error:
            assert error.status_code == 422
    finally:
        main_module.require_permission = original_permission
        main_module.get_film_roll_for_owner = original_get_roll

    original_auth_connection = auth.connection
    original_ensure_non_admin_target = auth._ensure_non_admin_target
    try:
        cleanup_cursor = FakeCursor()
        auth.connection = fake_connections(cleanup_cursor)
        auth._ensure_non_admin_target = lambda _user_id: {"id": "u1"}
        auth.delete_user_account("u1")
        statements = [sql for sql, _ in cleanup_cursor.calls]
        exposure_delete = next(index for index, sql in enumerate(statements) if sql.startswith("DELETE FROM film_exposures"))
        roll_delete = next(index for index, sql in enumerate(statements) if sql.startswith("DELETE FROM film_rolls"))
        user_delete = next(index for index, sql in enumerate(statements) if sql.startswith("DELETE FROM users"))
        assert exposure_delete < roll_delete < user_delete
    finally:
        auth.connection = original_auth_connection
        auth._ensure_non_admin_target = original_ensure_non_admin_target

    app_source = Path("public/app.js").read_text()
    html_source = Path("public/index.html").read_text()
    assert 'id="film-diary"' in html_source
    assert "data-film-exposure-add" in app_source
    assert "条曝光记录也会一起删除" in app_source
    assert "new Date(payload.takenAt).toISOString()" in app_source


if __name__ == "__main__":
    main()
