"""Persistent task capture, prioritization, and lightweight editing."""

from __future__ import annotations

from datetime import date
from datetime import time as clock_time

import pandas as pd
import plotly.express as px
import streamlit as st

from components.theme import empty_state, page_intro
from services.auth import AuthenticatedUser
from services.database import Database
from services.task_capture import TaskCapturePreview, parse_task_capture

CATEGORIES = ["General", "Deep work", "Work", "Personal", "Learning", "Admin", "Health"]
COMMITMENT_CATEGORIES = ["General", "Work", "Meetings", "Personal", "Learning", "Admin", "Health"]
PRIORITIES = ["High", "Medium", "Low"]

_CAPTURE_PREVIEW_KEY = "task_capture_preview"
_CAPTURE_DATE_KEY = "task_capture_preview_date"
_CAPTURE_VERSION_KEY = "task_capture_preview_version"


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


def _clear_quick_capture_preview() -> None:
    """Remove only the transient review data; nothing stored in the database changes."""
    st.session_state.pop(_CAPTURE_PREVIEW_KEY, None)
    st.session_state.pop(_CAPTURE_DATE_KEY, None)


def _capture_preview_date() -> date:
    stored = st.session_state.get(_CAPTURE_DATE_KEY)
    if isinstance(stored, str):
        try:
            return date.fromisoformat(stored)
        except ValueError:
            pass
    return date.today()


def _category_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def _time_from_storage(value: str) -> clock_time:
    try:
        hour, minute = value.split(":", 1)
        return clock_time(int(hour), int(minute))
    except (AttributeError, TypeError, ValueError):
        return clock_time(9, 0)


def _time_to_storage(value: clock_time | None) -> str:
    if not isinstance(value, clock_time):
        return ""
    return f"{value.hour:02d}:{value.minute:02d}"


def _clean_review_title(value: str) -> str:
    return " ".join(value.split()).strip()


def _review_minutes(value: object) -> int | None:
    """Re-validate a browser-provided estimate before it reaches persistence."""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return None
    return minutes if 5 <= minutes <= 480 else None


