"""The plan-first workspace where real tasks become a realistic day."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, time
from html import escape
from typing import Any

import streamlit as st

from components.ai_session import ai_provider_label, render_ai_setup
from services.ai import AIConfigurationError, AIPlanningError, AIService, DayPlanAdvice
from services.auth import AuthenticatedUser
from services.database import Database
from services.planning import (
    ScheduleBlock,
    ScheduleTemplate,
    build_template_schedule,
    get_day_pace,
    get_schedule_template,
    list_day_paces,
    minutes_from_time,
    template_default_work_hours,
    time_from_minutes,
)

EVENT_CATEGORIES = ["Deep work", "Meeting", "Personal", "Admin", "Health", "Break", "General"]
WORKDAY_START_KEY = "planner_workday_start"
WORKDAY_END_KEY = "planner_workday_end"
PACE_KEY = "planner_day_pace"


def _time_value(value: time) -> str:
    return value.strftime("%H:%M")


def _plan_advice_key(selected_date: date) -> str:
    return f"daycraft_plan_advice_{selected_date.isoformat()}"


def _unscheduled_key(selected_date: date) -> str:
    return f"daycraft_unscheduled_{selected_date.isoformat()}"


def _minutes_between(start_time: time, end_time: time) -> int:
    """Return a non-negative same-day duration without leaking scheduling logic to the UI."""
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    return max(0, end_minutes - start_minutes)


def _format_minutes(total_minutes: int) -> str:
    hours, minutes = divmod(max(0, total_minutes), 60)
    if hours and minutes:
        return f"{hours}h {minutes:02d}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _format_clock(total_minutes: int) -> str:
    hour, minute = divmod(total_minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    clock_hour = hour % 12 or 12
    return f"{clock_hour}:{minute:02d} {suffix}"


def _open_backlog() -> None:
    st.switch_page("app_pages/task_backlog.py")


def _open_focus() -> None:
    st.switch_page("app_pages/focus_mode.py")


def _set_pace_default_hours() -> None:
    """Make the day pace a useful starting point without locking working hours."""
    pace = get_day_pace(str(st.session_state.get(PACE_KEY) or "Balanced"))
    start_value, end_value = template_default_work_hours(pace.template_id)
    st.session_state[WORKDAY_START_KEY] = time.fromisoformat(start_value)
    st.session_state[WORKDAY_END_KEY] = time.fromisoformat(end_value)


def _block_guidance_key(start_time: str, end_time: str, title: str) -> str:
    """Identify a locally validated block without trusting model-provided time."""
    return f"{start_time}|{end_time}|{title}"


def _event_start_end(event: dict[str, Any], start_of_day: int, end_of_day: int) -> tuple[int, int] | None:
    try:
        start = max(start_of_day, minutes_from_time(str(event["start_time"])))
        end = min(end_of_day, minutes_from_time(str(event["end_time"])))
    except (KeyError, TypeError, ValueError):
        return None
    return (start, end) if start < end else None


def _layout_events(
    events: list[dict[str, Any]], start_of_day: int, end_of_day: int
) -> list[tuple[dict[str, Any], int, int, int, int]]:
    """Assign a narrow lane only when real calendar blocks overlap."""
    visible: list[tuple[dict[str, Any], int, int]] = []
    for event in events:
        interval = _event_start_end(event, start_of_day, end_of_day)
        if interval is not None:
            visible.append((event, *interval))
    visible.sort(key=lambda item: (item[1], item[2], str(item[0].get("title", ""))))

    active: list[tuple[int, int]] = []
    layout: list[tuple[dict[str, Any], int, int, int, int]] = []
    cluster_index = -1
    cluster_lanes: dict[int, int] = {}
    for event, event_start, event_end in visible:
        active = [(end, lane) for end, lane in active if end > event_start]
        if not active:
            cluster_index += 1
        occupied_lanes = {lane for _, lane in active}
        lane = next(index for index in range(len(active) + 1) if index not in occupied_lanes)
        active.append((event_end, lane))
        cluster_lanes[cluster_index] = max(cluster_lanes.get(cluster_index, 0), lane + 1)
        layout.append((event, event_start, event_end, lane, cluster_index))

    return [
        (event, event_start, event_end, lane, cluster_lanes[cluster])
        for event, event_start, event_end, lane, cluster in layout
    ]


def _event_tone(event: dict[str, Any]) -> str:
    """Map a saved block to one constrained visual treatment."""
    category = str(event.get("category") or "").lower()
    source = str(event.get("source") or "").lower()
    if source == "template" or (bool(event.get("preview")) and category != "break"):
        return "template"
    if category == "break":
        return "break"
    if source == "planner":
        return "planner"
    if "meeting" in category or "collaboration" in category:
        return "meeting"
    if category == "personal":
        return "personal"
    if category == "health":
        return "health"
    return "admin"


def _render_timeline(
    selected_date: date,
    events: list[dict[str, Any]],
    work_start: time,
    work_end: time,
    *,
    preview: bool,
) -> None:
    """Render a real vertical day canvas with 30-minute divisions."""
    start_of_day = work_start.hour * 60 + work_start.minute
    end_of_day = work_end.hour * 60 + work_end.minute
    total_minutes = max(1, end_of_day - start_of_day)
    # A 30-minute block needs enough vertical room for a legible title.  The
    # calendar is a secondary view, so a little more scroll is preferable to
    # cramming its labels together.
    grid_height = max(560, min(1020, round(total_minutes * 1.55)))
    hour_height = grid_height * 60 / total_minutes
    half_hour_height = hour_height / 2

    template_events = [event for event in events if str(event.get("source")) == "template"]
    real_events = [event for event in events if str(event.get("source")) != "template"]
    positioned_events = _layout_events(real_events, start_of_day, end_of_day)
    labels = range(start_of_day, end_of_day + 1, 60)
    if labels and list(labels)[-1] != end_of_day:
        labels = [*labels, end_of_day]

    rail = "".join(
        f'<span class="dc-time-label'
        f'{" dc-time-label--start" if value == start_of_day else ""}'
        f'{" dc-time-label--end" if value == end_of_day else ""}'
        f'" style="top:{(value - start_of_day) / total_minutes * 100:.4f}%">'
        f"{escape(_format_clock(value))}</span>"
        for value in labels
    )

    event_markup: list[str] = []
    for event, event_start, event_end, lane, lanes in positioned_events:
        top = (event_start - start_of_day) / total_minutes * 100
        height = (event_end - event_start) / total_minutes * 100
        lane_width = 100 / lanes
        left = lane * lane_width + 0.8
        width = max(1, lane_width - 1.6)
        density = "compact" if event_end - event_start <= 35 or lanes > 2 else "standard"
        title = escape(str(event.get("title") or "Untitled block"))
        category = escape(str(event.get("category") or "DayCraft"))
        source_label = category
        event_markup.append(
            f'<article class="dc-calendar-event" data-tone="{_event_tone(event)}" '
            f'data-density="{density}" '
            f'style="top:{top:.4f}%;height:{height:.4f}%;left:{left:.4f}%;width:{width:.4f}%" '
            f'title="{title} · {escape(_format_clock(event_start))}–{escape(_format_clock(event_end))}">'
            f'<span class="dc-event-title">{title}</span>'
            f'<span class="dc-event-meta">{escape(_format_clock(event_start))} · {escape(source_label)}</span>'
            "</article>"
        )

    for event in template_events:
        interval = _event_start_end(event, start_of_day, end_of_day)
        if interval is None:
            continue
        event_start, event_end = interval
        top = (event_start - start_of_day) / total_minutes * 100
        height = (event_end - event_start) / total_minutes * 100
        density = "compact" if event_end - event_start <= 35 else "standard"
        title = escape(str(event.get("title") or "Open work window"))
        category = escape(str(event.get("category") or "Rhythm"))
        event_markup.append(
            f'<article class="dc-calendar-event" data-tone="template" data-density="{density}" '
            f'style="top:{top:.4f}%;height:{height:.4f}%;left:.8%;width:98.4%">'
            f'<span class="dc-event-title">{title}</span>'
            f'<span class="dc-event-meta">{escape(_format_clock(event_start))} · {category} window</span>'
            "</article>"
        )

    now_line = ""
    current = datetime.now()
    current_minutes = current.hour * 60 + current.minute
    if selected_date == current.date() and start_of_day <= current_minutes <= end_of_day:
        now_top = (current_minutes - start_of_day) / total_minutes * 100
        now_line = f'<span class="dc-time-now-line" style="top:{now_top:.4f}%"></span>'

    mode = "Rhythm preview" if preview else "Saved day plan"
    header_date = escape(selected_date.strftime("%A, %d %B"))
    st.markdown(
        f"""
        <section class="dc-schedule-sheet" aria-label="{header_date} time canvas">
          <header class="dc-schedule-sheet-header">
            <span class="dc-schedule-sheet-title">{header_date}</span>
            <span class="dc-schedule-sheet-meta">{mode} · 30 minute grid</span>
          </header>
          <div class="dc-schedule-body" style="--dc-grid-height:{grid_height}px;--dc-hour-height:{hour_height:.2f}px;--dc-half-hour-height:{half_hour_height:.2f}px">
            <div class="dc-time-rail">{rail}</div>
            <div class="dc-time-grid">{now_line}{''.join(event_markup)}</div>
          </div>
          <footer class="dc-schedule-legend">
            <span><i class="dc-legend-dot dc-legend-task"></i>AI task block</span>
            <span><i class="dc-legend-dot dc-legend-break"></i>rhythm / break</span>
            <span><i class="dc-legend-dot dc-legend-commitment"></i>protected commitment</span>
          </footer>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _add_commitment_form(database: Database, user: AuthenticatedUser, selected_date: date) -> None:
    with st.popover("Protect time", icon=":material/lock_clock:", width="stretch"):
        st.caption("A protected commitment stays fixed while DayCraft places task blocks around it.")
        with st.form("add_planner_event", clear_on_submit=True):
            title = st.text_input("Commitment", placeholder="Client check-in")
            time_columns = st.columns(2)
            with time_columns[0]:
                start_time = st.time_input("Starts", value=time(9, 0))
            with time_columns[1]:
                end_time = st.time_input("Ends", value=time(10, 0))
            category = st.selectbox("Type", EVENT_CATEGORIES, index=1)
            location = st.text_input("Location (optional)", placeholder="Video call")
            submitted = st.form_submit_button("Save protected time", type="primary", width="stretch")
        if submitted:
            if not title.strip():
                st.error("Give the commitment a short name.")
            elif start_time >= end_time:
                st.error("The commitment must end after it starts.")
            else:
                database.create_event(
                    user.id,
                    title,
                    selected_date,
                    _time_value(start_time),
                    _time_value(end_time),
                    category=category,
                    location=location,
                    is_fixed=True,
                )
                st.toast("Protected time saved", icon=":material/check_circle:")
                st.rerun()


