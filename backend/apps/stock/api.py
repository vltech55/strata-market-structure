"""Stock router — symbols catalog and OHLCV series."""
from __future__ import annotations

from asgiref.sync import sync_to_async
from ninja import Query, Router
from ninja.errors import HttpError
from ninja.pagination import paginate

from apps.auth_jwt.dependencies import JWTAuth
from apps.stock.ingestion import backfill
from apps.stock.models import Candle, Interval, Symbol
from apps.stock.schemas import BackfillIn, CandleSeriesOut, SymbolOut

router = Router(auth=JWTAuth())


@router.get("/symbols", response=list[SymbolOut], summary="List symbols")
@paginate
def list_symbols(request, q: str | None = Query(default=None)):
    qs = Symbol.objects.all()
    if q:
        qs = qs.filter(code__icontains=q)
    return qs


@router.get("/candles/{symbol_code}", response=CandleSeriesOut, summary="Fetch OHLCV series")
async def candles(request, symbol_code: str, interval: str = "1h", limit: int = 500):
    try:
        Interval(interval)
    except ValueError as exc:
        raise HttpError(400, f"invalid interval: {interval}") from exc
    limit = min(max(limit, 1), 5000)

    @sync_to_async
    def _query():
        return list(
            Candle.objects.for_symbol(symbol_code, interval).latest_n(limit).values(
                "opened_at", "closed_at", "open", "high", "low", "close", "volume"
            )
        )

    rows = await _query()
    # Re-order to oldest-first for chart consumers.
    rows.reverse()
    return CandleSeriesOut(symbol=symbol_code, interval=interval, candles=rows)


@router.post("/backfill", response={202: dict}, summary="Trigger a historical backfill (async)")
async def trigger_backfill(request, payload: BackfillIn):
    try:
        symbol = await Symbol.objects.aget(code=payload.symbol)
    except Symbol.DoesNotExist as exc:
        raise HttpError(404, "symbol not found") from exc
    n = await backfill(symbol, Interval(payload.interval), start=payload.start, end=payload.end)
    return 202, {"upserted": n, "symbol": payload.symbol, "interval": payload.interval}
