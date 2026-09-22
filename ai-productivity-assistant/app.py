"""DayCraft's focused authenticated workspace router."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from components.auth import active_user, render_authentication
from components.sidebar import render_sidebar
from components.theme import apply_public_shell, apply_theme, configure_page
from services.database import Database

configure_page()
load_dotenv(Path(__file__).with_name(".env"))

def _public_login_route() -> None:
    """Register the unauthenticated route without rendering workspace content."""


def main() -> None:
    database = Database()
    database.initialize()
    apply_theme()

    user = active_user(database)
    if user is None:
        # Calling navigation before stopping is important: it switches Streamlit
        # out of legacy ``pages/`` discovery, while ``hidden`` keeps the login
        # screen free of workspace links and the empty sidebar they can create.
        public_page = st.navigation(
            [st.Page(_public_login_route, title="Sign in", default=True)],
            position="hidden",
        )
        apply_public_shell()
        user = render_authentication(database)
        if user is None:
            public_page.run()
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
    render_sidebar(user)
    selected_page.run()


if __name__ == "__main__":
    main()
