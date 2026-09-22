"""Bounded, side-effect-free support for DayCraft's AI Inbox.

This module accepts a single uploaded document only long enough to validate it
and pass it to Gemini in memory.  It never writes source bytes to the database,
filesystem, session state, or logs.  Gemini's response is separately parsed
into the same small review model used by typed quick capture.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePath

from services.task_capture import CapturedCommitment, CapturedTask, TaskCapturePreview

MAX_INBOX_FILE_BYTES = 5 * 1024 * 1024
MAX_INBOX_TEXT_CHARACTERS = 30_000
MAX_INBOX_PDF_PAGES = 25
MAX_INBOX_CANDIDATES = 16
MAX_INBOX_TASKS = 12
MAX_INBOX_COMMITMENTS = 12
MAX_INBOX_TITLE_CHARS = 140
MAX_INBOX_NOTES_CHARS = 500

TASK_CATEGORIES = {"General", "Deep work", "Work", "Personal", "Learning", "Admin", "Health"}
COMMITMENT_CATEGORIES = {"General", "Work", "Meetings", "Personal", "Learning", "Admin", "Health"}
PRIORITIES = {"High", "Medium", "Low"}

_PDF_HEADER = b"%PDF-"
_PNG_HEADER = b"\x89PNG\r\n\x1a\n"
_JPEG_HEADER = b"\xff\xd8\xff"
_WEBP_HEADER = b"RIFF"
_PDF_PAGE_MARKER = re.compile(rb"/Type\s*/Page\b")
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")

_EXTENSION_KIND = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".txt": "text",
    ".md": "text",
    ".markdown": "text",
}
_ALLOWED_DECLARED_TYPES = {
    "pdf": {"application/pdf"},
    "image": {"image/png", "image/jpeg", "image/webp"},
    "text": {"text/plain", "text/markdown", "text/x-markdown"},
}


class InboxUploadError(ValueError):
    """A concise user-facing error for an unsupported or unsafe upload."""


@dataclass(frozen=True)
class InboxAttachment:
    """A validated attachment kept only in process memory for one AI request."""

    filename: str
    mime_type: str
    kind: str
    content: bytes = field(repr=False)
    text_content: str | None = field(default=None, repr=False)
    pdf_page_count: int | None = None

    @property
    def display_name(self) -> str:
        return self.filename


def validate_inbox_upload(
    filename: object, declared_mime_type: object, raw_bytes: object
) -> InboxAttachment:
    """Revalidate filename, MIME, and bytes before Gemini sees an attachment.

    Browser-supplied extension and MIME metadata are never trusted on their own.
    A file must satisfy all applicable checks, and all content remains in local
    memory only for the current call.
    """
    safe_filename = _safe_filename(filename)
    extension = PurePath(safe_filename).suffix.lower()
    kind = _EXTENSION_KIND.get(extension)
    if kind is None:
        raise InboxUploadError("Upload a PDF, PNG, JPG, WEBP, TXT, or Markdown file.")
    if not isinstance(raw_bytes, bytes):
        raise InboxUploadError("The upload could not be read safely. Choose the file again.")
    if not raw_bytes:
        raise InboxUploadError("The uploaded file is empty.")
    if len(raw_bytes) > MAX_INBOX_FILE_BYTES:
        raise InboxUploadError("Files for AI Inbox must be 5 MB or smaller.")

    declared_mime = _normalise_mime(declared_mime_type)
    if declared_mime and declared_mime not in _ALLOWED_DECLARED_TYPES[kind]:
        raise InboxUploadError("The uploaded file type does not match its extension.")

    if kind == "pdf":
        return _validate_pdf(safe_filename, raw_bytes)
    if kind == "image":
        return _validate_image(safe_filename, declared_mime, raw_bytes)
    return _validate_text(safe_filename, raw_bytes)


def parse_inbox_candidates(payload: object, *, source_name: str) -> TaskCapturePreview:
    """Treat model JSON as untrusted data and return only bounded candidates.

    The output deliberately has no field for instructions, integrations,
    credentials, or side effects.  Invalid model values are skipped or reduced
    to a safe local default before the existing human-review step is shown.
    """
    if not isinstance(payload, str) or len(payload) > 100_000:
        return TaskCapturePreview(warnings=("Gemini returned an invalid AI Inbox response. Try a simpler file.",))
    try:
        value = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return TaskCapturePreview(warnings=("Gemini did not return usable task candidates. Try again.",))
    if not isinstance(value, dict):
        return TaskCapturePreview(warnings=("Gemini did not return a task-candidate object. Try again.",))

    source_label = _safe_filename(source_name)
    tasks: list[CapturedTask] = []
    commitments: list[CapturedCommitment] = []
    warnings: list[str] = []

    raw_tasks = value.get("tasks")
    if isinstance(raw_tasks, list):
        for item in raw_tasks:
            if len(tasks) >= MAX_INBOX_TASKS or len(tasks) + len(commitments) >= MAX_INBOX_CANDIDATES:
                warnings.append("Only the first safe AI Inbox candidates are shown for review.")
                break
            candidate = _parse_task_candidate(item, source_label)
            if candidate is not None:
                tasks.append(candidate)

    raw_commitments = value.get("commitments")
    if isinstance(raw_commitments, list):
        for item in raw_commitments:
            if (
                len(commitments) >= MAX_INBOX_COMMITMENTS
                or len(tasks) + len(commitments) >= MAX_INBOX_CANDIDATES
            ):
                warnings.append("Only the first safe AI Inbox candidates are shown for review.")
                break
            candidate = _parse_commitment_candidate(item, source_label)
            if candidate is not None:
                commitments.append(candidate)

    if not tasks and not commitments:
        warnings.append("No safe task or protected-time candidates were found in this file.")
    return TaskCapturePreview(tuple(tasks), tuple(commitments), tuple(dict.fromkeys(warnings)))


def _safe_filename(value: object) -> str:
    if not isinstance(value, str):
        raise InboxUploadError("The uploaded file needs a valid filename.")
    filename = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or "\x00" in filename or len(filename) > 180:
        raise InboxUploadError("The uploaded file has an invalid filename.")
    return filename


def _normalise_mime(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.split(";", 1)[0].strip().lower()


def _validate_pdf(filename: str, raw_bytes: bytes) -> InboxAttachment:
    if not raw_bytes.startswith(_PDF_HEADER):
        raise InboxUploadError("This .pdf file does not contain a readable PDF header.")
    page_count = len(_PDF_PAGE_MARKER.findall(raw_bytes))
    if not 1 <= page_count <= MAX_INBOX_PDF_PAGES:
        raise InboxUploadError(
            f"PDFs for AI Inbox must contain 1–{MAX_INBOX_PDF_PAGES} readable pages. Export a smaller PDF and try again."
        )
    return InboxAttachment(
        filename=filename,
        mime_type="application/pdf",
        kind="pdf",
        content=raw_bytes,
        pdf_page_count=page_count,
    )


def _validate_image(filename: str, declared_mime: str, raw_bytes: bytes) -> InboxAttachment:
    actual_mime = _image_mime(raw_bytes)
    if actual_mime is None:
        raise InboxUploadError("This image does not have a supported PNG, JPG, or WEBP signature.")
    extension = PurePath(filename).suffix.lower()
    expected_by_extension = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    if expected_by_extension.get(extension) != actual_mime:
        raise InboxUploadError("The image bytes do not match the filename extension.")
    if declared_mime and declared_mime != actual_mime:
        raise InboxUploadError("The image MIME type does not match the image bytes.")
    return InboxAttachment(filename=filename, mime_type=actual_mime, kind="image", content=raw_bytes)


def _image_mime(raw_bytes: bytes) -> str | None:
    if raw_bytes.startswith(_PNG_HEADER):
        return "image/png"
    if raw_bytes.startswith(_JPEG_HEADER):
        return "image/jpeg"
    if len(raw_bytes) >= 12 and raw_bytes.startswith(_WEBP_HEADER) and raw_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


def _validate_text(filename: str, raw_bytes: bytes) -> InboxAttachment:
    if b"\x00" in raw_bytes:
        raise InboxUploadError("Text and Markdown uploads cannot contain binary data.")
    try:
        decoded = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InboxUploadError("Text and Markdown files must use UTF-8 encoding.") from error
    cleaned_text = _CONTROL_CHARACTERS.sub(" ", decoded).strip()
    if not cleaned_text:
        raise InboxUploadError("The text file is empty after removing unsupported characters.")
    if len(cleaned_text) > MAX_INBOX_TEXT_CHARACTERS:
        raise InboxUploadError(
            f"Text and Markdown uploads must be {MAX_INBOX_TEXT_CHARACTERS:,} characters or shorter."
        )
    extension = PurePath(filename).suffix.lower()
    mime_type = "text/markdown" if extension in {".md", ".markdown"} else "text/plain"
    return InboxAttachment(
        filename=filename,
        mime_type=mime_type,
        kind="text",
        content=raw_bytes,
        text_content=cleaned_text,
    )


def _parse_task_candidate(item: object, source_label: str) -> CapturedTask | None:
    if not isinstance(item, dict):
        return None
    title = _candidate_text(item.get("title"), MAX_INBOX_TITLE_CHARS)
    if not title:
        return None
    estimated_minutes = _candidate_minutes(item.get("estimated_minutes"))
    category = _allowed_value(item.get("category"), TASK_CATEGORIES, "General")
    priority = _allowed_value(item.get("priority"), PRIORITIES, "Medium")
    notes = _candidate_text(item.get("notes"), MAX_INBOX_NOTES_CHARS)
    return CapturedTask(
        title=title,
        estimated_minutes=estimated_minutes,
        category=category,
        priority=priority,
        notes=notes,
        source_text=f"AI Inbox candidate from {source_label}",
    )


def _parse_commitment_candidate(item: object, source_label: str) -> CapturedCommitment | None:
    if not isinstance(item, dict):
        return None
    title = _candidate_text(item.get("title"), MAX_INBOX_TITLE_CHARS)
    start = _safe_time(item.get("start_time"))
    end = _safe_time(item.get("end_time"))
    if not title or start is None or end is None or start >= end:
        return None
    if _minutes_after(start, end) > 12 * 60:
        return None
    category = _allowed_value(item.get("category"), COMMITMENT_CATEGORIES, "General")
    return CapturedCommitment(
        title=title,
        start_time=start,
        end_time=end,
        category=category,
        source_text=f"AI Inbox candidate from {source_label}",
    )


def _candidate_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = _CONTROL_CHARACTERS.sub(" ", value)
    return " ".join(normalized.split()).strip()[:max_length].rstrip()


def _candidate_minutes(value: object) -> int:
    if isinstance(value, bool):
        return 30
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return 30
    return min(480, max(5, minutes))


def _allowed_value(value: object, allowed: set[str], fallback: str) -> str:
    return value if isinstance(value, str) and value in allowed else fallback


def _safe_time(value: object) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        return None
    return value


def _minutes_after(start: str, end: str) -> int:
    start_hour, start_minute = (int(part) for part in start.split(":", 1))
    end_hour, end_minute = (int(part) for part in end.split(":", 1))
    return (end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)
