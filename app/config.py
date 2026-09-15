import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5100"))
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "oka")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "oka")

    OPEN_PLATFORM_BASE_URL = os.getenv(
        "OPEN_PLATFORM_BASE_URL", "https://kfz.oookay.cn"
    ).rstrip("/")
    OPEN_PLATFORM_API_KEY = os.getenv("OPEN_PLATFORM_API_KEY", "").strip()

    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

    SITE_NAME = os.getenv("SITE_NAME", "OKA")
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "")
    SMTP_SENDER_NAME = os.getenv("SMTP_SENDER_NAME", "OKA")
    SMTP_SSL = os.getenv("SMTP_SSL", "1") == "1"
    DEV_SHOW_CODE = os.getenv("DEV_SHOW_CODE", "0") == "1"
    CODE_EXPIRE = int(os.getenv("CODE_EXPIRE", "600"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(220 * 1024 * 1024)))
