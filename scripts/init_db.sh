#!/bin/bash
# Initialize all service databases
# This script is for local development setup

echo "Waiting for PostgreSQL instances to be ready..."
sleep 5

echo "Running auth-service migrations..."
docker compose exec auth-service alembic upgrade head

echo "Running user-service migrations..."
docker compose exec user-service alembic upgrade head

echo "All migrations completed!"
