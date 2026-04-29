"""Glue between Django ORM and the pandas structure detectors."""
from __future__ import annotations

import logging
import subprocess
from dataclasses import asdict
from decimal import Decimal

import pandas as pd

from apps.chart.models import DetectionRun
from apps.chart.structure import StructureReport, analyse, multi_timeframe_coherence
from apps.stock.models import Candle, Interval, Symbol

log = logging.getLogger("strata.chart")


def candles_to_dataframe(symbol: Symbol, interval: Interval, *, limit: int = 1000) -> pd.DataFrame:
    """Pull the last `limit` candles for (symbol, interval) into a DatetimeIndex'd OHLCV frame."""
    rows = list(
        Candle.objects.for_symbol(symbol, interval).latest_n(limit).values(
            "opened_at", "open", "high", "low", "close", "volume"
        )
    )
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows).rename(columns={"opened_at": "ts"})
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.set_index("ts").sort_index()
    # Cast Decimals to float for pandas/numpy math. Use float64 — sufficient precision for prices.
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype("float64")
    return df


def run_and_persist(symbol: Symbol, interval: Interval, *, lookback: int = 1000) -> DetectionRun:
    df = candles_to_dataframe(symbol, interval, limit=lookback)
    if df.empty:
        raise RuntimeError(f"No candles for {symbol.code}:{interval.value}")
    report = analyse(df)
    return DetectionRun.objects.create(
        symbol=symbol,
        interval=interval.value,
        git_sha=_git_sha(),
        config_json={"lookback": lookback, "left": 3, "right": 3},
        report_json=_report_to_json(report),
        n_swings=len(report.swings),
        n_events=len(report.events),
        n_obs=len(report.order_blocks),
        n_fvgs=len(report.fvgs),
        current_trend=report.current_trend,
    )


def multi_tf_score(symbol: Symbol, *, intervals: list[str] = ["1h", "4h", "1d"]) -> dict:
    """Compute a coherence score over the requested timeframes."""
    reports: dict[str, StructureReport] = {}
    for code in intervals:
        df = candles_to_dataframe(symbol, Interval(code), limit=500)
        if not df.empty:
            reports[code] = analyse(df)
    return {
        "score": multi_timeframe_coherence(reports),
        "per_tf_trend": {tf: r.current_trend for tf, r in reports.items()},
    }


def _report_to_json(report: StructureReport) -> dict:
    return {
        "swings": [asdict(s) | {"kind": s.kind.value, "timestamp": s.timestamp.isoformat()} for s in report.swings],
        "events": [
            asdict(e) | {"kind": e.kind.value, "timestamp": e.timestamp.isoformat()}
            for e in report.events
        ],
        "order_blocks": [asdict(o) | {"timestamp": o.timestamp.isoformat()} for o in report.order_blocks],
        "fvgs": [asdict(f) | {"timestamp": f.timestamp.isoformat()} for f in report.fvgs],
        "wyckoff": [asdict(w) | {"phase": w.phase.value} for w in report.wyckoff],
        "current_trend": report.current_trend,
    }


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd="/app", text=True).strip()
    except Exception:
        return "unknown"
