from mediride_common.config import BaseServiceSettings


class NotificationSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-notifications:5432/mediride_notifications"
    SERVICE_NAME: str = "notification-service"
    PORT: int = 8007
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@mediride.com"


settings = NotificationSettings()
