"""Focused work sessions."""

from components.workspace import current_workspace
from pages.focus import render_focus

database, user, ai = current_workspace()
render_focus(database, user, ai)
