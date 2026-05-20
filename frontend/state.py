"""Session-state helpers and constants for the Streamlit app."""
from __future__ import annotations

import streamlit as st

INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
DEFAULT_INTERVAL = "1h"

WATCHLIST_DEFAULT = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ARBUSDT", "OPUSDT", "AVAXUSDT", "BNBUSDT", "LINKUSDT"]


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("token", None)
    ss.setdefault("refresh_token", None)
    ss.setdefault("user", None)

    ss.setdefault("symbol", "BTCUSDT")
    ss.setdefault("interval", DEFAULT_INTERVAL)
    ss.setdefault("lookback", 500)
    ss.setdefault("watchlist", WATCHLIST_DEFAULT)

    ss.setdefault("show_swings", True)
    ss.setdefault("show_events", True)
    ss.setdefault("show_order_blocks", True)
    ss.setdefault("show_fvgs", True)
    ss.setdefault("show_wyckoff", True)

    ss.setdefault("briefing", None)
    ss.setdefault("chat_history", [])
    ss.setdefault("active_session_id", None)
