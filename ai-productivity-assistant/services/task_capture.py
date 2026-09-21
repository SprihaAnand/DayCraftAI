"""Safe, deterministic parsing for DayCraft's quick task capture.

The quick-capture field is deliberately not an agent or an instruction runner.
It only extracts a small, reviewable set of tasks and same-day commitments from
plain language.  A person must review and explicitly confirm every item before
anything is written to the database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CAPTURE_CHARS = 4_000
MAX_CAPTURE_ITEMS = 20
MAX_TITLE_CHARS = 140
MIN_DURATION_MINUTES = 5
MAX_TASK_MINUTES = 480
MAX_COMMITMENT_MINUTES = 720


@dataclass(frozen=True)
class CapturedTask:
    """A flexible item that the normal planner may place around commitments."""

    title: str
    estimated_minutes: int
    category: str = "General"
    priority: str = "Medium"
    notes: str = ""
    source_text: str = ""


@dataclass(frozen=True)
class CapturedCommitment:
    """A protected, same-day time block discovered from an explicit time cue."""

    title: str
    start_time: str
    end_time: str
    category: str = "General"
    source_text: str = ""


@dataclass(frozen=True)
class TaskCapturePreview:
    """The bounded output shown to a person before a quick capture is saved."""

    tasks: tuple[CapturedTask, ...] = ()
    commitments: tuple[CapturedCommitment, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def item_count(self) -> int:
        return len(self.tasks) + len(self.commitments)


@dataclass(frozen=True)
class _Clock:
    hour: int
    minute: int
    meridiem: str | None

    @property
    def uses_24_hour_value(self) -> bool:
        return self.hour > 12


_TIME = r"(?:(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?)?)"
_RANGE = re.compile(
    rf"^(?P<title>.+?)\s+(?:from|between)\s+(?P<start>{_TIME})\s*(?:to|until|[-–])\s*(?P<end>{_TIME})\s*$",
    re.IGNORECASE,
)
_DURATION = (
    r"(?:a\s+half\s+hour|half(?:\s+an?)?\s+hour|half-hour|"
    r"a\s+quarter\s+hour|quarter(?:\s+of\s+an?)?\s+hour|"
    r"an?\s+hour|one\s+hour|two\s+hours?|three\s+hours?|"
    r"\d+(?:\.\d+)?\s*(?:minutes?|mins?|min|m|hours?|hrs?|hr|h))"
)
_AT_FOR = re.compile(
    rf"^(?P<title>.+?)\s+(?:at|@)\s+(?P<start>{_TIME})\s+(?:for\s+)?(?P<duration>{_DURATION})\s*$",
    re.IGNORECASE,
)
_AT_WITHOUT_DURATION = re.compile(
    rf"^(?P<title>.+?)\s+(?:at|@)\s+(?P<start>{_TIME})\s*$",
    re.IGNORECASE,
)
_CLOCK = re.compile(
    r"^(?P<hour>[01]?\d|2[0-3])(?::(?P<minute>[0-5]\d))?\s*(?P<meridiem>a\.?m\.?|p\.?m\.?)?$",
    re.IGNORECASE,
)
_ITEM_SPLIT = re.compile(r"(?:\r?\n|[;,•])+", re.MULTILINE)
_LEADING_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s*")
_LEADING_TASKS = re.compile(r"^\s*(?:tasks?|today|plan)\s*:\s*", re.IGNORECASE)
# Keep line breaks intact because they are a supported item separator; strip
# the remaining non-printing control characters before parsing.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")


def parse_task_capture(raw_text: str) -> TaskCapturePreview:
    """Create a reviewable quick-capture preview without side effects.

    A time becomes a protected commitment only with an unambiguous same-day
    range (``lunch from 1 to 2``) or a start plus duration (``meeting at 9 for
    half an hour``).  Everything else remains a flexible task.  This avoids
    guessing calendar blocks from vague language such as ``call at 9``.
    """
    if not isinstance(raw_text, str):
        return TaskCapturePreview(warnings=("Enter tasks as plain text before reviewing them.",))

    clean_text = _clean_input(raw_text)
    if not clean_text:
        return TaskCapturePreview(warnings=("Add at least one task or timed commitment to review.",))

    warnings: list[str] = []
    if len(clean_text) > MAX_CAPTURE_CHARS:
        clean_text = clean_text[:MAX_CAPTURE_CHARS]
        warnings.append(
            f"Only the first {MAX_CAPTURE_CHARS:,} characters were reviewed. Split a longer list into smaller captures."
        )

    clauses = _split_clauses(clean_text)
    if len(clauses) > MAX_CAPTURE_ITEMS:
        skipped = len(clauses) - MAX_CAPTURE_ITEMS
        clauses = clauses[:MAX_CAPTURE_ITEMS]
        warnings.append(
            f"Only the first {MAX_CAPTURE_ITEMS} items were reviewed; {skipped} additional item(s) were left out."
        )

    tasks: list[CapturedTask] = []
    commitments: list[CapturedCommitment] = []
    for clause in clauses:
        item, item_warning = _parse_clause(clause)
        if item_warning:
            warnings.append(item_warning)
        if isinstance(item, CapturedTask):
            tasks.append(item)
        elif isinstance(item, CapturedCommitment):
            commitments.append(item)

    if not tasks and not commitments:
        warnings.append("No usable tasks were found. Try a comma-separated list such as ‘write brief, lunch from 1 to 2’.")
    return TaskCapturePreview(tuple(tasks), tuple(commitments), tuple(warnings))


def _clean_input(value: str) -> str:
    """Bound control characters and normalize whitespace before parsing."""
    return _CONTROL_CHARACTERS.sub(" ", value).strip()


def _split_clauses(value: str) -> list[str]:
    clauses: list[str] = []
    for index, part in enumerate(_ITEM_SPLIT.split(value)):
        part = _LEADING_BULLET.sub("", part).strip()
        if index == 0:
            part = _LEADING_TASKS.sub("", part).strip()
        if part:
            clauses.append(part)
    return clauses


def _parse_clause(clause: str) -> tuple[CapturedTask | CapturedCommitment | None, str | None]:
    """Parse one bounded phrase and keep ambiguity visible to the reviewer."""
    range_match = _RANGE.match(clause)
    if range_match:
        title = _safe_title(range_match.group("title"))
        if not title:
            return None, f"Skipped an untitled timed item: ‘{_display_clause(clause)}’."
        try:
            start, end = _same_day_range(
                range_match.group("start"), range_match.group("end"), title
            )
        except ValueError:
            return _task_from_title(title, clause), (
                f"‘{_display_clause(clause)}’ was kept as a flexible task because its time range was unclear."
            )
        return _commitment_from_title(title, start, end, clause), None

    at_for_match = _AT_FOR.match(clause)
    if at_for_match:
        title = _safe_title(at_for_match.group("title"))
        if not title:
            return None, f"Skipped an untitled timed item: ‘{_display_clause(clause)}’."
        try:
            start = _default_minutes(_parse_clock(at_for_match.group("start")), title)
            duration = _duration_minutes(at_for_match.group("duration"))
            end = start + duration
            if end > 24 * 60 or not MIN_DURATION_MINUTES <= duration <= MAX_COMMITMENT_MINUTES:
                raise ValueError("duration outside same-day bounds")
        except ValueError:
            return _task_from_title(title, clause), (
                f"‘{_display_clause(clause)}’ was kept as a flexible task because its time was unclear."
            )
        return _commitment_from_title(title, start, end, clause), None

    at_match = _AT_WITHOUT_DURATION.match(clause)
    if at_match:
        title = _safe_title(at_match.group("title"))
        if not title:
            return None, f"Skipped an untitled item: ‘{_display_clause(clause)}’."
        return _task_from_title(title, clause), (
            f"‘{_display_clause(clause)}’ mentions a time but no duration, so it stays flexible until you set one."
        )

    title = _safe_title(clause)
    if not title:
        return None, f"Skipped an empty item: ‘{_display_clause(clause)}’."
    return _task_from_title(title, clause), None


def _safe_title(value: str) -> str:
    title = re.sub(r"\s+", " ", value).strip(" -–—:;,.\t")
    if len(title) > MAX_TITLE_CHARS:
        title = title[:MAX_TITLE_CHARS].rstrip()
    return title


def _display_clause(value: str) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    return compact[:MAX_TITLE_CHARS]


def _parse_clock(value: str) -> _Clock:
    normalized = value.lower().replace(".", "").strip()
    match = _CLOCK.fullmatch(normalized)
    if not match:
        raise ValueError("unsupported time")
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    meridiem = match.group("meridiem")
    if meridiem:
        meridiem = meridiem.replace(".", "")
        if not 1 <= hour <= 12:
            raise ValueError("12-hour clock value is invalid")
    return _Clock(hour=hour, minute=minute, meridiem=meridiem)


def _clock_minutes(clock: _Clock) -> int:
    if clock.meridiem == "am":
        hour = 0 if clock.hour == 12 else clock.hour
    elif clock.meridiem == "pm":
        hour = 12 if clock.hour == 12 else clock.hour + 12
    else:
        hour = clock.hour
    return hour * 60 + clock.minute


def _candidate_minutes(clock: _Clock) -> list[int]:
    if clock.meridiem or clock.uses_24_hour_value:
        return [_clock_minutes(clock)]
    if clock.hour == 12:
        return [0 + clock.minute, 12 * 60 + clock.minute]
    if clock.hour == 0:
        return [clock.minute]
    return [clock.hour * 60 + clock.minute, (clock.hour + 12) * 60 + clock.minute]


def _default_minutes(clock: _Clock, title: str) -> int:
    """Choose a conservative daytime interpretation for a time without am/pm."""
    candidates = _candidate_minutes(clock)
    if len(candidates) == 1:
        return candidates[0]
    lower_title = title.lower()
    if any(word in lower_title for word in ("lunch", "brunch", "dinner", "meal")):
        # Noon-ish meal names make “lunch from 1 to 2” unambiguous enough to
        # preview as 13:00–14:00; the person can still edit it before saving.
        return candidates[-1]
    return candidates[0]


def _same_day_range(start_value: str, end_value: str, title: str) -> tuple[int, int]:
    start_clock = _parse_clock(start_value)
    end_clock = _parse_clock(end_value)
    start = _default_minutes(start_clock, title)
    end_candidates = _candidate_minutes(end_clock)
    valid_ends = [
        candidate
        for candidate in end_candidates
        if MIN_DURATION_MINUTES <= candidate - start <= MAX_COMMITMENT_MINUTES
    ]
    if not valid_ends:
        raise ValueError("not a same-day range")
    return start, min(valid_ends)


def _duration_minutes(value: str) -> int:
    normalized = re.sub(r"\s+", " ", value.lower().strip())
    named = {
        "a half hour": 30,
        "half hour": 30,
        "half an hour": 30,
        "half-hour": 30,
        "a quarter hour": 15,
        "quarter hour": 15,
        "quarter of an hour": 15,
        "an hour": 60,
        "a hour": 60,
        "one hour": 60,
        "two hours": 120,
        "three hours": 180,
    }
    if normalized in named:
        return named[normalized]
    match = re.fullmatch(
        r"(?P<count>\d+(?:\.\d+)?)\s*(?P<unit>minutes?|mins?|min|m|hours?|hrs?|hr|h)",
        normalized,
    )
    if not match:
        raise ValueError("unsupported duration")
    count = float(match.group("count"))
    unit = match.group("unit")
    minutes = round(count * 60) if unit.startswith(("h", "hr")) else round(count)
    if not MIN_DURATION_MINUTES <= minutes <= MAX_COMMITMENT_MINUTES:
        raise ValueError("duration outside allowed range")
    return minutes


def _category_for(title: str) -> str:
    normalized = title.lower()
    if any(word in normalized for word in ("workout", "gym", "run", "yoga", "walk", "exercise")):
        return "Health"
    if any(word in normalized for word in ("read", "study", "course", "learn", "pages", "book")):
        return "Learning"
    if any(word in normalized for word in ("lunch", "dinner", "breakfast", "meal", "personal")):
        return "Personal"
    if any(word in normalized for word in ("meeting", "call", "review", "client", "standup")):
        return "Work"
    if any(word in normalized for word in ("email", "inbox", "admin", "invoice", "follow up")):
        return "Admin"
    if any(word in normalized for word in ("write", "draft", "build", "code", "design", "research")):
        return "Deep work"
    return "General"


def _default_duration_for(title: str) -> int:
    normalized = title.lower()
    if any(word in normalized for word in ("workout", "gym", "run", "yoga", "exercise")):
        return 45
    if any(word in normalized for word in ("read", "study", "course", "learn", "pages", "book")):
        return 30
    if any(word in normalized for word in ("lunch", "dinner", "breakfast", "meal")):
        return 60
    if any(word in normalized for word in ("write", "draft", "build", "code", "design", "research")):
        return 60
    if any(word in normalized for word in ("meeting", "call", "email", "admin", "follow up")):
        return 30
    return 30


def _priority_for(title: str) -> str:
    normalized = title.lower()
    return "High" if any(word in normalized for word in ("urgent", "asap", "critical", "must")) else "Medium"


def _task_from_title(title: str, source_text: str) -> CapturedTask:
    return CapturedTask(
        title=title,
        estimated_minutes=_default_duration_for(title),
        category=_category_for(title),
        priority=_priority_for(title),
        source_text=source_text,
    )


def _commitment_from_title(
    title: str, start_minutes: int, end_minutes: int, source_text: str
) -> CapturedCommitment:
    return CapturedCommitment(
        title=title,
        start_time=_time_string(start_minutes),
        end_time=_time_string(end_minutes),
        category=_category_for(title),
        source_text=source_text,
    )


def _time_string(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
