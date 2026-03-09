"""Request-context middleware — binds a request_id and timing onto every response."""
from __future__ import annotations

import time
import uuid
from typing import Callable

from django.http import HttpRequest, HttpResponse


class RequestContextMiddleware:
    """Adds `X-Request-ID` and `X-Response-Time-Ms` to every response."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]
        started = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response["X-Request-ID"] = request_id
        response["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response
