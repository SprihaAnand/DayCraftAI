import streamlit as st
import streamlit.components.v1 as components
import os
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from agent import (
    generate_schedule, analyze_productivity, suggest_improvements, 
    prioritize_tasks, generate_focus_session, create_weekly_plan
)
from scheduler import display_schedule, display_schedule_timeline, save_schedule, create_schedule_summary

# MCP Integration for Enhanced Visualizations
class ProductivityMCP:
    """Model Context Protocol integration for productivity visualizations"""
    
    def __init__(self):
        self.visualization_context = {
            "schedule_data": [],
            "productivity_metrics": {},
            "task_analytics": {},
            "time_tracking": {}
        }
    
    def extract_user_data(self, session_state):
        """Extract all user data from session state for visualization"""
        user_data = {
            'schedules': [],
            'tasks': [],
            'productivity_data': [],
            'focus_sessions': [],
            'weekly_goals': []
        }
        
        # Collect all user input data
        for key, value in session_state.items():
            if 'schedule' in key.lower() and value:
                user_data['schedules'].append(value)
            elif 'task' in key.lower() and value:
                user_data['tasks'].append(value)
            elif 'productivity' in key.lower() and value:
                user_data['productivity_data'].append(value)
            elif 'focus' in key.lower() and value:
                user_data['focus_sessions'].append(value)
            elif 'goal' in key.lower() and value:
                user_data['weekly_goals'].append(value)
        
        return user_data
    
    def parse_schedule_data(self, schedule_text):
        """Parse schedule text and extract time blocks for visualization"""
        time_blocks = []
        lines = schedule_text.split('\n')
        
        for line in lines:
            if ':' in line and any(time_indicator in line.lower() for time_indicator in ['am', 'pm', ':', 'morning', 'afternoon', 'evening']):
                # Extract time and task information
                try:
                    # Basic parsing - can be enhanced with regex
                    if '-' in line:
                        parts = line.split('-', 1)
                        if len(parts) == 2:
                            time_part = parts[0].strip()
                            task_part = parts[1].strip()
                            time_blocks.append({
                                'time': time_part,
                                'task': task_part,
                                'category': self._categorize_task(task_part)
                            })
                except:
                    continue
        
        return time_blocks
    
    def _categorize_task(self, task):
        """Categorize tasks for better visualization"""
        task_lower = task.lower()
        if any(keyword in task_lower for keyword in ['meeting', 'call', 'discussion']):
            return 'Meetings'
        elif any(keyword in task_lower for keyword in ['project', 'work', 'develop', 'code']):
            return 'Deep Work'
        elif any(keyword in task_lower for keyword in ['email', 'admin', 'organize']):
            return 'Administrative'
        elif any(keyword in task_lower for keyword in ['break', 'lunch', 'rest']):
            return 'Breaks'
        elif any(keyword in task_lower for keyword in ['learn', 'read', 'study']):
            return 'Learning'
        else:
            return 'Other'
    
    def create_schedule_timeline(self, schedule_data):
        """Create interactive timeline visualization"""
        if not schedule_data:
            return None
        
        df = pd.DataFrame(schedule_data)
        
        # Create Gantt-like chart
        fig = px.timeline(
            df, 
            x_start="start_time", 
            x_end="end_time", 
            y="task",
            color="category",
            title="📅 Daily Schedule Timeline",
            labels={"task": "Tasks", "category": "Category"}
        )
        
        fig.update_layout(
            height=400,
            showlegend=True,
            xaxis_title="Time",
            yaxis_title="Tasks"
        )
        
        return fig
    
    def create_real_productivity_dashboard(self):
        """Create dashboard using actual user data from session state"""
        if not hasattr(st.session_state, 'user_data') or not st.session_state.user_data:
            return None
        
        # Extract real metrics from user data
        metrics = self._process_user_metrics()
        
        if not any(metrics.values()):
            return None
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Task Categories', 'Daily Energy', 'Time Spent', 'Weekly Progress'),
            specs=[[{"type": "pie"}, {"type": "scatter"}],
                   [{"type": "bar"}, {"type": "scatter"}]]
        )
        
        # Task Categories from actual user input
        if metrics.get('task_categories'):
            categories = list(metrics['task_categories'].keys())
            values = list(metrics['task_categories'].values())
            
            fig.add_trace(
                go.Pie(labels=categories, values=values, name="Task Distribution"),
                row=1, col=1
            )
        
        # Energy levels from user input
        if metrics.get('energy_tracking'):
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(metrics['energy_tracking']))),
                    y=metrics['energy_tracking'],
                    mode='lines+markers',
                    name='Energy Level',
                    line=dict(color='orange')
                ),
                row=1, col=2
            )
        
        # Time allocation from user schedules
        if metrics.get('time_allocation'):
            fig.add_trace(
                go.Bar(
                    x=list(metrics['time_allocation'].keys()),
                    y=list(metrics['time_allocation'].values()),
                    name='Hours',
                    marker_color='lightblue'
                ),
                row=2, col=1
            )
        
        # Productivity scores from user feedback
        if metrics.get('productivity_scores'):
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(metrics['productivity_scores']))),
                    y=metrics['productivity_scores'],
                    mode='lines+markers',
                    name='Productivity',
                    line=dict(color='green')
                ),
                row=2, col=2
            )
        
        fig.update_layout(
            height=600, 
            showlegend=True, 
            title_text="📊 Your Personal Productivity Dashboard"
        )
        return fig
    
    def _process_user_metrics(self):
        """Process actual user data into visualization metrics"""
        metrics = {
            'task_categories': {},
            'energy_tracking': [],
            'time_allocation': {},
            'productivity_scores': []
        }
        
        # Process task data from user input
        if hasattr(st.session_state, 'all_tasks') and st.session_state.all_tasks:
            task_categories = {}
            for task in st.session_state.all_tasks:
                category = self._categorize_task(task)
                task_categories[category] = task_categories.get(category, 0) + 1
            metrics['task_categories'] = task_categories
        
        # Process energy data from user input
        if hasattr(st.session_state, 'energy_levels') and st.session_state.energy_levels:
            metrics['energy_tracking'] = st.session_state.energy_levels
        
        # Process time allocation from schedules
        if hasattr(st.session_state, 'schedule_times') and st.session_state.schedule_times:
            metrics['time_allocation'] = st.session_state.schedule_times
        
        # Process productivity scores
        if hasattr(st.session_state, 'productivity_ratings') and st.session_state.productivity_ratings:
            metrics['productivity_scores'] = st.session_state.productivity_ratings
        
        return metrics
    
    def create_task_priority_matrix(self, tasks):
        """Create Eisenhower Matrix visualization"""
        # Parse tasks and assign urgency/importance scores
        task_data = []
        for task in tasks:
            urgency = self._calculate_urgency(task)
            importance = self._calculate_importance(task)
            task_data.append({
                'task': task,
                'urgency': urgency,
                'importance': importance,
                'quadrant': self._get_quadrant(urgency, importance)
            })
        
        df = pd.DataFrame(task_data)
        
        fig = px.scatter(
            df,
            x='urgency',
            y='importance',
            color='quadrant',
            hover_data=['task'],
            title="🎯 Task Priority Matrix (Eisenhower Matrix)",
            labels={'urgency': 'Urgency →', 'importance': 'Importance →'}
        )
        
        # Add quadrant lines
        fig.add_hline(y=5, line_dash="dash", line_color="gray")
        fig.add_vline(x=5, line_dash="dash", line_color="gray")
        
        # Add quadrant labels
        fig.add_annotation(x=2.5, y=7.5, text="Important<br>Not Urgent", showarrow=False)
        fig.add_annotation(x=7.5, y=7.5, text="Important<br>& Urgent", showarrow=False)
        fig.add_annotation(x=2.5, y=2.5, text="Not Important<br>Not Urgent", showarrow=False)
        fig.add_annotation(x=7.5, y=2.5, text="Not Important<br>But Urgent", showarrow=False)
        
        fig.update_layout(height=500)
        return fig
    
    def _calculate_urgency(self, task):
        """Calculate urgency score (1-10) based on task keywords"""
        urgency_keywords = {
            'deadline': 9, 'urgent': 9, 'asap': 10, 'today': 8,
            'tomorrow': 7, 'this week': 6, 'soon': 5, 'eventually': 2
        }
        
        task_lower = task.lower()
        for keyword, score in urgency_keywords.items():
            if keyword in task_lower:
                return score
        return 5  # Default medium urgency
    
    def _calculate_importance(self, task):
        """Calculate importance score (1-10) based on task keywords"""
        importance_keywords = {
            'critical': 10, 'important': 8, 'strategic': 9, 'revenue': 9,
            'client': 8, 'project': 7, 'meeting': 6, 'email': 3, 'admin': 2
        }
        
        task_lower = task.lower()
        for keyword, score in importance_keywords.items():
            if keyword in task_lower:
                return score
        return 5  # Default medium importance
    
    def _get_quadrant(self, urgency, importance):
        """Determine Eisenhower Matrix quadrant"""
        if urgency >= 5 and importance >= 5:
            return "Do First (Urgent & Important)"
        elif urgency < 5 and importance >= 5:
            return "Schedule (Important, Not Urgent)"
        elif urgency >= 5 and importance < 5:
            return "Delegate (Urgent, Not Important)"
        else:
            return "Eliminate (Not Urgent, Not Important)"

