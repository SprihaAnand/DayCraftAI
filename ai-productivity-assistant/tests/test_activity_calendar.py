from __future__ import annotations

import unittest
from datetime import date, timedelta

from streamlit.testing.v1 import AppTest

from services.activity_calendar import (
    WEEKDAY_LABELS,
    build_completion_activity_calendar,
    completion_activity_window,
)


class CompletionActivityCalendarTests(unittest.TestCase):
    def test_window_is_exactly_fifty_two_monday_to_sunday_weeks(self) -> None:
        start_date, end_date = completion_activity_window(date(2026, 9, 22))

        self.assertEqual(start_date.weekday(), 0)
        self.assertEqual(end_date.weekday(), 6)
        self.assertEqual((end_date - start_date).days + 1, 52 * 7)

    def test_calendar_uses_only_completed_task_counts_and_combines_days(self) -> None:
        today = date(2026, 9, 22)
        cells = build_completion_activity_calendar(
            [
                {"date": "2026-09-21", "completed_tasks": 1, "focus_minutes": 900},
                {"date": "2026-09-21", "completed_tasks": 2, "focus_minutes": 0},
                {"date": "2026-09-22", "completed_tasks": 1},
                {"date": "2026-09-23", "completed_tasks": 99},
                {"date": "not-a-date", "completed_tasks": 100},
            ],
            today=today,
        )

        by_date = {cell.activity_date: cell for cell in cells}
        self.assertEqual(len(cells), 52 * 7)
        self.assertEqual(by_date[date(2026, 9, 21)].completed_tasks, 3)
        self.assertEqual(by_date[today].completed_tasks, 1)
        self.assertEqual(by_date[date(2026, 9, 23)].completed_tasks, 0)
        self.assertTrue(by_date[date(2026, 9, 23)].is_future)
        self.assertEqual(by_date[today].weekday_label, WEEKDAY_LABELS[today.weekday()])

    def test_out_of_window_and_invalid_counts_do_not_create_activity(self) -> None:
        today = date(2026, 9, 22)
        start_date, _ = completion_activity_window(today)
        cells = build_completion_activity_calendar(
            [
                {"date": (start_date - timedelta(days=1)).isoformat(), "completed_tasks": 5},
                {"date": today.isoformat(), "completed_tasks": -4},
                {"date": today.isoformat(), "completed_tasks": True},
                {"date": today.isoformat(), "completed_tasks": "2"},
            ],
            today=today,
        )

        by_date = {cell.activity_date: cell for cell in cells}
        self.assertEqual(by_date[today].completed_tasks, 2)
        self.assertEqual(sum(cell.completed_tasks for cell in cells), 2)


def _activity_calendar_script(rows: list[dict[str, object]], user_id: int) -> str:
    """Keep AppTest self-contained while checking the page's user-scoped query."""
    return f"""
from datetime import date

import streamlit as st

from pages.insights import _render_completion_activity_calendar
from services.auth import AuthenticatedUser


class ActivityDatabase:
    def daily_activity(self, requested_user_id, start_date, end_date):
        st.session_state[\"activity_calendar_requested_user_id\"] = requested_user_id
        return {rows!r}


_render_completion_activity_calendar(
    ActivityDatabase(),
    AuthenticatedUser(id={user_id}, email=\"user@example.com\", display_name=\"User\"),
    today=date(2026, 9, 22),
)
"""


class CompletionActivityCalendarSmokeTests(unittest.TestCase):
    def test_signed_in_user_activity_renders_a_native_heatmap(self) -> None:
        app = AppTest.from_string(
            _activity_calendar_script([{"date": "2026-09-22", "completed_tasks": 2}], 41)
        ).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["activity_calendar_requested_user_id"], 41)
        self.assertTrue(app.get("vega_lite_chart"))
        self.assertTrue(any("2 tasks completed" in item.value for item in app.markdown))

    def test_no_completions_shows_a_private_empty_state(self) -> None:
        app = AppTest.from_string(_activity_calendar_script([], 42)).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["activity_calendar_requested_user_id"], 42)
        self.assertFalse(app.get("vega_lite_chart"))
        self.assertTrue(app.info)


if __name__ == "__main__":
    unittest.main()
