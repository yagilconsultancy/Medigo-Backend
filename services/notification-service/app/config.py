from mediride_common.config import BaseServiceSettings


class NotificationSettings(BaseServiceSettings):
    SERVICE_NAME: str = "notification-service"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@mediride.com"
    PORT: int = 8007


settings = NotificationSettings()
