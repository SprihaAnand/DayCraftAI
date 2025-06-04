from datetime import datetime
import json
import streamlit as st

def show_reminders():
    now = datetime.now().strftime("%H:%M")
    try:
        with open("data\\user_schedule.json", "r") as f:
            schedule = json.load(f)
    except:
        return

    for item in schedule:
        if item["time"] == now:
            st.warning(f"⏰ Reminder: {item['task']}")
