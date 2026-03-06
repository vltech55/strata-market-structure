"""Django settings for Strata — production-style, env-var driven, multi-environment.

Environments are differentiated by the ENV variable: `development` | `staging` | `production`.
Production hardens security headers, requires TLS, and disables DEBUG regardless of DEBUG=.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_NAME = "Strata"


# ──────────────────────────────────────────────────────────────────────────────
# Typed settings loaded once at startup from environment + .env.
# ──────────────────────────────────────────────────────────────────────────────
class StrataConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    # Environment
    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    DJANGO_SECRET_KEY: str = Field(default="insecure-dev-only-do-not-use-in-prod", min_length=32)
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,backend"
    CSRF_TRUSTED_ORIGINS: str = "http://localhost:8000,http://localhost:8501"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:8501"

    # Database
    DATABASE_URL: PostgresDsn = Field(default="postgres://strata:strata@postgres:5432/strata")
    DB_CONN_MAX_AGE: int = 60
    DB_POOL_MIN_SIZE: int = 4
    DB_POOL_MAX_SIZE: int = 20

    # Redis / Celery
    REDIS_URL: RedisDsn = Field(default="redis://redis:6379/0")
    CELERY_BROKER_URL: RedisDsn = Field(default="redis://redis:6379/1")
    CELERY_RESULT_BACKEND: RedisDsn = Field(default="redis://redis:6379/2")
    CELERY_TASK_DEFAULT_QUEUE: str = "strata.default"
    CELERY_TASK_ACKS_LATE: bool = True
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1

    # Object storage
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "strata"
    MINIO_SECURE: bool = False

    # JWT
    JWT_PRIVATE_KEY_PATH: str = "/app/keys/jwt-rs256-private.pem"
    JWT_PUBLIC_KEY_PATH: str = "/app/keys/jwt-rs256-public.pem"
    JWT_ISSUER: str = "strata"
    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TTL_SECONDS: int = 900
    JWT_REFRESH_TTL_SECONDS: int = 2_592_000  # 30 days

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_MAX_TOKENS: int = 1200

    # Langfuse
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PROJECT: str = "strata"

    # Bybit
    BYBIT_BASE_URL: str = "https://api.bybit.com"
    BYBIT_CATEGORY: Literal["linear", "spot", "inverse"] = "linear"
    BYBIT_REQUEST_TIMEOUT: int = 20

    # Observability
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_SERVICE_NAME: str = "strata-backend"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

    @field_validator("OPENAI_TEMPERATURE")
    @classmethod
    def _temp_range(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("OPENAI_TEMPERATURE must be in [0, 2]")
        return v


cfg = StrataConfig()


# ──────────────────────────────────────────────────────────────────────────────
# Django settings — wired from `cfg`.
# ──────────────────────────────────────────────────────────────────────────────
SECRET_KEY = cfg.DJANGO_SECRET_KEY
DEBUG = cfg.DEBUG and cfg.ENV == "development"
ALLOWED_HOSTS = [h.strip() for h in cfg.ALLOWED_HOSTS.split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in cfg.CSRF_TRUSTED_ORIGINS.split(",") if o.strip()]
CORS_ALLOWED_ORIGINS = [o.strip() for o in cfg.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "corsheaders",
    "django_celery_beat",
    # local
    "apps.users.apps.UsersConfig",
    "apps.auth_jwt.apps.AuthJwtConfig",
    "apps.stock.apps.StockConfig",
    "apps.chart.apps.ChartConfig",
    "apps.ai.apps.AiConfig",
    "apps.chat.apps.ChatConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Strata observability — adds request_id and timing to every response.
    "strata.middleware.RequestContextMiddleware",
]

ROOT_URLCONF = "strata.urls"
WSGI_APPLICATION = "strata.wsgi.application"
ASGI_APPLICATION = "strata.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "backend" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Database — psycopg3 (sync) for ORM; async-capable backend used directly in async views.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": cfg.DATABASE_URL.path.lstrip("/") if cfg.DATABASE_URL.path else "strata",
        "USER": cfg.DATABASE_URL.username or "strata",
        "PASSWORD": cfg.DATABASE_URL.password or "",
        "HOST": cfg.DATABASE_URL.host or "postgres",
        "PORT": str(cfg.DATABASE_URL.port or 5432),
        "CONN_MAX_AGE": cfg.DB_CONN_MAX_AGE,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "pool": {
                "min_size": cfg.DB_POOL_MIN_SIZE,
                "max_size": cfg.DB_POOL_MAX_SIZE,
            },
            "application_name": "strata",
        },
        "ATOMIC_REQUESTS": False,   # async-friendly; controlled per-handler.
    }
}

# Auth
AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# i18n
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static / media
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "backend" / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "backend" / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Sessions — DB-backed, short TTL; the API itself is JWT-authenticated.
SESSION_COOKIE_AGE = 60 * 60 * 4
SESSION_SAVE_EVERY_REQUEST = False

# Celery — wired from cfg.
CELERY_BROKER_URL = str(cfg.CELERY_BROKER_URL)
CELERY_RESULT_BACKEND = str(cfg.CELERY_RESULT_BACKEND)
CELERY_TASK_DEFAULT_QUEUE = cfg.CELERY_TASK_DEFAULT_QUEUE
CELERY_TASK_ACKS_LATE = cfg.CELERY_TASK_ACKS_LATE
CELERY_WORKER_PREFETCH_MULTIPLIER = cfg.CELERY_WORKER_PREFETCH_MULTIPLIER
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_TIME_LIMIT = 600         # 10 min hard cap
CELERY_TASK_SOFT_TIME_LIMIT = 540
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ──────────────────────────────────────────────────────────────────────────────
# Security — locked down for staging/production. Dev keeps things relaxed.
# ──────────────────────────────────────────────────────────────────────────────
if cfg.ENV in ("staging", "production"):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31_536_000     # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

# ──────────────────────────────────────────────────────────────────────────────
# Logging — structlog-style JSON in prod, friendlier console in dev.
# ──────────────────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "strata.logging.JsonFormatter",
        },
        "console": {
            "format": "[%(asctime)s] %(levelname)-7s %(name)s · %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json" if cfg.LOG_FORMAT == "json" else "console",
        },
    },
    "root": {"handlers": ["stdout"], "level": cfg.LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
        "django.db.backends": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "strata": {"handlers": ["stdout"], "level": cfg.LOG_LEVEL, "propagate": False},
    },
}

# Sentry + OTel wiring lives in strata.observability and is invoked from celery.py / asgi.py / wsgi.py.
