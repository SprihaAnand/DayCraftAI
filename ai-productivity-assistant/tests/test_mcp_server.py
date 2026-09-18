from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_server import _validated_local_event, _validated_priority, _workspace, build_server
from services.auth import AuthService
from services.database import Database


class MCPServerTests(unittest.TestCase):
    def test_workspace_is_scoped_by_environment_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "mcp.db"
            database = Database(database_path)
            database.initialize()
            user = AuthService(database).register("ava@example.com", "Ava", "StrongPass123")
            with patch.dict(
                os.environ,
                {
                    "DAYCRAFT_DATABASE_PATH": str(database_path),
                    "DAYCRAFT_MCP_USER_EMAIL": "ava@example.com",
                },
                clear=False,
            ):
                scoped_database, scoped_user = _workspace()
                self.assertEqual(scoped_user["id"], user.id)
                self.assertEqual(scoped_database.path, database_path.resolve())

    def test_priority_validation_rejects_unexpected_values(self) -> None:
        self.assertEqual(_validated_priority("high"), "High")
        with self.assertRaises(ValueError):
            _validated_priority("urgent")

    def test_mcp_calendar_event_validation_prevents_invalid_or_overnight_ranges(self) -> None:
        event = _validated_local_event(
            "Protected writing",
            "2026-09-18",
            "09:00",
            "10:30",
            "Deep work",
            "Finish the opening section.",
        )
        self.assertEqual(event[0], "Protected writing")
        self.assertEqual(event[2:4], ("09:00", "10:30"))
        with self.assertRaises(ValueError):
            _validated_local_event("Bad range", "2026-09-18", "11:00", "10:30", "General", "")

    def test_mcp_server_builds_with_google_calendar_and_gmail_tools_available(self) -> None:
        self.assertIsNotNone(build_server())


if __name__ == "__main__":
    unittest.main()
