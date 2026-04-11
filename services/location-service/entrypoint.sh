#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting location service..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8004 --workers 2
