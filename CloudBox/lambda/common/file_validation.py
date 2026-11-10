"""Filename, MIME type, size, and upload-key validation helpers."""

import re
import uuid


MAX_FILE_SIZE = 25 * 1024 * 1024
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "zip": "application/zip",
}
_KEY_PATTERN = re.compile(r"^uploads/[0-9a-f]{32}$")


def validate_upload(body):
    raw_name = body.get("file_name")
    if not isinstance(raw_name, str) or not raw_name.strip() or len(raw_name) > 255:
        raise ValueError("Invalid filename")
    raw_name = raw_name.replace("\\", "/").rsplit("/", 1)[-1]
    file_name = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", raw_name).strip()
    if not file_name or file_name in {".", ".."}:
        raise ValueError("Invalid filename")

    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension not in CONTENT_TYPES:
        raise ValueError("Unsupported file type")

    content_type = CONTENT_TYPES[extension]
    requested_type = body.get("file_type")
    if requested_type not in (None, "", "application/octet-stream", content_type):
        raise ValueError("MIME type does not match filename")

    file_size = body.get("file_size")
    if isinstance(file_size, bool) or not isinstance(file_size, int) or not 0 <= file_size <= MAX_FILE_SIZE:
        raise ValueError("File size is outside the allowed range")
    return file_name, content_type, file_size


def validate_upload_key(value):
    return bool(_KEY_PATTERN.fullmatch(value)) if isinstance(value, str) else False


def make_upload_key():
    return f"uploads/{uuid.uuid4().hex}"
