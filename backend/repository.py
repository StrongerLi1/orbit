import json
import uuid
from contextlib import contextmanager
from typing import Any

from .database import connection, now_iso


USER_SCOPED_COLLECTIONS = frozenset({"todos", "plans"})


def _required_owner_id(collection: str, current_user_id: str) -> str:
    if collection in USER_SCOPED_COLLECTIONS and not current_user_id:
        raise ValueError(f"{collection} 必须绑定当前用户")
    return current_user_id


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


def _excerpt_row(row: dict[str, Any], current_user_id: str = "", is_admin: bool = False) -> dict[str, Any]:
    owner_user_id = row.get("owner_user_id") or ""
    return {
        "id": row["id"],
        "content": row["content"],
        "source": row["source"],
        "author": row["author"],
        "excerptDate": row["excerpt_date"],
        "note": row["note"],
        "createdAt": row["created_at"],
        "createdByName": row.get("owner_name") or "admin",
        "canManage": is_admin or bool(current_user_id and owner_user_id == current_user_id),
    }


ROW_MAPPERS = {
    "folders": lambda row: {"id": row["id"], "name": row["name"], "sortOrder": row["sort_order"], "createdAt": row["created_at"]},
    "bookmarks": lambda row: {"id": row["id"], "title": row["title"], "url": row["url"], "category": row["category"], "note": row["note"], "favorite": bool(row["favorite"]), "createdAt": row["created_at"]},
    "todos": lambda row: {"id": row["id"], "title": row["title"], "priority": row["priority"], "dueDate": row["due_date"], "completed": bool(row["completed"]), "createdAt": row["created_at"]},
    "plans": _plan_row,
    "excerpts": _excerpt_row,
}


ORDERS = {
    "folders": "sort_order ASC, created_at DESC",
    "bookmarks": "created_at DESC",
    "todos": "created_at DESC",
    "plans": "created_at DESC",
    "excerpts": "created_at DESC",
}


def list_items(collection: str, current_user_id: str = "", is_admin: bool = False) -> list[dict[str, Any]]:
    owner_user_id = _required_owner_id(collection, current_user_id)
    with connection() as conn:
        with conn.cursor() as cursor:
            if collection in USER_SCOPED_COLLECTIONS:
                cursor.execute(
                    f"SELECT * FROM `{collection}` WHERE owner_user_id = %s ORDER BY {ORDERS[collection]}",
                    (owner_user_id,),
                )
            elif collection == "excerpts":
                cursor.execute("SELECT e.* FROM excerpts e ORDER BY created_at DESC")
            else:
                cursor.execute(f"SELECT * FROM `{collection}` ORDER BY {ORDERS[collection]}")
            return [ROW_MAPPERS[collection](row, current_user_id, is_admin) if collection == "excerpts" else ROW_MAPPERS[collection](row) for row in cursor.fetchall()]


