import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


LAMBDA_ROOT = str(Path(__file__).resolve().parents[1] / "lambda")
if LAMBDA_ROOT not in sys.path:
    sys.path.insert(0, LAMBDA_ROOT)

from common import s3_service  # noqa: E402


class S3ServiceTests(unittest.TestCase):
    @patch.object(s3_service, "_client")
    def test_upload_url_signs_content_type_and_exact_length(self, client_factory):
        client = client_factory.return_value
        client.generate_presigned_url.return_value = "https://signed.example"
        with patch.dict(os.environ, {"S3_BUCKET_NAME": "cloudbox-files"}):
            result = s3_service.create_upload_url("uploads/generated-key", "text/plain", 12)

        self.assertEqual(result, "https://signed.example")
        client.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={
                "Bucket": "cloudbox-files",
                "Key": "uploads/generated-key",
                "ContentType": "text/plain",
                "ContentLength": 12,
            },
            ExpiresIn=300,
            HttpMethod="PUT",
        )

    @patch.object(s3_service, "_client")
    def test_download_url_preserves_unicode_filename_safely(self, client_factory):
        client = client_factory.return_value
        client.generate_presigned_url.return_value = "https://signed.example"
        file_name = "R\u00e9sum\u00e9 final \"draft\".pdf"
        with patch.dict(os.environ, {"S3_BUCKET_NAME": "cloudbox-files"}):
            result = s3_service.create_download_url("uploads/generated-key", file_name)

        self.assertEqual(result, "https://signed.example")
        disposition = client.generate_presigned_url.call_args.kwargs["Params"]["ResponseContentDisposition"]
        self.assertIn('filename="R_sum__final__draft_.pdf"', disposition)
        self.assertIn("filename*=UTF-8''R%C3%A9sum%C3%A9%20final%20%22draft%22.pdf", disposition)
        self.assertNotIn("\r", disposition)
        self.assertNotIn("\n", disposition)


if __name__ == "__main__":
    unittest.main()
