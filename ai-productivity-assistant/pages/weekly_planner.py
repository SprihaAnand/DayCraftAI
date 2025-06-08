import streamlit as st
from agent import create_weekly_plan
from datetime import datetime, timedelta

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

def format_weekly_events(events):
    """Format weekly events for inclusion in the AI prompt"""
    if not events:
        return ""
    
    events_text = "\n\nFIXED WEEKLY SCHEDULE (must be included in weekly plan):\n"
    
    # Group events by day
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    events_by_day = {day: [] for day in days_order}
    
    for event in events:
        for day in event['days']:
            events_by_day[day].append(event)
    
    for day in days_order:
        if events_by_day[day]:
            events_text += f"\n{day}:\n"
            for event in events_by_day[day]:
                location_str = f" at {event['location']}" if event['location'] else ""
                events_text += f"  - {event['start']} to {event['end']}: {event['title']} ({event['type']}){location_str}\n"
    
    events_text += "\nPlease create a weekly plan that works around these fixed commitments.\n"
    return events_text

def weekly_planner_page():
    st.header("📆 Weekly Productivity Planner")

    # Initialize session state for weekly events
    if 'weekly_events' not in st.session_state:
        st.session_state.weekly_events = []

    col1, col2 = st.columns([2, 1])

    with col1:
        # Weekly Events Input Section
        st.subheader("📝 Add Recurring Weekly Events")
        
        with st.expander("➕ Add Weekly Meeting/Class", expanded=False):
            # Basic event info
            event_title = st.text_input("Event Title:", placeholder="Team Standup, Calculus Class, etc.", key="weekly_title")
            
            event_col1, event_col2 = st.columns(2)
            with event_col1:
                event_start = st.text_input("Start Time:", placeholder="09:00 AM or 14:30", 
                                          help="Enter time in format: HH:MM AM/PM or HH:MM (24-hour)", key="weekly_start")
                event_type = st.text_input("Type:", placeholder="Meeting, Class, Appointment, etc.", key="weekly_type")
            
            with event_col2:
                event_end = st.text_input("End Time:", placeholder="10:00 AM or 15:30", 
                                        help="Enter time in format: HH:MM AM/PM or HH:MM (24-hour)", key="weekly_end")
                event_location = st.text_input("Location (optional):", placeholder="Conference Room, Building A, Online", key="weekly_location")
            
            # Day selection (outside of columns)
            st.write("**Select Days:**")
            selected_days = []
            
            # Use multiselect instead of nested columns with checkboxes
            selected_days = st.multiselect(
                "Choose days for this event:",
                options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                default=[],
                key="days_multiselect",
                help="Select one or more days when this event occurs"
            )
            
            col_add, col_clear = st.columns([1, 1])
            with col_add:
                if st.button("➕ Add Weekly Event"):
                    if event_title and event_start and event_end and event_type and selected_days:
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
                                'location': event_location,
                                'days': selected_days.copy()
                            }
                            st.session_state.weekly_events.append(new_event)
                            st.success(f"✅ Added: {event_title} on {', '.join(selected_days)}")
                            
                            # Clear form
                            for key in ['weekly_title', 'weekly_start', 'weekly_end', 'weekly_type', 'weekly_location', 'days_multiselect']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.rerun()
                    else:
                        missing = []
                        if not event_title: missing.append("title")
                        if not event_type: missing.append("type")
                        if not event_start: missing.append("start time")
                        if not event_end: missing.append("end time")
                        if not selected_days: missing.append("at least one day")
                        st.error(f"Please fill in: {', '.join(missing)}")
            
            with col_clear:
                if st.button("🗑️ Clear All Events"):
                    st.session_state.weekly_events = []
                    st.success("All weekly events cleared!")
                    st.rerun()

        # Display current weekly events
        if st.session_state.weekly_events:
            st.subheader("📋 Your Weekly Schedule:")
            
            # Group and display by day
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            events_by_day = {day: [] for day in days_order}
            
            for i, event in enumerate(st.session_state.weekly_events):
                for day in event['days']:
                    events_by_day[day].append((i, event))
            
            for day in days_order:
                if events_by_day[day]:
                    st.write(f"**{day}:**")
                    for event_idx, event in events_by_day[day]:
                        col_event, col_remove = st.columns([5, 1])
                        with col_event:
                            location_text = f" • {event['location']}" if event['location'] else ""
                            st.write(f"  📍 {event['start']} - {event['end']}: **{event['title']}** ({event['type']}){location_text}")
                        with col_remove:
                            if st.button("❌", key=f"remove_weekly_{event_idx}_{day}", help="Remove this event"):
                                st.session_state.weekly_events.pop(event_idx)
                                st.rerun()

        st.subheader("What do you want to achieve this week?")
        goals = st.text_area("Weekly Goals:", height=120, placeholder="Complete project proposal, prepare for presentation, learn new skill, exercise 3 times...")

        st.subheader("What constraints do you have?")
        constraints = st.text_area("Constraints & Commitments:", height=120, placeholder="Work 9-5, kids pickup at 3 PM, gym closes at 10 PM...")

        if st.button("📆 Create Weekly Plan", type="primary"):
            if goals or st.session_state.weekly_events:
                # Create enhanced prompt with weekly events
                weekly_events_text = format_weekly_events(st.session_state.weekly_events)
                enhanced_prompt = f"Goals: {goals}\n\nConstraints: {constraints}{weekly_events_text}"
                
                with st.spinner("🤖 Creating your weekly plan..."):
                    weekly_plan = create_weekly_plan(enhanced_prompt, "")

                if weekly_plan and not weekly_plan.startswith("Error"):
                    st.success("✅ Weekly plan created!")
                    
                    # Store in session state
                    st.session_state.current_weekly_plan = weekly_plan
                    if 'weekly_plans' not in st.session_state:
                        st.session_state.weekly_plans = []
                    st.session_state.weekly_plans.append({
                        'timestamp': datetime.now(),
                        'plan': weekly_plan,
                        'goals': goals,
                        'constraints': constraints,
                        'weekly_events': st.session_state.weekly_events.copy()
                    })
                    
                    # Display the plan
                    with st.expander("📅 Your Weekly Plan", expanded=True):
                        st.write(weekly_plan)
                    
                    # Download option
                    st.download_button(
                        label="📥 Download Weekly Plan",
                        data=weekly_plan,
                        file_name=f"weekly_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain"
                    )
                else:
                    st.error(f"Failed to create weekly plan: {weekly_plan}")
            else:
                st.error("Please enter your weekly goals or add some weekly events!")

    with col2:
        st.subheader("📋 Weekly Planning Tips:")
        st.markdown("""
        **Goal Setting**
        - 3-5 major goals max
        - Mix of urgent and important
        - Include learning/growth

        **Time Blocking**
        - Theme days (e.g., Monday = Planning)
        - Protect deep work time
        - Buffer for unexpected tasks

        **Review & Adjust**
        - Friday afternoon reviews
        - Sunday planning sessions
        """)
        
        if st.session_state.weekly_events:
            total_events = len(st.session_state.weekly_events)
            total_time_slots = sum(len(event['days']) for event in st.session_state.weekly_events)
            st.info(f"📌 You have {total_events} recurring events scheduled across {total_time_slots} time slots this week!")
        
        st.subheader("🎯 Quick Add Templates:")
        if st.button("+ Work Schedule (M-F 9-5)"):
            work_event = {
                'title': 'Work',
                'type': 'Work',
                'start': '09:00 AM',
                'end': '05:00 PM',
                'location': 'Office',
                'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            }
            st.session_state.weekly_events.append(work_event)
            st.success("Added standard work schedule!")
            st.rerun()
        
        if st.button("+ Daily Standup (M-F 9 AM)"):
            standup_event = {
                'title': 'Daily Standup',
                'type': 'Meeting',
                'start': '09:00 AM',
                'end': '09:30 AM',
                'location': 'Conference Room',
                'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            }
            st.session_state.weekly_events.append(standup_event)
            st.success("Added daily standup meetings!")
            st.rerun()