def _replace_planner_blocks(
    database: Database,
    user: AuthenticatedUser,
    selected_date: date,
    blocks: list[ScheduleBlock],
    *,
    note: str,
) -> None:
    """Replace only regenerable DayCraft blocks; never protected commitments."""
    database.delete_planner_events(user.id, selected_date)
    for block in blocks:
        if block.source != "planner":
            continue
        block_note = (
            f"{note} This is a DayCraft rhythm anchor."
            if block.block_type == "template_anchor"
            else note
        )
        database.create_event(
            user.id,
            block.title,
            selected_date,
            block.start_time,
            block.end_time,
            category=block.category,
            source="planner",
            notes=block_note,
            is_fixed=block.is_fixed,
        )


def _store_template_rhythm(
    database: Database,
    user: AuthenticatedUser,
    selected_date: date,
    work_start: time,
    work_end: time,
    template_id: str,
    pace: str,
) -> list[ScheduleBlock]:
    all_events = database.list_events(user.id, start_date=selected_date, end_date=selected_date)
    fixed_events = [event for event in all_events if event["source"] != "planner"]
    blocks, _ = build_template_schedule(
        selected_date,
        [],
        fixed_events,
        template_id=template_id,
        work_start=_time_value(work_start),
        work_end=_time_value(work_end),
        pace=pace,
    )
    _replace_planner_blocks(
        database,
        user,
        selected_date,
        blocks,
        note="A saved DayCraft schedule rhythm.",
    )
    return blocks


