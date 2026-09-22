"""Progress and reflection."""

from components.workspace import current_workspace
from pages.insights import render_insights

database, user, ai = current_workspace()
render_insights(database, user, ai)
