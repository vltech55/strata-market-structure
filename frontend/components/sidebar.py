"""Sidebar — watchlist, symbol & timeframe pickers, overlay toggles, account widget."""
from __future__ import annotations

import streamlit as st

from components.auth import render_account_widget
from state import INTERVALS, WATCHLIST_DEFAULT


def render_sidebar() -> None:
    st.markdown("<div class='strata-brand'>◰ STRATA</div><div class='strata-tag'>v0.1 · vltech55</div>",
                unsafe_allow_html=True)
    st.markdown("---")

    # ── Symbol + interval --------------------------------------------------
    st.markdown("**Instrument**")
    new_symbol = st.text_input("Symbol", value=st.session_state.symbol, label_visibility="collapsed").upper().strip()
    if new_symbol and new_symbol != st.session_state.symbol:
        st.session_state.symbol = new_symbol

    interval_idx = INTERVALS.index(st.session_state.interval) if st.session_state.interval in INTERVALS else 3
    st.session_state.interval = st.selectbox("Timeframe", INTERVALS, index=interval_idx, label_visibility="collapsed")
    st.session_state.lookback = st.slider("Lookback (bars)", 200, 3000, st.session_state.lookback, step=100)

    # ── Watchlist ---------------------------------------------------------
    st.markdown("---")
    st.markdown("**Watchlist**")
    for code in st.session_state.watchlist:
        cols = st.columns([0.8, 0.2])
        with cols[0]:
            if st.button(code, key=f"wl-{code}", use_container_width=True,
                         type=("primary" if code == st.session_state.symbol else "secondary")):
                st.session_state.symbol = code
                st.rerun()
        with cols[1]:
            if st.button("×", key=f"wl-rm-{code}", help="Remove"):
                st.session_state.watchlist = [c for c in st.session_state.watchlist if c != code]
                st.rerun()

    add_col = st.columns([0.7, 0.3])
    with add_col[0]:
        new_wl = st.text_input("Add ticker", key="add-wl", label_visibility="collapsed",
                                placeholder="add ticker…").upper().strip()
    with add_col[1]:
        if st.button("Add", use_container_width=True) and new_wl:
            if new_wl not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_wl)
            st.rerun()

    # ── Overlays ---------------------------------------------------------
    st.markdown("---")
    st.markdown("**Chart overlays**")
    st.session_state.show_swings = st.checkbox("Swing pivots", st.session_state.show_swings)
    st.session_state.show_events = st.checkbox("BoS / CHoCH lines", st.session_state.show_events)
    st.session_state.show_order_blocks = st.checkbox("Order blocks", st.session_state.show_order_blocks)
    st.session_state.show_fvgs = st.checkbox("Fair-value gaps", st.session_state.show_fvgs)
    st.session_state.show_wyckoff = st.checkbox("Wyckoff bands", st.session_state.show_wyckoff)

    # ── Account ---------------------------------------------------------
    st.markdown("---")
    render_account_widget()
