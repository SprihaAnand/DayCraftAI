"""Personal productivity insights based only on durable user-owned records."""

from __future__ import annotations

from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from services.activity_calendar import (
    WEEKDAY_LABELS,
    build_completion_activity_calendar,
    completion_activity_window,
)
from services.ai import AIService
from services.auth import AuthenticatedUser
from services.database import Database

PAGE_PATHS = {
    "Today": "app_pages/day_plan.py",
    "Focus": "app_pages/focus_mode.py",
}


def _navigate(page: str) -> None:
    """Move between registered workspace pages from first-use guidance."""
    st.switch_page(PAGE_PATHS[page])


def _render_check_in(
    database: Database,
    user: AuthenticatedUser,
    ai: AIService,
    *,
    today: date,
    existing_today: dict[str, object] | None,
) -> None:
    """Collect a lightweight daily reflection that can power real insights."""
    with st.container(border=True, key="review_checkin_card"):
        st.subheader("Close the day", icon=":material/favorite:")
        st.caption(
            "A private 30-second check-in helps you notice what made the day work — never to score it."
        )
        with st.form("daily_checkin"):
            first_row, second_row = st.columns(2)
            with first_row:
                energy = st.slider(
                    "Energy",
                    1,
                    10,
                    int(existing_today["energy"]) if existing_today else 6,
                )
                satisfaction = st.slider(
                    "Satisfaction",
                    1,
                    10,
                    int(existing_today["satisfaction"]) if existing_today else 6,
                )
            with second_row:
                focus = st.slider(
                    "Focus",
                    1,
                    10,
                    int(existing_today["focus"]) if existing_today else 6,
                )
                stress = st.slider(
                    "Stress",
                    1,
                    10,
                    int(existing_today["stress"]) if existing_today else 4,
                )
            notes = st.text_area(
                "A note for future you (optional)",
                value=str(existing_today["notes"]) if existing_today else "",
                height=72,
                placeholder="What helped or got in the way?",
            )
            save = st.form_submit_button(
                "Save check-in",
                type="primary",
                icon=":material/save:",
            )
        if save:
            database.upsert_check_in(
                user.id,
                today,
                energy=energy,
                focus=focus,
                satisfaction=satisfaction,
                stress=stress,
                notes=notes,
            )
            st.session_state["insight_reflection"] = ai.reflection(
                energy,
                focus,
                satisfaction,
                stress,
                notes,
            )
            st.rerun()


def _render_first_use_guidance() -> None:
    """Give an empty Progress screen a useful purpose before activity exists."""
    with st.container(border=True, key="review_empty_state"):
        st.subheader("Build a rhythm, not a scorecard", icon=":material/insights:")
        st.caption(
            "Your review gets useful after a few real days. Start with one plan, one focused block, and one honest note."
        )
        milestones = st.columns(3)
        milestones[0].caption(":material/calendar_today: 1. Craft a day")
        milestones[1].caption(":material/timer: 2. Protect time")
        milestones[2].caption(":material/favorite: 3. Check in")
        with st.container(horizontal=True):
            st.button(
                "Craft a day plan",
                key="insights_build_plan",
                type="primary",
                icon=":material/auto_awesome:",
                on_click=_navigate,
                args=("Today",),
            )
            st.button(
                "Start a focus session",
                key="insights_start_focus",
                icon=":material/timer:",
                on_click=_navigate,
                args=("Focus",),
            )
        st.caption("Your first trend appears from real activity only — DayCraft never fills in a story for you.")


def _render_completion_activity_calendar(
    database: Database,
    user: AuthenticatedUser,
    *,
    today: date,
) -> None:
    """Render a 52-week heatmap from only this signed-in user's completed tasks."""
    start_date, _ = completion_activity_window(today)
    # ``daily_activity`` is user-scoped in the data layer. The calendar helper
    # deliberately ignores focus minutes and every other field in these rows.
    activity_rows = database.daily_activity(user.id, start_date, today)
    cells = build_completion_activity_calendar(activity_rows, today=today)
    completed_cells = [cell for cell in cells if cell.completed_tasks > 0 and not cell.is_future]

    with st.container(border=True, key="insights_completion_calendar"):
        st.subheader("Your completion activity", icon=":material/calendar_month:")
        st.caption(
            "Each square is one day from your private task history. Hover or tap a square for its date and completed-task count."
        )
        if not completed_cells:
            st.info(
                "No completed tasks in this 52-week window yet. Mark a task complete to begin your private activity calendar.",
                icon=":material/task_alt:",
            )
            st.caption("This view never imports activity from GitHub, LeetCode, or another account.")
            return

        total_completed = sum(cell.completed_tasks for cell in completed_cells)
        most_active = max(completed_cells, key=lambda cell: cell.completed_tasks)
        max_completed = most_active.completed_tasks
        st.markdown(
            f"**{total_completed} tasks completed across {len(completed_cells)} active days.** "
            f"Most active: {most_active.date_label} ({most_active.activity_label})."
        )
        st.caption(
            "Legend: pale green = no completed tasks; darker green = more completed tasks; grey = upcoming day. "
            "The shade scales to your own 52-week task history."
        )

        chart_frame = pd.DataFrame(
            {
                "week_index": [cell.week_index for cell in cells],
                "weekday": [cell.weekday_label for cell in cells],
                "completed_tasks": [cell.completed_tasks for cell in cells],
                "is_future": [cell.is_future for cell in cells],
                "date_label": [cell.date_label for cell in cells],
                "activity_label": [cell.activity_label for cell in cells],
            }
        )
        color_domain_max = max(4, max_completed)
        heatmap = (
            alt.Chart(chart_frame, title="52-week completed-task activity")
            .mark_rect(stroke="#FFFFFF", strokeWidth=1)
            .encode(
                x=alt.X(
                    "week_index:O",
                    axis=None,
                    scale=alt.Scale(paddingInner=0.18, paddingOuter=0.08),
                ),
                y=alt.Y(
                    "weekday:O",
                    sort=list(WEEKDAY_LABELS),
                    axis=alt.Axis(title=None, labelPadding=8),
                    scale=alt.Scale(paddingInner=0.18, paddingOuter=0.08),
                ),
                color=alt.condition(
                    alt.datum.is_future,
                    alt.value("#E5E7EB"),
                    alt.Color(
                        "completed_tasks:Q",
                        scale=alt.Scale(
                            domain=[0, color_domain_max],
                            range=["#DCFCE7", "#86EFAC", "#22C55E", "#166534"],
                        ),
                        legend=None,
                    ),
                ),
                tooltip=[
                    alt.Tooltip("date_label:N", title="Date"),
                    alt.Tooltip("activity_label:N", title="Completed tasks"),
                ],
            )
            .properties(height=172)
            .configure_view(stroke=None)
        )
        st.altair_chart(heatmap, width="stretch", key="insights_completion_heatmap")


