"""Verify an uploaded S3 object before recording its metadata."""

import logging
from common.auth import authorization_response
from common.database import insert_file_metadata
from common.file_validation import MAX_FILE_SIZE, validate_upload, validate_upload_key
from common.http_utils import json_response, parse_json_body
from common.s3_service import delete_object, get_object_metadata


logger = logging.getLogger(__name__)
def handler(event, _context):
    auth_error = authorization_response(event)
    if auth_error:
        return auth_error
    try:
        body = parse_json_body(event)
        s3_key = body.get("s3_key")
        if not validate_upload_key(s3_key):
            raise ValueError("Invalid upload key")

        file_name, expected_type, expected_size = validate_upload({
            "file_name": body.get("file_name"),
            "file_type": body.get("file_type"),
            "file_size": body.get("file_size"),
        })

        metadata = get_object_metadata(s3_key)
        file_size = metadata.get("ContentLength")
        file_type = metadata.get("ContentType")
        if (
            isinstance(file_size, bool)
            or not isinstance(file_size, int)
            or file_size < 0
            or file_size > MAX_FILE_SIZE
            or file_size != expected_size
            or file_type != expected_type
        ):
            delete_object(s3_key)
            return json_response(400, "Uploaded object failed validation", error="invalid_upload")

        file_id = insert_file_metadata(file_name, s3_key, file_size, file_type)
        return json_response(200, "Upload confirmed", {
            "id": file_id,
            "file_name": file_name,
            "file_size": file_size,
            "file_type": file_type,
        })
    except (ValueError, UnicodeDecodeError):
        return json_response(400, "Invalid confirmation request", error="invalid_request")
    except Exception as exc:
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return json_response(400, "Uploaded object was not found", error="upload_not_found")
        logger.exception("Could not confirm uploaded object")
        return json_response(503, "Upload confirmation is unavailable", error="service_unavailable")
