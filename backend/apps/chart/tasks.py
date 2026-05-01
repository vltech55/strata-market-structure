"""Celery tasks: periodic structure recompute + nightly backtest snapshot."""
from __future__ import annotations

import logging

import pandas as pd
from celery import shared_task

from apps.chart.backtest import run_backtest
from apps.chart.models import BacktestRun
from apps.chart.services import candles_to_dataframe, run_and_persist
from apps.stock.models import Interval, Symbol, SymbolStatus

log = logging.getLogger("strata.tasks.chart")


@shared_task(name="apps.chart.tasks.recompute_active_symbols", acks_late=True)
def recompute_active_symbols(intervals: list[str] | None = None) -> dict[str, int]:
    intervals = intervals or ["1h", "4h"]
    out: dict[str, int] = {}
    for symbol in Symbol.objects.filter(status=SymbolStatus.ACTIVE).iterator():
        for code in intervals:
            try:
                run = run_and_persist(symbol, Interval(code))
                out[f"{symbol.code}:{code}"] = run.n_events
            except Exception:
                log.exception("structure recompute failed", extra={"symbol": symbol.code, "interval": code})
    return out


@shared_task(name="apps.chart.tasks.nightly_backtest_snapshot", acks_late=True)
def nightly_backtest_snapshot(intervals: list[str] | None = None) -> int:
    """Run the backtest on every active symbol/interval, persist per-detector stats."""
    intervals = intervals or ["1h", "4h"]
    persisted = 0
    for symbol in Symbol.objects.filter(status=SymbolStatus.ACTIVE).iterator():
        for code in intervals:
            df = candles_to_dataframe(symbol, Interval(code), limit=3000)
            if df.empty:
                continue
            try:
                stats = run_backtest(df)
            except Exception:
                log.exception("backtest failed", extra={"symbol": symbol.code, "interval": code})
                continue
            for detector, s in stats.items():
                if s.n_signals == 0:
                    continue
                BacktestRun.objects.create(
                    symbol=symbol, interval=code, git_sha=s.git_sha, detector=detector,
                    n_signals=s.n_signals, hit_rate=s.hit_rate, avg_pnl_pct=s.avg_pnl_pct,
                    max_drawdown_pct=s.max_drawdown_pct, risk_reward=s.risk_reward,
                )
                persisted += 1
    return persisted
