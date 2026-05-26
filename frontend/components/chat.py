"""Chat panel — grounded Q&A with structure context."""
from __future__ import annotations

import streamlit as st

import api_client


def render_chat() -> None:
    st.markdown("### Ask")
    st.caption(f"Grounded on **{st.session_state.symbol} {st.session_state.interval}** structure.")

    # History
    for msg in st.session_state.chat_history[-20:]:
        css = "chat-msg-user" if msg["role"] == "user" else "chat-msg-assistant"
        st.markdown(f"<div class='{css}'>{msg['content']}</div>", unsafe_allow_html=True)

    # Input
    q = st.chat_input("e.g. 'Why is the trend up?' · 'When was the most recent CHoCH?'")
    if q:
        st.session_state.chat_history.append({"role": "user", "content": q})
        try:
            with st.spinner("thinking…"):
                resp = api_client.ask(q, symbol=st.session_state.symbol, interval=st.session_state.interval)
                st.session_state.chat_history.append({"role": "assistant", "content": resp["content"]})
        except Exception as exc:
            st.session_state.chat_history.append({"role": "assistant", "content": f"_(error: {exc})_"})
        st.rerun()
