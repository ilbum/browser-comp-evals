.PHONY: up down logs up-infra migrate load-browsecomp eval-browsecomp worker api test lint fmt

PYTHONPATH := $(shell pwd)/packages:$(shell pwd)/apps
export PYTHONPATH

DATABASE_URL ?= postgresql+asyncpg://eval:eval@localhost:5432/eval_db
TEMPORAL_HOST ?= localhost:7233
TASK_COUNT ?= 10

# ── Infrastructure ────────────────────────────────────────────────────────────

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

up-infra:
	docker compose -f infra/docker-compose.yml up -d postgres temporal temporal-ui

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	DATABASE_URL=$(DATABASE_URL) alembic -c apps/api/alembic.ini upgrade head

migrate-down:
	DATABASE_URL=$(DATABASE_URL) alembic -c apps/api/alembic.ini downgrade -1

# ── Dataset ───────────────────────────────────────────────────────────────────

load-browsecomp:
	DATABASE_URL=$(DATABASE_URL) python scripts/load_browsecomp.py

# ── Eval ─────────────────────────────────────────────────────────────────────

eval-browsecomp:
	DATABASE_URL=$(DATABASE_URL) TEMPORAL_HOST=$(TEMPORAL_HOST) \
		python scripts/run_eval.py \
		--benchmark browsecomp \
		--task-count $(TASK_COUNT)

# ── Services ──────────────────────────────────────────────────────────────────

worker:
	DATABASE_URL=$(DATABASE_URL) TEMPORAL_HOST=$(TEMPORAL_HOST) \
		python -m api.workers.temporal_worker

api:
	DATABASE_URL=$(DATABASE_URL) TEMPORAL_HOST=$(TEMPORAL_HOST) \
		uvicorn api.main:app --reload --port 8000

# ── Dev ───────────────────────────────────────────────────────────────────────

test:
	pytest

lint:
	ruff check .

fmt:
	ruff format .

install:
	uv pip install -e ".[dev]"

show-run:
	DATABASE_URL=$(DATABASE_URL) python scripts/show_eval_run.py --eval-run-id $(RUN_ID)
