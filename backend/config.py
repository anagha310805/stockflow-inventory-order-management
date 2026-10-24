import os
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


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TOKEN_MAX_AGE = int(os.getenv("TOKEN_MAX_AGE", "43200"))
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:5177,http://127.0.0.1:5173,http://127.0.0.1:5177",
        ).split(",")
        if origin.strip()
    ]
