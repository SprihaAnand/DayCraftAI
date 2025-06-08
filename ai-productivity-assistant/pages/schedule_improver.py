import streamlit as st
from agent import suggest_improvements

def schedule_improver_page():
    st.header("🔧 Schedule Improver")

    if 'current_schedule' in st.session_state:
        st.subheader("Current Schedule:")
        with st.expander("View Current Schedule", expanded=True):
            st.write(st.session_state.current_schedule)

        st.subheader("What would you like to improve?")
        feedback = st.text_area("Share your feedback or specific issues:", height=120)
        improvement_focus = st.multiselect(
            "Focus areas for improvement:",
            ["Time Management", "Energy Optimization", "Work-Life Balance", "Meeting Efficiency", "Deep Work Protection", "Stress Reduction"]
        )

        full_feedback = f"{feedback}\n\nFocus Areas: {', '.join(improvement_focus)}" if improvement_focus else feedback

        if st.button("💡 Suggest Improvements", type="primary"):
            if feedback:
                with st.spinner("🤖 Analyzing and suggesting improvements..."):
                    improvements = suggest_improvements(st.session_state.current_schedule, full_feedback)

                if improvements and not improvements.startswith("Error"):
                    st.success("✅ Improvement suggestions ready!")
                    st.markdown("### 💡 Suggested Improvements")
                    st.write(improvements)
                else:
                    st.error(f"Failed to suggest improvements: {improvements}")
            else:
                st.warning("Please provide feedback on your schedule.")
    else:
        st.info("💡 Generate a schedule first using the Schedule Generator to use this feature.")
        if st.button("📅 Go to Schedule Generator"):
            st.session_state.page = "📅 Schedule Generator"
            st.rerun()