def get_item(collection: str, item_id: str, current_user_id: str = "", is_admin: bool = False) -> dict[str, Any] | None:
    owner_user_id = _required_owner_id(collection, current_user_id)
    with connection() as conn:
        with conn.cursor() as cursor:
            if collection in USER_SCOPED_COLLECTIONS:
                cursor.execute(
                    f"SELECT * FROM `{collection}` WHERE id = %s AND owner_user_id = %s",
                    (item_id, owner_user_id),
                )
            elif collection == "excerpts":
                cursor.execute("SELECT e.* FROM excerpts e WHERE e.id = %s", (item_id,))
            else:
                cursor.execute(f"SELECT * FROM `{collection}` WHERE id = %s", (item_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ROW_MAPPERS[collection](row, current_user_id, is_admin) if collection == "excerpts" else ROW_MAPPERS[collection](row)


def create_item(collection: str, item: dict[str, Any], current_user: dict[str, Any] | None = None) -> dict[str, Any]:
    current_user_id = current_user.get("id", "") if current_user else ""
    owner_user_id = _required_owner_id(collection, current_user_id)
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
                cursor.execute("INSERT INTO todos (id, owner_user_id, title, priority, due_date, completed, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)", (item_id, owner_user_id, item["title"], item["priority"], item["dueDate"], 1 if item["completed"] else 0, created_at))
            elif collection == "plans":
                cursor.execute("INSERT INTO plans (id, owner_user_id, title, frequency_type, target_count, start_date, end_date, completions, time, duration, color, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (item_id, owner_user_id, item["title"], item["frequencyType"], item["targetCount"], item["startDate"], item["endDate"], json.dumps(item["completions"], ensure_ascii=False), item["time"], item["duration"], item["color"], created_at))
            elif collection == "excerpts":
                if not current_user:
                    raise ValueError("摘录必须绑定当前用户")
                cursor.execute(
                    "INSERT INTO excerpts (id, owner_user_id, owner_name, content, source, author, excerpt_date, note, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (item_id, current_user["id"], current_user["username"], item["content"], item["source"], item["author"], item["excerptDate"], item["note"], created_at),
                )
    if current_user:
        return get_item(collection, item_id, current_user_id, "users:manage" in current_user.get("permissions", []))
    return get_item(collection, item_id)


def update_item(collection: str, item_id: str, item: dict[str, Any], current_user: dict[str, Any] | None = None) -> dict[str, Any] | None:
    current_user_id = current_user.get("id", "") if current_user else ""
    is_admin = bool(current_user and "users:manage" in current_user.get("permissions", []))
    owner_user_id = _required_owner_id(collection, current_user_id)
    if not get_item(collection, item_id, current_user_id, is_admin):
        return None
    with connection() as conn:
        with conn.cursor() as cursor:
            if collection == "folders":
                cursor.execute("UPDATE folders SET name = %s, sort_order = %s WHERE id = %s", (item["name"], item["sortOrder"], item_id))
            elif collection == "bookmarks":
                cursor.execute("UPDATE bookmarks SET title = %s, url = %s, category = %s, note = %s, favorite = %s WHERE id = %s", (item["title"], item["url"], item["category"], item["note"], 1 if item["favorite"] else 0, item_id))
            elif collection == "todos":
                cursor.execute("UPDATE todos SET title = %s, priority = %s, due_date = %s, completed = %s WHERE id = %s AND owner_user_id = %s", (item["title"], item["priority"], item["dueDate"], 1 if item["completed"] else 0, item_id, owner_user_id))
            elif collection == "plans":
                cursor.execute("UPDATE plans SET title = %s, frequency_type = %s, target_count = %s, start_date = %s, end_date = %s, completions = %s, time = %s, duration = %s, color = %s WHERE id = %s AND owner_user_id = %s", (item["title"], item["frequencyType"], item["targetCount"], item["startDate"], item["endDate"], json.dumps(item["completions"], ensure_ascii=False), item["time"], item["duration"], item["color"], item_id, owner_user_id))
            elif collection == "excerpts":
                cursor.execute("UPDATE excerpts SET content = %s, source = %s, author = %s, excerpt_date = %s, note = %s WHERE id = %s", (item["content"], item["source"], item["author"], item["excerptDate"], item["note"], item_id))
    return get_item(collection, item_id, current_user_id, is_admin)


def delete_item(collection: str, item_id: str, current_user: dict[str, Any] | None = None) -> dict[str, Any] | None:
    current_user_id = current_user.get("id", "") if current_user else ""
    is_admin = bool(current_user and "users:manage" in current_user.get("permissions", []))
    owner_user_id = _required_owner_id(collection, current_user_id)
    item = get_item(collection, item_id, current_user_id, is_admin)
    if not item:
        return None
    with connection() as conn:
        with conn.cursor() as cursor:
            if collection in USER_SCOPED_COLLECTIONS:
                cursor.execute(f"DELETE FROM `{collection}` WHERE id = %s AND owner_user_id = %s", (item_id, owner_user_id))
            else:
                cursor.execute(f"DELETE FROM `{collection}` WHERE id = %s", (item_id,))
    return item


def excerpt_owner_id(item_id: str) -> str | None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT owner_user_id FROM excerpts WHERE id = %s", (item_id,))
            row = cursor.fetchone()
            return row["owner_user_id"] if row else None


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


def _conversation_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "userId": row["user_id"],
        "username": row.get("username", ""),
        "title": row["title"],
        "hermesSessionId": row["hermes_session_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "deletedAt": row["deleted_at"],
    }


def _message_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "conversationId": row["conversation_id"],
        "userId": row["user_id"],
        "role": row["role"],
        "content": row["content"],
        "status": row.get("status") or "completed",
        "createdAt": row["created_at"],
    }


def list_hermes_conversations(user_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM hermes_conversations
                WHERE user_id = %s AND deleted_at = ''
                ORDER BY updated_at DESC
                """,
                (user_id,),
            )
            return [_conversation_row(row) for row in cursor.fetchall()]


def list_admin_hermes_conversations() -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.*, u.username
                FROM hermes_conversations c
                JOIN users u ON u.id = c.user_id
                WHERE c.deleted_at = ''
                ORDER BY c.updated_at DESC
                """
            )
            return [_conversation_row(row) for row in cursor.fetchall()]


def create_hermes_conversation(user_id: str, title: str = "") -> dict[str, Any]:
    created_at = now_iso()
    conversation_id = str(uuid.uuid4())
    clean_title = (title or "").strip()[:80] or "新的对话"
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO hermes_conversations
                    (id, user_id, title, hermes_session_id, created_at, updated_at, deleted_at)
                VALUES (%s, %s, %s, '', %s, %s, '')
                """,
                (conversation_id, user_id, clean_title, created_at, created_at),
            )
    conversation = get_hermes_conversation(conversation_id, user_id)
    if conversation is None:
        raise RuntimeError("Hermes conversation was not created")
    return conversation


def get_hermes_conversation(conversation_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    where = "c.id = %s AND c.deleted_at = ''"
    params: tuple[Any, ...] = (conversation_id,)
    if user_id is not None:
        where += " AND c.user_id = %s"
        params = (conversation_id, user_id)
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.*, u.username
                FROM hermes_conversations c
                LEFT JOIN users u ON u.id = c.user_id
                WHERE {where}
                """,
                params,
            )
            row = cursor.fetchone()
            return _conversation_row(row) if row else None


def list_hermes_messages(conversation_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM hermes_messages
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            )
            return [_message_row(row) for row in cursor.fetchall()]


def add_hermes_message(
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
    status: str = "completed",
) -> dict[str, Any]:
    message_id = str(uuid.uuid4())
    created_at = now_iso()
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO hermes_messages
                    (id, conversation_id, user_id, role, content, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (message_id, conversation_id, user_id, role, content, status, created_at),
            )
            cursor.execute("SELECT * FROM hermes_messages WHERE id = %s", (message_id,))
            return _message_row(cursor.fetchone())


@contextmanager
def hermes_chat_user_lock(user_id: str):
    lock_name = f"orbit:hermes-chat:{user_id}"[:64]
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0) AS acquired", (lock_name,))
            acquired = cursor.fetchone()["acquired"] == 1
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
                except Exception:
                    pass


