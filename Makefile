.PHONY: up down logs build migrate test lint seed seed-admin seed-rides clean \
	prod-ssh deploy deploy-build prod-migrate prod-logs prod-ps prod-up prod-down prod-key

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

# ===========================================
# Production deployment (remote EC2)
# ===========================================
# Override any of these per-command, e.g.  make deploy PROD_HOST=1.2.3.4
PROD_HOST     ?= 15.222.199.206
PROD_USER     ?= ec2-user
SSH_KEY       ?= medigo-prod
APP_DIR       ?= /opt/mediride
PROD_COMPOSE  ?= deploy/docker-compose.prod.yml

# PubkeyAcceptedAlgorithms re-enables the RSA-SHA2 signatures for the RSA key
# (newer OpenSSH disables ssh-rsa by default -> "Permission denied (publickey)").
SSH = ssh -i $(SSH_KEY) -o StrictHostKeyChecking=accept-new \
	-o PubkeyAcceptedAlgorithms=+ssh-rsa,rsa-sha2-512,rsa-sha2-256 \
	-o IdentitiesOnly=yes $(PROD_USER)@$(PROD_HOST)
# --env-file is required: with -f deploy/..., compose looks for .env next to the
# compose file, but the real .env lives in $(APP_DIR). Without this every secret
# (RDS_PASSWORD, JWT_SECRET_KEY, ...) interpolates to blank and would recreate
# the live containers with empty config.
DC_PROD = docker compose --env-file .env -f $(PROD_COMPOSE)

# SSH refuses keys with loose permissions; fix them before connecting.
prod-key:
	@chmod 600 $(SSH_KEY)

# Open an interactive shell on the production server.
prod-ssh: prod-key
	$(SSH)

# Full update: pull latest code, rebuild & restart, then run migrations.
deploy: prod-key
	$(SSH) 'cd $(APP_DIR) && git pull && $(DC_PROD) up -d --build && bash deploy/run-migrations-prod.sh'

# Rebuild & restart only (no migrations).
deploy-build: prod-key
	$(SSH) 'cd $(APP_DIR) && git pull && $(DC_PROD) up -d --build'

# Run all service migrations on prod.
prod-migrate: prod-key
	$(SSH) 'cd $(APP_DIR) && bash deploy/run-migrations-prod.sh'

# Tail prod logs (all services).  Single service:  make prod-logs SERVICE=ride-service
prod-logs: prod-key
	$(SSH) 'cd $(APP_DIR) && $(DC_PROD) logs -f --tail=100 $(SERVICE)'

# Show running prod containers.
prod-ps: prod-key
	$(SSH) 'cd $(APP_DIR) && $(DC_PROD) ps'

# Start / stop prod stack without rebuilding.
prod-up: prod-key
	$(SSH) 'cd $(APP_DIR) && $(DC_PROD) up -d'

prod-down: prod-key
	$(SSH) 'cd $(APP_DIR) && $(DC_PROD) down'
