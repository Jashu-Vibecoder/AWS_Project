"""Create a short-lived, content-bound S3 upload URL."""

import logging
from common.auth import authorization_response
from common.file_validation import make_upload_key, validate_upload
from common.http_utils import json_response, parse_json_body
from common.s3_service import create_upload_url


logger = logging.getLogger(__name__)


def handler(event, _context):
    auth_error = authorization_response(event)
    if auth_error:
        return auth_error
    try:
        body = parse_json_body(event)
        file_name, content_type, file_size = validate_upload(body)
        s3_key = make_upload_key()
        url = create_upload_url(s3_key, content_type, file_size)
        return json_response(200, "Upload URL created", {
            "upload_url": url,
            "s3_key": s3_key,
            "file_name": file_name,
            "file_type": content_type,
            "file_size": file_size,
            "expires_in": 300,
            "method": "PUT",
            "required_headers": {"Content-Type": content_type},
        })
    except (ValueError, UnicodeDecodeError):
        return json_response(400, "Invalid upload request", error="invalid_request")
    except Exception:
        logger.exception("Could not create upload URL")
        return json_response(503, "Upload service is unavailable", error="service_unavailable")
