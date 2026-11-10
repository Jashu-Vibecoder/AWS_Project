"""Environment-based configuration for the CloudBox API."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Config:
    """Settings are read from the project .env file or process environment."""

    DEBUG = os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "cloudbox_db")
    DB_USER = os.getenv("DB_USER", "cloudbox_app")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_SECRET_ARN = os.getenv("DB_SECRET_ARN", "")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
    DB_SSL_CA = os.getenv("DB_SSL_CA", "")
    API_AUTH_REQUIRED = os.getenv("API_AUTH_REQUIRED", "false").strip().lower() == "true"
    CLOUDBOX_API_TOKEN = os.getenv("CLOUDBOX_API_TOKEN", "")
    AUTH_TOKEN_SECRET_ARN = os.getenv("AUTH_TOKEN_SECRET_ARN", "")
    AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
    CORS_ALLOWED_ORIGINS = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5500,http://127.0.0.1:5500",
        ).split(",")
        if origin.strip()
    )
