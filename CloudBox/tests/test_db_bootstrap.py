import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


LAMBDA_ROOT = str(Path(__file__).resolve().parents[1] / "lambda")
if LAMBDA_ROOT not in sys.path:
    sys.path.insert(0, LAMBDA_ROOT)

from db_bootstrap import handler as db_bootstrap  # noqa: E402


def event(request_type="Create"):
    return {
        "RequestType": request_type,
        "ResponseURL": "https://response.example.invalid/",
        "StackId": "arn:aws:cloudformation:ap-southeast-2:123456789012:stack/test/id",
        "RequestId": "request-id",
        "LogicalResourceId": "DatabaseBootstrap",
        "ResourceProperties": {
            "DatabaseHost": "db.example.invalid",
            "DatabaseMasterSecretArn": "master-secret-arn",
            "DatabaseAppSecretArn": "app-secret-arn",
        },
    }


class DatabaseBootstrapTests(unittest.TestCase):
    def test_initializer_creates_schema_and_least_privilege_user(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        master = {"username": "cloudbox_master", "password": "master-test-value"}
        app = {"username": "cloudbox_app", "password": "app-test-value"}
        with patch.object(db_bootstrap, "_secret", side_effect=[master, app]) as get_secret, \
             patch.object(db_bootstrap, "_connect", return_value=connection) as connect:
            db_bootstrap._initialize_database(event()["ResourceProperties"])

        connect.assert_called_once_with("db.example.invalid", "cloudbox_master", "master-test-value")
        self.assertIn("master-secret-arn", [item.args[0] for item in get_secret.call_args_list])
        self.assertIn("app-secret-arn", [item.args[0] for item in get_secret.call_args_list])
        statements = [item.args[0] for item in cursor.execute.call_args_list]
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS cloudbox_db.files" in sql for sql in statements))
        self.assertIn("CREATE USER IF NOT EXISTS 'cloudbox_app'@'%' IDENTIFIED BY %s", statements)
        self.assertIn("ALTER USER 'cloudbox_app'@'%' IDENTIFIED BY %s", statements)
        self.assertIn(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON cloudbox_db.files TO 'cloudbox_app'@'%'",
            statements,
        )
        connection.close.assert_called_once_with()

    def test_handler_returns_cloudformation_response_without_secret_data(self):
        response = MagicMock()
        response.status = 200
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)
        with patch.object(db_bootstrap, "_initialize_database") as initialize, \
             patch.object(db_bootstrap, "urlopen", return_value=response) as send:
            db_bootstrap.handler(event(), None)

        initialize.assert_called_once()
        request = send.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["Status"], "SUCCESS")
        self.assertTrue(payload["NoEcho"])
        self.assertNotIn("password", json.dumps(payload).lower())

    def test_delete_retains_database_data_and_does_not_connect(self):
        response = MagicMock()
        response.status = 200
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)
        with patch.object(db_bootstrap, "_initialize_database") as initialize, \
             patch.object(db_bootstrap, "urlopen", return_value=response) as send:
            db_bootstrap.handler(event("Delete"), None)
        initialize.assert_not_called()
        payload = json.loads(send.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["Status"], "SUCCESS")
        self.assertEqual(payload["Reason"], "Database data retained")


if __name__ == "__main__":
    unittest.main()
