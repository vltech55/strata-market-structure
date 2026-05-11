"""Persisted briefings and per-step traces."""
from __future__ import annotations

import uuid

from django.db import models

from apps.stock.models import Symbol


class Briefing(models.Model):
    """One persisted AI briefing run. The graph trace lives in `events_json`."""

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    symbol          = models.ForeignKey(Symbol, on_delete=models.CASCADE, related_name="briefings", db_index=True)
    interval        = models.CharField(max_length=4, db_index=True)
    prompt_version  = models.CharField(max_length=16, default="v1", db_index=True)
    markdown        = models.TextField()
    wyckoff_phase   = models.CharField(max_length=32, default="undefined", db_index=True)
    wyckoff_conf    = models.FloatField(default=0.0)
    reviewer_sev    = models.CharField(max_length=8, default="low")
    iterations      = models.PositiveSmallIntegerField(default=1)
    events_json     = models.JSONField(default=list)             # node events captured during the run
    token_usage     = models.JSONField(default=dict)
    cost_usd        = models.FloatField(default=0.0)
    created_at      = models.DateTimeField(auto_now_add=True)
    duration_ms     = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "ai_briefing"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["symbol", "interval", "-created_at"], name="brief_lookup_idx"),
        ]
