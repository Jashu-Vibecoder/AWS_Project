"""Shared JSON request and response helpers for API Gateway Lambda events."""

import base64
import json


def parse_json_body(event):
    body = event.get("body")
    if isinstance(body, dict):
        return body
    if not isinstance(body, str) or not body:
        raise ValueError("A JSON request body is required")
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body, validate=True).decode("utf-8")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("The JSON request body must be an object")
    return value


def json_response(status_code, message, data=None, error=None):
    body = {"success": error is None, "message": message}
    if error is None:
        body["data"] = data if data is not None else {}
    else:
        body["error"] = {"code": error}
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, separators=(",", ":")),
        "isBase64Encoded": False,
    }


def path_parameter(event, name):
    params = event.get("pathParameters") or {}
    return params.get(name)
