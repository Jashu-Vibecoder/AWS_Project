import unittest
from unittest.mock import MagicMock, patch

from backend.services import metadata_service
from backend.services import file_service
from backend.services.file_service import _file_filter, serialize_file


class FakeCursor:
    def __init__(self, result=None, lastrowid=1, rowcount=1):
        self.result = result
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.fake_cursor


class MetadataServiceTests(unittest.TestCase):
    def test_file_list_queries_rows_and_total_with_parameters(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchall.return_value = [{
            "id": 2,
            "file_name": "report.pdf",
            "s3_key": "private/report.pdf",
            "file_size": 128,
            "file_type": "application/pdf",
            "uploaded_at": "2026-01-01T00:00:00Z",
        }]
        cursor.fetchone.return_value = {"total": 1}
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value = cursor
        with patch.object(file_service, "database_connection", return_value=connection):
            result = file_service.list_files(search="report", limit=10, offset=5)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["files"][0]["file_name"], "report.pdf")
        self.assertNotIn("s3_key", result["files"][0])
        self.assertEqual(cursor.execute.call_args_list[0].args[1], ["active", "%report%", 10, 5])
        self.assertEqual(cursor.execute.call_args_list[1].args[1], ["active", "%report%"])

    def test_dashboard_queries_and_serializes_statistics(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = {"total_files": 1, "total_storage": 12, "file_formats": 1}
        cursor.fetchall.side_effect = [
            [{"file_type": "text/plain", "file_count": 1, "total_size": 12}],
            [{"id": 1, "file_name": "note.txt", "file_size": 12,
              "file_type": "text/plain", "uploaded_at": "2026-01-01T00:00:00Z"}],
        ]
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value = cursor
        with patch.object(file_service, "database_connection", return_value=connection):
            result = file_service.get_dashboard_data()

        self.assertEqual(result["total_storage"], 12)
        self.assertEqual(result["formats"][0]["file_count"], 1)
        self.assertEqual(result["recent_uploads"][0]["file_name"], "note.txt")
        self.assertEqual(cursor.execute.call_count, 3)

    def test_create_is_idempotent_for_duplicate_s3_key(self):
        cursor = FakeCursor(lastrowid=42)
        with patch.object(metadata_service, "database_connection") as connect:
            connect.return_value.__enter__.return_value = FakeConnection(cursor)
            file_id = metadata_service.create_file_metadata(
                " report.pdf ", "users/1/report.pdf", 99, "application/pdf"
            )

        self.assertEqual(file_id, 42)
        query, values = cursor.calls[0]
        self.assertIn("ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)", query)
        self.assertEqual(values, ("report.pdf", "users/1/report.pdf", 99, "application/pdf", "active"))
        self.assertNotIn("users/1/report.pdf", query)

    def test_create_rejects_invalid_metadata_before_database_access(self):
        with patch.object(metadata_service, "database_connection") as connect:
            with self.assertRaises(ValueError):
                metadata_service.create_file_metadata("", "key", -1)
        connect.assert_not_called()

    def test_search_wildcards_are_escaped_and_values_parameterized(self):
        where, params = _file_filter("100%_done\\today")
        self.assertIn("file_name LIKE %s", where)
        self.assertNotIn("100%_done", where)
        self.assertEqual(params, ["active", "%100\\%\\_done\\\\today%"])

    def test_search_sql_injection_payload_is_only_a_parameter_value(self):
        payload = "' OR 1=1 --"
        where, params = _file_filter(payload)
        self.assertNotIn(payload, where)
        self.assertIn("file_name LIKE %s", where)
        self.assertEqual(params, ["active", f"%{payload}%"])

    def test_public_file_serialization_does_not_expose_s3_key(self):
        public_file = serialize_file({
            "id": 1,
            "file_name": "private.txt",
            "s3_key": "private/user-1/private.txt",
            "file_size": 4,
            "file_type": "text/plain",
            "uploaded_at": "2026-01-01T00:00:00Z",
        })
        self.assertNotIn("s3_key", public_file)

    def test_get_uses_parameterized_id_and_returns_row(self):
        row = {"id": 7, "file_name": "a.txt", "s3_key": "private/a.txt"}
        cursor = FakeCursor(result=row)
        with patch.object(metadata_service, "database_connection") as connect:
            connect.return_value.__enter__.return_value = FakeConnection(cursor)
            result = metadata_service.get_file_metadata(7)
        self.assertEqual(result, row)
        self.assertEqual(cursor.calls[0][1], (7,))

    def test_update_allows_only_known_columns_and_parameterizes_values(self):
        cursor = FakeCursor(rowcount=1)
        with patch.object(metadata_service, "database_connection") as connect:
            connect.return_value.__enter__.return_value = FakeConnection(cursor)
            changed = metadata_service.update_file_metadata(9, file_name="new.txt", status="deleted")
        query, values = cursor.calls[0]
        self.assertTrue(changed)
        self.assertIn("UPDATE files SET file_name = %s, status = %s WHERE id = %s", query)
        self.assertEqual(values, ("new.txt", "deleted", 9))

    def test_update_rejects_untrusted_column_names(self):
        with patch.object(metadata_service, "database_connection") as connect:
            with self.assertRaises(ValueError):
                metadata_service.update_file_metadata(1, **{"s3_key = %s; DROP TABLE files; --": "x"})
        connect.assert_not_called()

    def test_delete_returns_false_when_no_row_was_deleted(self):
        cursor = FakeCursor(rowcount=0)
        with patch.object(metadata_service, "database_connection") as connect:
            connect.return_value.__enter__.return_value = FakeConnection(cursor)
            deleted = metadata_service.delete_file_metadata(404)
        self.assertFalse(deleted)
        self.assertEqual(cursor.calls[0], ("DELETE FROM files WHERE id = %s", (404,)))


if __name__ == "__main__":
    unittest.main()
