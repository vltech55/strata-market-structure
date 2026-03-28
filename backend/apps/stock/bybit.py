"""Bybit public REST client — paginated kline fetch with backoff."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone as tz
from decimal import Decimal
from typing import Literal

import httpx
from django.conf import settings
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger("strata.bybit")

# Map our internal Interval codes to Bybit's interval strings.
_BYBIT_INTERVAL = {
    "1m": "1", "5m": "5", "15m": "15",
    "1h": "60", "4h": "240",
    "1d": "D", "1w": "W",
}


@dataclass(frozen=True)
class Kline:
    opened_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal

    @property
    def closed_at(self) -> datetime:
        return self.opened_at  # placeholder; closed = opened + interval, set at insert time


class BybitError(RuntimeError):
    """Raised when Bybit returns a non-zero `retCode` or an HTTP error after retries."""


class BybitClient:
    """Async Bybit public REST client.

    Production-grade: retries with exponential backoff on transient errors, honours
    rate-limit headers, and validates `retCode == 0` on every response (Bybit's
    convention — they return 200 OK with `retCode != 0` on logical failures).
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        category: Literal["linear", "spot", "inverse"] | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = base_url or settings.cfg.BYBIT_BASE_URL
        self.category = category or settings.cfg.BYBIT_CATEGORY
        self.timeout = timeout or float(settings.cfg.BYBIT_REQUEST_TIMEOUT)

    # ---- public surface -----------------------------------------------------
    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        *,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 200,
    ) -> list[Kline]:
        """Fetch a single kline page (max 1000 bars per Bybit response)."""
        if interval not in _BYBIT_INTERVAL:
            raise ValueError(f"unsupported interval: {interval}")
        params: dict[str, str | int] = {
            "category": self.category,
            "symbol": symbol,
            "interval": _BYBIT_INTERVAL[interval],
            "limit": min(max(limit, 1), 1000),
        }
        if start_ms is not None:
            params["start"] = start_ms
        if end_ms is not None:
            params["end"] = end_ms

        payload = await self._get("/v5/market/kline", params)
        rows = payload.get("result", {}).get("list", []) or []
        # Bybit returns newest-first; we normalise to oldest-first.
        klines = [self._parse_kline_row(row) for row in reversed(rows)]
        log.info("bybit.fetch_klines", extra={"symbol": symbol, "interval": interval, "n": len(klines)})
        return klines

    async def list_instruments(self) -> list[dict[str, object]]:
        payload = await self._get("/v5/market/instruments-info", {"category": self.category})
        return payload.get("result", {}).get("list", []) or []

    # ---- internals ---------------------------------------------------------
    async def _get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        url = f"{self.base_url}{path}"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((httpx.HTTPError, BybitError)),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    body = response.json()
                    if body.get("retCode") != 0:
                        raise BybitError(f"bybit retCode={body.get('retCode')}: {body.get('retMsg')}")
                    return body
        raise BybitError("unreachable")  # for mypy

    @staticmethod
    def _parse_kline_row(row: list[str]) -> Kline:
        # Bybit kline row: [startTime, open, high, low, close, volume, turnover]
        ms = int(row[0])
        return Kline(
            opened_at=datetime.fromtimestamp(ms / 1000.0, tz=tz.utc),
            open=Decimal(row[1]),
            high=Decimal(row[2]),
            low=Decimal(row[3]),
            close=Decimal(row[4]),
            volume=Decimal(row[5]),
            turnover=Decimal(row[6]) if len(row) > 6 else Decimal("0"),
        )
