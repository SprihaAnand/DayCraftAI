from __future__ import annotations

import unittest
from datetime import date

from services.planning import (
    build_template_schedule,
    get_day_pace,
    get_schedule_template,
    list_day_paces,
    list_schedule_templates,
    minutes_from_time,
    template_default_work_hours,
)

PLAN_DATE = date(2026, 9, 18)


def _task(task_id: int, title: str, minutes: int, priority: str = "Medium") -> dict[str, object]:
    return {
        "id": task_id,
        "title": title,
        "priority": priority,
        "category": "General",
        "estimated_minutes": minutes,
        "status": "todo",
        "due_date": PLAN_DATE.isoformat(),
    }


def _overlaps(left_start: str, left_end: str, right_start: str, right_end: str) -> bool:
    return max(minutes_from_time(left_start), minutes_from_time(right_start)) < min(
        minutes_from_time(left_end), minutes_from_time(right_end)
    )


class ScheduleTemplateTests(unittest.TestCase):
    def test_day_pace_registry_has_only_the_three_customer_choices(self) -> None:
        self.assertEqual([pace.name for pace in list_day_paces()], ["Chill", "Balanced", "Work-heavy"])
        self.assertEqual(get_day_pace("work-heavy").template_id, "deep-work")
        with self.assertRaisesRegex(ValueError, "Unknown day pace"):
            get_day_pace("maximal")

    def test_registry_exposes_four_distinct_templates_and_defaults(self) -> None:
        templates = list_schedule_templates()
        self.assertEqual(
            [template.id for template in templates],
            ["balanced", "deep-work", "meeting-day", "early-focus"],
        )
        self.assertEqual(template_default_work_hours("early-focus"), ("07:30", "16:00"))
        self.assertEqual(get_schedule_template("deep_work").name, "Deep work day")
        for template in templates:
            self.assertGreater(len(template.divisions), 5)
            self.assertLess(
                minutes_from_time(template.default_work_start),
                minutes_from_time(template.default_work_end),
            )

    def test_every_template_places_named_breaks_anchors_and_tasks(self) -> None:
        tasks = [
            _task(1, "Draft the proposal", 45, "High"),
            _task(2, "Reply to customers", 30),
            _task(3, "Prepare tomorrow", 30, "Low"),
        ]
        for template in list_schedule_templates():
            with self.subTest(template=template.id):
                blocks, unscheduled = build_template_schedule(PLAN_DATE, tasks, [], template_id=template.id)

                anchors = [block for block in blocks if block.block_type == "template_anchor"]
                planned_tasks = [block for block in blocks if block.block_type == "task"]
                self.assertFalse(unscheduled)
                self.assertGreaterEqual(len(anchors), 3)
                self.assertEqual({block.source for block in anchors}, {"planner"})
                self.assertTrue(all(block.task_id is None for block in anchors))
                self.assertTrue(all(block.category in {"Planning", "Break"} for block in anchors))
                self.assertEqual([block.task_id for block in planned_tasks], [1, 2, 3])
                self.assertTrue(all(block.source == "planner" for block in planned_tasks))
                self.assertTrue(all(block.task_id is not None for block in planned_tasks))

                for index, block in enumerate(blocks):
                    for later_block in blocks[index + 1 :]:
                        self.assertFalse(
                            _overlaps(
                                block.start_time,
                                block.end_time,
                                later_block.start_time,
                                later_block.end_time,
                            ),
                            f"{template.id}: {block} overlaps {later_block}",
                        )

    def test_calendar_commitments_win_over_anchors_and_tasks(self) -> None:
        commitments = [
            {
                "title": "Client workshop",
                "start_time": "09:00",
                "end_time": "11:30",
                "category": "Meeting",
                "source": "google",
                "is_fixed": 1,
            },
            {
                "title": "Lunch meeting",
                "start_time": "12:20",
                "end_time": "13:35",
                "category": "Meeting",
                "source": "google",
                "is_fixed": 1,
            },
        ]
        blocks, unscheduled = build_template_schedule(
            PLAN_DATE,
            [_task(1, "Prepare brief", 40, "High"), _task(2, "Send recap", 30)],
            commitments,
            template_id="balanced",
        )

        fixed_blocks = [block for block in blocks if block.block_type == "fixed"]
        generated_blocks = [block for block in blocks if block.block_type != "fixed"]
        self.assertEqual([(block.title, block.source) for block in fixed_blocks], [
            ("Client workshop", "google"),
            ("Lunch meeting", "google"),
        ])
        self.assertTrue(all(block.is_fixed for block in fixed_blocks))
        self.assertTrue(all(block.source == "planner" for block in generated_blocks))
        for commitment in fixed_blocks:
            for generated in generated_blocks:
                self.assertFalse(
                    _overlaps(
                        commitment.start_time,
                        commitment.end_time,
                        generated.start_time,
                        generated.end_time,
                    ),
                    f"{generated} overlaps protected commitment {commitment}",
                )
        self.assertLessEqual(len(unscheduled), 2)

    def test_ai_order_can_drive_the_deterministic_timing(self) -> None:
        tasks = [
            _task(1, "First by priority", 30, "High"),
            _task(2, "Second by priority", 30, "Medium"),
            _task(3, "AI says start here", 30, "Low"),
        ]
        blocks, unscheduled = build_template_schedule(
            PLAN_DATE,
            tasks,
            [],
            template_id="balanced",
            task_order=[3, 1, 2],
        )
        self.assertFalse(unscheduled)
        self.assertEqual(
            [block.task_id for block in blocks if block.block_type == "task"], [3, 1, 2]
        )

    def test_anchor_relocates_and_small_gaps_remain_available_for_later_tasks(self) -> None:
        commitments = [
            {
                "title": "Short call",
                "start_time": "11:00",
                "end_time": "11:10",
                "category": "Meeting",
                "source": "google",
                "is_fixed": 1,
            },
            {
                "title": "Block most of the morning",
                "start_time": "09:20",
                "end_time": "10:40",
                "category": "Meeting",
                "source": "google",
                "is_fixed": 1,
            },
        ]
        blocks, unscheduled = build_template_schedule(
            PLAN_DATE,
            [_task(1, "Long task", 70, "High"), _task(2, "Quick task", 15, "Low")],
            commitments,
            template_id="balanced",
        )
        screen_break = next(block for block in blocks if block.title == "Screen break")
        quick_task = next(block for block in blocks if block.task_id == 2)
        self.assertFalse(unscheduled)
        self.assertGreaterEqual(minutes_from_time(screen_break.start_time), minutes_from_time("11:10"))
        self.assertLessEqual(minutes_from_time(screen_break.end_time), minutes_from_time("11:30"))
        self.assertEqual(quick_task.start_time, "10:40")

    def test_work_hours_are_scaled_and_invalid_inputs_are_rejected(self) -> None:
        blocks, _ = build_template_schedule(
            PLAN_DATE,
            [_task(1, "Short task", 20)],
            [],
            template_id="early-focus",
            work_start="10:00",
            work_end="14:00",
        )
        self.assertTrue(blocks)
        self.assertTrue(
            all(
                minutes_from_time("10:00") <= minutes_from_time(block.start_time)
                and minutes_from_time(block.end_time) <= minutes_from_time("14:00")
                for block in blocks
            )
        )
        with self.assertRaisesRegex(ValueError, "Unknown schedule template"):
            build_template_schedule(PLAN_DATE, [], [], template_id="not-a-template")
        with self.assertRaisesRegex(ValueError, "later"):
            build_template_schedule(PLAN_DATE, [], [], work_start="17:00", work_end="09:00")
        with self.assertRaisesRegex(ValueError, "negative"):
            build_template_schedule(PLAN_DATE, [], [], buffer_minutes=-1)

    def test_chill_pace_leaves_more_unscheduled_capacity_without_touching_commitments(self) -> None:
        commitments = [
            {
                "title": "Fixed review",
                "start_time": "12:00",
                "end_time": "12:30",
                "category": "Meeting",
                "source": "google",
                "is_fixed": 1,
            }
        ]
        tasks = [_task(index, f"Task {index}", 70) for index in range(1, 6)]
        chill_blocks, chill_unscheduled = build_template_schedule(
            PLAN_DATE, tasks, commitments, pace="Chill"
        )
        heavy_blocks, heavy_unscheduled = build_template_schedule(
            PLAN_DATE, tasks, commitments, pace="Work-heavy"
        )

        self.assertGreaterEqual(len(chill_unscheduled), len(heavy_unscheduled))
        for blocks in (chill_blocks, heavy_blocks):
            review = next(block for block in blocks if block.title == "Fixed review")
            self.assertEqual((review.start_time, review.end_time), ("12:00", "12:30"))
            self.assertTrue(review.is_fixed)


if __name__ == "__main__":
    unittest.main()
