"""Bybit client tests — verify parsing, retry, and error handling under httpx-mock."""
from __future__ import annotations

import pytest
import respx
import httpx

from apps.stock.bybit import BybitClient, BybitError


# httpx + respx is the canonical mocking combo for async HTTP in modern Python tests.


@pytest.mark.asyncio
@respx.mock
async def test_fetch_klines_parses_and_reverses():
    # Bybit returns newest-first; we expect oldest-first output.
    body = {
        "retCode": 0, "retMsg": "OK",
        "result": {"list": [
            ["1735776000000", "100", "101", "99",  "100.5", "1.5", "150"],   # newest
            ["1735772400000", "98",  "99",  "97",  "98.5",  "1.0", "98"],
            ["1735768800000", "95",  "96",  "94",  "95.5",  "0.8", "76"],    # oldest in this page
        ]},
    }
    respx.get("https://api.bybit.com/v5/market/kline").mock(return_value=httpx.Response(200, json=body))

    client = BybitClient()
    klines = await client.fetch_klines("BTCUSDT", "1h", limit=3)

    assert len(klines) == 3
    assert klines[0].open == 95          # oldest first after reversal
    assert klines[-1].close == 100.5     # newest last


@pytest.mark.asyncio
@respx.mock
async def test_fetch_klines_raises_on_non_zero_retcode():
    respx.get("https://api.bybit.com/v5/market/kline").mock(
        return_value=httpx.Response(200, json={"retCode": 10001, "retMsg": "bad symbol", "result": {}})
    )
    with pytest.raises(BybitError):
        # Retries 4 attempts then re-raises.
        await BybitClient().fetch_klines("BAD", "1h", limit=1)


def test_unknown_interval_rejected_eagerly():
    import asyncio
    with pytest.raises(ValueError):
        asyncio.run(BybitClient().fetch_klines("BTCUSDT", "3h", limit=1))
