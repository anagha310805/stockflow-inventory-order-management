import os
import ssl
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def database_url():
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        if configured_url.startswith("mysql://"):
            return configured_url.replace("mysql://", "mysql+pymysql://", 1)
        return configured_url
    username = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    if not username or not password:
        return None
    return URL.create(
        "mysql+pymysql",
        username=username,
        password=password,
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE", "stockflow"),
        query={"charset": "utf8mb4"},
    ).render_as_string(hide_password=False)


def engine_options():
    options = {
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "280")),
        "pool_pre_ping": True,
    }
    db_uri = database_url() or ""
    host = os.getenv("MYSQL_HOST", "")
    use_ssl = os.getenv("MYSQL_SSL", "").lower() in ("true", "1", "yes", "required")
    is_remote = any(k in db_uri.lower() for k in ("tidbcloud.com", "aivencloud.com", "rds.amazonaws.com", "sslmode", "ssl_mode")) or (host and host not in ("127.0.0.1", "localhost"))
    if use_ssl or is_remote:
        options["connect_args"] = {"ssl": ssl.create_default_context()}
    return options


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_ENGINE_OPTIONS = engine_options()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TOKEN_MAX_AGE = int(os.getenv("TOKEN_MAX_AGE", "43200"))
    _DEFAULT_CORS_ORIGINS = [
        "https://stockflow-inventory-order-managemen.vercel.app",
        "https://stockflow-inventory-order-management.vercel.app",
        "http://localhost:5173",
        "http://localhost:5177",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5177",
    ]
    _ENV_CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    CORS_ORIGINS = list(dict.fromkeys(_ENV_CORS_ORIGINS + _DEFAULT_CORS_ORIGINS)) if _ENV_CORS_ORIGINS else _DEFAULT_CORS_ORIGINS
