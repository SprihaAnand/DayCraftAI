from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

from services.ai import AIConfigurationError, AIService, parse_day_plan_payload
from services.calendar import normalize_google_event
from services.planning import build_daily_plan


class PlanningAndIntegrationTests(unittest.TestCase):
    def test_daily_planner_uses_real_gaps_and_keeps_fixed_events(self) -> None:
        fixed_events = [
            {
                "title": "Standup",
                "start_time": "10:00",
                "end_time": "10:30",
                "category": "Meeting",
                "source": "manual",
                "is_fixed": 1,
            },
            {
                "title": "Client call",
                "start_time": "13:00",
                "end_time": "14:00",
                "category": "Meeting",
                "source": "google",
                "is_fixed": 1,
            },
        ]
        tasks = [
            {
                "id": 1,
                "title": "Write proposal",
                "priority": "High",
                "category": "Deep work",
                "estimated_minutes": 60,
                "status": "todo",
                "due_date": "2026-09-18",
            },
            {
                "id": 2,
                "title": "Reply to email",
                "priority": "Low",
                "category": "Admin",
                "estimated_minutes": 30,
                "status": "todo",
                "due_date": "2026-09-18",
            },
        ]
        blocks, unscheduled = build_daily_plan(
            date(2026, 9, 18), tasks, fixed_events, work_start="09:00", work_end="15:00"
        )

        proposal = next(block for block in blocks if block.title == "Write proposal")
        standup = next(block for block in blocks if block.title == "Standup")
        self.assertEqual((standup.start_time, standup.end_time), ("10:00", "10:30"))
        self.assertTrue(proposal.end_time <= "10:00" or proposal.start_time >= "10:30")
        self.assertFalse(unscheduled)

    def test_google_event_normalization_handles_timed_and_all_day_events(self) -> None:
        timed = normalize_google_event(
            {
                "id": "event-1",
                "summary": "Review",
                "start": {"dateTime": "2026-09-18T09:00:00+05:30"},
                "end": {"dateTime": "2026-09-18T10:00:00+05:30"},
            }
        )
        self.assertEqual(timed["event_date"], "2026-09-18")
        self.assertEqual(timed["start_time"], "09:00")

        all_day = normalize_google_event(
            {
                "id": "event-2",
                "summary": "Holiday",
                "start": {"date": "2026-09-19"},
                "end": {"date": "2026-09-20"},
            }
        )
        self.assertEqual(all_day["start_time"], "00:00")
        self.assertEqual(all_day["category"], "All day")

    def test_ai_service_falls_back_without_a_key(self) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""}, clear=False):
            response = AIService().reflection(6, 6, 6, 4, "")
        self.assertTrue(response.used_fallback)
        self.assertEqual(response.provider, "local planner")
        self.assertIn("tomorrow", response.content)

    def test_day_plan_requires_an_ai_provider_when_no_key_is_configured(self) -> None:
        tasks = [
            {
                "id": 9,
                "title": "Important work",
                "priority": "High",
                "category": "Deep work",
                "estimated_minutes": 60,
                "status": "todo",
                "due_date": "2026-09-18",
            },
            {
                "id": 10,
                "title": "Optional reply",
                "priority": "Low",
                "category": "Admin",
                "estimated_minutes": 15,
                "status": "todo",
                "due_date": None,
            },
        ]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""}, clear=False):
            with self.assertRaises(AIConfigurationError):
                AIService().create_day_plan(
                    date(2026, 9, 18),
                    tasks,
                    [],
                    work_start="09:00",
                    work_end="17:00",
                )

    def test_gemini_day_plan_uses_stateless_structured_interactions(self) -> None:
        tasks = [
            {
                "id": 1,
                "title": "Prepare launch note",
                "priority": "High",
                "category": "Work",
                "estimated_minutes": 45,
                "status": "todo",
                "due_date": "2026-09-18",
            }
        ]
        with (
            patch.dict(
                os.environ,
                {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-3.8-flash"},
                clear=False,
            ),
            patch("google.genai.Client") as client_class,
        ):
            interaction = client_class.return_value.interactions.create.return_value
            interaction.output_text = (
                '{"ordered_task_ids": [1], "focus_theme": "Finish the launch note", '
                '"plan_note": "Use the first free block."}'
            )
            advice = AIService().create_day_plan(
                date(2026, 9, 18),
                tasks,
                [],
                work_start="09:00",
                work_end="17:00",
            )

        self.assertFalse(advice.used_fallback)
        self.assertEqual(advice.ordered_task_ids, [1])
        create_kwargs = client_class.return_value.interactions.create.call_args.kwargs
        self.assertEqual(create_kwargs["model"], "gemini-3.8-flash")
        self.assertFalse(create_kwargs["store"])
        self.assertEqual(create_kwargs["response_format"]["type"], "text")
        self.assertEqual(create_kwargs["response_format"]["mime_type"], "application/json")
        self.assertIn("ordered_task_ids", create_kwargs["response_format"]["schema"]["required"])

    def test_gemini_coaching_uses_a_stateless_interaction(self) -> None:
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False),
            patch("google.genai.Client") as client_class,
        ):
            client_class.return_value.interactions.create.return_value.output_text = "Start with one clear task."
            response = AIService().reflection(6, 6, 6, 4, "")

        self.assertFalse(response.used_fallback)
        self.assertEqual(response.content, "Start with one clear task.")
        create_kwargs = client_class.return_value.interactions.create.call_args.kwargs
        self.assertFalse(create_kwargs["store"])
        self.assertNotIn("response_format", create_kwargs)

    def test_gemini_order_is_validated_before_the_local_scheduler_uses_it(self) -> None:
        ordered_ids, focus_theme, plan_note = parse_day_plan_payload(
            '{"ordered_task_ids": [2, 999, 2], "focus_theme": "Start small", "plan_note": "Protect the first block."}',
            {1, 2},
            [1, 2],
        )
        self.assertEqual(ordered_ids, [2, 1])
        self.assertEqual(focus_theme, "Start small")
        self.assertEqual(plan_note, "Protect the first block.")

        tasks = [
            {
                "id": 1,
                "title": "Important brief",
                "priority": "High",
                "category": "Deep work",
                "estimated_minutes": 30,
                "status": "todo",
                "due_date": "2026-09-18",
            },
            {
                "id": 2,
                "title": "Quick reply",
                "priority": "Low",
                "category": "Admin",
                "estimated_minutes": 30,
                "status": "todo",
                "due_date": "2026-09-18",
            },
        ]
        blocks, unscheduled = build_daily_plan(
            date(2026, 9, 18), tasks, [], work_start="09:00", work_end="10:15", task_order=ordered_ids
        )
        self.assertFalse(unscheduled)
        self.assertEqual([block.title for block in blocks], ["Quick reply", "Important brief"])


if __name__ == "__main__":
    unittest.main()
