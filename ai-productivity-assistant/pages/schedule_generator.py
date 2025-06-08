import streamlit as st
from agent import generate_schedule
from scheduler import display_schedule, create_schedule_summary
from components.mcp import ProductivityMCP
import pandas as pd
from datetime import datetime, timedelta
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

mcp = ProductivityMCP()

def generate_schedule_pdf(schedule_text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    lines = schedule_text.split('\n')
    y = height - 50  # Start from top

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Your Personalized Schedule")
    y -= 30

    c.setFont("Helvetica", 12)
    for line in lines:
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 12)
        c.drawString(50, y, line)
        y -= 20

    c.save()
    buffer.seek(0)
    return buffer

def parse_time_input(time_str):
    """Parse time input in various formats"""
    if not time_str:
        return None
    
    time_str = time_str.strip().upper()
    
    try:
        # Try parsing 12-hour format (e.g., "09:00 AM", "2:30 PM")
        if 'AM' in time_str or 'PM' in time_str:
            return datetime.strptime(time_str, "%I:%M %p").time()
        # Try parsing 24-hour format (e.g., "14:30", "09:00")
        elif ':' in time_str:
            return datetime.strptime(time_str, "%H:%M").time()
        # Try parsing hour only (e.g., "14", "9")
        else:
            hour = int(time_str)
            if 0 <= hour <= 23:
                return datetime.strptime(f"{hour}:00", "%H:%M").time()
    except ValueError:
        pass
    
    return None

def format_time_display(time_obj):
    """Format time object for display"""
    return time_obj.strftime("%I:%M %p")

def format_time_slot(start_time, end_time, title, location=""):
    """Format a time slot for inclusion in the prompt"""
    location_str = f" at {location}" if location else ""
    return f"- {start_time} to {end_time}: {title}{location_str}"

def schedule_generator_page():
    st.header("📅 Daily Schedule Generator")

    # Initialize session state for meetings/classes
    if 'fixed_events' not in st.session_state:
        st.session_state.fixed_events = []

    col1, col2 = st.columns([2, 1])

    with col1:
        # Meeting/Class Input Section
        st.subheader("📝 Add Fixed Meetings & Classes")
        
        with st.expander("➕ Add Meeting/Class", expanded=False):
            event_col1, event_col2 = st.columns(2)
            
            with event_col1:
                event_title = st.text_input("Meeting/Class Title:", placeholder="Team Meeting, Math Class, etc.")
                event_start = st.text_input("Start Time:", placeholder="09:00 AM or 14:30", help="Enter time in format: HH:MM AM/PM or HH:MM (24-hour)")
                event_location = st.text_input("Location (optional):", placeholder="Conference Room A, Online, etc.")
            
            with event_col2:
                event_type = st.text_input("Type:", placeholder="Meeting, Class, Appointment, etc.")
                event_end = st.text_input("End Time:", placeholder="10:00 AM or 15:30", help="Enter time in format: HH:MM AM/PM or HH:MM (24-hour)")
                
            col_add, col_clear = st.columns([1, 1])
            with col_add:
                if st.button("➕ Add Event"):
                    if event_title and event_start and event_end and event_type:
                        start_time = parse_time_input(event_start)
                        end_time = parse_time_input(event_end)
                        
                        if start_time is None:
                            st.error("Invalid start time format! Use formats like '09:00 AM', '14:30', or '9'")
                        elif end_time is None:
                            st.error("Invalid end time format! Use formats like '10:00 AM', '15:30', or '10'")
                        elif start_time >= end_time:
                            st.error("End time must be after start time!")
                        else:
                            new_event = {
                                'title': event_title,
                                'type': event_type,
                                'start': format_time_display(start_time),
                                'end': format_time_display(end_time),
                                'location': event_location
                            }
                            st.session_state.fixed_events.append(new_event)
                            st.success(f"✅ Added: {event_title}")
                            st.rerun()
                    else:
                        st.error("Please fill in title, type, start time, and end time!")
            
            with col_clear:
                if st.button("🗑️ Clear All Events"):
                    st.session_state.fixed_events = []
                    st.success("All events cleared!")
                    st.rerun()

        # Display current fixed events
        if st.session_state.fixed_events:
            st.subheader("📋 Your Fixed Events:")
            for i, event in enumerate(st.session_state.fixed_events):
                event_container = st.container()
                with event_container:
                    col_event, col_remove = st.columns([4, 1])
                    with col_event:
                        location_text = f" • {event['location']}" if event['location'] else ""
                        st.write(f"**{event['title']}** ({event['type']}) - {event['start']} to {event['end']}{location_text}")
                    with col_remove:
                        if st.button("❌", key=f"remove_{i}", help="Remove this event"):
                            st.session_state.fixed_events.pop(i)
                            st.rerun()

        st.subheader("Tell me about your day:")
        prompt = st.text_area(
            "Describe your tasks, deadlines, and preferences:",
            placeholder="I need to finish a report by 3 PM, want to review presentation materials, need time for lunch...",
            height=150
        )

        col1a, col1b = st.columns(2)
        with col1a:
            work_style = st.selectbox("Work Style Preference:", ["Balanced", "Deep Work Focus", "Meeting Heavy", "Creative Work"])
        with col1b:
            energy_level = st.selectbox("When are you most energetic?", ["Morning Person", "Afternoon Peak", "Evening Owl", "Consistent Throughout"])

        # Construct enhanced prompt with fixed events
        fixed_events_text = ""
        if st.session_state.fixed_events:
            fixed_events_text = "\n\nFIXED APPOINTMENTS (must be included in schedule):\n"
            for event in st.session_state.fixed_events:
                fixed_events_text += format_time_slot(
                    event['start'], 
                    event['end'], 
                    f"{event['title']} ({event['type']})", 
                    event['location']
                ) + "\n"
            fixed_events_text += "\nPlease schedule other tasks around these fixed appointments.\n"

        enhanced_prompt = f"{prompt}{fixed_events_text}\nWork Style: {work_style}\nEnergy Pattern: {energy_level}"

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
        schedule = st.session_state.current_schedule

        st.subheader("📅 Your Generated Schedule:")
        with st.expander("View Current Schedule", expanded=True):
            st.write(st.session_state.current_schedule)
        
        # Download buttons
        col_download1, col_download2 = st.columns(2)
        with col_download1:
            st.download_button(
                label="📥 Download as TXT",
                data=st.session_state.current_schedule,
                file_name=f"schedule_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )
        
        with col_download2:
            pdf_file = generate_schedule_pdf(schedule)
            st.download_button(
                label="📄 Download as PDF",
                data=pdf_file,
                file_name=f"schedule_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf"
            )
        
        # Schedule visualization
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
        - **Add fixed events first** using the form above
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