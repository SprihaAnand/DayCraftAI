"""Visual system and small safe presentation helpers for the Streamlit app."""

from __future__ import annotations

from html import escape

import streamlit as st


def configure_page() -> None:
    st.set_page_config(
        page_title="DayCraft — Your day, intentionally",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={"About": "DayCraft is a private, AI-assisted productivity workspace."},
    )


def apply_theme() -> None:
    """Apply the original schedule-studio treatment used across the workspace.

    Theme tokens live in ``.streamlit/config.toml``. The narrow CSS layer here is
    intentional: it provides the calendar grid and editorial canvas that native
    Streamlit widgets cannot express by themselves.
    """
    st.markdown(
        """
        <style>
        :root {
            --dc-paper: #FFFDF7;
            --dc-canvas: #F4F2EA;
            --dc-ink: #101217;
            --dc-muted: #59616D;
            --dc-blue: #2769DC;
            --dc-navy: #173B84;
            --dc-acid: #EFFF3E;
            --dc-coral: #FF7A5C;
            --dc-line: #101217;
            --dc-soft-blue: #E7F0FF;
            --dc-soft-lime: #F7FFC2;
        }
        .stApp { background: var(--dc-canvas); color: var(--dc-ink); }
        [data-testid="stHeader"] {
            background: rgba(244, 242, 234, .93);
            border-bottom: 2px solid var(--dc-line);
        }
        .block-container { max-width: 1480px; padding-top: 1.8rem; padding-bottom: 3.8rem; }
        h1, h2, h3, h4 { color: var(--dc-ink); letter-spacing: -.045em; }
        h1 { font-weight: 750; }
        p, label, [data-testid="stCaptionContainer"] { color: var(--dc-muted); }
        [data-testid="stSidebar"] { background: var(--dc-navy); border-right: 2px solid var(--dc-line); }
        [data-testid="stSidebar"] * { color: var(--dc-paper); }
        [data-testid="stSidebar"] [data-testid="stButton"] > button {
            color: var(--dc-ink) !important;
            background: var(--dc-acid) !important;
            border-color: var(--dc-ink) !important;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
            transform: translate(-1px, -1px);
            box-shadow: 4px 4px 0 var(--dc-ink);
        }
        [data-testid="stNavigation"] {
            background: var(--dc-paper);
            border: 2px solid var(--dc-line);
            box-shadow: 4px 4px 0 var(--dc-line);
            padding: .25rem .4rem;
        }
        [data-testid="stNavigation"] a, [data-testid="stSidebarNav"] a { border-radius: 3px; }
        [data-testid="stNavigation"] a[aria-current="page"] {
            color: var(--dc-ink) !important;
            background: var(--dc-acid) !important;
        }
        [data-testid="stMetric"] {
            background: var(--dc-paper);
            border: 2px solid var(--dc-line);
            border-radius: 4px;
            padding: .95rem 1rem;
            box-shadow: 4px 4px 0 rgba(16, 18, 23, .92);
        }
        [data-testid="stMetricLabel"] { color: var(--dc-muted); font-size: .76rem; font-weight: 700; letter-spacing: .075em; text-transform: uppercase; }
        [data-testid="stMetricValue"] { color: var(--dc-ink); font-weight: 750; }
        [data-testid="stButton"] > button, [data-testid="stDownloadButton"] > button {
            min-height: 2.55rem;
            border: 2px solid var(--dc-line);
            border-radius: 4px;
            font-weight: 750;
            letter-spacing: -.01em;
            box-shadow: 3px 3px 0 rgba(16, 18, 23, .92);
            transition: transform .12s ease, box-shadow .12s ease, background .12s ease;
        }
        [data-testid="stButton"] > button:hover, [data-testid="stDownloadButton"] > button:hover {
            transform: translate(-1px, -1px);
            box-shadow: 5px 5px 0 rgba(16, 18, 23, .92);
        }
        [data-testid="stButton"] > button:active, [data-testid="stDownloadButton"] > button:active {
            transform: translate(2px, 2px);
            box-shadow: 1px 1px 0 rgba(16, 18, 23, .92);
        }
        [data-testid="stButton"] > button[kind="primary"] {
            color: var(--dc-paper);
            background: var(--dc-navy);
            border-color: var(--dc-line);
        }
        [data-testid="stButton"] > button[kind="primary"]:hover { background: var(--dc-blue); }
        .st-key-template_apply button, .st-key-planner_build button, .st-key-today_craft_plan button {
            color: var(--dc-ink) !important;
            background: var(--dc-acid) !important;
        }
        .st-key-template_apply button:hover, .st-key-planner_build button:hover, .st-key-today_craft_plan button:hover {
            background: #F7FF91 !important;
        }
        [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stNumberInput"] input, [data-testid="stDateInput"] input,
        [data-testid="stTimeInput"] input {
            border: 1.5px solid var(--dc-line) !important;
            border-radius: 3px !important;
            background: var(--dc-paper) !important;
        }
        [data-testid="stExpander"] {
            background: var(--dc-paper);
            border: 2px solid var(--dc-line);
            border-radius: 4px;
            box-shadow: 3px 3px 0 rgba(16, 18, 23, .78);
        }
        [data-testid="stRadio"] label, [data-testid="stPills"] button { border-radius: 3px !important; }
        .dc-kicker { color: var(--dc-navy); font-size: .72rem; font-weight: 850; letter-spacing: .12em; text-transform: uppercase; margin-bottom: .38rem; }
        .dc-hero { background: var(--dc-paper); border: 2px solid var(--dc-line); border-radius: 4px; padding: 1.35rem 1.45rem; margin: .25rem 0 1.25rem; box-shadow: 5px 5px 0 var(--dc-line); }
        .dc-hero h1 { margin: 0 0 .35rem; }
        .dc-hero p { margin: 0; font-size: 1rem; max-width: 760px; }
        .dc-card { background: var(--dc-paper); border: 2px solid var(--dc-line); border-radius: 4px; padding: 1rem 1.05rem; margin: .5rem 0; box-shadow: 3px 3px 0 rgba(16, 18, 23, .82); }
        .dc-card-title { color: var(--dc-ink); font-weight: 750; margin-bottom: .25rem; }
        .dc-card-meta { color: var(--dc-muted); font-size: .88rem; }
        .dc-pill { display: inline-block; padding: .16rem .5rem; border: 1px solid var(--dc-line); border-radius: 2px; font-size: .71rem; font-weight: 800; margin-right: .35rem; }
        .dc-pill-high { background: #FFC7BD; color: var(--dc-ink); }
        .dc-pill-medium { background: #FFF19B; color: var(--dc-ink); }
        .dc-pill-low { background: #CFEFDE; color: var(--dc-ink); }
        .dc-pill-connected { background: var(--dc-acid); color: var(--dc-ink); }
        .dc-pill-neutral { background: var(--dc-soft-blue); color: var(--dc-ink); }
        .dc-empty { text-align: center; padding: 2.5rem 1rem; color: var(--dc-muted); background: var(--dc-paper); border: 2px dashed var(--dc-line); border-radius: 4px; }
        .dc-sidebar-brand { font-weight: 800; font-size: 1.35rem; letter-spacing: -.04em; color: var(--dc-paper); }
        .dc-sidebar-subtitle { color: rgba(255,253,247,.76); font-size: .84rem; margin-bottom: 1.6rem; }

        /* Editorial Today header: an original blueprint board, not a copied product surface. */
        .dc-today-hero, .dc-planner-hero {
            position: relative;
            overflow: hidden;
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1.3rem;
            padding: clamp(1.35rem, 4vw, 2.35rem);
            margin: .2rem 0 1.35rem;
            color: var(--dc-paper);
            border: 2px solid var(--dc-line);
            border-radius: 4px;
            background-color: var(--dc-blue);
            background-image: linear-gradient(rgba(255,253,247,.18) 1px, transparent 1px), linear-gradient(90deg, rgba(255,253,247,.18) 1px, transparent 1px);
            background-size: 26px 26px;
            box-shadow: 6px 6px 0 var(--dc-line);
        }
        .dc-today-hero::after, .dc-planner-hero::after {
            content: "";
            position: absolute;
            width: 240px;
            height: 240px;
            top: -135px;
            right: -85px;
            border: 2px solid var(--dc-line);
            border-radius: 50%;
            background: var(--dc-acid);
        }
        .dc-today-hero-copy, .dc-planner-hero-copy { position: relative; z-index: 1; max-width: 850px; }
        .dc-today-hero h1, .dc-planner-hero h1 { color: var(--dc-paper); margin: 0 0 .48rem; font-size: clamp(2.05rem, 4.3vw, 3.65rem); font-weight: 800; letter-spacing: -.065em; line-height: .96; text-transform: uppercase; }
        .dc-today-hero p, .dc-planner-hero p { max-width: 760px; margin: 0; color: rgba(255,253,247,.9) !important; font-size: 1rem; }
        .dc-today-hero .dc-kicker, .dc-planner-hero .dc-kicker { color: var(--dc-acid); }
        .dc-today-status, .dc-blueprint-chip {
            position: relative; z-index: 1; flex: 0 0 auto; display: inline-flex; align-items: center; gap: .42rem;
            padding: .44rem .7rem; color: var(--dc-ink); background: var(--dc-acid); border: 2px solid var(--dc-line);
            border-radius: 3px; font-size: .72rem; font-weight: 850; letter-spacing: .07em; text-transform: uppercase;
        }
        .dc-status-dot { width: .45rem; height: .45rem; border: 1px solid var(--dc-ink); border-radius: 999px; background: #2A9B6D; }
        .dc-dashboard-actions { margin: .7rem 0 1.5rem; }
        .dc-dashboard-note { align-self: center; color: var(--dc-muted); font-size: .9rem; }

        .dc-flow-heading { margin: 2.1rem 0 .8rem; }
        .dc-flow-heading h2, .dc-canvas-heading h2 { margin: .12rem 0 .28rem; color: var(--dc-ink); font-size: clamp(1.42rem, 2.6vw, 2rem); }
        .dc-flow-heading p, .dc-canvas-heading p { margin: 0; color: var(--dc-muted) !important; }
        .dc-rhythm-shell { margin: 1.3rem 0 1.15rem; padding: 1rem 1.1rem; background: var(--dc-paper); border: 2px solid var(--dc-line); box-shadow: 4px 4px 0 var(--dc-line); }
        .st-key-planner_rhythm > div { border: 2px solid var(--dc-line) !important; border-radius: 4px !important; background: var(--dc-paper) !important; box-shadow: 4px 4px 0 var(--dc-line); }
        .dc-rhythm-title { margin: 0; color: var(--dc-ink); font-size: 1.25rem; font-weight: 800; letter-spacing: -.04em; }
        .dc-rhythm-copy { margin: .25rem 0 0; color: var(--dc-muted) !important; }
        .dc-template-note { margin: .65rem 0 0; padding: .55rem .65rem; color: var(--dc-ink); background: var(--dc-soft-lime); border-left: 3px solid var(--dc-ink); font-size: .86rem; }
        .dc-rhythm-map { display: flex; min-height: 4.25rem; margin-top: .8rem; overflow: hidden; border: 2px solid var(--dc-line); background: #F0EEE5; }
        .dc-rhythm-segment { display: flex; flex: 1 1 0; flex-direction: column; justify-content: center; min-width: 0; padding: .35rem .45rem; border-right: 1px solid var(--dc-line); color: var(--dc-ink); }
        .dc-rhythm-segment:last-child { border-right: 0; }
        .dc-rhythm-segment[data-tone="work"] { background: #C9DAFF; }
        .dc-rhythm-segment[data-tone="break"] { background: var(--dc-acid); }
        .dc-rhythm-segment[data-tone="anchor"] { background: var(--dc-paper); }
        .dc-rhythm-segment strong { overflow: hidden; font-size: .69rem; font-weight: 850; line-height: 1.05; text-overflow: ellipsis; white-space: nowrap; }
        .dc-rhythm-segment span { overflow: hidden; margin-top: .15rem; color: rgba(16,18,23,.68); font-family: "JetBrains Mono", monospace; font-size: .58rem; text-overflow: ellipsis; white-space: nowrap; }
        .dc-planner-toolbar { margin: 1.2rem 0 .9rem; }
        .dc-canvas-heading { display: flex; align-items: end; justify-content: space-between; gap: 1rem; margin: 2.2rem 0 .85rem; }
        .dc-canvas-label { margin-bottom: .5rem; color: var(--dc-navy); font-size: .7rem; font-weight: 850; letter-spacing: .1em; }
        .st-key-plan_canvas_summary > div { border: 2px solid var(--dc-line) !important; border-radius: 4px !important; background: var(--dc-paper) !important; box-shadow: 4px 4px 0 var(--dc-line); }

        /* Static schedule grid gives time its physical place in the plan. */
        .dc-schedule-sheet { background: var(--dc-paper); border: 2px solid var(--dc-line); box-shadow: 5px 5px 0 var(--dc-line); }
        .dc-schedule-sheet-header { display: flex; align-items: center; justify-content: space-between; gap: .8rem; padding: .72rem .85rem; color: var(--dc-paper); background: var(--dc-ink); border-bottom: 2px solid var(--dc-line); }
        .dc-schedule-sheet-title { font-size: .81rem; font-weight: 850; letter-spacing: .09em; text-transform: uppercase; }
        .dc-schedule-sheet-meta { color: rgba(255,253,247,.74); font-size: .75rem; }
        .dc-schedule-body { display: grid; grid-template-columns: 4.55rem minmax(0, 1fr); }
        .dc-time-rail { position: relative; min-height: var(--dc-grid-height); border-right: 2px solid var(--dc-line); background: #F0EEE5; }
        .dc-time-label { position: absolute; right: .5rem; transform: translateY(-.58rem); color: var(--dc-muted); font-family: "JetBrains Mono", monospace; font-size: .69rem; font-weight: 650; }
        .dc-time-label:last-child { transform: translateY(-1.05rem); }
        .dc-time-grid { position: relative; min-height: var(--dc-grid-height); overflow: hidden; background-color: var(--dc-paper); background-image: repeating-linear-gradient(to bottom, transparent 0, transparent calc(var(--dc-hour-height) - 1px), rgba(16,18,23,.58) calc(var(--dc-hour-height) - 1px), rgba(16,18,23,.58) var(--dc-hour-height)), repeating-linear-gradient(to bottom, transparent 0, transparent calc(var(--dc-half-hour-height) - 1px), rgba(16,18,23,.13) calc(var(--dc-half-hour-height) - 1px), rgba(16,18,23,.13) var(--dc-half-hour-height)); }
        .dc-time-now-line { position: absolute; z-index: 3; left: 0; right: 0; height: 2px; background: var(--dc-coral); }
        .dc-calendar-event { position: absolute; z-index: 2; display: flex; flex-direction: column; gap: .08rem; min-width: 0; overflow: hidden; padding: .42rem .55rem; border: 2px solid var(--dc-line); border-radius: 2px; box-shadow: 2px 2px 0 rgba(16,18,23,.78); color: var(--dc-ink); }
        .dc-calendar-event[data-tone="planner"] { background: var(--dc-blue); color: var(--dc-paper); }
        .dc-calendar-event[data-tone="planner"] .dc-event-meta { color: rgba(255,253,247,.82); }
        .dc-calendar-event[data-tone="template"] { z-index: 1; background: rgba(239,255,62,.42); border-style: dashed; box-shadow: none; }
        .dc-calendar-event[data-tone="break"] { background: var(--dc-acid); }
        .dc-calendar-event[data-tone="google"] { background: repeating-linear-gradient(-45deg, #E3E7F0, #E3E7F0 7px, #F8F9FC 7px, #F8F9FC 14px); }
        .dc-calendar-event[data-tone="meeting"] { background: #C9DAFF; }
        .dc-calendar-event[data-tone="personal"] { background: #FFD0C6; }
        .dc-calendar-event[data-tone="admin"] { background: #EAE4FF; }
        .dc-calendar-event[data-tone="health"] { background: #CDEEDB; }
        .dc-event-title { overflow: hidden; font-size: .79rem; font-weight: 800; line-height: 1.08; text-overflow: ellipsis; white-space: nowrap; }
        .dc-event-meta { overflow: hidden; color: rgba(16,18,23,.72); font-family: "JetBrains Mono", monospace; font-size: .63rem; text-overflow: ellipsis; white-space: nowrap; }
        .dc-schedule-empty { display: flex; min-height: 430px; align-items: center; justify-content: center; padding: 1.2rem; text-align: center; color: var(--dc-muted); background: var(--dc-paper); border: 2px dashed var(--dc-line); }
        .dc-schedule-empty strong { display: block; color: var(--dc-ink); margin-bottom: .3rem; }
        .dc-schedule-legend { display: flex; flex-wrap: wrap; gap: .45rem .8rem; padding: .6rem .85rem; border-top: 2px solid var(--dc-line); color: var(--dc-muted); font-size: .72rem; }
        .dc-legend-dot { display: inline-block; width: .65rem; height: .65rem; margin-right: .25rem; border: 1px solid var(--dc-line); vertical-align: -.06rem; }
        .dc-legend-task { background: var(--dc-blue); }.dc-legend-break { background: var(--dc-acid); }.dc-legend-commitment { background: #C9DAFF; }.dc-legend-google { background: #E3E7F0; }
        .dc-unscheduled { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .7rem; }
        .dc-unscheduled-chip { padding: .28rem .48rem; background: #FFD0C6; border: 1px solid var(--dc-line); color: var(--dc-ink); font-size: .76rem; font-weight: 700; }

        @media (max-width: 760px) {
            .block-container { padding-top: 1.1rem; }
            .dc-today-hero, .dc-planner-hero { display: block; }
            .dc-today-status, .dc-blueprint-chip { margin-top: 1rem; }
            .dc-canvas-heading { display: block; }
            .dc-canvas-heading p { margin-top: .35rem; }
            .dc-schedule-body { grid-template-columns: 3.7rem minmax(0, 1fr); }
            .dc-time-label { font-size: .62rem; right: .25rem; }
            .dc-calendar-event { padding: .34rem .38rem; }
            .dc-rhythm-segment { padding: .28rem .25rem; }
            .dc-rhythm-segment strong { font-size: .6rem; }
            .dc-rhythm-segment span { display: none; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_intro(eyebrow: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="dc-hero">
          <div class="dc-kicker">{escape(eyebrow)}</div>
          <h1>{escape(title)}</h1>
          <p>{escape(description)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, meta: str = "", *, pill: str | None = None, pill_class: str = "neutral") -> None:
    pill_html = (
        f'<span class="dc-pill dc-pill-{escape(pill_class)}">{escape(pill)}</span>' if pill else ""
    )
    st.markdown(
        f"""
        <div class="dc-card">
          <div class="dc-card-title">{escape(title)}</div>
          <div class="dc-card-meta">{pill_html}{escape(meta)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(title: str, detail: str) -> None:
    st.markdown(
        f'<div class="dc-empty"><strong>{escape(title)}</strong><br>{escape(detail)}</div>',
        unsafe_allow_html=True,
    )


def focus_styles() -> None:
    """Apply the warm, single-purpose treatment used only by Focus mode."""
    st.markdown(
        """
        <style>
        .st-key-focus_console_card { max-width: 760px; margin: .8rem auto 0; border: 0 !important; background: transparent !important; }
        .st-key-focus_console_card > div { border: 0 !important; background: transparent !important; padding: 0 !important; }
        .dc-focus-timer {
            position: relative; overflow: hidden; text-align: center; color: #FFFDF7; border: 2px solid #101217; border-radius: 4px;
            padding: clamp(1.45rem, 4vw, 2.4rem) clamp(1.1rem, 5vw, 3.2rem) 1.7rem;
            background-color: #173B84; background-image: linear-gradient(rgba(255,253,247,.12) 1px, transparent 1px), linear-gradient(90deg, rgba(255,253,247,.12) 1px, transparent 1px);
            background-size: 24px 24px; box-shadow: 6px 6px 0 #101217;
        }
        .dc-focus-timer::after { content: ""; position: absolute; width: 220px; height: 220px; right: -110px; bottom: -130px; border: 2px solid #101217; border-radius: 50%; background: #EFFF3E; }
        .dc-focus-timer-topline { position: relative; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: .8rem; color: rgba(255,253,247,.82); font-size: .78rem; font-weight: 650; letter-spacing: .04em; text-transform: uppercase; }
        .dc-focus-status { color: #FFFDF7; }
        .dc-focus-clock { position: relative; z-index: 1; margin: .4rem 0 .12rem; color: #FFFDF7; font-size: clamp(4.6rem, 13vw, 7.4rem); line-height: 1; font-weight: 760; letter-spacing: -.075em; font-variant-numeric: tabular-nums; }
        .dc-focus-note { position: relative; z-index: 1; margin: 0; color: rgba(255,253,247,.87) !important; font-size: .96rem; }
        .dc-focus-task { position: relative; z-index: 1; display: inline-flex; flex-direction: column; max-width: min(100%, 480px); margin-top: 1.25rem; padding: .64rem 1rem; border: 2px solid rgba(255,253,247,.45); border-radius: 3px; background: rgba(16,18,23,.2); text-align: left; }
        .dc-focus-task span { color: rgba(255,253,247,.7); font-size: .7rem; font-weight: 650; letter-spacing: .05em; text-transform: uppercase; }
        .dc-focus-task strong { overflow: hidden; color: #FFFDF7; font-size: .95rem; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
        .st-key-focus_start button, .st-key-focus_resume button { color: #101217 !important; border-color: #101217 !important; background: #EFFF3E !important; }
        .st-key-focus_reflection_card { max-width: 760px; margin: 1rem auto 0; }
        .st-key-focus_reflection_card > div { border: 2px solid #101217 !important; border-radius: 4px !important; box-shadow: 4px 4px 0 #101217; }
        @media (max-width: 640px) { .dc-focus-timer-topline { font-size: .68rem; } .dc-focus-clock { font-size: 4.35rem; } .dc-focus-task { width: 100%; } }
        </style>
        """,
        unsafe_allow_html=True,
    )
