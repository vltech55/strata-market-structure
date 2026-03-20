"""Persistent refresh-token store — supports rotation, revocation, and per-token replay detection."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class RefreshToken(models.Model):
    """One row per issued refresh token. The token's `jti` is stored, not the token itself."""

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jti         = models.CharField(max_length=64, unique=True, db_index=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="refresh_tokens")
    user_agent  = models.CharField(max_length=255, blank=True, default="")
    ip          = models.GenericIPAddressField(null=True, blank=True)
    issued_at   = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at  = models.DateTimeField(db_index=True)
    revoked_at  = models.DateTimeField(null=True, blank=True)
    replaced_by = models.OneToOneField(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replaces"
    )

    class Meta:
        db_table = "auth_refresh_token"
        indexes = [
            models.Index(fields=["user", "-issued_at"], name="rt_user_issued_idx"),
            models.Index(fields=["expires_at"], name="rt_expires_idx"),
        ]

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()

    def revoke(self, replaced_by: "RefreshToken | None" = None) -> None:
        self.revoked_at = timezone.now()
        if replaced_by:
            self.replaced_by = replaced_by
        self.save(update_fields=["revoked_at", "replaced_by"])