# Initialize MCP
mcp = ProductivityMCP()

# Initialize session state for user data collection
if 'all_tasks' not in st.session_state:
    st.session_state.all_tasks = []
if 'energy_levels' not in st.session_state:
    st.session_state.energy_levels = []
if 'schedule_times' not in st.session_state:
    st.session_state.schedule_times = {}
if 'productivity_ratings' not in st.session_state:
    st.session_state.productivity_ratings = []
if 'user_schedules' not in st.session_state:
    st.session_state.user_schedules = []

# Streamlit app configuration
st.set_page_config(
    page_title="AI Productivity Assistant with Visualizations",
    page_icon="🤖",
    layout="wide"
)

# Load environment variables
load_dotenv()

# Apply your existing dark mode styles here
# ... (keep your existing styling code) ...

# App title and description
st.title("🤖 AI Productivity Assistant")
st.markdown("*Powered by Google Gemini AI with Advanced Visualizations*")

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
        "📆 Weekly Planner",
        "📈 Visualization Dashboard"  # New page
    ]
)

# Enhanced Schedule Generator with Visualization
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
        
        # Additional options (keep your existing code)
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
                    
                    # Store schedule in session state for visualization
                    st.session_state.current_schedule = schedule
                    st.session_state.user_schedules.append({
                        'timestamp': datetime.now(),
                        'schedule': schedule,
                        'work_style': work_style,
                        'energy_level': energy_level
                    })
                    
                    # Display the schedule
                    display_schedule(schedule)
                    
                    # NEW: Create visualization
                    st.subheader("📊 Schedule Visualization")
                    schedule_blocks = mcp.parse_schedule_data(schedule)
                    
                    if schedule_blocks:
                        # Create sample timeline data
                        timeline_data = []
                        current_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
                        
                        for i, block in enumerate(schedule_blocks[:6]):  # Limit to 6 blocks for demo
                            start_time = current_time + timedelta(hours=i*1.5)
                            end_time = start_time + timedelta(hours=1)
                            timeline_data.append({
                                'task': block['task'][:30] + '...' if len(block['task']) > 30 else block['task'],
                                'category': block['category'],
                                'start_time': start_time,
                                'end_time': end_time
                            })
                        
                        df = pd.DataFrame(timeline_data)
                        
                        # Create timeline chart
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
                        
                        # Category distribution
                        category_counts = df['category'].value_counts()
                        fig_pie = px.pie(
                            values=category_counts.values,
                            names=category_counts.index,
                            title="📊 Time Distribution by Category"
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
                    
                    # Create summary
                    create_schedule_summary(schedule)
    
    with col2:
        # Keep your existing tips section
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

# Enhanced Task Prioritizer with Matrix Visualization
elif page == "📋 Task Prioritizer":
    st.header("📋 Task Prioritizer with Priority Matrix")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Enter your tasks:")
        task_input = st.text_area(
            "List your tasks (one per line):",
            placeholder="Review project proposal\nPrepare presentation slides\nReply to emails\nTeam meeting preparation\nComplete budget analysis",
            height=150
        )
        
        context = st.text_area(
            "Additional context (deadlines, importance, etc.):",
            placeholder="Project proposal due tomorrow, presentation is for CEO next week...",
            height=80
        )
        
        if st.button("🎯 Prioritize Tasks", type="primary"):
            if task_input:
                # Store user tasks for visualization
                user_tasks = [task.strip() for task in task_input.split('\n') if task.strip()]
                st.session_state.all_tasks.extend(user_tasks)
                
                with st.spinner("🤖 Analyzing and prioritizing your tasks..."):
                    priorities = prioritize_tasks(f"Tasks:\n{task_input}\n\nContext:\n{context}")
                
                if priorities and not priorities.startswith("Error"):
                    st.success("✅ Tasks prioritized successfully!")
                    st.write(priorities)
                    
                    # Create Priority Matrix Visualization with actual user data
                    st.subheader("🎯 Your Personal Priority Matrix")
                    
                    if user_tasks:
                        matrix_fig = mcp.create_task_priority_matrix(user_tasks)
                        st.plotly_chart(matrix_fig, use_container_width=True)
                        
                        st.info("💡 **Your task analysis:**\n"
                               "- **Top Right (Red)**: Your urgent & important tasks\n"
                               "- **Top Left (Blue)**: Important tasks to schedule\n"
                               "- **Bottom Right (Green)**: Urgent tasks to delegate\n"
                               "- **Bottom Left (Purple)**: Tasks to eliminate")
    
    with col2:
        # Keep your existing priority framework
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

# New Visualization Dashboard Page - Using Real User Data
elif page == "📈 Visualization Dashboard":
    st.header("📈 Your Personal Productivity Dashboard")
    
    # Check if user has entered any data
    has_data = (
        len(st.session_state.all_tasks) > 0 or 
        len(st.session_state.energy_levels) > 0 or 
        len(st.session_state.schedule_times) > 0 or 
        len(st.session_state.productivity_ratings) > 0 or
        len(st.session_state.user_schedules) > 0
    )
    
    if has_data:
        st.success("✅ Displaying your personal productivity data!")
        
        # Create dashboard with actual user data
        dashboard_fig = mcp.create_real_productivity_dashboard()
        
        if dashboard_fig:
            st.plotly_chart(dashboard_fig, use_container_width=True)
        
        # Show detailed metrics based on user data
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_tasks = len(st.session_state.all_tasks)
            st.metric("Total Tasks Entered", total_tasks)
        
        with col2:
            if st.session_state.energy_levels:
                avg_energy = sum(st.session_state.energy_levels) / len(st.session_state.energy_levels)
                st.metric("Avg Energy Level", f"{avg_energy:.1f}/10")
            else:
                st.metric("Avg Energy Level", "No data")
        
        with col3:
            if st.session_state.productivity_ratings:
                avg_satisfaction = sum(st.session_state.productivity_ratings) / len(st.session_state.productivity_ratings)
                st.metric("Avg Satisfaction", f"{avg_satisfaction:.1f}/10")
            else:
                st.metric("Avg Satisfaction", "No data")
        
        with col4:
            total_schedules = len(st.session_state.user_schedules)
            st.metric("Schedules Created", total_schedules)
        
        # Individual data sections
        st.markdown("---")
        
        # Task Categories Analysis
        if st.session_state.all_tasks:
            st.subheader("📋 Your Task Categories")
            task_categories = {}
            for task in st.session_state.all_tasks:
                category = mcp._categorize_task(task)
                task_categories[category] = task_categories.get(category, 0) + 1
            
            if task_categories:
                task_df = pd.DataFrame(list(task_categories.items()), 
                                     columns=['Category', 'Count'])
                fig_tasks = px.pie(task_df, values='Count', names='Category', 
                                 title="Your Task Distribution")
                st.plotly_chart(fig_tasks, use_container_width=True)
                
                # Show actual tasks by category
                with st.expander("📝 View Your Tasks by Category"):
                    for category, count in task_categories.items():
                        st.write(f"**{category}** ({count} tasks):")
                        category_tasks = [task for task in st.session_state.all_tasks 
                                        if mcp._categorize_task(task) == category]
                        for task in category_tasks[:3]:  # Show first 3
                            st.write(f"• {task}")
                        if len(category_tasks) > 3:
                            st.write(f"• ... and {len(category_tasks) - 3} more")
        
        # Energy Tracking
        if st.session_state.energy_levels:
            st.subheader("⚡ Your Energy Patterns")
            energy_df = pd.DataFrame({
                'Session': range(1, len(st.session_state.energy_levels) + 1),
                'Energy Level': st.session_state.energy_levels
            })
            fig_energy = px.line(energy_df, x='Session', y='Energy Level', 
                               title="Your Energy Levels Over Time",
                               markers=True)
            fig_energy.update_layout(yaxis_range=[0, 10])
            st.plotly_chart(fig_energy, use_container_width=True)
        
        # Time Allocation
        if st.session_state.schedule_times:
            st.subheader("⏰ Your Time Allocation")
            time_df = pd.DataFrame(list(st.session_state.schedule_times.items()), 
                                 columns=['Activity', 'Hours'])
            fig_time = px.bar(time_df, x='Activity', y='Hours', 
                            title="Hours Spent on Different Activities")
            st.plotly_chart(fig_time, use_container_width=True)
        
        # Productivity Trends
        if st.session_state.productivity_ratings:
            st.subheader("📈 Your Satisfaction Trends")
            satisfaction_df = pd.DataFrame({
                'Session': range(1, len(st.session_state.productivity_ratings) + 1),
                'Satisfaction': st.session_state.productivity_ratings
            })
            fig_satisfaction = px.line(satisfaction_df, x='Session', y='Satisfaction', 
                                     title="Your Satisfaction Levels Over Time",
                                     markers=True)
            fig_satisfaction.update_layout(yaxis_range=[0, 10])
            st.plotly_chart(fig_satisfaction, use_container_width=True)
        
        # Recent Schedules
        st.subheader("📅 Your Recent Schedules")
        for i, schedule_data in enumerate(reversed(st.session_state.user_schedules[-3:])):
            st.markdown(f"### Schedule {len(st.session_state.user_schedules) - i}")
            st.write(f"🕒 {schedule_data['timestamp'].strftime('%Y-%m-%d %H:%M')}")
            st.write(f"Work Style: {schedule_data['work_style']}, Energy: {schedule_data['energy_level']}")
            st.write(schedule_data['schedule'])

        
    
    else:
        st.info("📊 **No data to visualize yet!**")
        st.markdown("""
        ### 🎯 To see your personal productivity dashboard:
        
        1. **📅 Generate a schedule** - Go to Schedule Generator and create your daily plan
        2. **📋 Prioritize tasks** - Use Task Prioritizer to add your tasks
        3. **📊 Analyze productivity** - Enter your completed tasks and time spent
        4. **🎯 Plan focus sessions** - Create focused work sessions
        5. **📆 Make weekly plans** - Set your weekly goals
        
        Once you've used these features, return here to see beautiful visualizations of YOUR data!
        """)
        
        st.markdown("### 📈 What you'll see:")
        st.markdown("""
        - **Task Distribution**: Pie charts of your actual task categories
        - **Energy Patterns**: Line graphs of your energy levels over time  
        - **Time Allocation**: Bar charts showing how you spend your time
        - **Satisfaction Trends**: Your productivity satisfaction scores
        - **Schedule History**: All your generated schedules with timestamps
        - **Personal Metrics**: KPIs based on your actual input data
        """)
        
        # Quick links to other pages
        st.markdown("### 🚀 Quick Start:")
        col_start1, col_start2, col_start3 = st.columns(3)
        
        with col_start1:
            if st.button("📅 Create Schedule"):
                st.session_state.current_page = "📅 Schedule Generator"
        
        with col_start2:
            if st.button("📋 Add Tasks"):
                st.session_state.current_page = "📋 Task Prioritizer"
        
        with col_start3:
            if st.button("📊 Track Progress"):
                st.session_state.current_page = "📊 Productivity Analyzer visualization examples"
        st.markdown("""
        ### 🎯 What this dashboard shows:
        
        **Task Distribution** - How you spend your time across different categories
        
        **Energy Levels** - Your energy patterns throughout the day
        
        **Time Allocation** - Hours spent on different types of work
        
        **Productivity Trends** - Your productivity scores over time
        
        **Key Metrics** - Important KPIs for tracking your productivity
        
        **Weekly Trends** - Longer-term patterns in your work habits
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
            # Store context data in session state for dashboard
            if "energy_levels" not in st.session_state:
                st.session_state.energy_levels = []
            if "productivity_ratings" not in st.session_state:
                st.session_state.productivity_ratings = []
            
            st.session_state.energy_levels.append(energy_level)
            st.session_state.productivity_ratings.append(satisfaction)

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
            st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>Made with ❤️ using Streamlit, Google Gemini AI, and MCP for Advanced Visualizations</p>
    <p><small>Enhanced with Interactive Charts • Real-time Analytics • Smart Visualizations</small></p>
</div>
""", unsafe_allow_html=True)
