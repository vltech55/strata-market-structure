"""Pydantic schemas for the AI pipeline — request/response and node-level state."""
from __future__ import annotations

from typing import Annotated, TypedDict

import operator
from pydantic import BaseModel, Field

# ──────────────────────────────────────────────────────────────────────────────
# Public API schemas.
# ──────────────────────────────────────────────────────────────────────────────


class BriefingIn(BaseModel):
    symbol: str
    interval: str
    lookback: int = 1000
    prompt_version: str = "v1"


class WyckoffJudgment(BaseModel):
    current_phase: str
    confidence: float = Field(ge=0.0, le=1.0)
    volume_supports_label: bool
    notes: str = ""


class ReviewerJudgment(BaseModel):
    issues: list[str] = Field(default_factory=list)
    severity: str = "low"
    requires_revision: bool = False


class BriefingOut(BaseModel):
    symbol: str
    interval: str
    prompt_version: str
    current_trend: str
    mtf_score: float
    narrative_markdown: str
    wyckoff: WyckoffJudgment
    reviewer: ReviewerJudgment
    iterations: int = Field(ge=1, default=1)
    token_usage: dict[str, int] = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# LangGraph state TypedDict.
# List fields are annotated with operator.add so parallel branches merge cleanly.
# ──────────────────────────────────────────────────────────────────────────────


class BriefingState(TypedDict, total=False):
    # inputs
    symbol: str
    interval: str
    prompt_version: str
    structure_json: dict
    mtf_score: float

    # working artifacts
    stats_summary: str
    narrative_draft: str
    wyckoff: WyckoffJudgment
    reviewer: ReviewerJudgment

    # control + accounting
    iterations: int
    token_usage: dict[str, int]
    events: Annotated[list[str], operator.add]

    # final output
    briefing_markdown: str
