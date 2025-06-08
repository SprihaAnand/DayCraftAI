import streamlit as st
from agent import analyze_productivity

def productivity_analyzer_page():
    st.header("📊 Productivity Analyzer")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Tasks Completed Today:")
        tasks_completed = st.text_area("List what you accomplished:", height=120)

    with col2:
        st.subheader("Time Spent:")
        time_spent = st.text_area("How did you spend your time?", height=120)

    st.subheader("Additional Context (Optional):")
    col3, col4 = st.columns(2)

    with col3:
        energy_level = st.slider("Energy Level Today:", 1, 10, 7)
        focus_quality = st.slider("Focus Quality:", 1, 10, 7)

    with col4:
        satisfaction = st.slider("Satisfaction with Progress:", 1, 10, 7)
        stress_level = st.slider("Stress Level:", 1, 10, 4)

    context_info = f"""
    Energy Level: {energy_level}/10
    Focus Quality: {focus_quality}/10
    Satisfaction: {satisfaction}/10
    Stress Level: {stress_level}/10
    """

    if st.button("📊 Analyze Productivity", type="primary"):
        if tasks_completed and time_spent:
            if "energy_levels" not in st.session_state:
                st.session_state.energy_levels = []
            if "productivity_ratings" not in st.session_state:
                st.session_state.productivity_ratings = []

            st.session_state.energy_levels.append(energy_level)
            st.session_state.productivity_ratings.append(satisfaction)

            full_input = f"Tasks Completed: {tasks_completed}\nTime Spent: {time_spent}\n{context_info}"

            with st.spinner("🤖 Analyzing your productivity..."):
                analysis = analyze_productivity(full_input, "")

            if analysis and not analysis.startswith("Error"):
                st.success("✅ Productivity analysis complete!")
                st.markdown("### 📈 Your Productivity Report")
                st.write(analysis)
            else:
                st.error(f"Failed to analyze productivity: {analysis}")
        else:
            st.warning("Please fill in both tasks completed and time spent.")
