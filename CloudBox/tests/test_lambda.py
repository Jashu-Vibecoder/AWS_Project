import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


LAMBDA_ROOT = str(Path(__file__).resolve().parents[1] / "lambda")
if LAMBDA_ROOT not in sys.path:
    sys.path.insert(0, LAMBDA_ROOT)

from confirm_upload import handler as confirm_upload  # noqa: E402
from delete_file import handler as delete_file  # noqa: E402
from download_url import handler as download_url  # noqa: E402
from upload_url import handler as upload_url  # noqa: E402


def body(response):
    return json.loads(response["body"])


class LambdaHandlerTests(unittest.TestCase):
    def test_upload_url_requires_bearer_token_when_auth_is_enabled(self):
        previous_required = os.environ.get("API_AUTH_REQUIRED")
        previous_token = os.environ.get("CLOUDBOX_API_TOKEN")
        os.environ["API_AUTH_REQUIRED"] = "true"
        os.environ["CLOUDBOX_API_TOKEN"] = "lambda-test-token"
        try:
            with patch.object(upload_url, "create_upload_url", return_value="https://signed.example") as sign:
                denied = upload_url.handler({"body": json.dumps({"file_name": "notes.txt", "file_size": 1})}, None)
                allowed = upload_url.handler({
                    "headers": {"authorization": "Bearer lambda-test-token"},
                    "body": json.dumps({"file_name": "notes.txt", "file_size": 1}),
                }, None)
            self.assertEqual(denied["statusCode"], 401)
            self.assertEqual(allowed["statusCode"], 200)
            sign.assert_called_once()
        finally:
            if previous_required is None:
                os.environ.pop("API_AUTH_REQUIRED", None)
            else:
                os.environ["API_AUTH_REQUIRED"] = previous_required
            if previous_token is None:
                os.environ.pop("CLOUDBOX_API_TOKEN", None)
            else:
                os.environ["CLOUDBOX_API_TOKEN"] = previous_token

    def test_all_file_operation_lambdas_require_bearer_token(self):
        previous_required = os.environ.get("API_AUTH_REQUIRED")
        previous_token = os.environ.get("CLOUDBOX_API_TOKEN")
        previous_secret_arn = os.environ.get("AUTH_TOKEN_SECRET_ARN")
        os.environ["API_AUTH_REQUIRED"] = "true"
        os.environ["CLOUDBOX_API_TOKEN"] = "lambda-test-token"
        os.environ.pop("AUTH_TOKEN_SECRET_ARN", None)
        try:
            handlers = [upload_url, confirm_upload, download_url, delete_file]
            responses = [module.handler({}, None) for module in handlers]
            self.assertEqual([response["statusCode"] for response in responses], [401] * 4)
        finally:
            if previous_required is None:
                os.environ.pop("API_AUTH_REQUIRED", None)
            else:
                os.environ["API_AUTH_REQUIRED"] = previous_required
            if previous_token is None:
                os.environ.pop("CLOUDBOX_API_TOKEN", None)
            else:
                os.environ["CLOUDBOX_API_TOKEN"] = previous_token
            if previous_secret_arn is None:
                os.environ.pop("AUTH_TOKEN_SECRET_ARN", None)
            else:
                os.environ["AUTH_TOKEN_SECRET_ARN"] = previous_secret_arn

    def test_upload_url_signs_expected_type_and_length(self):
        with patch.object(upload_url, "create_upload_url", return_value="https://signed.example") as sign:
            response = upload_url.handler({"body": json.dumps({
                "file_name": "notes.txt",
                "file_type": "text/plain",
                "file_size": 12,
            })}, None)

        self.assertEqual(response["statusCode"], 200)
        data = body(response)["data"]
        self.assertEqual(data["file_name"], "notes.txt")
        self.assertTrue(data["s3_key"].startswith("uploads/"))
        self.assertEqual(sign.call_args.args[1:], ("text/plain", 12))

    def test_upload_url_rejects_unsupported_or_oversized_file(self):
        with patch.object(upload_url, "create_upload_url") as sign:
            response = upload_url.handler({"body": json.dumps({
                "file_name": "program.exe", "file_size": 1,
            })}, None)
            mismatched_type = upload_url.handler({"body": json.dumps({
                "file_name": "notes.txt", "file_type": "image/png", "file_size": 1,
            })}, None)
            too_large = upload_url.handler({"body": json.dumps({
                "file_name": "notes.txt", "file_size": 25 * 1024 * 1024 + 1,
            })}, None)
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(mismatched_type["statusCode"], 400)
        self.assertEqual(too_large["statusCode"], 400)
        sign.assert_not_called()

    def test_upload_url_rejects_missing_and_blank_filename(self):
        with patch.object(upload_url, "create_upload_url") as sign:
            missing = upload_url.handler({"body": json.dumps({"file_size": 1})}, None)
            blank = upload_url.handler({"body": json.dumps({"file_name": "  ", "file_size": 1})}, None)
        self.assertEqual(missing["statusCode"], 400)
        self.assertEqual(blank["statusCode"], 400)
        sign.assert_not_called()

    def test_upload_url_returns_service_unavailable_if_signing_fails(self):
        with patch.object(upload_url, "create_upload_url", side_effect=RuntimeError("S3 unavailable")):
            response = upload_url.handler({"body": json.dumps({
                "file_name": "notes.txt", "file_size": 1,
            })}, None)
        self.assertEqual(response["statusCode"], 503)
        self.assertEqual(body(response)["error"]["code"], "service_unavailable")

    def test_upload_url_returns_opaque_key_and_rejects_invalid_json(self):
        with patch.object(upload_url, "create_upload_url", return_value="https://signed.example"):
            response = upload_url.handler({"body": "{"}, None)
            good = upload_url.handler({"body": json.dumps({"file_name": "notes.txt", "file_size": 1})}, None)
        self.assertEqual(response["statusCode"], 400)
        key = body(good)["data"]["s3_key"]
        self.assertRegex(key, r"^uploads/[0-9a-f]{32}$")

    @patch.object(confirm_upload, "insert_file_metadata", return_value=15)
    @patch.object(confirm_upload, "get_object_metadata", return_value={
        "ContentLength": 12, "ContentType": "text/plain",
    })
    def test_confirm_records_only_a_verified_s3_object(self, head, insert):
        key = f"uploads/{'a' * 32}"
        response = confirm_upload.handler({"body": json.dumps({
            "s3_key": key, "file_name": "notes.txt", "file_type": "text/plain", "file_size": 12,
        })}, None)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body(response)["data"]["id"], 15)
        head.assert_called_once_with(key)
        insert.assert_called_once_with("notes.txt", key, 12, "text/plain")

    @patch.object(confirm_upload, "insert_file_metadata")
    @patch.object(confirm_upload, "get_object_metadata", return_value={
        "ContentLength": 12, "ContentType": "text/plain",
    })
    def test_confirm_is_idempotent_for_the_same_object_key(self, _head, insert):
        insert.return_value = 15
        request = {"body": json.dumps({
            "s3_key": f"uploads/{'c' * 32}", "file_name": "notes.txt",
            "file_type": "text/plain", "file_size": 12,
        })}
        first = confirm_upload.handler(request, None)
        second = confirm_upload.handler(request, None)
        self.assertEqual(first["statusCode"], 200)
        self.assertEqual(second["statusCode"], 200)
        self.assertEqual(body(first)["data"]["id"], body(second)["data"]["id"])
        self.assertEqual(insert.call_count, 2)

    @patch.object(confirm_upload, "delete_object")
    @patch.object(confirm_upload, "insert_file_metadata")
    @patch.object(confirm_upload, "get_object_metadata", return_value={
        "ContentLength": 25 * 1024 * 1024 + 1, "ContentType": "text/plain",
    })
    def test_confirm_removes_invalid_oversized_object_without_metadata(self, _head, insert, remove):
        key = f"uploads/{'b' * 32}"
        response = confirm_upload.handler({"body": json.dumps({
            "s3_key": key, "file_name": "notes.txt", "file_type": "text/plain", "file_size": 12,
        })}, None)
        self.assertEqual(response["statusCode"], 400)
        remove.assert_called_once_with(key)
        insert.assert_not_called()

    @patch.object(confirm_upload, "get_object_metadata")
    def test_confirm_rejects_a_browser_chosen_object_key(self, head):
        response = confirm_upload.handler({"body": json.dumps({
            "s3_key": "uploads/another-user/private.txt",
            "file_name": "notes.txt",
            "file_type": "text/plain",
            "file_size": 12,
        })}, None)
        self.assertEqual(response["statusCode"], 400)
        head.assert_not_called()

    @patch.object(confirm_upload, "insert_file_metadata", side_effect=RuntimeError("db unavailable"))
    @patch.object(confirm_upload, "get_object_metadata", return_value={
        "ContentLength": 12, "ContentType": "text/plain",
    })
    def test_confirm_returns_service_unavailable_when_database_fails(self, _head, _insert):
        response = confirm_upload.handler({"body": json.dumps({
            "s3_key": f"uploads/{'d' * 32}", "file_name": "notes.txt",
            "file_type": "text/plain", "file_size": 12,
        })}, None)
        self.assertEqual(response["statusCode"], 503)
        self.assertEqual(body(response)["error"]["code"], "service_unavailable")

    @patch.object(confirm_upload, "insert_file_metadata")
    @patch.object(confirm_upload, "get_object_metadata", side_effect=type(
        "MissingObject", (Exception,), {"response": {"Error": {"Code": "NoSuchKey"}}}
    )())
    def test_confirm_rejects_missing_s3_object_without_database_write(self, _head, insert):
        response = confirm_upload.handler({"body": json.dumps({
            "s3_key": f"uploads/{'e' * 32}", "file_name": "notes.txt",
            "file_type": "text/plain", "file_size": 12,
        })}, None)
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body(response)["error"]["code"], "upload_not_found")
        insert.assert_not_called()

    @patch.object(download_url, "create_download_url", return_value="https://download.example")
    @patch.object(download_url, "get_file_metadata", return_value={
        "id": 2, "file_name": "notes.txt", "s3_key": "uploads/a/notes.txt", "status": "active",
    })
    def test_download_url_is_created_for_active_record(self, get_record, sign):
        with patch.object(download_url, "get_object_metadata", return_value={"ContentLength": 12}):
            response = download_url.handler({"pathParameters": {"id": "2"}}, None)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body(response)["data"]["download_url"], "https://download.example")
        get_record.assert_called_once_with(2)
        sign.assert_called_once_with("uploads/a/notes.txt", "notes.txt")

    @patch.object(download_url, "create_download_url")
    @patch.object(download_url, "get_file_metadata", return_value=None)
    def test_download_url_rejects_missing_metadata(self, _get_record, sign):
        response = download_url.handler({"pathParameters": {"id": "999"}}, None)
        self.assertEqual(response["statusCode"], 404)
        sign.assert_not_called()

    @patch.object(download_url, "create_download_url")
    @patch.object(download_url, "get_object_metadata", side_effect=type("MissingObject", (Exception,), {"response": {"Error": {"Code": "NoSuchKey"}}})())
    @patch.object(download_url, "get_file_metadata", return_value={
        "id": 2, "file_name": "notes.txt", "s3_key": "uploads/a", "status": "active",
    })
    def test_download_url_reports_missing_s3_object(self, _record, _head, sign):
        response = download_url.handler({"pathParameters": {"id": "2"}}, None)
        self.assertEqual(response["statusCode"], 404)
        sign.assert_not_called()

    @patch.object(delete_file, "delete_file_metadata", return_value=True)
    @patch.object(delete_file, "delete_object")
    @patch.object(delete_file, "get_file_metadata", return_value={
        "id": 2, "s3_key": "uploads/a/notes.txt", "status": "active",
    })
    def test_delete_removes_object_then_metadata(self, get_record, remove_object, remove_record):
        order = []
        remove_object.side_effect = lambda _key: order.append("s3")
        remove_record.side_effect = lambda _file_id: order.append("db") or True
        response = delete_file.handler({"pathParameters": {"id": "2"}}, None)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(order, ["s3", "db"])
        get_record.assert_called_once_with(2)

    @patch.object(delete_file, "delete_file_metadata", side_effect=[False, True])
    @patch.object(delete_file, "delete_object")
    @patch.object(delete_file, "get_file_metadata", return_value={
        "id": 2, "s3_key": "uploads/a", "status": "active",
    })
    def test_delete_retry_finishes_metadata_cleanup_after_s3_delete(self, _record, delete_object, delete_metadata):
        failed = delete_file.handler({"pathParameters": {"id": "2"}}, None)
        retried = delete_file.handler({"pathParameters": {"id": "2"}}, None)
        self.assertEqual(failed["statusCode"], 503)
        self.assertEqual(retried["statusCode"], 200)
        self.assertEqual(delete_object.call_count, 2)
        self.assertEqual(delete_metadata.call_count, 2)

    def test_invalid_file_ids_return_400(self):
        response = download_url.handler({"pathParameters": {"id": "-1"}}, None)
        self.assertEqual(response["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
