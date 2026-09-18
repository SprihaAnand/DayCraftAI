"""Account and integration settings."""

from components.workspace import current_workspace
from pages.settings import render_settings

database, user, calendar, _ = current_workspace()
render_settings(database, user, calendar)