def _build_and_store_plan(
    database: Database,
    user: AuthenticatedUser,
    ai: AIService,
    selected_date: date,
    work_start: time,
    work_end: time,
    intention: str,
    template_id: str,
    pace: str,
) -> tuple[list[ScheduleBlock], list[dict[str, Any]], DayPlanAdvice]:
    all_events = database.list_events(user.id, start_date=selected_date, end_date=selected_date)
    fixed_events = [event for event in all_events if event["source"] != "planner"]
    tasks = database.list_tasks(user.id, include_completed=False)
    template = get_schedule_template(template_id)
    rhythm_context = f"Use the {template.name} rhythm: {template.description}"
    full_intention = ". ".join(part for part in (rhythm_context, intention.strip()) if part)
    advice = ai.create_day_plan(
        selected_date,
        tasks,
        fixed_events,
        work_start=_time_value(work_start),
        work_end=_time_value(work_end),
        intention=full_intention,
        pace=pace,
    )
    blocks, unscheduled = build_template_schedule(
        selected_date,
        tasks,
        fixed_events,
        template_id=template_id,
        work_start=_time_value(work_start),
        work_end=_time_value(work_end),
        task_order=advice.ordered_task_ids,
        pace=pace,
    )
    block_guidance = {
        _block_guidance_key(block.start_time, block.end_time, block.title): advice.task_guidance[block.task_id]
        for block in blocks
        if block.task_id is not None and block.task_id in advice.task_guidance
    }
    advice = replace(advice, block_guidance=block_guidance)
    _replace_planner_blocks(
        database,
        user,
        selected_date,
        blocks,
        note="AI ordered this DayCraft block; timing was validated locally against protected time.",
    )
    database.save_plan(
        user.id,
        "daily",
        f"{advice.focus_theme}\n\n{advice.plan_note}",
        {
            "date": selected_date.isoformat(),
            "provider": advice.provider,
            "fallback": advice.used_fallback,
            "task_order": advice.ordered_task_ids,
            "template": template.id,
            "pace": advice.pace,
            "focus_theme": advice.focus_theme,
            "plan_note": advice.plan_note,
            "block_guidance": advice.block_guidance,
        },
    )
    return blocks, unscheduled, advice


