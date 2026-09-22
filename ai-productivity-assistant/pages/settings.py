"""Account, AI, and deliberate Google connection controls for DayCraft."""

from __future__ import annotations

import json
from typing import NamedTuple
from urllib.parse import urlsplit

import streamlit as st
from cryptography.fernet import Fernet

from components.ai_session import render_ai_setup
from components.theme import card, page_intro
from services.auth import AuthenticatedUser
from services.calendar import CalendarError, CalendarService
from services.database import Database
from services.gmail import GmailError, GmailService


class RedirectPreflight(NamedTuple):
    """A safe, display-ready check of the configured Google callback URL."""

    ready: bool
    matched_current_app: bool | None
    message: str


def _origin(url: str, *, allow_path: bool = False) -> str | None:
    """Return a normalized HTTP(S) origin from a safe app or callback URL."""
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    if not allow_path and parsed.path not in {"", "/"}:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _redirect_preflight(redirect_uri: str, current_url: str | None) -> RedirectPreflight:
    """Catch stale or malformed OAuth callbacks before creating a Google flow.

    The origin comparison deliberately permits a callback path, but blocks a
    flow when a Cloud secret points at a different deployed app.  Google will
    otherwise successfully finish consent and send the user to that old app.
    """
    configured_origin = _origin(redirect_uri)
    if configured_origin is None:
        return RedirectPreflight(
            False,
            None,
            "The configured Google callback is not a plain http(s) URL. Use the exact app URL, without "
            "Markdown brackets, a query string, or a fragment.",
        )

    if configured_origin == "https://share.streamlit.io":
        return RedirectPreflight(
            False,
            None,
            "The Google callback points to Streamlit's dashboard, not your DayCraft app. Use this app's "
            "public https://…streamlit.app URL instead.",
        )

    current_origin = _origin(current_url or "", allow_path=True)
    if current_origin and configured_origin != current_origin:
        return RedirectPreflight(
            False,
            False,
            "The configured Google callback belongs to a different app address. Update GOOGLE_REDIRECT_URI "
            "to match the DayCraft URL open in this browser, then start a fresh Google connection.",
        )

    if current_origin:
        return RedirectPreflight(
            True,
            True,
            "The configured Google callback matches the DayCraft app open in this browser.",
        )

    return RedirectPreflight(
        True,
        None,
        "The callback URL is formatted correctly. Open it in a private browser window to confirm it loads "
        "the DayCraft sign-in screen before connecting Google.",
    )


def _current_app_url() -> str | None:
    """Read the browser URL when the Streamlit runtime exposes it."""
    try:
        return st.context.url
    except AttributeError:
        return None


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


def _render_calendar_connection(
    calendar: CalendarService, user: AuthenticatedUser, *, callback_ready: bool
) -> None:
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

        if local_setup_ready and callback_ready:
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
                st.caption(
                    "Google opens in a new tab. After approval, sign in there once to the same DayCraft account "
                    "to finish securely, then return here and refresh."
                )
            return

        if local_setup_ready:
            st.error(
                "Fix the Google callback check above before connecting Calendar. This prevents Google from "
                "returning to an old or inaccessible Streamlit app.",
                icon=":material/link_off:",
            )
            return

        st.caption("Finish the shared Google setup below to let Calendar protect real meetings in your plan.")
        _render_google_status(checks)


def _render_gmail_connection(
    gmail: GmailService, user: AuthenticatedUser, *, callback_ready: bool
) -> None:
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

        if local_setup_ready and callback_ready:
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
                st.caption(
                    "Google opens in a new tab. After approval, sign in there once to the same DayCraft account "
                    "to finish securely, then return here and refresh. Gmail requests send-only access."
                )
            return

        if local_setup_ready:
            st.error(
                "Fix the Google callback check above before connecting Gmail. This prevents Google from "
                "returning to an old or inaccessible Streamlit app.",
                icon=":material/link_off:",
            )
            return

        st.caption("Finish the shared Google setup below before connecting Gmail send-only access.")
        _render_google_status(checks)


def _render_google_callback_preflight(calendar: CalendarService) -> bool:
    """Render the visible Cloud/OAuth check before either Google connection."""
    redirect_uri = calendar.redirect_uri
    preflight = _redirect_preflight(redirect_uri, _current_app_url())

    with st.container(border=True):
        st.subheader("Google callback check", icon=":material/route:")
        st.caption("Google must return to the same public DayCraft address that you are using now.")
        if redirect_uri:
            st.code(redirect_uri, language=None)
        if preflight.ready:
            if preflight.matched_current_app:
                st.success(preflight.message, icon=":material/check_circle:")
            else:
                st.info(preflight.message, icon=":material/open_in_new:")
            if _origin(redirect_uri):
                st.link_button(
                    "Open callback URL to verify",
                    redirect_uri,
                    icon=":material/open_in_new:",
                    width="content",
                )
        else:
            st.error(preflight.message, icon=":material/error:")
            st.caption(
                "In Streamlit Community Cloud, update `GOOGLE_REDIRECT_URI` in App settings → Secrets, "
                "reboot the app, close older Google tabs, then create a new connection link here."
            )
    return preflight.ready


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
        callback_ready = _render_google_callback_preflight(calendar)
        _render_calendar_connection(calendar, user, callback_ready=callback_ready)
        st.space("small")
        _render_gmail_connection(gmail, user, callback_ready=callback_ready)
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
