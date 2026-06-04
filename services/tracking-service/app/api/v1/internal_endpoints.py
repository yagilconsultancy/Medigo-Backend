"""Internal API endpoints for inter-service communication."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.tracking_session_repo import TrackingSessionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal")


def _require_internal_service(
    x_internal_service: str | None = Header(None),
) -> str:
    if not x_internal_service:
        raise HTTPException(status_code=403, detail="Internal access only")
    return x_internal_service


@router.get("/{ride_id}/driver-location")
async def get_driver_location(
    ride_id: UUID,
    _caller: str = Depends(_require_internal_service),
    db: AsyncSession = Depends(get_db),
):
    """Return the driver's last known GPS position for a ride."""
    repo = TrackingSessionRepository(db)
    session = await repo.get_active_by_ride_id(ride_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active tracking session for this ride")

    return {
        "ride_id": str(session.ride_id),
        "driver_id": str(session.driver_id),
        "latitude": float(session.current_latitude) if session.current_latitude else None,
        "longitude": float(session.current_longitude) if session.current_longitude else None,
    }
