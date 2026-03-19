from mediride_common.config import BaseServiceSettings


class PaymentSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-payments:5432/mediride_payments"
    SERVICE_NAME: str = "payment-service"
    PORT: int = 8005
    RIDE_SERVICE_URL: str = "http://ride-service:8003"
    WITHDRAWAL_FEE_PERCENT: float = 0.015  # 1.5%
    MIN_WITHDRAWAL_AMOUNT: float = 10.00
    DEFAULT_CURRENCY: str = "CAD"

    # Stripe Payment Gateway
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""


settings = PaymentSettings()
