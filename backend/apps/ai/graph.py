"""LangGraph briefing pipeline.

Nodes (5):
  1. data_stats          — pure-Python: compute OHLCV summary stats from the structure JSON.
  2. structure_narrator  — LLM: turn structural events into a plain-English narrative.
  3. wyckoff_classifier  — LLM: refine Wyckoff phase classification.
  4. risk_reviewer       — LLM: critique the narrative; flag unsupported claims.
  5. formatter           — LLM: produce the final Markdown briefing.

Edges:
  data_stats → structure_narrator → wyckoff_classifier → risk_reviewer
  risk_reviewer ──(requires_revision & iter<2)── back to structure_narrator
  risk_reviewer ──(else)── formatter → END

The state schema (BriefingState) carries the working artifacts; list fields are
annotated with operator.add so list writes merge across parallel branches if we
ever add them (kept consistent with the broader Strata convention).
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from apps.ai.agents import (
    build_formatter,
    build_risk_reviewer,
    build_structure_narrator,
    build_wyckoff_classifier,
)
from apps.ai.schemas import BriefingState, ReviewerJudgment, WyckoffJudgment

log = logging.getLogger("strata.graph")

MAX_ITERATIONS = 2


# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────


def node_data_stats(state: BriefingState) -> dict:
    """Compute deterministic stats from the structure JSON. No LLM call."""
    sj = state.get("structure_json", {})
    events = sj.get("events", [])
    swings = sj.get("swings", [])
    last_event = events[-1] if events else None
    last_swing_high = next((s for s in reversed(swings) if s["kind"] == "swing_high"), None)
    last_swing_low = next((s for s in reversed(swings) if s["kind"] == "swing_low"), None)
    summary = (
        f"current_trend={sj.get('current_trend', 'undefined')}, "
        f"n_events={len(events)}, n_swings={len(swings)}, "
        f"last_event={last_event['kind'] if last_event else 'none'}@"
        f"{last_event['timestamp'] if last_event else 'n/a'}, "
        f"last_swing_high={last_swing_high['price'] if last_swing_high else 'n/a'}, "
        f"last_swing_low={last_swing_low['price'] if last_swing_low else 'n/a'}"
    )
    return {"stats_summary": summary, "events": [f"data_stats: {summary}"], "iterations": 0}


def node_structure_narrator(state: BriefingState) -> dict:
    narrator = build_structure_narrator(state.get("prompt_version", "v1"))
    text = narrator({
        "stats_summary": state.get("stats_summary", ""),
        "structure": state.get("structure_json", {}),
    })
    return {"narrative_draft": text, "events": [f"narrator: produced draft ({len(text)} chars)"]}


def node_wyckoff_classifier(state: BriefingState) -> dict:
    classifier = build_wyckoff_classifier(state.get("prompt_version", "v1"))
    raw = classifier({
        "draft": state.get("narrative_draft", ""),
        "wyckoff_segments": state.get("structure_json", {}).get("wyckoff", []),
    })
    judgment = WyckoffJudgment(
        current_phase=str(raw.get("current_phase", "undefined")),
        confidence=float(raw.get("confidence", 0.5)),
        volume_supports_label=bool(raw.get("volume_supports_label", False)),
        notes=str(raw.get("notes", "")),
    )
    return {"wyckoff": judgment, "events": [f"wyckoff: {judgment.current_phase} ({judgment.confidence:.2f})"]}


def node_risk_reviewer(state: BriefingState) -> dict:
    reviewer = build_risk_reviewer(state.get("prompt_version", "v1"))
    raw = reviewer({
        "draft": state.get("narrative_draft", ""),
        "wyckoff": state.get("wyckoff", WyckoffJudgment(current_phase="undefined", confidence=0.0,
                                                       volume_supports_label=False)).model_dump(),
        "structure": state.get("structure_json", {}),
    })
    judgment = ReviewerJudgment(
        issues=[str(i) for i in raw.get("issues", [])],
        severity=str(raw.get("severity", "low")),
        requires_revision=bool(raw.get("requires_revision", False)),
    )
    iterations = state.get("iterations", 0) + 1
    return {
        "reviewer": judgment,
        "iterations": iterations,
        "events": [f"reviewer: {judgment.severity} sev, {len(judgment.issues)} issues, "
                   f"revise={judgment.requires_revision}, iter={iterations}"],
    }


def node_formatter(state: BriefingState) -> dict:
    formatter = build_formatter(state.get("prompt_version", "v1"))
    md = formatter({
        "symbol": state.get("symbol", ""),
        "interval": state.get("interval", ""),
        "stats_summary": state.get("stats_summary", ""),
        "draft": state.get("narrative_draft", ""),
        "wyckoff": (state.get("wyckoff") or WyckoffJudgment(current_phase="undefined", confidence=0.0,
                                                            volume_supports_label=False)).model_dump(),
        "reviewer": (state.get("reviewer") or ReviewerJudgment()).model_dump(),
        "mtf_score": state.get("mtf_score", 0.0),
        "structure": state.get("structure_json", {}),
    })
    return {"briefing_markdown": md, "events": [f"formatter: {len(md)} chars"]}


# ──────────────────────────────────────────────────────────────────────────────
# Routing — bounded revise loop
# ──────────────────────────────────────────────────────────────────────────────


def after_reviewer(state: BriefingState) -> str:
    reviewer = state.get("reviewer") or ReviewerJudgment()
    iterations = state.get("iterations", 0)
    if reviewer.requires_revision and iterations < MAX_ITERATIONS:
        log.info("graph.revise", extra={"iterations": iterations, "issues": len(reviewer.issues)})
        return "revise"
    return "finalize"


# ──────────────────────────────────────────────────────────────────────────────
# Compile
# ──────────────────────────────────────────────────────────────────────────────


def build_graph():
    g = StateGraph(BriefingState)
    g.add_node("data_stats", node_data_stats)
    g.add_node("structure_narrator", node_structure_narrator)
    g.add_node("wyckoff_classifier", node_wyckoff_classifier)
    g.add_node("risk_reviewer", node_risk_reviewer)
    g.add_node("formatter", node_formatter)

    g.add_edge(START, "data_stats")
    g.add_edge("data_stats", "structure_narrator")
    g.add_edge("structure_narrator", "wyckoff_classifier")
    g.add_edge("wyckoff_classifier", "risk_reviewer")
    g.add_conditional_edges(
        "risk_reviewer",
        after_reviewer,
        {"revise": "structure_narrator", "finalize": "formatter"},
    )
    g.add_edge("formatter", END)
    return g.compile()
