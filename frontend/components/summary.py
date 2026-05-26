"""AI briefing panel."""
from __future__ import annotations

import streamlit as st

import api_client


def render_summary() -> None:
    symbol = st.session_state.symbol
    interval = st.session_state.interval

    cols = st.columns([0.7, 0.3])
    with cols[0]:
        st.markdown("### Analyst")
    with cols[1]:
        if st.button("↻  Refresh", use_container_width=True):
            try:
                with st.spinner("running multi-agent pipeline…"):
                    st.session_state.briefing = api_client.briefing(symbol, interval)
            except Exception as exc:
                st.error(f"briefing failed: {exc}")

    if st.session_state.briefing is None:
        try:
            existing = api_client.latest_briefing(symbol, interval)
            st.session_state.briefing = existing
        except Exception:
            existing = None

    briefing = st.session_state.briefing
    if not briefing:
        st.caption("No briefing yet. Click **Refresh** to generate one.")
        return

    # Top-of-panel meta row.
    meta = st.columns(3)
    meta[0].markdown(f"<div class='strata-tag'>trend</div><b class='num'>{briefing.get('current_trend', '—').upper()}</b>",
                      unsafe_allow_html=True)
    meta[1].markdown(f"<div class='strata-tag'>MTF</div><b class='num'>{briefing.get('mtf_score', 0):+.2f}</b>",
                      unsafe_allow_html=True)
    meta[2].markdown(f"<div class='strata-tag'>iterations</div><b class='num'>{briefing.get('iterations', 1)}</b>",
                      unsafe_allow_html=True)
    st.markdown("")
    st.markdown(briefing.get("narrative_markdown", "*(empty)*"))
