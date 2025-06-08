import streamlit as st

def init_session_state():
    if 'all_tasks' not in st.session_state:
        st.session_state.all_tasks = []
    if 'energy_levels' not in st.session_state:
        st.session_state.energy_levels = []
    if 'schedule_times' not in st.session_state:
        st.session_state.schedule_times = {}
    if 'productivity_ratings' not in st.session_state:
        st.session_state.productivity_ratings = []
    if 'user_schedules' not in st.session_state:
        st.session_state.user_schedules = []
    if 'current_schedule' not in st.session_state:
        st.session_state.current_schedule = None
    if 'page' not in st.session_state:
        st.session_state.page = "📅 Schedule Generator"
