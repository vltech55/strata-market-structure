"""Symbol + Candle models.

A `Candle` row is one OHLCV bar at a given timeframe. We use a composite uniqueness
constraint (symbol, interval, opened_at) so dedup is enforced at the DB and an
ON CONFLICT upsert is possible during ingestion.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _


class Interval(models.TextChoices):
    MIN_1   = "1m",  _("1 minute")
    MIN_5   = "5m",  _("5 minutes")
    MIN_15  = "15m", _("15 minutes")
    HOUR_1  = "1h",  _("1 hour")
    HOUR_4  = "4h",  _("4 hours")
    DAY_1   = "1d",  _("1 day")
    WEEK_1  = "1w",  _("1 week")

    @property
    def seconds(self) -> int:
        return {
            "1m": 60, "5m": 300, "15m": 900,
            "1h": 3600, "4h": 14_400,
            "1d": 86_400, "1w": 604_800,
        }[self.value]


class SymbolStatus(models.TextChoices):
    ACTIVE   = "active",   _("Active")
    INACTIVE = "inactive", _("Inactive")
    DELISTED = "delisted", _("Delisted")


class Symbol(models.Model):
    """A tradable instrument. `code` is the exchange ticker (e.g. 'BTCUSDT')."""

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code          = models.CharField(max_length=32, unique=True, db_index=True)
    base_asset    = models.CharField(max_length=16)
    quote_asset   = models.CharField(max_length=16)
    exchange      = models.CharField(max_length=32, default="bybit", db_index=True)
    category      = models.CharField(max_length=16, default="linear")   # linear | spot | inverse
    status        = models.CharField(max_length=16, choices=SymbolStatus.choices, default=SymbolStatus.ACTIVE, db_index=True)
    tick_size     = models.DecimalField(max_digits=24, decimal_places=12, default=Decimal("0.01"))
    lot_size      = models.DecimalField(max_digits=24, decimal_places=12, default=Decimal("0.001"))
    min_qty       = models.DecimalField(max_digits=24, decimal_places=12, default=Decimal("0.001"))
    listed_at     = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stock_symbol"
        ordering = ("code",)
        indexes = [
            models.Index(fields=["exchange", "status"], name="sym_exchange_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.exchange}:{self.code}"


class CandleQuerySet(models.QuerySet["Candle"]):
    def for_symbol(self, symbol: Symbol | str, interval: Interval | str):
        sym_id = symbol.id if isinstance(symbol, Symbol) else None
        sym_code = symbol if isinstance(symbol, str) else None
        qs = self.select_related("symbol").filter(interval=interval)
        return qs.filter(symbol_id=sym_id) if sym_id else qs.filter(symbol__code=sym_code)

    def latest_n(self, n: int):
        return self.order_by("-opened_at")[:n]


class Candle(models.Model):
    """One OHLCV bar. Volume + turnover both kept since Bybit returns both."""

    id          = models.BigAutoField(primary_key=True)
    symbol      = models.ForeignKey(Symbol, on_delete=models.CASCADE, related_name="candles", db_index=True)
    interval    = models.CharField(max_length=4, choices=Interval.choices, db_index=True)
    opened_at   = models.DateTimeField(db_index=True)              # bar start (UTC)
    closed_at   = models.DateTimeField()                            # bar end   (UTC)
    open        = models.DecimalField(max_digits=24, decimal_places=12)
    high        = models.DecimalField(max_digits=24, decimal_places=12)
    low         = models.DecimalField(max_digits=24, decimal_places=12)
    close       = models.DecimalField(max_digits=24, decimal_places=12)
    volume      = models.DecimalField(max_digits=32, decimal_places=8)
    turnover    = models.DecimalField(max_digits=32, decimal_places=8, default=Decimal("0"))
    ingested_at = models.DateTimeField(auto_now_add=True)

    objects = CandleQuerySet.as_manager()

    class Meta:
        db_table = "stock_candle"
        constraints = [
            models.UniqueConstraint(fields=["symbol", "interval", "opened_at"], name="candle_unique_bar"),
            models.CheckConstraint(check=models.Q(high__gte=models.F("low")), name="candle_high_gte_low"),
            models.CheckConstraint(check=models.Q(high__gte=models.F("open")), name="candle_high_gte_open"),
            models.CheckConstraint(check=models.Q(high__gte=models.F("close")), name="candle_high_gte_close"),
            models.CheckConstraint(check=models.Q(low__lte=models.F("open")), name="candle_low_lte_open"),
            models.CheckConstraint(check=models.Q(low__lte=models.F("close")), name="candle_low_lte_close"),
        ]
        indexes = [
            models.Index(fields=["symbol", "interval", "-opened_at"], name="candle_lookup_idx"),
        ]
        ordering = ("-opened_at",)

    def __str__(self) -> str:
        return f"{self.symbol.code} {self.interval} @ {self.opened_at:%Y-%m-%d %H:%M}"
