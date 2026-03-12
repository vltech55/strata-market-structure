"""Observability wiring — Sentry, OpenTelemetry, Langfuse handle.

Imported once at process start (from `wsgi.py`, `asgi.py`, and the Celery worker_process_init hook).
Safe to import multiple times: each SDK is idempotent.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("strata.observability")


def _init_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            integrations=[DjangoIntegration(), CeleryIntegration()],
            send_default_pii=False,
            release=os.getenv("GIT_SHA", "dev"),
        )
        logger.info("sentry initialised")
    except Exception:
        logger.exception("sentry init failed — continuing without it")


def _init_otel() -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource(attributes={SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "strata")}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
        trace.set_tracer_provider(provider)

        DjangoInstrumentor().instrument()
        CeleryInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()
        logger.info("opentelemetry initialised")
    except Exception:
        logger.exception("OpenTelemetry init failed — continuing without it")


_LANGFUSE_HANDLE = None


def get_langfuse():
    """Return a shared Langfuse client (None if no keys configured)."""
    global _LANGFUSE_HANDLE
    if _LANGFUSE_HANDLE is not None:
        return _LANGFUSE_HANDLE
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not (pk and sk):
        return None
    try:
        from langfuse import Langfuse

        _LANGFUSE_HANDLE = Langfuse(
            public_key=pk,
            secret_key=sk,
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        logger.info("langfuse initialised")
    except Exception:
        logger.exception("Langfuse init failed — continuing without it")
        _LANGFUSE_HANDLE = None
    return _LANGFUSE_HANDLE


_init_sentry()
_init_otel()
