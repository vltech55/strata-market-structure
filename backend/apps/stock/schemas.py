"""Stock API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SymbolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    base_asset: str
    quote_asset: str
    exchange: str
    category: str
    status: str


class CandleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    opened_at: datetime
    closed_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class CandleSeriesOut(BaseModel):
    symbol: str
    interval: str
    candles: list[CandleOut]


class BackfillIn(BaseModel):
    symbol: str
    interval: str
    start: datetime
    end: datetime | None = None
