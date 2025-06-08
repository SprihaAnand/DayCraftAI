# app.py

import streamlit as st
from dotenv import load_dotenv

# Components
from components.sidebar import render_sidebar
from components.header import render_header

# Utils
from utils.session_state import init_session_state

# Pages
from pages import (
    schedule_generator,
    task_prioritizer,
    productivity_analyzer,
    schedule_improver,
    focus_session,
    weekly_planner,
    visualization_dashboard
)

# Setup environment and session state
load_dotenv()
init_session_state()
render_header()
page = render_sidebar()

hide_streamlit_style = """
<style>
[data-testid="stSidebarNav"] {
    display: none;
}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Routing logic
if page == "📅 Schedule Generator":
    schedule_generator.schedule_generator_page()
elif page == "📋 Task Prioritizer":
    task_prioritizer.task_prioritizer_page()
elif page == "📊 Productivity Analyzer":
    productivity_analyzer.productivity_analyzer_page()
elif page == "🔧 Schedule Improver":
    schedule_improver.schedule_improver_page()
elif page == "🎯 Focus Session":
    focus_session.focus_session_page()
elif page == "📆 Weekly Planner":
    weekly_planner.weekly_planner_page()
elif page == "📈 Visualization Dashboard":
    visualization_dashboard.visualization_dashboard_page()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>Made with ❤️ using Streamlit, Google Gemini AI, and MCP for Advanced Visualizations</p>
    <p><small>Enhanced with Interactive Charts • Real-time Analytics • Smart Visualizations</small></p>
</div>
""", unsafe_allow_html=True)
