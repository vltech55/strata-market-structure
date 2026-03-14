"""django-ninja root API.

Mounts the per-app routers under `/api/v1/<domain>/`. Uses the JWT RS256 dependency
defined in `apps.auth_jwt.dependencies`. OpenAPI is served at `/api/docs`.
"""
from __future__ import annotations

from ninja import NinjaAPI
from ninja.errors import HttpError

from apps.ai.api import router as ai_router
from apps.auth_jwt.api import router as auth_router
from apps.chart.api import router as chart_router
from apps.chat.api import router as chat_router
from apps.stock.api import router as stock_router
from apps.users.api import router as users_router

api = NinjaAPI(
    title="Strata API",
    version="1.0.0",
    description=(
        "Production crypto market-structure analytics. "
        "OHLCV ingestion, swing / BoS / CHoCH / Wyckoff detection, multi-agent LLM briefings."
    ),
    urls_namespace="strata_api",
    docs_url="/docs",
    openapi_url="/openapi.json",
    csrf=False,  # Token-auth API; CSRF is enforced on browser sessions only.
)

# Public auth endpoints (no JWT required).
api.add_router("/v1/auth", auth_router, tags=["auth"])

# Authenticated endpoints.
api.add_router("/v1/users",  users_router,  tags=["users"])
api.add_router("/v1/stock",  stock_router,  tags=["stock"])
api.add_router("/v1/chart",  chart_router,  tags=["chart"])
api.add_router("/v1/ai",     ai_router,     tags=["ai"])
api.add_router("/v1/chat",   chat_router,   tags=["chat"])


@api.exception_handler(HttpError)
def _http_error(request, exc: HttpError):
    return api.create_response(request, {"detail": exc.message}, status=exc.status_code)


@api.exception_handler(Exception)
def _internal_error(request, exc: Exception):
    # Structured + Sentry-friendly. Don't leak internals to clients.
    import logging
    logging.getLogger("strata.api").exception("unhandled exception in api", extra={"path": request.path})
    return api.create_response(request, {"detail": "internal_error"}, status=500)
