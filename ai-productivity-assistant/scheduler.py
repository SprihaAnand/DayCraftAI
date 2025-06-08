import streamlit as st
import pandas as pd
import plotly.express as px

def display_schedule(schedule_text):
    st.subheader("📝 Your AI-Generated Schedule")

    # Parse schedule text into a dataframe
    rows = []
    for line in schedule_text.split('\n'):
        if ' - ' in line:
            time, task = line.split(' - ', 1)
            rows.append({'Time': time.strip(), 'Task': task.strip()})
    if rows:
        df = pd.DataFrame(rows)
        st.table(df)
    else:
        # fallback if parsing fails, show markdown with line breaks
        st.markdown(schedule_text.replace('\n', '  \n'))


def create_schedule_summary(schedule_text):
    st.subheader("📌 Quick Summary")
    num_lines = len(schedule_text.strip().split("\n"))
    num_meetings = sum(1 for line in schedule_text.lower().split("\n") if "meeting" in line)
    num_breaks = sum(1 for line in schedule_text.lower().split("\n") if "break" in line)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Activities", num_lines)
    col2.metric("Meetings", num_meetings)
    col3.metric("Breaks", num_breaks)

def display_schedule_timeline(schedule_blocks):
    if not schedule_blocks:
        return

    df = pd.DataFrame(schedule_blocks)
    fig = px.timeline(
        df,
        x_start="start_time",
        x_end="end_time",
        y="task",
        color="category",
        title="📅 Your Schedule Timeline"
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

def save_schedule(schedule_text, filename="my_schedule.txt"):
    with open(filename, "w") as f:
        f.write(schedule_text)
    st.success(f"✅ Schedule saved as {filename}")
