"""Small, dependency-free iCalendar import and export helpers for DayCraft.

The module deliberately implements a narrow, safe subset of RFC 5545.  It
creates normal timed VEVENTs for a manual download and accepts only bounded,
non-recurring VEVENTs that can be represented as one local fixed commitment.
It never performs network I/O or invokes an external calendar service.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_ICALENDAR_BYTES = 512 * 1024
MAX_ICALENDAR_EVENTS = 100
MAX_ICALENDAR_LINES = 5_000
MAX_ICALENDAR_LINE_BYTES = 8_192
_MAX_TITLE_LENGTH = 180
_MAX_LOCATION_LENGTH = 240
_MAX_NOTES_LENGTH = 2_000
_RECURRENCE_PROPERTIES = {"RRULE", "RDATE", "EXDATE", "RECURRENCE-ID"}
_PROPERTY_NAME = re.compile(r"^[A-Z0-9-]+$")


class ICalendarError(ValueError):
    """Raised for a malformed, unsafe, or unsupported calendar file."""


@dataclass(frozen=True)
class ImportedEvent:
    """A single safe event ready for review before a database write."""

    uid: str
    title: str
    event_date: date
    start_time: str
    end_time: str
    location: str = ""
    notes: str = ""
    category: str = "Imported"

    @property
    def fingerprint(self) -> str:
        return event_fingerprint(self)


@dataclass(frozen=True)
class ICalendarImport:
    """The parsed, reviewable portion of an uploaded calendar file."""

    events: tuple[ImportedEvent, ...]
    skipped_events: int = 0


def configured_timezone(value: object | None) -> str:
    """Return a usable IANA timezone name without trusting deployment config."""
    candidate = str(value or "UTC").strip() or "UTC"
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return "UTC"
    return candidate


def _zone_for(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ICalendarError("The calendar file uses an unsupported timezone.") from exc


def _parse_iso_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_time(value: object) -> tuple[int, int]:
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return int(value.hour), int(value.minute)
    parsed = str(value).strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", parsed):
        raise ValueError("Invalid local event time")
    hour, minute = parsed.split(":", 1)
    return int(hour), int(minute)


def _escape_text(value: object) -> str:
    text = str(value or "")
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;").replace(",", "\\,")
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def _unescape_text(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character == "\\" and index + 1 < len(value):
            escaped = value[index + 1]
            result.append("\n" if escaped in {"n", "N"} else escaped)
            index += 2
            continue
        result.append(character)
        index += 1
    return "".join(result)


def _safe_text(value: str, *, limit: int, single_line: bool = False) -> str:
    cleaned = "".join(character for character in value if character == "\n" or ord(character) >= 32)
    if single_line:
        cleaned = " ".join(cleaned.split())
    else:
        cleaned = cleaned.strip()
    return cleaned[:limit]


def _fold_line(line: str) -> list[str]:
    """Fold a content line at 75 UTF-8 octets as RFC 5545 requires."""
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    limit = 75
    for character in line:
        character_size = len(character.encode("utf-8"))
        if current and current_size + character_size > limit:
            chunks.append("".join(current))
            current = [character]
            current_size = character_size
            # Continuation lines begin with a literal space, leaving 74 bytes.
            limit = 74
        else:
            current.append(character)
            current_size += character_size
    chunks.append("".join(current))
    return [chunks[0], *(f" {chunk}" for chunk in chunks[1:])]


def _stable_uid(event: Mapping[str, object]) -> str:
    """Create a deterministic UID without exposing a database identifier."""
    if event.get("id") is not None:
        identity = f"id:{event.get('id')}"
    else:
        identity = "|".join(
            str(event.get(name) or "")
            for name in ("event_date", "start_time", "end_time", "title", "location", "source")
        )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    return f"daycraft-{digest}@local.daycraft"


def _event_lines(event: Mapping[str, object], *, timezone_name: str, stamp: str) -> list[str]:
    event_date = _parse_iso_date(event.get("event_date") or "")
    start_hour, start_minute = _parse_time(event.get("start_time") or "")
    end_hour, end_minute = _parse_time(event.get("end_time") or "")
    start = datetime(event_date.year, event_date.month, event_date.day, start_hour, start_minute)
    end = datetime(event_date.year, event_date.month, event_date.day, end_hour, end_minute)
    if end <= start:
        raise ValueError("Event must end after it starts")

    title = _safe_text(str(event.get("title") or "Untitled block"), limit=_MAX_TITLE_LENGTH, single_line=True)
    location = _safe_text(str(event.get("location") or ""), limit=_MAX_LOCATION_LENGTH, single_line=True)
    notes = _safe_text(str(event.get("notes") or ""), limit=_MAX_NOTES_LENGTH)
    category = _safe_text(str(event.get("category") or "DayCraft"), limit=80, single_line=True)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{_stable_uid(event)}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;TZID={timezone_name}:{start.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND;TZID={timezone_name}:{end.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{_escape_text(title)}",
        f"CATEGORIES:{_escape_text(category)}",
        "STATUS:CONFIRMED",
    ]
    if location:
        lines.append(f"LOCATION:{_escape_text(location)}")
    if notes:
        lines.append(f"DESCRIPTION:{_escape_text(notes)}")
    lines.append("END:VEVENT")
    return lines


def export_icalendar(
    events: Iterable[Mapping[str, object]],
    *,
    timezone_name: str = "UTC",
    calendar_name: str = "DayCraft schedule",
) -> bytes:
    """Create a manually downloadable, standards-compliant iCalendar file.

    Invalid local records are skipped rather than producing a malformed file.
    This function only creates bytes; it does not send them anywhere.
    """
    zone_name = configured_timezone(timezone_name)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    display_name = _safe_text(calendar_name, limit=100, single_line=True) or "DayCraft schedule"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DayCraft//Private schedule export//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_text(display_name)}",
        f"X-WR-TIMEZONE:{zone_name}",
    ]
    for event in list(events)[:MAX_ICALENDAR_EVENTS]:
        try:
            lines.extend(_event_lines(event, timezone_name=zone_name, stamp=stamp))
        except (TypeError, ValueError):
            continue
    lines.append("END:VCALENDAR")
    folded = [folded_line for line in lines for folded_line in _fold_line(line)]
    return ("\r\n".join(folded) + "\r\n").encode("utf-8")


def _unfold_lines(payload: bytes) -> list[str]:
    if not payload:
        raise ICalendarError("Choose a non-empty .ics file.")
    if len(payload) > MAX_ICALENDAR_BYTES:
        raise ICalendarError("This .ics file is too large. Upload a file smaller than 512 KB.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ICalendarError("The .ics file must be UTF-8 text.") from exc
    if "\x00" in text:
        raise ICalendarError("The .ics file contains unsupported binary data.")

    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(raw_lines) > MAX_ICALENDAR_LINES:
        raise ICalendarError("This .ics file contains too many lines.")
    unfolded: list[str] = []
    for line in raw_lines:
        if len(line.encode("utf-8")) > MAX_ICALENDAR_LINE_BYTES:
            raise ICalendarError("This .ics file contains an overly long line.")
        if line.startswith((" ", "\t")):
            if not unfolded:
                raise ICalendarError("The .ics file has an invalid folded line.")
            unfolded[-1] += line[1:]
        elif line:
            unfolded.append(line)
    return unfolded


def _split_outside_quotes(value: str, separator: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quoted = False
    for character in value:
        if character == '"':
            quoted = not quoted
        if character == separator and not quoted:
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
    if quoted:
        raise ICalendarError("The .ics file has an unterminated parameter value.")
    parts.append("".join(current))
    return parts


def _parse_content_line(line: str) -> tuple[str, dict[str, str], str]:
    quoted = False
    colon_index = -1
    for index, character in enumerate(line):
        if character == '"':
            quoted = not quoted
        elif character == ":" and not quoted:
            colon_index = index
            break
    if colon_index <= 0:
        raise ICalendarError("The .ics file has an invalid content line.")
    head, value = line[:colon_index], line[colon_index + 1 :]
    parts = _split_outside_quotes(head, ";")
    name = parts[0].upper()
    if not _PROPERTY_NAME.fullmatch(name):
        raise ICalendarError("The .ics file has an invalid property name.")
    parameters: dict[str, str] = {}
    for raw_parameter in parts[1:]:
        if "=" not in raw_parameter:
            raise ICalendarError("The .ics file has an invalid property parameter.")
        parameter_name, parameter_value = raw_parameter.split("=", 1)
        parameter_name = parameter_name.strip().upper()
        if not _PROPERTY_NAME.fullmatch(parameter_name):
            raise ICalendarError("The .ics file has an invalid property parameter.")
        parameters[parameter_name] = parameter_value.strip().strip('"')
    return name, parameters, value


def _parse_temporal(value: str, parameters: Mapping[str, str], target_zone: ZoneInfo) -> tuple[date | datetime, bool]:
    value = value.strip()
    if parameters.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").date(), True
    utc_value = value.endswith("Z")
    raw_value = value[:-1] if utc_value else value
    parsed: datetime | None = None
    for format_string in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            parsed = datetime.strptime(raw_value, format_string)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValueError("Unsupported date-time")
    if utc_value:
        return parsed.replace(tzinfo=UTC).astimezone(target_zone), False
    event_zone = _zone_for(parameters["TZID"]) if parameters.get("TZID") else target_zone
    return parsed.replace(tzinfo=event_zone).astimezone(target_zone), False


def _first(properties: Mapping[str, list[tuple[dict[str, str], str]]], name: str) -> tuple[dict[str, str], str] | None:
    values = properties.get(name)
    return values[0] if values else None


def _event_from_properties(
    properties: Mapping[str, list[tuple[dict[str, str], str]]], target_zone: ZoneInfo
) -> ImportedEvent | None:
    if any(name in properties for name in _RECURRENCE_PROPERTIES):
        return None
    raw_start = _first(properties, "DTSTART")
    raw_end = _first(properties, "DTEND")
    if raw_start is None or raw_end is None:
        return None
    try:
        start, is_all_day_start = _parse_temporal(raw_start[1], raw_start[0], target_zone)
        end, is_all_day_end = _parse_temporal(raw_end[1], raw_end[0], target_zone)
    except (ValueError, ICalendarError):
        return None
    if is_all_day_start != is_all_day_end:
        return None
    if is_all_day_start:
        if not isinstance(start, date) or not isinstance(end, date) or end != start + timedelta(days=1):
            return None
        event_date, start_time, end_time = start, "00:00", "23:59"
    else:
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            return None
        if end <= start or end.date() != start.date():
            # DayCraft records one local day at a time; never truncate a
            # cross-day source event into an incorrect commitment.
            return None
        event_date = start.date()
        start_time = start.strftime("%H:%M")
        end_time = end.strftime("%H:%M")

    summary = _first(properties, "SUMMARY")
    location = _first(properties, "LOCATION")
    description = _first(properties, "DESCRIPTION")
    uid = _first(properties, "UID")
    title = _safe_text(_unescape_text(summary[1]) if summary else "Imported event", limit=_MAX_TITLE_LENGTH, single_line=True)
    if not title:
        title = "Imported event"
    location_text = _safe_text(
        _unescape_text(location[1]) if location else "", limit=_MAX_LOCATION_LENGTH, single_line=True
    )
    notes = _safe_text(_unescape_text(description[1]) if description else "", limit=_MAX_NOTES_LENGTH)
    raw_uid = _safe_text(_unescape_text(uid[1]) if uid else "", limit=240, single_line=True)
    fallback_uid = hashlib.sha256(
        f"{event_date.isoformat()}|{start_time}|{end_time}|{title}|{location_text}".encode()
    ).hexdigest()
    return ImportedEvent(
        uid=raw_uid or f"import-{fallback_uid[:32]}",
        title=title,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location=location_text,
        notes=notes,
    )


def parse_icalendar(payload: bytes, *, timezone_name: str = "UTC") -> ICalendarImport:
    """Parse a bounded, non-recurring VEVENT subset into a reviewable result."""
    target_zone = _zone_for(configured_timezone(timezone_name))
    stack: list[str] = []
    current_event: dict[str, list[tuple[dict[str, str], str]]] | None = None
    accepted: list[ImportedEvent] = []
    seen_fingerprints: set[str] = set()
    skipped = 0
    vevent_count = 0
    saw_calendar = False

    for line in _unfold_lines(payload):
        name, parameters, value = _parse_content_line(line)
        if name == "BEGIN":
            component = value.upper()
            if component == "VCALENDAR":
                if stack or saw_calendar:
                    raise ICalendarError("The .ics file has an invalid calendar structure.")
                saw_calendar = True
            elif not stack:
                raise ICalendarError("The .ics file must begin with VCALENDAR.")
            if component == "VEVENT":
                if current_event is not None:
                    raise ICalendarError("The .ics file nests calendar events.")
                vevent_count += 1
                if vevent_count > MAX_ICALENDAR_EVENTS:
                    raise ICalendarError("This .ics file has more than 100 events.")
                current_event = {}
            stack.append(component)
            continue
        if name == "END":
            component = value.upper()
            if not stack or stack[-1] != component:
                raise ICalendarError("The .ics file has mismatched calendar components.")
            if component == "VEVENT":
                if current_event is None:
                    raise ICalendarError("The .ics file has an invalid event.")
                event = _event_from_properties(current_event, target_zone)
                if event is None or event.fingerprint in seen_fingerprints:
                    skipped += 1
                else:
                    accepted.append(event)
                    seen_fingerprints.add(event.fingerprint)
                current_event = None
            stack.pop()
            continue
        if not stack:
            raise ICalendarError("The .ics file must begin with VCALENDAR.")
        if current_event is not None and stack == ["VCALENDAR", "VEVENT"]:
            current_event.setdefault(name, []).append((parameters, value))

    if stack or not saw_calendar:
        raise ICalendarError("The .ics file is missing a complete VCALENDAR component.")
    return ICalendarImport(events=tuple(accepted), skipped_events=skipped)


def event_fingerprint(event: ImportedEvent | Mapping[str, object]) -> str:
    """Return a content fingerprint used only for local duplicate avoidance."""
    if isinstance(event, ImportedEvent):
        event_date = event.event_date.isoformat()
        title, start_time, end_time, location = event.title, event.start_time, event.end_time, event.location
    else:
        try:
            event_date = _parse_iso_date(event.get("event_date") or "").isoformat()
        except (TypeError, ValueError):
            event_date = str(event.get("event_date") or "")
        title = str(event.get("title") or "")
        start_time = str(event.get("start_time") or "")
        end_time = str(event.get("end_time") or "")
        location = str(event.get("location") or "")
    canonical = "|".join(
        " ".join(value.casefold().split())
        for value in (event_date, title, start_time, end_time, location)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def filter_new_imports(
    candidates: Iterable[ImportedEvent], existing_events: Iterable[Mapping[str, object]]
) -> tuple[tuple[ImportedEvent, ...], int]:
    """Remove duplicate imported events and report how many were withheld."""
    known = {event_fingerprint(event) for event in existing_events}
    result: list[ImportedEvent] = []
    skipped = 0
    for candidate in candidates:
        fingerprint = candidate.fingerprint
        if fingerprint in known:
            skipped += 1
            continue
        known.add(fingerprint)
        result.append(candidate)
    return tuple(result), skipped
