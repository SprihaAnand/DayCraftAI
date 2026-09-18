"""SQLite persistence for DayCraft.

The repository intentionally keeps the data-access layer independent of
Streamlit. That makes returning-user data durable and keeps it straightforward
to replace SQLite with a managed database when deploying at larger scale.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _as_iso_date(value: date | str | None) -> str | None:
    if value is None or value == "":
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


class Database:
    """Small repository layer with parameterized queries and per-user scoping."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured_path = os.getenv("DAYCRAFT_DATABASE_PATH")
        default_path = Path(__file__).resolve().parents[1] / "data" / "daycraft.db"
        self.path = Path(path or configured_path or default_path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _record(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def initialize(self) -> None:
        """Create all tables and indexes. Safe to call on every application start."""
        schema = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            due_date TEXT,
            priority TEXT NOT NULL DEFAULT 'Medium',
            category TEXT NOT NULL DEFAULT 'General',
            estimated_minutes INTEGER NOT NULL DEFAULT 30 CHECK (estimated_minutes > 0),
            status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'completed')),
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            location TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            is_fixed INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'manual',
            external_id TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, external_id)
        );

        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
            completed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS check_ins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            entry_date TEXT NOT NULL,
            energy INTEGER NOT NULL CHECK (energy BETWEEN 1 AND 10),
            focus INTEGER NOT NULL CHECK (focus BETWEEN 1 AND 10),
            satisfaction INTEGER NOT NULL CHECK (satisfaction BETWEEN 1 AND 10),
            stress INTEGER NOT NULL CHECK (stress BETWEEN 1 AND 10),
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(user_id, entry_date)
        );

        CREATE TABLE IF NOT EXISTS generated_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_type TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS oauth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            encrypted_payload TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, provider)
        );

        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL DEFAULT 'google_calendar',
            expires_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_tasks_user_due_date ON tasks(user_id, due_date);
        CREATE INDEX IF NOT EXISTS idx_events_user_date ON calendar_events(user_id, event_date);
        CREATE INDEX IF NOT EXISTS idx_focus_user_completed ON focus_sessions(user_id, completed_at);
        CREATE INDEX IF NOT EXISTS idx_checkins_user_date ON check_ins(user_id, entry_date);
        """
        with self._connection() as connection:
            connection.executescript(schema)
            # Databases created before Gmail support did not record which Google
            # integration initiated a state. Preserve those states as Calendar
            # states so existing in-flight Calendar OAuth links stay valid.
            state_columns = {
                str(column["name"])
                for column in connection.execute("PRAGMA table_info(oauth_states)").fetchall()
            }
            if "provider" not in state_columns:
                connection.execute(
                    "ALTER TABLE oauth_states "
                    "ADD COLUMN provider TEXT NOT NULL DEFAULT 'google_calendar'"
                )
            connection.execute("PRAGMA journal_mode = WAL")

    # Users -----------------------------------------------------------------
    def create_user(
        self, email: str, display_name: str, password_hash: str, password_salt: str
    ) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (email, display_name, password_hash, password_salt, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (email.lower().strip(), display_name.strip(), password_hash, password_salt, _utc_now()),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._record(row) or {}

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._record(row)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
            ).fetchone()
        return self._record(row)

    def update_last_login(self, user_id: int) -> None:
        with self._connection() as connection:
            connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (_utc_now(), user_id))

    # Tasks -----------------------------------------------------------------
    def create_task(
        self,
        user_id: int,
        title: str,
        *,
        priority: str = "Medium",
        category: str = "General",
        due_date: date | str | None = None,
        estimated_minutes: int = 30,
        notes: str = "",
    ) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks
                (user_id, title, notes, due_date, priority, category, estimated_minutes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    title.strip(),
                    notes.strip(),
                    _as_iso_date(due_date),
                    priority,
                    category,
                    max(5, int(estimated_minutes)),
                    _utc_now(),
                ),
            )
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._record(row) or {}

    def get_task(self, user_id: int, task_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
            ).fetchone()
        return self._record(row)

    def list_tasks(self, user_id: int, *, include_completed: bool = True) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM tasks
                WHERE user_id = ? AND (? = 1 OR status != 'completed')
                ORDER BY
                    CASE status WHEN 'completed' THEN 1 ELSE 0 END,
                    CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
                    CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                    due_date ASC,
                    created_at DESC
                """,
                (user_id, int(include_completed)),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_task(self, user_id: int, task_id: int, **updates: Any) -> dict[str, Any] | None:
        allowed = {
            "title",
            "notes",
            "due_date",
            "priority",
            "category",
            "estimated_minutes",
        }
        clean_updates = {key: value for key, value in updates.items() if key in allowed}
        if not clean_updates:
            return self.get_task(user_id, task_id)
        if "due_date" in clean_updates:
            clean_updates["due_date"] = _as_iso_date(clean_updates["due_date"])
        if "estimated_minutes" in clean_updates:
            clean_updates["estimated_minutes"] = max(5, int(clean_updates["estimated_minutes"]))
        assignments = ", ".join(f"{column} = ?" for column in clean_updates)
        values = list(clean_updates.values()) + [task_id, user_id]
        with self._connection() as connection:
            connection.execute(f"UPDATE tasks SET {assignments} WHERE id = ? AND user_id = ?", values)
        return self.get_task(user_id, task_id)

    def set_task_status(self, user_id: int, task_id: int, *, completed: bool) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ? AND user_id = ?",
                ("completed" if completed else "todo", _utc_now() if completed else None, task_id, user_id),
            )

    def delete_task(self, user_id: int, task_id: int) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))

    # Calendar events -------------------------------------------------------
    def create_event(
        self,
        user_id: int,
        title: str,
        event_date: date | str,
        start_time: str,
        end_time: str,
        *,
        category: str = "General",
        location: str = "",
        notes: str = "",
        is_fixed: bool = False,
        source: str = "manual",
        external_id: str | None = None,
    ) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO calendar_events
                (user_id, title, event_date, start_time, end_time, category, location, notes,
                 is_fixed, source, external_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    title.strip(),
                    _as_iso_date(event_date),
                    start_time,
                    end_time,
                    category,
                    location.strip(),
                    notes.strip(),
                    int(is_fixed),
                    source,
                    external_id,
                    _utc_now(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM calendar_events WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._record(row) or {}

    def list_events(
        self, user_id: int, *, start_date: date | str | None = None, end_date: date | str | None = None
    ) -> list[dict[str, Any]]:
        conditions = ["user_id = ?"]
        values: list[Any] = [user_id]
        if start_date:
            conditions.append("event_date >= ?")
            values.append(_as_iso_date(start_date))
        if end_date:
            conditions.append("event_date <= ?")
            values.append(_as_iso_date(end_date))
        where = " AND ".join(conditions)
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM calendar_events WHERE {where} ORDER BY event_date, start_time, end_time",
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_event(self, user_id: int, event_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM calendar_events WHERE id = ? AND user_id = ?", (event_id, user_id)
            ).fetchone()
        return self._record(row)

    def delete_event(self, user_id: int, event_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM calendar_events WHERE id = ? AND user_id = ?", (event_id, user_id)
            )

    def delete_planner_events(self, user_id: int, event_date: date | str) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM calendar_events WHERE user_id = ? AND event_date = ? AND source = 'planner'",
                (user_id, _as_iso_date(event_date)),
            )

    def update_event_external_id(self, user_id: int, event_id: int, external_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE calendar_events SET external_id = ? WHERE id = ? AND user_id = ?",
                (external_id, event_id, user_id),
            )

    def upsert_external_event(self, user_id: int, event: dict[str, Any]) -> dict[str, Any]:
        """Persist a Google event once; later imports update the same local record."""
        external_id = event["external_id"]
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT id FROM calendar_events WHERE user_id = ? AND external_id = ?",
                (user_id, external_id),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE calendar_events SET title = ?, event_date = ?, start_time = ?, end_time = ?,
                    category = ?, location = ?, notes = ?, source = 'google'
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        event["title"],
                        event["event_date"],
                        event["start_time"],
                        event["end_time"],
                        event.get("category", "Calendar"),
                        event.get("location", ""),
                        event.get("notes", ""),
                        existing["id"],
                        user_id,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM calendar_events WHERE id = ?", (existing["id"],)
                ).fetchone()
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO calendar_events
                    (user_id, title, event_date, start_time, end_time, category, location, notes,
                     is_fixed, source, external_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'google', ?, ?)
                    """,
                    (
                        user_id,
                        event["title"],
                        event["event_date"],
                        event["start_time"],
                        event["end_time"],
                        event.get("category", "Calendar"),
                        event.get("location", ""),
                        event.get("notes", ""),
                        external_id,
                        _utc_now(),
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM calendar_events WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
        return self._record(row) or {}

    # Focus, check-ins, and plans ------------------------------------------
    def record_focus_session(
        self, user_id: int, duration_minutes: int, task_id: int | None = None
    ) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO focus_sessions (user_id, task_id, duration_minutes, completed_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, task_id, max(1, int(duration_minutes)), _utc_now()),
            )
            row = connection.execute(
                "SELECT * FROM focus_sessions WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._record(row) or {}

    def upsert_check_in(
        self,
        user_id: int,
        entry_date: date | str,
        *,
        energy: int,
        focus: int,
        satisfaction: int,
        stress: int,
        notes: str = "",
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO check_ins
                (user_id, entry_date, energy, focus, satisfaction, stress, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, entry_date) DO UPDATE SET
                    energy = excluded.energy,
                    focus = excluded.focus,
                    satisfaction = excluded.satisfaction,
                    stress = excluded.stress,
                    notes = excluded.notes,
                    created_at = excluded.created_at
                """,
                (
                    user_id,
                    _as_iso_date(entry_date),
                    int(energy),
                    int(focus),
                    int(satisfaction),
                    int(stress),
                    notes.strip(),
                    _utc_now(),
                ),
            )

    def get_check_ins(
        self, user_id: int, start_date: date | str, end_date: date | str
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM check_ins
                WHERE user_id = ? AND entry_date BETWEEN ? AND ?
                ORDER BY entry_date
                """,
                (user_id, _as_iso_date(start_date), _as_iso_date(end_date)),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_plan(
        self, user_id: int, plan_type: str, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO generated_plans (user_id, plan_type, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, plan_type, content, json.dumps(metadata or {}), _utc_now()),
            )

    def list_plans(self, user_id: int, plan_type: str, limit: int = 5) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM generated_plans
                WHERE user_id = ? AND plan_type = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (user_id, plan_type, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    # Dashboard queries -----------------------------------------------------
    def dashboard_metrics(self, user_id: int, day: date | str) -> dict[str, int]:
        day_value = _as_iso_date(day)
        with self._connection() as connection:
            completed = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND substr(completed_at, 1, 10) = ?",
                (user_id, day_value),
            ).fetchone()[0]
            open_tasks = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status != 'completed'", (user_id,)
            ).fetchone()[0]
            focus_minutes = connection.execute(
                """
                SELECT COALESCE(SUM(duration_minutes), 0) FROM focus_sessions
                WHERE user_id = ? AND substr(completed_at, 1, 10) = ?
                """,
                (user_id, day_value),
            ).fetchone()[0]
            events = connection.execute(
                "SELECT COUNT(*) FROM calendar_events WHERE user_id = ? AND event_date = ?",
                (user_id, day_value),
            ).fetchone()[0]
        return {
            "completed_today": int(completed),
            "open_tasks": int(open_tasks),
            "focus_minutes": int(focus_minutes),
            "events_today": int(events),
        }

    def daily_activity(
        self, user_id: int, start_date: date | str, end_date: date | str
    ) -> list[dict[str, Any]]:
        """Return a dense daily series for task completions and focus minutes."""
        start = date.fromisoformat(_as_iso_date(start_date) or "")
        end = date.fromisoformat(_as_iso_date(end_date) or "")
        with self._connection() as connection:
            completed_rows = connection.execute(
                """
                SELECT substr(completed_at, 1, 10) AS day, COUNT(*) AS count
                FROM tasks WHERE user_id = ? AND completed_at IS NOT NULL
                    AND substr(completed_at, 1, 10) BETWEEN ? AND ?
                GROUP BY day
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchall()
            focus_rows = connection.execute(
                """
                SELECT substr(completed_at, 1, 10) AS day, COALESCE(SUM(duration_minutes), 0) AS minutes
                FROM focus_sessions WHERE user_id = ?
                    AND substr(completed_at, 1, 10) BETWEEN ? AND ?
                GROUP BY day
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchall()
        completed = {row["day"]: int(row["count"]) for row in completed_rows}
        focus = {row["day"]: int(row["minutes"]) for row in focus_rows}
        results: list[dict[str, Any]] = []
        current = start
        while current <= end:
            day_key = current.isoformat()
            results.append(
                {"date": day_key, "completed_tasks": completed.get(day_key, 0), "focus_minutes": focus.get(day_key, 0)}
            )
            current += timedelta(days=1)
        return results

    # OAuth tokens ----------------------------------------------------------
    def save_oauth_token(self, user_id: int, provider: str, encrypted_payload: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO oauth_tokens (user_id, provider, encrypted_payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, provider) DO UPDATE SET
                    encrypted_payload = excluded.encrypted_payload,
                    updated_at = excluded.updated_at
                """,
                (user_id, provider, encrypted_payload, _utc_now()),
            )

    def get_oauth_token(self, user_id: int, provider: str) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT encrypted_payload FROM oauth_tokens WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            ).fetchone()
        return str(row["encrypted_payload"]) if row else None

    def delete_oauth_token(self, user_id: int, provider: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM oauth_tokens WHERE user_id = ? AND provider = ?", (user_id, provider)
            )

    def create_oauth_state(
        self, user_id: int, minutes_valid: int = 10, *, provider: str = "google_calendar"
    ) -> str:
        """Create a short-lived OAuth state bound to one user and integration.

        ``minutes_valid`` remains positional for backwards compatibility with
        earlier Calendar callers. Providers are stored with the state so a
        callback issued for Gmail cannot complete a Calendar connection.
        """
        clean_provider = _oauth_provider(provider)
        state = secrets.token_urlsafe(32)
        expires_at = (datetime.now(UTC) + timedelta(minutes=minutes_valid)).isoformat()
        with self._connection() as connection:
            connection.execute("DELETE FROM oauth_states WHERE expires_at < ?", (_utc_now(),))
            connection.execute(
                "INSERT INTO oauth_states (state, user_id, provider, expires_at) VALUES (?, ?, ?, ?)",
                (state, user_id, clean_provider, expires_at),
            )
        return state

    def oauth_state_provider(
        self, state: str, expected_user_id: int | None = None
    ) -> str | None:
        """Return a valid state’s provider without consuming it.

        The app uses this narrow lookup solely to dispatch a shared Google OAuth
        callback to Calendar or Gmail. Invalid, expired, and cross-account states
        are removed rather than revealing their provider.
        """
        with self._connection() as connection:
            row = connection.execute(
                "SELECT user_id, provider, expires_at FROM oauth_states WHERE state = ?", (state,)
            ).fetchone()
            if not row or not _valid_oauth_state(row, expected_user_id):
                connection.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
                return None
        return _oauth_provider(str(row["provider"] or "google_calendar"))

    def consume_oauth_state(
        self,
        state: str,
        expected_user_id: int | None = None,
        *,
        expected_provider: str | None = None,
    ) -> int | None:
        """Consume a state once, optionally binding it to the active user session."""
        clean_expected_provider = _oauth_provider(expected_provider) if expected_provider else None
        with self._connection() as connection:
            row = connection.execute(
                "SELECT user_id, provider, expires_at FROM oauth_states WHERE state = ?", (state,)
            ).fetchone()
            connection.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        if not row or not _valid_oauth_state(row, expected_user_id):
            return None
        provider = _oauth_provider(str(row["provider"] or "google_calendar"))
        if clean_expected_provider is not None and provider != clean_expected_provider:
            return None
        return int(row["user_id"])


def _oauth_provider(value: str) -> str:
    """Keep OAuth provider names bounded and safe for durable state records."""
    provider = value.strip() if isinstance(value, str) else ""
    if not provider or len(provider) > 100:
        raise ValueError("OAuth provider must be a non-empty value up to 100 characters.")
    return provider


def _valid_oauth_state(row: sqlite3.Row, expected_user_id: int | None) -> bool:
    try:
        expires_at = datetime.fromisoformat(str(row["expires_at"]))
        owner_id = int(row["user_id"])
    except (TypeError, ValueError):
        return False
    if expires_at.tzinfo is None:
        return False
    return expires_at > datetime.now(UTC) and (
        expected_user_id is None or owner_id == expected_user_id
    )
