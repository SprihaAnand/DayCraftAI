import streamlit as st
from agent import create_weekly_plan

def weekly_planner_page():
    st.header("📆 Weekly Productivity Planner")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("What do you want to achieve this week?")
        goals = st.text_area("Weekly Goals:", height=120)

        st.subheader("What constraints do you have?")
        constraints = st.text_area("Constraints & Commitments:", height=120)

        if st.button("📆 Create Weekly Plan", type="primary"):
            if goals:
                with st.spinner("🤖 Creating your weekly plan..."):
                    weekly_plan = create_weekly_plan(goals, constraints)

                if weekly_plan and not weekly_plan.startswith("Error"):
                    st.success("✅ Weekly plan created!")
                    st.write(weekly_plan)
                else:
                    st.error(f"Failed to create weekly plan: {weekly_plan}")
            else:
                st.warning("Please enter your weekly goals.")

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
