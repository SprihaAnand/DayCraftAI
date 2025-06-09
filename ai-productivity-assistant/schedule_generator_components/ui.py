import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from schedule_generator_components.helpers import parse_time_input, format_time_display
from schedule_generator_components.pdf_generator import generate_schedule_pdf

def render_event_input_form(add_event_callback, clear_callback):
    st.subheader("📝 Add Fixed Meetings & Classes")
    with st.expander("➕ Add Meeting/Class", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Meeting/Class Title:", placeholder="Team Meeting")
            start = st.text_input("Start Time:", placeholder="09:00 AM or 14:30")
            location = st.text_input("Location (optional):", placeholder="Online")

        with col2:
            type_ = st.text_input("Type:", placeholder="Meeting")
            end = st.text_input("End Time:", placeholder="10:00 AM or 15:30")

        col_add, col_clear = st.columns(2)

        with col_add:
            if st.button("➕ Add Event"):
                if title and start and end and type_:
                    start_time = parse_time_input(start)
                    end_time = parse_time_input(end)

                    if not start_time:
                        st.error("Invalid start time format!")
                    elif not end_time:
                        st.error("Invalid end time format!")
                    elif start_time >= end_time:
                        st.error("End time must be after start time!")
                    else:
                        event = {
                            'title': title,
                            'type': type_,
                            'start': format_time_display(start_time),
                            'end': format_time_display(end_time),
                            'location': location
                        }
                        add_event_callback(event)
                else:
                    st.error("Please fill in all required fields (title, type, start and end time)!")

        with col_clear:
            if st.button("🗑️ Clear All Events"):
                clear_callback()


def render_fixed_events_list():
    if st.session_state.fixed_events:
        st.subheader("📋 Your Fixed Events:")
        for i, event in enumerate(st.session_state.fixed_events):
            col, col_rm = st.columns([4, 1])
            with col:
                location_text = f" • {event['location']}" if event['location'] else ""
                st.write(f"**{event['title']}** ({event['type']}) - {event['start']} to {event['end']}{location_text}")
            with col_rm:
                if st.button("❌", key=f"remove_{i}", help="Remove this event"):
                    st.session_state.fixed_events.pop(i)
                    st.rerun()


def render_schedule_output(mcp, schedule):
    st.subheader("📅 Your Generated Schedule:")
    with st.expander("View Current Schedule", expanded=True):
        st.write(schedule)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📥 Download as TXT",
            data=schedule,
            file_name=f"schedule_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain"
        )

    with col2:
        pdf_file = generate_schedule_pdf(schedule)
        st.download_button(
            "📄 Download as PDF",
            data=pdf_file,
            file_name=f"schedule_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf"
        )

    # Visualizations
    schedule_blocks = mcp.parse_schedule_data(schedule)
    if schedule_blocks:
        timeline_data = []
        base_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

        for i, block in enumerate(schedule_blocks[:6]):
            start_time = base_time + timedelta(hours=i * 1.5)
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


def render_tips_sidebar():
    st.subheader("💡 Tips for better schedules:")
    st.markdown("""
    - **Add fixed events first**
    - **Be specific** about task deadlines  
    - **Mention energy levels** and preferences
    - **Include buffer time** between activities
    - **Add breaks and meals** to your tasks
    - **Specify priorities** (high/medium/low)
    - **Share constraints** (commute, family time)
    - **Include preferred work styles**
    """)

    if st.session_state.fixed_events:
        st.info(f"📌 You have {len(st.session_state.fixed_events)} fixed events that will be included in your schedule!")
