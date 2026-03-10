"""Celery app factory.

Loads Django settings, picks up `CELERY_*` config, autodiscovers tasks across apps,
and binds Sentry + OTel + Langfuse instrumentation at worker boot.
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "strata.settings")

app = Celery("strata")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["apps.stock", "apps.chart", "apps.ai", "apps.chat"])


# ──────────────────────────────────────────────────────────────────────────────
# Beat schedule — periodic ingestion + nightly backtest snapshot.
# ──────────────────────────────────────────────────────────────────────────────
app.conf.beat_schedule = {
    "ingest-active-symbols-every-minute": {
        "task": "apps.stock.tasks.ingest_active_symbols",
        "schedule": 60.0,
        "options": {"queue": "strata.ingestion", "expires": 55},
    },
    "recompute-structure-every-5-minutes": {
        "task": "apps.chart.tasks.recompute_active_symbols",
        "schedule": 300.0,
        "options": {"queue": "strata.structure"},
    },
    "nightly-backtest-snapshot": {
        "task": "apps.chart.tasks.nightly_backtest_snapshot",
        "schedule": crontab(hour=3, minute=15),
        "options": {"queue": "strata.batch"},
    },
}

app.conf.task_routes = {
    "apps.stock.*":  {"queue": "strata.ingestion"},
    "apps.chart.*":  {"queue": "strata.structure"},
    "apps.ai.*":     {"queue": "strata.ai"},
    "apps.chat.*":   {"queue": "strata.ai"},
}


@worker_process_init.connect
def _init_observability(**_: object) -> None:
    from strata import observability  # noqa: F401
