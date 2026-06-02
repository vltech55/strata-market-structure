# Strata — Architecture

## Process model

Strata runs as six processes inside one Docker Compose stack:

| Process    | Purpose                                                  | Image base                      |
|------------|----------------------------------------------------------|---------------------------------|
| `backend`  | Django 5 + django-ninja, served by uWSGI                  | multi-stage Python 3.13-slim    |
| `worker`   | Celery worker — ingestion, structure recompute, AI jobs    | same image, different command   |
| `beat`     | Celery beat — schedules recurring jobs                    | same image                      |
| `flower`   | Celery monitoring UI                                       | same image                      |
| `streamlit`| Frontend workspace                                         | same image, different command   |
| `postgres` | Primary datastore                                          | postgres:16-alpine              |
| `redis`    | Celery broker + result backend + cache                    | redis:7-alpine                  |
| `minio`    | S3-compatible object storage (chart snapshots, reports)   | minio/minio:latest              |

Sharing one image across `backend`, `worker`, `beat`, `flower`, and `streamlit` is deliberate
— one build cache, one dependency set, one set of code paths to audit. The container's role is
determined by its `command:` in compose.

## Domain split

The Django project mirrors the JD's six-app structure exactly:

```
backend/apps/
  users/      — custom User (email-as-username), role flags, lockout, audit timestamps
  auth_jwt/   — RS256 JWT issuance, refresh-token rotation, replay detection
  stock/      — Symbol + Candle models, Bybit REST client, ingestion service, Celery tasks
  chart/      — pandas-native structure detection (swings, BoS/CHoCH, Wyckoff, OB, FVG),
                multi-TF coherence, persisted DetectionRun + BacktestRun
  ai/         — LangGraph multi-agent briefing pipeline, Langfuse trace integration,
                persisted Briefing model
  chat/       — ChatSession + ChatMessage, grounded Q&A against the structure snapshot
```

`auth_jwt` rather than `auth` because `django.contrib.auth` is reserved.

## Data flow — full request lifecycle

A request from the Streamlit workspace asking "give me a briefing for BTCUSDT 1h" follows
this path:

```
Streamlit ─── POST /api/v1/ai/briefing ───▶  uWSGI ──▶  django-ninja router
                                                         │
                                                  JWTAuth dependency (RS256 verify)
                                                         │
                                                         ▼
                                              apps.ai.services.generate_briefing
                                                         │
                                              ┌──────────┼──────────┐
                                              ▼                     ▼
                                  Postgres (candles)       Postgres (multi-tf candles)
                                              │                     │
                                              ▼                     ▼
                                  apps.chart.services.analyse → multi_tf_score
                                              │
                                              ▼
                                  LangGraph BriefingState assembled
                                              │
                                              ▼
                       data_stats → narrator → wyckoff → reviewer ───┐
                                                          │           │
                                          requires_revision & iter<2 │
                                                          ▼           │ no
                                                       (revise)        ▼
                                                          │         formatter
                                                          └────▶ structure_narrator
                                                                       │
                                                                       ▼
                                                                Persist Briefing row
                                                                       │
                                                                       ▼
                                                                Return BriefingOut
```

Every LLM call goes through a Langfuse handle (configured in `strata.observability`),
producing a full prompt+response trace.

## Async/sync boundary

The API surface is `async def`. The ORM is still sync (Django 5's async support is partial),
so DB-bound critical sections wrap in `sync_to_async(..., thread_sensitive=True)`. The Bybit
client and the LangGraph graph are natively async (httpx + LangGraph's `ainvoke`).

Celery workers are prefork (sync). They use `asyncio.run(...)` to wrap the async ingestion
helpers. Each worker is single-task-prefetch (`worker_prefetch_multiplier=1`) so a slow task
never head-of-line-blocks faster ones.

## Migrations

Django manages its own migrations per app under `apps/<name>/migrations/`. To generate the
initial set after the first scaffold:

```
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

The schemas in this scaffold include `CheckConstraint`s (OHLC sanity) and composite uniqueness
(`Candle.unique_constraint(symbol, interval, opened_at)`) so even a buggy ingestion path can't
corrupt the index.

## Security model

- **Transport.** TLS terminated upstream (reverse proxy / k8s ingress). The Django security
  middleware enforces HSTS + secure cookies when `ENV=production`.
- **Authentication.** JWT RS256. The private key signs; the public key verifies. Keys live
  outside the image (mounted from `./keys/` locally; from a k8s Secret in production).
- **Tokens.** Short-lived access (15 min), rotating refresh (30 days). Each refresh token's
  `jti` is persisted in `auth_refresh_token`; using a previously-rotated token revokes the
  whole family — replay detection.
- **Lockout.** Per-user counter on failed logins; 10 failures locks the account for 15 minutes.
- **API.** No CSRF on the JSON API (token auth only). CORS is explicit-allow per origin.

## Observability

| Layer        | Tool                         | Where wired                                          |
|--------------|------------------------------|------------------------------------------------------|
| LLM traces   | Langfuse                     | `strata.observability.get_langfuse()` + `services.py` |
| App tracing  | OpenTelemetry → OTLP/gRPC    | `strata.observability._init_otel()`                  |
| Errors       | Sentry                       | `strata.observability._init_sentry()`                |
| Logs         | structlog-style JSON         | `strata.logging.JsonFormatter`                       |
| Metrics      | uWSGI stats + Celery events  | `observability/uwsgi.ini`, Flower                    |
| Request tags | X-Request-ID middleware      | `strata.middleware.RequestContextMiddleware`         |
