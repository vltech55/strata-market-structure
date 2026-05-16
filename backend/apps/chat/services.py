"""Chat services — answer a question grounded on the most recent structure report."""
from __future__ import annotations

import json

from asgiref.sync import sync_to_async
from langchain_core.messages import HumanMessage, SystemMessage

from apps.ai.agents import _llm
from apps.chart.services import candles_to_dataframe
from apps.chart.structure import analyse
from apps.stock.models import Interval, Symbol


SYSTEM = """You are an analyst assistant for crypto market structure. You receive a question and a
structured snapshot (current_trend, latest events, swings, Wyckoff segments, MTF score).

Answer briefly and factually. Cite event timestamps. If the answer isn't supported by the snapshot,
say "the data doesn't show that" rather than inventing a number."""


async def answer(question: str, *, symbol_code: str | None, interval: str | None) -> str:
    snapshot: dict | None = None
    if symbol_code and interval:
        @sync_to_async
        def _snap():
            symbol = Symbol.objects.get(code=symbol_code)
            df = candles_to_dataframe(symbol, Interval(interval), limit=500)
            if df.empty:
                return None
            r = analyse(df)
            return {
                "symbol": symbol_code,
                "interval": interval,
                "current_trend": r.current_trend,
                "latest_events": [
                    {"kind": e.kind.value, "price": e.price, "ts": e.timestamp.isoformat()}
                    for e in r.events[-5:]
                ],
                "latest_swings": [
                    {"kind": s.kind.value, "price": s.price, "ts": s.timestamp.isoformat()}
                    for s in r.swings[-5:]
                ],
                "wyckoff": [
                    {"phase": w.phase.value, "confidence": w.confidence}
                    for w in r.wyckoff[-3:]
                ],
            }

        snapshot = await _snap()

    llm = _llm(temperature=0.2)
    resp = llm.invoke([
        SystemMessage(content=SYSTEM),
        HumanMessage(content=json.dumps({"question": question, "snapshot": snapshot}, default=str)),
    ])
    return resp.content if isinstance(resp.content, str) else str(resp.content)
