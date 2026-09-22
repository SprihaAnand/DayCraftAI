"""Pure, user-safe shaping for the Insights completion activity calendar.

This module never queries a database or accepts a user identifier. Its input is
the signed-in user's already-scoped daily activity series, and it deliberately
reads only the ``completed_tasks`` value from each record.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class CompletionActivityCell:
    """One displayable day in a fixed-width completion activity calendar."""

    activity_date: date
    week_index: int
    weekday_label: str
    completed_tasks: int
    is_future: bool

    @property
    def date_label(self) -> str:
        """Return a platform-independent, screen-reader-friendly date label."""
        return f"{self.weekday_label}, {self.activity_date.strftime('%b')} {self.activity_date.day}, {self.activity_date.year}"

    @property
    def activity_label(self) -> str:
        """Explain the square without requiring color perception."""
        if self.is_future:
            return "Upcoming day"
        noun = "task" if self.completed_tasks == 1 else "tasks"
        return f"{self.completed_tasks} completed {noun}"


def completion_activity_window(today: date, *, weeks: int = 52) -> tuple[date, date]:
    """Return full Monday-to-Sunday weeks ending with the current week."""
    if weeks < 1:
        raise ValueError("Activity calendar weeks must be at least 1.")
    current_week_start = today - timedelta(days=today.weekday())
    start_date = current_week_start - timedelta(weeks=weeks - 1)
    end_date = start_date + timedelta(days=(weeks * 7) - 1)
    return start_date, end_date


def build_completion_activity_calendar(
    daily_activity: Iterable[Mapping[str, Any]],
    *,
    today: date,
    weeks: int = 52,
) -> list[CompletionActivityCell]:
    """Build dense activity cells using only locally recorded task completions.

    Malformed, future, and out-of-window records are ignored. Duplicate daily
    records are combined so this remains deterministic even if the backing
    query changes from a dense to a sparse series.
    """
    start_date, end_date = completion_activity_window(today, weeks=weeks)
    completions_by_day: dict[date, int] = {}
    for record in daily_activity:
        activity_date = _as_date(record.get("date"))
        completed_tasks = _non_negative_int(record.get("completed_tasks"))
        if activity_date is None or not start_date <= activity_date <= today:
            continue
        completions_by_day[activity_date] = completions_by_day.get(activity_date, 0) + completed_tasks

    cells: list[CompletionActivityCell] = []
    current_date = start_date
    while current_date <= end_date:
        cells.append(
            CompletionActivityCell(
                activity_date=current_date,
                week_index=(current_date - start_date).days // 7,
                weekday_label=WEEKDAY_LABELS[current_date.weekday()],
                completed_tasks=completions_by_day.get(current_date, 0),
                is_future=current_date > today,
            )
        )
        current_date += timedelta(days=1)
    return cells


def _as_date(value: object) -> date | None:
    """Accept the local database's ISO day keys without raising on bad data."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _non_negative_int(value: object) -> int:
    """Keep a malformed counter from corrupting a visual activity scale."""
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
