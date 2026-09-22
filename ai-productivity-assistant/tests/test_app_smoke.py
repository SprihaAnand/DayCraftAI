from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services.ai import DayPlanAdvice
from services.database import Database
from services.task_capture import CapturedCommitment, CapturedTask, TaskCapturePreview

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class AppSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.previous_database_path = os.environ.get("DAYCRAFT_DATABASE_PATH")
        self.previous_gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.previous_openai_api_key = os.environ.get("OPENAI_API_KEY")
        os.environ["DAYCRAFT_DATABASE_PATH"] = f"{self.temporary_directory.name}/ui-test.db"
        # Smoke tests must never make a network request using a developer's local key.
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    def tearDown(self) -> None:
        if self.previous_database_path is None:
            os.environ.pop("DAYCRAFT_DATABASE_PATH", None)
        else:
            os.environ["DAYCRAFT_DATABASE_PATH"] = self.previous_database_path
        if self.previous_gemini_api_key is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = self.previous_gemini_api_key
        if self.previous_openai_api_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = self.previous_openai_api_key
        self.temporary_directory.cleanup()

    def _signed_in_app(self, *, configure_ai: bool = False) -> AppTest:
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        # The first two inputs belong to Sign in; the next three create an account.
        app.text_input[2].input("Taylor")
        app.text_input[3].input("taylor@example.com")
        app.text_input[4].input("StrongPass123")
        next(button for button in app.button if button.label == "Create my workspace").click().run()
        self.assertEqual(len(app.exception), 0)
        craft_button = next(button for button in app.button if button.label == "Create my written plan")
        self.assertTrue(craft_button.disabled)
        if configure_ai:
            next(
                text_input for text_input in app.text_input if text_input.label == "Gemini API key"
            ).input("session-test-key")
            next(
                button for button in app.button if button.label == "Use Gemini for this session"
            ).click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertFalse(any(item.label == "Gemini API key" for item in app.text_input))
        return app

    def test_signed_out_login_has_no_workspace_navigation(self) -> None:
        """The public route must not expose empty workspace navigation links."""
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.get("navigation"))
        self.assertFalse(app.get("page_link"))
        self.assertTrue(any(item.label == "Email" for item in app.text_input))

    def test_account_onboarding_and_all_workspace_views_render(self) -> None:
        app = self._signed_in_app()
        pages = {
            "Tasks": "app_pages/task_backlog.py",
            "Focus": "app_pages/focus_mode.py",
            "Progress": "app_pages/progress_review.py",
            "Settings": "app_pages/account_settings.py",
            "Today": "app_pages/day_plan.py",
        }
        for title, page_path in pages.items():
            app.switch_page(page_path).run()
            self.assertEqual(len(app.exception), 0, msg=f"{title} had a Streamlit exception")

    def test_settings_has_no_external_calendar_or_mail_controls(self) -> None:
        app = self._signed_in_app()
        app.switch_page("app_pages/account_settings.py").run()

        self.assertEqual(len(app.exception), 0)
        blocked_labels = {
            "Connect Google Calendar",
            "Connect Gmail",
            "Import upcoming events",
            "Disconnect Calendar",
            "Disconnect Gmail",
            "Continue securely with Google",
            "Send email now",
            "Sync",
        }
        control_labels = {element.label for element in app.button}
        self.assertFalse(blocked_labels & control_labels)

    def test_task_can_move_from_capture_to_a_generated_day_plan(self) -> None:
        app = self._signed_in_app(configure_ai=True)
        app.switch_page("app_pages/task_backlog.py").run()
        next(text_input for text_input in app.text_input if text_input.label == "Task").input(
            "Draft launch brief"
        )
        next(button for button in app.button if button.label == "Save task").click().run()
        self.assertEqual(len(app.exception), 0)

        app.switch_page("app_pages/day_plan.py").run()
        self.assertFalse(
                next(button for button in app.button if button.label == "Create my written plan").disabled
        )
        database = Database(os.environ["DAYCRAFT_DATABASE_PATH"])
        user = database.get_user_by_email("taylor@example.com")
        task = database.list_tasks(user["id"], include_completed=False)[0]
        ai_advice = DayPlanAdvice(
            ordered_task_ids=[int(task["id"])],
            focus_theme="Draft the launch brief first",
            plan_note="Use the first available protected work block.",
            provider="gemini-3.8-flash",
            used_fallback=False,
        )
        with patch("services.ai.AIService.create_day_plan", return_value=ai_advice):
            next(button for button in app.button if button.label == "Create my written plan").click().run()
        self.assertEqual(len(app.exception), 0)

        events = database.list_events(user["id"])
        self.assertTrue(
            any(event["title"] == "Draft launch brief" and event["source"] == "planner" for event in events)
        )

    def test_quick_capture_requires_an_explicit_review_before_writing_items(self) -> None:
        app = self._signed_in_app()
        app.switch_page("app_pages/task_backlog.py").run()
        next(
            text_area
            for text_area in app.text_area
            if text_area.label == "Tasks and commitments"
        ).input(
            "Lunch from 1 to 2, workout, meeting at 9 for half hour, read 10 pages"
        )
        next(button for button in app.button if button.label == "Review items").click().run()
        self.assertEqual(len(app.exception), 0)

        database = Database(os.environ["DAYCRAFT_DATABASE_PATH"])
        user = database.get_user_by_email("taylor@example.com")
        self.assertFalse(database.list_tasks(user["id"]))
        self.assertFalse(database.list_events(user["id"]))
        self.assertTrue(any(item.label == "Add reviewed items" for item in app.button))

        next(
            checkbox
            for checkbox in app.checkbox
            if checkbox.label.startswith("I reviewed these items")
        ).check()
        next(button for button in app.button if button.label == "Add reviewed items").click().run()
        self.assertEqual(len(app.exception), 0)

        task_titles = {task["title"] for task in database.list_tasks(user["id"])}
        event_titles = {event["title"] for event in database.list_events(user["id"])}
        self.assertEqual(task_titles, {"workout", "read 10 pages"})
        self.assertEqual(event_titles, {"Lunch", "meeting"})

    def test_ai_inbox_keeps_uploaded_file_candidates_out_of_the_database_until_confirmed(self) -> None:
        app = self._signed_in_app()
        app.switch_page("app_pages/task_backlog.py").run()
        inbox_preview = TaskCapturePreview(
            tasks=(
                CapturedTask(
                    title="Draft launch brief",
                    estimated_minutes=45,
                    category="Deep work",
                    priority="High",
                ),
            ),
            commitments=(
                CapturedCommitment(
                    title="Client meeting",
                    start_time="09:00",
                    end_time="09:30",
                    category="Meetings",
                ),
            ),
        )
        next(
            uploader
            for uploader in app.file_uploader
            if uploader.label == "Upload a file for Gemini to read"
        ).set_value(("inbox.md", b"# Inbox\nDraft the launch brief", "text/markdown")).run()

        with patch("services.ai.AIService.extract_inbox_candidates", return_value=inbox_preview):
            next(
                button for button in app.button if button.label == "Extract candidates with Gemini"
            ).click().run()
        self.assertEqual(len(app.exception), 0)

        database = Database(os.environ["DAYCRAFT_DATABASE_PATH"])
        user = database.get_user_by_email("taylor@example.com")
        self.assertFalse(database.list_tasks(user["id"]))
        self.assertFalse(database.list_events(user["id"]))
        self.assertTrue(any(item.label == "Add reviewed items" for item in app.button))

        next(
            checkbox
            for checkbox in app.checkbox
            if checkbox.label.startswith("I reviewed these items")
        ).check()
        next(button for button in app.button if button.label == "Add reviewed items").click().run()
        self.assertEqual(len(app.exception), 0)

        self.assertEqual(
            {task["title"] for task in database.list_tasks(user["id"])}, {"Draft launch brief"}
        )
        saved_events = database.list_events(user["id"])
        self.assertEqual({event["title"] for event in saved_events}, {"Client meeting"})
        self.assertEqual(saved_events[0]["source"], "ai_inbox")

    def test_a_saved_rhythm_creates_timed_breaks_without_touching_protected_commitments(self) -> None:
        app = self._signed_in_app()
        database = Database(os.environ["DAYCRAFT_DATABASE_PATH"])
        user = database.get_user_by_email("taylor@example.com")
        database.create_event(
            user["id"],
            "Customer call",
            date.today(),
            "11:30",
            "12:00",
            category="Meeting",
            is_fixed=True,
        )

        next(button for button in app.button if button.label == "Save time divisions").click().run()
        self.assertEqual(len(app.exception), 0)

        events = database.list_events(user["id"])
        self.assertTrue(any(event["title"] == "Customer call" and event["source"] == "manual" for event in events))
        self.assertTrue(any(event["source"] == "planner" and event["category"] == "Break" for event in events))

if __name__ == "__main__":
    unittest.main()
