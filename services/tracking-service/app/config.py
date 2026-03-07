from mediride_common.config import BaseServiceSettings


class TrackingSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-tracking:5432/mediride_tracking"
    SERVICE_NAME: str = "tracking-service"
    PORT: int = 8006
    LOCATION_SERVICE_URL: str = "http://location-service:8004"
    ETA_UPDATE_INTERVAL_SECONDS: int = 30


settings = TrackingSettings()
