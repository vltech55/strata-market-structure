"""Chat API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    symbol: str | None
    interval: str
    title: str
    updated_at: datetime


class ChatSessionCreateIn(BaseModel):
    symbol: str | None = None
    interval: str = "1h"
    title: str = ""


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ChatAskIn(BaseModel):
    question: str
    symbol: str | None = None
    interval: str | None = None
