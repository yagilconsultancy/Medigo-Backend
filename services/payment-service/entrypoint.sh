#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting payment service..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8005 --workers 2
