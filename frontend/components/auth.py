"""Auth gate — login/signup. Persists tokens to streamlit-local-storage for browser-side persistence."""
from __future__ import annotations

import httpx
import streamlit as st
from streamlit_local_storage import LocalStorage

import api_client

_LS_TOKEN = "strata.token"
_LS_REFRESH = "strata.refresh"


def _ls() -> LocalStorage:
    if "_ls" not in st.session_state:
        st.session_state["_ls"] = LocalStorage()
    return st.session_state["_ls"]


def _restore_tokens_from_storage() -> None:
    ls = _ls()
    tok = ls.getItem(_LS_TOKEN)
    ref = ls.getItem(_LS_REFRESH)
    if tok and not st.session_state.get("token"):
        st.session_state["token"] = tok
    if ref and not st.session_state.get("refresh_token"):
        st.session_state["refresh_token"] = ref


def _store_tokens(tok: str, ref: str) -> None:
    ls = _ls()
    ls.setItem(_LS_TOKEN, tok)
    ls.setItem(_LS_REFRESH, ref)
    st.session_state["token"] = tok
    st.session_state["refresh_token"] = ref


def _clear_tokens() -> None:
    ls = _ls()
    ls.deleteItem(_LS_TOKEN)
    ls.deleteItem(_LS_REFRESH)
    st.session_state.pop("token", None)
    st.session_state.pop("refresh_token", None)
    st.session_state.pop("user", None)


def auth_gate() -> bool:
    """Return True if the user is authenticated. Renders a login form if not."""
    _restore_tokens_from_storage()

    if st.session_state.get("token"):
        try:
            if not st.session_state.get("user"):
                st.session_state["user"] = api_client.me()
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                # Try refresh once.
                ref = st.session_state.get("refresh_token")
                if ref:
                    try:
                        pair = api_client.refresh_token(ref)
                        _store_tokens(pair["access_token"], pair["refresh_token"])
                        st.session_state["user"] = api_client.me()
                        return True
                    except httpx.HTTPStatusError:
                        pass
            _clear_tokens()
        except Exception:
            _clear_tokens()

    # Render login form.
    st.markdown(
        """
        <div class='strata-strip'>
            <span class='strata-brand'>◰ STRATA</span>
            <span class='strata-tag'>crypto market-structure analyst</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("##")
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        tab_login, tab_signup = st.tabs(["Sign in", "Create account"])
        with tab_login:
            with st.form("login", clear_on_submit=False, border=True):
                email = st.text_input("Email", autocomplete="username")
                pw = st.text_input("Password", type="password", autocomplete="current-password")
                if st.form_submit_button("Sign in", type="primary", use_container_width=True):
                    try:
                        pair = api_client.login(email, pw)
                        _store_tokens(pair["access_token"], pair["refresh_token"])
                        st.session_state["user"] = api_client.me()
                        st.rerun()
                    except httpx.HTTPStatusError as exc:
                        st.error(exc.response.json().get("detail", "login failed"))
        with tab_signup:
            with st.form("signup", clear_on_submit=False, border=True):
                email2 = st.text_input("Email ", autocomplete="email")
                name2 = st.text_input("Full name (optional)")
                pw2 = st.text_input("Password (≥12 chars)", type="password", autocomplete="new-password")
                if st.form_submit_button("Create account", type="primary", use_container_width=True):
                    try:
                        pair = api_client.signup(email2, pw2, name2)
                        _store_tokens(pair["access_token"], pair["refresh_token"])
                        st.session_state["user"] = api_client.me()
                        st.rerun()
                    except httpx.HTTPStatusError as exc:
                        st.error(exc.response.json().get("detail", "signup failed"))
    return False


def render_account_widget() -> None:
    user = st.session_state.get("user") or {}
    name = user.get("full_name") or user.get("email", "")
    role = user.get("role", "viewer")
    cols = st.columns([0.7, 0.3])
    with cols[0]:
        st.markdown(f"<span class='num'>{name}</span> · <span class='pill pill-mute'>{role}</span>",
                    unsafe_allow_html=True)
    with cols[1]:
        if st.button("Sign out", use_container_width=True):
            _clear_tokens()
            st.rerun()
