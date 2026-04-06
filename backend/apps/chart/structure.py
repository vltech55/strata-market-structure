"""Market-structure detection — pure pandas / NumPy, vectorized.

Implements the canonical Smart-Money / Wyckoff toolkit:

  • swing pivots             (fractal: high/low extremum in a 2k+1 window)
  • Break of Structure (BoS) (continuation of the prevailing trend)
  • Change of Character      (CHoCH — trend reversal at a swing)
  • Wyckoff phase classifier (accumulation / markup / distribution / markdown)
  • Order blocks             (last opposite candle before a structure break)
  • Fair Value Gaps (FVG)    (3-bar gap between candle 1 and candle 3)
  • Multi-timeframe coherence (trend agreement score across TFs)

The hot path is vectorized — pivot detection runs in pandas rolling ops; the BoS/CHoCH
state machine then walks the (much smaller) pivot list. We never iterate the full OHLCV
series in Python on the hot path.

The detectors return *dataclasses* (lightweight, JSON-serialisable, Pydantic-compatible);
service-layer code converts them to chart overlays or persists them to the `Detection` model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Public dataclasses
# ──────────────────────────────────────────────────────────────────────────────


class SwingKind(str, Enum):
    HIGH = "swing_high"
    LOW = "swing_low"


class StructureEventKind(str, Enum):
    BOS_UP = "bos_up"           # uptrend continuation (broke prior high)
    BOS_DOWN = "bos_down"       # downtrend continuation (broke prior low)
    CHOCH_UP = "choch_up"       # reversal: from down → up
    CHOCH_DOWN = "choch_down"   # reversal: from up → down


class WyckoffPhase(str, Enum):
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"
    UNDEFINED = "undefined"


@dataclass(frozen=True)
class SwingPoint:
    index: int             # integer offset into the OHLCV frame
    timestamp: pd.Timestamp
    price: float
    kind: SwingKind


@dataclass(frozen=True)
class StructureEvent:
    index: int
    timestamp: pd.Timestamp
    price: float
    kind: StructureEventKind
    broken_swing_index: int   # which prior swing was broken


@dataclass(frozen=True)
class OrderBlock:
    index: int
    timestamp: pd.Timestamp
    high: float
    low: float
    bullish: bool             # True = demand block (bullish OB), False = supply (bearish OB)
    triggered_by_event_index: int


@dataclass(frozen=True)
class FairValueGap:
    index: int                # index of the *third* candle (the one that creates the visible gap)
    timestamp: pd.Timestamp
    top: float
    bottom: float
    bullish: bool


@dataclass(frozen=True)
class WyckoffSegment:
    start_index: int
    end_index: int
    phase: WyckoffPhase
    confidence: float         # 0..1


@dataclass(frozen=True)
class StructureReport:
    swings: list[SwingPoint] = field(default_factory=list)
    events: list[StructureEvent] = field(default_factory=list)
    order_blocks: list[OrderBlock] = field(default_factory=list)
    fvgs: list[FairValueGap] = field(default_factory=list)
    wyckoff: list[WyckoffSegment] = field(default_factory=list)

    @property
    def current_trend(self) -> str:
        for ev in reversed(self.events):
            if ev.kind in (StructureEventKind.BOS_UP, StructureEventKind.CHOCH_UP):
                return "up"
            if ev.kind in (StructureEventKind.BOS_DOWN, StructureEventKind.CHOCH_DOWN):
                return "down"
        return "undefined"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV frame missing required columns: {missing}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("OHLCV frame must have a DatetimeIndex")
    if not df.index.is_monotonic_increasing:
        df = df.sort_index()
    return df


# ──────────────────────────────────────────────────────────────────────────────
# 1. Swing-point detection (vectorized fractal)
# ──────────────────────────────────────────────────────────────────────────────


def detect_swings(df: pd.DataFrame, *, left: int = 3, right: int = 3) -> list[SwingPoint]:
    """Find swing highs/lows using a fractal pivot of `left + right + 1` bars.

    A bar at index `i` is a **swing high** iff its high is strictly greater than
    each of the `left` bars to its left AND each of the `right` bars to its right.
    Equality on either side disqualifies the bar (this prevents flat-top runs from
    spawning duplicate pivots).

    Implementation is fully vectorized via two rolling windows:
      • `rolling(window=left+right+1, center=True).max()` → bar's high equals window-max → candidate.
      • additional strict-greater checks ensure exclusivity against ties.
    """
    df = _validate(df)
    if df.empty:
        return []
    window = left + right + 1
    if len(df) < window:
        return []

    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    idx = df.index

    high_max = pd.Series(high).rolling(window=window, center=True, min_periods=window).max().to_numpy()
    low_min = pd.Series(low).rolling(window=window, center=True, min_periods=window).min().to_numpy()

    # A bar is a swing high if it owns the window max *and* it's strictly greater than
    # any neighbour at the same level on either side (no ties at the extremum).
    is_high = (high == high_max) & np.isfinite(high_max)
    is_low = (low == low_min) & np.isfinite(low_min)

    # Strict-greater enforcement: for each candidate, look left/right and ensure no ties.
    for i in np.where(is_high)[0]:
        lo, hi = max(0, i - left), min(len(high), i + right + 1)
        neighbours = np.delete(high[lo:hi], i - lo)
        if not (high[i] > neighbours).all():
            is_high[i] = False
    for i in np.where(is_low)[0]:
        lo, hi = max(0, i - left), min(len(low), i + right + 1)
        neighbours = np.delete(low[lo:hi], i - lo)
        if not (low[i] < neighbours).all():
            is_low[i] = False

    swings: list[SwingPoint] = []
    for i in np.where(is_high)[0]:
        swings.append(SwingPoint(int(i), idx[i], float(high[i]), SwingKind.HIGH))
    for i in np.where(is_low)[0]:
        swings.append(SwingPoint(int(i), idx[i], float(low[i]), SwingKind.LOW))
    swings.sort(key=lambda s: s.index)
    return swings


# ──────────────────────────────────────────────────────────────────────────────
# 2. BoS / CHoCH detection — state machine over the swing list
# ──────────────────────────────────────────────────────────────────────────────


def detect_structure_events(df: pd.DataFrame, swings: Sequence[SwingPoint]) -> list[StructureEvent]:
    """Walk the swing list with a trend state machine emitting BoS / CHoCH events.

    Rules (the canonical SMC definitions):
      • In an UP trend, a higher-high breakout is a **BoS_UP** (continuation).
      • In an UP trend, a *lower* low that violates the last swing low is a **CHoCH_DOWN**.
      • Symmetric rules in a DOWN trend.
      • Trend begins as UNKNOWN; the first BoS-or-CHoCH-like move establishes direction.

    We use **closing price** to confirm a break — wicks alone don't count. This matches
    how most discretionary traders read structure on intraday TFs.
    """
    df = _validate(df)
    close = df["close"].to_numpy()
    idx = df.index
    if not swings:
        return []

    trend: str = "unknown"
    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None
    events: list[StructureEvent] = []

    for sp in swings:
        # Find the first bar AFTER this swing where close confirms a break of the *other-side* last swing.
        if sp.kind is SwingKind.HIGH:
            # Update last_high tracking.
            if last_high is None or sp.price > last_high.price:
                broken = _confirm_break(close, idx, sp.index + 1, last_high, direction="up") if last_high else None
                if broken is not None:
                    kind = StructureEventKind.BOS_UP if trend == "up" else StructureEventKind.CHOCH_UP
                    events.append(StructureEvent(broken[0], broken[1], broken[2], kind, last_high.index))
                    trend = "up"
            last_high = sp
        else:  # LOW
            if last_low is None or sp.price < last_low.price:
                broken = _confirm_break(close, idx, sp.index + 1, last_low, direction="down") if last_low else None
                if broken is not None:
                    kind = StructureEventKind.BOS_DOWN if trend == "down" else StructureEventKind.CHOCH_DOWN
                    events.append(StructureEvent(broken[0], broken[1], broken[2], kind, last_low.index))
                    trend = "down"
            last_low = sp

    return events


def _confirm_break(
    close: np.ndarray,
    idx: pd.DatetimeIndex,
    start_from: int,
    swing: SwingPoint,
    *,
    direction: str,
) -> tuple[int, pd.Timestamp, float] | None:
    """Return the (i, ts, close) of the first bar at-or-after `start_from` that closes through the swing."""
    end = len(close)
    if start_from >= end:
        return None
    if direction == "up":
        hits = np.where(close[start_from:end] > swing.price)[0]
    else:
        hits = np.where(close[start_from:end] < swing.price)[0]
    if len(hits) == 0:
        return None
    i = int(start_from + hits[0])
    return i, idx[i], float(close[i])


# ──────────────────────────────────────────────────────────────────────────────
# 3. Order blocks — last opposite-side candle before a confirmed break
# ──────────────────────────────────────────────────────────────────────────────


def detect_order_blocks(df: pd.DataFrame, events: Sequence[StructureEvent]) -> list[OrderBlock]:
    """For each BoS / CHoCH, walk backward from the breakout bar to find the last
    candle of opposite direction — that's the canonical order block."""
    df = _validate(df)
    o = df["open"].to_numpy()
    c = df["close"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    idx = df.index

    blocks: list[OrderBlock] = []
    for ev in events:
        bullish_break = ev.kind in (StructureEventKind.BOS_UP, StructureEventKind.CHOCH_UP)
        # Walk backwards from the breakout bar looking for an *opposite-coloured* candle.
        for i in range(ev.index - 1, max(0, ev.index - 30) - 1, -1):
            is_bearish_candle = c[i] < o[i]
            is_bullish_candle = c[i] > o[i]
            if bullish_break and is_bearish_candle:
                blocks.append(OrderBlock(
                    index=i, timestamp=idx[i], high=float(h[i]), low=float(l[i]),
                    bullish=True, triggered_by_event_index=ev.index,
                ))
                break
            if (not bullish_break) and is_bullish_candle:
                blocks.append(OrderBlock(
                    index=i, timestamp=idx[i], high=float(h[i]), low=float(l[i]),
                    bullish=False, triggered_by_event_index=ev.index,
                ))
                break
    return blocks


# ──────────────────────────────────────────────────────────────────────────────
# 4. Fair-value gaps (3-bar imbalance)
# ──────────────────────────────────────────────────────────────────────────────


def detect_fvgs(df: pd.DataFrame, *, min_gap_pct: float = 0.0005) -> list[FairValueGap]:
    """A bullish FVG exists between candles (i-2, i) when high[i-2] < low[i]. Symmetric for bearish."""
    df = _validate(df)
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    idx = df.index
    n = len(df)
    if n < 3:
        return []

    bullish_mask = h[:-2] < l[2:]
    bearish_mask = l[:-2] > h[2:]

    fvgs: list[FairValueGap] = []
    for i in np.where(bullish_mask)[0]:
        top, bottom = float(l[i + 2]), float(h[i])
        if top - bottom < min_gap_pct * bottom:
            continue
        fvgs.append(FairValueGap(int(i + 2), idx[i + 2], top, bottom, bullish=True))
    for i in np.where(bearish_mask)[0]:
        top, bottom = float(l[i]), float(h[i + 2])
        if top - bottom < min_gap_pct * bottom:
            continue
        fvgs.append(FairValueGap(int(i + 2), idx[i + 2], top, bottom, bullish=False))
    fvgs.sort(key=lambda g: g.index)
    return fvgs


# ──────────────────────────────────────────────────────────────────────────────
# 5. Wyckoff phase classifier (volatility-and-trend heuristic)
# ──────────────────────────────────────────────────────────────────────────────


def classify_wyckoff(df: pd.DataFrame, *, window: int = 30) -> list[WyckoffSegment]:
    """Heuristic Wyckoff phase classifier.

    We segment the series by *trend slope* and *normalized volatility*:
      • LOW slope + LOW volatility (after a downtrend)  → ACCUMULATION
      • POS slope + RISING price                          → MARKUP
      • LOW slope + LOW volatility (after an uptrend)   → DISTRIBUTION
      • NEG slope + FALLING price                         → MARKDOWN
      • everything else                                   → UNDEFINED

    This is intentionally a coarse classifier — exact Wyckoff events (SC/AR/ST/Spring)
    require volume-spike confirmation; the LLM narrator can refine the classification
    when given the raw segments + volume context.
    """
    df = _validate(df)
    if len(df) < window * 2:
        return []

    close = df["close"]
    # Slope via simple linear-fit on a rolling window (vectorized via cumulative trick).
    x = np.arange(len(df))
    slope = close.rolling(window).apply(
        lambda s: np.polyfit(x[: len(s)], s, 1)[0] if len(s) >= 2 else np.nan, raw=True
    )
    rolling_std = close.rolling(window).std()
    norm_vol = (rolling_std / close.rolling(window).mean()).fillna(0.0)

    # Thresholds — normalized so they work across price levels.
    slope_thresh = (close.diff().abs().median() or 0.0) * 0.5
    vol_thresh_low = norm_vol.quantile(0.30)
    vol_thresh_high = norm_vol.quantile(0.70)

    # Direction at each window position.
    direction = np.where(slope > slope_thresh, 1, np.where(slope < -slope_thresh, -1, 0))
    # Previous direction (so we know whether a sideways stretch follows up- or down-trend).
    prev_direction = pd.Series(direction).shift(window).fillna(0).astype(int).to_numpy()

    phases = np.full(len(df), WyckoffPhase.UNDEFINED.value, dtype=object)
    is_sideways = norm_vol < vol_thresh_low
    is_volatile = norm_vol > vol_thresh_high
    phases[(direction == 1) & ~is_sideways] = WyckoffPhase.MARKUP.value
    phases[(direction == -1) & ~is_sideways] = WyckoffPhase.MARKDOWN.value
    phases[is_sideways & (prev_direction == -1)] = WyckoffPhase.ACCUMULATION.value
    phases[is_sideways & (prev_direction == 1)] = WyckoffPhase.DISTRIBUTION.value

    # Compress consecutive equal labels into segments.
    segments: list[WyckoffSegment] = []
    if len(phases) == 0:
        return segments
    start = 0
    for i in range(1, len(phases)):
        if phases[i] != phases[start]:
            confidence = float(1.0 - norm_vol.iloc[start:i].mean()) if not is_volatile[start:i].all() else 0.4
            segments.append(WyckoffSegment(
                start_index=int(start), end_index=int(i - 1),
                phase=WyckoffPhase(phases[start]), confidence=max(0.0, min(1.0, confidence)),
            ))
            start = i
    segments.append(WyckoffSegment(
        start_index=int(start), end_index=int(len(phases) - 1),
        phase=WyckoffPhase(phases[start]), confidence=0.6,
    ))
    # Drop tiny segments and "undefined" runs shorter than the window.
    return [s for s in segments if (s.end_index - s.start_index) >= window // 2 and s.phase != WyckoffPhase.UNDEFINED]


# ──────────────────────────────────────────────────────────────────────────────
# 6. Multi-timeframe coherence
# ──────────────────────────────────────────────────────────────────────────────


def multi_timeframe_coherence(reports: dict[str, StructureReport]) -> float:
    """Score (-1..1) measuring how much higher- and lower-TF trends agree.

    +1 = all TFs in the same direction · 0 = mixed · −1 = all opposite.
    """
    if not reports:
        return 0.0
    direction_value = {"up": 1.0, "down": -1.0, "undefined": 0.0}
    values = [direction_value[r.current_trend] for r in reports.values()]
    mean = float(np.mean(values))
    # Penalise undefined slots.
    defined_fraction = sum(1 for v in values if v != 0.0) / len(values)
    return mean * defined_fraction


# ──────────────────────────────────────────────────────────────────────────────
# Top-level orchestrator
# ──────────────────────────────────────────────────────────────────────────────


def analyse(df: pd.DataFrame, *, left: int = 3, right: int = 3, wyckoff_window: int = 30) -> StructureReport:
    """Run the full detection suite and return a combined StructureReport."""
    df = _validate(df)
    swings = detect_swings(df, left=left, right=right)
    events = detect_structure_events(df, swings)
    obs = detect_order_blocks(df, events)
    fvgs = detect_fvgs(df)
    wyckoff = classify_wyckoff(df, window=wyckoff_window)
    return StructureReport(swings=swings, events=events, order_blocks=obs, fvgs=fvgs, wyckoff=wyckoff)
