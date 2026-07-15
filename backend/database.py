import json
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from .config import DATA_FILE, settings


COLLECTIONS = {"bookmarks", "todos", "plans", "folders", "excerpts"}


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def local_date() -> str:
    return date.today().isoformat()


def seed_data() -> dict[str, list[dict[str, Any]]]:
    created_at = now_iso()
    return {
        "excerpts": [],
        "folders": [
            {"id": str(uuid.uuid4()), "name": "阅读", "createdAt": created_at},
            {"id": str(uuid.uuid4()), "name": "工具", "createdAt": created_at},
            {"id": str(uuid.uuid4()), "name": "灵感", "createdAt": created_at},
        ],
        "bookmarks": [
            {"id": str(uuid.uuid4()), "title": "Readwise Reader", "url": "https://readwise.io/read", "category": "阅读", "note": "稍后读与高亮整理", "favorite": True, "createdAt": created_at},
            {"id": str(uuid.uuid4()), "title": "Linear", "url": "https://linear.app", "category": "工具", "note": "简洁的项目管理", "favorite": False, "createdAt": created_at},
            {"id": str(uuid.uuid4()), "title": "Are.na", "url": "https://www.are.na", "category": "灵感", "note": "收集视觉与想法", "favorite": True, "createdAt": created_at},
        ],
        "todos": [
            {"id": str(uuid.uuid4()), "title": "整理本周收藏", "priority": "medium", "dueDate": "", "completed": False, "createdAt": created_at},
            {"id": str(uuid.uuid4()), "title": "完成个人工作台第一版", "priority": "high", "dueDate": local_date(), "completed": False, "createdAt": created_at},
        ],
        "plans": [
            {"id": str(uuid.uuid4()), "title": "晨间阅读", "frequencyType": "daily", "targetCount": 1, "startDate": local_date(), "endDate": "", "completions": {}, "time": "08:00", "duration": 30, "color": "violet", "createdAt": created_at},
            {"id": str(uuid.uuid4()), "title": "专注工作", "frequencyType": "daily", "targetCount": 1, "startDate": local_date(), "endDate": "", "completions": {}, "time": "09:30", "duration": 90, "color": "orange", "createdAt": created_at},
            {"id": str(uuid.uuid4()), "title": "晚间复盘", "frequencyType": "daily", "targetCount": 1, "startDate": local_date(), "endDate": "", "completions": {}, "time": "21:30", "duration": 20, "color": "green", "createdAt": created_at},
        ],
    }


def _base_connection(database: str | None = None):
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=database,
        charset=settings.mysql_charset,
        cursorclass=DictCursor,
        autocommit=True,
    )


@contextmanager
def connection():
    conn = _base_connection(settings.mysql_database)
    try:
        yield conn
    finally:
        conn.close()


