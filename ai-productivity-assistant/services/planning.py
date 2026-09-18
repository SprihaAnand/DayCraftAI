"""Deterministic schedule building that safely turns tasks into real time blocks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

PRIORITY_WEIGHT = {"High": 0, "Medium": 1, "Low": 2}


@dataclass(frozen=True)
class ScheduleBlock:
    title: str
    start_time: str
    end_time: str
    category: str
    source: str
    task_id: int | None = None
    is_fixed: bool = False
    # The source tells persistence where a block came from.  This field makes
    # it possible for a UI to distinguish a calendar commitment, a template
    # anchor, and a task without inferring that information from the title.
    block_type: str = "task"

    @property
    def duration_minutes(self) -> int:
        return minutes_from_time(self.end_time) - minutes_from_time(self.start_time)


def minutes_from_time(value: str) -> int:
    """Convert a HH:MM storage value to minutes since midnight."""
    hour, minute = value.split(":", 1)
    result = int(hour) * 60 + int(minute)
    if not 0 <= result <= 24 * 60:
        raise ValueError(f"Invalid time: {value}")
    return result


def time_from_minutes(value: int) -> str:
    value = max(0, min(value, 24 * 60))
    return f"{value // 60:02d}:{value % 60:02d}"


def task_sort_key(task: dict[str, Any]) -> tuple[int, int, str, int]:
    due_date = task.get("due_date") or "9999-12-31"
    return (
        PRIORITY_WEIGHT.get(str(task.get("priority")), 3),
        0 if due_date != "9999-12-31" else 1,
        str(due_date),
        int(task["id"]),
    )


@dataclass(frozen=True)
class TemplateDivision:
    """One named portion of a reusable workday template.

    ``kind`` is either ``"task"`` (a window in which work can be placed) or
    ``"anchor"`` (a named break or planning ritual that should reserve time).
    Anchor divisions may move by ``flex_minutes`` when a real commitment is in
    their preferred slot, but are never allowed to overlap it.
    """

    title: str
    start_time: str
    end_time: str
    category: str
    kind: str
    flex_minutes: int = 0


@dataclass(frozen=True)
class ScheduleTemplate:
    """A deterministic day shape that can be used without an AI provider."""

    id: str
    name: str
    description: str
    default_work_start: str
    default_work_end: str
    divisions: tuple[TemplateDivision, ...]


SCHEDULE_TEMPLATES: tuple[ScheduleTemplate, ...] = (
    ScheduleTemplate(
        id="balanced",
        name="Balanced day",
        description="Two focus windows, a collaboration block, and a calm closeout.",
        default_work_start="09:00",
        default_work_end="17:30",
        divisions=(
            TemplateDivision("Set direction", "09:00", "09:20", "Planning", "anchor", 15),
            TemplateDivision("Morning focus", "09:20", "11:00", "Deep work", "task"),
            TemplateDivision("Screen break", "11:00", "11:15", "Break", "anchor", 20),
            TemplateDivision("Collaboration", "11:15", "12:30", "Collaboration", "task"),
            TemplateDivision("Lunch reset", "12:30", "13:15", "Break", "anchor", 45),
            TemplateDivision("Afternoon focus", "13:15", "15:00", "Deep work", "task"),
            TemplateDivision("Admin and follow-ups", "15:00", "16:15", "Admin", "task"),
            TemplateDivision("Recharge", "16:15", "16:30", "Break", "anchor", 20),
            TemplateDivision("Close the loop", "16:30", "17:30", "Admin", "task"),
        ),
    ),
    ScheduleTemplate(
        id="deep-work",
        name="Deep work day",
        description="Longer uninterrupted focus sprints with deliberate recovery time.",
        default_work_start="09:00",
        default_work_end="17:30",
        divisions=(
            TemplateDivision("Daily map", "09:00", "09:15", "Planning", "anchor", 15),
            TemplateDivision("Focus sprint one", "09:15", "11:00", "Deep work", "task"),
            TemplateDivision("Walk and recover", "11:00", "11:20", "Break", "anchor", 25),
            TemplateDivision("Focus sprint two", "11:20", "12:45", "Deep work", "task"),
            TemplateDivision("Lunch reset", "12:45", "13:30", "Break", "anchor", 45),
            TemplateDivision("Focus sprint three", "13:30", "15:15", "Deep work", "task"),
            TemplateDivision("Reset", "15:15", "15:30", "Break", "anchor", 20),
            TemplateDivision("Light admin", "15:30", "16:15", "Admin", "task"),
            TemplateDivision("Close the loop", "16:15", "17:30", "Admin", "task"),
        ),
    ),
    ScheduleTemplate(
        id="meeting-day",
        name="Meeting day",
        description="Collaboration windows, note buffers, and protected action time.",
        default_work_start="09:00",
        default_work_end="17:30",
        divisions=(
            TemplateDivision("Open and prioritise", "09:00", "09:20", "Planning", "anchor", 15),
            TemplateDivision("Collaboration window one", "09:20", "10:30", "Meetings", "task"),
            TemplateDivision("Notes buffer", "10:30", "10:45", "Break", "anchor", 20),
            TemplateDivision("Meeting window", "10:45", "12:00", "Meetings", "task"),
            TemplateDivision("Lunch reset", "12:00", "12:45", "Break", "anchor", 45),
            TemplateDivision("Meeting window two", "12:45", "14:00", "Meetings", "task"),
            TemplateDivision("Action work", "14:00", "15:00", "Follow-up", "task"),
            TemplateDivision("Reset", "15:00", "15:15", "Break", "anchor", 20),
            TemplateDivision("Follow-ups", "15:15", "16:30", "Follow-up", "task"),
            TemplateDivision("Close the loop", "16:30", "17:30", "Admin", "task"),
        ),
    ),
    ScheduleTemplate(
        id="early-focus",
        name="Early focus",
        description="An early start for high-value focus before collaboration begins.",
        default_work_start="07:30",
        default_work_end="16:00",
        divisions=(
            TemplateDivision("Start ritual", "07:30", "07:45", "Planning", "anchor", 15),
            TemplateDivision("Sunrise focus", "07:45", "09:45", "Deep work", "task"),
            TemplateDivision("Move", "09:45", "10:00", "Break", "anchor", 20),
            TemplateDivision("Focus before lunch", "10:00", "11:30", "Deep work", "task"),
            TemplateDivision("Lunch reset", "11:30", "12:15", "Break", "anchor", 45),
            TemplateDivision("Collaboration", "12:15", "13:30", "Collaboration", "task"),
            TemplateDivision("Admin and follow-ups", "13:30", "15:15", "Admin", "task"),
            TemplateDivision("Close the loop", "15:15", "16:00", "Planning", "anchor", 20),
        ),
    ),
)


def list_schedule_templates() -> tuple[ScheduleTemplate, ...]:
    """Return the built-in templates in the order they should be shown in a UI."""
    return SCHEDULE_TEMPLATES


def get_schedule_template(template_id: str) -> ScheduleTemplate:
    """Resolve a template id and raise a clear error for an unknown option."""
    normalized_id = str(template_id).strip().lower().replace("_", "-")
    for template in SCHEDULE_TEMPLATES:
        if template.id == normalized_id:
            return template
    available = ", ".join(template.id for template in SCHEDULE_TEMPLATES)
    raise ValueError(f"Unknown schedule template '{template_id}'. Choose one of: {available}.")


def template_default_work_hours(template_id: str) -> tuple[str, str]:
    """Return the default start and end times for a schedule template."""
    template = get_schedule_template(template_id)
    return template.default_work_start, template.default_work_end


def _scaled_template_interval(
    division: TemplateDivision,
    template: ScheduleTemplate,
    work_start: int,
    work_end: int,
) -> tuple[int, int]:
    """Scale a template division when a user chooses different working hours."""
    template_start = minutes_from_time(template.default_work_start)
    template_end = minutes_from_time(template.default_work_end)
    template_span = template_end - template_start
    actual_span = work_end - work_start
    division_start = minutes_from_time(division.start_time)
    division_end = minutes_from_time(division.end_time)
    start = work_start + round((division_start - template_start) * actual_span / template_span)
    end = work_start + round((division_end - template_start) * actual_span / template_span)
    return max(work_start, start), min(work_end, max(start, end))


def _free_intervals(
    start: int, end: int, occupied: list[ScheduleBlock]
) -> list[tuple[int, int]]:
    """Return all real gaps after clipping occupied blocks to a workday window."""
    intervals: list[tuple[int, int]] = []
    for block in occupied:
        block_start = max(start, minutes_from_time(block.start_time))
        block_end = min(end, minutes_from_time(block.end_time))
        if block_start < block_end:
            intervals.append((block_start, block_end))
    intervals.sort()

    free: list[tuple[int, int]] = []
    cursor = start
    for block_start, block_end in intervals:
        if block_start > cursor:
            free.append((cursor, block_start))
        cursor = max(cursor, block_end)
    if cursor < end:
        free.append((cursor, end))
    return free


def _fixed_blocks_for_window(
    existing_events: list[dict[str, Any]], start: int, end: int
) -> list[ScheduleBlock]:
    """Normalize external commitments without changing their stored details."""
    blocks: list[ScheduleBlock] = []
    for event in existing_events:
        try:
            event_start = max(start, minutes_from_time(str(event["start_time"])))
            event_end = min(end, minutes_from_time(str(event["end_time"])))
        except (KeyError, TypeError, ValueError):
            continue
        if event_start >= event_end:
            continue
        blocks.append(
            ScheduleBlock(
                title=str(event.get("title") or "Untitled commitment"),
                start_time=time_from_minutes(event_start),
                end_time=time_from_minutes(event_end),
                category=str(event.get("category") or "Calendar"),
                source=str(event.get("source") or "calendar"),
                is_fixed=bool(event.get("is_fixed")),
                block_type="fixed",
            )
        )
    return blocks


def _place_template_anchor(
    division: TemplateDivision,
    preferred_start: int,
    preferred_end: int,
    work_start: int,
    work_end: int,
    occupied: list[ScheduleBlock],
) -> ScheduleBlock | None:
    """Reserve a named template anchor in the nearest real free interval."""
    duration = preferred_end - preferred_start
    if duration <= 0:
        return None

    earliest_start = max(work_start, preferred_start - division.flex_minutes)
    latest_start = min(work_end - duration, preferred_start + division.flex_minutes)
    if earliest_start > latest_start:
        return None

    candidates: list[tuple[int, int]] = []
    for free_start, free_end in _free_intervals(work_start, work_end, occupied):
        earliest_in_gap = max(free_start, earliest_start)
        latest_in_gap = min(free_end - duration, latest_start)
        if earliest_in_gap > latest_in_gap:
            continue
        preferred_in_gap = min(max(preferred_start, earliest_in_gap), latest_in_gap)
        candidates.append((abs(preferred_in_gap - preferred_start), preferred_in_gap))

    if not candidates:
        return None
    _, anchor_start = min(candidates)
    return ScheduleBlock(
        title=division.title,
        start_time=time_from_minutes(anchor_start),
        end_time=time_from_minutes(anchor_start + duration),
        category=division.category,
        source="planner",
        is_fixed=False,
        block_type="template_anchor",
    )


def _open_tasks_for_date(
    selected_date: date, tasks: list[dict[str, Any]], task_order: list[int] | None = None
) -> list[dict[str, Any]]:
    """Use the same overdue-and-due-today rule as the standard daily planner."""
    open_tasks = [
        task
        for task in tasks
        if task.get("status") != "completed"
        and (not task.get("due_date") or str(task["due_date"]) <= selected_date.isoformat())
    ]
    if not task_order:
        return sorted(open_tasks, key=task_sort_key)

    order_index = {task_id: index for index, task_id in enumerate(task_order)}
    return sorted(
        open_tasks,
        key=lambda task: (order_index.get(int(task["id"]), len(order_index)), task_sort_key(task)),
    )


def build_template_schedule(
    selected_date: date,
    tasks: list[dict[str, Any]],
    existing_events: list[dict[str, Any]],
    *,
    template_id: str = "balanced",
    work_start: str | None = None,
    work_end: str | None = None,
    buffer_minutes: int = 10,
    task_order: list[int] | None = None,
) -> tuple[list[ScheduleBlock], list[dict[str, Any]]]:
    """Build a time-boxed daily plan from a reusable template.

    The template supplies predictable focus, collaboration, and recovery
    divisions.  Existing events always win: anchors can move only within their
    small configured flexibility window, and task blocks use only the genuine
    remaining gaps.  Every generated block uses ``source='planner'`` so it can
    be persisted through the existing planner-event path.  A generated break
    or ritual has ``block_type='template_anchor'`` and no ``task_id``; work
    placed for a task has ``block_type='task'`` and that task's id.  When
    supplied, ``task_order`` is honored first, so an AI can choose the order
    while this deterministic engine remains responsible for safe timing.
    """
    if buffer_minutes < 0:
        raise ValueError("Buffer minutes cannot be negative.")

    template = get_schedule_template(template_id)
    start_value = work_start or template.default_work_start
    end_value = work_end or template.default_work_end
    start_of_day = minutes_from_time(start_value)
    end_of_day = minutes_from_time(end_value)
    if start_of_day >= end_of_day:
        raise ValueError("Workday end must be later than workday start.")

    fixed_blocks = _fixed_blocks_for_window(existing_events, start_of_day, end_of_day)
    template_intervals = [
        (division, *_scaled_template_interval(division, template, start_of_day, end_of_day))
        for division in template.divisions
    ]

    anchors: list[ScheduleBlock] = []
    occupied = [*fixed_blocks]
    for division, division_start, division_end in template_intervals:
        if division.kind != "anchor":
            continue
        anchor = _place_template_anchor(
            division,
            division_start,
            division_end,
            start_of_day,
            end_of_day,
            occupied,
        )
        if anchor is not None:
            anchors.append(anchor)
            occupied.append(anchor)

    task_slots: list[tuple[int, int, TemplateDivision]] = []
    for division, division_start, division_end in template_intervals:
        if division.kind != "task" or division_start >= division_end:
            continue
        for free_start, free_end in _free_intervals(division_start, division_end, occupied):
            task_slots.append((free_start, free_end, division))
    task_slots.sort(key=lambda slot: (slot[0], slot[1]))

    proposed: list[ScheduleBlock] = []
    unscheduled: list[dict[str, Any]] = []
    for task in _open_tasks_for_date(selected_date, tasks, task_order):
        duration = max(10, int(task.get("estimated_minutes") or 30))
        placed = False
        for slot_index, (slot_start, slot_end, division) in enumerate(task_slots):
            if slot_end - slot_start >= duration:
                proposed.append(
                    ScheduleBlock(
                        title=str(task.get("title") or "Untitled task"),
                        start_time=time_from_minutes(slot_start),
                        end_time=time_from_minutes(slot_start + duration),
                        category=division.title,
                        source="planner",
                        task_id=int(task["id"]),
                        is_fixed=False,
                        block_type="task",
                    )
                )
                next_start = slot_start + duration + buffer_minutes
                if next_start >= slot_end:
                    task_slots.pop(slot_index)
                else:
                    task_slots[slot_index] = (next_start, slot_end, division)
                placed = True
                break
        if not placed:
            unscheduled.append(task)

    return (
        sorted(
            [*fixed_blocks, *anchors, *proposed],
            key=lambda block: (minutes_from_time(block.start_time), minutes_from_time(block.end_time)),
        ),
        unscheduled,
    )


def build_daily_plan(
    selected_date: date,
    tasks: list[dict[str, Any]],
    existing_events: list[dict[str, Any]],
    *,
    work_start: str = "09:00",
    work_end: str = "17:30",
    buffer_minutes: int = 10,
    task_order: list[int] | None = None,
) -> tuple[list[ScheduleBlock], list[dict[str, Any]]]:
    """Fit incomplete tasks into real gaps around existing calendar events.

    It never fabricates calendar time: existing events retain their stored time,
    and every proposed task block comes from a verified free interval.
    """
    start_of_day = minutes_from_time(work_start)
    end_of_day = minutes_from_time(work_end)
    if start_of_day >= end_of_day:
        raise ValueError("Workday end must be later than workday start.")

    occupied: list[ScheduleBlock] = []
    for event in existing_events:
        try:
            event_start = max(start_of_day, minutes_from_time(str(event["start_time"])))
            event_end = min(end_of_day, minutes_from_time(str(event["end_time"])))
        except (KeyError, ValueError):
            continue
        if event_start >= event_end:
            continue
        occupied.append(
            ScheduleBlock(
                title=str(event["title"]),
                start_time=time_from_minutes(event_start),
                end_time=time_from_minutes(event_end),
                category=str(event.get("category") or "Calendar"),
                source=str(event.get("source") or "calendar"),
                is_fixed=bool(event.get("is_fixed")),
                block_type="fixed",
            )
        )
    occupied.sort(key=lambda block: (minutes_from_time(block.start_time), minutes_from_time(block.end_time)))

    free_slots: list[tuple[int, int]] = []
    cursor = start_of_day
    for block in occupied:
        block_start = minutes_from_time(block.start_time)
        block_end = minutes_from_time(block.end_time)
        if block_start > cursor:
            free_slots.append((cursor, block_start))
        cursor = max(cursor, block_end)
    if cursor < end_of_day:
        free_slots.append((cursor, end_of_day))

    open_tasks = [
        task
        for task in tasks
        if task.get("status") != "completed"
        and (not task.get("due_date") or str(task["due_date"]) <= selected_date.isoformat())
    ]
    if task_order:
        order_index = {task_id: index for index, task_id in enumerate(task_order)}
        open_tasks.sort(
            key=lambda task: (order_index.get(int(task["id"]), len(order_index)), task_sort_key(task))
        )
    else:
        open_tasks.sort(key=task_sort_key)

    proposed: list[ScheduleBlock] = []
    unscheduled: list[dict[str, Any]] = []
    slot_index = 0
    for task in open_tasks:
        duration = max(10, int(task.get("estimated_minutes") or 30))
        placed = False
        while slot_index < len(free_slots):
            slot_start, slot_end = free_slots[slot_index]
            if slot_end - slot_start >= duration:
                block_end = slot_start + duration
                proposed.append(
                    ScheduleBlock(
                        title=str(task["title"]),
                        start_time=time_from_minutes(slot_start),
                        end_time=time_from_minutes(block_end),
                        category=str(task.get("category") or "General"),
                        source="planner",
                        task_id=int(task["id"]),
                    )
                )
                free_slots[slot_index] = (block_end + buffer_minutes, slot_end)
                if free_slots[slot_index][0] >= slot_end:
                    slot_index += 1
                placed = True
                break
            slot_index += 1
        if not placed:
            unscheduled.append(task)

    return sorted([*occupied, *proposed], key=lambda block: minutes_from_time(block.start_time)), unscheduled


def plan_as_markdown(blocks: list[ScheduleBlock], unscheduled: list[dict[str, Any]]) -> str:
    lines = ["## Day plan", ""]
    if blocks:
        lines.extend(
            f"- **{block.start_time}–{block.end_time}** · {block.title} ({block.category})"
            for block in blocks
        )
    else:
        lines.append("No commitments or task blocks are scheduled yet.")
    if unscheduled:
        lines.extend(["", "### Still to place", *[f"- {task['title']}" for task in unscheduled]])
    return "\n".join(lines)