def _render_written_agenda(
    advice: DayPlanAdvice, events: list[dict[str, Any]], unscheduled_titles: list[str]
) -> None:
    """Put the AI-written, locally grounded agenda before the visual calendar.

    The model's words are limited to the already-validated theme, note, and
    task cues.  Every time and commitment shown below comes from the local
    database, so a provider can never add or move calendar reality.
    """
    with st.container(border=True, key="planner_written_agenda"):
        st.markdown(":blue-badge[AI-written day plan]")
        st.subheader(advice.focus_theme, icon=":material/auto_awesome:", anchor=False)
        st.write(advice.plan_note)
        st.caption(
            f"{advice.provider} shaped a {advice.pace.lower()} day; DayCraft validated every time and protected commitment."
        )
        for event in events:
            try:
                start = _format_clock(minutes_from_time(str(event["start_time"])))
                end = _format_clock(minutes_from_time(str(event["end_time"])))
            except (KeyError, TypeError, ValueError):
                continue
            is_commitment = str(event.get("source")) != "planner"
            event_kind = "Protected commitment" if is_commitment else str(event.get("category") or "Task block")
            with st.container(border=True):
                st.markdown(f"**{start}–{end} · {escape(str(event.get('title') or 'Untitled block'))}**")
                st.caption(event_kind)
                cue = advice.block_guidance.get(
                    _block_guidance_key(
                        str(event.get("start_time") or ""),
                        str(event.get("end_time") or ""),
                        str(event.get("title") or ""),
                    )
                )
                if cue:
                    st.write(cue)
        if unscheduled_titles:
            st.warning(
                "Still to place: " + ", ".join(unscheduled_titles) + ". Keep these for another day or shorten the estimates.",
                icon=":material/schedule:",
            )
        if advice.notice:
            st.caption(advice.notice)


def _restore_saved_advice(database: Database, user: AuthenticatedUser, selected_date: date) -> DayPlanAdvice | None:
    """Recover the latest written agenda for this date after a browser refresh."""
    for saved_plan in database.list_plans(user.id, "daily", limit=12):
        try:
            metadata = json.loads(str(saved_plan.get("metadata_json") or "{}"))
        except json.JSONDecodeError:
            continue
        if not isinstance(metadata, dict) or metadata.get("date") != selected_date.isoformat():
            continue
        guidance = metadata.get("block_guidance")
        safe_guidance = (
            {str(key): str(value)[:240] for key, value in guidance.items() if isinstance(key, str) and isinstance(value, str)}
            if isinstance(guidance, dict)
            else {}
        )
        return DayPlanAdvice(
            ordered_task_ids=[int(item) for item in metadata.get("task_order", []) if str(item).isdigit()],
            focus_theme=str(metadata.get("focus_theme") or "Your day is ready."),
            plan_note=str(metadata.get("plan_note") or saved_plan.get("content") or ""),
            provider=str(metadata.get("provider") or "AI planner"),
            used_fallback=bool(metadata.get("fallback")),
            block_guidance=safe_guidance,
            pace=str(metadata.get("pace") or "Balanced"),
        )
    return None


