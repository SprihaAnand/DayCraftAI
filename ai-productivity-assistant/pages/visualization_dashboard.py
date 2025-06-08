import streamlit as st
from components.mcp import ProductivityMCP
import plotly.express as px
import pandas as pd

mcp = ProductivityMCP()

def visualization_dashboard_page():
    st.header("📈 Your Personal Productivity Dashboard")

    has_data = (
        len(st.session_state.all_tasks) > 0 or
        len(st.session_state.energy_levels) > 0 or
        len(st.session_state.schedule_times) > 0 or
        len(st.session_state.productivity_ratings) > 0 or
        len(st.session_state.user_schedules) > 0
    )

    if not has_data:
        st.info("📊 **No data to visualize yet!**")
        return

    st.success("✅ Displaying your personal productivity data!")
    dashboard_fig = mcp.create_real_productivity_dashboard()
    if dashboard_fig:
        st.plotly_chart(dashboard_fig, use_container_width=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tasks Entered", len(st.session_state.all_tasks))
    with col2:
        avg_energy = sum(st.session_state.energy_levels) / len(st.session_state.energy_levels) if st.session_state.energy_levels else 0
        st.metric("Avg Energy Level", f"{avg_energy:.1f}/10")
    with col3:
        avg_satisfaction = sum(st.session_state.productivity_ratings) / len(st.session_state.productivity_ratings) if st.session_state.productivity_ratings else 0
        st.metric("Avg Satisfaction", f"{avg_satisfaction:.1f}/10")
    with col4:
        st.metric("Schedules Created", len(st.session_state.user_schedules))

    if st.session_state.all_tasks:
        st.subheader("📋 Your Task Categories")
        task_categories = {}
        for task in st.session_state.all_tasks:
            category = mcp._categorize_task(task)
            task_categories[category] = task_categories.get(category, 0) + 1

        task_df = pd.DataFrame(list(task_categories.items()), columns=['Category', 'Count'])
        fig_tasks = px.pie(task_df, values='Count', names='Category', title="Your Task Distribution")
        st.plotly_chart(fig_tasks, use_container_width=True)

    if st.session_state.energy_levels:
        st.subheader("⚡ Your Energy Patterns")
        energy_df = pd.DataFrame({
            'Session': range(1, len(st.session_state.energy_levels) + 1),
            'Energy Level': st.session_state.energy_levels
        })
        fig_energy = px.line(energy_df, x='Session', y='Energy Level', title="Your Energy Levels Over Time", markers=True)
        fig_energy.update_layout(yaxis_range=[0, 10])
        st.plotly_chart(fig_energy, use_container_width=True)

    if st.session_state.schedule_times:
        st.subheader("⏰ Your Time Allocation")
        time_df = pd.DataFrame(list(st.session_state.schedule_times.items()), columns=['Activity', 'Hours'])
        fig_time = px.bar(time_df, x='Activity', y='Hours', title="Hours Spent on Different Activities")
        st.plotly_chart(fig_time, use_container_width=True)

    if st.session_state.productivity_ratings:
        st.subheader("📈 Your Satisfaction Trends")
        satisfaction_df = pd.DataFrame({
            'Session': range(1, len(st.session_state.productivity_ratings) + 1),
            'Satisfaction': st.session_state.productivity_ratings
        })
        fig_satisfaction = px.line(satisfaction_df, x='Session', y='Satisfaction', title="Your Satisfaction Levels Over Time", markers=True)
        fig_satisfaction.update_layout(yaxis_range=[0, 10])
        st.plotly_chart(fig_satisfaction, use_container_width=True)

    st.subheader("📅 Your Recent Schedules")
    for i, schedule_data in enumerate(reversed(st.session_state.user_schedules[-3:])):
        st.markdown(f"### Schedule {len(st.session_state.user_schedules) - i}")
        st.write(f"🕒 {schedule_data['timestamp'].strftime('%Y-%m-%d %H:%M')}")
        st.write(f"Work Style: {schedule_data['work_style']}, Energy: {schedule_data['energy_level']}")
        st.write(schedule_data['schedule'])
