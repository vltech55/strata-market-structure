"""Shared pytest fixtures.

The structure-detection tests don't need Django — they exercise pure pandas. The API
tests do; pytest-django provides the `db` fixture which builds an isolated test database.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def rng():
    return np.random.default_rng(42)


@pytest.fixture
def ts_index():
    """Hourly DatetimeIndex spanning 500 bars from 2026-01-01."""
    return pd.date_range("2026-01-01", periods=500, freq="h", tz="UTC")


@pytest.fixture
def synthetic_uptrend(ts_index) -> pd.DataFrame:
    """A clearly-trending series — slowly climbing close with small noise."""
    n = len(ts_index)
    close = np.linspace(100.0, 200.0, n) + (np.sin(np.linspace(0, 8 * np.pi, n)) * 2.0)
    df = pd.DataFrame({
        "open":  close - 0.4,
        "high":  close + 0.8,
        "low":   close - 0.8,
        "close": close,
        "volume": np.full(n, 1000.0),
    }, index=ts_index)
    return df


@pytest.fixture
def synthetic_downtrend(ts_index) -> pd.DataFrame:
    """A clearly-falling series — for symmetry checks."""
    n = len(ts_index)
    close = np.linspace(200.0, 100.0, n) + (np.sin(np.linspace(0, 8 * np.pi, n)) * 2.0)
    df = pd.DataFrame({
        "open":  close + 0.4,
        "high":  close + 0.8,
        "low":   close - 0.8,
        "close": close,
        "volume": np.full(n, 1000.0),
    }, index=ts_index)
    return df


@pytest.fixture
def synthetic_flat(ts_index) -> pd.DataFrame:
    """Constant price — pathological case for the detector."""
    n = len(ts_index)
    return pd.DataFrame({
        "open": np.full(n, 100.0), "high": np.full(n, 100.0),
        "low":  np.full(n, 100.0), "close": np.full(n, 100.0),
        "volume": np.full(n, 1000.0),
    }, index=ts_index)


@pytest.fixture
def fvg_pattern(ts_index) -> pd.DataFrame:
    """Three-bar bullish FVG: bar0.high=100, bar1 in the middle, bar2.low=105 → gap 100..105."""
    n = len(ts_index)
    o = np.full(n, 100.0)
    h = np.full(n, 100.5)
    l = np.full(n, 99.5)
    c = np.full(n, 100.0)
    # Insert a bullish FVG at index 100 / 101 / 102.
    o[100], h[100], l[100], c[100] = 99.0,  100.0,  98.5,   99.5
    o[101], h[101], l[101], c[101] = 99.5,  104.5,  99.4,  104.0   # impulse candle
    o[102], h[102], l[102], c[102] = 104.5, 106.0,  105.0, 105.5   # opens past bar0.high
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": np.full(n, 1000.0)}, index=ts_index)
