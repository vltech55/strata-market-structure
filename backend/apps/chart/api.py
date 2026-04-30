"""Chart router — on-demand structure analysis + MTF coherence."""
from __future__ import annotations

from asgiref.sync import sync_to_async
from ninja import Router
from ninja.errors import HttpError

from apps.auth_jwt.dependencies import JWTAuth
from apps.chart.schemas import MultiTFScoreOut, StructureReportOut
from apps.chart.services import candles_to_dataframe, multi_tf_score, run_and_persist
from apps.chart.structure import analyse
from apps.stock.models import Interval, Symbol

router = Router(auth=JWTAuth())


@router.get("/structure/{symbol_code}", response=StructureReportOut, summary="Compute structure for a symbol")
async def structure(request, symbol_code: str, interval: str = "1h", lookback: int = 1000):
    try:
        Interval(interval)
    except ValueError as exc:
        raise HttpError(400, f"invalid interval: {interval}") from exc

    @sync_to_async
    def _build():
        symbol = Symbol.objects.get(code=symbol_code)
        df = candles_to_dataframe(symbol, Interval(interval), limit=lookback)
        if df.empty:
            raise HttpError(404, f"no candles for {symbol_code}:{interval}")
        report = analyse(df)
        return symbol, report

    symbol, report = await _build()
    return StructureReportOut(
        symbol=symbol.code,
        interval=interval,
        current_trend=report.current_trend,
        swings=[{"index": s.index, "timestamp": s.timestamp, "price": s.price, "kind": s.kind.value} for s in report.swings],
        events=[
            {"index": e.index, "timestamp": e.timestamp, "price": e.price, "kind": e.kind.value,
             "broken_swing_index": e.broken_swing_index} for e in report.events
        ],
        order_blocks=[
            {"index": o.index, "timestamp": o.timestamp, "high": o.high, "low": o.low, "bullish": o.bullish}
            for o in report.order_blocks
        ],
        fvgs=[
            {"index": f.index, "timestamp": f.timestamp, "top": f.top, "bottom": f.bottom, "bullish": f.bullish}
            for f in report.fvgs
        ],
        wyckoff=[
            {"start_index": w.start_index, "end_index": w.end_index, "phase": w.phase.value, "confidence": w.confidence}
            for w in report.wyckoff
        ],
    )


@router.get("/mtf/{symbol_code}", response=MultiTFScoreOut, summary="Multi-timeframe trend coherence")
async def mtf(request, symbol_code: str):
    @sync_to_async
    def _compute():
        symbol = Symbol.objects.get(code=symbol_code)
        return multi_tf_score(symbol)

    result = await _compute()
    return MultiTFScoreOut(symbol=symbol_code, score=result["score"], per_tf_trend=result["per_tf_trend"])
