from pydantic_settings import BaseSettings


class BaseServiceSettings(BaseSettings):
    """Base settings shared across all services."""

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://mediride:dev_password@rabbitmq:5672/mediride"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # S3-compatible storage (MinIO in dev, AWS S3 in prod)
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_REGION: str = "us-east-1"
    S3_BUCKET_DOCUMENTS: str = "mediride-documents"

    # Google Maps API
    GOOGLE_MAPS_API_KEY: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}
