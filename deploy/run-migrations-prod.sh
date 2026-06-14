#!/bin/bash
set -euo pipefail

# ===========================================
# Run all service migrations (Production)
# ===========================================

COMPOSE_FILE="deploy/docker-compose.prod.yml"
DC="docker compose -f $COMPOSE_FILE"

echo "Waiting for services to be ready..."
sleep 10

SERVICES=("auth-service" "user-service" "ride-service" "location-service" "payment-service" "tracking-service" "notification-service")

for SERVICE in "${SERVICES[@]}"; do
    echo "Running $SERVICE migrations..."
    $DC exec -T "$SERVICE" alembic upgrade head
done

echo ""
echo "All migrations completed!"