def _render_schedule_list(
    database: Database,
    user: AuthenticatedUser,
    events: list[dict[str, Any]],
) -> None:
    if not events:
        st.caption("The canvas above is a preview. Save a rhythm or build task blocks to make it your plan.")
        return

    with st.expander("Schedule details", icon=":material/format_list_bulleted:"):
        for event in events:
            with st.container(border=True):
                details, actions = st.columns([0.78, 0.22], vertical_alignment="center")
                with details:
                    st.markdown(f"**{event['start_time']}–{event['end_time']} · {event['title']}**")
                    if event["source"] == "planner":
                        source = f"DayCraft · {event['category']}"
                    else:
                        source = f"Protected commitment · {event['category']}"
                    st.caption(source)
                with actions:
                    if st.button(
                        "Remove",
                        icon=":material/close:",
                        key=f"remove_event_{event['id']}",
                        width="stretch",
                    ):
                        database.delete_event(user.id, int(event["id"]))
                        st.rerun()


def _render_plan_canvas_summary(
    events: list[dict[str, Any]],
    work_start: time,
    work_end: time,
    *,
    unscheduled_count: int = 0,
) -> None:
    """Keep capacity visible beside the time canvas without turning it into another dashboard."""
    fixed_events = [
        event for event in events if event.get("source") not in {"planner", "template"}
    ]
    planner_events = [event for event in events if event.get("source") == "planner"]

    def event_minutes(event: dict[str, Any]) -> int:
        try:
            start = time.fromisoformat(str(event["start_time"]))
            end = time.fromisoformat(str(event["end_time"]))
        except (KeyError, TypeError, ValueError):
            return 0
        return _minutes_between(start, end)

    total_capacity = _minutes_between(work_start, work_end)
    fixed_minutes = sum(event_minutes(event) for event in fixed_events)
    scheduled_minutes = sum(event_minutes(event) for event in planner_events)
    available_minutes = max(0, total_capacity - fixed_minutes - scheduled_minutes)
    task_blocks = [
        event
        for event in planner_events
        if str(event.get("category")) not in {"Break", "Planning"}
    ]

    with st.container(border=True, key="plan_canvas_summary"):
        st.markdown('<div class="dc-canvas-label">TODAY\'S CAPACITY</div>', unsafe_allow_html=True)
        st.metric("Scheduled time", _format_minutes(scheduled_minutes), icon=":material/auto_awesome:")
        st.metric("Still open", _format_minutes(available_minutes), icon=":material/hourglass_top:")
        st.caption(f"{len(fixed_events)} protected commitment(s) stay untouched.")
        if unscheduled_count:
            st.warning(
                f"{unscheduled_count} task(s) still need another day or a shorter estimate.",
                icon=":material/schedule:",
            )
        if task_blocks:
            st.button(
                "Start a focus session",
                key="plan_open_focus",
                icon=":material/timer:",
                on_click=_open_focus,
                width="stretch",
            )
        st.caption("This is your local plan. Saving a rhythm only changes DayCraft blocks.")


def _scaled_preview_interval(
    template: ScheduleTemplate, start_time: str, end_time: str, work_start: time, work_end: time
) -> tuple[str, str]:
    """Mirror the template engine's proportional preview for custom working hours."""
    source_start = minutes_from_time(template.default_work_start)
    source_end = minutes_from_time(template.default_work_end)
    actual_start = work_start.hour * 60 + work_start.minute
    actual_end = work_end.hour * 60 + work_end.minute
    source_span = source_end - source_start
    actual_span = actual_end - actual_start
    start = actual_start + round((minutes_from_time(start_time) - source_start) * actual_span / source_span)
    end = actual_start + round((minutes_from_time(end_time) - source_start) * actual_span / source_span)
    return time_from_minutes(max(actual_start, start)), time_from_minutes(min(actual_end, max(start, end)))


