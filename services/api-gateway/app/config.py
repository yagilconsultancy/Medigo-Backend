from pydantic_settings import BaseSettings


class GatewaySettings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # JWT
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"

    # Service URLs
    AUTH_SERVICE_URL: str = "http://auth-service:8001"
    USER_SERVICE_URL: str = "http://user-service:8002"
    RIDE_SERVICE_URL: str = "http://ride-service:8003"
    LOCATION_SERVICE_URL: str = "http://location-service:8004"
    PAYMENT_SERVICE_URL: str = "http://payment-service:8005"
    TRACKING_SERVICE_URL: str = "http://tracking-service:8006"

    # Rate limiting
    REDIS_URL: str = "redis://redis:6379/0"
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = GatewaySettings()
