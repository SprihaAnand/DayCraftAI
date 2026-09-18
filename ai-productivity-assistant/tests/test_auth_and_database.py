from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from services.auth import AuthenticationError, AuthService
from services.database import Database


class DatabaseAndAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temporary_directory.name) / "daycraft-test.db")
        self.database.initialize()
        self.auth = AuthService(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_account_authentication_and_user_scoping(self) -> None:
        user = self.auth.register("Ava@example.com", "Ava", "StrongPass123")
        other_user = self.auth.register("ben@example.com", "Ben", "AnotherPass456")

        authenticated = self.auth.authenticate("ava@EXAMPLE.com", "StrongPass123")
        self.assertEqual(authenticated.id, user.id)
        with self.assertRaisesRegex(AuthenticationError, "incorrect"):
            self.auth.authenticate("ava@example.com", "wrong-password")

        task = self.database.create_task(user.id, "Write launch brief", priority="High", estimated_minutes=45)
        self.assertEqual(self.database.list_tasks(user.id), [task])
        self.assertEqual(self.database.list_tasks(other_user.id), [])

        self.database.set_task_status(user.id, task["id"], completed=True)
        completed_task = self.database.get_task(user.id, task["id"])
        self.assertEqual(completed_task["status"], "completed")
        self.assertTrue(completed_task["completed_at"])

    def test_events_checkins_and_dashboard_metrics_persist(self) -> None:
        user = self.auth.register("ava@example.com", "Ava", "StrongPass123")
        today = date.today().isoformat()
        task = self.database.create_task(user.id, "Review proposal")
        self.database.set_task_status(user.id, task["id"], completed=True)
        self.database.create_event(
            user.id,
            "Daily standup",
            today,
            "09:00",
            "09:30",
            category="Meeting",
            is_fixed=True,
        )
        self.database.record_focus_session(user.id, 25, task["id"])
        self.database.upsert_check_in(
            user.id,
            today,
            energy=7,
            focus=8,
            satisfaction=7,
            stress=3,
            notes="Good start",
        )

        events = self.database.list_events(user.id, start_date=today, end_date=today)
        self.assertEqual(len(events), 1)
        self.assertEqual(self.database.get_check_ins(user.id, today, today)[0]["focus"], 8)
        metrics = self.database.dashboard_metrics(user.id, today)
        self.assertEqual(metrics["events_today"], 1)
        self.assertEqual(metrics["open_tasks"], 0)
        self.assertEqual(metrics["focus_minutes"], 25)

    def test_oauth_state_is_single_use(self) -> None:
        user = self.auth.register("ava@example.com", "Ava", "StrongPass123")
        state = self.database.create_oauth_state(user.id)
        self.assertEqual(self.database.consume_oauth_state(state), user.id)
        self.assertIsNone(self.database.consume_oauth_state(state))

    def test_oauth_state_cannot_be_consumed_from_a_different_account(self) -> None:
        owner = self.auth.register("ava@example.com", "Ava", "StrongPass123")
        other_user = self.auth.register("ben@example.com", "Ben", "AnotherPass456")
        state = self.database.create_oauth_state(owner.id)
        self.assertIsNone(self.database.consume_oauth_state(state, expected_user_id=other_user.id))
        self.assertIsNone(self.database.consume_oauth_state(state, expected_user_id=owner.id))


if __name__ == "__main__":
    unittest.main()
