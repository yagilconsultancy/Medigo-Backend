FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install shared library
COPY libs/common /tmp/libs/common
RUN pip install --no-cache-dir /tmp/libs/common && rm -rf /tmp/libs

# Install service dependencies
COPY services/auth-service/pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy service code
COPY services/auth-service/app ./app
COPY services/auth-service/alembic.ini .
COPY services/auth-service/alembic ./alembic

RUN useradd --create-home appuser
USER appuser

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
