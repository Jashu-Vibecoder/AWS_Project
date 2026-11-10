"""Write and lookup operations for file metadata.

These database operations are kept separate from Flask's read-only routes.
The upload/delete workflow can use them from the API Gateway/Lambda phase.
"""

from backend.database import database_connection


_ALLOWED_STATUSES = {"active", "deleted"}
_UPDATABLE_FIELDS = {"file_name", "file_size", "file_type", "status"}


def _validate_metadata(file_name, s3_key, file_size, file_type, status):
    if not isinstance(file_name, str) or not file_name.strip() or len(file_name) > 255:
        raise ValueError("file_name must contain 1 to 255 characters")
    if not isinstance(s3_key, str) or not s3_key.strip() or len(s3_key) > 500:
        raise ValueError("s3_key must contain 1 to 500 characters")
    if isinstance(file_size, bool) or not isinstance(file_size, int) or file_size < 0:
        raise ValueError("file_size must be a non-negative integer")
    if file_type is not None and (not isinstance(file_type, str) or len(file_type) > 100):
        raise ValueError("file_type must be 100 characters or fewer")
    if not isinstance(status, str) or status not in _ALLOWED_STATUSES:
        raise ValueError("status must be 'active' or 'deleted'")


def create_file_metadata(file_name, s3_key, file_size, file_type=None, status="active"):
    """Insert metadata once; a repeated S3 key returns its existing row id."""
    _validate_metadata(file_name, s3_key, file_size, file_type, status)
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO files (file_name, s3_key, file_size, file_type, status) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)",
                (file_name.strip(), s3_key, file_size, file_type, status),
            )
            return int(cursor.lastrowid)


def get_file_metadata(file_id):
    """Return one internal metadata row, including its S3 key, or None."""
    if isinstance(file_id, bool) or not isinstance(file_id, int) or file_id < 1:
        raise ValueError("file_id must be a positive integer")
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, file_name, s3_key, file_size, file_type, status, uploaded_at "
                "FROM files WHERE id = %s",
                (file_id,),
            )
            return cursor.fetchone()


def update_file_metadata(file_id, **changes):
    """Update validated metadata fields; return whether the row changed."""
    if isinstance(file_id, bool) or not isinstance(file_id, int) or file_id < 1:
        raise ValueError("file_id must be a positive integer")
    if not changes or not changes.keys() <= _UPDATABLE_FIELDS:
        raise ValueError("Provide one or more supported metadata fields")
    if "file_name" in changes:
        name = changes["file_name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 255:
            raise ValueError("file_name must contain 1 to 255 characters")
        changes["file_name"] = name.strip()
    if "file_size" in changes:
        size = changes["file_size"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("file_size must be a non-negative integer")
    if "file_type" in changes:
        mime_type = changes["file_type"]
        if mime_type is not None and (not isinstance(mime_type, str) or len(mime_type) > 100):
            raise ValueError("file_type must be 100 characters or fewer")
    if "status" in changes and (
        not isinstance(changes["status"], str) or changes["status"] not in _ALLOWED_STATUSES
    ):
        raise ValueError("status must be 'active' or 'deleted'")

    # Column names come only from the fixed allowlist; values remain parameterized.
    columns = list(changes)
    assignments = ", ".join(f"{column} = %s" for column in columns)
    values = tuple(changes[column] for column in columns) + (file_id,)
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE files SET {assignments} WHERE id = %s", values)
            return cursor.rowcount > 0


def delete_file_metadata(file_id):
    """Delete one metadata row; S3 object deletion is handled by its caller."""
    if isinstance(file_id, bool) or not isinstance(file_id, int) or file_id < 1:
        raise ValueError("file_id must be a positive integer")
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM files WHERE id = %s", (file_id,))
            return cursor.rowcount > 0
