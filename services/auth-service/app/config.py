from mediride_common.config import BaseServiceSettings


class AuthSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-auth:5432/mediride_auth"
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 3
    OTP_MAX_REQUESTS_PER_HOUR: int = 5
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    SERVICE_NAME: str = "auth-service"
    PORT: int = 8001


settings = AuthSettings()
