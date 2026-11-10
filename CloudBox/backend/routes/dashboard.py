"""Dashboard summary endpoint."""

from flask import Blueprint, jsonify

from backend.services.file_service import get_dashboard_data


bp = Blueprint("dashboard", __name__)


@bp.get("/api/dashboard")
def dashboard():
    return jsonify({
        "success": True,
        "message": "Dashboard data retrieved",
        "data": get_dashboard_data(),
    })
