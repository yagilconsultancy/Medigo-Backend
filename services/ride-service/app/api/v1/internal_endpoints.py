"""Internal API endpoints for inter-service communication."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.ride_repo import RideRepository
from app.schemas.ride import RideResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal")


def _require_internal_service(
    x_internal_service: str | None = Header(None),
) -> str:
    if not x_internal_service:
        raise HTTPException(status_code=403, detail="Internal access only")
    return x_internal_service


class UpdateFareRequest(BaseModel):
    final_fare: float


@router.get("/rides/{ride_id}")
async def get_ride_internal(
    ride_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    repo = RideRepository(session)
    ride = await repo.get_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return RideResponse.model_validate(ride).model_dump(mode="json")


@router.get("/rides/driver/{driver_id}/completed")
async def get_driver_completed_rides(
    driver_id: UUID,
    page: int = 1,
    limit: int = 50,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    repo = RideRepository(session)
    offset = (page - 1) * limit
    rides, total = await repo.get_by_driver(driver_id, "completed", offset, limit)
    return {
        "rides": [RideResponse.model_validate(r).model_dump(mode="json") for r in rides],
        "total": total,
    }


@router.put("/rides/{ride_id}/fare")
async def update_ride_fare(
    ride_id: UUID,
    request: UpdateFareRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    repo = RideRepository(session)
    ride = await repo.get_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    await repo.update(ride_id, final_fare=request.final_fare)
    return {"updated": True, "ride_id": str(ride_id), "final_fare": request.final_fare}
