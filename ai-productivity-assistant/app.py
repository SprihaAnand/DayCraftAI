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

_PENDING_GOOGLE_CALLBACK = "pending_google_callback"


def _capture_google_callback() -> None:
    """Move Google callback values out of the URL and into this callback tab.

    ``st.link_button`` opens Google in a new tab, which starts a new Streamlit
    session on return. Storing the short-lived code only in that new tab lets us
    ask the person to sign in again before associating the authorization with a
    DayCraft account. This keeps a copied authorization URL from linking a
    Google account to the wrong DayCraft user.
    """
    query = st.query_params
    provider_error = query.get("error")
    code = query.get("code")
    state = query.get("state")
    if provider_error:
        st.session_state.pop(_PENDING_GOOGLE_CALLBACK, None)
        st.session_state["google_callback_error"] = "Google access was not approved."
        st.query_params.clear()
        st.rerun()
    if code or state:
        if isinstance(code, str) and isinstance(state, str) and code and state:
            st.session_state[_PENDING_GOOGLE_CALLBACK] = {"code": code, "state": state}
        else:
            st.session_state.pop(_PENDING_GOOGLE_CALLBACK, None)
            st.session_state["google_callback_error"] = "Google returned an incomplete connection response. Start again."
        st.query_params.clear()
        st.rerun()


def _pending_google_callback() -> tuple[str, str] | None:
    """Return one safely shaped callback retained in this browser tab only."""
    pending = st.session_state.get(_PENDING_GOOGLE_CALLBACK)
    if not isinstance(pending, dict):
        return None
    code = pending.get("code")
    state = pending.get("state")
    if not isinstance(code, str) or not isinstance(state, str) or not code or not state:
        st.session_state.pop(_PENDING_GOOGLE_CALLBACK, None)
        return None
    return code, state


def _complete_pending_google_callback(
    database: Database,
    calendar: CalendarService,
    gmail: GmailService,
    *,
    expected_user_id: int,
) -> bool:
    """Exchange a callback only after its tab authenticated the initiating user.

    Returns ``True`` only when the signed-in account is different from the
    account that began the connection, so the caller can keep the retry path on
    screen without consuming the still-valid authorization transaction.
    """
    pending = _pending_google_callback()
    if pending is None:
        return False
    code, state = pending
    provider = database.oauth_state_provider(state, expected_user_id=expected_user_id)
    if provider not in {CALENDAR_PROVIDER, GMAIL_PROVIDER}:
        # A valid unbound state means the current DayCraft account is simply the
        # wrong one. Leave it untouched so the person can sign in to the correct
        # account in this same callback tab and finish safely.
        if database.oauth_state_provider(state) in {CALENDAR_PROVIDER, GMAIL_PROVIDER}:
            st.error(
                "This Google connection was started from a different DayCraft account. "
                "Sign out below, then sign in to that same account to finish it.",
                icon=":material/account_circle:",
            )
            if st.button(
                "Sign out and use the other account",
                icon=":material/logout:",
                key="oauth_callback_sign_out",
                width="content",
            ):
                st.session_state.pop("authenticated_user_id", None)
                st.rerun()
            return True
        st.session_state.pop(_PENDING_GOOGLE_CALLBACK, None)
        st.session_state["google_callback_error"] = (
            "This Google connection link expired or is no longer valid. Start the connection again."
        )
        st.rerun()

    try:
        if provider == CALENDAR_PROVIDER:
            calendar.complete_authorization(state, code, expected_user_id=expected_user_id)
            st.session_state["google_callback_success"] = "calendar"
        else:
            gmail.complete_authorization(state, code, expected_user_id=expected_user_id)
            st.session_state["google_callback_success"] = "gmail"
    except (CalendarError, GmailError) as error:
        st.session_state["google_callback_error"] = str(error)
    finally:
        # The server-side state is one-use. Do not leave a rejected or consumed
        # authorization code in browser session memory.
        st.session_state.pop(_PENDING_GOOGLE_CALLBACK, None)
    st.rerun()
    return False


def main() -> None:
    database = Database()
    database.initialize()
    calendar = CalendarService(database)
    gmail = GmailService(database)
    _capture_google_callback()
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

    if _pending_google_callback():
        st.info(
            "To finish connecting Google securely, sign in below to the same DayCraft account that started it.",
            icon=":material/lock:",
        )

    user = render_authentication(database)
    if user is None:
        st.stop()

    if _complete_pending_google_callback(
        database, calendar, gmail, expected_user_id=user.id
    ):
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
