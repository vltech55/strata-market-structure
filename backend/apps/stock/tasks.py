"""Celery tasks for OHLCV ingestion."""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task

from apps.stock.ingestion import ingest_recent
from apps.stock.models import Interval, Symbol, SymbolStatus

log = logging.getLogger("strata.tasks.stock")


@shared_task(
    name="apps.stock.tasks.ingest_active_symbols",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def ingest_active_symbols(self, intervals: list[str] | None = None) -> dict[str, int]:
    """Refresh recent candles for every active symbol on the given intervals.

    Default intervals (1h, 4h) are the ones the structure-detector cares about most.
    """
    intervals = intervals or ["1h", "4h"]
    summary: dict[str, int] = {}
    for symbol in Symbol.objects.filter(status=SymbolStatus.ACTIVE).iterator():
        for interval_code in intervals:
            interval = Interval(interval_code)
            try:
                n = asyncio.run(ingest_recent(symbol, interval, lookback_bars=300))
                summary[f"{symbol.code}:{interval_code}"] = n
            except Exception:
                log.exception("ingest failed", extra={"symbol": symbol.code, "interval": interval_code})
    return summary


@shared_task(name="apps.stock.tasks.ingest_one")
def ingest_one(symbol_id: str, interval: str, *, lookback_bars: int = 500) -> int:
    """Refresh one (symbol, interval) — used by the chart recompute pipeline."""
    symbol = Symbol.objects.get(id=symbol_id)
    return asyncio.run(ingest_recent(symbol, Interval(interval), lookback_bars=lookback_bars))
