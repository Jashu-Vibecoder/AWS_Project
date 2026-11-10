import unittest
from unittest.mock import patch

from backend.app import create_app
from backend.database import DatabaseUnavailable


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    @patch("backend.routes.health.check_database_connection")
    def test_health_returns_success_when_database_is_available(self, check_db):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"]["database"], "connected")
        check_db.assert_called_once_with()

    @patch("backend.routes.dashboard.get_dashboard_data")
    def test_dashboard_returns_service_data(self, get_dashboard):
        get_dashboard.return_value = {"total_files": 3, "total_storage": 896}
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"]["total_files"], 3)

    @patch("backend.routes.files.list_files")
    def test_file_list_and_search_pass_search_and_pagination(self, list_files):
        list_files.return_value = {"files": [], "total": 0}
        response = self.client.get("/api/files/search?q=quarterly&limit=12&offset=24")
        self.assertEqual(response.status_code, 200)
        list_files.assert_called_once_with(search="quarterly", limit=12, offset=24)
        self.assertEqual(response.json["data"]["limit"], 12)

    @patch("backend.routes.files.list_files")
    def test_file_search_rejects_invalid_pagination_without_query(self, list_files):
        response = self.client.get("/api/files?limit=1000")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "invalid_pagination")
        list_files.assert_not_called()

    @patch("backend.routes.files.list_files")
    def test_file_search_rejects_overlong_query(self, list_files):
        response = self.client.get("/api/files", query_string={"q": "x" * 256})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "invalid_search")
        list_files.assert_not_called()

    @patch("backend.routes.health.check_database_connection", side_effect=DatabaseUnavailable())
    def test_database_failure_is_reported_without_internal_details(self, _check_db):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"]["code"], "database_unavailable")
        self.assertNotIn("password", response.get_data(as_text=True).lower())

    def test_cors_allows_configured_local_frontend_origin(self):
        response = self.client.options(
            "/api/files",
            headers={
                "Origin": "http://localhost:5500",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://localhost:5500")

    def test_cors_does_not_allow_unconfigured_origin(self):
        response = self.client.get("/api/files", headers={"Origin": "https://untrusted.example"})
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_api_routes_require_a_configured_bearer_token(self):
        app = create_app({
            "TESTING": True,
            "API_AUTH_REQUIRED": True,
            "CLOUDBOX_API_TOKEN": "local-test-token",
        })
        client = app.test_client()
        denied = client.get("/api/files")
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(denied.json["error"]["code"], "unauthorized")

        with patch("backend.routes.files.list_files", return_value={"files": [], "total": 0}):
            allowed = client.get("/api/files", headers={"Authorization": "Bearer local-test-token"})
        self.assertEqual(allowed.status_code, 200)

    def test_health_check_remains_available_when_api_auth_is_required(self):
        app = create_app({
            "TESTING": True,
            "API_AUTH_REQUIRED": True,
            "CLOUDBOX_API_TOKEN": "local-test-token",
        })
        with patch("backend.routes.health.check_database_connection"):
            response = app.test_client().get("/health")
        self.assertEqual(response.status_code, 200)

    def test_unknown_route_uses_json_error_shape(self):
        response = self.client.get("/not-a-route")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json["success"])
        self.assertIn("error", response.json)


if __name__ == "__main__":
    unittest.main()
