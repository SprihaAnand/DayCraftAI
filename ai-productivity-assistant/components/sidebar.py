import streamlit as st

def render_sidebar():
    st.sidebar.title("🧭 Navigation")
    return st.sidebar.selectbox(
        "Choose a feature:",
        [
            "📅 Schedule Generator",
            "📋 Task Prioritizer",
            "📊 Productivity Analyzer",
            "🔧 Schedule Improver",
            "🎯 Focus Session",
            "📆 Weekly Planner",
            "📈 Visualization Dashboard"
        ]
    )
