"""Account, AI, and deliberate Google connection controls for DayCraft."""

from __future__ import annotations

import json

import streamlit as st
from cryptography.fernet import Fernet

from components.ai_session import render_ai_setup
from components.theme import card, page_intro
from services.auth import AuthenticatedUser
from services.calendar import CalendarError, CalendarService
from services.database import Database
from services.gmail import GmailError, GmailService


def _google_checks(connection: CalendarService | GmailService) -> list[tuple[str, bool, str]]:
    """Return safe readiness checks without displaying secret values."""
    encryption_key_is_valid = False
    if connection.encryption_key:
        try:
            Fernet(connection.encryption_key.encode("utf-8"))
        except (TypeError, ValueError):
            pass
        else:
            encryption_key_is_valid = True

    return [
        (
            "Google OAuth app",
            bool(connection.client_id and connection.client_secret),
            "Create a Web application OAuth client in Google Cloud.",
        ),
        (
            "Approved redirect URL",
            bool(connection.redirect_uri),
            "Register the same URL in Google Cloud and in your .env file.",
        ),
        (
            "Token encryption",
            encryption_key_is_valid,
            "Generate a Fernet key so Google refresh tokens are encrypted at rest.",
        ),
    ]


def _render_google_status(checks: list[tuple[str, bool, str]]) -> None:
    for label, is_ready, guidance in checks:
        status, color, icon = (
            ("Ready", "green", ":material/check_circle:")
            if is_ready
            else ("Needs setup", "orange", ":material/pending:")
        )
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{label}**")
            st.badge(status, color=color, icon=icon)
        if not is_ready:
            st.caption(guidance)


def _google_env_template(redirect_uri: str) -> str:
    """Show placeholders only; OAuth client secrets never enter this UI."""
    return f"""# .env — keep this file private and out of Git
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI={redirect_uri}
DAYCRAFT_ENCRYPTION_KEY=paste-the-generated-fernet-key-here"""


def _render_google_setup(connection: CalendarService | GmailService) -> None:
    redirect_uri = connection.redirect_uri or "http://localhost:8501"
    with st.expander("Set up Google Calendar and Gmail", icon=":material/settings:", expanded=False):
        st.markdown(
            "This one secure setup supports both connections. Google consent is still separate: you decide whether "
            "DayCraft can access Calendar events and whether it can send Gmail messages."
        )
        st.markdown("**1. Create a Google OAuth app**")
        st.markdown(
            "In Google Cloud Console, create or select a project, configure the OAuth consent screen, and create a "
            "**Web application** OAuth client. Enable the Google Calendar API and Gmail API only if you will use them."
        )
        st.link_button(
            "Open Google Cloud Console",
            "https://console.cloud.google.com/apis/credentials",
            icon=":material/open_in_new:",
            width="content",
        )
        st.markdown("**2. Add the exact redirect URL**")
        st.markdown(
            "Add this exact address to the OAuth client's **Authorized redirect URIs**. Use your public HTTPS URL "
            "in production, and put that same address in `.env`."
        )
        st.code(redirect_uri, language=None)
        st.markdown("**3. Generate the encryption key on your machine**")
        st.code(
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"',
            language="bash",
        )
        st.markdown("**4. Update `.env`, then restart Streamlit**")
        st.caption("This snippet intentionally contains placeholders instead of secrets.")
        st.code(_google_env_template(redirect_uri), language="bash")
        st.caption(
            "Calendar requests `calendar.events` to read commitments and write only events you explicitly sync. "
            "Gmail requests `gmail.send` only; DayCraft cannot read your inbox."
        )


def _render_calendar_connection(calendar: CalendarService, user: AuthenticatedUser) -> None:
    checks = _google_checks(calendar)
    local_setup_ready = all(is_ready for _, is_ready, _ in checks)

    with st.container(border=True):
        st.subheader("Google Calendar", icon=":material/calendar_month:")
        if calendar.is_connected(user.id):
            st.caption(
                "Your upcoming commitments can protect real availability. DayCraft creates Google events only when "
                "you select Sync on a specific local block."
            )
            actions = st.columns(2)
            with actions[0]:
                if st.button(
                    "Import upcoming events",
                    type="primary",
                    icon=":material/download:",
                    key="calendar_import",
                    width="stretch",
                ):
                    try:
                        count = calendar.import_upcoming(user.id)
                    except CalendarError as error:
                        st.error(str(error), icon=":material/error:")
                    else:
                        st.success(f"Imported or refreshed {count} event(s).", icon=":material/check_circle:")
            with actions[1]:
                if st.button(
                    "Disconnect Calendar",
                    icon=":material/link_off:",
                    key="calendar_disconnect",
                    width="stretch",
                ):
                    calendar.disconnect(user.id)
                    st.success("Google Calendar was disconnected from this DayCraft account.")
                    st.rerun()
            return

        if local_setup_ready:
            st.caption("Connect the Google account whose availability should shape your daily plan.")
            if st.button(
                "Connect Google Calendar",
                type="primary",
                icon=":material/link:",
                key="calendar_connect",
                width="content",
            ):
                try:
                    st.session_state["calendar_authorization_url"] = calendar.authorization_url(user.id)
                except CalendarError as error:
                    st.error(str(error), icon=":material/error:")
            authorization_url = st.session_state.get("calendar_authorization_url")
            if authorization_url:
                st.link_button(
                    "Continue securely with Google",
                    str(authorization_url),
                    type="primary",
                    icon=":material/open_in_new:",
                    width="stretch",
                )
                st.caption("Google returns here after approval. The one-time link belongs only to this DayCraft account.")
            return

        st.caption("Finish the shared Google setup below to let Calendar protect real meetings in your plan.")
        _render_google_status(checks)