def initialize_database() -> None:
    with _base_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )

    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS folders (
                    id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(120) NOT NULL UNIQUE,
                    created_at VARCHAR(40) NOT NULL,
                    sort_order INT NOT NULL DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'folders' AND COLUMN_NAME = 'sort_order'
                """,
                (settings.mysql_database,),
            )
            if cursor.fetchone()["count"] == 0:
                cursor.execute("ALTER TABLE folders ADD COLUMN sort_order INT NOT NULL DEFAULT 0 AFTER created_at")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(300) NOT NULL,
                    url TEXT NOT NULL,
                    category VARCHAR(120) NOT NULL,
                    note TEXT NOT NULL,
                    favorite TINYINT(1) NOT NULL DEFAULT 0,
                    created_at VARCHAR(40) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id VARCHAR(64) PRIMARY KEY,
                    owner_user_id VARCHAR(64) NULL DEFAULT NULL,
                    title VARCHAR(300) NOT NULL,
                    priority VARCHAR(20) NOT NULL,
                    due_date VARCHAR(20) NOT NULL,
                    completed TINYINT(1) NOT NULL DEFAULT 0,
                    created_at VARCHAR(40) NOT NULL,
                    INDEX idx_todos_owner_created (owner_user_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id VARCHAR(64) PRIMARY KEY,
                    owner_user_id VARCHAR(64) NULL DEFAULT NULL,
                    title VARCHAR(300) NOT NULL,
                    frequency_type VARCHAR(20) NOT NULL,
                    target_count INT NOT NULL,
                    start_date VARCHAR(20) NOT NULL,
                    end_date VARCHAR(20) NOT NULL,
                    completions JSON NOT NULL,
                    time VARCHAR(10) NOT NULL,
                    duration INT NOT NULL,
                    color VARCHAR(20) NOT NULL,
                    created_at VARCHAR(40) NOT NULL,
                    INDEX idx_plans_owner_created (owner_user_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            for table in ("todos", "plans"):
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = 'owner_user_id'
                    """,
                    (settings.mysql_database, table),
                )
                if cursor.fetchone()["count"] == 0:
                    cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN owner_user_id VARCHAR(64) NULL DEFAULT NULL AFTER id")
                index_name = f"idx_{table}_owner_created"
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s
                    """,
                    (settings.mysql_database, table, index_name),
                )
                if cursor.fetchone()["count"] == 0:
                    cursor.execute(f"ALTER TABLE `{table}` ADD INDEX `{index_name}` (owner_user_id, created_at)")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS excerpts (
                    id VARCHAR(64) PRIMARY KEY,
                    owner_user_id VARCHAR(64) NULL DEFAULT NULL,
                    owner_name VARCHAR(64) NOT NULL DEFAULT 'admin',
                    is_anonymous TINYINT(1) NOT NULL DEFAULT 0,
                    content TEXT NOT NULL,
                    source VARCHAR(300) NOT NULL,
                    author VARCHAR(160) NOT NULL,
                    excerpt_date VARCHAR(20) NOT NULL,
                    note TEXT NOT NULL,
                    created_at VARCHAR(40) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            for column, definition in {
                "owner_user_id": "VARCHAR(64) NULL DEFAULT NULL AFTER id",
                "owner_name": "VARCHAR(64) NOT NULL DEFAULT 'admin' AFTER owner_user_id",
                "is_anonymous": "TINYINT(1) NOT NULL DEFAULT 0 AFTER owner_name",
            }.items():
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'excerpts' AND COLUMN_NAME = %s
                    """,
                    (settings.mysql_database, column),
                )
                if cursor.fetchone()["count"] == 0:
                    cursor.execute(f"ALTER TABLE excerpts ADD COLUMN {column} {definition}")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(300) NOT NULL,
                    author VARCHAR(200) NOT NULL,
                    file_format VARCHAR(20) NOT NULL,
                    original_filename VARCHAR(300) NOT NULL,
                    stored_filename VARCHAR(120) NOT NULL,
                    file_size BIGINT NOT NULL,
                    cover_filename VARCHAR(120) NOT NULL DEFAULT '',
                    cover_content_type VARCHAR(80) NOT NULL DEFAULT '',
                    uploaded_by VARCHAR(64) NOT NULL,
                    uploaded_by_name VARCHAR(64) NOT NULL,
                    created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL,
                    INDEX idx_books_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS book_reads (
                    id VARCHAR(64) PRIMARY KEY,
                    book_id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(64) NOT NULL,
                    read_date VARCHAR(20) NOT NULL,
                    created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL,
                    INDEX idx_book_reads_book_user_date (book_id, user_id, read_date),
                    INDEX idx_book_reads_user_book (user_id, book_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS book_reviews (
                    id VARCHAR(64) PRIMARY KEY,
                    book_id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(64) NOT NULL,
                    reviewer_name VARCHAR(64) NOT NULL,
                    is_anonymous TINYINT(1) NOT NULL DEFAULT 0,
                    content TEXT NOT NULL,
                    created_at VARCHAR(40) NOT NULL,
                    INDEX idx_book_reviews_book_created (book_id, created_at),
                    INDEX idx_book_reviews_user (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'book_reviews' AND COLUMN_NAME = 'is_anonymous'
                """,
                (settings.mysql_database,),
            )
            if cursor.fetchone()["count"] == 0:
                cursor.execute("ALTER TABLE book_reviews ADD COLUMN is_anonymous TINYINT(1) NOT NULL DEFAULT 0 AFTER reviewer_name")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS hermes_conversations (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    title VARCHAR(160) NOT NULL,
                    hermes_session_id VARCHAR(120) NOT NULL DEFAULT '',
                    created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL,
                    deleted_at VARCHAR(40) NOT NULL DEFAULT '',
                    INDEX idx_hermes_conversations_user (user_id, deleted_at, updated_at),
                    INDEX idx_hermes_conversations_deleted (deleted_at, updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS hermes_messages (
                    id VARCHAR(64) PRIMARY KEY,
                    conversation_id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(64) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content MEDIUMTEXT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'completed',
                    created_at VARCHAR(40) NOT NULL,
                    INDEX idx_hermes_messages_conversation (conversation_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'hermes_messages' AND COLUMN_NAME = 'status'
                """,
                (settings.mysql_database,),
            )
            if cursor.fetchone()["count"] == 0:
                cursor.execute(
                    "ALTER TABLE hermes_messages ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'completed' AFTER content"
                )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(64) PRIMARY KEY,
                    username VARCHAR(64) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    is_admin TINYINT(1) NOT NULL DEFAULT 0,
                    is_banned TINYINT(1) NOT NULL DEFAULT 0,
                    created_at VARCHAR(40) NOT NULL,
                    last_login_at VARCHAR(40) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users' AND COLUMN_NAME = 'is_banned'
                """,
                (settings.mysql_database,),
            )
            if cursor.fetchone()["count"] == 0:
                cursor.execute("ALTER TABLE users ADD COLUMN is_banned TINYINT(1) NOT NULL DEFAULT 0 AFTER is_admin")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(64) NOT NULL UNIQUE,
                    description VARCHAR(255) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS permissions (
                    id VARCHAR(80) PRIMARY KEY,
                    name VARCHAR(80) NOT NULL UNIQUE,
                    description VARCHAR(255) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_id VARCHAR(64) NOT NULL,
                    permission_id VARCHAR(80) NOT NULL,
                    PRIMARY KEY (role_id, permission_id),
                    INDEX idx_role_permissions_permission (permission_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id VARCHAR(64) NOT NULL,
                    role_id VARCHAR(64) NOT NULL,
                    PRIMARY KEY (user_id, role_id),
                    INDEX idx_user_roles_role (role_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )

    if settings.migrate_from_json:
        migrate_from_json_if_empty(DATA_FILE)
    from .auth import seed_admin_user, seed_rbac_defaults
    seed_rbac_defaults()
    seed_admin_user()
    backfill_legacy_owners()


def backfill_legacy_owners() -> None:
    """Attach legacy user-owned content to the seeded admin."""
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username FROM users WHERE username = %s LIMIT 1",
                (settings.admin_username or "admin",),
            )
            admin = cursor.fetchone()
            if not admin:
                cursor.execute("SELECT id, username FROM users WHERE is_admin = 1 ORDER BY created_at ASC LIMIT 1")
                admin = cursor.fetchone()
            if admin:
                for table in ("todos", "plans", "excerpts"):
                    cursor.execute(
                        f"UPDATE `{table}` SET owner_user_id = %s WHERE owner_user_id IS NULL OR owner_user_id = ''",
                        (admin["id"],),
                    )


def migrate_from_json_if_empty(source: Path) -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM bookmarks")
            has_data = cursor.fetchone()["count"] > 0
    if has_data:
        return

    if source.exists():
        data = json.loads(source.read_text(encoding="utf-8"))
    else:
        data = seed_data()
    data = normalize_db(data)
    replace_all(data)


def normalize_db(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    normalized = {name: list(data.get(name) or []) for name in COLLECTIONS}
    changed_categories = []
    if not normalized["folders"]:
        names = []
        for bookmark in normalized["bookmarks"]:
            category = str(bookmark.get("category") or "").strip()
            if category and category not in names:
                names.append(category)
        normalized["folders"] = [{"id": str(uuid.uuid4()), "name": name, "createdAt": now_iso()} for name in names]

    for plan in normalized["plans"]:
        if not plan.get("frequencyType"):
            original_date = plan.get("date") or local_date()
            plan["frequencyType"] = "daily"
            plan["targetCount"] = 1
            plan["startDate"] = original_date
            plan["endDate"] = ""
            plan["completions"] = {original_date: 1} if plan.get("completed") else {}
        if not isinstance(plan.get("completions"), dict):
            plan["completions"] = {}

    for bookmark in normalized["bookmarks"]:
        category = str(bookmark.get("category") or "未分类").strip()
        bookmark["category"] = category
        changed_categories.append(category)

    existing_folders = {folder.get("name") for folder in normalized["folders"]}
    for category in dict.fromkeys(changed_categories):
        if category and category not in existing_folders:
            normalized["folders"].append({"id": str(uuid.uuid4()), "name": category, "createdAt": now_iso()})
            existing_folders.add(category)

    return normalized


def replace_all(data: dict[str, list[dict[str, Any]]]) -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM excerpts")
            cursor.execute("DELETE FROM plans")
            cursor.execute("DELETE FROM todos")
            cursor.execute("DELETE FROM bookmarks")
            cursor.execute("DELETE FROM folders")
            for index, folder in enumerate(data["folders"]):
                cursor.execute(
                    "INSERT INTO folders (id, name, created_at, sort_order) VALUES (%s, %s, %s, %s)",
                    (folder.get("id") or str(uuid.uuid4()), folder.get("name", ""), folder.get("createdAt") or now_iso(), int(folder.get("sortOrder", index) or 0)),
                )
            for bookmark in reversed(data["bookmarks"]):
                cursor.execute(
                    "INSERT INTO bookmarks (id, title, url, category, note, favorite, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (bookmark.get("id") or str(uuid.uuid4()), bookmark.get("title", ""), bookmark.get("url", ""), bookmark.get("category", "未分类"), bookmark.get("note", ""), 1 if bookmark.get("favorite") else 0, bookmark.get("createdAt") or now_iso()),
                )
            for todo in reversed(data["todos"]):
                cursor.execute(
                    "INSERT INTO todos (id, owner_user_id, title, priority, due_date, completed, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (todo.get("id") or str(uuid.uuid4()), None, todo.get("title", ""), todo.get("priority", "medium"), todo.get("dueDate", ""), 1 if todo.get("completed") else 0, todo.get("createdAt") or now_iso()),
                )
            for plan in reversed(data["plans"]):
                cursor.execute(
                    "INSERT INTO plans (id, owner_user_id, title, frequency_type, target_count, start_date, end_date, completions, time, duration, color, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (plan.get("id") or str(uuid.uuid4()), None, plan.get("title", ""), plan.get("frequencyType", "daily"), int(plan.get("targetCount") or 1), plan.get("startDate") or local_date(), plan.get("endDate") or "", json.dumps(plan.get("completions") or {}, ensure_ascii=False), plan.get("time") or "09:00", int(plan.get("duration") or 30), plan.get("color") or "violet", plan.get("createdAt") or now_iso()),
                )
            for excerpt in reversed(data["excerpts"]):
                cursor.execute(
                    "INSERT INTO excerpts (id, owner_user_id, owner_name, is_anonymous, content, source, author, excerpt_date, note, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (excerpt.get("id") or str(uuid.uuid4()), None, "admin", 1 if excerpt.get("isAnonymous") else 0, excerpt.get("content", ""), excerpt.get("source", ""), excerpt.get("author", ""), excerpt.get("excerptDate", ""), excerpt.get("note", ""), excerpt.get("createdAt") or now_iso()),
                )
