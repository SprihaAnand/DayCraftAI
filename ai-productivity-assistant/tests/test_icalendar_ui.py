from __future__ import annotations

import unittest

from streamlit.testing.v1 import AppTest


class ICalendarSettingsUiTests(unittest.TestCase):
    def test_settings_exposes_a_local_review_first_calendar_import(self) -> None:
        def script() -> None:
            from pages.settings import render_settings
            from services.auth import AuthenticatedUser

            class FakeDatabase:
                def list_tasks(self, user_id: int, *, include_completed: bool) -> list[dict[str, object]]:
                    return []

                def list_events(self, user_id: int) -> list[dict[str, object]]:
                    return []

            render_settings(
                FakeDatabase(),  # type: ignore[arg-type]
                AuthenticatedUser(id=1, email="review@example.com", display_name="Review"),
            )

        app = AppTest.from_function(script).run()

        self.assertFalse(app.exception)
        uploader = next(item for item in app.file_uploader if item.label == "Choose one .ics file")
        self.assertEqual(uploader.proto.max_upload_size_mb, 1)
        self.assertTrue(any(item.label == "Download tasks and schedule data (JSON)" for item in app.download_button))


if __name__ == "__main__":
    unittest.main()
