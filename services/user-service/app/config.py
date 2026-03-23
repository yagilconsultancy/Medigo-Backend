from mediride_common.config import BaseServiceSettings


class UserSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-users:5432/mediride_users"
    SERVICE_NAME: str = "user-service"
    PORT: int = 8002
    INVITE_TOKEN_EXPIRE_DAYS: int = 7
    PAYMENT_SERVICE_URL: str = "http://payment-service:8005"


settings = UserSettings()