def update_hermes_conversation_after_message(
    conversation_id: str,
    title: str,
    hermes_session_id: str,
) -> dict[str, Any] | None:
    updated_at = now_iso()
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE hermes_conversations
                SET title = %s, hermes_session_id = %s, updated_at = %s
                WHERE id = %s AND deleted_at = ''
                """,
                (title, hermes_session_id, updated_at, conversation_id),
            )
    return get_hermes_conversation(conversation_id)


def soft_delete_hermes_conversation(conversation_id: str, user_id: str | None = None) -> dict[str, bool]:
    deleted_at = now_iso()
    where = "id = %s AND deleted_at = ''"
    params: tuple[Any, ...] = (deleted_at, conversation_id)
    if user_id is not None:
        where += " AND user_id = %s"
        params = (deleted_at, conversation_id, user_id)
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"UPDATE hermes_conversations SET deleted_at = %s WHERE {where}", params)
            return {"ok": cursor.rowcount > 0}


def _book_row(row: dict[str, Any]) -> dict[str, Any]:
    current_user_read_count = int(row.get("current_user_read_count") or 0)
    return {
        "id": row["id"],
        "title": row["title"],
        "author": row["author"],
        "fileFormat": row["file_format"],
        "originalFilename": row["original_filename"],
        "fileSize": int(row["file_size"]),
        "hasCover": bool(row.get("cover_filename")),
        "uploadedByName": row["uploaded_by_name"],
        "readerCount": int(row.get("reader_count") or 0),
        "readCount": int(row.get("read_count") or 0),
        "currentUserReadCount": current_user_read_count,
        "currentUserRead": current_user_read_count > 0,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _book_review_row(row: dict[str, Any], current_user_id: str = "", is_admin: bool = False) -> dict[str, Any]:
    owner_user_id = row["user_id"]
    return {
        "id": row["id"],
        "username": row["reviewer_name"],
        "content": row["content"],
        "createdAt": row["created_at"],
        "canDelete": is_admin or owner_user_id == current_user_id,
    }


def list_books(user_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT b.*,
                    COALESCE(stats.reader_count, 0) AS reader_count,
                    COALESCE(stats.read_count, 0) AS read_count,
                    COALESCE(mine.current_user_read_count, 0) AS current_user_read_count
                FROM books b
                LEFT JOIN (
                    SELECT book_id, COUNT(DISTINCT user_id) AS reader_count, COUNT(*) AS read_count
                    FROM book_reads
                    GROUP BY book_id
                ) stats ON stats.book_id = b.id
                LEFT JOIN (
                    SELECT book_id, COUNT(*) AS current_user_read_count
                    FROM book_reads
                    WHERE user_id = %s
                    GROUP BY book_id
                ) mine ON mine.book_id = b.id
                ORDER BY b.created_at DESC
                """,
                (user_id,),
            )
            return [_book_row(row) for row in cursor.fetchall()]


