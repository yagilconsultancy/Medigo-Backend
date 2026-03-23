from mediride_common.config import BaseServiceSettings


class NotificationSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-notifications:5432/mediride_notifications"
    SERVICE_NAME: str = "notification-service"
    PORT: int = 8007

    # AWS SES
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    SES_CONFIGURATION_SET: str = ""
    EMAIL_FROM: str = "noreply@mediride.com"


settings = NotificationSettings()
