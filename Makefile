# Curio task runner.  Run `make help` to list targets.
# The app runs on Python 3.14 via uv; infra (db, redis, ollama) runs in Docker.
.DEFAULT_GOAL := help
.PHONY: help infra up down logs test lint fmt fmt-check types check migrate migrations superuser shell pull-model

help:  ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

infra:  ## Start only the infra (db, redis, ollama) for the host fast-loop
	docker compose up -d db redis ollama

up:  ## Build and start the full stack
	docker compose up --build

down:  ## Stop the stack
	docker compose down

logs:  ## Tail logs
	docker compose logs -f

test:  ## Run the test suite
	uv run pytest

lint:  ## Lint
	uv run ruff check .

fmt:  ## Format code
	uv run ruff format .

fmt-check:  ## Check formatting (no changes)
	uv run ruff format --check .

types:  ## Type-check
	uv run mypy src

check: lint fmt-check types test  ## Full local quality gate (same as /verify)

migrate:  ## Apply migrations
	uv run python manage.py migrate

migrations:  ## Make migrations
	uv run python manage.py makemigrations

superuser:  ## Create a Django superuser
	uv run python manage.py createsuperuser

shell:  ## Django shell (auto-imports models on 5.2)
	uv run python manage.py shell

pull-model:  ## Pull qwen3:8b into the ollama service (first run only)
	docker compose exec ollama ollama pull qwen3:8b