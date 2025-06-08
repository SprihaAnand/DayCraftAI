import streamlit as st
from agent import prioritize_tasks
from components.mcp import ProductivityMCP
import pandas as pd

mcp = ProductivityMCP()

def task_prioritizer_page():
    st.header("📋 Task Prioritizer with Priority Matrix")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Enter your tasks:")
        task_input = st.text_area("List your tasks (one per line):", height=150)
        context = st.text_area("Additional context (deadlines, importance, etc.):", height=80)

        if st.button("🎯 Prioritize Tasks", type="primary"):
            if task_input:
                user_tasks = [task.strip() for task in task_input.split('\n') if task.strip()]
                st.session_state.all_tasks.extend(user_tasks)

                with st.spinner("🤖 Analyzing and prioritizing your tasks..."):
                    priorities = prioritize_tasks(f"Tasks:\n{task_input}\n\nContext:\n{context}")

                if priorities and not priorities.startswith("Error"):
                    st.success("✅ Tasks prioritized successfully!")
                    st.write(priorities)
                    st.subheader("🎯 Your Personal Priority Matrix")
                    if user_tasks:
                        matrix_fig = mcp.create_task_priority_matrix(user_tasks)
                        st.plotly_chart(matrix_fig, use_container_width=True)

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