def _render_quick_capture(database: Database, user: AuthenticatedUser) -> None:
    """Render a side-effect-free capture preview, then an explicit import review."""
    with st.container(border=True, key="quick_capture_card"):
        st.subheader("Drop in your day", icon=":material/auto_awesome:", anchor=False)
        st.caption(
            "Write naturally. DayCraft keeps explicit times protected and leaves the rest flexible for your plan."
        )
        with st.form("quick_task_capture", clear_on_submit=False, border=False):
            raw_capture = st.text_area(
                "Tasks and commitments",
                placeholder=(
                    "Lunch from 1 to 2, workout, meeting at 9 for half an hour, read 10 pages"
                ),
                height=104,
                max_chars=4_000,
                help="Use commas or new lines. Timed blocks need a range or a duration.",
            )
            selected_date = st.date_input(
                "Plan this date",
                value=date.today(),
                help="Timed commitments will be protected on this local DayCraft plan date.",
            )
            review_requested = st.form_submit_button(
                "Review items", type="primary", icon=":material/visibility:"
            )
        if review_requested:
            preview = parse_task_capture(raw_capture)
            if not preview.item_count:
                _clear_quick_capture_preview()
                for warning in preview.warnings:
                    st.warning(warning, icon=":material/info:")
            else:
                st.session_state[_CAPTURE_PREVIEW_KEY] = preview
                st.session_state[_CAPTURE_DATE_KEY] = selected_date.isoformat()
                st.session_state[_CAPTURE_VERSION_KEY] = int(
                    st.session_state.get(_CAPTURE_VERSION_KEY, 0)
                ) + 1

    preview = st.session_state.get(_CAPTURE_PREVIEW_KEY)
    if not isinstance(preview, TaskCapturePreview):
        return

    capture_date = _capture_preview_date()
    version = int(st.session_state.get(_CAPTURE_VERSION_KEY, 0))
    with st.container(border=True, key="quick_capture_review"):
        st.subheader("Review before adding", icon=":material/fact_check:", anchor=False)
        display_date = f"{capture_date:%A, %b} {capture_date.day}"
        st.caption(
            f"Nothing has been saved yet. Review the {preview.item_count} item(s) for {display_date} "
            "and choose exactly what to add."
        )
        for warning in preview.warnings:
            st.warning(warning, icon=":material/info:")

        with st.form("quick_capture_review_form", border=False):
            reviewed_tasks: list[dict[str, object]] = []
            reviewed_commitments: list[dict[str, object]] = []

            if preview.commitments:
                st.markdown("**Protected time**")
                st.caption("These stay fixed while DayCraft fits flexible work around them.")
                for index, item in enumerate(preview.commitments):
                    with st.container(border=True):
                        include = st.checkbox(
                            "Add this protected time",
                            value=True,
                            key=f"capture_commitment_include_{version}_{index}",
                        )
                        title = st.text_input(
                            "Commitment",
                            value=item.title,
                            key=f"capture_commitment_title_{version}_{index}",
                        )
                        start_column, end_column, category_column = st.columns(3)
                        with start_column:
                            start = st.time_input(
                                "Starts",
                                value=_time_from_storage(item.start_time),
                                format="24h",
                                key=f"capture_commitment_start_{version}_{index}",
                            )
                        with end_column:
                            end = st.time_input(
                                "Ends",
                                value=_time_from_storage(item.end_time),
                                format="24h",
                                key=f"capture_commitment_end_{version}_{index}",
                            )
                        with category_column:
                            category = st.selectbox(
                                "Category",
                                COMMITMENT_CATEGORIES,
                                index=_category_index(COMMITMENT_CATEGORIES, item.category),
                                key=f"capture_commitment_category_{version}_{index}",
                            )
                    reviewed_commitments.append(
                        {
                            "include": include,
                            "title": title,
                            "start": start,
                            "end": end,
                            "category": category,
                        }
                    )

            if preview.tasks:
                st.markdown("**Flexible tasks**")
                st.caption("These enter your task queue with the estimate shown. The planner decides their time around protected commitments.")
                for index, item in enumerate(preview.tasks):
                    with st.container(border=True):
                        include = st.checkbox(
                            "Add this task",
                            value=True,
                            key=f"capture_task_include_{version}_{index}",
                        )
                        title = st.text_input(
                            "Task title",
                            value=item.title,
                            key=f"capture_task_title_{version}_{index}",
                        )
                        estimate_column, category_column, priority_column = st.columns(3)
                        with estimate_column:
                            estimated_minutes = st.number_input(
                                "Minutes",
                                min_value=5,
                                max_value=480,
                                value=int(item.estimated_minutes),
                                step=5,
                                key=f"capture_task_minutes_{version}_{index}",
                            )
                        with category_column:
                            category = st.selectbox(
                                "Category",
                                CATEGORIES,
                                index=_category_index(CATEGORIES, item.category),
                                key=f"capture_task_category_{version}_{index}",
                            )
                        with priority_column:
                            priority = st.selectbox(
                                "Priority",
                                PRIORITIES,
                                index=_category_index(PRIORITIES, item.priority),
                                key=f"capture_task_priority_{version}_{index}",
                            )
                    reviewed_tasks.append(
                        {
                            "include": include,
                            "title": title,
                            "estimated_minutes": estimated_minutes,
                            "category": category,
                            "priority": priority,
                        }
                    )

            confirmation = st.checkbox(
                "I reviewed these items and want to add the selected ones to my DayCraft workspace.",
                key=f"capture_confirmation_{version}",
            )
            save_column, discard_column = st.columns(2)
            with save_column:
                save_review = st.form_submit_button(
                    "Add reviewed items", type="primary", icon=":material/add_task:"
                )
            with discard_column:
                discard_review = st.form_submit_button("Discard review", icon=":material/close:")

        if discard_review:
            _clear_quick_capture_preview()
            st.toast("Review discarded. Nothing was added.", icon=":material/delete_outline:")
            st.rerun()

        if save_review:
            selected_tasks = [item for item in reviewed_tasks if bool(item["include"])]
            selected_commitments = [
                item for item in reviewed_commitments if bool(item["include"])
            ]
            validation_errors: list[str] = []
            if not confirmation:
                validation_errors.append("Confirm that you reviewed the selected items before adding them.")
            if not selected_tasks and not selected_commitments:
                validation_errors.append("Select at least one task or protected time block to add.")

            for item in selected_tasks:
                title = _clean_review_title(str(item["title"]))
                minutes = _review_minutes(item["estimated_minutes"])
                if not title or len(title) > 140:
                    validation_errors.append("Each selected task needs a title of 1–140 characters.")
                if minutes is None:
                    validation_errors.append("Each selected task estimate must be between 5 and 480 minutes.")
                if item["category"] not in CATEGORIES or item["priority"] not in PRIORITIES:
                    validation_errors.append("A selected task has an unsupported category or priority.")

            for item in selected_commitments:
                title = _clean_review_title(str(item["title"]))
                start = item["start"]
                end = item["end"]
                if not title or len(title) > 140:
                    validation_errors.append("Each selected commitment needs a title of 1–140 characters.")
                if not isinstance(start, clock_time) or not isinstance(end, clock_time) or start >= end:
                    validation_errors.append("Each selected commitment must end after it starts on the same day.")
                if item["category"] not in COMMITMENT_CATEGORIES:
                    validation_errors.append("A selected commitment has an unsupported category.")

            if validation_errors:
                for error in dict.fromkeys(validation_errors):
                    st.error(error, icon=":material/error:")
            else:
                for item in selected_tasks:
                    database.create_task(
                        user.id,
                        _clean_review_title(str(item["title"])),
                        priority=str(item["priority"]),
                        category=str(item["category"]),
                        due_date=capture_date,
                        estimated_minutes=_review_minutes(item["estimated_minutes"]) or 30,
                        notes="Added through quick capture.",
                    )
                for item in selected_commitments:
                    database.create_event(
                        user.id,
                        _clean_review_title(str(item["title"])),
                        capture_date,
                        _time_to_storage(item["start"] if isinstance(item["start"], clock_time) else None),
                        _time_to_storage(item["end"] if isinstance(item["end"], clock_time) else None),
                        category=str(item["category"]),
                        is_fixed=True,
                        source="capture",
                        notes="Protected time added through quick capture.",
                    )
                _clear_quick_capture_preview()
                st.toast("Reviewed items added. Your planner can now place work around protected time.", icon=":material/check_circle:")
                st.rerun()


def _render_manual_task_capture(database: Database, user: AuthenticatedUser) -> None:
    """Keep precise single-task entry available without competing with quick capture."""
    with st.expander("Add one task manually", icon=":material/add_task:"):
        st.caption("Use this when you already know all of the details.")
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

    _render_quick_capture(database, user)
    _render_manual_task_capture(database, user)

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
