"""Backward-compatible helpers for older imports.

The app itself uses :mod:`services.ai`. These helpers deliberately never raise
at import time when a Gemini key is absent.
"""

from __future__ import annotations

from services.ai import AIConfigurationError, AIService


def _respond(prompt: str, fallback: str) -> str:
    try:
        return AIService().generate(prompt, fallback).content
    except AIConfigurationError:
        # These legacy helpers are not DayCraft's daily-plan action. Preserve
        # their import-safe compatibility while the product itself requires AI
        # before it can craft a time-blocked daily plan.
        return fallback


def generate_schedule(prompt: str) -> str:
    return _respond(
        f"Create a realistic, time-blocked daily productivity schedule for:\n{prompt}",
        "Create a task in DayCraft and use Today to place it into a real available time slot.",
    )


def analyze_productivity(tasks_completed: str, time_spent: str) -> str:
    return _respond(
        f"Offer a concise productivity reflection. Completed: {tasks_completed}\nTime: {time_spent}",
        "Record a daily check-in in Progress to track patterns over time.",
    )


def suggest_improvements(current_schedule: str, feedback: str) -> str:
    return _respond(
        f"Suggest practical schedule improvements. Schedule: {current_schedule}\nFeedback: {feedback}",
        "Review your plan’s task estimates, then leave a buffer between fixed commitments.",
    )


def prioritize_tasks(task_list: str) -> str:
    return _respond(
        f"Prioritize these tasks and explain the tradeoffs briefly:\n{task_list}",
        "Use High for urgent, high-impact work; Medium for important work; Low for optional work.",
    )


def generate_focus_session(duration: int, task_type: str) -> str:
    return _respond(
        f"Create a {duration}-minute focus session for: {task_type}",
        f"Set a {duration}-minute timer, remove distractions, and finish with a two-minute review.",
    )


def create_weekly_plan(goals: str, constraints: str) -> str:
    return _respond(
        f"Create a realistic weekly productivity plan. Goals: {goals}\nConstraints: {constraints}",
        "Choose three outcomes, place them in open calendar gaps, and review them on Friday.",
    )


if __name__ == "__main__":
    # Existing deployments used ``agent.py`` as their Streamlit entry point.
    # Keep those URLs working while the canonical entry point remains app.py.
    from app import main

    main()
