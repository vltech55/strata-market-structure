"""Issue, verify, and rotate JWT tokens (RS256)."""
from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Literal

from django.conf import settings
from django.utils import timezone
from jose import JWTError, jwt

from apps.auth_jwt.keys import private_key_pem, public_key_pem
from apps.auth_jwt.models import RefreshToken
from apps.users.models import User


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = 0


class TokenError(RuntimeError):
    """Raised on any token failure — invalid signature, expired, revoked, replayed."""


def _now() -> int:
    return int(time.time())


def _claims(*, sub: str, ttl_seconds: int, token_type: str, extra: dict[str, object] | None = None) -> dict[str, object]:
    iat = _now()
    base: dict[str, object] = {
        "iss": settings.cfg.JWT_ISSUER,
        "sub": sub,
        "iat": iat,
        "nbf": iat,
        "exp": iat + ttl_seconds,
        "jti": secrets.token_urlsafe(32),
        "typ": token_type,
    }
    if extra:
        base.update(extra)
    return base


def _encode(claims: dict[str, object]) -> str:
    return jwt.encode(claims, private_key_pem(), algorithm=settings.cfg.JWT_ALGORITHM)


def issue_tokens(user: User, *, ip: str | None = None, user_agent: str = "") -> TokenPair:
    """Issue an access+refresh pair and persist the refresh JTI for rotation/revocation."""
    access_claims = _claims(
        sub=str(user.id),
        ttl_seconds=settings.cfg.JWT_ACCESS_TTL_SECONDS,
        token_type="access",
        extra={"role": user.role, "email": user.email},
    )
    refresh_claims = _claims(
        sub=str(user.id),
        ttl_seconds=settings.cfg.JWT_REFRESH_TTL_SECONDS,
        token_type="refresh",
    )
    RefreshToken.objects.create(
        jti=refresh_claims["jti"],
        user=user,
        user_agent=user_agent[:255],
        ip=ip,
        expires_at=timezone.now() + timezone.timedelta(seconds=settings.cfg.JWT_REFRESH_TTL_SECONDS),
    )
    return TokenPair(
        access_token=_encode(access_claims),
        refresh_token=_encode(refresh_claims),
        expires_in=settings.cfg.JWT_ACCESS_TTL_SECONDS,
    )


def decode(token: str, *, expected_type: str) -> dict[str, object]:
    try:
        claims = jwt.decode(
            token,
            public_key_pem(),
            algorithms=[settings.cfg.JWT_ALGORITHM],
            issuer=settings.cfg.JWT_ISSUER,
            options={"require": ["exp", "iat", "iss", "sub", "jti", "typ"]},
        )
    except JWTError as exc:
        raise TokenError(f"invalid token: {exc}") from exc
    if claims.get("typ") != expected_type:
        raise TokenError(f"wrong token type — expected {expected_type}, got {claims.get('typ')}")
    return claims


def rotate_refresh(refresh_token_str: str, *, ip: str | None, user_agent: str) -> TokenPair:
    """Verify a refresh token, revoke it, and issue a fresh pair. Replay-detects revoked tokens."""
    claims = decode(refresh_token_str, expected_type="refresh")
    jti = str(claims["jti"])
    try:
        record = RefreshToken.objects.select_related("user").get(jti=jti)
    except RefreshToken.DoesNotExist as exc:
        raise TokenError("refresh token unknown") from exc

    if not record.is_active:
        # Replay attempt: any prior token now arriving is suspicious. Revoke the whole family.
        RefreshToken.objects.filter(user=record.user, revoked_at__isnull=True).update(revoked_at=timezone.now())
        raise TokenError("refresh token revoked — all sessions invalidated as a precaution")

    new_pair = issue_tokens(record.user, ip=ip, user_agent=user_agent)
    # Bind the new refresh token's record to the old one for audit.
    new_record = RefreshToken.objects.get(jti=jti_from_token(new_pair.refresh_token))
    record.revoke(replaced_by=new_record)
    return new_pair


def revoke_refresh(refresh_token_str: str) -> None:
    """Mark a specific refresh token revoked (logout)."""
    try:
        claims = decode(refresh_token_str, expected_type="refresh")
    except TokenError:
        return  # idempotent — already invalid is fine
    RefreshToken.objects.filter(jti=claims["jti"], revoked_at__isnull=True).update(revoked_at=timezone.now())


def jti_from_token(token: str) -> str:
    """Lightweight helper — pulls `jti` without verifying signature (only safe right after issuing)."""
    unverified = jwt.get_unverified_claims(token)
    return str(unverified["jti"])
