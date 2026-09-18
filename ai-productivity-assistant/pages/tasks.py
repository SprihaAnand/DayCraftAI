"""Persistent task capture, prioritization, and lightweight editing."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from components.theme import empty_state, page_intro
from services.auth import AuthenticatedUser
from services.database import Database

CATEGORIES = ["General", "Deep work", "Work", "Personal", "Learning", "Admin", "Health"]
PRIORITIES = ["High", "Medium", "Low"]


def _urgency(task: dict[str, object]) -> int:
    due_date = task.get("due_date")
    if not due_date:
        return 3
    days = (date.fromisoformat(str(due_date)) - date.today()).days
    if days <= 0:
        return 10
    if days == 1:
        return 8
    if days <= 3:
        return 6
    return 4


def _importance(priority: str) -> int:
    return {"High": 9, "Medium": 6, "Low": 3}.get(priority, 5)


def render_tasks(database: Database, user: AuthenticatedUser) -> None:
    """Render a calm task inbox that makes the next planning decision obvious."""
    tasks = database.list_tasks(user.id, include_completed=True)
    open_tasks = [task for task in tasks if task["status"] != "completed"]
    due_soon = [task for task in open_tasks if _urgency(task) >= 8]
    planned_minutes = sum(int(task["estimated_minutes"]) for task in open_tasks)

    page_intro(
        "Task studio",
        "Turn loose ends into a plan.",
        "Capture the work, make its shape clear, then let Today place it where it fits.",
    )

    metric_columns = st.columns(3)
    metric_columns[0].metric("Ready to plan", len(open_tasks), help="Open tasks in your workspace.")
    metric_columns[1].metric(
        "Needs attention",
        len(due_soon),
        help="Open work due today or tomorrow.",
    )
    metric_columns[2].metric(
        "Open capacity",
        f"{planned_minutes // 60}h {planned_minutes % 60:02d}m",
        help="Your current estimate for all open tasks.",
    )

    with st.container(border=True, key="task_capture_card"):
        st.subheader("Capture an intention", icon=":material/add_task:", anchor=False)
        st.caption("Keep the title specific. You can add the context that makes it schedulable below.")
        with st.form("add_task", clear_on_submit=True, border=False):
            title = st.text_input("Task", placeholder="Prepare the client review")
            details = st.expander("Add timing and context", icon=":material/tune:")
            with details:
                notes = st.text_area(
                    "Notes (optional)",
                    placeholder="What does done look like?",
                    height=72,
                )
                column_one, column_two, column_three, column_four = st.columns(4)
                with column_one:
                    priority = st.selectbox("Priority", PRIORITIES, index=1)
                with column_two:
                    category = st.selectbox("Category", CATEGORIES)
                with column_three:
                    due_date = st.date_input("Due date", value=None)
                with column_four:
                    estimated_minutes = st.selectbox(
                        "Estimate", [15, 30, 45, 60, 90, 120, 180], index=1
                    )
            submitted = st.form_submit_button(
                "Save task", type="primary", icon=":material/add:"
            )
        if submitted:
            if not title.strip():
                st.error("Give the task a clear title.")
            else:
                database.create_task(
                    user.id,
                    title,
                    priority=priority,
                    category=category,
                    due_date=due_date,
                    estimated_minutes=estimated_minutes,
                    notes=notes,
                )
                st.toast("Task added to your studio.", icon=":material/check_circle:")
                st.rerun()

    list_tab, matrix_tab = st.tabs(["Your queue", "Priority map"])

    with list_tab:
        st.subheader("Choose what belongs in today", icon=":material/view_list:", anchor=False)
        st.caption("High-priority and time-sensitive work rises to the top. Everything else stays safely in view.")
        status_filter, priority_filter = st.columns([1.2, 0.8], vertical_alignment="bottom")
        with status_filter:
            status = st.segmented_control(
                "Show",
                ["Open", "Completed", "All"],
                default="Open",
                required=True,
                key="task_status_filter",
            )
        with priority_filter:
            priority_choice = st.selectbox(
                "Priority", ["All", *PRIORITIES], key="task_priority_filter"
            )
        filtered_tasks = [
            task
            for task in tasks
            if (
                (status == "All" or (status == "Completed") == (task["status"] == "completed"))
                and (priority_choice == "All" or task["priority"] == priority_choice)
            )
        ]
        if not filtered_tasks:
            empty_state(
                "Your queue is clear",
                "Add a task above, or change the view to revisit completed work.",
            )
        for task in filtered_tasks:
            is_complete = task["status"] == "completed"
            with st.container(border=True, key=f"task_card_{task['id']}"):
                task_columns = st.columns([0.08, 0.66, 0.26], vertical_alignment="center")
                with task_columns[0]:
                    complete = st.checkbox(
                        "Complete",
                        value=is_complete,
                        key=f"task_complete_{task['id']}",
                        label_visibility="collapsed",
                    )
                    if complete != is_complete:
                        database.set_task_status(user.id, int(task["id"]), completed=complete)
                        st.rerun()
                with task_columns[1]:
                    title = f"~~{task['title']}~~" if is_complete else task["title"]
                    st.markdown(f"**{title}**")
                    due_label = f"Due {task['due_date']}" if task["due_date"] else "Flexible timing"
                    st.caption(
                        f"{task['category']} · {task['estimated_minutes']} min · {due_label}"
                    )
                with task_columns[2]:
                    st.markdown(
                        f'<span class="dc-pill dc-pill-{str(task["priority"]).lower()}">{task["priority"]}</span>',
                        unsafe_allow_html=True,
                    )
                    with st.popover(
                        "Edit",
                        icon=":material/edit:",
                        key=f"task_edit_{task['id']}",
                        width="content",
                    ):
                        st.caption("Refine the details that affect its placement.")
                        current_due = (
                            date.fromisoformat(task["due_date"]) if task["due_date"] else None
                        )
                        with st.form(f"edit_task_{task['id']}"):
                            updated_title = st.text_input("Task", value=task["title"])
                            updated_notes = st.text_area("Notes", value=task["notes"], height=72)
                            edit_one, edit_two = st.columns(2)
                            with edit_one:
                                updated_priority = st.selectbox(
                                    "Priority",
                                    PRIORITIES,
                                    index=PRIORITIES.index(task["priority"]),
                                )
                                updated_due = st.date_input(
                                    "Due date", value=current_due, key=f"due_{task['id']}"
                                )
                            with edit_two:
                                updated_category = st.selectbox(
                                    "Category",
                                    CATEGORIES,
                                    index=(
                                        CATEGORIES.index(task["category"])
                                        if task["category"] in CATEGORIES
                                        else 0
                                    ),
                                )
                                estimate_options = [15, 30, 45, 60, 90, 120, 180]
                                current_estimate = int(task["estimated_minutes"])
                                updated_estimate = st.selectbox(
                                    "Estimate",
                                    estimate_options,
                                    index=(
                                        estimate_options.index(current_estimate)
                                        if current_estimate in estimate_options
                                        else 1
                                    ),
                                )
                            save_column, delete_column = st.columns(2)
                            save = save_column.form_submit_button("Save changes", type="primary")
                            delete = delete_column.form_submit_button("Delete task")
                        if save:
                            if not updated_title.strip():
                                st.error("A task needs a title.")
                            else:
                                database.update_task(
                                    user.id,
                                    int(task["id"]),
                                    title=updated_title,
                                    notes=updated_notes,
                                    priority=updated_priority,
                                    category=updated_category,
                                    due_date=updated_due,
                                    estimated_minutes=updated_estimate,
                                )
                                st.toast("Task updated.", icon=":material/check_circle:")
                                st.rerun()
                        if delete:
                            database.delete_task(user.id, int(task["id"]))
                            st.toast("Task deleted.", icon=":material/delete:")
                            st.rerun()

    with matrix_tab:
        st.subheader("A faster way to choose", icon=":material/grid_view:", anchor=False)
        st.caption("Move the upper-right work into your day first; keep the rest visible without overloading it.")
        if not open_tasks:
            empty_state("No open tasks", "Add something to prioritize when you are ready.")
        else:
            matrix_data = pd.DataFrame(
                [
                    {
                        "Task": task["title"],
                        "Urgency": _urgency(task),
                        "Importance": _importance(str(task["priority"])),
                        "Priority": task["priority"],
                        "Estimate": f"{task['estimated_minutes']} min",
                    }
                    for task in open_tasks
                ]
            )
            figure = px.scatter(
                matrix_data,
                x="Urgency",
                y="Importance",
                color="Priority",
                hover_data=["Task", "Estimate"],
                range_x=[0, 10.5],
                range_y=[0, 10.5],
                color_discrete_map={"High": "#DC2626", "Medium": "#D97706", "Low": "#16A34A"},
            )
            figure.add_hline(y=5, line_dash="dot", line_color="#A7A9B8")
            figure.add_vline(x=5, line_dash="dot", line_color="#A7A9B8")
            figure.update_layout(
                title="",
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                height=440,
                margin={"l": 20, "r": 20, "t": 20, "b": 20},
            )
            st.plotly_chart(figure, width="stretch")
            st.caption("Urgency comes from due dates; importance comes from the priority you chose.")
