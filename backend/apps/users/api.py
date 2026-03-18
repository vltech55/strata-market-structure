"""Users API — current-user read + profile update. Auth via JWT RS256."""
from __future__ import annotations

from ninja import Router

from apps.auth_jwt.dependencies import JWTAuth, Principal
from apps.users.models import User
from apps.users.schemas import UserOut, UserUpdateIn

router = Router(auth=JWTAuth())


@router.get("/me", response=UserOut, summary="Current user")
async def me(request, principal: Principal = JWTAuth.dep) -> User:
    return await User.objects.aget(id=principal.user_id)


@router.patch("/me", response=UserOut, summary="Update current user")
async def update_me(request, payload: UserUpdateIn, principal: Principal = JWTAuth.dep) -> User:
    user = await User.objects.aget(id=principal.user_id)
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.password:
        user.set_password(payload.password)
    await user.asave()
    return user
