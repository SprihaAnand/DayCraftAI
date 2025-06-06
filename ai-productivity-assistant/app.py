import streamlit as st
import streamlit.components.v1 as components
import os
from dotenv import load_dotenv
from agent import (
    generate_schedule, analyze_productivity, suggest_improvements, 
    prioritize_tasks, generate_focus_session, create_weekly_plan
)
from scheduler import display_schedule, display_schedule_timeline, save_schedule, create_schedule_summary
def add_google_verification(verification_code):
    components.html(
        f"""
        <head>
            <meta name="google-site-verification" content="XX-AXaVhktY4Z8Nbo0TQuNE-JfiWLsADb0Azfs8Ijj8" />
        </head>
        """,
        height=0,  # Prevent iframe from displaying a scrollbar
        width=0,
    )
# Streamlit app configuration (must be first Streamlit command)
st.set_page_config(
    page_title="AI Productivity Assistant",
    page_icon="🤖",
    layout="wide"
)

# Load environment variables
load_dotenv()

# Dark mode toggle (in sidebar)
dark_mode = st.sidebar.checkbox("🌙 Dark Mode")

# Apply dark or light mode styles
def apply_mode_styles():
    if dark_mode:
        st.markdown(
            """
            <style>
            /* Whole page and main container */
            html, body, .main, .block-container {
                background-color: #121212 !important;
                color: #e0e0e0 !important;
            }

            /* Sidebar */
            [data-testid="stSidebar"] {
                background-color: #1e1e1e !important;
                color: #e0e0e0 !important;
            }

            /* General text */
            p, span, h1, h2, h3, h4, h5, h6, label, div, li {
                color: #e0e0e0 !important;
            }

            /* Input fields */
            input, textarea {
                background-color: #222 !important;
                color: #eee !important;
                border: 1px solid #555 !important;
            }

            /* Dropdowns */
            .stSelectbox div[data-baseweb="select"] {
                background-color: #222 !important;
                color: #eee !important;
            }

            /* Fix dropdown menu items */
            .stSelectbox div[data-baseweb="select"] * {
                color: #eee !important;
                background-color: #222 !important;
            }

            /* Placeholder text */
            input::placeholder, textarea::placeholder {
                color: #bbb !important;
                opacity: 1 !important;
            }

            /* Buttons */
            .stButton > button {
                background-color: #333 !important;
                color: white !important;
                border: none !important;
            }
            .stButton > button:hover {
                background-color: #555 !important;
            }

            /* Expander */
            .streamlit-expanderHeader {
                background-color: #1e1e1e !important;
                color: #e0e0e0 !important;
            }
            .streamlit-expanderContent {
                background-color: #121212 !important;
                color: #e0e0e0 !important;
            }

            /* Scrollbars */
            ::-webkit-scrollbar {
                width: 8px;
            }
            ::-webkit-scrollbar-track {
                background: #121212;
            }
            ::-webkit-scrollbar-thumb {
                background-color: #444;
                border-radius: 10px;
            }

            /* Header (top navigation or toolbar) */
            header[data-testid="stHeader"] {
                background-color: #121212 !important;
            }

            /* Dropdown popups */
            div[data-testid="stDropdown"] {
                background-color: #222 !important;
                color: #eee !important;
            }

            /* Dropdown menu list */
            li[role="listbox"] {
                background-color: #222 !important;
                color: #eee !important;
            }

            /* Dropdown items */
            li[role="listbox"] li {
                background-color: #222 !important;
                color: #eee !important;
            }

            /* Fix focus/hover states */
            li[role="listbox"] li:hover {
                background-color: #333 !important;
            }
            </style>
            """,
            unsafe_allow_html=True
            
        )

    else:
        st.markdown(
            """
            <style>
            html, body, .main, .block-container {
                background-color: white !important;
                color: black !important;
            }
            [data-testid="stSidebar"] {
                background-color: white !important;
                color: black !important;
            }
            .stButton > button {
                background-color: #f0f0f0 !important;
                color: black !important;
                border: none !important;
            }
            input, textarea, select {
                background-color: white !important;
                color: black !important;
                border: 1px solid #ccc !important;
            }
            input::placeholder, textarea::placeholder {
                color: #999 !important;
                opacity: 1 !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

apply_mode_styles()

# --- Rest of your app below ---

# App title and description
st.title("🤖 AI Productivity Assistant")
st.markdown("*Powered by Google Gemini AI*")

# Sidebar for navigation
st.sidebar.title("🧭 Navigation")
page = st.sidebar.selectbox(
    "Choose a feature:",
    [
        "📅 Schedule Generator", 
        "📋 Task Prioritizer", 
        "📊 Productivity Analyzer", 
        "🔧 Schedule Improver",
        "🎯 Focus Session",
        "📆 Weekly Planner"
    ]
)

# Check if API key is set
if not os.getenv("GEMINI_API_KEY"):
    st.error("⚠️ Please set your GEMINI_API_KEY in the .env file")
    st.markdown("""
    **How to get your Gemini API key:**
    1. Go to [Google AI Studio](https://aistudio.google.com/)
    2. Click "Get API Key"
    3. Create a new API key
    4. Add it to your .env file as: `GEMINI_API_KEY=your_key_here`
    """)
    st.stop()

# Schedule Generator Page
if page == "📅 Schedule Generator":
    st.header("📅 Daily Schedule Generator")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Tell me about your day:")
        prompt = st.text_area(
            "Describe your tasks, meetings, deadlines, and preferences:",
            placeholder="I have a team meeting at 10 AM, need to finish a report by 3 PM, want to include lunch break and some time for emails. I'm most productive in the morning...",
            height=150
        )
        
        # Additional options
        col1a, col1b = st.columns(2)
        with col1a:
            work_style = st.selectbox(
                "Work Style Preference:",
                ["Balanced", "Deep Work Focus", "Meeting Heavy", "Creative Work"]
            )
        with col1b:
            energy_level = st.selectbox(
                "When are you most energetic?",
                ["Morning Person", "Afternoon Peak", "Evening Owl", "Consistent Throughout"]
            )
        
        enhanced_prompt = f"{prompt}\n\nWork Style: {work_style}\nEnergy Pattern: {energy_level}"
        
        if st.button("🚀 Generate Schedule", type="primary"):
            if prompt:
                with st.spinner("🤖 Creating your personalized schedule..."):
                    schedule = generate_schedule(enhanced_prompt)
                
                if schedule and not schedule.startswith("Error"):
                    st.success("✅ Schedule generated successfully!")
                    
                    # Store schedule in session state
                    st.session_state.current_schedule = schedule
                    
                    # Display the schedule
                    display_schedule(schedule)
                    
                    # Create summary
                    create_schedule_summary(schedule)
                    
                    # Option to save schedule
                    col_save1, col_save2 = st.columns(2)
                    with col_save1:
                        if st.button("💾 Save Schedule"):
                            filename = save_schedule(schedule)
                            if filename:
                                st.success(f"Schedule saved as {filename}")
                    
                    with col_save2:
                        if st.button("📋 Copy to Clipboard"):
                            st.code(schedule, language="text")
                
                else:
                    st.error(f"Failed to generate schedule: {schedule}")
            else:
                st.warning("Please enter a description of your day.")
    
    with col2:
        st.subheader("💡 Tips for better schedules:")
        st.markdown("""
        - **Be specific** about meeting times
        - **Mention energy levels** (morning vs evening person)
        - **Include buffer time** between tasks
        - **Add breaks and meals**
        - **Specify deadlines** and priorities
        - **Share constraints** (commute, family time)
        - **Include preferred work styles**
        """)
        
        st.subheader("📊 Quick Stats:")
        if 'current_schedule' in st.session_state:
            st.success("✅ Schedule ready!")
        else:
            st.info("📝 No schedule generated yet")

# Task Prioritizer Page
elif page == "📋 Task Prioritizer":
    st.header("📋 Task Prioritizer")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Enter your tasks:")
        task_input = st.text_area(
            "List your tasks (one per line or comma-separated):",
            placeholder="Review project proposal\nPrepare presentation slides\nReply to emails\nTeam meeting preparation\nComplete budget analysis\nUpdate project documentation",
            height=150
        )
        
        # Additional context
        context = st.text_area(
            "Additional context (deadlines, importance, etc.):",
            placeholder="Project proposal due tomorrow, presentation is for CEO next week, budget analysis is quarterly requirement...",
            height=80
        )
        
        full_input = f"Tasks:\n{task_input}\n\nContext:\n{context}" if context else task_input
    
    with col2:
        st.subheader("🎯 Priority Framework:")
        st.markdown("""
        **High Priority**: Urgent + Important
        - Deadlines today/tomorrow
        - Critical business impact
        
        **Medium Priority**: Important but not urgent
        - Strategic work
        - Planning activities
        
        **Low Priority**: Nice to have
        - Optional improvements
        - Future preparation
        """)
    
    if st.button("🎯 Prioritize Tasks", type="primary"):
        if task_input:
            with st.spinner("🤖 Analyzing and prioritizing your tasks..."):
                priorities = prioritize_tasks(full_input)
            
            if priorities and not priorities.startswith("Error"):
                st.success("✅ Tasks prioritized successfully!")
                st.markdown("### 📊 Prioritized Task List")
                st.write(priorities)
            else:
                st.error(f"Failed to prioritize tasks: {priorities}")
        else:
            st.warning("Please enter your tasks.")

# Focus Session Page
elif page == "🎯 Focus Session":
    st.header("🎯 Focus Session Planner")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Plan your focus session:")
        
        col1a, col1b = st.columns(2)
        with col1a:
            duration = st.selectbox(
                "Session Duration:",
                [25, 45, 60, 90, 120],
                help="Choose based on your attention span and task complexity"
            )
        
        with col1b:
            task_type = st.selectbox(
                "Type of Work:",
                ["Creative Work", "Analytical Tasks", "Writing", "Coding", "Planning", "Research", "Administrative"]
            )
        
        task_description = st.text_area(
            "Describe what you want to accomplish:",
            placeholder="Write the introduction for my research paper, focusing on the literature review section...",
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
        - Great for most tasks
        
        **Deep Work Sessions**
        - 60-90 min uninterrupted
        - For complex, creative work
        
        **Timeboxing**
        - Fixed time for specific tasks
        - Prevents perfectionism
        """)

# Weekly Planner Page
elif page == "📆 Weekly Planner":
    st.header("📆 Weekly Productivity Planner")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("What do you want to achieve this week?")
        goals = st.text_area(
            "Weekly Goals:",
            placeholder="Complete project phase 1\nPrepare quarterly presentation\nCatch up on industry reading\nOrganize team building event",
            height=120
        )
        
        st.subheader("What constraints do you have?")
        constraints = st.text_area(
            "Constraints & Commitments:",
            placeholder="Monday - all day workshop\nWednesday - client meetings\nFriday afternoon - team retrospective\nPersonal: gym 3x per week",
            height=120
        )
        
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

# Productivity Analyzer Page
elif page == "📊 Productivity Analyzer":
    st.header("📊 Productivity Analyzer")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Tasks Completed Today:")
        tasks_completed = st.text_area(
            "List what you accomplished:",
            placeholder="✅ Finished project proposal\n✅ Attended 3 meetings\n✅ Replied to 20 emails\n✅ Completed code review\n✅ Updated documentation",
            height=120
        )
    
    with col2:
        st.subheader("Time Spent:")
        time_spent = st.text_area(
            "How did you spend your time?",
            placeholder="🕐 4 hours on project work\n🕐 2 hours in meetings\n🕐 1 hour on emails\n🕐 30 minutes on planning\n🕐 1 hour on learning",
            height=120
        )
    
    # Additional context
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
            full_analysis_input = f"""
            Tasks Completed: {tasks_completed}
            Time Spent: {time_spent}
            {context_info}
            """
            
            with st.spinner("🤖 Analyzing your productivity..."):
                analysis = analyze_productivity(full_analysis_input, "")
            
            if analysis and not analysis.startswith("Error"):
                st.success("✅ Productivity analysis complete!")
                st.markdown("### 📈 Your Productivity Report")
                st.write(analysis)
            else:
                st.error(f"Failed to analyze productivity: {analysis}")
        else:
            st.warning("Please fill in both tasks completed and time spent.")

# Schedule Improver Page
elif page == "🔧 Schedule Improver":
    st.header("🔧 Schedule Improver")
    
    # Check if there's a current schedule
    if 'current_schedule' in st.session_state:
        st.subheader("Current Schedule:")
        with st.expander("View Current Schedule", expanded=True):
            st.write(st.session_state.current_schedule)
        
        st.subheader("What would you like to improve?")
        feedback = st.text_area(
            "Share your feedback or specific issues:",
            placeholder="⏰ I need more time for lunch\n🏃 The morning is too packed\n🧠 I prefer to do creative work in the afternoon\n📅 Need buffer time between meetings\n💤 I get tired after 2 PM",
            height=120
        )
        
        # Improvement focus
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
            st.experimental_rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>Made with ❤️ using Streamlit and Google Gemini AI</p>
    <p><small>Free tier: 15 requests per minute • 1,500 requests per day</small></p>
</div>
""", unsafe_allow_html=True)
