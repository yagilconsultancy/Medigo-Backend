#!/bin/bash
set -euo pipefail

# ===========================================
# Run all service migrations
# ===========================================

COMPOSE_FILE="deploy/docker-compose.staging.yml"
DC="docker compose -f $COMPOSE_FILE"

echo "Waiting for services to be ready..."
sleep 10

echo "Running auth-service migrations..."
$DC exec -T auth-service alembic upgrade head

echo "Running user-service migrations..."
$DC exec -T user-service alembic upgrade head

echo "Running ride-service migrations..."
$DC exec -T ride-service alembic upgrade head

echo "Running location-service migrations..."
$DC exec -T location-service alembic upgrade head

echo "Running payment-service migrations..."
$DC exec -T payment-service alembic upgrade head

echo "Running tracking-service migrations..."
$DC exec -T tracking-service alembic upgrade head

echo "Running notification-service migrations..."
$DC exec -T notification-service alembic upgrade head

echo ""
echo "All migrations completed!"
