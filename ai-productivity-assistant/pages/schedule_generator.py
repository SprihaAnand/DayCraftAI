import streamlit as st
from agent import generate_schedule
from scheduler import display_schedule, create_schedule_summary
from components.mcp import ProductivityMCP
import pandas as pd
from datetime import datetime, timedelta

mcp = ProductivityMCP()

def schedule_generator_page():
    st.header("📅 Daily Schedule Generator")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Tell me about your day:")
        prompt = st.text_area(
            "Describe your tasks, meetings, deadlines, and preferences:",
            placeholder="I have a team meeting at 10 AM, need to finish a report by 3 PM...",
            height=150
        )

        col1a, col1b = st.columns(2)
        with col1a:
            work_style = st.selectbox("Work Style Preference:", ["Balanced", "Deep Work Focus", "Meeting Heavy", "Creative Work"])
        with col1b:
            energy_level = st.selectbox("When are you most energetic?", ["Morning Person", "Afternoon Peak", "Evening Owl", "Consistent Throughout"])

        enhanced_prompt = f"{prompt}\n\nWork Style: {work_style}\nEnergy Pattern: {energy_level}"

        if st.button("🚀 Generate Schedule", type="primary"):
            if prompt:
                with st.spinner("🤖 Creating your personalized schedule..."):
                    schedule = generate_schedule(enhanced_prompt)

                if schedule and not schedule.startswith("Error"):
                    st.success("✅ Schedule generated successfully!")
                    st.session_state.current_schedule = schedule
                    st.session_state.user_schedules.append({
                        'timestamp': datetime.now(),
                        'schedule': schedule,
                        'work_style': work_style,
                        'energy_level': energy_level
                    })

                    display_schedule(schedule)
                    st.subheader("📊 Schedule Visualization")
                    schedule_blocks = mcp.parse_schedule_data(schedule)

                    if schedule_blocks:
                        timeline_data = []
                        current_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
                        for i, block in enumerate(schedule_blocks[:6]):
                            start_time = current_time + timedelta(hours=i * 1.5)
                            end_time = start_time + timedelta(hours=1)
                            timeline_data.append({
                                'task': block['task'][:30] + '...' if len(block['task']) > 30 else block['task'],
                                'category': block['category'],
                                'start_time': start_time,
                                'end_time': end_time
                            })

                        df = pd.DataFrame(timeline_data)
                        st.plotly_chart(mcp.create_schedule_timeline(df.to_dict('records')), use_container_width=True)

                        category_counts = df['category'].value_counts()
                        fig_pie = mcp.create_task_category_pie(category_counts)
                        st.plotly_chart(fig_pie, use_container_width=True)

                    create_schedule_summary(schedule)

    with col2:
        st.subheader("💡 Tips for better schedules:")
        st.markdown("""
        - **Be specific** about meeting times
        - **Mention energy levels**
        - **Include buffer time**
        - **Add breaks and meals**
        - **Specify deadlines** and priorities
        - **Share constraints** (commute, family time)
        - **Include preferred work styles**
        """)