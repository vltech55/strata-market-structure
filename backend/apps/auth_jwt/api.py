"""Public auth endpoints — login, refresh, logout, signup."""
from __future__ import annotations

from django.contrib.auth import authenticate
from ninja import Router
from ninja.errors import HttpError

from apps.auth_jwt.schemas import LoginIn, LogoutIn, RefreshIn, TokenOut
from apps.auth_jwt.services import TokenError, issue_tokens, revoke_refresh, rotate_refresh
from apps.users.models import User
from apps.users.schemas import UserOut, UserSignupIn

router = Router()


def _client_ip(request) -> str | None:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@router.post("/signup", response={201: TokenOut}, summary="Create a new account")
def signup(request, payload: UserSignupIn):
    if User.objects.filter(email__iexact=payload.email).exists():
        raise HttpError(409, "email already registered")
    user = User.objects.create_user(email=payload.email, password=payload.password, full_name=payload.full_name)
    pair = issue_tokens(user, ip=_client_ip(request), user_agent=request.headers.get("User-Agent", ""))
    return 201, TokenOut(**pair.__dict__)


@router.post("/login", response=TokenOut, summary="Exchange credentials for a token pair")
def login(request, payload: LoginIn):
    try:
        user = User.objects.get(email__iexact=payload.email)
    except User.DoesNotExist as exc:
        raise HttpError(401, "invalid credentials") from exc

    if user.is_locked:
        raise HttpError(429, "account temporarily locked — too many failed attempts")

    authed = authenticate(request, username=user.email, password=payload.password)
    if authed is None or not authed.is_active:
        user.register_login_failure()
        raise HttpError(401, "invalid credentials")

    user.register_login_success(ip=_client_ip(request))
    pair = issue_tokens(user, ip=_client_ip(request), user_agent=request.headers.get("User-Agent", ""))
    return TokenOut(**pair.__dict__)


@router.post("/refresh", response=TokenOut, summary="Rotate a refresh token")
def refresh(request, payload: RefreshIn):
    try:
        pair = rotate_refresh(
            payload.refresh_token,
            ip=_client_ip(request),
            user_agent=request.headers.get("User-Agent", ""),
        )
    except TokenError as exc:
        raise HttpError(401, str(exc)) from exc
    return TokenOut(**pair.__dict__)


@router.post("/logout", response={204: None}, summary="Revoke a refresh token")
def logout(request, payload: LogoutIn):
    revoke_refresh(payload.refresh_token)
    return 204, None
