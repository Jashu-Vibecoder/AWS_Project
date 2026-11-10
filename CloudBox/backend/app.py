"""Flask application factory for the CloudBox metadata API."""

import logging

from flask import Flask, current_app, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from backend.config import Config
from backend.auth import authorization_error
from backend.database import DatabaseUnavailable
from backend.routes.dashboard import bp as dashboard_bp
from backend.routes.files import bp as files_bp
from backend.routes.health import bp as health_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ALLOWED_ORIGINS"]}},
        methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=600,
    )

    logging.basicConfig(level=logging.INFO)
    app.register_blueprint(health_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(files_bp)

    @app.before_request
    def protect_api_routes():
        if request.path.startswith("/api/"):
            return authorization_error()
        return None

    @app.errorhandler(DatabaseUnavailable)
    def database_unavailable(_error):
        current_app.logger.warning("Database request failed")
        return jsonify({
            "success": False,
            "message": "The database is unavailable",
            "error": {"code": "database_unavailable"},
        }), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify({
            "success": False,
            "message": error.description,
            "error": {"code": error.name.lower().replace(" ", "_")},
        }), error.code

    @app.errorhandler(Exception)
    def unexpected_error(_error):
        current_app.logger.exception("Unhandled API error")
        return jsonify({
            "success": False,
            "message": "An unexpected error occurred",
            "error": {"code": "internal_error"},
        }), 500

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=Config.DEBUG)
