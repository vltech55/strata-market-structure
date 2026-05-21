"""Typed HTTP client for the Strata backend API."""
from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st


def _api_base() -> str:
    # Inside docker network: STRATA_API_URL. From a browser-side context Streamlit
    # itself runs server-side, so we use the in-network URL.
    return os.getenv("STRATA_API_URL", "http://backend:8000/api")


def _client() -> httpx.Client:
    return httpx.Client(base_url=_api_base(), timeout=30.0)


def _auth_headers() -> dict[str, str]:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


# ──────────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────────


def login(email: str, password: str) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/v1/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()


def signup(email: str, password: str, full_name: str = "") -> dict[str, Any]:
    with _client() as c:
        r = c.post("/v1/auth/signup", json={"email": email, "password": password, "full_name": full_name})
    r.raise_for_status()
    return r.json()


def refresh_token(refresh_token_str: str) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/v1/auth/refresh", json={"refresh_token": refresh_token_str})
    r.raise_for_status()
    return r.json()


def me() -> dict[str, Any]:
    with _client() as c:
        r = c.get("/v1/users/me", headers=_auth_headers())
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────────────────────────────────────
# Stock / chart
# ──────────────────────────────────────────────────────────────────────────────


def candles(symbol: str, interval: str, limit: int) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/v1/stock/candles/{symbol}", params={"interval": interval, "limit": limit},
                  headers=_auth_headers())
    r.raise_for_status()
    return r.json()


def structure(symbol: str, interval: str, lookback: int) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/v1/chart/structure/{symbol}", params={"interval": interval, "lookback": lookback},
                  headers=_auth_headers())
    r.raise_for_status()
    return r.json()


def mtf(symbol: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/v1/chart/mtf/{symbol}", headers=_auth_headers())
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────────────────────────────────────
# AI
# ──────────────────────────────────────────────────────────────────────────────


def briefing(symbol: str, interval: str, lookback: int = 1000) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/v1/ai/briefing", json={"symbol": symbol, "interval": interval, "lookback": lookback},
                   headers=_auth_headers())
    r.raise_for_status()
    return r.json()


def latest_briefing(symbol: str, interval: str) -> dict[str, Any] | None:
    with _client() as c:
        r = c.get(f"/v1/ai/briefing/{symbol}/{interval}/latest", headers=_auth_headers())
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────────────────────────────────────


def ask(question: str, symbol: str | None, interval: str | None) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/v1/chat/ask",
                   json={"question": question, "symbol": symbol, "interval": interval},
                   headers=_auth_headers())
    r.raise_for_status()
    return r.json()
