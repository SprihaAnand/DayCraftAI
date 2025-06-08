import streamlit as st
from agent import generate_focus_session

def focus_session_page():
    st.header("🎯 Focus Session Planner")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Plan your focus session:")
        col1a, col1b = st.columns(2)
        with col1a:
            duration = st.selectbox("Session Duration:", [25, 45, 60, 90, 120])
        with col1b:
            task_type = st.selectbox("Type of Work:", [
                "Creative Work", "Analytical Tasks", "Writing", "Coding", "Planning", "Research", "Administrative"
            ])

        task_description = st.text_area(
            "Describe what you want to accomplish:",
            placeholder="Write the introduction for my research paper...",
            height=100
        )

        if st.button("🎯 Create Focus Session", type="primary"):
            with st.spinner("🤖 Creating your focus session plan..."):
                session_plan = generate_focus_session(duration, f"{task_type}: {task_description}")

            if session_plan and not session_plan.startswith("Error"):
                st.success("✅ Focus session plan ready!")
                st.write(session_plan)
            else:
                st.error(f"Failed to create focus session: {session_plan}")

    with col2:
        st.subheader("⏱️ Focus Techniques:")
        st.markdown("""
        **Pomodoro Technique**
        - 25 min work + 5 min break

        **Deep Work Sessions**
        - 60-90 min uninterrupted

        **Timeboxing**
        - Fixed time for specific tasks
        """)
