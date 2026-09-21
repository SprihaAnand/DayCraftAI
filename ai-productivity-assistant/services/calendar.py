"""Google Calendar OAuth and sync service.

OAuth client secrets remain in environment variables and refresh tokens are
encrypted before they reach SQLite. The UI renders configuration guidance when
the optional integration has not been configured yet.
"""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from services.database import Database

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
PROVIDER = "google_calendar"


class CalendarError(RuntimeError):
    """An expected Calendar configuration or integration error."""


class CalendarService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
        self.encryption_key = os.getenv("DAYCRAFT_ENCRYPTION_KEY", "").strip()
        self.timezone_name = os.getenv("DAYCRAFT_TIMEZONE", "UTC").strip() or "UTC"

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri and self.encryption_key)

    @property
    def configuration_message(self) -> str:
        if self.is_configured:
            return "Calendar is ready to connect."
        return (
            "Google Calendar setup is incomplete. Open Settings → Connections to finish the OAuth and "
            "token-encryption setup, then restart DayCraft."
        )

    def _cipher(self) -> Fernet:
        if not self.encryption_key:
            raise CalendarError("Calendar token encryption is not configured.")
        try:
            return Fernet(self.encryption_key.encode("utf-8"))
        except (TypeError, ValueError) as error:
            raise CalendarError("DAYCRAFT_ENCRYPTION_KEY is not a valid Fernet key.") from error

    def _ensure_configured(self) -> None:
        if not self.is_configured:
            raise CalendarError(self.configuration_message)

    def _flow(self, *, code_verifier: str | None = None):
        self._ensure_configured()
        try:
            from google_auth_oauthlib.flow import Flow
        except ImportError as error:
            raise CalendarError("Install google-auth-oauthlib to enable Calendar.") from error
        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri],
            }
        }
        return Flow.from_client_config(
            client_config,
            scopes=[CALENDAR_SCOPE],
            redirect_uri=self.redirect_uri,
            code_verifier=code_verifier,
            autogenerate_code_verifier=False,
        )

    def authorization_url(self, user_id: int) -> str:
        """Create a one-time, database-backed OAuth state and authorization URL."""
        code_verifier = _new_pkce_verifier()
        flow = self._flow(code_verifier=code_verifier)
        state = self.database.create_oauth_state(
            user_id, provider=PROVIDER, code_verifier=code_verifier
        )
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        return authorization_url

    def complete_authorization(self, state: str, code: str, *, expected_user_id: int) -> int:
        """Exchange an OAuth callback only for the user who initiated it."""
        transaction = self.database.consume_oauth_transaction(
            state, expected_user_id=expected_user_id, expected_provider=PROVIDER
        )
        if transaction is None:
            raise CalendarError(
                "This Calendar connection link expired or does not belong to the signed-in account. Start again."
            )
        if not transaction.code_verifier:
            raise CalendarError("This Calendar connection link is incomplete. Start the connection again.")
        try:
            flow = self._flow(code_verifier=transaction.code_verifier)
            flow.fetch_token(code=code)
            payload = flow.credentials.to_json().encode("utf-8")
            encrypted_payload = self._cipher().encrypt(payload).decode("utf-8")
            self.database.save_oauth_token(transaction.user_id, PROVIDER, encrypted_payload)
        except CalendarError:
            raise
        except Exception as error:
            raise CalendarError("Google did not complete the Calendar connection. Please try again.") from error
        return transaction.user_id

    def is_connected(self, user_id: int) -> bool:
        return self.database.get_oauth_token(user_id, PROVIDER) is not None

    def disconnect(self, user_id: int) -> None:
        self.database.delete_oauth_token(user_id, PROVIDER)

    def _credentials(self, user_id: int):
        encrypted_payload = self.database.get_oauth_token(user_id, PROVIDER)
        if not encrypted_payload:
            raise CalendarError("Connect Google Calendar before syncing events.")
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            payload = self._cipher().decrypt(encrypted_payload.encode("utf-8")).decode("utf-8")
            credentials = Credentials.from_authorized_user_info(
                parse_json_payload(payload), scopes=[CALENDAR_SCOPE]
            )
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                updated_payload = self._cipher().encrypt(credentials.to_json().encode("utf-8")).decode("utf-8")
                self.database.save_oauth_token(user_id, PROVIDER, updated_payload)
            if not credentials.valid:
                raise CalendarError("Calendar access expired. Disconnect and connect again.")
            return credentials
        except CalendarError:
            raise
        except InvalidToken as error:
            raise CalendarError("Calendar token cannot be decrypted. Check the encryption key.") from error
        except Exception as error:
            raise CalendarError("Calendar access expired. Disconnect and connect again.") from error

    def _api(self, user_id: int):
        try:
            from googleapiclient.discovery import build
        except ImportError as error:
            raise CalendarError("Install google-api-python-client to enable Calendar.") from error
        return build("calendar", "v3", credentials=self._credentials(user_id), cache_discovery=False)

    def list_upcoming(self, user_id: int, max_results: int = 20) -> list[dict[str, Any]]:
        service = self._api(user_id)
        try:
            payload = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=datetime.now(UTC).isoformat(),
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception as error:
            raise CalendarError("Unable to read Google Calendar right now.") from error
        return [normalize_google_event(item) for item in payload.get("items", [])]

    def import_upcoming(self, user_id: int, max_results: int = 50) -> int:
        events = self.list_upcoming(user_id, max_results=max_results)
        for event in events:
            self.database.upsert_external_event(user_id, event)
        return len(events)

    def push_event(self, user_id: int, event: dict[str, Any]) -> str:
        """Create one local event in the connected user’s primary Google Calendar."""
        if event.get("external_id"):
            return str(event["external_id"])
        service = self._api(user_id)
        event_date = str(event["event_date"])
        body = {
            "summary": str(event["title"]),
            "location": str(event.get("location") or ""),
            "description": str(event.get("notes") or ""),
            "start": {
                "dateTime": f"{event_date}T{event['start_time']}:00",
                "timeZone": self.timezone_name,
            },
            "end": {
                "dateTime": f"{event_date}T{event['end_time']}:00",
                "timeZone": self.timezone_name,
            },
        }
        try:
            created = service.events().insert(calendarId="primary", body=body).execute()
        except Exception as error:
            raise CalendarError("Unable to create the Google Calendar event.") from error
        external_id = str(created["id"])
        self.database.update_event_external_id(user_id, int(event["id"]), external_id)
        return external_id


