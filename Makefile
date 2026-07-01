.PHONY: up down logs build migrate test lint seed clean deploy deploy-staging

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

# Clean
clean:
	docker compose down -v
	docker system prune -f

# Deploy — pushes the current commit to the branch that triggers the
# corresponding GitHub Actions deploy workflow (see .github/workflows/).
#   deploy         -> prod    (pushes HEAD to `pro`,  deploys prod-api.getmedigo.com)
#   deploy-staging -> staging (pushes HEAD to `main`, deploys staging.getmedigo.com)
deploy:
	@echo "Deploying current commit ($$(git rev-parse --short HEAD)) to PRODUCTION via branch 'pro'..."
	git push origin HEAD:pro

deploy-staging:
	@echo "Deploying current commit ($$(git rev-parse --short HEAD)) to STAGING via branch 'main'..."
	git push origin HEAD:main
