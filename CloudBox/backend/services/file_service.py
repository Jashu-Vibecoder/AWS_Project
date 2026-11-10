"""Read-only file metadata queries used by the Flask API."""

from datetime import datetime, timezone

from backend.database import database_connection


ACTIVE_STATUS = "active"


def serialize_file(record):
    """Return public metadata fields without exposing the internal S3 key."""
    uploaded_at = record["uploaded_at"]
    if isinstance(uploaded_at, datetime):
        if uploaded_at.tzinfo is None:
            uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
        uploaded_at = uploaded_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "id": int(record["id"]),
        "file_name": record["file_name"],
        "file_size": int(record["file_size"]),
        "file_type": record.get("file_type") or "application/octet-stream",
        "uploaded_at": uploaded_at,
    }


def _file_filter(search):
    clauses = ["status = %s"]
    params = [ACTIVE_STATUS]
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("file_name LIKE %s ESCAPE '\\\\'")
        params.append(f"%{escaped}%")
    return " AND ".join(clauses), params


def list_files(search="", limit=100, offset=0):
    """Return an ordered page and matching count using parameterized SQL."""
    where_sql, params = _file_filter(search)
    fields = "id, file_name, file_size, file_type, uploaded_at"
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {fields} FROM files WHERE {where_sql} "
                "ORDER BY uploaded_at DESC, id DESC LIMIT %s OFFSET %s",
                [*params, limit, offset],
            )
            records = cursor.fetchall()
            cursor.execute(f"SELECT COUNT(*) AS total FROM files WHERE {where_sql}", params)
            total = cursor.fetchone()["total"]

    return {"files": [serialize_file(record) for record in records], "total": int(total)}


def get_dashboard_data():
    """Return file totals, format breakdown, and recent uploads."""
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS total_files, "
                "COALESCE(SUM(file_size), 0) AS total_storage, "
                "COUNT(DISTINCT COALESCE(file_type, 'application/octet-stream')) AS file_formats "
                "FROM files WHERE status = %s",
                (ACTIVE_STATUS,),
            )
            summary = cursor.fetchone()
            cursor.execute(
                "SELECT COALESCE(file_type, 'application/octet-stream') AS file_type, "
                "COUNT(*) AS file_count, COALESCE(SUM(file_size), 0) AS total_size "
                "FROM files WHERE status = %s "
                "GROUP BY COALESCE(file_type, 'application/octet-stream') "
                "ORDER BY file_count DESC, file_type ASC",
                (ACTIVE_STATUS,),
            )
            formats = cursor.fetchall()
            cursor.execute(
                "SELECT id, file_name, file_size, file_type, uploaded_at FROM files "
                "WHERE status = %s ORDER BY uploaded_at DESC, id DESC LIMIT %s",
                (ACTIVE_STATUS, 5),
            )
            recent = cursor.fetchall()

    return {
        "total_files": int(summary["total_files"]),
        "total_storage": int(summary["total_storage"]),
        "file_formats": int(summary["file_formats"]),
        "formats": [
            {
                "file_type": item["file_type"],
                "file_count": int(item["file_count"]),
                "total_size": int(item["total_size"]),
            }
            for item in formats
        ],
        "recent_uploads": [serialize_file(record) for record in recent],
    }
