"""Mock-only coverage for the provider boundary used by DayCraft planning."""

from __future__ import annotations

import os
import sys
import types
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from services.ai import (
    AIConfigurationError,
    AIPlanningError,
    AIService,
    parse_day_plan_guidance,
    parse_day_plan_payload,
)


def _tasks() -> list[dict[str, object]]:
    return [
        {
            "id": 7,
            "title": "Prepare launch note",
            "priority": "High",
            "category": "Work",
            "estimated_minutes": 45,
            "status": "todo",
            "due_date": "2026-09-18",
        }
    ]


class AIProviderTests(unittest.TestCase):
    def test_missing_provider_key_raises_for_a_daily_plan(self) -> None:
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "DAYCRAFT_AI_PROVIDER": ""},
            clear=False,
        ):
            service = AIService(provider="gemini", api_key="")
            self.assertFalse(service.is_configured)
            self.assertIn("Add a Gemini API key", service.configuration_message)
            with self.assertRaises(AIConfigurationError):
                service.create_day_plan(
                    date(2026, 9, 18), _tasks(), [], work_start="09:00", work_end="17:00"
                )

    def test_session_configuration_takes_precedence_over_deployment_environment(self) -> None:
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "deployment-gemini", "OPENAI_API_KEY": "deployment-openai"},
            clear=False,
        ):
            service = AIService(api_key="session-openai", provider="openai", model="gpt-session")

        self.assertTrue(service.is_configured)
        self.assertEqual(service.provider, "openai")
        self.assertEqual(service.model, "gpt-session")
        self.assertEqual(service.api_key, "session-openai")

    def test_gemini_plan_uses_stateless_structured_interactions(self) -> None:
        with (
            patch("google.genai.Client") as client_class,
            patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False),
        ):
            client_class.return_value.interactions.create.return_value.output_text = (
                '{"ordered_task_ids": [7], "focus_theme": "Finish the launch note", '
                '"plan_note": "Use the first free block."}'
            )
            advice = AIService(api_key="session-gemini", provider="gemini").create_day_plan(
                date(2026, 9, 18), _tasks(), [], work_start="09:00", work_end="17:00"
            )

        self.assertFalse(advice.used_fallback)
        self.assertEqual(advice.ordered_task_ids, [7])
        create_kwargs = client_class.return_value.interactions.create.call_args.kwargs
        self.assertFalse(create_kwargs["store"])
        self.assertEqual(create_kwargs["response_format"]["mime_type"], "application/json")
        self.assertIn("ordered_task_ids", create_kwargs["response_format"]["schema"]["required"])

    def test_openai_plan_uses_stateless_strict_json_schema_responses(self) -> None:
        fake_client = MagicMock()
        fake_client.responses.create.return_value.output_text = (
            '{"ordered_task_ids": [7], "focus_theme": "Ship the note", '
            '"plan_note": "Use the opening focus block."}'
        )
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = MagicMock(return_value=fake_client)

        with patch.dict(sys.modules, {"openai": fake_openai}):
            advice = AIService(api_key="session-openai", provider="openai").create_day_plan(
                date(2026, 9, 18), _tasks(), [], work_start="09:00", work_end="17:00"
            )

        self.assertEqual(advice.ordered_task_ids, [7])
        fake_openai.OpenAI.assert_called_once_with(api_key="session-openai")
        create_kwargs = fake_client.responses.create.call_args.kwargs
        self.assertEqual(create_kwargs["model"], "gpt-5.2")
        self.assertFalse(create_kwargs["store"])
        self.assertEqual(create_kwargs["text"]["format"]["type"], "json_schema")
        self.assertTrue(create_kwargs["text"]["format"]["strict"])
        self.assertFalse(create_kwargs["text"]["format"]["schema"]["additionalProperties"])

    def test_openai_reflection_uses_the_responses_api_without_storage(self) -> None:
        fake_client = MagicMock()
        fake_client.responses.create.return_value.output_text = "Protect one recovery break tomorrow."
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = MagicMock(return_value=fake_client)

        with patch.dict(sys.modules, {"openai": fake_openai}):
            response = AIService(api_key="session-openai", provider="openai").reflection(6, 6, 6, 4, "")

        self.assertFalse(response.used_fallback)
        self.assertEqual(response.content, "Protect one recovery break tomorrow.")
        create_kwargs = fake_client.responses.create.call_args.kwargs
        self.assertFalse(create_kwargs["store"])
        self.assertNotIn("text", create_kwargs)

    def test_invalid_model_output_cannot_create_a_local_day_plan(self) -> None:
        with patch("google.genai.Client") as client_class:
            client_class.return_value.interactions.create.return_value.output_text = "not JSON"
            with self.assertRaises(AIPlanningError):
                AIService(api_key="session-gemini", provider="gemini").create_day_plan(
                    date(2026, 9, 18), _tasks(), [], work_start="09:00", work_end="17:00"
                )

    def test_plan_payload_keeps_only_real_task_ids(self) -> None:
        order, _, _ = parse_day_plan_payload(
            '{"ordered_task_ids": [7, 999, 7], "focus_theme": "Focus", "plan_note": "Plan"}',
            {7, 8},
            [8, 7],
        )
        self.assertEqual(order, [7, 8])

    def test_task_guidance_is_limited_to_real_tasks_and_cannot_be_a_second_schedule(self) -> None:
        guidance = parse_day_plan_guidance(
            """{
                "task_guidance": [
                    {"task_id": 7, "focus": "Draft the opening before polishing details."},
                    {"task_id": 99, "focus": "Invented task"},
                    {"task_id": 8, "focus": "Move the meeting to 2 PM."},
                    {"task_id": 7, "focus": "Duplicate cue"}
                ]
            }""",
            {7, 8},
        )
        self.assertEqual(guidance, {7: "Draft the opening before polishing details."})

    def test_day_pace_is_sent_to_the_ai_but_timing_stays_out_of_its_response(self) -> None:
        with patch("google.genai.Client") as client_class:
            client_class.return_value.interactions.create.return_value.output_text = (
                '{"ordered_task_ids": [7], "focus_theme": "Make a calm start", '
                '"plan_note": "Leave breathing room around the important work.", '
                '"task_guidance": [{"task_id": 7, "focus": "Start with a clear outline."}]}'
            )
            advice = AIService(api_key="session-gemini", provider="gemini").create_day_plan(
                date(2026, 9, 18),
                _tasks(),
                [{"title": "Standup", "start_time": "09:00", "end_time": "09:30"}],
                work_start="09:00",
                work_end="17:00",
                pace="Chill",
            )

        self.assertEqual(advice.pace, "Chill")
        self.assertEqual(advice.task_guidance, {7: "Start with a clear outline."})
        prompt = client_class.return_value.interactions.create.call_args.kwargs["input"]
        self.assertIn("requested day pace is Chill", prompt)
        self.assertIn("Calendar commitments are fixed and cannot move", prompt)


if __name__ == "__main__":
    unittest.main()
