"""DayCraft's focused authenticated workspace router."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from components.auth import render_authentication
from components.sidebar import render_sidebar
from components.theme import apply_theme, configure_page
from services.calendar import PROVIDER as CALENDAR_PROVIDER
from services.calendar import CalendarError, CalendarService
from services.database import Database
from services.gmail import PROVIDER as GMAIL_PROVIDER
from services.gmail import GmailError, GmailService

configure_page()
load_dotenv(Path(__file__).with_name(".env"))


def _handle_google_callback(
    database: Database, calendar: CalendarService, gmail: GmailService
) -> None:
    """Route one signed, short-lived Google OAuth callback to its integration."""
    query = st.query_params
    provider_error = query.get("error")
    code = query.get("code")
    state = query.get("state")
    if provider_error:
        st.session_state["google_callback_error"] = "Google access was not approved."
        st.query_params.clear()
        st.rerun()
    if code and state:
        active_user_id = st.session_state.get("authenticated_user_id")
        if not active_user_id:
            st.session_state["google_callback_error"] = (
                "Sign in to the account that started this Google connection, then begin again."
            )
            st.query_params.clear()
            st.rerun()
        provider = database.oauth_state_provider(str(state), expected_user_id=int(active_user_id))
        if provider not in {CALENDAR_PROVIDER, GMAIL_PROVIDER}:
            st.session_state["google_callback_error"] = (
                "This Google connection link expired or does not belong to the signed-in account. Start again."
            )
            st.query_params.clear()
            st.rerun()
        try:
            if provider == CALENDAR_PROVIDER:
                calendar.complete_authorization(
                    str(state), str(code), expected_user_id=int(active_user_id)
                )
                st.session_state["google_callback_success"] = "calendar"
            else:
                gmail.complete_authorization(str(state), str(code), expected_user_id=int(active_user_id))
                st.session_state["google_callback_success"] = "gmail"
        except (CalendarError, GmailError) as error:
            st.session_state["google_callback_error"] = str(error)
        st.query_params.clear()
        st.rerun()


def main() -> None:
    database = Database()
    database.initialize()
    calendar = CalendarService(database)
    gmail = GmailService(database)
    _handle_google_callback(database, calendar, gmail)
    apply_theme()

    callback_error = st.session_state.pop("google_callback_error", None)
    callback_success = st.session_state.pop("google_callback_success", None)
    if callback_error:
        st.error(callback_error, icon=":material/error:")
    if callback_success:
        success_copy = (
            "Google Calendar connected. Import events from Settings when you are ready."
            if callback_success == "calendar"
            else "Gmail connected. DayCraft can send an email only when you explicitly compose and send one."
        )
        st.success(success_copy, icon=":material/check_circle:")

    user = render_authentication(database)
    if user is None:
        st.stop()

    pages = [
        st.Page(
            "app_pages/day_plan.py",
            title="Today",
            icon=":material/today:",
            default=True,
        ),
        st.Page("app_pages/task_backlog.py", title="Tasks", icon=":material/checklist:"),
        st.Page("app_pages/focus_mode.py", title="Focus", icon=":material/timer:"),
        st.Page("app_pages/progress_review.py", title="Review", icon=":material/insights:"),
        st.Page("app_pages/account_settings.py", title="Settings", icon=":material/settings:"),
    ]
    selected_page = st.navigation(pages, position="top")
    render_sidebar(user, calendar, gmail)
    selected_page.run()


if __name__ == "__main__":
    main()
