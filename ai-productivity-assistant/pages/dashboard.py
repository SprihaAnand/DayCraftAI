"""Small Today overview that hands quickly into the day planner."""

from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from components.ai_session import ai_provider_label
from services.ai import AIService
from services.auth import AuthenticatedUser
from services.database import Database


def _open_tasks() -> None:
    """Send task capture to the dedicated backlog page."""
    st.switch_page("app_pages/task_backlog.py")


def render_dashboard(database: Database, user: AuthenticatedUser, ai: AIService) -> None:
    """Give Today one clear starting point before the schedule studio below."""
    today = date.today()
    events = database.list_events(user.id, start_date=today, end_date=today)
    open_tasks = database.list_tasks(user.id, include_completed=False)
    planned_blocks = [event for event in events if event["source"] == "planner"]
    task_blocks = [
        event
        for event in planned_blocks
        if str(event.get("category")) not in {"Break", "Planning"}
    ]
    fixed_events = [event for event in events if event["source"] != "planner"]
    estimated_minutes = sum(int(task.get("estimated_minutes") or 0) for task in open_tasks)
    planning_status = (
        "Plan ready"
        if task_blocks
        else (
            "Rhythm saved"
            if planned_blocks
            else (f"{ai_provider_label(ai)} ready" if ai.is_configured else "AI setup needed")
        )
    )

    if task_blocks:
        heading = "Your day has a shape."
        description = "The time canvas below is your source of truth. Protect the next meaningful block."
    elif planned_blocks:
        heading = "Your rhythm is in place."
        description = "Add or review tasks, then let AI fill the open work windows around your protected time."
    elif open_tasks:
        heading = "Make space for today."
        description = "Choose a rhythm, then let AI turn your real work into an honest time plan."
    else:
        heading = "Start with one real task."
        description = "Capture it first. The schedule studio will give it a real place in your day."

    st.markdown(
        f"""
        <section class="dc-today-hero">
          <div class="dc-today-hero-copy">
            <span class="dc-kicker">DayCraft / {escape(today.strftime('%a').upper())} {today.day:02d}</span>
            <h1>{escape(heading)}</h1>
            <p>{escape(user.display_name)}, {escape(description)}</p>
          </div>
          <div class="dc-today-status">
            <span class="dc-status-dot"></span>{escape(planning_status)}
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    stat_columns = st.columns(3)
    stat_columns[0].metric("Open work", len(open_tasks), icon=":material/task_alt:")
    stat_columns[1].metric("Time protected", len(fixed_events), icon=":material/event_available:")
    stat_columns[2].metric(
        "Backlog estimate",
        f"{estimated_minutes // 60}h {estimated_minutes % 60:02d}m" if estimated_minutes else "—",
        icon=":material/timelapse:",
    )

    action, note = st.columns([0.33, 0.67], vertical_alignment="center")
    with action:
        if not open_tasks:
            st.button(
                "Capture a task",
                key="today_open_tasks",
                type="primary",
                icon=":material/add_task:",
                on_click=_open_tasks,
                width="stretch",
            )
        elif not task_blocks:
            if st.button(
                "Build my time blocks",
                key="today_craft_plan",
                type="primary",
                icon=":material/auto_awesome:",
                width="stretch",
            ):
                st.session_state["daycraft_request_generate"] = True
    with note:
        if task_blocks:
            st.markdown(
                '<p class="dc-dashboard-note">Your schedule below is the source of truth. Sync only the blocks you explicitly want in Google Calendar.</p>',
                unsafe_allow_html=True,
            )
        elif ai.is_configured:
            st.markdown(
                '<p class="dc-dashboard-note">Pick a ready-made day rhythm below. AI sets task order; DayCraft validates every minute against protected time.</p>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<p class="dc-dashboard-note">Connect Gemini or OpenAI in the schedule studio below before building task blocks. Your work stays saved in your account.</p>',
                unsafe_allow_html=True,
            )
