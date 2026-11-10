"""Small MySQL access layer for Lambda metadata operations."""

import os
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor
import certifi

from common.secrets import get_secret


@contextmanager
def database_connection():
    """Open a short-lived connection using Lambda environment configuration."""
    connection = None
    try:
        kwargs = {
            "host": os.environ["DB_HOST"],
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.environ["DB_USER"],
            "password": _database_password(),
            "database": os.getenv("DB_NAME", "cloudbox_db"),
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
            "read_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
            "write_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
            "autocommit": True,
            "init_command": "SET time_zone = '+00:00'",
        }
        ca_file = os.getenv("DB_SSL_CA") or certifi.where()
        kwargs["ssl"] = {"ca": ca_file, "check_hostname": True}
        connection = pymysql.connect(**kwargs)
        yield connection
    except (KeyError, ValueError, pymysql.MySQLError, OSError) as exc:
        raise RuntimeError("Metadata database is unavailable") from exc
    finally:
        if connection is not None:
            connection.close()


def _database_password():
    secret_arn = os.getenv("DB_SECRET_ARN", "")
    if secret_arn:
        secret = get_secret(secret_arn)
        if isinstance(secret, dict):
            return str(secret.get("password", ""))
        return str(secret or "")
    return os.environ["DB_PASSWORD"]


def insert_file_metadata(file_name, s3_key, file_size, file_type):
    """Insert confirmed object metadata idempotently by its unique S3 key."""
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO files (file_name, s3_key, file_size, file_type, status) "
                "VALUES (%s, %s, %s, %s, 'active') "
                "ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)",
                (file_name, s3_key, file_size, file_type),
            )
            return int(cursor.lastrowid)


def get_file_metadata(file_id):
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, file_name, s3_key, file_size, file_type, status "
                "FROM files WHERE id = %s",
                (file_id,),
            )
            return cursor.fetchone()


def delete_file_metadata(file_id):
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM files WHERE id = %s", (file_id,))
            return cursor.rowcount > 0
