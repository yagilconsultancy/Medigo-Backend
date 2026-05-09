from pydantic import AliasChoices, Field

from mediride_common.config import BaseServiceSettings


class NotificationSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-notifications:5432/mediride_notifications"
    SERVICE_NAME: str = "notification-service"
    PORT: int = 8007

    # Internal service URLs
    USER_SERVICE_URL: str = "http://user-service:8002"

    # AWS SES (legacy)
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    SES_CONFIGURATION_SET: str = ""

    # SMTP (Gmail)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = Field(default="", validation_alias=AliasChoices("SMTP_USERNAME", "SMTP_USER"))
    SMTP_PASSWORD: str = ""  # Gmail App Password
    EMAIL_FROM: str = "noreply@mediride.com"


settings = NotificationSettings()
