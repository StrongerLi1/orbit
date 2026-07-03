import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_FILE = BASE_DIR / "data" / "db.json"


class Settings:
    app_name = "Orbit Personal Hub"
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))
    mysql_host = os.getenv("MYSQL_HOST", "127.0.0.1")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user = os.getenv("MYSQL_USER", "orbit")
    mysql_password = os.getenv("MYSQL_PASSWORD", "orbit_password")
    mysql_database = os.getenv("MYSQL_DATABASE", "orbit")
    mysql_charset = os.getenv("MYSQL_CHARSET", "utf8mb4")
    migrate_from_json = os.getenv("MYSQL_MIGRATE_FROM_JSON", "true").lower() in {"1", "true", "yes", "on"}
    pansou_base_url = os.getenv("PANSOU_BASE_URL") or os.getenv("LIMITLESS_SEARCH_BASE_URL", "http://127.0.0.1:8888")
    pansou_base_url = pansou_base_url.rstrip("/")
    pansou_timeout = float(os.getenv("PANSOU_TIMEOUT") or os.getenv("LIMITLESS_SEARCH_TIMEOUT", "12"))
    session_secret = os.getenv("SESSION_SECRET", "dev-session-secret-change-me")
    admin_username = os.getenv("ADMIN_USERNAME", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")


settings = Settings()
