"""Account, AI-planning, and local workspace controls for DayCraft."""

from __future__ import annotations

import json

import streamlit as st

from components.ai_session import render_ai_setup
from components.theme import card, page_intro
from services.auth import AuthenticatedUser
from services.database import Database


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
