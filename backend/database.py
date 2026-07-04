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
                    title VARCHAR(300) NOT NULL,
                    priority VARCHAR(20) NOT NULL,
                    due_date VARCHAR(20) NOT NULL,
                    completed TINYINT(1) NOT NULL DEFAULT 0,
                    created_at VARCHAR(40) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(300) NOT NULL,
                    frequency_type VARCHAR(20) NOT NULL,
                    target_count INT NOT NULL,
                    start_date VARCHAR(20) NOT NULL,
                    end_date VARCHAR(20) NOT NULL,
                    completions JSON NOT NULL,
                    time VARCHAR(10) NOT NULL,
                    duration INT NOT NULL,
                    color VARCHAR(20) NOT NULL,
                    created_at VARCHAR(40) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS excerpts (
                    id VARCHAR(64) PRIMARY KEY,
                    content TEXT NOT NULL,
                    source VARCHAR(300) NOT NULL,
                    author VARCHAR(160) NOT NULL,
                    excerpt_date VARCHAR(20) NOT NULL,
                    note TEXT NOT NULL,
                    created_at VARCHAR(40) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
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
            for folder in reversed(data["folders"]):
                cursor.execute(
                    "INSERT INTO folders (id, name, created_at, sort_order) VALUES (%s, %s, %s, %s)",
                    (folder.get("id") or str(uuid.uuid4()), folder.get("name", ""), folder.get("createdAt") or now_iso(), 0),
                )
            for bookmark in reversed(data["bookmarks"]):
                cursor.execute(
                    "INSERT INTO bookmarks (id, title, url, category, note, favorite, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (bookmark.get("id") or str(uuid.uuid4()), bookmark.get("title", ""), bookmark.get("url", ""), bookmark.get("category", "未分类"), bookmark.get("note", ""), 1 if bookmark.get("favorite") else 0, bookmark.get("createdAt") or now_iso()),
                )
            for todo in reversed(data["todos"]):
                cursor.execute(
                    "INSERT INTO todos (id, title, priority, due_date, completed, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (todo.get("id") or str(uuid.uuid4()), todo.get("title", ""), todo.get("priority", "medium"), todo.get("dueDate", ""), 1 if todo.get("completed") else 0, todo.get("createdAt") or now_iso()),
                )
            for plan in reversed(data["plans"]):
                cursor.execute(
                    "INSERT INTO plans (id, title, frequency_type, target_count, start_date, end_date, completions, time, duration, color, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (plan.get("id") or str(uuid.uuid4()), plan.get("title", ""), plan.get("frequencyType", "daily"), int(plan.get("targetCount") or 1), plan.get("startDate") or local_date(), plan.get("endDate") or "", json.dumps(plan.get("completions") or {}, ensure_ascii=False), plan.get("time") or "09:00", int(plan.get("duration") or 30), plan.get("color") or "violet", plan.get("createdAt") or now_iso()),
                )
            for excerpt in reversed(data["excerpts"]):
                cursor.execute(
                    "INSERT INTO excerpts (id, content, source, author, excerpt_date, note, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (excerpt.get("id") or str(uuid.uuid4()), excerpt.get("content", ""), excerpt.get("source", ""), excerpt.get("author", ""), excerpt.get("excerptDate", ""), excerpt.get("note", ""), excerpt.get("createdAt") or now_iso()),
                )
