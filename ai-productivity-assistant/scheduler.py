import streamlit as st
import re
from datetime import datetime, timedelta

def display_schedule(schedule):
    """
    Display the schedule in a formatted way
    Handles both string and structured data formats
    """
    if isinstance(schedule, str):
        # If schedule is a string, display it directly with formatting
        st.subheader("📅 Your Daily Schedule")
        
        # Split the schedule into lines and format nicely
        lines = schedule.split('\n')
        for line in lines:
            line = line.strip()
            if line:
                # Check if line looks like a time entry
                if re.match(r'^\d{1,2}:\d{2}', line) or re.match(r'^\d{1,2}[ap]m', line.lower()):
                    st.write(f"⏰ **{line}**")
                elif line.startswith('#') or line.startswith('**'):
                    st.write(line)
                elif line.startswith('-') or line.startswith('•'):
                    st.write(f"  {line}")
                else:
                    st.write(line)
    
    elif isinstance(schedule, list):
        # If schedule is a list of dictionaries
        st.subheader("📅 Your Daily Schedule")
        for item in schedule:
            if isinstance(item, dict) and 'time' in item and 'task' in item:
                st.write(f"⏰ **{item['time']}** → {item['task']}")
            else:
                st.write(str(item))
    
    else:
        # Fallback for other data types
        st.subheader("📅 Your Daily Schedule")
        st.write(str(schedule))

def parse_schedule_to_events(schedule_text):
    """
    Parse a text schedule into structured events
    Returns a list of dictionaries with time and task
    """
    events = []
    
    if not isinstance(schedule_text, str):
        return events
    
    lines = schedule_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Try to match time patterns
        time_patterns = [
            r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\s*[-–—:]\s*(.+)',
            r'(\d{1,2}:\d{2})\s*[-–—:]\s*(.+)',
            r'(\d{1,2}[ap]m)\s*[-–—:]\s*(.+)',
            r'(\d{1,2}:\d{2}\s*[ap]m)\s*[-–—:]\s*(.+)',
        ]
        
        for pattern in time_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                time_str = match.group(1).strip()
                task = match.group(2).strip()
                events.append({
                    'time': time_str,
                    'task': task
                })
                break
    
    return events

def display_schedule_timeline(schedule):
    """
    Display schedule in a timeline format
    """
    st.subheader("📅 Daily Timeline")
    
    if isinstance(schedule, str):
        events = parse_schedule_to_events(schedule)
        
        if events:
            # Display as timeline
            for event in events:
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.write(f"⏰ **{event['time']}**")
                with col2:
                    st.write(event['task'])
        else:
            # If no events parsed, display original text
            st.write(schedule)
    
    elif isinstance(schedule, list):
        for item in schedule:
            if isinstance(item, dict) and 'time' in item and 'task' in item:
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.write(f"⏰ **{item['time']}**")
                with col2:
                    st.write(item['task'])
            else:
                st.write(str(item))
    else:
        st.write(str(schedule))

def save_schedule(schedule, filename=None):
    """
    Save schedule to a file
    """
    if filename is None:
        filename = f"schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            if isinstance(schedule, str):
                f.write(schedule)
            elif isinstance(schedule, list):
                for item in schedule:
                    if isinstance(item, dict):
                        f.write(f"{item.get('time', '')}: {item.get('task', '')}\n")
                    else:
                        f.write(f"{item}\n")
            else:
                f.write(str(schedule))
        
        return filename
    except Exception as e:
        st.error(f"Error saving schedule: {str(e)}")
        return None

def create_schedule_summary(schedule):
    """
    Create a summary of the schedule
    """
    if isinstance(schedule, str):
        events = parse_schedule_to_events(schedule)
        total_events = len(events)
        
        if total_events > 0:
            st.info(f"📊 Schedule contains {total_events} scheduled activities")
        
        # Try to identify key activities
        important_keywords = ['meeting', 'deadline', 'presentation', 'interview', 'appointment']
        important_events = []
        
        for event in events:
            task_lower = event['task'].lower()
            for keyword in important_keywords:
                if keyword in task_lower:
                    important_events.append(event)
                    break
        
        if important_events:
            st.warning("⚠️ Important activities today:")
            for event in important_events:
                st.write(f"• {event['time']}: {event['task']}")
    
    elif isinstance(schedule, list):
        st.info(f"📊 Schedule contains {len(schedule)} items")

def export_to_calendar_format(schedule):
    """
    Export schedule to a calendar-friendly format
    """
    if isinstance(schedule, str):
        events = parse_schedule_to_events(schedule)
    elif isinstance(schedule, list):
        events = schedule
    else:
        return "Unable to export schedule"
    
    calendar_text = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Productivity Agent//EN\n"
    
    for event in events:
        if isinstance(event, dict) and 'time' in event and 'task' in event:
            calendar_text += f"BEGIN:VEVENT\n"
            calendar_text += f"SUMMARY:{event['task']}\n"
            calendar_text += f"DTSTART:{event['time']}\n"
            calendar_text += f"END:VEVENT\n"
    
    calendar_text += "END:VCALENDAR"
    return calendar_text