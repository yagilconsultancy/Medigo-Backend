#!/bin/bash
set -e

if [ -f alembic.ini ] && command -v alembic >/dev/null 2>&1; then
    echo "Running database migrations..."
    alembic upgrade head
fi

echo "Starting API gateway..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