def _render_gmail_connection(gmail: GmailService, user: AuthenticatedUser) -> None:
    checks = _google_checks(gmail)
    local_setup_ready = all(is_ready for _, is_ready, _ in checks)

    with st.container(border=True):
        st.subheader("Gmail", icon=":material/mail:")
        if gmail.is_connected(user.id):
            st.caption(
                "Send a plain-text message through the connected Gmail account. DayCraft never reads the inbox and "
                "each email needs an explicit send action."
            )
            with st.expander("Compose a Gmail message", icon=":material/edit:", expanded=False):
                with st.form("send_gmail_message", clear_on_submit=True):
                    recipients = st.text_input("To", placeholder="person@example.com, teammate@example.com")
                    subject = st.text_input("Subject", placeholder="A quick update")
                    body = st.text_area("Message", placeholder="Write the message you want to send.", height=150)
                    confirm_send = st.checkbox("I understand this sends the email immediately.")
                    send = st.form_submit_button(
                        "Send email now",
                        type="primary",
                        icon=":material/send:",
                        width="stretch",
                    )
                if send:
                    if not confirm_send:
                        st.error("Confirm that you want to send this email now.")
                    else:
                        try:
                            gmail.send_message(user.id, to=recipients, subject=subject, body=body)
                        except GmailError as error:
                            st.error(str(error), icon=":material/error:")
                        else:
                            st.success("Gmail confirmed the message was sent.", icon=":material/check_circle:")
            if st.button(
                "Disconnect Gmail",
                icon=":material/link_off:",
                key="gmail_disconnect",
                width="content",
            ):
                gmail.disconnect(user.id)
                st.success("Gmail was disconnected from this DayCraft account.")
                st.rerun()
            return

        if local_setup_ready:
            st.caption("Connect Google to authorize send-only Gmail access. Your inbox remains inaccessible to DayCraft.")
            if st.button(
                "Connect Gmail",
                type="primary",
                icon=":material/link:",
                key="gmail_connect",
                width="content",
            ):
                try:
                    st.session_state["gmail_authorization_url"] = gmail.authorization_url(user.id)
                except GmailError as error:
                    st.error(str(error), icon=":material/error:")
            authorization_url = st.session_state.get("gmail_authorization_url")
            if authorization_url:
                st.link_button(
                    "Continue securely with Google",
                    str(authorization_url),
                    type="primary",
                    icon=":material/open_in_new:",
                    width="stretch",
                )
                st.caption("Google asks only for permission to send messages after you explicitly compose one here.")
            return

        st.caption("Finish the shared Google setup below before connecting Gmail send-only access.")
        _render_google_status(checks)


def render_settings(database: Database, user: AuthenticatedUser, calendar: CalendarService) -> None:
    """Render account, required AI planning, integrations, and data controls."""
    gmail = GmailService(database)
    page_intro(
        "Settings",
        "Control your planning workspace.",
        "AI creates the daily plan; Google connections add real availability and explicit communication when you want them.",
    )
    account_tab, connections_tab, data_tab = st.tabs(["Account", "Connections", "Data & privacy"])

    with account_tab:
        card(user.display_name, user.email, pill="Private workspace", pill_class="neutral")
        st.caption(
            "Your account keeps tasks, plans, focus sessions, check-ins, and Google connection tokens separate from "
            "every other account. Passwords are salted and one-way hashed. Sign in with the same email and password "
            "on a later visit to return to the same workspace."
        )

    with connections_tab:
        st.subheader("Your planning engine", icon=":material/auto_awesome:")
        st.caption("A Gemini or OpenAI key is required before DayCraft can craft a daily plan.")
        render_ai_setup(key_prefix="settings", heading="Connect DayCraft's required AI planner")

        st.divider()
        st.subheader("Google workspace", icon=":material/account_tree:")
        st.caption(
            "An email address identifies your DayCraft account, but Google access requires separate OAuth consent. "
            "Calendar and Gmail use the same secure app configuration while retaining distinct permissions."
        )
        _render_calendar_connection(calendar, user)
        st.space("small")
        _render_gmail_connection(gmail, user)
        _render_google_setup(calendar)

    with data_tab:
        st.subheader("Export your workspace", icon=":material/download:")
        tasks = database.list_tasks(user.id, include_completed=True)
        events = database.list_events(user.id)
        export_payload = json.dumps(
            {"account": {"display_name": user.display_name, "email": user.email}, "tasks": tasks, "events": events},
            indent=2,
        )
        st.download_button(
            "Download tasks and calendar data (JSON)",
            data=export_payload,
            file_name="daycraft-export.json",
            mime="application/json",
            icon=":material/download:",
            width="stretch",
        )
        with st.container(border=True):
            st.subheader("Keep secrets outside your workspace data", icon=":material/shield_lock:")
            st.caption(
                "Browser-entered AI keys remain only in the active browser session and are cleared at sign-out. "
                "Deployment keys and OAuth client secrets belong in `.env` or a secret manager; neither appears in exports."
            )
        st.caption(
            "The export excludes password hashes and encrypted Google refresh tokens. SQLite is suitable for a personal "
            "or self-hosted deployment; use a managed database and identity provider before a public multi-user launch."
        )
