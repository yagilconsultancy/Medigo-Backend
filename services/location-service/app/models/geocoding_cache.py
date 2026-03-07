import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class GeocodingCache(Base):
    __tablename__ = "geocoding_cache"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    address: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    formatted_address: Mapped[str] = mapped_column(String(500), nullable=False)
    place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_geocoding_cache_address_lower", func.lower("address")),
    )
