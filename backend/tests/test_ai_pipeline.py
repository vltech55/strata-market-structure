"""Smoke test for the LangGraph briefing pipeline.

The point of this test is to verify the *graph wiring* — node order, state flow,
schema validation, conditional edge — without burning OpenAI tokens. We patch each
LLM-backed agent factory with a deterministic stub.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


@pytest.fixture
def fake_structure_json() -> dict:
    return {
        "current_trend": "up",
        "swings": [
            {"index": 10, "timestamp": "2026-01-01T00:00:00+00:00", "price": 100.0, "kind": "swing_low"},
            {"index": 30, "timestamp": "2026-01-02T00:00:00+00:00", "price": 110.0, "kind": "swing_high"},
        ],
        "events": [
            {"index": 25, "timestamp": "2026-01-01T20:00:00+00:00", "price": 105.0,
             "kind": "choch_up", "broken_swing_index": 10},
        ],
        "order_blocks": [],
        "fvgs": [],
        "wyckoff": [{"start_index": 0, "end_index": 50, "phase": "markup", "confidence": 0.7}],
    }


def _stub_narrator(payload):
    return "Trend is up. CHoCH_UP printed at 2026-01-01T20:00 on close 105.0."


def _stub_wyckoff(payload):
    return {"current_phase": "markup", "confidence": 0.75, "volume_supports_label": True,
            "notes": "Steady demand, no exhaustion."}


def _stub_reviewer(payload):
    return {"issues": [], "severity": "low", "requires_revision": False}


def _stub_formatter(payload):
    return f"# {payload['symbol']} · {payload['interval']} — Structure Briefing\n\n**Trend:** up · stub."


@pytest.mark.asyncio
async def test_graph_runs_end_to_end(fake_structure_json):
    from apps.ai import graph as graph_module

    with (
        patch.object(graph_module, "build_structure_narrator", return_value=_stub_narrator),
        patch.object(graph_module, "build_wyckoff_classifier", return_value=_stub_wyckoff),
        patch.object(graph_module, "build_risk_reviewer", return_value=_stub_reviewer),
        patch.object(graph_module, "build_formatter", return_value=_stub_formatter),
    ):
        compiled = graph_module.build_graph()
        final = await compiled.ainvoke({
            "symbol": "BTCUSDT", "interval": "1h", "prompt_version": "v1",
            "structure_json": fake_structure_json, "mtf_score": 0.5,
        })

    assert "briefing_markdown" in final
    assert "BTCUSDT" in final["briefing_markdown"]
    assert final["iterations"] == 1
    assert final["wyckoff"].current_phase == "markup"
    assert final["reviewer"].requires_revision is False
    # The event log should record every node.
    nodes_visited = {e.split(":")[0] for e in final.get("events", [])}
    assert {"data_stats", "narrator", "wyckoff", "reviewer", "formatter"}.issubset(nodes_visited)


@pytest.mark.asyncio
async def test_revise_loop_fires_when_reviewer_flags(fake_structure_json):
    """When the reviewer demands revision, the graph loops back to narrator (once)."""
    from apps.ai import graph as graph_module

    seen_iterations = []

    def stateful_reviewer(payload):
        # First call flags; second call passes.
        if not seen_iterations:
            seen_iterations.append(1)
            return {"issues": ["unsupported claim"], "severity": "medium", "requires_revision": True}
        return {"issues": [], "severity": "low", "requires_revision": False}

    with (
        patch.object(graph_module, "build_structure_narrator", return_value=_stub_narrator),
        patch.object(graph_module, "build_wyckoff_classifier", return_value=_stub_wyckoff),
        patch.object(graph_module, "build_risk_reviewer", return_value=stateful_reviewer),
        patch.object(graph_module, "build_formatter", return_value=_stub_formatter),
    ):
        compiled = graph_module.build_graph()
        final = await compiled.ainvoke({
            "symbol": "BTCUSDT", "interval": "1h", "prompt_version": "v1",
            "structure_json": fake_structure_json, "mtf_score": 0.5,
        })

    assert final["iterations"] == 2, "should loop exactly once on revise=True"
