"""Chat sessions and messages — analyst Q&A grounded on the structure report."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.stock.models import Symbol


class ChatSession(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sessions")
    symbol      = models.ForeignKey(Symbol, on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_sessions")
    interval    = models.CharField(max_length=4, blank=True, default="1h")
    title       = models.CharField(max_length=200, blank=True, default="")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_session"
        ordering = ("-updated_at",)
        indexes = [models.Index(fields=["user", "-updated_at"], name="cs_user_updated_idx")]


class ChatRole(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    SYSTEM = "system", "System"


class ChatMessage(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session     = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role        = models.CharField(max_length=12, choices=ChatRole.choices, db_index=True)
    content     = models.TextField()
    tokens_in   = models.PositiveIntegerField(default=0)
    tokens_out  = models.PositiveIntegerField(default=0)
    cost_usd    = models.FloatField(default=0.0)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "chat_message"
        ordering = ("created_at",)
        indexes = [models.Index(fields=["session", "created_at"], name="cm_session_created_idx")]
