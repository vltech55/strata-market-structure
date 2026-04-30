"""Chart API schemas — pure-Pydantic structure report for the frontend."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SwingOut(BaseModel):
    index: int
    timestamp: datetime
    price: float
    kind: str


class StructureEventOut(BaseModel):
    index: int
    timestamp: datetime
    price: float
    kind: str
    broken_swing_index: int


class OrderBlockOut(BaseModel):
    index: int
    timestamp: datetime
    high: float
    low: float
    bullish: bool


class FVGOut(BaseModel):
    index: int
    timestamp: datetime
    top: float
    bottom: float
    bullish: bool


class WyckoffSegmentOut(BaseModel):
    start_index: int
    end_index: int
    phase: str
    confidence: float


class StructureReportOut(BaseModel):
    symbol: str
    interval: str
    current_trend: str
    swings: list[SwingOut]
    events: list[StructureEventOut]
    order_blocks: list[OrderBlockOut]
    fvgs: list[FVGOut]
    wyckoff: list[WyckoffSegmentOut]


class MultiTFScoreOut(BaseModel):
    symbol: str
    score: float
    per_tf_trend: dict[str, str]