def get_book(book_id: str, user_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT b.*,
                    (SELECT COUNT(DISTINCT r.user_id) FROM book_reads r WHERE r.book_id = b.id) AS reader_count,
                    (SELECT COUNT(*) FROM book_reads r WHERE r.book_id = b.id) AS read_count,
                    (SELECT COUNT(*) FROM book_reads r WHERE r.book_id = b.id AND r.user_id = %s) AS current_user_read_count
                FROM books b
                WHERE b.id = %s
                """,
                (user_id, book_id),
            )
            row = cursor.fetchone()
            return _book_row(row) if row else None


def get_book_storage(book_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM books WHERE id = %s", (book_id,))
            return cursor.fetchone()


def create_book(book: dict[str, Any], user_id: str) -> dict[str, Any]:
    created_at = now_iso()
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO books
                    (id, title, author, file_format, original_filename, stored_filename,
                     file_size, cover_filename, cover_content_type, uploaded_by,
                     uploaded_by_name, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    book["id"], book["title"], book["author"], book["fileFormat"],
                    book["originalFilename"], book["storedFilename"], book["fileSize"],
                    book.get("coverFilename", ""), book.get("coverContentType", ""),
                    user_id, book["uploadedByName"], created_at, created_at,
                ),
            )
    result = get_book(book["id"], user_id)
    if result is None:
        raise RuntimeError("Book was not created")
    return result


def update_book(
    book_id: str,
    user_id: str,
    title: str,
    author: str,
    cover_filename: str,
    cover_content_type: str,
) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE books
                SET title = %s, author = %s, cover_filename = %s,
                    cover_content_type = %s, updated_at = %s
                WHERE id = %s
                """,
                (title, author, cover_filename, cover_content_type, now_iso(), book_id),
            )
    return get_book(book_id, user_id)


