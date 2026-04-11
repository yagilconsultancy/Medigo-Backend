#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting tracking service..."
exec uvicorn app.main:socket_app --host 0.0.0.0 --port 8006 --workers 1
