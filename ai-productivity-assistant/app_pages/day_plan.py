"""The main daily-planning workflow."""

from components.plan_chat import render_plan_chat
from components.workspace import current_workspace
from pages.dashboard import render_dashboard
from pages.planner import render_planner

database, user, ai = current_workspace()
render_dashboard(database, user, ai)
render_planner(database, user, ai)
render_plan_chat(database, user, ai)
