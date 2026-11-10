"""MySQL connection management and availability checks."""

from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from backend.config import Config
from backend.secrets import get_secret


class DatabaseUnavailable(RuntimeError):
    """Raised when the API cannot safely reach its configured database."""


def _database_password():
    if Config.DB_SECRET_ARN:
        secret = get_secret(Config.DB_SECRET_ARN, Config.AWS_REGION)
        if isinstance(secret, dict):
            return str(secret.get("password", ""))
        return str(secret or "")
    return Config.DB_PASSWORD


@contextmanager
def database_connection():
    """Open one short-lived connection and always close it."""
    connection = None
    try:
        import certifi

        connection = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=_database_password(),
            database=Config.DB_NAME,
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=Config.DB_CONNECT_TIMEOUT,
            read_timeout=Config.DB_CONNECT_TIMEOUT,
            write_timeout=Config.DB_CONNECT_TIMEOUT,
            autocommit=True,
            init_command="SET time_zone = '+00:00'",
            ssl={"ca": Config.DB_SSL_CA or certifi.where(), "check_hostname": True},
        )
        yield connection
    except (pymysql.MySQLError, OSError) as exc:
        raise DatabaseUnavailable("Database is unavailable") from exc
    except Exception as exc:
        # Secrets Manager and other configured credential providers fail
        # before PyMySQL can connect. Keep those details out of API responses.
        if Config.DB_SECRET_ARN:
            raise DatabaseUnavailable("Database credentials are unavailable") from exc
        raise
    finally:
        if connection is not None:
            connection.close()


def check_database_connection():
    """Run a minimal query without exposing connection details to callers."""
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
