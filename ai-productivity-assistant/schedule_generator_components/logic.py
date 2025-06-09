from schedule_generator_components.helpers import format_time_slot
import streamlit as st

def build_enhanced_prompt(prompt, work_style, energy_level):
    fixed_events_text = ""
    if st.session_state.fixed_events:
        fixed_events_text = "\n\nFIXED APPOINTMENTS (must be included in schedule):\n"
        for event in st.session_state.fixed_events:
            fixed_events_text += format_time_slot(
                event['start'], event['end'],
                f"{event['title']} ({event['type']})",
                event['location']
            ) + "\n"
        fixed_events_text += "\nPlease schedule other tasks around these fixed appointments.\n"
    return f"{prompt}{fixed_events_text}\nWork Style: {work_style}\nEnergy Pattern: {energy_level}"

def add_event_to_session(event):
    st.session_state.fixed_events.append(event)
    st.success(f"✅ Added: {event['title']}")
    st.rerun()

def clear_all_events():
    st.session_state.fixed_events = []
    st.success("All events cleared!")
    st.rerun()
