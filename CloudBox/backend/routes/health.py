"""Application and database health endpoint."""

from flask import Blueprint, jsonify

from backend.database import check_database_connection


bp = Blueprint("health", __name__)


@bp.get("/health")
def health_check():
    check_database_connection()
    return jsonify({
        "success": True,
        "message": "Service is healthy",
        "data": {"status": "ok", "database": "connected"},
    })
