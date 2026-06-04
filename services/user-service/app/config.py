from mediride_common.config import BaseServiceSettings


class UserSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-users:5432/mediride_users"
    SERVICE_NAME: str = "user-service"
    PORT: int = 8002
    INVITE_TOKEN_EXPIRE_DAYS: int = 7
    PAYMENT_SERVICE_URL: str = "http://payment-service:8005"
    AUTH_SERVICE_URL: str = "http://auth-service:8001"
    RIDE_SERVICE_URL: str = "http://ride-service:8003"

    # Default password for newly created drivers
    DEFAULT_DRIVER_PASSWORD: str = "MediRide2026!"

    # Default password for newly created admins
    DEFAULT_ADMIN_PASSWORD: str = "MediAdmin2026!"


settings = UserSettings()
