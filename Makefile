.PHONY: install dev-up dev-down migrate seed test lint typecheck format e2e docs clean

install:
	uv sync --all-packages

dev-up:
	docker compose -f docker-compose.yml up -d --build
	@echo "Waiting for services to be healthy..."
	@sleep 10
	$(MAKE) migrate

dev-down:
	docker compose -f docker-compose.yml down

migrate:
	uv run alembic -c migrations/alembic.ini upgrade head

seed:
	uv run python scripts/seed.py

test:
	uv run pytest tests/unit -v --tb=short

lint:
	uv run ruff check .

typecheck:
	uv run mypy packages apps services --ignore-missing-imports

format:
	uv run ruff format .
	uv run ruff check --fix .

e2e:
	uv run pytest tests/end-to-end -v --tb=short

docs:
	@echo "API docs available at http://localhost:8000/docs when API is running"

clean:
	docker compose -f docker-compose.yml down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