def parse_json_payload(payload: str) -> dict[str, Any]:
    """Parse an OAuth credential payload without importing app configuration."""
    import json

    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("Invalid credential payload")
    return value


def _new_pkce_verifier() -> str:
    """Create an RFC 7636 verifier retained only with the short-lived state."""
    return secrets.token_urlsafe(64)


def normalize_google_event(event: dict[str, Any]) -> dict[str, Any]:
    """Convert the Calendar API event object into DayCraft’s local event shape."""
    start = event.get("start", {})
    end = event.get("end", {})
    start_value = start.get("dateTime") or start.get("date")
    end_value = end.get("dateTime") or end.get("date")
    if not start_value or not end_value:
        raise CalendarError("Google returned an event without a start or end time.")
    is_all_day = "date" in start
    if is_all_day:
        event_date = str(start_value)
        start_time, end_time = "00:00", "23:59"
    else:
        start_dt = datetime.fromisoformat(str(start_value).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end_value).replace("Z", "+00:00"))
        event_date = start_dt.date().isoformat()
        start_time, end_time = start_dt.strftime("%H:%M"), end_dt.strftime("%H:%M")
    return {
        "external_id": str(event["id"]),
        "title": str(event.get("summary") or "Untitled event"),
        "event_date": event_date,
        "start_time": start_time,
        "end_time": end_time,
        "category": "All day" if is_all_day else "Calendar",
        "location": str(event.get("location") or ""),
        "notes": str(event.get("description") or ""),
    }
