"""A local, user-scoped Model Context Protocol server for DayCraft.

Run this process through an MCP client using stdio. It deliberately reads the
target account only from ``DAYCRAFT_MCP_USER_EMAIL`` in the process environment;
an LLM cannot switch to another local account by passing a different email.
"""

from __future__ import annotations

import os
from datetime import date, time
from typing import Any

from services.database import Database


def _workspace() -> tuple[Database, dict[str, Any]]:
    email = os.getenv("DAYCRAFT_MCP_USER_EMAIL", "").strip()
    if not email:
        raise ValueError("Set DAYCRAFT_MCP_USER_EMAIL before starting the DayCraft MCP server.")
    database = Database()
    database.initialize()
    user = database.get_user_by_email(email)
    if not user:
        raise ValueError("No DayCraft account matches DAYCRAFT_MCP_USER_EMAIL.")
    return database, user


def _validated_priority(priority: str) -> str:
    normalized = priority.title()
    if normalized not in {"High", "Medium", "Low"}:
        raise ValueError("Priority must be High, Medium, or Low.")
    return normalized


def _validated_local_event(
    title: str,
    event_date: str,
    start_time: str,
    end_time: str,
    category: str,
    notes: str,
) -> tuple[str, date, str, str, str, str]:
    """Validate a local DayCraft event before an MCP client can create it."""
    clean_title = title.strip()
    clean_category = category.strip() or "General"
    clean_notes = notes.strip()
    if not clean_title or len(clean_title) > 200:
        raise ValueError("Event title must contain between 1 and 200 characters.")
    if len(clean_category) > 80 or len(clean_notes) > 10_000:
        raise ValueError("Event category or notes are too long.")
    try:
        parsed_date = date.fromisoformat(event_date)
        parsed_start = time.fromisoformat(start_time)
        parsed_end = time.fromisoformat(end_time)
    except (TypeError, ValueError) as error:
        raise ValueError("Use ISO date (YYYY-MM-DD) and 24-hour times (HH:MM).") from error
    if parsed_start >= parsed_end:
        raise ValueError("An event must end after it starts.")
    return (
        clean_title,
        parsed_date,
        parsed_start.strftime("%H:%M"),
        parsed_end.strftime("%H:%M"),
        clean_category,
        clean_notes,
    )


def build_server():
    """Build lazily so the Streamlit application does not require MCP to start."""
    try:
        # MCP Python SDK v2 import path.
        from mcp.server import MCPServer
    except ImportError:
        try:
            # Compatibility with MCP Python SDK v1.
            from mcp.server.fastmcp import FastMCP as MCPServer
        except ImportError as error:
            raise RuntimeError("Install the optional 'mcp' dependency to run the DayCraft MCP server.") from error

    mcp = MCPServer("DayCraft")

    @mcp.tool()
    def get_today_brief() -> dict[str, Any]:
        """Return today’s actual task, focus, and local agenda summary for the configured account."""
        database, user = _workspace()
        today = date.today()
        return {
            "date": today.isoformat(),
            "metrics": database.dashboard_metrics(int(user["id"]), today),
            "agenda": database.list_events(int(user["id"]), start_date=today, end_date=today),
            "next_tasks": database.list_tasks(int(user["id"]), include_completed=False)[:5],
        }

    @mcp.tool()
    def list_open_tasks(limit: int = 25) -> list[dict[str, Any]]:
        """List open tasks for the configured account, ordered by priority and due date."""
        database, user = _workspace()
        safe_limit = max(1, min(int(limit), 100))
        return database.list_tasks(int(user["id"]), include_completed=False)[:safe_limit]

    @mcp.tool()
    def create_task(
        title: str,
        priority: str = "Medium",
        estimated_minutes: int = 30,
        due_date: str | None = None,
        category: str = "General",
        notes: str = "",
    ) -> dict[str, Any]:
        """Create a task in the configured user’s DayCraft workspace."""
        if not title.strip():
            raise ValueError("Task title cannot be empty.")
        if due_date:
            date.fromisoformat(due_date)
        database, user = _workspace()
        return database.create_task(
            int(user["id"]),
            title,
            priority=_validated_priority(priority),
            estimated_minutes=max(5, min(int(estimated_minutes), 480)),
            due_date=due_date,
            category=category.strip() or "General",
            notes=notes,
        )

    @mcp.tool()
    def complete_task(task_id: int) -> dict[str, Any]:
        """Mark one task as complete only when it belongs to the configured account."""
        database, user = _workspace()
        task = database.get_task(int(user["id"]), int(task_id))
        if not task:
            raise ValueError("Task not found in the configured DayCraft workspace.")
        database.set_task_status(int(user["id"]), int(task_id), completed=True)
        return database.get_task(int(user["id"]), int(task_id)) or {}

    @mcp.tool()
    def list_agenda(day: str | None = None) -> list[dict[str, Any]]:
        """List the configured user’s DayCraft agenda for an ISO date (defaults to today)."""
        agenda_day = date.fromisoformat(day) if day else date.today()
        database, user = _workspace()
        return database.list_events(int(user["id"]), start_date=agenda_day, end_date=agenda_day)

    @mcp.tool()
    def create_daycraft_event(
        title: str,
        event_date: str,
        start_time: str,
        end_time: str,
        category: str = "General",
        notes: str = "",
    ) -> dict[str, Any]:
        """Create a fixed local DayCraft commitment without contacting an external service."""
        clean_title, parsed_date, clean_start, clean_end, clean_category, clean_notes = _validated_local_event(
            title, event_date, start_time, end_time, category, notes
        )
        database, user = _workspace()
        return database.create_event(
            int(user["id"]),
            clean_title,
            parsed_date,
            clean_start,
            clean_end,
            category=clean_category,
            notes=clean_notes,
            is_fixed=True,
            source="manual",
        )

    return mcp


def main() -> None:
    try:
        server = build_server()
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    server.run()


if __name__ == "__main__":
    main()
