"""Plotly candlestick chart with structure overlays — the workspace centerpiece."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import api_client

# Color palette — terminal aesthetic.
COLOR_UP        = "#3fb950"
COLOR_DOWN      = "#f85149"
COLOR_GRID      = "#1c2331"
COLOR_PAPER     = "#0b0f17"
COLOR_INK       = "#d6dde7"
COLOR_MUTE      = "#8b949e"
COLOR_BOS_UP    = "#58a6ff"
COLOR_BOS_DOWN  = "#bc8cff"
COLOR_CHOCH_UP  = "#3fb950"
COLOR_CHOCH_DOWN = "#f85149"
COLOR_OB_BULL   = "rgba( 63, 185, 80, 0.18)"
COLOR_OB_BEAR   = "rgba(248,  81, 73, 0.18)"
COLOR_FVG_BULL  = "rgba( 88, 166, 255, 0.16)"
COLOR_FVG_BEAR  = "rgba(188, 140, 255, 0.16)"


def render_chart_workspace() -> None:
    tabs = st.tabs(["📈 Chart", "🧭 Multi-TF", "🧪 Backtest"])
    with tabs[0]:
        _render_main_chart()
    with tabs[1]:
        _render_mtf_panel()
    with tabs[2]:
        _render_backtest_panel()


def _render_main_chart() -> None:
    symbol = st.session_state.symbol
    interval = st.session_state.interval
    lookback = int(st.session_state.lookback)

    try:
        candles_resp = api_client.candles(symbol, interval, lookback)
        structure_resp = api_client.structure(symbol, interval, lookback)
    except Exception as exc:
        st.error(f"Failed to load chart data: {exc}")
        return

    candles = candles_resp.get("candles", [])
    if not candles:
        st.warning(f"No candles for {symbol}:{interval}. Trigger a backfill from the API.")
        return

    df = pd.DataFrame(candles)
    df["opened_at"] = pd.to_datetime(df["opened_at"])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col])

    # ── Top metrics row ----------------------------------------------------
    last_close = float(df["close"].iloc[-1])
    first_close = float(df["close"].iloc[0])
    pct_change = (last_close - first_close) / first_close * 100 if first_close else 0.0
    range_low, range_high = float(df["low"].min()), float(df["high"].max())
    current_trend = structure_resp.get("current_trend", "undefined")

    m = st.columns(5)
    m[0].metric("Last", f"{last_close:,.2f}", f"{pct_change:+.2f}%")
    m[1].metric("Range high", f"{range_high:,.2f}")
    m[2].metric("Range low",  f"{range_low:,.2f}")
    m[3].metric("Swings",     len(structure_resp.get("swings", [])))
    m[4].metric("Events",     len(structure_resp.get("events", [])))

    trend_pill = {"up": "pill-up", "down": "pill-down"}.get(current_trend, "pill-mute")
    st.markdown(f"<span class='pill {trend_pill}'>trend: {current_trend.upper()}</span>",
                unsafe_allow_html=True)

    # ── Plotly chart ------------------------------------------------------
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["opened_at"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN,
        increasing_fillcolor=COLOR_UP, decreasing_fillcolor=COLOR_DOWN,
        name=symbol, showlegend=False,
    ))

    # Wyckoff phase bands (semi-transparent vertical rectangles).
    if st.session_state.show_wyckoff:
        for w in structure_resp.get("wyckoff", []):
            si, ei = int(w["start_index"]), int(w["end_index"])
            if ei >= len(df) or si < 0:
                continue
            color = {
                "accumulation": "rgba(63,185,80,0.05)",
                "markup":       "rgba(63,185,80,0.10)",
                "distribution": "rgba(248,81,73,0.05)",
                "markdown":     "rgba(248,81,73,0.10)",
            }.get(w["phase"], "rgba(110,118,129,0.05)")
            fig.add_vrect(
                x0=df["opened_at"].iloc[si], x1=df["opened_at"].iloc[ei],
                fillcolor=color, line_width=0,
                annotation_text=w["phase"], annotation_position="top left",
                annotation=dict(font_size=10, font_color=COLOR_MUTE),
            )

    # Order blocks (semi-transparent rectangles).
    if st.session_state.show_order_blocks:
        for ob in structure_resp.get("order_blocks", []):
            x0 = df["opened_at"].iloc[ob["index"]]
            x1 = df["opened_at"].iloc[-1]
            color = COLOR_OB_BULL if ob["bullish"] else COLOR_OB_BEAR
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=ob["low"], y1=ob["high"],
                          fillcolor=color, line=dict(width=0), layer="below")

    # FVGs.
    if st.session_state.show_fvgs:
        for fvg in structure_resp.get("fvgs", []):
            i = int(fvg["index"])
            if i >= len(df):
                continue
            x0 = df["opened_at"].iloc[max(0, i - 2)]
            x1 = df["opened_at"].iloc[-1]
            color = COLOR_FVG_BULL if fvg["bullish"] else COLOR_FVG_BEAR
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=fvg["bottom"], y1=fvg["top"],
                          fillcolor=color, line=dict(width=0), layer="below")

    # Swing pivots.
    if st.session_state.show_swings:
        swings = structure_resp.get("swings", [])
        sh_x = [s["timestamp"] for s in swings if s["kind"] == "swing_high"]
        sh_y = [s["price"]     for s in swings if s["kind"] == "swing_high"]
        sl_x = [s["timestamp"] for s in swings if s["kind"] == "swing_low"]
        sl_y = [s["price"]     for s in swings if s["kind"] == "swing_low"]
        fig.add_trace(go.Scatter(x=sh_x, y=sh_y, mode="markers", marker_symbol="triangle-down",
                                  marker_size=8, marker_color=COLOR_DOWN, name="swing high", showlegend=False))
        fig.add_trace(go.Scatter(x=sl_x, y=sl_y, mode="markers", marker_symbol="triangle-up",
                                  marker_size=8, marker_color=COLOR_UP, name="swing low", showlegend=False))

    # BoS / CHoCH horizontal break levels with annotation.
    if st.session_state.show_events:
        for ev in structure_resp.get("events", []):
            color = {"bos_up": COLOR_BOS_UP, "bos_down": COLOR_BOS_DOWN,
                     "choch_up": COLOR_CHOCH_UP, "choch_down": COLOR_CHOCH_DOWN}.get(ev["kind"], COLOR_MUTE)
            i = int(ev["index"])
            if i >= len(df):
                continue
            fig.add_hline(
                y=ev["price"], line_color=color, line_dash="dot", line_width=1,
                annotation_text=ev["kind"].replace("_", " "),
                annotation_position="right",
                annotation=dict(font_size=10, font_color=color),
            )

    # Layout — terminal feel.
    fig.update_layout(
        height=620, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor=COLOR_PAPER, plot_bgcolor=COLOR_PAPER,
        font=dict(color=COLOR_INK, family="ui-monospace, Menlo, Consolas, monospace", size=11),
        xaxis=dict(rangeslider=dict(visible=False), gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID,
                    showspikes=True, spikecolor=COLOR_MUTE, spikethickness=1),
        yaxis=dict(gridcolor=COLOR_GRID, zerolinecolor=COLOR_GRID,
                    showspikes=True, spikecolor=COLOR_MUTE, spikethickness=1),
        hovermode="x unified", showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": True})


def _render_mtf_panel() -> None:
    symbol = st.session_state.symbol
    try:
        data = api_client.mtf(symbol)
    except Exception as exc:
        st.error(f"MTF query failed: {exc}")
        return
    cols = st.columns(len(data["per_tf_trend"]) + 1)
    cols[0].metric("Coherence", f"{data['score']:+.2f}", help="-1 fully opposed · 0 mixed · +1 aligned")
    for (tf, trend), col in zip(data["per_tf_trend"].items(), cols[1:]):
        col.metric(tf, trend.upper())


def _render_backtest_panel() -> None:
    st.markdown("**Backtest snapshot** — nightly per-detector hit-rate / drawdown / risk-reward (writes to `BacktestRun`).")
    st.info("Snapshots are produced by the `nightly_backtest_snapshot` Celery task. Run `make backtest` for an on-demand pass.", icon="🧪")
