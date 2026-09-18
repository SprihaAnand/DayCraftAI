from __future__ import annotations

import base64
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from services.calendar import PROVIDER as CALENDAR_PROVIDER
from services.calendar import CalendarService
from services.database import Database
from services.gmail import PROVIDER as GMAIL_PROVIDER
from services.gmail import GmailError, GmailService


class _Credentials:
    def to_json(self) -> str:
        return json.dumps({"token": "test-access-token", "refresh_token": "test-refresh-token"})


class _Flow:
    def __init__(self) -> None:
        self.credentials = _Credentials()
        self.authorization_state: str | None = None
        self.authorization_kwargs: dict[str, object] | None = None
        self.code: str | None = None

    def authorization_url(self, **kwargs: object) -> tuple[str, str]:
        self.authorization_kwargs = kwargs
        self.authorization_state = str(kwargs["state"])
        return "https://accounts.google.test/consent", self.authorization_state

    def fetch_token(self, *, code: str) -> None:
        self.code = code


class _GmailApi:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def users(self) -> _GmailApi:
        return self

    def messages(self) -> _GmailApi:
        return self

    def send(self, **kwargs: object) -> _GmailApi:
        self.request = kwargs
        return self

    def execute(self) -> dict[str, str]:
        return {"id": "gmail-message-123"}


class GmailAndGoogleOAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temporary_directory.name) / "daycraft-test.db")
        self.database.initialize()
        self.user = self.database.create_user("ava@example.com", "Ava", "hash", "salt")
        self.environment = patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "client-id",
                "GOOGLE_CLIENT_SECRET": "client-secret",
                "GOOGLE_REDIRECT_URI": "http://localhost:8501",
                "DAYCRAFT_ENCRYPTION_KEY": Fernet.generate_key().decode("utf-8"),
            },
            clear=False,
        )
        self.environment.start()
        self.gmail = GmailService(self.database)

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_initialize_migrates_existing_calendar_oauth_states(self) -> None:
        state = "legacy-calendar-state"
        expires_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        connection = sqlite3.connect(self.database.path)
        try:
            connection.execute("DROP TABLE oauth_states")
            connection.execute(
                """
                CREATE TABLE oauth_states (
                    state TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO oauth_states (state, user_id, expires_at) VALUES (?, ?, ?)",
                (state, self.user["id"], expires_at),
            )
            connection.commit()
        finally:
            connection.close()
        self.database.initialize()

        connection = sqlite3.connect(self.database.path)
        try:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(oauth_states)")]
        finally:
            connection.close()
        self.assertIn("provider", columns)
        self.assertEqual(
            self.database.oauth_state_provider(state, expected_user_id=self.user["id"]),
            "google_calendar",
        )

    def test_gmail_state_is_provider_bound_and_single_use(self) -> None:
        state = self.database.create_oauth_state(self.user["id"], provider=GMAIL_PROVIDER)

        self.assertEqual(
            self.database.oauth_state_provider(state, expected_user_id=self.user["id"]), GMAIL_PROVIDER
        )
        self.assertIsNone(
            self.database.consume_oauth_state(
                state, expected_user_id=self.user["id"], expected_provider="google_calendar"
            )
        )
        self.assertIsNone(self.database.consume_oauth_state(state, expected_user_id=self.user["id"]))

    def test_calendar_authorization_url_remains_calendar_bound(self) -> None:
        calendar = CalendarService(self.database)
        flow = _Flow()
        with patch.object(calendar, "_flow", return_value=flow):
            authorization_url = calendar.authorization_url(self.user["id"])

        self.assertEqual(authorization_url, "https://accounts.google.test/consent")
        self.assertEqual(
            self.database.oauth_state_provider(flow.authorization_state or "", self.user["id"]),
            CALENDAR_PROVIDER,
        )

    def test_gmail_authorization_url_and_callback_store_an_encrypted_token(self) -> None:
        flow = _Flow()
        with patch.object(self.gmail, "_flow", return_value=flow):
            authorization_url = self.gmail.authorization_url(self.user["id"])
        self.assertEqual(authorization_url, "https://accounts.google.test/consent")
        self.assertIsNotNone(flow.authorization_state)
        self.assertEqual(
            self.database.oauth_state_provider(flow.authorization_state or "", self.user["id"]),
            GMAIL_PROVIDER,
        )

        with patch.object(self.gmail, "_flow", return_value=flow):
            completed_user_id = self.gmail.complete_authorization(
                flow.authorization_state or "", "authorization-code", expected_user_id=self.user["id"]
            )
        encrypted_token = self.database.get_oauth_token(self.user["id"], GMAIL_PROVIDER)
        self.assertEqual(completed_user_id, self.user["id"])
        self.assertEqual(flow.code, "authorization-code")
        self.assertIsNotNone(encrypted_token)
        self.assertNotIn("test-access-token", encrypted_token or "")
        decrypted = self.gmail._cipher().decrypt((encrypted_token or "").encode("utf-8"))
        self.assertEqual(json.loads(decrypted.decode("utf-8"))["token"], "test-access-token")

    def test_gmail_sends_a_validated_plain_text_message(self) -> None:
        gmail_api = _GmailApi()
        with patch.object(self.gmail, "_api", return_value=gmail_api):
            message_id = self.gmail.send_message(
                self.user["id"],
                to=["Ava <ava@example.com>", "ben@example.com", "AVA@example.com"],
                subject="DayCraft plan",
                body="Your focus block starts at 09:00.",
            )

        self.assertEqual(message_id, "gmail-message-123")
        request = gmail_api.request or {}
        self.assertEqual(request["userId"], "me")
        raw = (request["body"] or {})["raw"]  # type: ignore[index]
        rendered_message = base64.urlsafe_b64decode(str(raw).encode("ascii")).decode("utf-8")
        self.assertIn("To: ava@example.com, ben@example.com", rendered_message)
        self.assertIn("Subject: DayCraft plan", rendered_message)
        self.assertIn("Your focus block starts at 09:00.", rendered_message)

    def test_gmail_rejects_header_injection_before_calling_google(self) -> None:
        with patch.object(self.gmail, "_api") as api:
            with self.assertRaisesRegex(GmailError, "valid recipient"):
                self.gmail.send_message(
                    self.user["id"],
                    to="ava@example.com\r\nBcc: attacker@example.com",
                    subject="Hello",
                    body="Safe body",
                )
        api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
