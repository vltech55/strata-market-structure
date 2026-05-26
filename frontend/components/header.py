"""Header strip — brand · API health · current symbol · timeframe · account."""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st


def render_header() -> None:
    user = st.session_state.get("user") or {}
    symbol = st.session_state.get("symbol", "—")
    interval = st.session_state.get("interval", "—")
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    st.markdown(
        f"""
        <div class='strata-strip'>
            <span class='strata-brand'>◰ STRATA</span>
            <span class='strata-tag'>market-structure analyst</span>
            <span style='flex:1'></span>
            <span class='num'>{symbol}</span>
            <span class='pill pill-mute'>{interval}</span>
            <span class='pill pill-up'>● live</span>
            <span class='num strata-tag'>{now}</span>
            <span style='width:14px'></span>
            <span class='num strata-tag'>{user.get('email', '')}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
