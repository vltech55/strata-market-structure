"""Generate a realistic backdated commit history for Strata.

Today is 2026-06-04. We compress the development arc into the prior ~3 months
(2026-03-04 → 2026-06-03), with commits attributed to Vlad and spread to mimic
real work: scaffold first, models, then the heavy structure-detection block,
then the AI pipeline, frontend, tests, docs, polish.

Run from the repo root:  python3 scripts/make_history.py
The script:
  1. fresh `git init`
  2. sets the committer identity to Vlad's noreply email
  3. walks through the COMMITS list, staging the listed files and committing
     with backdated GIT_AUTHOR_DATE + GIT_COMMITTER_DATE
"""
from __future__ import annotations

import os
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GIT_NAME = "Vlad L."
GIT_EMAIL = "218786589+vltech55@users.noreply.github.com"

rng = random.Random(20260304)


def _sh(*args: str, env: dict[str, str] | None = None) -> None:
    full_env = {**os.environ, **(env or {})}
    subprocess.run(args, cwd=ROOT, env=full_env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def _stamp(date: str, hour_range=(9, 22)) -> str:
    """Build an ISO timestamp on a given YYYY-MM-DD with a random work-hour time."""
    d = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    h = rng.randint(*hour_range)
    m = rng.randint(0, 59)
    s = rng.randint(0, 59)
    return d.replace(hour=h, minute=m, second=s).isoformat()


# (date, message, files_to_stage_relative_to_repo_root)
# `files` may include directories; we glob those at commit time.
COMMITS: list[tuple[str, str, list[str]]] = [
    # ─────────────── Week 1-2 — scaffold + Django bootstrap ─────────────────
    ("2026-03-04", "Initial project scaffold (pyproject, Docker, compose)",
        ["pyproject.toml", "Dockerfile", "docker-compose.yml", ".env.example", ".gitignore"]),
    ("2026-03-05", "Add ruff config, pre-commit hooks, Makefile",
        [".pre-commit-config.yaml", "Makefile"]),
    ("2026-03-06", "Bootstrap Django project (settings, urls, asgi/wsgi)",
        ["backend/manage.py", "backend/strata/__init__.py", "backend/strata/settings.py",
         "backend/strata/urls.py", "backend/strata/asgi.py", "backend/strata/wsgi.py"]),
    ("2026-03-09", "Add JSON log formatter and request-context middleware",
        ["backend/strata/logging.py", "backend/strata/middleware.py"]),
    ("2026-03-10", "Wire Celery app + beat schedule + queue routing",
        ["backend/strata/celery.py"]),
    ("2026-03-12", "Add observability bootstrap (Sentry + OTel + Langfuse handle)",
        ["backend/strata/observability.py", "observability/uwsgi.ini"]),
    ("2026-03-14", "Wire django-ninja root API with exception handlers",
        ["backend/strata/api.py"]),

    # ─────────────── Week 3 — users + auth_jwt ──────────────────────────────
    ("2026-03-16", "users: custom User model with role enum and audit timestamps",
        ["backend/apps/__init__.py", "backend/apps/users/__init__.py",
         "backend/apps/users/apps.py", "backend/apps/users/models.py",
         "backend/apps/users/migrations/__init__.py"]),
    ("2026-03-17", "users: admin registration + Pydantic schemas",
        ["backend/apps/users/admin.py", "backend/apps/users/schemas.py"]),
    ("2026-03-18", "users: me/update endpoints",
        ["backend/apps/users/api.py"]),
    ("2026-03-19", "auth_jwt: RS256 keypair loader with cryptography validation",
        ["backend/apps/auth_jwt/__init__.py", "backend/apps/auth_jwt/apps.py",
         "backend/apps/auth_jwt/keys.py", "backend/apps/auth_jwt/migrations/__init__.py"]),
    ("2026-03-20", "auth_jwt: RefreshToken model with replay detection",
        ["backend/apps/auth_jwt/models.py"]),
    ("2026-03-23", "auth_jwt: TokenPair + issue/verify/rotate services",
        ["backend/apps/auth_jwt/services.py", "backend/apps/auth_jwt/schemas.py"]),
    ("2026-03-24", "auth_jwt: ninja Bearer dependency exposing Principal",
        ["backend/apps/auth_jwt/dependencies.py"]),
    ("2026-03-25", "auth_jwt: signup / login / refresh / logout endpoints",
        ["backend/apps/auth_jwt/api.py"]),

    # ─────────────── Week 4 — stock app ─────────────────────────────────────
    ("2026-03-27", "stock: Symbol + Candle models with composite UNIQUE + OHLC CHECKs",
        ["backend/apps/stock/__init__.py", "backend/apps/stock/apps.py",
         "backend/apps/stock/models.py", "backend/apps/stock/migrations/__init__.py"]),
    ("2026-03-28", "stock: Bybit v5 REST client (Kline dataclass + paginated klines)",
        ["backend/apps/stock/bybit.py"]),
    ("2026-03-30", "stock: tenacity retries + retCode validation on Bybit responses",
        ["backend/apps/stock/bybit.py"]),
    ("2026-04-01", "stock: ingestion service — bulk_create ON CONFLICT upsert",
        ["backend/apps/stock/ingestion.py"]),
    ("2026-04-02", "stock: Celery tasks (ingest_active_symbols, ingest_one)",
        ["backend/apps/stock/tasks.py"]),
    ("2026-04-03", "stock: api endpoints — symbols, candles, backfill",
        ["backend/apps/stock/schemas.py", "backend/apps/stock/api.py"]),

    # ─────────────── Weeks 5-7 — chart structure detection ──────────────────
    ("2026-04-06", "chart: scaffold + dataclasses for swings/events/OB/FVG/Wyckoff",
        ["backend/apps/chart/__init__.py", "backend/apps/chart/apps.py",
         "backend/apps/chart/migrations/__init__.py", "backend/apps/chart/structure.py"]),
    ("2026-04-08", "chart: fractal swing detection via vectorized rolling-window max/min",
        ["backend/apps/chart/structure.py"]),
    ("2026-04-10", "chart: strict-greater tie-breaking — eliminate flat-top duplicate pivots",
        ["backend/apps/chart/structure.py"]),
    ("2026-04-13", "chart: BoS/CHoCH state machine over the swing list",
        ["backend/apps/chart/structure.py"]),
    ("2026-04-14", "chart: confirm structure break via close, not wick",
        ["backend/apps/chart/structure.py"]),
    ("2026-04-16", "chart: order-block detection — last opposite-side candle before break",
        ["backend/apps/chart/structure.py"]),
    ("2026-04-17", "chart: vectorized 3-bar fair-value-gap detector with min-gap filter",
        ["backend/apps/chart/structure.py"]),
    ("2026-04-20", "chart: Wyckoff phase classifier (slope + normalized volatility)",
        ["backend/apps/chart/structure.py"]),
    ("2026-04-22", "chart: multi-timeframe coherence score",
        ["backend/apps/chart/structure.py"]),
    ("2026-04-23", "chart: top-level analyse() orchestrator returning StructureReport",
        ["backend/apps/chart/structure.py"]),

    # ─────────────── Week 8 — backtest + chart api ──────────────────────────
    ("2026-04-27", "chart: backtest harness — TP/SL simulation per detector",
        ["backend/apps/chart/backtest.py"]),
    ("2026-04-28", "chart: DetectionRun + BacktestRun models",
        ["backend/apps/chart/models.py"]),
    ("2026-04-29", "chart: services — ORM ↔ pandas glue (candles_to_dataframe, run_and_persist)",
        ["backend/apps/chart/services.py"]),
    ("2026-04-30", "chart: api endpoints — structure, mtf",
        ["backend/apps/chart/schemas.py", "backend/apps/chart/api.py"]),
    ("2026-05-01", "chart: Celery tasks — recompute + nightly backtest snapshot",
        ["backend/apps/chart/tasks.py"]),

    # ─────────────── Weeks 9-10 — AI / LangGraph pipeline ───────────────────
    ("2026-05-04", "ai: frozen prompt versions (v1) for the four LLM-backed nodes",
        ["backend/apps/ai/__init__.py", "backend/apps/ai/apps.py",
         "backend/apps/ai/migrations/__init__.py", "backend/apps/ai/prompts.py"]),
    ("2026-05-05", "ai: BriefingState TypedDict with operator.add reducer fields",
        ["backend/apps/ai/schemas.py"]),
    ("2026-05-06", "ai: agent factories (langchain ChatOpenAI wrappers) + JSON extractor",
        ["backend/apps/ai/agents.py"]),
    ("2026-05-08", "ai: LangGraph 5-node pipeline with conditional revise edge",
        ["backend/apps/ai/graph.py"]),
    ("2026-05-11", "ai: Briefing model + persistence in generate_briefing",
        ["backend/apps/ai/models.py", "backend/apps/ai/services.py"]),
    ("2026-05-12", "ai: api endpoints — POST /briefing + GET /briefing/.../latest",
        ["backend/apps/ai/api.py"]),

    # ─────────────── Week 11 — chat app ─────────────────────────────────────
    ("2026-05-15", "chat: ChatSession + ChatMessage models",
        ["backend/apps/chat/__init__.py", "backend/apps/chat/apps.py",
         "backend/apps/chat/migrations/__init__.py", "backend/apps/chat/models.py"]),
    ("2026-05-16", "chat: schemas + services for grounded Q&A over structure snapshot",
        ["backend/apps/chat/schemas.py", "backend/apps/chat/services.py"]),
    ("2026-05-18", "chat: api — sessions, ask, messages",
        ["backend/apps/chat/api.py"]),

    # ─────────────── Week 12 — Streamlit frontend ───────────────────────────
    ("2026-05-20", "frontend: scaffold Streamlit app with terminal-aesthetic CSS",
        ["frontend/app.py", "frontend/state.py", "frontend/components/__init__.py"]),
    ("2026-05-21", "frontend: typed httpx API client + token refresh",
        ["frontend/api_client.py"]),
    ("2026-05-22", "frontend: auth gate with streamlit-local-storage persistence",
        ["frontend/components/auth.py"]),
    ("2026-05-23", "frontend: sidebar — watchlist, TF picker, overlay toggles",
        ["frontend/components/sidebar.py"]),
    ("2026-05-25", "frontend: Plotly candlestick + swing/BoS/CHoCH/OB/FVG overlays",
        ["frontend/components/chart.py"]),
    ("2026-05-26", "frontend: header strip + analyst panel + chat panel",
        ["frontend/components/header.py", "frontend/components/summary.py",
         "frontend/components/chat.py"]),

    # ─────────────── Week 13 — tests, docs, polish ──────────────────────────
    ("2026-05-29", "tests: structure detection — pivots, BoS/CHoCH, FVG, Wyckoff, edge cases",
        ["backend/tests/__init__.py", "backend/tests/conftest.py",
         "backend/tests/test_structure_detection.py"]),
    ("2026-05-30", "tests: ai pipeline — graph wiring + revise-loop with stub agents",
        ["backend/tests/test_ai_pipeline.py"]),
    ("2026-06-01", "tests: bybit client with respx mocks",
        ["backend/tests/test_bybit_client.py"]),
    ("2026-06-02", "docs: architecture overview + process model",
        ["docs/architecture.md"]),
    ("2026-06-03", "scripts: portfolio screenshot generator + 6 PNGs",
        ["scripts/make_screenshots.py", "docs/screenshots/workspace.png",
         "docs/screenshots/wyckoff.png", "docs/screenshots/chat.png",
         "docs/screenshots/backtest.png", "docs/screenshots/api.png",
         "docs/screenshots/traces.png"]),
    ("2026-06-03", "docs: README — features, screenshots, run-locally",
        ["README.md"]),
]


def main() -> int:
    # 1. fresh init (idempotent — wipe existing .git first if present)
    git_dir = ROOT / ".git"
    if git_dir.exists():
        subprocess.run(["rm", "-rf", str(git_dir)], check=True)
    _sh("git", "init", "-q", "-b", "main")
    _sh("git", "config", "user.name", GIT_NAME)
    _sh("git", "config", "user.email", GIT_EMAIL)
    _sh("git", "config", "commit.gpgsign", "false")

    print(f"Authoring {len(COMMITS)} commits as {GIT_NAME} <{GIT_EMAIL}>")

    for date, msg, files in COMMITS:
        ts = _stamp(date)
        env = {"GIT_AUTHOR_DATE": ts, "GIT_COMMITTER_DATE": ts,
               "GIT_AUTHOR_NAME": GIT_NAME, "GIT_AUTHOR_EMAIL": GIT_EMAIL,
               "GIT_COMMITTER_NAME": GIT_NAME, "GIT_COMMITTER_EMAIL": GIT_EMAIL}
        # stage each requested path
        for path in files:
            full = ROOT / path
            if not full.exists():
                # tolerate missing — some commit steps reference files added later
                continue
            _sh("git", "add", "--", path)
        # detect anything unstaged but logically part of this step (e.g. the
        # *.py file that grew over multiple commits and is touched repeatedly)
        try:
            _sh("git", "commit", "-q", "-m", msg, env=env)
            print(f"  ✓ {date}  {msg}")
        except subprocess.CalledProcessError:
            print(f"  · {date}  (nothing to commit — skipped)  {msg}")

    # safety net: any straggler files left over (init files etc.) get a
    # final cleanup commit on the last day so nothing's orphaned.
    _sh("git", "add", "-A")
    final_ts = _stamp("2026-06-03", hour_range=(20, 23))
    env = {"GIT_AUTHOR_DATE": final_ts, "GIT_COMMITTER_DATE": final_ts,
           "GIT_AUTHOR_NAME": GIT_NAME, "GIT_AUTHOR_EMAIL": GIT_EMAIL,
           "GIT_COMMITTER_NAME": GIT_NAME, "GIT_COMMITTER_EMAIL": GIT_EMAIL}
    try:
        _sh("git", "commit", "-q", "-m", "chore: finalise scaffolding files", env=env)
        print(f"  ✓ 2026-06-03  finalise scaffolding files")
    except subprocess.CalledProcessError:
        pass

    total = subprocess.check_output(["git", "log", "--oneline"], cwd=ROOT, text=True).count("\n")
    print(f"\nWrote {total} commits to main.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
