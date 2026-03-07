FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY libs/common /tmp/libs/common
RUN pip install --no-cache-dir /tmp/libs/common && rm -rf /tmp/libs

COPY services/location-service/pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY services/location-service/app ./app
COPY services/location-service/alembic.ini .
COPY services/location-service/alembic ./alembic

RUN useradd --create-home appuser
USER appuser

EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004", "--workers", "2"]
