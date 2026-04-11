#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting notification service..."
exec uvicorn app.main:socket_app --host 0.0.0.0 --port 8007 --workers 1
