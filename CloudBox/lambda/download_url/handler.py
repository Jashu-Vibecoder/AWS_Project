"""Create a short-lived download URL for an active metadata record."""

import logging

from common.auth import authorization_response
from common.database import get_file_metadata
from common.http_utils import json_response, path_parameter
from common.s3_service import create_download_url, get_object_metadata


logger = logging.getLogger(__name__)


def handler(event, _context):
    auth_error = authorization_response(event)
    if auth_error:
        return auth_error
    raw_id = path_parameter(event, "id")
    if not isinstance(raw_id, str) or not raw_id.isdigit() or int(raw_id) < 1:
        return json_response(400, "A positive file id is required", error="invalid_file_id")
    try:
        record = get_file_metadata(int(raw_id))
        if not record or record.get("status") != "active":
            return json_response(404, "File was not found", error="file_not_found")
        get_object_metadata(record["s3_key"])
        url = create_download_url(record["s3_key"], record["file_name"])
        return json_response(200, "Download URL created", {
            "download_url": url,
            "expires_in": 300,
            "file_name": record["file_name"],
        })
    except Exception as exc:
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return json_response(404, "Stored file was not found", error="file_not_found")
        logger.exception("Could not create download URL")
        return json_response(503, "Download service is unavailable", error="service_unavailable")
