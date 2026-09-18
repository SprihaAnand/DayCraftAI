"""Local account authentication with salted password hashes.

This is suitable for a self-hosted single-instance deployment. For a public
internet deployment, put the same repository behind a managed identity service
or replace this service with an OIDC provider; the rest of the app only needs a
stable user id from the repository.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any

from services.database import Database

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PBKDF2_ITERATIONS = 600_000


class AuthenticationError(ValueError):
    """An expected, safe-to-display authentication error."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    email: str
    display_name: str

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> AuthenticatedUser:
        return cls(id=int(record["id"]), email=str(record["email"]), display_name=str(record["display_name"]))


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise AuthenticationError("Enter a valid email address.")
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 10:
        raise AuthenticationError("Use at least 10 characters for your password.")
    if password.lower() == password or password.upper() == password or not any(char.isdigit() for char in password):
        raise AuthenticationError("Use upper- and lower-case letters plus a number in your password.")


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256 and a unique random salt."""
    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_value), PBKDF2_ITERATIONS
    )
    return digest.hex(), salt_value


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    candidate, _ = hash_password(password, password_salt)
    return hmac.compare_digest(candidate, password_hash)


class AuthService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def register(self, email: str, display_name: str, password: str) -> AuthenticatedUser:
        normalized_email = normalize_email(email)
        clean_name = display_name.strip()
        if len(clean_name) < 2:
            raise AuthenticationError("Enter the name you would like DayCraft to use.")
        validate_password(password)
        password_hash, password_salt = hash_password(password)
        try:
            record = self.database.create_user(
                normalized_email, clean_name[:80], password_hash, password_salt
            )
        except sqlite3.IntegrityError as error:
            raise AuthenticationError("An account already exists for that email. Sign in instead.") from error
        return AuthenticatedUser.from_record(record)

    def authenticate(self, email: str, password: str) -> AuthenticatedUser:
        normalized_email = normalize_email(email)
        record = self.database.get_user_by_email(normalized_email)
        # Preserve a neutral failure message so user enumeration is not possible.
        if not record or not verify_password(password, record["password_hash"], record["password_salt"]):
            raise AuthenticationError("Email or password is incorrect.")
        self.database.update_last_login(int(record["id"]))
        return AuthenticatedUser.from_record(record)