def render_insights(database: Database, user: AuthenticatedUser, ai: AIService) -> None:
    """Render supportive, evidence-based insights without fabricated activity."""
    end_date = date.today()
    heading, controls = st.columns([1.35, 0.65], vertical_alignment="bottom")
    with heading:
        st.markdown(":blue-badge[REVIEW]")
        st.title("See the shape of your week", icon=":material/insights:", anchor=False)
        st.caption("A calm look at the work you finished, the time you protected, and how it felt.")
    with controls:
        period_label = st.segmented_control(
            "Review window",
            ["Last 7 days", "Last 30 days"],
            default="Last 7 days",
            key="insights_period",
            width="stretch",
        )
    _render_completion_activity_calendar(database, user, today=end_date)
    days = 30 if period_label == "Last 30 days" else 7
    start_date = end_date - timedelta(days=days - 1)
    activity = database.daily_activity(user.id, start_date, end_date)
    check_ins = database.get_check_ins(user.id, start_date, end_date)
    activity_frame = pd.DataFrame(activity)
    check_in_frame = pd.DataFrame(check_ins)

    total_tasks = int(activity_frame["completed_tasks"].sum())
    total_focus = int(activity_frame["focus_minutes"].sum())
    has_history = bool(total_tasks or total_focus or not check_in_frame.empty)

    if not has_history:
        _render_first_use_guidance()
    else:
        active_days = int(
            ((activity_frame["completed_tasks"] > 0) | (activity_frame["focus_minutes"] > 0)).sum()
        )
        metric_columns = st.columns(4)
        with metric_columns[0]:
            st.metric(
                "Tasks completed",
                total_tasks,
                icon=":material/task_alt:",
                border=True,
            )
        with metric_columns[1]:
            st.metric(
                "Focus time",
                f"{total_focus} min",
                icon=":material/timer:",
                border=True,
            )
        with metric_columns[2]:
            st.metric(
                "Active days",
                f"{active_days}/{days}",
                icon=":material/calendar_month:",
                border=True,
            )
        with metric_columns[3]:
            st.metric(
                "Check-ins",
                len(check_in_frame),
                icon=":material/favorite:",
                border=True,
            )

        activity_charts: list[tuple[str, str, str, str]] = []
        if total_tasks:
            activity_charts.append(
                ("Completed work", "completed_tasks", "Tasks completed", "#635BFF")
            )
        if total_focus:
            activity_charts.append(("Focused minutes", "focus_minutes", "Minutes", "#0EA5A5"))
        if activity_charts:
            with st.container(border=True, key="review_activity_card"):
                st.subheader("Your recent rhythm", icon=":material/bar_chart:")
                st.caption("A factual view of what made it onto your calendar and into done.")
                chart_columns = st.columns(len(activity_charts))
                for chart_column, (title, column, y_label, color) in zip(
                    chart_columns, activity_charts, strict=True
                ):
                    with chart_column:
                        st.markdown(f"**{title}**")
                        if column == "completed_tasks":
                            st.bar_chart(
                                activity_frame,
                                x="date",
                                y=column,
                                y_label=y_label,
                                color=color,
                            )
                        else:
                            st.area_chart(
                                activity_frame,
                                x="date",
                                y=column,
                                y_label=y_label,
                                color=color,
                            )

        if not check_in_frame.empty:
            with st.container(border=True, key="review_wellbeing_card"):
                st.subheader("How the work felt", icon=":material/favorite:")
                st.line_chart(
                    check_in_frame,
                    x="entry_date",
                    y=["energy", "focus", "satisfaction", "stress"],
                    y_label="Score out of 10",
                    color=["#635BFF", "#0EA5A5", "#D97706", "#DC2626"],
                )
                st.caption(
                    "Energy, focus, satisfaction, and stress are self-reported context — not a performance grade."
                )

    existing_today = next(
        (item for item in check_ins if item["entry_date"] == end_date.isoformat()),
        None,
    )
    _render_check_in(
        database,
        user,
        ai,
        today=end_date,
        existing_today=existing_today,
    )

    reflection = st.session_state.get("insight_reflection")
    if reflection:
        with st.container(border=True, key="review_reflection_card"):
            st.subheader("Reflection note", icon=":material/lightbulb:")
            if reflection.notice:
                st.caption(reflection.notice)
            st.markdown(reflection.content)
