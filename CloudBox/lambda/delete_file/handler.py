"""Delete an active S3 object, then remove its metadata row."""

import logging

from common.auth import authorization_response
from common.database import delete_file_metadata, get_file_metadata
from common.http_utils import json_response, path_parameter
from common.s3_service import delete_object


logger = logging.getLogger(__name__)


def handler(event, _context):
    auth_error = authorization_response(event)
    if auth_error:
        return auth_error
    raw_id = path_parameter(event, "id")
    if not isinstance(raw_id, str) or not raw_id.isdigit() or int(raw_id) < 1:
        return json_response(400, "A positive file id is required", error="invalid_file_id")
    try:
        file_id = int(raw_id)
        record = get_file_metadata(file_id)
        if not record or record.get("status") != "active":
            return json_response(404, "File was not found", error="file_not_found")

        # S3 deletion is idempotent, so a retry can finish metadata cleanup if
        # the database operation fails after the object is removed.
        delete_object(record["s3_key"])
        if not delete_file_metadata(file_id):
            raise RuntimeError("File metadata disappeared during deletion")
        return json_response(200, "File deleted", {"id": file_id})
    except Exception:
        logger.exception("Could not delete file")
        return json_response(503, "File deletion is unavailable", error="service_unavailable")
