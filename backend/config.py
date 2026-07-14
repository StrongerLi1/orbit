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
    library_storage_dir = Path(os.getenv("LIBRARY_STORAGE_DIR", str(BASE_DIR / "data" / "library"))).expanduser()
    library_max_file_mb = max(1, int(os.getenv("LIBRARY_MAX_FILE_MB", "100")))
    library_max_cover_mb = max(1, int(os.getenv("LIBRARY_MAX_COVER_MB", "5")))
    hermes_dashboard_url = os.getenv("HERMES_DASHBOARD_URL", "http://127.0.0.1:9119").rstrip("/")
    hermes_dashboard_public_path = os.getenv("HERMES_DASHBOARD_PUBLIC_PATH", "/hermes-dashboard").rstrip("/") or "/hermes-dashboard"
    hermes_dashboard_command = os.getenv("HERMES_DASHBOARD_COMMAND", "hermes dashboard --host 127.0.0.1 --port 9119 --no-open")
    hermes_dashboard_stop_command = os.getenv("HERMES_DASHBOARD_STOP_COMMAND", "hermes dashboard --stop")
    hermes_dashboard_timeout = float(os.getenv("HERMES_DASHBOARD_TIMEOUT", "5"))
    hermes_stream_command = os.getenv("HERMES_STREAM_COMMAND", "")
    hermes_stream_pool_size = max(1, min(8, int(os.getenv("HERMES_STREAM_POOL_SIZE", "2"))))
    hermes_stream_pool_wait_timeout = max(0.1, float(os.getenv("HERMES_STREAM_POOL_WAIT_TIMEOUT", "5")))
    hermes_chat_timeout = max(0.0, float(os.getenv("HERMES_CHAT_TIMEOUT", "1800")))
    session_secret = os.getenv("SESSION_SECRET", "dev-session-secret-change-me")
    jwt_secret = os.getenv("JWT_SECRET") or session_secret
    jwt_access_minutes = int(os.getenv("JWT_ACCESS_MINUTES", "15"))
    jwt_refresh_days = int(os.getenv("JWT_REFRESH_DAYS", "14"))
    redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))
    redis_password = os.getenv("REDIS_PASSWORD", "")
    admin_username = os.getenv("ADMIN_USERNAME", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")


settings = Settings()
