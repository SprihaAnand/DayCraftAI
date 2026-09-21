from __future__ import annotations

import unittest

from services.task_capture import MAX_CAPTURE_ITEMS, parse_task_capture


class TaskCaptureParserTests(unittest.TestCase):
    def test_mixed_natural_language_capture_separates_flexible_tasks_and_commitments(self) -> None:
        preview = parse_task_capture(
            "tasks: lunch from 1 to 2, workout, meeting at 9 for half hour, read 10 pages"
        )

        self.assertEqual(
            [(item.title, item.estimated_minutes, item.category) for item in preview.tasks],
            [("workout", 45, "Health"), ("read 10 pages", 30, "Learning")],
        )
        self.assertEqual(
            [
                (item.title, item.start_time, item.end_time, item.category)
                for item in preview.commitments
            ],
            [("lunch", "13:00", "14:00", "Personal"), ("meeting", "09:00", "09:30", "Work")],
        )
        self.assertFalse(preview.warnings)

    def test_explicit_meridiems_and_cross_noon_ranges_are_normalized(self) -> None:
        preview = parse_task_capture(
            "Client call from 11 am to 1 pm; design review at 2:15pm for 45 minutes"
        )

        self.assertEqual(
            [(item.start_time, item.end_time) for item in preview.commitments],
            [("11:00", "13:00"), ("14:15", "15:00")],
        )

    def test_ambiguous_time_without_duration_stays_a_flexible_task(self) -> None:
        preview = parse_task_capture("Call the dentist at 9")

        self.assertEqual(len(preview.tasks), 1)
        self.assertEqual(preview.tasks[0].title, "Call the dentist")
        self.assertFalse(preview.commitments)
        self.assertTrue(any("no duration" in warning for warning in preview.warnings))

    def test_new_lines_are_supported_as_separate_review_items(self) -> None:
        preview = parse_task_capture("- Write outline\n- Lunch from 12 to 1\n- Take a walk")

        self.assertEqual([item.title for item in preview.tasks], ["Write outline", "Take a walk"])
        self.assertEqual(
            [(item.title, item.start_time, item.end_time) for item in preview.commitments],
            [("Lunch", "12:00", "13:00")],
        )

    def test_overnight_or_excessive_ranges_are_not_silently_added_as_commitments(self) -> None:
        preview = parse_task_capture("Night shift from 9 pm to 8 am")

        self.assertEqual(len(preview.tasks), 1)
        self.assertFalse(preview.commitments)
        self.assertTrue(any("time range was unclear" in warning for warning in preview.warnings))

    def test_parser_limits_import_scope_and_never_executes_input(self) -> None:
        raw = ", ".join(f"Task {index}" for index in range(MAX_CAPTURE_ITEMS + 3))
        preview = parse_task_capture(raw)

        self.assertEqual(len(preview.tasks), MAX_CAPTURE_ITEMS)
        self.assertTrue(any("left out" in warning for warning in preview.warnings))
        self.assertEqual(preview.tasks[0].title, "Task 0")
        self.assertEqual(preview.tasks[-1].title, f"Task {MAX_CAPTURE_ITEMS - 1}")


if __name__ == "__main__":
    unittest.main()
