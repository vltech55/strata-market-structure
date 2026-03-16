"""Custom user model — email-as-username, audit timestamps, role flags."""
from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    ADMIN   = "admin",   _("Admin")
    ANALYST = "analyst", _("Analyst")
    VIEWER  = "viewer",  _("Viewer")


class UserManager(BaseUserManager["User"]):
    """Manager keyed on email rather than username."""

    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra: object) -> "User":
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra: object) -> "User":
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("role", UserRole.VIEWER)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str, **extra: object) -> "User":
        extra.update(is_staff=True, is_superuser=True, is_active=True, role=UserRole.ADMIN)
        return self._create(email, password, **extra)

    def active(self):
        return self.get_queryset().filter(is_active=True)


class User(AbstractBaseUser, PermissionsMixin):
    """Application user. Authenticates by email; JWT RS256 issued on login."""

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email         = models.EmailField(_("email address"), unique=True, db_index=True)
    full_name     = models.CharField(_("full name"), max_length=200, blank=True)
    role          = models.CharField(max_length=16, choices=UserRole.choices, default=UserRole.VIEWER, db_index=True)
    is_active     = models.BooleanField(default=True)
    is_staff      = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_logins = models.PositiveIntegerField(default=0)
    locked_until  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(default=timezone.now, editable=False)
    updated_at    = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "auth_user"
        ordering = ("email",)
        indexes = [
            models.Index(fields=["role", "is_active"], name="user_role_active_idx"),
            models.Index(fields=["-created_at"], name="user_created_desc_idx"),
        ]

    # ------------------------------------------------------------------
    def __str__(self) -> str:
        return self.email

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_login_success(self, ip: str | None) -> None:
        self.failed_logins = 0
        self.locked_until = None
        self.last_login_ip = ip
        self.save(update_fields=["failed_logins", "locked_until", "last_login_ip", "updated_at"])

    def register_login_failure(self, *, max_attempts: int = 10, lock_minutes: int = 15) -> None:
        self.failed_logins += 1
        if self.failed_logins >= max_attempts:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=lock_minutes)
        self.save(update_fields=["failed_logins", "locked_until", "updated_at"])
