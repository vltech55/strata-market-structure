"""Backtest harness — replays the structure detectors over historical OHLCV and
produces per-detector hit-rate / drawdown / risk-reward stats.

This is the harness that lets you A/B detector tweaks objectively. Persists results
to the `BacktestRun` model (see models.py), tagged with the git SHA so commits are
comparable in the dashboard.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from apps.chart.structure import (
    StructureEvent,
    StructureEventKind,
    analyse,
)

log = logging.getLogger("strata.backtest")


@dataclass(frozen=True)
class TradeOutcome:
    entry_index: int
    entry_price: float
    exit_index: int
    exit_price: float
    pnl_pct: float
    hit_take_profit: bool


@dataclass(frozen=True)
class BacktestStats:
    detector: str
    n_signals: int
    n_wins: int
    hit_rate: float
    avg_pnl_pct: float
    median_pnl_pct: float
    max_drawdown_pct: float
    risk_reward: float       # avg-win / abs(avg-loss)
    git_sha: str


def run_backtest(
    df: pd.DataFrame,
    *,
    take_profit_pct: float = 0.02,
    stop_loss_pct: float = 0.01,
    max_bars_held: int = 50,
) -> dict[str, BacktestStats]:
    """For every structural event in the report, simulate a trade entered at that bar's
    close with a fixed TP/SL. Returns one BacktestStats per event-kind."""
    report = analyse(df)
    close = df["close"].to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()

    by_kind: dict[str, list[TradeOutcome]] = {k.value: [] for k in StructureEventKind}
    for ev in report.events:
        outcome = _simulate_trade(
            close, high, low, ev,
            take_profit_pct=take_profit_pct, stop_loss_pct=stop_loss_pct, max_bars_held=max_bars_held,
        )
        if outcome is not None:
            by_kind[ev.kind.value].append(outcome)

    sha = _git_sha()
    stats: dict[str, BacktestStats] = {}
    for detector, outcomes in by_kind.items():
        stats[detector] = _summarise(detector, outcomes, sha)
    return stats


def _simulate_trade(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    ev: StructureEvent,
    *,
    take_profit_pct: float,
    stop_loss_pct: float,
    max_bars_held: int,
) -> TradeOutcome | None:
    entry_i = ev.index
    if entry_i + 1 >= len(close):
        return None
    entry_px = float(close[entry_i])
    bullish = ev.kind in (StructureEventKind.BOS_UP, StructureEventKind.CHOCH_UP)
    tp = entry_px * (1 + take_profit_pct) if bullish else entry_px * (1 - take_profit_pct)
    sl = entry_px * (1 - stop_loss_pct) if bullish else entry_px * (1 + stop_loss_pct)
    end = min(entry_i + max_bars_held + 1, len(close))
    for i in range(entry_i + 1, end):
        if bullish:
            if low[i] <= sl:
                return TradeOutcome(entry_i, entry_px, i, float(sl), -stop_loss_pct, hit_take_profit=False)
            if high[i] >= tp:
                return TradeOutcome(entry_i, entry_px, i, float(tp), take_profit_pct, hit_take_profit=True)
        else:
            if high[i] >= sl:
                return TradeOutcome(entry_i, entry_px, i, float(sl), -stop_loss_pct, hit_take_profit=False)
            if low[i] <= tp:
                return TradeOutcome(entry_i, entry_px, i, float(tp), take_profit_pct, hit_take_profit=True)
    # Closed at end of window at market.
    final_px = float(close[end - 1])
    pnl = (final_px - entry_px) / entry_px * (1 if bullish else -1)
    return TradeOutcome(entry_i, entry_px, end - 1, final_px, pnl, hit_take_profit=False)


def _summarise(detector: str, outcomes: list[TradeOutcome], sha: str) -> BacktestStats:
    if not outcomes:
        return BacktestStats(detector, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, sha)
    pnl = np.array([o.pnl_pct for o in outcomes])
    wins = pnl > 0
    cum = np.cumprod(1.0 + pnl) - 1.0
    running_max = np.maximum.accumulate(cum)
    drawdown = float(np.min(cum - running_max))
    avg_win = float(pnl[wins].mean()) if wins.any() else 0.0
    avg_loss = float(pnl[~wins].mean()) if (~wins).any() else 0.0
    rr = (avg_win / abs(avg_loss)) if avg_loss != 0 else 0.0
    return BacktestStats(
        detector=detector,
        n_signals=len(outcomes),
        n_wins=int(wins.sum()),
        hit_rate=float(wins.mean()),
        avg_pnl_pct=float(pnl.mean()),
        median_pnl_pct=float(np.median(pnl)),
        max_drawdown_pct=drawdown,
        risk_reward=rr,
        git_sha=sha,
    )


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd="/app", text=True).strip()
    except Exception:
        return "unknown"
