"""Shared, authenticated workspace dependencies for Streamlit page scripts."""

from __future__ import annotations

import streamlit as st

from components.ai_session import current_ai_service
from components.auth import active_user
from services.ai import AIService
from services.auth import AuthenticatedUser
from services.calendar import CalendarService
from services.database import Database


def current_workspace() -> tuple[Database, AuthenticatedUser, CalendarService, AIService]:
    """Build lightweight services for the signed-in user on the current rerun."""
    database = Database()
    database.initialize()
    user = active_user(database)
    if user is None:
        st.error("Your session has ended. Please sign in again.")
        st.stop()
    return database, user, CalendarService(database), current_ai_service()
