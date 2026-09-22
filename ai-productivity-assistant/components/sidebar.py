"""The small account rail shared by the focused workspace pages."""

from __future__ import annotations

import streamlit as st

from components.ai_session import clear_session_ai_configuration
from services.auth import AuthenticatedUser


def render_sidebar(user: AuthenticatedUser) -> None:
    """Keep account status nearby without turning navigation into a control panel."""
    with st.sidebar:
        st.title("DayCraft", icon=":material/event_note:")
        st.caption("Plan a day you can actually finish.")
        st.space("small")
        st.markdown(f"**{user.display_name}**")
        st.caption(user.email)
        st.space("small")
        if st.button(
            "Sign out",
            icon=":material/logout:",
            key="sign_out",
            width="stretch",
        ):
            st.session_state.pop("authenticated_user_id", None)
            st.session_state.pop("focus_timer", None)
            clear_session_ai_configuration()
            st.rerun()
