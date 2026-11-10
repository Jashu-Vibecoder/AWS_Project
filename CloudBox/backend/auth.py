"""Optional bearer-token gate for the single-user demonstration deployment."""

import hmac

from flask import current_app, jsonify, request

from backend.secrets import get_secret


def _expected_token(config):
    token = config.get("CLOUDBOX_API_TOKEN")
    if token:
        return str(token)
    secret_arn = config.get("AUTH_TOKEN_SECRET_ARN")
    if not secret_arn:
        return ""
    secret = get_secret(secret_arn, config.get("AWS_REGION"))
    if isinstance(secret, dict):
        return str(secret.get("token", ""))
    return str(secret or "")


def authorization_error():
    config = current_app.config
    token_is_configured = bool(config.get("CLOUDBOX_API_TOKEN") or config.get("AUTH_TOKEN_SECRET_ARN"))
    if not config.get("API_AUTH_REQUIRED") and not token_is_configured:
        return None

    try:
        expected = _expected_token(config)
    except Exception:
        current_app.logger.warning("API authentication secret could not be loaded")
        return jsonify({"success": False, "message": "Authentication is temporarily unavailable", "error": {"code": "auth_unavailable"}}), 503
    if not expected:
        return jsonify({"success": False, "message": "API authentication is not configured", "error": {"code": "auth_not_configured"}}), 503

    supplied = request.headers.get("Authorization", "")
    scheme, _, value = supplied.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(value, expected):
        return jsonify({"success": False, "message": "A valid bearer token is required", "error": {"code": "unauthorized"}}), 401
    return None


