"""Google Gmail OAuth and deliberately explicit email delivery for DayCraft.

The service requests only Gmail's send scope. OAuth refresh tokens are encrypted
before persistence, and callers must invoke :meth:`send_message` with a complete
recipient, subject, and body for every delivery. DayCraft never reads a mailbox.
"""

from __future__ import annotations

import base64
import json
import os
import re
from email.message import EmailMessage
from email.utils import getaddresses
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from services.database import Database

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.send"
PROVIDER = "google_gmail"
MAX_RECIPIENTS = 25
MAX_SUBJECT_LENGTH = 200
MAX_BODY_LENGTH = 20_000

_EMAIL_PATTERN = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


class GmailError(RuntimeError):
    """An expected Gmail configuration or delivery error."""


class GmailService:
    """Authorize Gmail send-only access and deliver a user-confirmed message."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
        self.encryption_key = os.getenv("DAYCRAFT_ENCRYPTION_KEY", "").strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri and self.encryption_key)

    @property
    def configuration_message(self) -> str:
        if self.is_configured:
            return "Gmail is ready to connect. DayCraft will only request permission to send email."
        return (
            "Gmail setup is incomplete. Finish the shared Google OAuth and token-encryption setup "
            "in Settings, then restart DayCraft."
        )

    def _cipher(self) -> Fernet:
        if not self.encryption_key:
            raise GmailError("Gmail token encryption is not configured.")
        try:
            return Fernet(self.encryption_key.encode("utf-8"))
        except (TypeError, ValueError) as error:
            raise GmailError("DAYCRAFT_ENCRYPTION_KEY is not a valid Fernet key.") from error

    def _ensure_configured(self) -> None:
        if not self.is_configured:
            raise GmailError(self.configuration_message)

    def _flow(self):
        self._ensure_configured()
        try:
            from google_auth_oauthlib.flow import Flow
        except ImportError as error:
            raise GmailError("Install google-auth-oauthlib to enable Gmail.") from error
        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri],
            }
        }
        return Flow.from_client_config(client_config, scopes=[GMAIL_SCOPE], redirect_uri=self.redirect_uri)

    def authorization_url(self, user_id: int) -> str:
        """Create a one-time Gmail-specific state and its Google consent URL."""
        flow = self._flow()
        state = self.database.create_oauth_state(user_id, provider=PROVIDER)
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            state=state,
        )
        return authorization_url

    def complete_authorization(self, state: str, code: str, *, expected_user_id: int) -> int:
        """Exchange a callback only when it belongs to this user’s Gmail flow."""
        user_id = self.database.consume_oauth_state(
            state, expected_user_id=expected_user_id, expected_provider=PROVIDER
        )
        if user_id is None:
            raise GmailError(
                "This Gmail connection link expired or does not belong to the signed-in account. Start again."
            )
        try:
            flow = self._flow()
            flow.fetch_token(code=code)
            payload = flow.credentials.to_json().encode("utf-8")
            encrypted_payload = self._cipher().encrypt(payload).decode("utf-8")
            self.database.save_oauth_token(user_id, PROVIDER, encrypted_payload)
        except GmailError:
            raise
        except Exception as error:
            raise GmailError("Google did not complete the Gmail connection. Please try again.") from error
        return user_id

    def is_connected(self, user_id: int) -> bool:
        return self.database.get_oauth_token(user_id, PROVIDER) is not None

    def disconnect(self, user_id: int) -> None:
        self.database.delete_oauth_token(user_id, PROVIDER)

    def _credentials(self, user_id: int):
        encrypted_payload = self.database.get_oauth_token(user_id, PROVIDER)
        if not encrypted_payload:
            raise GmailError("Connect Gmail before sending email.")
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            payload = self._cipher().decrypt(encrypted_payload.encode("utf-8")).decode("utf-8")
            credentials = Credentials.from_authorized_user_info(
                _parse_json_payload(payload), scopes=[GMAIL_SCOPE]
            )
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                updated_payload = self._cipher().encrypt(credentials.to_json().encode("utf-8")).decode("utf-8")
                self.database.save_oauth_token(user_id, PROVIDER, updated_payload)
            if not credentials.valid:
                raise GmailError("Gmail access expired. Disconnect and connect again.")
            return credentials
        except GmailError:
            raise
        except InvalidToken as error:
            raise GmailError("Gmail token cannot be decrypted. Check the encryption key.") from error
        except Exception as error:
            raise GmailError("Gmail access expired. Disconnect and connect again.") from error

    def _api(self, user_id: int):
        try:
            from googleapiclient.discovery import build
        except ImportError as error:
            raise GmailError("Install google-api-python-client to enable Gmail.") from error
        return build("gmail", "v1", credentials=self._credentials(user_id), cache_discovery=False)

    def send_message(
        self, user_id: int, *, to: str | list[str] | tuple[str, ...], subject: str, body: str
    ) -> str:
        """Send one plain-text message through the connected user’s Gmail account.

        Inputs are validated before the Gmail client is instantiated. This keeps
        the operation intentional and blocks header-injection attempts.
        """
        recipients = normalize_recipients(to)
        clean_subject = _clean_subject(subject)
        clean_body = _clean_body(body)
        message = EmailMessage()
        message["To"] = ", ".join(recipients)
        message["Subject"] = clean_subject
        message.set_content(clean_body)
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        try:
            response = (
                self._api(user_id)
                .users()
                .messages()
                .send(userId="me", body={"raw": encoded_message})
                .execute()
            )
        except GmailError:
            raise
        except Exception as error:
            raise GmailError("Unable to send the Gmail message right now.") from error
        message_id = response.get("id") if isinstance(response, dict) else None
        if not message_id:
            raise GmailError("Gmail did not confirm the message delivery. Please try again.")
        return str(message_id)


def normalize_recipients(value: str | list[str] | tuple[str, ...]) -> list[str]:
    """Return unique, safe email addresses for a Gmail message header."""
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        raw_values = list(value)
    else:
        raise GmailError("Enter one or more valid recipient email addresses.")
    if not raw_values or any("\r" in item or "\n" in item for item in raw_values):
        raise GmailError("Enter one or more valid recipient email addresses.")

    recipients: list[str] = []
    seen: set[str] = set()
    for _, address in getaddresses(raw_values):
        if not _EMAIL_PATTERN.fullmatch(address) or len(address) > 320:
            raise GmailError("Enter one or more valid recipient email addresses.")
        canonical_address = address.casefold()
        if canonical_address not in seen:
            recipients.append(address)
            seen.add(canonical_address)
    if not recipients or len(recipients) > MAX_RECIPIENTS:
        raise GmailError(f"Enter between 1 and {MAX_RECIPIENTS} valid recipient email addresses.")
    return recipients


def _clean_subject(value: str) -> str:
    if not isinstance(value, str):
        raise GmailError("Add a subject before sending the email.")
    subject = value.strip()
    if not subject or len(subject) > MAX_SUBJECT_LENGTH or "\r" in subject or "\n" in subject:
        raise GmailError(f"Use a subject between 1 and {MAX_SUBJECT_LENGTH} characters.")
    return subject


def _clean_body(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_BODY_LENGTH:
        raise GmailError(f"Use an email message between 1 and {MAX_BODY_LENGTH} characters.")
    return value


def _parse_json_payload(payload: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("Invalid credential payload")
    return value
