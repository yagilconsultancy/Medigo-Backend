from pydantic import model_validator
from pydantic_settings import BaseSettings

DEV_JWT_SECRET = "dev-secret-key-change-in-production"


class GatewaySettings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # JWT
    JWT_SECRET_KEY: str = DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"

    # Service URLs
    AUTH_SERVICE_URL: str = "http://auth-service:8001"
    USER_SERVICE_URL: str = "http://user-service:8002"
    RIDE_SERVICE_URL: str = "http://ride-service:8003"
    LOCATION_SERVICE_URL: str = "http://location-service:8004"
    PAYMENT_SERVICE_URL: str = "http://payment-service:8005"
    TRACKING_SERVICE_URL: str = "http://tracking-service:8006"
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8007"

    # Rate limiting
    REDIS_URL: str = "redis://redis:6379/0"
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Admin activity logging (fire-and-forget to auth-service)
    ACTIVITY_LOG_ENABLED: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _require_real_jwt_secret(self):
        if self.ENVIRONMENT == "production" and self.JWT_SECRET_KEY in ("", DEV_JWT_SECRET):
            raise ValueError("JWT_SECRET_KEY must be set in production")
        return self


settings = GatewaySettings()
