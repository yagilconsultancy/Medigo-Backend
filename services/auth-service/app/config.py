from mediride_common.config import BaseServiceSettings


class AuthSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-auth:5432/mediride_auth"
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 3
    OTP_MAX_REQUESTS_PER_HOUR: int = 5
    # The driver activation code arrives in a welcome email the driver may not
    # open for days, so it lives much longer than a login OTP (7 days).
    DRIVER_ACTIVATION_CODE_EXPIRE_MINUTES: int = 7 * 24 * 60
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    SERVICE_NAME: str = "auth-service"
    PORT: int = 8001
    USER_SERVICE_URL: str = "http://user-service:8002"
    # Sign in with Apple / Google. Comma separated client ids the identity token
    # must be issued for (Apple: app bundle id and web Service ID; Google: the
    # iOS, Android and web client ids). Empty means that provider is switched off.
    GOOGLE_CLIENT_IDS: str = ""
    APPLE_CLIENT_IDS: str = ""


settings = AuthSettings()
