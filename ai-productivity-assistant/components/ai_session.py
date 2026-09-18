"""Session-only AI provider configuration for DayCraft.

API keys entered in the browser are deliberately kept in Streamlit session
state.  They are never written to SQLite, exported with workspace data, or
added to a query string.  A deployment can instead supply one provider key via
its secret manager / environment.
"""

from __future__ import annotations

import streamlit as st

from services.ai import AIService

SESSION_API_KEY = "daycraft_ai_api_key"
SESSION_MODEL = "daycraft_ai_model"
SESSION_PROVIDER = "daycraft_ai_provider"

_PROVIDER_OPTIONS = {"Gemini": "gemini", "OpenAI": "openai"}
_DEFAULT_MODELS = {"gemini": "gemini-3.8-flash", "openai": "gpt-5.2"}


def clear_session_ai_configuration() -> None:
    """Forget an in-browser provider key, including it when the user signs out."""
    for state_key in (SESSION_API_KEY, SESSION_MODEL, SESSION_PROVIDER):
        st.session_state.pop(state_key, None)


def has_session_ai_configuration() -> bool:
    """Return whether this browser session explicitly supplied a provider key."""
    return bool(st.session_state.get(SESSION_API_KEY))


def current_ai_service() -> AIService:
    """Build an AI service from session credentials or deployment configuration."""
    return AIService(
        api_key=str(st.session_state.get(SESSION_API_KEY) or "").strip() or None,
        provider=str(st.session_state.get(SESSION_PROVIDER) or "").strip() or None,
        model=str(st.session_state.get(SESSION_MODEL) or "").strip() or None,
    )


def ai_provider_label(ai: AIService) -> str:
    """Present a friendly provider label without exposing model or key details."""
    provider = str(getattr(ai, "provider", "")).strip().lower()
    if provider == "gemini":
        return "Gemini"
    if provider == "openai":
        return "OpenAI"
    return "AI"


def _save_session_key(provider_label: str, api_key: str, model: str) -> None:
    provider = _PROVIDER_OPTIONS[provider_label]
    st.session_state[SESSION_PROVIDER] = provider
    st.session_state[SESSION_API_KEY] = api_key.strip()
    st.session_state[SESSION_MODEL] = model.strip() or _DEFAULT_MODELS[provider]


def render_ai_setup(
    *,
    key_prefix: str,
    heading: str = "Connect an AI planner",
    compact: bool = False,
) -> AIService:
    """Render a secure, reusable provider setup card and return current service.

    The daily-plan action is intentionally unavailable while this service is
    unconfigured.  Deployment keys are recognized without rendering a browser
    secret form; users may still choose a session-only override in Settings.
    """
    ai = current_ai_service()
    override_state_key = f"{key_prefix}_show_ai_session_override"
    show_session_override = bool(st.session_state.get(override_state_key))
    if ai.is_configured and not show_session_override:
        provider_label = ai_provider_label(ai)
        source = "this browser session" if has_session_ai_configuration() else "this deployment"
        with st.container(border=not compact):
            st.subheader(f"{provider_label} planner is ready", icon=":material/auto_awesome:")
            st.caption(
                f"DayCraft will use {provider_label} to prioritize your plan. The active key comes from {source}."
            )
            if has_session_ai_configuration():
                if st.button(
                    "Forget session key",
                    key=f"{key_prefix}_forget_ai_key",
                    icon=":material/key_off:",
                ):
                    clear_session_ai_configuration()
                    st.rerun()
            else:
                if st.button(
                    "Use a different session key",
                    key=f"{key_prefix}_override_ai_key",
                    icon=":material/key:",
                ):
                    st.session_state[override_state_key] = True
                    st.rerun()
        return ai

    with st.container(border=True):
        form_heading = "Use a session-only provider override" if show_session_override else heading
        st.subheader(form_heading, icon=":material/auto_awesome:")
        st.caption(
            "AI planning is required to craft a day. Choose Gemini or OpenAI, then add a key for this browser "
            "session. The key is never stored in DayCraft's database."
        )
        provider_label = st.segmented_control(
            "Planner provider",
            list(_PROVIDER_OPTIONS),
            default="Gemini",
            key=f"{key_prefix}_ai_provider_choice",
            width="stretch",
        )
        provider_label = str(provider_label or "Gemini")
        provider = _PROVIDER_OPTIONS[provider_label]
        with st.form(f"{key_prefix}_ai_session_key"):
            api_key = st.text_input(
                f"{provider_label} API key",
                type="password",
                autocomplete="new-password",
                placeholder="Paste a key for this session",
                help="This is held only in this browser session and is cleared when you sign out.",
            )
            with st.expander("Advanced model selection", expanded=False):
                model = st.text_input(
                    "Model",
                    value=_DEFAULT_MODELS[provider],
                    help="Keep the default unless your provider account supports a different compatible model.",
                )
            submitted = st.form_submit_button(
                f"Use {provider_label} for this session",
                type="primary",
                icon=":material/verified:",
                width="stretch",
            )
        if submitted:
            if not api_key.strip():
                st.error("Paste an API key to enable AI planning.")
            else:
                _save_session_key(provider_label, api_key, model)
                st.session_state.pop(override_state_key, None)
                st.rerun()
        provider_url = (
            "https://aistudio.google.com/app/apikey"
            if provider == "gemini"
            else "https://platform.openai.com/api-keys"
        )
        st.link_button(
            f"Get a {provider_label} API key",
            provider_url,
            icon=":material/open_in_new:",
            width="content",
        )
    return ai
