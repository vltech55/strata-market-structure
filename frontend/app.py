"""Strata — Streamlit workspace (production trading-terminal aesthetic).

Layout:
  ┌────────────────────────────────────────────────────────────────────────┐
  │  HEADER  — brand · API status · symbol search · account                 │
  ├──────────────┬───────────────────────────────────────────┬─────────────┤
  │              │                                           │             │
  │  SIDEBAR     │   CHART WORKSPACE                          │  ANALYST    │
  │  ───────     │   ───────────────                          │  ─────────  │
  │  watchlist   │   Plotly candlestick + overlays:           │  AI         │
  │  TF picker   │     swings · BoS · CHoCH · Wyckoff bands  │  briefing   │
  │  detector    │     order blocks · FVGs                    │             │
  │  settings    │                                            │  chat       │
  │              │   tabs: Chart · MTF · Backtest             │             │
  │              │                                            │             │
  └──────────────┴───────────────────────────────────────────┴─────────────┘
"""
from __future__ import annotations

import os

import streamlit as st

from components.auth import auth_gate, render_account_widget
from components.chart import render_chart_workspace
from components.header import render_header
from components.sidebar import render_sidebar
from components.summary import render_summary
from components.chat import render_chat
from state import init_state

# ──────────────────────────────────────────────────────────────────────────────
# Page configuration — wide, dark, terminal feel.
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Strata — Market-Structure Analyst",
    page_icon="◰",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Strata — production crypto market-structure analyst",
    },
)

# Inject custom CSS for the terminal aesthetic (dense layout, monospace numerics,
# dark surfaces, accent green/red for bullish/bearish).
_CSS = """
<style>
/* Dark, dense workspace */
[data-testid="stAppViewContainer"] { background-color: #0b0f17; color: #d6dde7; }
[data-testid="stSidebar"]          { background-color: #0e131c; border-right: 1px solid #1c2331; }
[data-testid="stHeader"]           { background: transparent; }
.main .block-container             { padding-top: 0.75rem; padding-bottom: 0.5rem; max-width: 100%; }

/* Brand strip */
.strata-strip {
    display: flex; align-items: center; gap: 16px;
    padding: 6px 14px; background: linear-gradient(90deg, #0e131c 0%, #131a26 100%);
    border-bottom: 1px solid #1c2331; font-family: ui-monospace, Menlo, Consolas, monospace;
}
.strata-brand { color: #58a6ff; font-weight: 700; letter-spacing: 0.12em; }
.strata-tag   { color: #6e7681; font-size: 11px; }

/* Status pills */
.pill { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; letter-spacing:0.03em; }
.pill-up   { background: rgba( 56,139,80,0.18); color:#3fb950; border:1px solid rgba(63,185,80,0.35); }
.pill-down { background: rgba(248, 81,73,0.18); color:#f85149; border:1px solid rgba(248,81,73,0.35); }
.pill-mute { background: rgba(110,118,129,0.18); color:#8b949e; border:1px solid rgba(110,118,129,0.35); }

/* Numerics — tabular-aligned monospace */
.metric-num, .num { font-family: ui-monospace, Menlo, Consolas, monospace; font-variant-numeric: tabular-nums; }

/* Tighter Streamlit metrics */
[data-testid="stMetricValue"] { font-family: ui-monospace, Menlo, Consolas, monospace; }
[data-testid="stMetricDelta"] svg { display: none; }

/* Tabs */
[data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #1c2331; }
[data-baseweb="tab"]      { background: transparent !important; color: #8b949e; padding: 6px 12px; }
[data-baseweb="tab"][aria-selected="true"] { color: #58a6ff; border-bottom: 2px solid #58a6ff; }

/* Chat bubbles */
.chat-msg-user      { background: #131a26; border-left: 3px solid #58a6ff; padding: 8px 10px; margin: 6px 0; border-radius: 4px; }
.chat-msg-assistant { background: #0f1521; border-left: 3px solid #3fb950; padding: 8px 10px; margin: 6px 0; border-radius: 4px; }

/* Hide Streamlit's branding for a polished terminal feel */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header[data-testid="stHeader"] { height: 0; }

/* Scrollbar polish */
::-webkit-scrollbar           { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb     { background: #1c2331; border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: #2a3548; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# State + auth gate
# ──────────────────────────────────────────────────────────────────────────────
init_state()
if not auth_gate():
    st.stop()

# ──────────────────────────────────────────────────────────────────────────────
# Layout
# ──────────────────────────────────────────────────────────────────────────────
render_header()

with st.sidebar:
    render_sidebar()

workspace_col, analyst_col = st.columns([0.66, 0.34], gap="medium")

with workspace_col:
    render_chart_workspace()

with analyst_col:
    render_summary()
    st.markdown("---")
    render_chat()
