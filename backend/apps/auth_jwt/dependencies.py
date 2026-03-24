"""Ninja auth dependency — verifies a `Bearer <jwt>` header and returns a `Principal`."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.http import HttpRequest
from ninja.security import HttpBearer

from apps.auth_jwt.services import TokenError, decode


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    email: str
    role: str
    jti: str


class JWTAuth(HttpBearer):
    """Pass with `Authorization: Bearer <access_token>`."""

    openapi_scheme = "bearer"
    openapi_in = "header"
    header = "Authorization"

    # Used by handlers that need the principal as a kwarg.
    dep = None  # populated below

    def authenticate(self, request: HttpRequest, token: str) -> Principal | None:
        try:
            claims = decode(token, expected_type="access")
        except TokenError:
            return None
        principal = Principal(
            user_id=uuid.UUID(str(claims["sub"])),
            email=str(claims.get("email", "")),
            role=str(claims.get("role", "viewer")),
            jti=str(claims["jti"]),
        )
        # Convention: ninja passes the auth result as `request.auth`; we expose Principal directly.
        request.principal = principal  # type: ignore[attr-defined]
        return principal


# Pseudo-dependency object used as a default arg in handler signatures so the type-check passes;
# ninja injects the real `Principal` via `request.auth`. This pattern is a stand-in for FastAPI's Depends.
JWTAuth.dep = None
