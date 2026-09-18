"""A distraction-light focus space that records durable work sessions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any

import streamlit as st

from components.theme import focus_styles
from services.ai import AIService
from services.auth import AuthenticatedUser
from services.database import Database

SESSION_LENGTHS = (25, 45, 60, 90)


def _new_timer(user_id: int) -> dict[str, object]:
    """Create a timer owned by the signed-in user for this browser session."""
    return {
        "phase": "ready",
        "duration_minutes": 25,
        "task_id": None,
        "task_title": "Free focus",
        "remaining_seconds": 25 * 60,
        "started_at": None,
        "logged": False,
        "session_id": None,
        "owner_id": user_id,
    }


def _timer(user_id: int) -> dict[str, object]:
    """Return a safe, user-scoped timer, resetting stale browser state."""
    existing = st.session_state.get("focus_timer")
    if not isinstance(existing, dict) or existing.get("owner_id") != user_id:
        st.session_state.focus_timer = _new_timer(user_id)
        return st.session_state.focus_timer

    defaults = _new_timer(user_id)
    for key, value in defaults.items():
        existing.setdefault(key, value)
    return existing


def _clear_reflection() -> None:
    st.session_state.pop("focus_reflection_response", None)
    st.session_state.pop("focus_reflection_session_id", None)


def _remaining_seconds(timer: dict[str, object]) -> int:
    remaining = max(0, int(timer.get("remaining_seconds", 0)))
    if timer.get("phase") != "running" or not timer.get("started_at"):
        return remaining
    try:
        started_at = datetime.fromisoformat(str(timer["started_at"]))
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return remaining
    elapsed = int((datetime.now(UTC) - started_at).total_seconds())
    return max(0, remaining - elapsed)


def _task_id_for_user(database: Database, user_id: int, task_id: object) -> int | None:
    """Defend the database link if browser state is stale or manipulated."""
    try:
        candidate = int(task_id) if task_id is not None else None
    except (TypeError, ValueError):
        return None
    if candidate is None:
        return None
    return candidate if database.get_task(user_id, candidate) else None


def _log_completion(database: Database, user_id: int, timer: dict[str, object], minutes: int) -> None:
    if bool(timer.get("logged")):
        return
    session = database.record_focus_session(
        user_id,
        max(1, minutes),
        _task_id_for_user(database, user_id, timer.get("task_id")),
    )
    timer["logged"] = True
    timer["session_id"] = session.get("id")


def _start_timer(user_id: int, duration: int, task_id: int | None, task_title: str) -> None:
    st.session_state.focus_timer = {
        "phase": "running",
        "duration_minutes": duration,
        "task_id": task_id,
        "task_title": task_title,
        "remaining_seconds": duration * 60,
        "started_at": datetime.now(UTC).isoformat(),
        "logged": False,
        "session_id": None,
        "owner_id": user_id,
    }
    _clear_reflection()


def _finish_timer(database: Database, user_id: int, timer: dict[str, object], remaining: int) -> None:
    total_seconds = max(1, int(timer["duration_minutes"]) * 60)
    elapsed_minutes = max(1, round((total_seconds - remaining) / 60))
    _log_completion(database, user_id, timer, elapsed_minutes)
    timer["phase"] = "complete"
    timer["started_at"] = None
    timer["remaining_seconds"] = remaining


def _timer_markup(timer: dict[str, object], remaining: int) -> str:
    minutes, seconds = divmod(remaining, 60)
    phase = str(timer.get("phase", "ready"))
    copy = {
        "ready": ("Ready when you are", "Choose one thing, then make room for it."),
        "running": ("Deep work in progress", "Everything else can wait for a little while."),
        "paused": ("Session paused", "Take a breath. Resume when you are ready."),
        "complete": ("Session complete", "Your focused minutes have been saved."),
    }
    status, note = copy.get(phase, copy["ready"])
    task_title = escape(str(timer.get("task_title") or "Free focus"))
    duration = max(1, int(timer.get("duration_minutes", 25)))
    return f"""
    <section class="dc-focus-timer" aria-label="Focus timer">
      <div class="dc-focus-timer-topline">
        <span class="dc-focus-status">{escape(status)}</span>
        <span>{duration} minute block</span>
      </div>
      <div class="dc-focus-clock">{minutes:02d}:{seconds:02d}</div>
      <p class="dc-focus-note">{escape(note)}</p>
      <div class="dc-focus-task"><span>Working on</span><strong>{task_title}</strong></div>
    </section>
    """


def _render_reflection(database: Database, user_id: int, ai: AIService, timer: dict[str, object]) -> None:
    """Reveal an optional, compact reflection only after a saved session."""
    session_id = timer.get("session_id")
    if timer.get("phase") != "complete" or not session_id:
        return

    with st.container(border=True, key="focus_reflection_card"):
        st.subheader("Close the loop", anchor=False)
        st.caption("Optional: one sentence is enough. It helps make Progress useful over time.")
        with st.form("focus_reflection", border=False):
            reflection = st.text_area(
                "What helped or got in the way?",
                placeholder="For example: starting before opening email made this easier.",
                height=92,
            )
            ratings = st.columns(2)
            energy = ratings[0].slider("Energy", 1, 10, 6, key="focus_energy")
            focus = ratings[1].slider("Focus", 1, 10, 6, key="focus_quality")
            submit_reflection = st.form_submit_button("Save reflection", icon=":material/check:")

        if submit_reflection:
            database.upsert_check_in(
                user_id,
                datetime.now().date(),
                energy=energy,
                focus=focus,
                satisfaction=focus,
                stress=max(1, 11 - energy),
                notes=reflection,
            )
            st.session_state["focus_reflection_response"] = ai.reflection(
                energy, focus, focus, max(1, 11 - energy), reflection
            )
            st.session_state["focus_reflection_session_id"] = session_id
            st.toast("Reflection saved to Progress.", icon=":material/check_circle:")

        response = st.session_state.get("focus_reflection_response")
        if st.session_state.get("focus_reflection_session_id") == session_id and response:
            if response.notice:
                st.caption(response.notice)
            st.markdown(response.content)


@st.fragment(run_every=timedelta(seconds=1), key="focus_console")
def _render_focus_console(
    database: Database,
    user_id: int,
    tasks: list[dict[str, Any]],
    ai: AIService,
) -> None:
    """Render the complete focus interaction independently of the rest of the app."""
    timer = _timer(user_id)
    phase = str(timer.get("phase", "ready"))
    remaining = _remaining_seconds(timer)
    total_seconds = max(1, int(timer.get("duration_minutes", 25)) * 60)

    if phase == "running" and remaining == 0:
        _finish_timer(database, user_id, timer, remaining)
        st.rerun()

    task_by_id = {int(task["id"]): task for task in tasks}
    task_ids: list[int | None] = [None, *task_by_id]
    if st.session_state.get("focus_task_id") not in task_ids:
        st.session_state["focus_task_id"] = None
    if st.session_state.get("focus_duration") not in SESSION_LENGTHS:
        st.session_state["focus_duration"] = 25

    active = phase in {"running", "paused"}
    with st.container(border=True, key="focus_console_card"):
        st.markdown(_timer_markup(timer, remaining), unsafe_allow_html=True)
        st.progress(
            min(1.0, max(0.0, (total_seconds - remaining) / total_seconds)),
            text=f"{max(0, total_seconds - remaining) // 60} minutes protected",
        )

        if active:
            st.caption(
                "Your session is locked to this task. Pause, finish early, or reset it before choosing another one."
            )
            controls = st.container(horizontal=True, horizontal_alignment="center", wrap=True)
            if phase == "running":
                if controls.button("Pause", key="focus_pause", icon=":material/pause:"):
                    timer["remaining_seconds"] = remaining
                    timer["started_at"] = None
                    timer["phase"] = "paused"
                    st.rerun()
            else:
                if controls.button(
                    "Resume", type="primary", key="focus_resume", icon=":material/play_arrow:"
                ):
                    timer["started_at"] = datetime.now(UTC).isoformat()
                    timer["phase"] = "running"
                    st.rerun()
            if controls.button("End & save", key="focus_finish", icon=":material/check:"):
                _finish_timer(database, user_id, timer, remaining)
                st.rerun()
            if controls.button("Reset", key="focus_reset", icon=":material/restart_alt:"):
                st.session_state.focus_timer = _new_timer(user_id)
                _clear_reflection()
                st.rerun()
        else:
            setup = st.container(key="focus_setup")
            with setup:
                setup_title, duration_title = st.columns([1.35, 0.65], vertical_alignment="bottom")
                with setup_title:
                    selected_task_id = st.selectbox(
                        "What are you focusing on?",
                        task_ids,
                        format_func=lambda task_id: (
                            "Focus without a linked task"
                            if task_id is None
                            else str(task_by_id[task_id]["title"])
                        ),
                        key="focus_task_id",
                        persist_state="session",
                    )
                with duration_title:
                    selected_duration = st.segmented_control(
                        "Session length",
                        SESSION_LENGTHS,
                        format_func=lambda minutes: f"{minutes}m",
                        required=True,
                        key="focus_duration",
                        persist_state="session",
                        width="stretch",
                    )
            if not tasks:
                st.caption(
                    "No open tasks yet. You can start a free session now, or add a task later to connect the work."
                )
            button_label = "Start another session" if phase == "complete" else "Start focus"
            with st.container(horizontal=True, horizontal_alignment="center"):
                if st.button(
                    button_label,
                    type="primary",
                    key="focus_start",
                    icon=":material/play_arrow:",
                    width="content",
                ):
                    safe_task_id = selected_task_id if selected_task_id in task_by_id else None
                    task_title = (
                        str(task_by_id[safe_task_id]["title"]) if safe_task_id is not None else "Free focus"
                    )
                    _start_timer(user_id, int(selected_duration or 25), safe_task_id, task_title)
                    st.rerun()
            if phase == "complete":
                if st.button(
                    "Reset timer", key="focus_reset_complete", icon=":material/restart_alt:", width="content"
                ):
                    st.session_state.focus_timer = _new_timer(user_id)
                    _clear_reflection()
                    st.rerun()

    _render_reflection(database, user_id, ai, timer)


def render_focus(database: Database, user: AuthenticatedUser, ai: AIService) -> None:
    """Render a one-decision focus flow: choose, start, then reflect."""
    focus_styles()
    today_metrics = database.dashboard_metrics(user.id, datetime.now().date())
    tasks = database.list_tasks(user.id, include_completed=False)
    next_task = str(tasks[0]["title"]) if tasks else "Free focus"

    title, summary = st.columns([1.35, 0.65], vertical_alignment="center")
    with title:
        st.markdown(":blue-badge[FOCUS STUDIO]")
        st.title("Protect the next block", icon=":material/center_focus_strong:", anchor=False)
        st.caption(
            "Choose one meaningful outcome, protect the time, then return with a cleaner record of the day."
        )
    with summary:
        st.metric("Protected today", f"{today_metrics['focus_minutes']} min")
        st.caption("Saved sessions feed your Review — nothing is inferred.")

    with st.container(border=True, key="focus_intention_card"):
        context, outcome = st.columns([0.42, 0.58], vertical_alignment="center")
        with context:
            st.markdown("**Your focus lane**")
            st.caption(
                f"{len(tasks)} task{'s' if len(tasks) != 1 else ''} ready to work on."
            )
        with outcome:
            st.markdown("**Suggested starting point**")
            st.caption(next_task)

    _render_focus_console(database, user.id, tasks, ai)
