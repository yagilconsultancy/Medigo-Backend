from mediride_common.config import BaseServiceSettings


class RideSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-rides:5432/mediride_rides"
    SERVICE_NAME: str = "ride-service"
    PORT: int = 8003
    USER_SERVICE_URL: str = "http://user-service:8002"
    PAYMENT_SERVICE_URL: str = "http://payment-service:8005"
    RIDE_REQUEST_EXPIRY_SECONDS: int = 120
    SHARE_BASE_URL: str = "https://app.mediride.com"


settings = RideSettings()
