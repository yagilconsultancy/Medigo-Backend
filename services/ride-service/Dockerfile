FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY libs/common /tmp/libs/common
RUN pip install --no-cache-dir /tmp/libs/common && rm -rf /tmp/libs

COPY services/ride-service/pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY services/ride-service/app ./app
COPY services/ride-service/alembic.ini .
COPY services/ride-service/alembic ./alembic
COPY services/ride-service/entrypoint.sh .

RUN chmod +x entrypoint.sh

RUN useradd --create-home appuser
USER appuser

EXPOSE 8003

CMD ["./entrypoint.sh"]
