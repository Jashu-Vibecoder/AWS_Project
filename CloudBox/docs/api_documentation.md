# CloudBox API

All endpoints return JSON. Typical envelope:

```json
{"success": true, "message": "Files retrieved", "data": {}}
```

When bearer-token auth is enabled, send `Authorization: Bearer <token>` to Flask `/api/*` routes and every API Gateway route. Never put the token in a URL. Errors use `success: false`, `message`, and an `error.code`. Upload URL expiry is five minutes; download URL expiry is five minutes.

In deployment, `CloudFrontApiBaseUrl` is used for both APIs: CloudFront routes `/health`, `/api/*`, and file-operation paths to API Gateway; the HTTP API routes Flask paths through a private VPC Link and routes file operations to Lambda. Use the direct `ApiBaseUrl` only for local development or API diagnostics; API Gateway CORS allows configured localhost origins. Deployed browser calls use the same CloudFront origin.

## Flask metadata API

### `GET /health`

Checks the Flask process and database connection. No request body. Returns 200 with `{ "status": "ok", "database": "connected" }`, or 503 when MySQL/credentials are unavailable. It is intentionally not behind `/api/*` auth in the current implementation.

### `GET /api/dashboard`

Returns active file count, total bytes, distinct formats, a format breakdown, and up to five most recent files.

Example response data:

```json
{"total_files": 1, "total_storage": 12, "file_formats": 1, "formats": [{"file_type":"text/plain","file_count":1,"total_size":12}], "recent_uploads": [{"id":1,"file_name":"notes.txt","file_size":12,"file_type":"text/plain","uploaded_at":"2026-01-01T00:00:00Z"}]}
```

### `GET /api/files`

Query: optional `q` filename substring, `limit` 1–100 (default 100), `offset` 0–100000 (default 0). Search wildcards are escaped and SQL values are parameterized. Data includes `files`, `total`, `limit`, and `offset`. Invalid pagination or a search string longer than 255 chars returns 400.

### `GET /api/files/search?q=notes`

Search alias for `/api/files`; supports the same `limit` and `offset` parameters and response shape.

## API Gateway file operations

### `POST /upload-url`

Request JSON:

```json
{"file_name":"notes.txt","file_type":"text/plain","file_size":12}
```

Returns `upload_url`, opaque `s3_key`, the original display name without any client path components or control characters, validated type/size, `expires_in: 300`, method `PUT`, and required `Content-Type` header. Allowed types are configured in `lambda/common/file_validation.py`; maximum size is 25 MiB. Unsupported extensions, mismatched MIME type, invalid name/size, or malformed JSON return 400. The browser must send the returned content type and exact content length when using the presigned PUT. Download responses use an ASCII fallback plus a UTF-8 filename parameter so spaces and international characters are preserved.

### `POST /upload-confirm`

Request JSON:

```json
{"s3_key":"uploads/0123456789abcdef0123456789abcdef","file_name":"notes.txt","file_type":"text/plain","file_size":12}
```

Lambda accepts only generated UUID-shaped upload keys, verifies the S3 object's actual content type and size, then inserts metadata. Returns the database ID and normalized metadata. Invalid data returns 400; absent uploaded object returns 400; S3/database unavailability returns 503. The unique S3 key makes repeated confirmation idempotent.

### `GET /download-url/{id}`

Example: `GET /download-url/42`. Accepts a positive numeric database ID only. Returns a five-minute `download_url`, expiry, and original filename. Invalid ID is 400; absent/inactive row or S3 object is 404; service errors are 503. The client never chooses an arbitrary key.

### `DELETE /files/{id}`

Example: `DELETE /files/42`. Deletes the associated object, then metadata. Returns the deleted ID. Invalid ID is 400, missing/inactive record is 404, and service errors are 503. Retry is safe when S3 deletion succeeded but metadata deletion failed because S3 deletion is idempotent.

## Cross-origin requirements

Flask `CORS_ALLOWED_ORIGINS` must list the exact frontend origin for local development. File bucket CORS allows the two local development origins and the exact HTTPS CloudFront origin. Since that hostname is generated when CloudFront is created, `deploy_cloudbox.ps1` performs a follow-up stack update to set the origin after distribution creation; there is no CloudFront hostname wildcard. The rule allows only `PUT`, `GET`, and `HEAD`, the signed `Content-Type` header, and exposes `ETag`. The short-lived presigned URL authorizes S3 access; CORS is not an authorization control. API Gateway CORS permits the configured localhost origins; deployed browser requests use the same CloudFront origin. CORS is browser policy, not authentication.
