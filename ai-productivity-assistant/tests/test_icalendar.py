from __future__ import annotations

import re
import unittest

from services.icalendar import (
    MAX_ICALENDAR_BYTES,
    ICalendarError,
    event_fingerprint,
    export_icalendar,
    filter_new_imports,
    parse_icalendar,
)


class ICalendarTests(unittest.TestCase):
    def test_export_is_crlf_folded_timezone_aware_and_uses_a_stable_uid(self) -> None:
        event = {
            "id": 42,
            "title": "Review, plans; and \\ notes",
            "event_date": "2026-09-22",
            "start_time": "09:00",
            "end_time": "10:30",
            "category": "Deep work",
            "location": "Desk, home",
            "notes": "Line one\nLine two",
        }
        payload = export_icalendar([event], timezone_name="Asia/Kolkata")
        repeated = export_icalendar([event], timezone_name="Asia/Kolkata")

        self.assertIn(b"DTSTART;TZID=Asia/Kolkata:20260922T090000", payload)
        self.assertIn(b"SUMMARY:Review\\, plans\\; and \\\\ notes", payload)
        self.assertTrue(payload.endswith(b"\r\n"))
        self.assertNotIn(b"\n", payload.replace(b"\r\n", b""))
        first_uid = re.search(rb"UID:([^\r]+)", payload)
        second_uid = re.search(rb"UID:([^\r]+)", repeated)
        self.assertIsNotNone(first_uid)
        self.assertEqual(first_uid.group(1), second_uid.group(1))  # type: ignore[union-attr]

        parsed = parse_icalendar(payload, timezone_name="Asia/Kolkata")
        self.assertEqual(len(parsed.events), 1)
        imported = parsed.events[0]
        self.assertEqual(imported.title, event["title"])
        self.assertEqual((imported.start_time, imported.end_time), ("09:00", "10:30"))
        self.assertEqual(imported.location, "Desk, home")
        self.assertEqual(imported.notes, "Line one\nLine two")

    def test_export_folds_unicode_content_at_rfc_octet_boundary(self) -> None:
        payload = export_icalendar(
            [
                {
                    "id": 7,
                    "title": "é" * 100,
                    "event_date": "2026-09-22",
                    "start_time": "09:00",
                    "end_time": "09:30",
                }
            ],
            timezone_name="UTC",
        )
        self.assertTrue(all(len(line) <= 75 for line in payload.split(b"\r\n") if line))
        self.assertEqual(len(parse_icalendar(payload).events[0].title), 100)

    def test_import_normalizes_utc_into_the_requested_timezone(self) -> None:
        payload = b"\r\n".join(
            [
                b"BEGIN:VCALENDAR",
                b"VERSION:2.0",
                b"BEGIN:VEVENT",
                b"UID:utc-event",
                b"DTSTART:20260922T033000Z",
                b"DTEND:20260922T043000Z",
                b"SUMMARY:Client\\, review",
                b"LOCATION:Video room",
                b"END:VEVENT",
                b"END:VCALENDAR",
                b"",
            ]
        )
        parsed = parse_icalendar(payload, timezone_name="Asia/Kolkata")

        self.assertEqual(len(parsed.events), 1)
        event = parsed.events[0]
        self.assertEqual(event.event_date.isoformat(), "2026-09-22")
        self.assertEqual((event.start_time, event.end_time), ("09:00", "10:00"))
        self.assertEqual(event.title, "Client, review")

    def test_import_skips_recurrence_cross_day_and_duplicate_source_events(self) -> None:
        payload = b"\r\n".join(
            [
                b"BEGIN:VCALENDAR",
                b"VERSION:2.0",
                b"BEGIN:VEVENT",
                b"UID:repeating",
                b"DTSTART:20260922T090000Z",
                b"DTEND:20260922T100000Z",
                b"RRULE:FREQ=DAILY",
                b"SUMMARY:Recurring",
                b"END:VEVENT",
                b"BEGIN:VEVENT",
                b"UID:cross-day",
                b"DTSTART:20260922T230000Z",
                b"DTEND:20260923T010000Z",
                b"SUMMARY:Cross day",
                b"END:VEVENT",
                b"BEGIN:VEVENT",
                b"UID:real",
                b"DTSTART:20260922T110000Z",
                b"DTEND:20260922T113000Z",
                b"SUMMARY:Safe event",
                b"END:VEVENT",
                b"BEGIN:VEVENT",
                b"UID:same-values-different-uid",
                b"DTSTART:20260922T110000Z",
                b"DTEND:20260922T113000Z",
                b"SUMMARY:Safe event",
                b"END:VEVENT",
                b"END:VCALENDAR",
                b"",
            ]
        )
        parsed = parse_icalendar(payload, timezone_name="UTC")

        self.assertEqual([event.title for event in parsed.events], ["Safe event"])
        self.assertEqual(parsed.skipped_events, 3)

    def test_import_rejects_malformed_or_oversized_files(self) -> None:
        with self.assertRaisesRegex(ICalendarError, "VCALENDAR"):
            parse_icalendar(b"BEGIN:VEVENT\r\nEND:VEVENT\r\n")
        with self.assertRaisesRegex(ICalendarError, "too large"):
            parse_icalendar(b"A" * (MAX_ICALENDAR_BYTES + 1))

    def test_duplicate_filter_uses_local_content_not_untrusted_uid(self) -> None:
        parsed = parse_icalendar(
            b"\r\n".join(
                [
                    b"BEGIN:VCALENDAR",
                    b"BEGIN:VEVENT",
                    b"UID:untrusted-remote-uid",
                    b"DTSTART:20260922T090000Z",
                    b"DTEND:20260922T093000Z",
                    b"SUMMARY:Morning review",
                    b"LOCATION:Desk",
                    b"END:VEVENT",
                    b"END:VCALENDAR",
                    b"",
                ]
            )
        )
        existing = {
            "title": "Morning review",
            "event_date": "2026-09-22",
            "start_time": "09:00",
            "end_time": "09:30",
            "location": "Desk",
        }
        remaining, skipped = filter_new_imports(parsed.events, [existing])

        self.assertEqual(remaining, ())
        self.assertEqual(skipped, 1)
        self.assertEqual(event_fingerprint(parsed.events[0]), event_fingerprint(existing))


if __name__ == "__main__":
    unittest.main()
