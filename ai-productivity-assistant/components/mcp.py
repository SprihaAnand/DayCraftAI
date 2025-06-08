import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class ProductivityMCP:
    def __init__(self):
        self.visualization_context = {
            "schedule_data": [],
            "productivity_metrics": {},
            "task_analytics": {},
            "time_tracking": {}
        }

    def parse_schedule_data(self, schedule_text):
        if not schedule_text:
            return []

        time_blocks = []
        lines = schedule_text.split('\n')
        for line in lines:
            if ':' in line and any(t in line.lower() for t in ['am', 'pm', 'morning', 'afternoon', 'evening']):
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
        return time_blocks

    def _categorize_task(self, task):
        task_lower = task.lower()
        if any(k in task_lower for k in ['meeting', 'call', 'discussion']): return 'Meetings'
        if any(k in task_lower for k in ['project', 'work', 'develop', 'code']): return 'Deep Work'
        if any(k in task_lower for k in ['email', 'admin', 'organize']): return 'Administrative'
        if any(k in task_lower for k in ['break', 'lunch', 'rest']): return 'Breaks'
        if any(k in task_lower for k in ['learn', 'read', 'study']): return 'Learning'
        return 'Other'

    def create_schedule_timeline(self, schedule_data):
        if not schedule_data: return None
        df = pd.DataFrame(schedule_data)
        fig = px.timeline(df, x_start="start_time", x_end="end_time", y="task", color="category")
        fig.update_layout(height=400, showlegend=True)
        return fig

    def create_task_category_pie(self, category_counts):
        fig = px.pie(values=category_counts.values, names=category_counts.index, title="📊 Time Distribution by Category")
        return fig

    def create_task_priority_matrix(self, tasks):
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
        fig = px.scatter(df, x='urgency', y='importance', color='quadrant', hover_data=['task'],
                         title="🎯 Task Priority Matrix (Eisenhower Matrix)")
        fig.add_hline(y=5, line_dash="dash", line_color="gray")
        fig.add_vline(x=5, line_dash="dash", line_color="gray")
        return fig

    def _calculate_urgency(self, task):
        urgency_keywords = {'deadline': 9, 'urgent': 9, 'asap': 10, 'today': 8,
                             'tomorrow': 7, 'this week': 6, 'soon': 5, 'eventually': 2}
        for k, v in urgency_keywords.items():
            if k in task.lower(): return v
        return 5

    def _calculate_importance(self, task):
        importance_keywords = {'critical': 10, 'important': 8, 'strategic': 9,
                                'revenue': 9, 'client': 8, 'project': 7,
                                'meeting': 6, 'email': 3, 'admin': 2}
        for k, v in importance_keywords.items():
            if k in task.lower(): return v
        return 5

    def _get_quadrant(self, urgency, importance):
        if urgency >= 5 and importance >= 5: return "Do First (Urgent & Important)"
        if urgency < 5 and importance >= 5: return "Schedule (Important, Not Urgent)"
        if urgency >= 5 and importance < 5: return "Delegate (Urgent, Not Important)"
        return "Eliminate (Not Urgent, Not Important)"

    def create_real_productivity_dashboard(self):
        if not hasattr(st.session_state, 'user_data') or not st.session_state.user_data:
            return None
        metrics = self._process_user_metrics()
        if not any(metrics.values()):
            return None
        fig = make_subplots(rows=2, cols=2, subplot_titles=(
            'Task Categories', 'Daily Energy', 'Time Spent', 'Weekly Progress'),
            specs=[[{"type": "pie"}, {"type": "scatter"}],
                   [{"type": "bar"}, {"type": "scatter"}]]
        )
        if metrics.get('task_categories'):
            fig.add_trace(go.Pie(labels=list(metrics['task_categories'].keys()),
                                 values=list(metrics['task_categories'].values())), row=1, col=1)
        if metrics.get('energy_tracking'):
            fig.add_trace(go.Scatter(y=metrics['energy_tracking'], mode='lines+markers'), row=1, col=2)
        if metrics.get('time_allocation'):
            fig.add_trace(go.Bar(x=list(metrics['time_allocation'].keys()),
                                 y=list(metrics['time_allocation'].values())), row=2, col=1)
        if metrics.get('productivity_scores'):
            fig.add_trace(go.Scatter(y=metrics['productivity_scores'], mode='lines+markers'), row=2, col=2)
        fig.update_layout(height=600, showlegend=True, title_text="📊 Your Personal Productivity Dashboard")
        return fig

    def _process_user_metrics(self):
        metrics = {'task_categories': {}, 'energy_tracking': [], 'time_allocation': {}, 'productivity_scores': []}
        if hasattr(st.session_state, 'all_tasks'):
            for task in st.session_state.all_tasks:
                cat = self._categorize_task(task)
                metrics['task_categories'][cat] = metrics['task_categories'].get(cat, 0) + 1
        if hasattr(st.session_state, 'energy_levels'):
            metrics['energy_tracking'] = st.session_state.energy_levels
        if hasattr(st.session_state, 'schedule_times'):
            metrics['time_allocation'] = st.session_state.schedule_times
        if hasattr(st.session_state, 'productivity_ratings'):
            metrics['productivity_scores'] = st.session_state.productivity_ratings
        return metrics