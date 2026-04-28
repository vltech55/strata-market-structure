"""Persisted detection runs and backtest results."""
from __future__ import annotations

import uuid

from django.db import models

from apps.stock.models import Symbol


class DetectionRun(models.Model):
    """One persisted analysis of (symbol, interval) at a point in time."""

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    symbol       = models.ForeignKey(Symbol, on_delete=models.CASCADE, related_name="detection_runs", db_index=True)
    interval     = models.CharField(max_length=4, db_index=True)
    git_sha      = models.CharField(max_length=40, blank=True, default="")
    config_json  = models.JSONField(default=dict)     # detector params used (left/right/window/...)
    report_json  = models.JSONField(default=dict)     # serialised StructureReport
    n_swings     = models.PositiveIntegerField(default=0)
    n_events     = models.PositiveIntegerField(default=0)
    n_obs        = models.PositiveIntegerField(default=0)
    n_fvgs       = models.PositiveIntegerField(default=0)
    current_trend = models.CharField(max_length=16, default="undefined")
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chart_detection_run"
        indexes = [
            models.Index(fields=["symbol", "interval", "-created_at"], name="dr_lookup_idx"),
        ]
        ordering = ("-created_at",)


class BacktestRun(models.Model):
    """A backtest stats snapshot, keyed to a git SHA for A/B comparison across commits."""

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    symbol       = models.ForeignKey(Symbol, on_delete=models.CASCADE, related_name="backtest_runs", db_index=True)
    interval     = models.CharField(max_length=4, db_index=True)
    git_sha      = models.CharField(max_length=40, db_index=True)
    detector     = models.CharField(max_length=32, db_index=True)
    n_signals    = models.PositiveIntegerField()
    hit_rate     = models.FloatField()
    avg_pnl_pct  = models.FloatField()
    max_drawdown_pct = models.FloatField()
    risk_reward  = models.FloatField()
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chart_backtest_run"
        indexes = [
            models.Index(fields=["symbol", "interval", "detector", "-created_at"], name="bt_lookup_idx"),
        ]
        ordering = ("-created_at",)
