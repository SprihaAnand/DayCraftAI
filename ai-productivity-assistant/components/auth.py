"""Account forms and session bridge for the DayCraft UI."""

from __future__ import annotations

import streamlit as st

from components.theme import page_intro
from services.auth import AuthenticatedUser, AuthenticationError, AuthService
from services.database import Database


def active_user(database: Database) -> AuthenticatedUser | None:
    user_id = st.session_state.get("authenticated_user_id")
    if not user_id:
        return None
    record = database.get_user_by_id(int(user_id))
    if not record:
        st.session_state.pop("authenticated_user_id", None)
        return None
    return AuthenticatedUser.from_record(record)


def render_authentication(database: Database) -> AuthenticatedUser | None:
    user = active_user(database)
    if user:
        return user

    page_intro(
        "A calmer way to work",
        "Make space for what matters.",
        "Plan your real calendar, protect focus time, and keep your data with your account.",
    )
    sign_in, create_account = st.tabs(["Sign in", "Create account"])
    service = AuthService(database)

    with sign_in:
        with st.form("sign_in_form"):
            email = st.text_input("Email", placeholder="you@example.com", autocomplete="email")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            try:
                user = service.authenticate(email, password)
            except AuthenticationError as error:
                st.error(str(error))
            else:
                st.session_state.authenticated_user_id = user.id
                st.rerun()

    with create_account:
        with st.form("create_account_form"):
            display_name = st.text_input("First name or display name", autocomplete="name")
            email = st.text_input("Email", placeholder="you@example.com", autocomplete="email")
            password = st.text_input(
                "Password", type="password", autocomplete="new-password", help="10+ characters, with upper- and lower-case letters and a number."
            )
            submitted = st.form_submit_button("Create my workspace", type="primary", width="stretch")
        if submitted:
            try:
                user = service.register(email, display_name, password)
            except AuthenticationError as error:
                st.error(str(error))
            else:
                st.session_state.authenticated_user_id = user.id
                st.rerun()

    st.caption(
        "Your password is stored as a salted one-way hash. Workspace data is scoped to your account."
    )
    return None
