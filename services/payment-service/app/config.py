from mediride_common.config import BaseServiceSettings


class PaymentSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-payments:5432/mediride_payments"
    SERVICE_NAME: str = "payment-service"
    PORT: int = 8005
    RIDE_SERVICE_URL: str = "http://ride-service:8003"
    WITHDRAWAL_FEE_PERCENT: float = 0.015  # 1.5%
    MIN_WITHDRAWAL_AMOUNT: float = 10.00

    # Moneris Payment Gateway
    MONERIS_CLIENT_ID: str = ""
    MONERIS_CLIENT_SECRET: str = ""
    MONERIS_STORE_ID: str = ""
    MONERIS_SANDBOX: bool = True  # False for production


settings = PaymentSettings()
