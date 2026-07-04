import json
import uuid
from typing import Any

from .database import connection, now_iso


def _plan_row(row: dict[str, Any]) -> dict[str, Any]:
    completions = row["completions"]
    if isinstance(completions, str):
        completions = json.loads(completions or "{}")
    return {
        "id": row["id"],
        "title": row["title"],
        "frequencyType": row["frequency_type"],
        "targetCount": row["target_count"],
        "startDate": row["start_date"],
        "endDate": row["end_date"],
        "completions": completions or {},
        "time": row["time"],
        "duration": row["duration"],
        "color": row["color"],
        "createdAt": row["created_at"],
    }


ROW_MAPPERS = {
    "folders": lambda row: {"id": row["id"], "name": row["name"], "sortOrder": row["sort_order"], "createdAt": row["created_at"]},
    "bookmarks": lambda row: {"id": row["id"], "title": row["title"], "url": row["url"], "category": row["category"], "note": row["note"], "favorite": bool(row["favorite"]), "createdAt": row["created_at"]},
    "todos": lambda row: {"id": row["id"], "title": row["title"], "priority": row["priority"], "dueDate": row["due_date"], "completed": bool(row["completed"]), "createdAt": row["created_at"]},
    "plans": _plan_row,
    "excerpts": lambda row: {"id": row["id"], "content": row["content"], "source": row["source"], "author": row["author"], "excerptDate": row["excerpt_date"], "note": row["note"], "createdAt": row["created_at"]},
}


ORDERS = {
    "folders": "sort_order ASC, created_at DESC",
    "bookmarks": "created_at DESC",
    "todos": "created_at DESC",
    "plans": "created_at DESC",
    "excerpts": "created_at DESC",
}


def list_items(collection: str) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM `{collection}` ORDER BY {ORDERS[collection]}")
            return [ROW_MAPPERS[collection](row) for row in cursor.fetchall()]


def get_item(collection: str, item_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM `{collection}` WHERE id = %s", (item_id,))
            row = cursor.fetchone()
            return ROW_MAPPERS[collection](row) if row else None


def create_item(collection: str, item: dict[str, Any]) -> dict[str, Any]:
    created_at = now_iso()
    item_id = str(uuid.uuid4())
    with connection() as conn:
        with conn.cursor() as cursor:
            if collection == "folders":
                cursor.execute("SELECT COALESCE(MAX(sort_order) + 1, 0) AS next_order FROM folders")
                sort_order = item.get("sortOrder", cursor.fetchone()["next_order"])
                cursor.execute("INSERT INTO folders (id, name, created_at, sort_order) VALUES (%s, %s, %s, %s)", (item_id, item["name"], created_at, sort_order))
            elif collection == "bookmarks":
                cursor.execute("INSERT INTO bookmarks (id, title, url, category, note, favorite, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)", (item_id, item["title"], item["url"], item["category"], item["note"], 1 if item["favorite"] else 0, created_at))
            elif collection == "todos":
                cursor.execute("INSERT INTO todos (id, title, priority, due_date, completed, created_at) VALUES (%s, %s, %s, %s, %s, %s)", (item_id, item["title"], item["priority"], item["dueDate"], 1 if item["completed"] else 0, created_at))
            elif collection == "plans":
                cursor.execute("INSERT INTO plans (id, title, frequency_type, target_count, start_date, end_date, completions, time, duration, color, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (item_id, item["title"], item["frequencyType"], item["targetCount"], item["startDate"], item["endDate"], json.dumps(item["completions"], ensure_ascii=False), item["time"], item["duration"], item["color"], created_at))
            elif collection == "excerpts":
                cursor.execute("INSERT INTO excerpts (id, content, source, author, excerpt_date, note, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)", (item_id, item["content"], item["source"], item["author"], item["excerptDate"], item["note"], created_at))
    return get_item(collection, item_id)


def update_item(collection: str, item_id: str, item: dict[str, Any]) -> dict[str, Any] | None:
    if not get_item(collection, item_id):
        return None
    with connection() as conn:
        with conn.cursor() as cursor:
            if collection == "folders":
                cursor.execute("UPDATE folders SET name = %s, sort_order = %s WHERE id = %s", (item["name"], item["sortOrder"], item_id))
            elif collection == "bookmarks":
                cursor.execute("UPDATE bookmarks SET title = %s, url = %s, category = %s, note = %s, favorite = %s WHERE id = %s", (item["title"], item["url"], item["category"], item["note"], 1 if item["favorite"] else 0, item_id))
            elif collection == "todos":
                cursor.execute("UPDATE todos SET title = %s, priority = %s, due_date = %s, completed = %s WHERE id = %s", (item["title"], item["priority"], item["dueDate"], 1 if item["completed"] else 0, item_id))
            elif collection == "plans":
                cursor.execute("UPDATE plans SET title = %s, frequency_type = %s, target_count = %s, start_date = %s, end_date = %s, completions = %s, time = %s, duration = %s, color = %s WHERE id = %s", (item["title"], item["frequencyType"], item["targetCount"], item["startDate"], item["endDate"], json.dumps(item["completions"], ensure_ascii=False), item["time"], item["duration"], item["color"], item_id))
            elif collection == "excerpts":
                cursor.execute("UPDATE excerpts SET content = %s, source = %s, author = %s, excerpt_date = %s, note = %s WHERE id = %s", (item["content"], item["source"], item["author"], item["excerptDate"], item["note"], item_id))
    return get_item(collection, item_id)


def delete_item(collection: str, item_id: str) -> dict[str, Any] | None:
    item = get_item(collection, item_id)
    if not item:
        return None
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"DELETE FROM `{collection}` WHERE id = %s", (item_id,))
    return item


def folder_exists(name: str) -> bool:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM folders WHERE LOWER(name) = LOWER(%s)", (name,))
            return cursor.fetchone() is not None


def folder_has_bookmarks(name: str) -> bool:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM bookmarks WHERE category = %s LIMIT 1", (name,))
            return cursor.fetchone() is not None
