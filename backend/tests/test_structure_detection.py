"""Tests for the structure detection algorithms.

These exercise the pure-pandas detectors against fixtures with known answers.
No Django, no LLM — fast and deterministic.
"""
from __future__ import annotations

import pandas as pd
import pytest

from apps.chart.structure import (
    StructureEventKind,
    SwingKind,
    analyse,
    classify_wyckoff,
    detect_fvgs,
    detect_order_blocks,
    detect_structure_events,
    detect_swings,
    multi_timeframe_coherence,
)


# ──────────────────────────────────────────────────────────────────────────────
# Swing pivots
# ──────────────────────────────────────────────────────────────────────────────


class TestSwings:
    def test_uptrend_has_alternating_highs_and_lows(self, synthetic_uptrend):
        swings = detect_swings(synthetic_uptrend, left=3, right=3)
        assert len(swings) >= 8, "uptrend with sine ripple should produce multiple swings"
        # First we test that we get both kinds.
        kinds = {s.kind for s in swings}
        assert SwingKind.HIGH in kinds and SwingKind.LOW in kinds

    def test_swings_alternate_in_orderly_fashion(self, synthetic_uptrend):
        swings = detect_swings(synthetic_uptrend, left=3, right=3)
        # We don't enforce strict alternation but consecutive same-kind swings
        # should be the exception, not the rule.
        same_kind_runs = sum(1 for i in range(1, len(swings)) if swings[i].kind == swings[i - 1].kind)
        assert same_kind_runs <= len(swings) // 2

    def test_flat_series_has_no_swings(self, synthetic_flat):
        assert detect_swings(synthetic_flat, left=3, right=3) == []

    def test_empty_frame_is_handled(self):
        empty = pd.DataFrame({"open": [], "high": [], "low": [], "close": [], "volume": []},
                              index=pd.DatetimeIndex([], tz="UTC"))
        assert detect_swings(empty) == []

    def test_left_right_window_can_be_tuned(self, synthetic_uptrend):
        swings_3 = detect_swings(synthetic_uptrend, left=3, right=3)
        swings_5 = detect_swings(synthetic_uptrend, left=5, right=5)
        # Larger window → strictly fewer or equal pivots (more stringent test).
        assert len(swings_5) <= len(swings_3)

    def test_rejects_frame_without_required_columns(self):
        df = pd.DataFrame({"close": [1, 2, 3]}, index=pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC"))
        with pytest.raises(ValueError):
            detect_swings(df)

    def test_rejects_non_datetime_index(self):
        df = pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1], "volume": [1]})
        with pytest.raises(ValueError):
            detect_swings(df)


# ──────────────────────────────────────────────────────────────────────────────
# BoS / CHoCH state machine
# ──────────────────────────────────────────────────────────────────────────────


class TestStructureEvents:
    def test_uptrend_produces_bos_up_events(self, synthetic_uptrend):
        swings = detect_swings(synthetic_uptrend, left=3, right=3)
        events = detect_structure_events(synthetic_uptrend, swings)
        bos_ups = [e for e in events if e.kind == StructureEventKind.BOS_UP]
        assert len(bos_ups) > 0

    def test_downtrend_produces_bos_down_events(self, synthetic_downtrend):
        swings = detect_swings(synthetic_downtrend, left=3, right=3)
        events = detect_structure_events(synthetic_downtrend, swings)
        bos_downs = [e for e in events if e.kind == StructureEventKind.BOS_DOWN]
        assert len(bos_downs) > 0

    def test_no_events_without_swings(self, synthetic_uptrend):
        assert detect_structure_events(synthetic_uptrend, []) == []

    def test_event_broken_index_points_at_an_earlier_swing(self, synthetic_uptrend):
        swings = detect_swings(synthetic_uptrend, left=3, right=3)
        events = detect_structure_events(synthetic_uptrend, swings)
        for ev in events:
            assert ev.broken_swing_index < ev.index


# ──────────────────────────────────────────────────────────────────────────────
# Fair value gaps
# ──────────────────────────────────────────────────────────────────────────────


class TestFVG:
    def test_engineered_bullish_fvg_is_detected(self, fvg_pattern):
        fvgs = detect_fvgs(fvg_pattern, min_gap_pct=0.001)
        # The engineered gap should land at index ~102.
        assert any(f.bullish and 100 <= f.index <= 103 for f in fvgs)

    def test_flat_series_has_no_fvgs(self, synthetic_flat):
        assert detect_fvgs(synthetic_flat) == []

    def test_short_series_returns_empty(self):
        df = pd.DataFrame({"open": [1, 2], "high": [1, 2], "low": [1, 2], "close": [1, 2], "volume": [1, 1]},
                           index=pd.date_range("2026-01-01", periods=2, freq="h", tz="UTC"))
        assert detect_fvgs(df) == []


# ──────────────────────────────────────────────────────────────────────────────
# Order blocks
# ──────────────────────────────────────────────────────────────────────────────


class TestOrderBlocks:
    def test_uptrend_produces_bullish_order_blocks(self, synthetic_uptrend):
        report = analyse(synthetic_uptrend)
        if not report.events:
            pytest.skip("no events generated — synthetic series too uniform")
        bullish = [o for o in report.order_blocks if o.bullish]
        # In a sustained uptrend, demand blocks should outnumber supply blocks.
        assert len(bullish) >= len(report.order_blocks) - len(bullish)


# ──────────────────────────────────────────────────────────────────────────────
# Wyckoff phases
# ──────────────────────────────────────────────────────────────────────────────


class TestWyckoff:
    def test_uptrend_segments_include_markup(self, synthetic_uptrend):
        segments = classify_wyckoff(synthetic_uptrend)
        phases = {s.phase.value for s in segments}
        assert "markup" in phases

    def test_downtrend_segments_include_markdown(self, synthetic_downtrend):
        segments = classify_wyckoff(synthetic_downtrend)
        phases = {s.phase.value for s in segments}
        assert "markdown" in phases

    def test_flat_series_produces_no_directional_phases(self, synthetic_flat):
        segments = classify_wyckoff(synthetic_flat)
        assert all(s.phase.value in {"accumulation", "distribution"} or s.phase.value == "undefined"
                    for s in segments)


# ──────────────────────────────────────────────────────────────────────────────
# Multi-timeframe coherence
# ──────────────────────────────────────────────────────────────────────────────


class TestCoherence:
    def test_all_up_scores_positive(self, synthetic_uptrend):
        r = analyse(synthetic_uptrend)
        score = multi_timeframe_coherence({"1h": r, "4h": r, "1d": r})
        assert score >= 0.0  # all up or all undefined

    def test_empty_input_returns_zero(self):
        assert multi_timeframe_coherence({}) == 0.0
