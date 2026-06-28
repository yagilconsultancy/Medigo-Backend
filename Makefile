.PHONY: up down logs build migrate test lint seed seed-admin seed-rides clean

up:
	docker compose up -d

up-build:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

logs-%:
	docker compose logs -f $*

build:
	docker compose build

# Migrations
migrate:
	docker compose exec auth-service alembic upgrade head
	docker compose exec user-service alembic upgrade head

migrate-auth:
	docker compose exec auth-service alembic upgrade head

migrate-users:
	docker compose exec user-service alembic upgrade head

migration-auth:
	docker compose exec auth-service alembic revision --autogenerate -m "$(msg)"

migration-users:
	docker compose exec user-service alembic revision --autogenerate -m "$(msg)"

# Testing
test:
	docker compose exec auth-service pytest -v
	docker compose exec user-service pytest -v

test-auth:
	docker compose exec auth-service pytest -v

test-users:
	docker compose exec user-service pytest -v

# Linting
lint:
	docker compose exec auth-service ruff check .
	docker compose exec user-service ruff check .

# Seed data
seed:
	docker compose exec auth-service python -m scripts.seed_data

seed-admin:
	docker compose exec auth-service python -m scripts.seed_admin

seed-rides:
	docker compose exec ride-service python -m scripts.seed_data

# Clean
clean:
	docker compose down -v
	docker system prune -f
