"""Bearer-token check shared by API Gateway Lambda handlers."""

import hmac
import os

from common.http_utils import json_response
from common.secrets import get_secret

_CACHED_TOKEN = None
_CACHED_SECRET_ARN = None


def _expected_token():
    global _CACHED_TOKEN, _CACHED_SECRET_ARN
    token = os.getenv("CLOUDBOX_API_TOKEN", "")
    if token:
        return token
    secret_arn = os.getenv("AUTH_TOKEN_SECRET_ARN", "")
    if not secret_arn:
        return ""
    if _CACHED_SECRET_ARN == secret_arn and _CACHED_TOKEN is not None:
        return _CACHED_TOKEN
    secret = get_secret(secret_arn)
    token = secret.get("token", "") if isinstance(secret, dict) else secret
    _CACHED_SECRET_ARN = secret_arn
    _CACHED_TOKEN = str(token or "")
    return _CACHED_TOKEN


def authorization_response(event):
    required = os.getenv("API_AUTH_REQUIRED", "false").strip().lower() == "true"
    configured = bool(os.getenv("CLOUDBOX_API_TOKEN") or os.getenv("AUTH_TOKEN_SECRET_ARN"))
    if not required and not configured:
        return None
    try:
        expected = _expected_token()
    except Exception:
        return json_response(503, "Authentication is temporarily unavailable", error="auth_unavailable")
    if not expected:
        return json_response(503, "API authentication is not configured", error="auth_not_configured")
    headers = {str(key).lower(): value for key, value in (event.get("headers") or {}).items()}
    scheme, _, supplied = str(headers.get("authorization", "")).partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(supplied, expected):
        return json_response(401, "A valid bearer token is required", error="unauthorized")
    return None
