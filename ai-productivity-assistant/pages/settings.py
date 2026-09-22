"""Account, AI-planning, and local workspace controls for DayCraft."""

from __future__ import annotations

import hashlib
import json
import os

import streamlit as st

from components.ai_session import render_ai_setup
from components.theme import card, page_intro
from services.auth import AuthenticatedUser
from services.database import Database
from services.icalendar import (
    ICalendarError,
    ImportedEvent,
    configured_timezone,
    filter_new_imports,
    parse_icalendar,
)

_ICALENDAR_DIGEST_KEY = "daycraft_icalendar_upload_digest"
_ICALENDAR_SELECTION_KEY = "daycraft_icalendar_import_selection"


def _preview_label(event: ImportedEvent) -> str:
    return f"{event.event_date.isoformat()} · {event.start_time}–{event.end_time} · {event.title}"


def _render_icalendar_import(database: Database, user: AuthenticatedUser) -> None:
    """Render a review-first local import with no write until confirmation."""
    st.subheader("Import a calendar file", icon=":material/upload_file:")
    st.caption(
        "Upload one small .ics file to review safe single-day, non-recurring events. Nothing is sent to a calendar service, "
        "and nothing is saved until you confirm the selected commitments."
    )
    uploaded = st.file_uploader(
        "Choose one .ics file",
        type=["ics", "ical"],
        accept_multiple_files=False,
        max_upload_size=1,
        key="icalendar_import_upload",
        help="Files are parsed locally in this app session. Files larger than 512 KB are rejected.",
    )
    if uploaded is None:
        return

    payload = uploaded.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    try:
        parsed = parse_icalendar(
            payload,
            timezone_name=configured_timezone(os.getenv("DAYCRAFT_TIMEZONE", "UTC")),
        )
    except ICalendarError as error:
        st.error(str(error))
        return

    new_events, duplicate_count = filter_new_imports(parsed.events, database.list_events(user.id))
    if st.session_state.get(_ICALENDAR_DIGEST_KEY) != digest:
        # This runs before the selection widget so it is safe to reset a prior
        # upload's review state without modifying a rendered widget.
        st.session_state[_ICALENDAR_DIGEST_KEY] = digest
        st.session_state[_ICALENDAR_SELECTION_KEY] = [event.fingerprint for event in new_events]

    if parsed.skipped_events:
        st.caption(
            f"{parsed.skipped_events} unsupported, recurring, cross-day, or duplicate-in-file event(s) were skipped."
        )
    if duplicate_count:
        st.caption(f"{duplicate_count} event(s) already match your local schedule and were excluded.")
    if not new_events:
        st.info("There are no new safe events to import from this file.", icon=":material/info:")
        return

    by_fingerprint = {event.fingerprint: event for event in new_events}
    st.dataframe(
        [
            {
                "Date": event.event_date.isoformat(),
                "Time": f"{event.start_time}–{event.end_time}",
                "Commitment": event.title,
                "Location": event.location or "—",
            }
            for event in new_events
        ],
        hide_index=True,
        width="stretch",
    )
    selected_fingerprints = st.multiselect(
        "Choose commitments to import",
        list(by_fingerprint),
        format_func=lambda fingerprint: _preview_label(by_fingerprint[fingerprint]),
        key=_ICALENDAR_SELECTION_KEY,
        max_selections=len(by_fingerprint),
        help="Only selected items can be imported after the confirmation below.",
    )
    selected = [
        by_fingerprint[fingerprint]
        for fingerprint in selected_fingerprints
        if isinstance(fingerprint, str) and fingerprint in by_fingerprint
    ]
    confirmation_key = f"icalendar_import_confirm_{digest[:12]}"
    confirmed = st.checkbox(
        "I reviewed these events and want to create them as fixed local commitments.",
        key=confirmation_key,
    )
    import_requested = st.button(
        "Import selected commitments",
        type="primary",
        icon=":material/event_available:",
        key=f"icalendar_import_submit_{digest[:12]}",
        disabled=not confirmed or not selected,
        width="stretch",
    )
    if not import_requested:
        return

    # Re-check selection and duplicates immediately before the only write. UI
    # widget limits are not a security boundary, and another browser tab could
    # have created a matching commitment while this preview was open.
    selected = tuple(event for event in selected if event.fingerprint in by_fingerprint)
    selected, just_deduplicated = filter_new_imports(selected, database.list_events(user.id))
    if not selected:
        st.info("Those selected events are already present, so no changes were made.", icon=":material/info:")
        return
    for event in selected:
        database.create_event(
            user.id,
            event.title,
            event.event_date,
            event.start_time,
            event.end_time,
            category="Imported",
            location=event.location,
            notes=event.notes,
            is_fixed=True,
            source="manual",
        )
    suffix = f" ({just_deduplicated} duplicate(s) skipped)" if just_deduplicated else ""
    st.success(f"Imported {len(selected)} fixed local commitment(s){suffix}.")
    st.rerun()


def render_settings(database: Database, user: AuthenticatedUser) -> None:
    """Render account, required AI planning, and safe local-data controls."""
    page_intro(
        "Settings",
        "Control your planning workspace.",
        "Set up the AI planner and manage the data kept in your private workspace.",
    )
    account_tab, ai_tab, data_tab = st.tabs(["Account", "AI planner", "Data & privacy"])

    with account_tab:
        card(user.display_name, user.email, pill="Private workspace", pill_class="neutral")
        st.caption(
            "Your account keeps tasks, plans, focus sessions, and check-ins separate from every other account. "
            "Passwords are salted and one-way hashed. Sign in with the same email and password on a later visit "
            "to return to the same workspace."
        )

    with ai_tab:
        st.subheader("Your planning engine", icon=":material/auto_awesome:")
        st.caption("A Gemini or OpenAI key is required before DayCraft can craft a daily plan.")
        render_ai_setup(key_prefix="settings", heading="Connect DayCraft's required AI planner")

    with data_tab:
        st.subheader("Export your workspace", icon=":material/download:")
        tasks = database.list_tasks(user.id, include_completed=True)
        events = database.list_events(user.id)
        export_payload = json.dumps(
            {"account": {"display_name": user.display_name, "email": user.email}, "tasks": tasks, "events": events},
            indent=2,
        )
        st.download_button(
            "Download tasks and schedule data (JSON)",
            data=export_payload,
            file_name="daycraft-export.json",
            mime="application/json",
            icon=":material/download:",
            width="stretch",
        )
        st.divider()
        _render_icalendar_import(database, user)
        with st.container(border=True):
            st.subheader("Keep secrets outside your workspace data", icon=":material/shield_lock:")
            st.caption(
                "Browser-entered AI keys remain only in the active browser session and are cleared at sign-out. "
                "Deployment keys belong in `.env` or a secret manager; neither appears in exports."
            )
        st.caption(
            "The export excludes password hashes, browser-session keys, and server secrets. SQLite is suitable for "
            "a personal or self-hosted deployment; use a managed database and identity provider before a public "
            "multi-user launch."
        )
