.PHONY: dev infra test lint build up down bench migrate
infra:
	docker compose -f docker-compose.dev.yml up -d --wait
migrate:
	cd backend && uv run alembic upgrade head
dev: infra migrate
	@echo "Run: (cd backend && uv run uvicorn app.main:create_app --factory --reload) ; (cd agent && uv run python -m voice_agent.worker dev) ; (cd frontend && npm run dev)"
test:
	cd backend && uv run pytest -q
	cd agent && uv run pytest -q
lint:
	cd backend && uv run ruff check . && uv run mypy app
	cd agent && uv run ruff check .
build:
	docker compose build
up:
	docker compose up -d --build --wait
down:
	docker compose down
bench:
	cd benchmarks && uv run python latency.py