def delete_book(book_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        conn.begin()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM books WHERE id = %s FOR UPDATE", (book_id,))
                book = cursor.fetchone()
                if not book:
                    conn.rollback()
                    return None
                cursor.execute("DELETE FROM book_reads WHERE book_id = %s", (book_id,))
                cursor.execute("DELETE FROM book_reviews WHERE book_id = %s", (book_id,))
                cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
            conn.commit()
            return book
        except Exception:
            conn.rollback()
            raise


def list_book_reads(book_id: str, current_user_id: str) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.user_id, r.read_date, r.created_at, r.updated_at, u.username
                FROM book_reads r
                JOIN users u ON u.id = r.user_id
                WHERE r.book_id = %s
                ORDER BY u.username ASC, r.read_date DESC, r.created_at DESC
                """,
                (book_id,),
            )
            rows = cursor.fetchall()
    readers: list[dict[str, Any]] = []
    by_user: dict[str, dict[str, Any]] = {}
    for row in rows:
        reader = by_user.get(row["user_id"])
        if reader is None:
            reader = {
                "username": row["username"],
                "isCurrentUser": row["user_id"] == current_user_id,
                "reads": [],
            }
            by_user[row["user_id"]] = reader
            readers.append(reader)
        reader["reads"].append({
            "id": row["id"],
            "readDate": row["read_date"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        })
    return {"readerCount": len(readers), "readCount": len(rows), "readers": readers}


def list_book_reviews(book_id: str, current_user_id: str, is_admin: bool = False) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, book_id, user_id, reviewer_name, content, created_at
                FROM book_reviews
                WHERE book_id = %s
                ORDER BY created_at DESC
                """,
                (book_id,),
            )
            return [_book_review_row(row, current_user_id, is_admin) for row in cursor.fetchall()]


def _insert_book_review(
    cursor,
    review_id: str,
    book_id: str,
    user_id: str,
    reviewer_name: str,
    content: str,
    created_at: str,
) -> None:
    cursor.execute(
        """
        INSERT INTO book_reviews (id, book_id, user_id, reviewer_name, content, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (review_id, book_id, user_id, reviewer_name, content, created_at),
    )


def create_book_review(book_id: str, user_id: str, reviewer_name: str, content: str) -> dict[str, Any]:
    review_id = str(uuid.uuid4())
    created_at = now_iso()
    with connection() as conn:
        with conn.cursor() as cursor:
            _insert_book_review(cursor, review_id, book_id, user_id, reviewer_name, content, created_at)
    return {
        "id": review_id,
        "username": reviewer_name,
        "content": content,
        "createdAt": created_at,
        "canDelete": True,
    }


def delete_book_review(book_id: str, review_id: str, user_id: str, is_admin: bool = False) -> bool:
    where = "id = %s AND book_id = %s"
    params: tuple[Any, ...] = (review_id, book_id)
    if not is_admin:
        where += " AND user_id = %s"
        params += (user_id,)
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"DELETE FROM book_reviews WHERE {where}", params)
            return cursor.rowcount > 0


def create_book_read(
    book_id: str,
    user_id: str,
    read_date: str,
    review_content: str = "",
    reviewer_name: str = "",
) -> dict[str, Any]:
    read_id = str(uuid.uuid4())
    created_at = now_iso()
    review = None
    with connection() as conn:
        conn.begin()
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO book_reads (id, book_id, user_id, read_date, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (read_id, book_id, user_id, read_date, created_at, created_at),
                )
                if review_content:
                    review_id = str(uuid.uuid4())
                    _insert_book_review(cursor, review_id, book_id, user_id, reviewer_name, review_content, created_at)
                    review = {
                        "id": review_id,
                        "username": reviewer_name,
                        "content": review_content,
                        "createdAt": created_at,
                        "canDelete": True,
                    }
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    result = {"id": read_id, "readDate": read_date, "createdAt": created_at, "updatedAt": created_at}
    if review is not None:
        result["review"] = review
    return result


def update_book_read(book_id: str, read_id: str, user_id: str, read_date: str) -> dict[str, Any] | None:
    updated_at = now_iso()
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE book_reads SET read_date = %s, updated_at = %s
                WHERE id = %s AND book_id = %s AND user_id = %s
                """,
                (read_date, updated_at, read_id, book_id, user_id),
            )
            cursor.execute(
                """
                SELECT id, read_date, created_at, updated_at
                FROM book_reads
                WHERE id = %s AND book_id = %s AND user_id = %s
                """,
                (read_id, book_id, user_id),
            )
            row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "readDate": row["read_date"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def delete_book_read(book_id: str, read_id: str, user_id: str) -> bool:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM book_reads WHERE id = %s AND book_id = %s AND user_id = %s",
                (read_id, book_id, user_id),
            )
            return cursor.rowcount > 0