def _rhythm_preview_events(
    selected_date: date,
    template: ScheduleTemplate,
    work_start: time,
    work_end: time,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Show a usable template frame before a person chooses to save or generate it."""
    fixed_events = [event for event in events if event.get("source") != "planner"]
    anchors, _ = build_template_schedule(
        selected_date,
        [],
        fixed_events,
        template_id=template.id,
        work_start=_time_value(work_start),
        work_end=_time_value(work_end),
    )
    preview: list[dict[str, Any]] = [
        {
            "title": block.title,
            "start_time": block.start_time,
            "end_time": block.end_time,
            "category": block.category,
            "source": block.source,
            "preview": True,
        }
        for block in anchors
    ]
    for division in template.divisions:
        if division.kind != "task":
            continue
        start_value, end_value = _scaled_preview_interval(
            template, division.start_time, division.end_time, work_start, work_end
        )
        if minutes_from_time(start_value) >= minutes_from_time(end_value):
            continue
        preview.append(
            {
                "title": division.title,
                "start_time": start_value,
                "end_time": end_value,
                "category": division.category,
                "source": "template",
                "preview": True,
            }
        )
    return preview


def _render_day_pace_picker() -> tuple[str, ScheduleTemplate]:
    """Offer one simple decision before planning: how full should today feel?"""
    paces = list_day_paces()
    valid_names = {pace.name for pace in paces}
    selected_name = str(st.session_state.get(PACE_KEY) or "Balanced")
    if selected_name not in valid_names:
        selected_name = "Balanced"
        st.session_state[PACE_KEY] = selected_name
    with st.container(border=True, key="planner_day_pace_card"):
        st.subheader("How full should today feel?", icon=":material/tune:", anchor=False)
        selected_name = st.segmented_control(
            "Day pace",
            [pace.name for pace in paces],
            key=PACE_KEY,
            on_change=_set_pace_default_hours,
            width="stretch",
        )
        pace = get_day_pace(str(selected_name or "Balanced"))
        st.caption(pace.description)
    return pace.name, get_schedule_template(pace.template_id)


def render_planner(database: Database, user: AuthenticatedUser, ai: AIService) -> None:
    """Render one natural flow: choose pace, protect reality, then build a written agenda."""
    st.session_state.setdefault(PACE_KEY, "Balanced")
    pace = get_day_pace(str(st.session_state[PACE_KEY]))
    initial_start, initial_end = template_default_work_hours(pace.template_id)
    st.session_state.setdefault(WORKDAY_START_KEY, time.fromisoformat(initial_start))
    st.session_state.setdefault(WORKDAY_END_KEY, time.fromisoformat(initial_end))

    st.markdown(
        """
        <div class="dc-flow-heading">
          <span class="dc-kicker">SCHEDULE STUDIO</span>
          <h2>Start with the kind of day you actually have.</h2>
          <p>Choose a pace, protect what cannot move, then let AI turn your real work into a written plan inside verified free time.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_pace, selected_template = _render_day_pace_picker()
    with st.container(
        horizontal=True,
        wrap=True,
        vertical_alignment="bottom",
        gap="medium",
        key="planner_toolbar",
    ):
        selected_date = st.date_input("Plan date", value=date.today(), key="plan_date", width=220)
        _add_commitment_form(database, user, selected_date)
        with st.popover("Edit hours", icon=":material/schedule:", width="stretch"):
            st.time_input("Start", key=WORKDAY_START_KEY)
            st.time_input("Finish", key=WORKDAY_END_KEY)

    work_start = st.session_state[WORKDAY_START_KEY]
    work_end = st.session_state[WORKDAY_END_KEY]
    open_tasks = database.list_tasks(user.id, include_completed=False)
    total_estimate = sum(int(task.get("estimated_minutes") or 0) for task in open_tasks)

    action_left, action_right = st.columns([0.36, 0.64], vertical_alignment="bottom")
    with action_left:
        save_rhythm = st.button(
            "Save time divisions",
            key="template_apply",
            icon=":material/bookmark_add:",
            width="stretch",
        )
        st.caption("Replaces only DayCraft blocks; protected commitments stay untouched.")
    with action_right:
        if ai.is_configured:
            st.badge(f"{ai_provider_label(ai)} ready", color="green", icon=":material/auto_awesome:")
        else:
            st.badge("AI key required", color="orange", icon=":material/key:")
        st.caption(
            f"{len(open_tasks)} open task(s) · {_format_minutes(total_estimate)} estimated. "
            "AI writes the agenda; the local planner protects time."
        )
        intention = st.text_input(
            "What needs real thinking today?",
            placeholder="Finish the client proposal before lunch",
            key="planning_intention",
        )
        build = st.button(
            "Create my written plan",
            type="primary",
            icon=":material/auto_awesome:",
            key="planner_build",
            width="stretch",
            disabled=not ai.is_configured or not open_tasks,
        )

    if not ai.is_configured:
        with st.expander("Connect an AI planner to write your day plan", icon=":material/key:", expanded=True):
            ai = render_ai_setup(
                key_prefix="planner",
                heading="AI is required to write your day plan",
                compact=False,
            )

    if save_rhythm:
        if work_start >= work_end:
            st.error("Finish time needs to be after the start time.")
        else:
            with st.spinner("Setting up your day rhythm..."):
                try:
                    _store_template_rhythm(
                        database,
                        user,
                        selected_date,
                        work_start,
                        work_end,
                        selected_template.id,
                        selected_pace,
                    )
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state[_unscheduled_key(selected_date)] = []
                    st.toast("Time divisions saved", icon=":material/check_circle:")
                    st.rerun()

    dashboard_requested_plan = bool(st.session_state.pop("daycraft_request_generate", False))
    if dashboard_requested_plan and not ai.is_configured:
        st.warning(
            "Connect an AI planner first, then DayCraft can turn these tasks into a realistic day.",
            icon=":material/key:",
        )

    if build or (dashboard_requested_plan and ai.is_configured and bool(open_tasks)):
        if work_start >= work_end:
            st.error("Finish time needs to be after the start time.")
        else:
            with st.spinner("Building a realistic plan from your tasks and protected time..."):
                try:
                    blocks, unscheduled, advice = _build_and_store_plan(
                        database,
                        user,
                        ai,
                        selected_date,
                        work_start,
                        work_end,
                        intention,
                        selected_template.id,
                        selected_pace,
                    )
                except (AIConfigurationError, AIPlanningError, ValueError) as error:
                    st.error(str(error))
                else:
                    st.session_state[_plan_advice_key(selected_date)] = advice
                    st.session_state[_unscheduled_key(selected_date)] = [
                        str(task.get("title") or "Untitled task") for task in unscheduled
                    ]
                    if blocks:
                        st.toast("Your AI-written day plan is ready", icon=":material/check_circle:")
                    st.rerun()

    events = database.list_events(user.id, start_date=selected_date, end_date=selected_date)
    advice = st.session_state.get(_plan_advice_key(selected_date)) or _restore_saved_advice(
        database, user, selected_date
    )

    has_saved_task_blocks = any(
        event.get("source") == "planner"
        and str(event.get("category")) not in {"Break", "Planning"}
        for event in events
    )
    canvas_events = (
        events
        if has_saved_task_blocks
        else _rhythm_preview_events(
            selected_date, selected_template, work_start, work_end, events
        )
    )
    unscheduled_titles = list(st.session_state.get(_unscheduled_key(selected_date), []))
    if advice:
        _render_written_agenda(advice, events, unscheduled_titles)

    st.markdown(
        "<div class=\"dc-canvas-heading\"><div><span class=\"dc-kicker\">SECONDARY TIME VIEW</span><h2>Your day on the clock</h2></div><p>The calendar view mirrors the written agenda above; it does not replace it.</p></div>",
        unsafe_allow_html=True,
    )
    with st.container(key="planner_time_canvas"):
        _render_timeline(
            selected_date,
            canvas_events,
            work_start,
            work_end,
            preview=not has_saved_task_blocks,
        )
        if unscheduled_titles:
            chips = "".join(
                f'<span class="dc-unscheduled-chip">{escape(title)}</span>' for title in unscheduled_titles
            )
            st.markdown(
                f'<div class="dc-unscheduled"><strong>Still to place</strong>{chips}</div>',
                unsafe_allow_html=True,
            )

    with st.container(key="planner_time_summary"):
        _render_plan_canvas_summary(
            canvas_events,
            work_start,
            work_end,
            unscheduled_count=len(unscheduled_titles),
        )
        if not open_tasks:
            st.button(
                "Capture a task",
                key="planner_add_first_task",
                type="primary",
                icon=":material/add_task:",
                on_click=_open_backlog,
                width="stretch",
            )

    _render_schedule_list(database, user, events)
