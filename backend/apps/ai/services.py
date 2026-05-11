"""Generate a briefing — wires the LangGraph pipeline to the structure detector."""
from __future__ import annotations

import logging
import time
from dataclasses import asdict

from asgiref.sync import sync_to_async

from apps.ai.graph import build_graph
from apps.ai.models import Briefing
from apps.ai.schemas import BriefingOut, ReviewerJudgment, WyckoffJudgment
from apps.chart.services import candles_to_dataframe, multi_tf_score
from apps.chart.structure import analyse
from apps.stock.models import Interval, Symbol
from strata.observability import get_langfuse

log = logging.getLogger("strata.ai.services")


async def generate_briefing(
    symbol_code: str,
    interval: str,
    *,
    lookback: int = 1000,
    prompt_version: str = "v1",
) -> BriefingOut:
    @sync_to_async
    def _prepare():
        symbol = Symbol.objects.get(code=symbol_code)
        df = candles_to_dataframe(symbol, Interval(interval), limit=lookback)
        if df.empty:
            raise RuntimeError(f"no candles for {symbol_code}:{interval}")
        report = analyse(df)
        mtf = multi_tf_score(symbol)
        from apps.chart.services import _report_to_json
        return symbol, _report_to_json(report), float(mtf["score"]), report.current_trend

    symbol, structure_json, mtf, current_trend = await _prepare()

    graph = build_graph()
    initial = {
        "symbol": symbol_code,
        "interval": interval,
        "prompt_version": prompt_version,
        "structure_json": structure_json,
        "mtf_score": mtf,
    }
    started = time.perf_counter()
    langfuse = get_langfuse()
    trace = None
    if langfuse:
        trace = langfuse.trace(name="strata.briefing", input=initial, tags=[symbol_code, interval, prompt_version])

    final_state = await graph.ainvoke(initial)

    duration_ms = int((time.perf_counter() - started) * 1000)
    if trace:
        trace.update(output={"markdown_len": len(final_state.get("briefing_markdown", "")),
                              "iterations": final_state.get("iterations", 1)})
        langfuse.flush()

    out = BriefingOut(
        symbol=symbol_code,
        interval=interval,
        prompt_version=prompt_version,
        current_trend=current_trend,
        mtf_score=mtf,
        narrative_markdown=final_state.get("briefing_markdown", ""),
        wyckoff=final_state.get("wyckoff", WyckoffJudgment(current_phase="undefined", confidence=0.0,
                                                            volume_supports_label=False)),
        reviewer=final_state.get("reviewer", ReviewerJudgment()),
        iterations=final_state.get("iterations", 1),
        token_usage={},
    )

    @sync_to_async
    def _persist():
        return Briefing.objects.create(
            symbol=symbol,
            interval=interval,
            prompt_version=prompt_version,
            markdown=out.narrative_markdown,
            wyckoff_phase=out.wyckoff.current_phase,
            wyckoff_conf=out.wyckoff.confidence,
            reviewer_sev=out.reviewer.severity,
            iterations=out.iterations,
            events_json=final_state.get("events", []),
            duration_ms=duration_ms,
        )

    await _persist()
    return out
