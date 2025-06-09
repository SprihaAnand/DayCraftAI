from schedule_generator_components.helpers import parse_time_input, format_time_display, format_time_slot
from schedule_generator_components.pdf_generator import generate_schedule_pdf
from schedule_generator_components.logic import build_enhanced_prompt, add_event_to_session, clear_all_events
from schedule_generator_components.ui import render_event_input_form, render_fixed_events_list, render_schedule_output, render_tips_sidebar

import streamlit as st
from agent import generate_schedule
from scheduler import create_schedule_summary
from components.mcp import ProductivityMCP
from datetime import datetime

mcp = ProductivityMCP()

def schedule_generator_page():
    st.header("📅 Daily Schedule Generator")

    if 'fixed_events' not in st.session_state:
        st.session_state.fixed_events = []

    col1, col2 = st.columns([2, 1])

    with col1:
        render_event_input_form(add_event_to_session, clear_all_events)
        render_fixed_events_list()

        st.subheader("Tell me about your day:")
        prompt = st.text_area("Describe your tasks, deadlines, and preferences:",
                              placeholder="I need to finish a report by 3 PM, want to review presentation materials, need time for lunch...",
                              height=150)

        col1a, col1b = st.columns(2)
        with col1a:
            work_style = st.selectbox("Work Style Preference:", ["Balanced", "Deep Work Focus", "Meeting Heavy", "Creative Work"])
        with col1b:
            energy_level = st.selectbox("When are you most energetic?", ["Morning Person", "Afternoon Peak", "Evening Owl", "Consistent Throughout"])

        enhanced_prompt = build_enhanced_prompt(prompt, work_style, energy_level)

        if st.button("🚀 Generate Schedule", type="primary"):
            if prompt or st.session_state.fixed_events:
                with st.spinner("🤖 Creating your personalized schedule..."):
                    schedule = generate_schedule(enhanced_prompt)

                if schedule and not schedule.startswith("Error"):
                    st.success("✅ Schedule generated successfully!")
                    st.session_state.current_schedule = schedule
                    st.session_state.user_schedules.append({
                        'timestamp': datetime.now(),
                        'schedule': schedule,
                        'work_style': work_style,
                        'energy_level': energy_level,
                        'fixed_events': st.session_state.fixed_events.copy()
                    })
            else:
                st.error("Please add some tasks or fixed events to generate a schedule!")

    if "current_schedule" in st.session_state and st.session_state.current_schedule:
        render_schedule_output(mcp, st.session_state.current_schedule)
        create_schedule_summary(st.session_state.current_schedule)

    with col2:
        render_tips_sidebar()
