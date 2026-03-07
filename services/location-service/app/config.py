from mediride_common.config import BaseServiceSettings


class LocationSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql+asyncpg://mediride:dev_password@postgres-locations:5432/mediride_locations"
    SERVICE_NAME: str = "location-service"
    PORT: int = 8004
    GEOCODING_CACHE_TTL_HOURS: int = 720  # 30 days


settings = LocationSettings()
