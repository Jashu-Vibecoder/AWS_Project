"""File listing and filename search endpoints."""

from flask import Blueprint, jsonify, request

from backend.services.file_service import list_files


bp = Blueprint("files", __name__)
MAX_PAGE_SIZE = 100
MAX_OFFSET = 100_000


def _parse_integer(name, default, minimum, maximum):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@bp.get("/api/files")
@bp.get("/api/files/search")
def files():
    search = request.args.get("q", "").strip()
    if len(search) > 255:
        return jsonify({
            "success": False,
            "message": "Search text must be 255 characters or fewer",
            "error": {"code": "invalid_search"},
        }), 400

    try:
        limit = _parse_integer("limit", 100, 1, MAX_PAGE_SIZE)
        offset = _parse_integer("offset", 0, 0, MAX_OFFSET)
    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc),
            "error": {"code": "invalid_pagination"},
        }), 400

    result = list_files(search=search, limit=limit, offset=offset)
    return jsonify({
        "success": True,
        "message": "Files retrieved",
        "data": {**result, "limit": limit, "offset": offset},
    })
