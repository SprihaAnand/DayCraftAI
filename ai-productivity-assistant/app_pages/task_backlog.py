"""Task capture and backlog management."""

from components.workspace import current_workspace
from pages.tasks import render_tasks

database, user, _, _ = current_workspace()
render_tasks(database, user)
