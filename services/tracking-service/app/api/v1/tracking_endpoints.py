from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_publisher
from app.repositories.location_history_repo import LocationHistoryRepository
from app.repositories.tracking_session_repo import TrackingSessionRepository
from app.schemas.tracking import (
    LocationHistoryEntry,
    LocationHistoryResponse,
    TrackingSessionResponse,
)
from app.services.tracking_service import TrackingService
from mediride_common.auth.dependencies import get_current_user, require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_tracking_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> TrackingService:
    return TrackingService(
        session_repo=TrackingSessionRepository(session),
        history_repo=LocationHistoryRepository(session),
        publisher=publisher,
    )


@router.get("/{ride_id}", response_model=StandardResponse[TrackingSessionResponse])
async def get_tracking_session(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.RIDER, UserRole.DRIVER, UserRole.ADMIN])),
    service: TrackingService = Depends(_get_tracking_service),
):
    """Get current tracking session for a ride."""
    session = await service.get_session(ride_id)
    return StandardResponse(
        data=TrackingSessionResponse.model_validate(session),
        message="Tracking session retrieved",
    )


@router.get("/{ride_id}/history", response_model=StandardResponse[LocationHistoryResponse])
async def get_location_history(
    ride_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    user: UserClaims = Depends(require_role([UserRole.RIDER, UserRole.DRIVER, UserRole.ADMIN])),
    service: TrackingService = Depends(_get_tracking_service),
):
    """Get location history for a ride."""
    entries, total, session_id = await service.get_location_history(ride_id, offset, limit)
    return StandardResponse(
        data=LocationHistoryResponse(
            ride_id=ride_id,
            session_id=session_id,
            entries=[LocationHistoryEntry.model_validate(e) for e in entries],
            total=total,
        ),
        message="Location history retrieved",
    )


@router.get("/driver/current", response_model=StandardResponse[TrackingSessionResponse])
async def get_driver_current_session(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: TrackingService = Depends(_get_tracking_service),
):
    """Get driver's active tracking session."""
    session = await service.get_session_by_driver(user.id)
    return StandardResponse(
        data=TrackingSessionResponse.model_validate(session),
        message="Active tracking session retrieved",
    )
