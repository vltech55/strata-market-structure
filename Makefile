.PHONY: help up down logs build keys migrate seed superuser test lint fmt typecheck backtest shell flower clean

COMPOSE := docker compose

help:
	@echo "Strata — developer commands"
	@echo "  make up           — start the full stack (postgres, redis, minio, backend, worker, beat, flower, streamlit)"
	@echo "  make down         — stop and remove containers (keeps volumes)"
	@echo "  make logs         — tail logs for every service"
	@echo "  make build        — rebuild images"
	@echo "  make keys         — generate the RS256 keypair under ./keys/"
	@echo "  make migrate      — apply Django migrations"
	@echo "  make seed         — load demo symbols and a small OHLCV fixture"
	@echo "  make superuser    — create a Django admin user"
	@echo "  make test         — run pytest"
	@echo "  make lint         — ruff lint"
	@echo "  make fmt          — ruff format + ruff --fix"
	@echo "  make typecheck    — mypy"
	@echo "  make backtest     — run the structure-detector backtest harness"
	@echo "  make shell        — Django shell"
	@echo "  make flower       — open Flower in browser (Celery monitor)"

up:
	$(COMPOSE) up -d --build
	@echo
	@echo "  Streamlit  →  http://localhost:8501"
	@echo "  API docs   →  http://localhost:8000/api/docs"
	@echo "  Flower     →  http://localhost:5555"
	@echo "  MinIO UI   →  http://localhost:9001"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

build:
	$(COMPOSE) build

keys:
	@mkdir -p keys
	@if [ ! -f keys/jwt-rs256-private.pem ]; then \
		openssl genpkey -algorithm RSA -out keys/jwt-rs256-private.pem -pkeyopt rsa_keygen_bits:4096; \
		openssl rsa -in keys/jwt-rs256-private.pem -pubout -out keys/jwt-rs256-public.pem; \
		chmod 600 keys/jwt-rs256-private.pem; \
		echo "✓ RS256 keypair generated under ./keys/"; \
	else \
		echo "  keys already exist — skipping"; \
	fi

migrate:
	$(COMPOSE) exec backend python manage.py migrate

seed:
	$(COMPOSE) exec backend python manage.py loaddata backend/fixtures/symbols.json
	$(COMPOSE) exec backend python manage.py seed_demo_candles --symbol BTCUSDT --interval 1h --bars 2000

superuser:
	$(COMPOSE) exec backend python manage.py createsuperuser

test:
	$(COMPOSE) exec backend pytest

lint:
	$(COMPOSE) exec backend ruff check backend/

fmt:
	$(COMPOSE) exec backend ruff format backend/
	$(COMPOSE) exec backend ruff check --fix backend/

typecheck:
	$(COMPOSE) exec backend mypy backend/

backtest:
	$(COMPOSE) exec backend python manage.py backtest --symbol BTCUSDT --interval 1h --detector all

shell:
	$(COMPOSE) exec backend python manage.py shell

flower:
	open http://localhost:5555 2>/dev/null || xdg-open http://localhost:5555 2>/dev/null || true

clean:
	$(COMPOSE) down -v
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov .coverage
