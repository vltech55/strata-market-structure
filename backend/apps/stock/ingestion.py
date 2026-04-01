"""OHLCV ingestion service — page through Bybit and upsert candles."""
from __future__ import annotations

import logging
from datetime import datetime, timezone as tz

from django.db import transaction

from apps.stock.bybit import BybitClient, Kline
from apps.stock.models import Candle, Interval, Symbol

log = logging.getLogger("strata.ingestion")


async def ingest_recent(symbol: Symbol, interval: Interval, *, lookback_bars: int = 500) -> int:
    """Fetch and upsert the most recent `lookback_bars` for (symbol, interval)."""
    client = BybitClient()
    klines = await client.fetch_klines(symbol.code, interval.value, limit=lookback_bars)
    if not klines:
        return 0
    return await _upsert(symbol, interval, klines)


async def backfill(
    symbol: Symbol,
    interval: Interval,
    *,
    start: datetime,
    end: datetime | None = None,
) -> int:
    """Backfill historical candles from `start` to `end` (default = now), paginating."""
    client = BybitClient()
    end = end or datetime.now(tz.utc)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    total = 0
    page_size = 1000
    cursor = start_ms
    while cursor < end_ms:
        klines = await client.fetch_klines(
            symbol.code, interval.value, start_ms=cursor, end_ms=end_ms, limit=page_size
        )
        if not klines:
            break
        total += await _upsert(symbol, interval, klines)
        # Advance cursor past the latest returned bar to avoid loops on overlapping pages.
        cursor = int(klines[-1].opened_at.timestamp() * 1000) + interval.seconds * 1000
        if len(klines) < page_size:
            break
    return total


async def _upsert(symbol: Symbol, interval: Interval, klines: list[Kline]) -> int:
    """Upsert via Postgres ON CONFLICT DO UPDATE. Runs in a single transaction."""
    if not klines:
        return 0

    rows = [
        Candle(
            symbol=symbol,
            interval=interval,
            opened_at=k.opened_at,
            closed_at=k.opened_at + _td(interval),
            open=k.open,
            high=k.high,
            low=k.low,
            close=k.close,
            volume=k.volume,
            turnover=k.turnover,
        )
        for k in klines
    ]

    def _bulk() -> int:
        with transaction.atomic():
            Candle.objects.bulk_create(
                rows,
                update_conflicts=True,
                unique_fields=["symbol", "interval", "opened_at"],
                update_fields=["closed_at", "open", "high", "low", "close", "volume", "turnover"],
            )
        return len(rows)

    from asgiref.sync import sync_to_async

    n = await sync_to_async(_bulk, thread_sensitive=True)()
    log.info("ingest.upsert", extra={"symbol": symbol.code, "interval": interval.value, "rows": n})
    return n


def _td(interval: Interval):
    from datetime import timedelta
    return timedelta(seconds=interval.seconds)
