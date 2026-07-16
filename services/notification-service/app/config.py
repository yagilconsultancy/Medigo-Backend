from pydantic import AliasChoices, Field

from mediride_common.config import BaseServiceSettings


class NotificationSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-notifications:5432/mediride_notifications"
    SERVICE_NAME: str = "notification-service"
    PORT: int = 8007

    # Internal service URLs
    USER_SERVICE_URL: str = "http://user-service:8002"
    PAYMENT_SERVICE_URL: str = "http://payment-service:8005"

    # AWS SES (legacy)
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    SES_CONFIGURATION_SET: str = ""

    # SMTP (Mailgun)
    SMTP_HOST: str = "smtp.mailgun.org"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_USERNAME", "SMTP_USER", "SMTP_LOGIN"),
    )
    SMTP_PASSWORD: str = Field(default="", validation_alias=AliasChoices("SMTP_PASSWORD", "SMTP_PASS"))
    SMTP_STARTTLS: bool = True
    SMTP_USE_TLS: bool = False
    SMTP_TIMEOUT_SECONDS: int = 30
    EMAIL_FROM: str = "noreply@mail.getmedigo.com"
    # Partner (fleet) emails send through the same SMTP account as every other
    # email; only the Reply-To differs so applicant replies reach the partners
    # inbox. No separate partner SMTP login.
    PARTNERS_EMAIL_REPLY_TO: str = "partners@mail.getmedigo.com"

    # Ops alerts: who gets notified when a new ride is booked.
    # Comma-separated; set to an empty string to disable the alert.
    ADMIN_BOOKING_ALERT_EMAILS: str = "admin@getmedigo.com"
    BACKOFFICE_URL: str = "https://backoffice.getmedigo.com"

    @property
    def admin_booking_alert_recipients(self) -> list[str]:
        return [
            email.strip()
            for email in self.ADMIN_BOOKING_ALERT_EMAILS.split(",")
            if email.strip()
        ]


settings = NotificationSettings()
