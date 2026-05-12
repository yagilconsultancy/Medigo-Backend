FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY libs/common /tmp/libs/common
RUN pip install --no-cache-dir /tmp/libs/common && rm -rf /tmp/libs

COPY services/api-gateway/pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY services/api-gateway/app ./app
COPY services/api-gateway/entrypoint.sh .

RUN chmod +x entrypoint.sh

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["./entrypoint.sh"]
